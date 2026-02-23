require "rails_helper"

RSpec.describe Games::GameAI do
  let(:definition) { instance_double(Games::GameDefinition) }
  let(:ai) { Games::GameAI.new(definition) }

  describe "#initialize" do
    it "stores the definition" do
      expect(ai.definition).to eq(definition)
    end
  end

  describe "#ai_type" do
    it "raises NotImplementedError" do
      expect { ai.ai_type }.to raise_error(NotImplementedError)
    end
  end

  describe "#pick_move" do
    it "raises NotImplementedError" do
      expect { ai.pick_move({}, "p1") }.to raise_error(NotImplementedError)
    end
  end

  describe "#evaluate_position" do
    it "returns 0.0 by default" do
      expect(ai.evaluate_position({}, "p1")).to eq(0.0)
    end
  end

  describe "#explain_move" do
    it "returns empty string by default" do
      expect(ai.explain_move({}, {})).to eq("")
    end
  end
end
