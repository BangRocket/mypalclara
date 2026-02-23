require "rails_helper"

RSpec.describe Games::ClientAdapter do
  let(:definition) { instance_double(Games::GameDefinition) }
  let(:adapter) { Games::ClientAdapter.new(definition) }

  describe "#initialize" do
    it "stores the definition" do
      expect(adapter.definition).to eq(definition)
    end
  end

  describe "#state_for_client" do
    it "raises NotImplementedError" do
      expect { adapter.state_for_client({}, perspective: "p1") }.to raise_error(NotImplementedError)
    end
  end

  describe "#available_actions" do
    it "raises NotImplementedError" do
      expect { adapter.available_actions({}, "p1") }.to raise_error(NotImplementedError)
    end
  end
end
