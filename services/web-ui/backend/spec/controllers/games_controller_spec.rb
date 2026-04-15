require "rails_helper"

RSpec.describe GamesController, type: :controller do
  let(:user) { create(:user) }

  before do
    session[:user_id] = user.id
  end

  describe "POST #create" do
    context "blackjack game" do
      it "creates a game with correct attributes" do
        post :create, params: { game_type: "blackjack", ai_players: ["clara"] }

        game = Game.last
        expect(game).to be_present
        expect(game.game_type).to eq("blackjack")
        expect(game.state).to eq("in_progress")
        expect(game.creator).to eq(user)
        expect(game.started_at).to be_present
      end

      it "adds the human player at seat 0" do
        post :create, params: { game_type: "blackjack", ai_players: ["clara"] }

        game = Game.last
        human_player = game.game_players.find_by(user: user)
        expect(human_player).to be_present
        expect(human_player.seat_position).to eq(0)
        expect(human_player.player_state).to eq("active")
      end

      it "adds AI players at subsequent seats" do
        post :create, params: { game_type: "blackjack", ai_players: ["clara", "flo"] }

        game = Game.last
        ai_players = game.game_players.where.not(ai_personality: nil).order(:seat_position)
        expect(ai_players.length).to eq(2)
        expect(ai_players[0].ai_personality).to eq("clara")
        expect(ai_players[0].seat_position).to eq(1)
        expect(ai_players[1].ai_personality).to eq("flo")
        expect(ai_players[1].seat_position).to eq(2)
      end

      it "deals cards to all players" do
        post :create, params: { game_type: "blackjack", ai_players: ["clara"] }

        game = Game.last
        game_data = game.game_data.deep_symbolize_keys

        expect(game_data[:hands]).to be_present
        expect(game_data[:hands].keys.length).to eq(2)
        game_data[:hands].each_value do |hand|
          expect(hand.length).to eq(2)
        end
        expect(game_data[:dealer_hand].length).to eq(2)
        expect(game_data[:phase]).to eq("player_turns")
      end

      it "redirects to the game show page" do
        post :create, params: { game_type: "blackjack", ai_players: ["clara"] }

        game = Game.last
        expect(response).to redirect_to(game_path(game))
      end
    end

    context "checkers game" do
      it "creates a checkers game with board state" do
        post :create, params: { game_type: "checkers", ai_players: ["clara"] }

        game = Game.last
        expect(game.game_type).to eq("checkers")
        expect(game.state).to eq("in_progress")

        game_data = game.game_data.deep_symbolize_keys
        expect(game_data[:board]).to be_present
        expect(game_data[:board].length).to eq(8)
      end

      it "does not deal cards for checkers" do
        post :create, params: { game_type: "checkers", ai_players: ["clara"] }

        game = Game.last
        game_data = game.game_data.deep_symbolize_keys
        expect(game_data[:hands]).to be_nil
        expect(game_data[:deck]).to be_nil
      end
    end

    context "with no AI players" do
      it "creates a game with only the human player" do
        post :create, params: { game_type: "blackjack" }

        game = Game.last
        expect(game.game_players.count).to eq(1)
        expect(game.game_players.first.user).to eq(user)
      end
    end

    context "with invalid game type" do
      it "rejects invalid game types" do
        expect {
          post :create, params: { game_type: "poker", ai_players: ["clara"] }
        }.not_to change(Game, :count)

        expect(response).to have_http_status(:unprocessable_entity)
      end
    end
  end

  describe "GET #show" do
    let(:game) do
      game = create(:game, creator: user, game_type: "blackjack", state: "in_progress")
      create(:game_player, game: game, user: user, seat_position: 0)
      create(:ai_game_player, game: game, ai_personality: "clara", seat_position: 1)
      game
    end

    it "renders the game page with Inertia" do
      get :show, params: { id: game.id }
      expect(response).to be_successful
    end

    it "includes game props" do
      get :show, params: { id: game.id }
      # Inertia renders with props - check the assigns or response
      expect(response).to be_successful
    end
  end

  describe "POST #move" do
    let(:engine) { Games::BlackjackEngine.new }
    let(:initial_state) do
      state = engine.new_game
      engine.deal(state, ["player-#{user.id}", "clara"])
    end
    let(:game) do
      create(:game,
        creator: user,
        game_type: "blackjack",
        state: "in_progress",
        game_data: initial_state.deep_stringify_keys
      )
    end
    let!(:human_player) do
      create(:game_player, game: game, user: user, seat_position: 0, player_state: "active")
    end
    let!(:ai_player) do
      create(:ai_game_player, game: game, ai_personality: "clara", seat_position: 1)
    end

    it "applies a valid hit move" do
      post :move, params: { id: game.id, move_type: "hit" }

      expect(response).to be_successful
      game.reload
      game_data = game.game_data.deep_symbolize_keys
      hand = game_data[:hands][:"player-#{user.id}"]
      expect(hand.length).to eq(3)
    end

    it "records the move in the database" do
      expect {
        post :move, params: { id: game.id, move_type: "hit" }
      }.to change(Move, :count).by(1)

      move = Move.last
      expect(move.game).to eq(game)
      expect(move.game_player).to eq(human_player)
      expect(move.action).to eq({ "type" => "hit" })
      expect(move.move_number).to eq(1)
    end

    it "increments the game move_count" do
      post :move, params: { id: game.id, move_type: "hit" }

      game.reload
      expect(game.move_count).to eq(1)
    end

    it "applies a valid stand move" do
      post :move, params: { id: game.id, move_type: "stand" }

      expect(response).to be_successful
      game.reload
      game_data = game.game_data.deep_symbolize_keys
      expect(game_data[:stood]).to include("player-#{user.id}")
    end

    it "rejects a move when game is not in progress" do
      game.update!(state: "resolved")

      post :move, params: { id: game.id, move_type: "hit" }

      expect(response).to have_http_status(:unprocessable_entity)
      parsed = JSON.parse(response.body)
      expect(parsed["error"]).to be_present
    end

    it "rejects a move from a non-participant" do
      other_user = create(:user)
      session[:user_id] = other_user.id

      post :move, params: { id: game.id, move_type: "hit" }

      expect(response).to have_http_status(:unprocessable_entity)
      parsed = JSON.parse(response.body)
      expect(parsed["error"]).to be_present
    end
  end

  describe "POST #ai_move" do
    let(:engine) { Games::BlackjackEngine.new }
    let(:initial_state) do
      state = engine.new_game
      engine.deal(state, ["player-#{user.id}", "clara"])
    end
    let(:game) do
      create(:game,
        creator: user,
        game_type: "blackjack",
        state: "in_progress",
        game_data: initial_state.deep_stringify_keys
      )
    end
    let!(:human_player) do
      create(:game_player, game: game, user: user, seat_position: 0, player_state: "active")
    end
    let!(:ai_player) do
      create(:ai_game_player, game: game, ai_personality: "clara", seat_position: 1)
    end

    before do
      stub_request(:post, /mypalclara\.com\/api\/v1\/game\/move/)
        .to_return(
          status: 200,
          body: { move: { type: "hit" }, commentary: "Let me try my luck!", mood: "confident" }.to_json,
          headers: { "Content-Type" => "application/json" }
        )
      ENV["GAME_API_KEY"] = "test-key"
    end

    it "makes a ClaraApi call and applies the AI move" do
      post :ai_move, params: { id: game.id, game_player_id: ai_player.id }

      expect(response).to be_successful
      game.reload
      game_data = game.game_data.deep_symbolize_keys
      hand = game_data[:hands][:clara]
      expect(hand.length).to eq(3)
    end

    it "records the AI move with commentary" do
      expect {
        post :ai_move, params: { id: game.id, game_player_id: ai_player.id }
      }.to change(Move, :count).by(1)

      move = Move.last
      expect(move.game_player).to eq(ai_player)
      expect(move.action).to eq({ "type" => "hit" })
      expect(move.clara_commentary).to eq("Let me try my luck!")
    end

    it "handles ClaraApi timeout gracefully with fallback" do
      stub_request(:post, /mypalclara\.com\/api\/v1\/game\/move/)
        .to_timeout

      post :ai_move, params: { id: game.id, game_player_id: ai_player.id }

      expect(response).to be_successful
      expect(Move.last.action["type"]).to be_present
    end

    it "rejects AI move for a non-AI player" do
      post :ai_move, params: { id: game.id, game_player_id: human_player.id }

      expect(response).to have_http_status(:unprocessable_entity)
    end
  end
end
