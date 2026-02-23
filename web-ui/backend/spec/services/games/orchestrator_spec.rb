require "rails_helper"
require "webmock/rspec"

RSpec.describe Games::Orchestrator do
  let(:user) { create(:user) }
  let(:game) { create(:game, game_type: "checkers", state: "in_progress", creator: user) }
  let(:human_player) { create(:game_player, game: game, user: user, seat_position: 0) }
  let(:ai_player) { create(:ai_game_player, game: game, ai_personality: "clara", seat_position: 1) }
  let(:orchestrator) { Games::Orchestrator.new(game) }

  before do
    ENV["CLARA_API_URL"] = "https://test.example.com"
    ENV["GAME_API_KEY"] = "test-key"

    # Initialize game state
    definition = Games::Checkers::Definition.new
    state = definition.new_game
    game.update!(game_data: state)

    # Stub commentary calls
    stub_request(:post, "https://test.example.com/api/v1/game/event")
      .to_return(
        status: 200,
        body: { commentary: "Nice!", mood: "happy" }.to_json,
        headers: { "Content-Type" => "application/json" }
      )
  end

  describe "#human_move" do
    it "validates and applies a legal move" do
      human_player # ensure created
      legal = Games::Checkers::Definition.new.legal_moves(game.game_data.deep_symbolize_keys, "red")
      move = legal.first

      result = orchestrator.human_move(human_player, move)

      expect(result[:game]).to be_present
      game.reload
      expect(game.game_data.deep_symbolize_keys[:board][move[:from][0]][move[:from][1]]).to be_nil
    end

    it "records the move" do
      human_player
      legal = Games::Checkers::Definition.new.legal_moves(game.game_data.deep_symbolize_keys, "red")

      expect {
        orchestrator.human_move(human_player, legal.first)
      }.to change(Move, :count).by(1)
    end

    it "rejects illegal moves" do
      human_player
      illegal_move = { from: [0, 0], to: [7, 7] }

      result = orchestrator.human_move(human_player, illegal_move)
      expect(result[:error]).to be_present
    end
  end

  describe "#ai_move" do
    context "with traditional AI (checkers)" do
      it "picks and applies a move" do
        ai_player
        # Set it to black's turn
        state = game.game_data.deep_symbolize_keys
        state[:current_player] = "black"
        game.update!(game_data: state)

        result = orchestrator.ai_move(ai_player)

        expect(result[:move]).to be_present
        expect(result[:game]).to be_present
      end

      it "records the move with commentary" do
        ai_player
        state = game.game_data.deep_symbolize_keys
        state[:current_player] = "black"
        game.update!(game_data: state)

        expect {
          orchestrator.ai_move(ai_player)
        }.to change(Move, :count).by(1)

        move_record = Move.last
        expect(move_record.game_player).to eq(ai_player)
      end
    end
  end

  describe "#load_state" do
    it "normalizes string/symbol keys correctly" do
      # Simulate JSONB round-trip with string keys
      raw_state = { "board" => [[nil]], "current_player" => "red", "captured" => {} }
      game.update!(game_data: raw_state)

      state = orchestrator.send(:load_state)
      expect(state[:board]).to be_a(Array)
      expect(state[:current_player]).to eq("red")
    end
  end
end
