require "rails_helper"

RSpec.describe Games::Checkers::LLMAdapter do
  let(:definition) { Games::Checkers::Definition.new }
  let(:adapter) { Games::Checkers::LLMAdapter.new(definition) }

  describe "#state_summary" do
    it "describes piece counts and current turn" do
      state = definition.new_game
      summary = adapter.state_summary(state, perspective: "red")

      expect(summary).to include("12")
      expect(summary).to include("Red")
    end

    it "mentions kings when present" do
      state = definition.new_game
      state[:board][0][1] = "R"  # Add a king
      summary = adapter.state_summary(state, perspective: "red")

      expect(summary).to include("king")
    end
  end

  describe "#describe_moves" do
    it "returns descriptions for each move" do
      state = definition.new_game
      moves = definition.legal_moves(state, "red")
      descriptions = adapter.describe_moves(moves, state: state)

      expect(descriptions.length).to eq(moves.length)
      descriptions.each do |desc|
        expect(desc).to have_key(:move)
        expect(desc).to have_key(:description)
        expect(desc[:description]).to be_a(String)
      end
    end

    it "mentions captures in description" do
      move = { from: [4, 3], to: [2, 5], captures: [[3, 4]] }
      descriptions = adapter.describe_moves([move], state: definition.new_game)
      expect(descriptions.first[:description]).to include("captur")
    end
  end
end
