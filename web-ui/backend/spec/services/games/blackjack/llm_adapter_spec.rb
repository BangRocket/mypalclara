require "rails_helper"

RSpec.describe Games::Blackjack::LLMAdapter do
  let(:definition) { Games::Blackjack::Definition.new }
  let(:adapter) { Games::Blackjack::LLMAdapter.new(definition) }

  describe "#state_summary" do
    it "describes hand and dealer card" do
      state = {
        hands: { "clara" => ["KS", "7H"] },
        dealer_hand: ["10D", "3C"],
        phase: :player_turns
      }
      summary = adapter.state_summary(state, perspective: "clara")

      expect(summary).to include("17")   # hand value
      expect(summary).to include("10D")  # dealer showing
    end
  end

  describe "#describe_moves" do
    it "returns descriptions for each move" do
      moves = %w[hit stand double_down]
      descriptions = adapter.describe_moves(moves, state: {})

      expect(descriptions.length).to eq(3)
      descriptions.each do |desc|
        expect(desc).to have_key(:id)
        expect(desc).to have_key(:description)
      end
    end
  end
end
