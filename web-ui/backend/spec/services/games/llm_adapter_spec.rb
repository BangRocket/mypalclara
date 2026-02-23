require "rails_helper"

RSpec.describe Games::LLMAdapter do
  let(:definition) { instance_double(Games::GameDefinition) }
  let(:adapter) { Games::LLMAdapter.new(definition) }

  describe "#initialize" do
    it "stores the definition" do
      expect(adapter.definition).to eq(definition)
    end
  end

  describe "#state_summary" do
    it "raises NotImplementedError" do
      expect { adapter.state_summary({}, perspective: "p1") }.to raise_error(NotImplementedError)
    end
  end

  describe "#describe_moves" do
    it "raises NotImplementedError" do
      expect { adapter.describe_moves([], state: {}) }.to raise_error(NotImplementedError)
    end
  end

  describe "#relevant_history" do
    it "returns the last N entries from history" do
      history = (1..10).to_a
      expect(adapter.relevant_history(history, state: {})).to eq([6, 7, 8, 9, 10])
    end

    it "respects the limit parameter" do
      history = (1..10).to_a
      expect(adapter.relevant_history(history, state: {}, limit: 3)).to eq([8, 9, 10])
    end

    it "returns all entries when history is shorter than limit" do
      history = [1, 2]
      expect(adapter.relevant_history(history, state: {}, limit: 5)).to eq([1, 2])
    end
  end
end
