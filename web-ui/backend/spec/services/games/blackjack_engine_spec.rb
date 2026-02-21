require "rails_helper"

RSpec.describe Games::BlackjackEngine do
  let(:engine) { Games::BlackjackEngine.new }

  describe "#new_game" do
    it "creates a shuffled deck and empty hands" do
      state = engine.new_game
      expect(state[:deck].length).to eq(52)
      expect(state[:dealer_hand]).to eq([])
      expect(state[:phase]).to eq("dealing")
    end
  end

  describe "#deal" do
    it "deals two cards to each player and one to dealer" do
      state = engine.new_game
      player_ids = ["player-1", "player-2"]
      state = engine.deal(state, player_ids)

      expect(state[:hands]["player-1"].length).to eq(2)
      expect(state[:hands]["player-2"].length).to eq(2)
      expect(state[:dealer_hand].length).to eq(2)
      expect(state[:phase]).to eq("player_turns")
      expect(state[:deck].length).to eq(46)
    end
  end

  describe "#hand_value" do
    it "counts number cards at face value" do
      expect(engine.hand_value(["7♠", "3♥"])).to eq(10)
    end

    it "counts face cards as 10" do
      expect(engine.hand_value(["K♠", "Q♥"])).to eq(20)
    end

    it "counts ace as 11 when safe" do
      expect(engine.hand_value(["A♠", "7♥"])).to eq(18)
    end

    it "counts ace as 1 when 11 would bust" do
      expect(engine.hand_value(["A♠", "7♥", "8♦"])).to eq(16)
    end

    it "detects blackjack" do
      expect(engine.hand_value(["A♠", "K♥"])).to eq(21)
    end
  end

  describe "#legal_moves" do
    it "returns hit and stand for normal hand" do
      state = { hands: { "p1" => ["7♠", "3♥"] }, phase: "player_turns" }
      moves = engine.legal_moves(state, "p1")
      expect(moves).to include("hit", "stand")
    end

    it "returns empty for busted hand" do
      state = { hands: { "p1" => ["K♠", "Q♥", "5♦"] }, phase: "player_turns" }
      moves = engine.legal_moves(state, "p1")
      expect(moves).to eq([])
    end

    it "includes double_down on first two cards" do
      state = { hands: { "p1" => ["7♠", "3♥"] }, phase: "player_turns" }
      moves = engine.legal_moves(state, "p1")
      expect(moves).to include("double_down")
    end

    it "excludes double_down after hit" do
      state = { hands: { "p1" => ["7♠", "3♥", "2♦"] }, phase: "player_turns" }
      moves = engine.legal_moves(state, "p1")
      expect(moves).not_to include("double_down")
    end
  end

  describe "#apply_move" do
    it "adds a card on hit" do
      state = engine.new_game
      state = engine.deal(state, ["p1"])
      hand_before = state[:hands]["p1"].length
      state = engine.apply_move(state, "p1", "hit")
      expect(state[:hands]["p1"].length).to eq(hand_before + 1)
    end

    it "marks player as stood on stand" do
      state = engine.new_game
      state = engine.deal(state, ["p1"])
      state = engine.apply_move(state, "p1", "stand")
      expect(state[:stood]).to include("p1")
    end
  end

  describe "#resolve" do
    it "determines winners correctly" do
      state = {
        hands: { "p1" => ["K♠", "9♥"] },
        dealer_hand: ["K♦", "7♣"],
        deck: [],
        phase: "resolving",
        stood: ["p1"],
      }
      results = engine.resolve(state)
      expect(results["p1"]).to eq("won")
    end

    it "dealer wins on tie" do
      state = {
        hands: { "p1" => ["K♠", "8♥"] },
        dealer_hand: ["K♦", "8♣"],
        deck: [],
        phase: "resolving",
        stood: ["p1"],
      }
      results = engine.resolve(state)
      expect(results["p1"]).to eq("draw")
    end

    it "busted players lose" do
      state = {
        hands: { "p1" => ["K♠", "Q♥", "5♦"] },
        dealer_hand: ["K♦", "7♣"],
        deck: [],
        phase: "resolving",
        stood: [],
      }
      results = engine.resolve(state)
      expect(results["p1"]).to eq("lost")
    end
  end
end
