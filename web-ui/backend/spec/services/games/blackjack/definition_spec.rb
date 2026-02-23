require "rails_helper"

RSpec.describe Games::Blackjack::Definition do
  let(:definition) { Games::Blackjack::Definition.new }

  describe "#game_type" do
    it "returns 'blackjack'" do
      expect(definition.game_type).to eq("blackjack")
    end
  end

  describe "#new_game" do
    it "creates a deck of 52 cards" do
      state = definition.new_game
      expect(state[:deck].length).to eq(52)
    end

    it "creates empty hands" do
      state = definition.new_game
      expect(state[:dealer_hand]).to eq([])
      expect(state[:hands]).to eq({})
    end

    it "sets phase to :dealing symbol" do
      state = definition.new_game
      expect(state[:phase]).to eq(:dealing)
      expect(state[:phase]).to be_a(Symbol)
    end

    it "initializes current_player_index and turn_count" do
      state = definition.new_game
      expect(state[:current_player_index]).to eq(0)
      expect(state[:turn_count]).to eq(0)
    end
  end

  describe "#deal" do
    it "deals 2 cards to each player and 2 to dealer" do
      state = definition.new_game
      state = definition.deal(state, ["p1", "p2"])

      expect(state[:hands]["p1"].length).to eq(2)
      expect(state[:hands]["p2"].length).to eq(2)
      expect(state[:dealer_hand].length).to eq(2)
    end

    it "removes dealt cards from the deck" do
      state = definition.new_game
      state = definition.deal(state, ["p1", "p2"])

      # 52 - 2 players * 2 cards - 2 dealer cards = 46
      expect(state[:deck].length).to eq(46)
    end

    it "transitions phase to :player_turns" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])

      expect(state[:phase]).to eq(:player_turns)
      expect(state[:phase]).to be_a(Symbol)
    end
  end

  describe "#hand_value" do
    it "counts number cards at face value" do
      expect(definition.hand_value(["7\u2660", "3\u2665"])).to eq(10)
    end

    it "counts face cards as 10" do
      expect(definition.hand_value(["K\u2660", "Q\u2665"])).to eq(20)
    end

    it "counts J as 10" do
      expect(definition.hand_value(["J\u2660", "5\u2665"])).to eq(15)
    end

    it "counts ace as 11 when safe" do
      expect(definition.hand_value(["A\u2660", "7\u2665"])).to eq(18)
    end

    it "counts ace as 1 when 11 would bust" do
      expect(definition.hand_value(["A\u2660", "7\u2665", "8\u2666"])).to eq(16)
    end

    it "detects blackjack" do
      expect(definition.hand_value(["A\u2660", "K\u2665"])).to eq(21)
    end

    it "handles multiple aces" do
      # Two aces: 11 + 11 = 22, reduce one to 1 = 12
      expect(definition.hand_value(["A\u2660", "A\u2665"])).to eq(12)
    end
  end

  describe "#legal_moves" do
    it "returns hit and stand for a normal hand" do
      state = { hands: { "p1" => ["7\u2660", "3\u2665"] }, phase: :player_turns }
      moves = definition.legal_moves(state, "p1")
      expect(moves).to include("hit", "stand")
    end

    it "returns empty for a busted hand" do
      state = { hands: { "p1" => ["K\u2660", "Q\u2665", "5\u2666"] }, phase: :player_turns }
      moves = definition.legal_moves(state, "p1")
      expect(moves).to eq([])
    end

    it "includes double_down on first two cards" do
      state = { hands: { "p1" => ["7\u2660", "3\u2665"] }, phase: :player_turns }
      moves = definition.legal_moves(state, "p1")
      expect(moves).to include("double_down")
    end

    it "excludes double_down after hit" do
      state = { hands: { "p1" => ["7\u2660", "3\u2665", "2\u2666"] }, phase: :player_turns }
      moves = definition.legal_moves(state, "p1")
      expect(moves).not_to include("double_down")
    end

    it "returns empty for unknown player" do
      state = { hands: { "p1" => ["7\u2660", "3\u2665"] }, phase: :player_turns }
      moves = definition.legal_moves(state, "unknown")
      expect(moves).to eq([])
    end
  end

  describe "#apply_move" do
    it "accepts move as a hash with player and action keys" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      hand_before = state[:hands]["p1"].length

      state = definition.apply_move(state, { player: "p1", action: "hit" })
      expect(state[:hands]["p1"].length).to eq(hand_before + 1)
    end

    it "adds a card on hit" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      hand_before = state[:hands]["p1"].length

      state = definition.apply_move(state, { player: "p1", action: "hit" })
      expect(state[:hands]["p1"].length).to eq(hand_before + 1)
    end

    it "marks player as stood on stand" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])

      state = definition.apply_move(state, { player: "p1", action: "stand" })
      expect(state[:stood]).to include("p1")
    end

    it "adds a card and stands on double_down" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      hand_before = state[:hands]["p1"].length

      state = definition.apply_move(state, { player: "p1", action: "double_down" })
      expect(state[:hands]["p1"].length).to eq(hand_before + 1)
      expect(state[:stood]).to include("p1")
    end

    it "does not mutate the original state" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      original_hand = state[:hands]["p1"].dup

      definition.apply_move(state, { player: "p1", action: "hit" })
      expect(state[:hands]["p1"]).to eq(original_hand)
    end
  end

  describe "#phase" do
    it "returns the current phase from state" do
      state = definition.new_game
      expect(definition.phase(state)).to eq(:dealing)
    end

    it "returns :player_turns after dealing" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      expect(definition.phase(state)).to eq(:player_turns)
    end

    it "returns :resolving after dealer plays" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      state = definition.apply_move(state, { player: "p1", action: "stand" })
      state = definition.dealer_play(state)
      expect(definition.phase(state)).to eq(:resolving)
    end
  end

  describe "#players" do
    it "returns the player ids from hands" do
      state = definition.new_game
      state = definition.deal(state, ["p1", "p2"])
      expect(definition.players(state)).to contain_exactly("p1", "p2")
    end
  end

  describe "#current_player" do
    it "returns the current player based on index" do
      state = definition.new_game
      state = definition.deal(state, ["p1", "p2"])
      expect(definition.current_player(state)).to eq("p1")
    end

    it "returns nil when no players" do
      state = definition.new_game
      expect(definition.current_player(state)).to be_nil
    end
  end

  describe "#dealer_play" do
    it "draws until dealer reaches 17 or more" do
      state = {
        hands: { "p1" => ["K\u2660", "9\u2665"] },
        dealer_hand: ["6\u2666", "5\u2663"],
        deck: ["7\u2660", "3\u2665", "2\u2666", "K\u2665"],
        phase: :player_turns,
        stood: ["p1"],
        current_player_index: 0,
        turn_count: 0
      }

      state = definition.dealer_play(state)
      expect(definition.hand_value(state[:dealer_hand])).to be >= 17
      expect(state[:phase]).to eq(:resolving)
    end
  end

  describe "#resolve" do
    it "returns 'won' when player beats dealer" do
      state = {
        hands: { "p1" => ["K\u2660", "9\u2665"] },
        dealer_hand: ["K\u2666", "7\u2663"],
        deck: [],
        phase: :resolving,
        stood: ["p1"]
      }
      results = definition.resolve(state)
      expect(results["p1"]).to eq("won")
    end

    it "returns 'draw' on tie" do
      state = {
        hands: { "p1" => ["K\u2660", "8\u2665"] },
        dealer_hand: ["K\u2666", "8\u2663"],
        deck: [],
        phase: :resolving,
        stood: ["p1"]
      }
      results = definition.resolve(state)
      expect(results["p1"]).to eq("draw")
    end

    it "returns 'lost' when player busts" do
      state = {
        hands: { "p1" => ["K\u2660", "Q\u2665", "5\u2666"] },
        dealer_hand: ["K\u2666", "7\u2663"],
        deck: [],
        phase: :resolving,
        stood: []
      }
      results = definition.resolve(state)
      expect(results["p1"]).to eq("lost")
    end

    it "returns 'won' when dealer busts" do
      state = {
        hands: { "p1" => ["K\u2660", "7\u2665"] },
        dealer_hand: ["K\u2666", "7\u2663", "8\u2660"],
        deck: [],
        phase: :resolving,
        stood: ["p1"]
      }
      results = definition.resolve(state)
      expect(results["p1"]).to eq("won")
    end
  end

  describe "#winner" do
    it "returns nil before resolving phase" do
      state = definition.new_game
      expect(definition.winner(state)).to be_nil
    end

    it "returns nil during player_turns phase" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      expect(definition.winner(state)).to be_nil
    end

    it "returns a GameResult when in resolving phase with a winner" do
      state = {
        hands: { "p1" => ["K\u2660", "9\u2665"] },
        dealer_hand: ["K\u2666", "7\u2663"],
        deck: [],
        phase: :resolving,
        stood: ["p1"]
      }
      result = definition.winner(state)
      expect(result).to be_a(Games::GameResult)
      expect(result.winners).to include("p1")
      expect(result.status).to eq(:won)
    end

    it "returns a GameResult with losers when player loses" do
      state = {
        hands: { "p1" => ["K\u2660", "Q\u2665", "5\u2666"] },
        dealer_hand: ["K\u2666", "7\u2663"],
        deck: [],
        phase: :resolving,
        stood: []
      }
      result = definition.winner(state)
      expect(result).to be_a(Games::GameResult)
      expect(result.losers).to include("p1")
      expect(result.status).to eq(:lost)
    end

    it "returns a GameResult for draws" do
      state = {
        hands: { "p1" => ["K\u2660", "8\u2665"] },
        dealer_hand: ["K\u2666", "8\u2663"],
        deck: [],
        phase: :resolving,
        stood: ["p1"]
      }
      result = definition.winner(state)
      expect(result).to be_a(Games::GameResult)
      expect(result.status).to eq(:draw)
      expect(result.draws).to include("p1")
    end

    it "returns GameResult that responds to over?" do
      state = {
        hands: { "p1" => ["K\u2660", "9\u2665"] },
        dealer_hand: ["K\u2666", "7\u2663"],
        deck: [],
        phase: :resolving,
        stood: ["p1"]
      }
      result = definition.winner(state)
      expect(result.over?).to be true
    end
  end

  describe "#game_over?" do
    it "returns false before resolving" do
      state = definition.new_game
      expect(definition.game_over?(state)).to be false
    end

    it "returns true when game is resolved with a result" do
      state = {
        hands: { "p1" => ["K\u2660", "9\u2665"] },
        dealer_hand: ["K\u2666", "7\u2663"],
        deck: [],
        phase: :resolving,
        stood: ["p1"]
      }
      expect(definition.game_over?(state)).to be true
    end
  end
end
