require "rails_helper"

RSpec.describe Games::Blackjack::AI do
  let(:definition) { Games::Blackjack::Definition.new }
  let(:ai) { Games::Blackjack::AI.new(definition) }

  describe "#ai_type" do
    it "returns :llm" do
      expect(ai.ai_type).to eq(:llm)
    end
  end

  describe "#evaluate_position" do
    it "returns -1.0 for busted hand" do
      state = { hands: { "p1" => ["KS", "QH", "5D"] }, dealer_hand: ["7C"] }
      expect(ai.evaluate_position(state, "p1")).to eq(-1.0)
    end

    it "returns high score for 21" do
      state = { hands: { "p1" => ["AS", "KH"] }, dealer_hand: ["7C"] }
      eval_score = ai.evaluate_position(state, "p1")
      expect(eval_score).to be > 0.8
    end

    it "returns moderate score for 17-19" do
      state = { hands: { "p1" => ["KS", "8H"] }, dealer_hand: ["7C"] }
      eval_score = ai.evaluate_position(state, "p1")
      expect(eval_score).to be_between(-0.5, 0.5)
    end

    it "returns low score for under 17" do
      state = { hands: { "p1" => ["7S", "5H"] }, dealer_hand: ["KD"] }
      eval_score = ai.evaluate_position(state, "p1")
      expect(eval_score).to be < 0.0
    end
  end

  describe "#explain_move" do
    it "explains hit" do
      state = { hands: { "p1" => ["7S", "5H"] }, dealer_hand: ["6C"] }
      explanation = ai.explain_move(state, { player: "p1", action: "hit" })
      expect(explanation).to be_a(String)
      expect(explanation).not_to be_empty
    end

    it "explains stand" do
      state = { hands: { "p1" => ["KS", "8H"] }, dealer_hand: ["6C"] }
      explanation = ai.explain_move(state, { player: "p1", action: "stand" })
      expect(explanation).to be_a(String)
      expect(explanation).not_to be_empty
    end
  end

  describe "#pick_move" do
    it "raises NotImplementedError (LLM-delegated)" do
      state = { hands: { "p1" => ["7S", "5H"] }, dealer_hand: ["6C"], phase: :player_turns }
      expect { ai.pick_move(state, "p1") }.to raise_error(NotImplementedError)
    end
  end
end
