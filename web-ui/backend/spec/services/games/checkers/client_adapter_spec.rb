require "rails_helper"

RSpec.describe Games::Checkers::ClientAdapter do
  let(:definition) { Games::Checkers::Definition.new }
  let(:adapter) { Games::Checkers::ClientAdapter.new(definition) }

  describe "#state_for_client" do
    it "includes board and current player" do
      state = definition.new_game
      client_state = adapter.state_for_client(state, perspective: "red")

      expect(client_state[:board]).to be_a(Array)
      expect(client_state[:current_player]).to eq("red")
    end
  end

  describe "#available_actions" do
    it "returns legal moves for current player" do
      state = definition.new_game
      actions = adapter.available_actions(state, "red")

      expect(actions).not_to be_empty
      actions.each do |action|
        expect(action).to have_key(:from)
        expect(action).to have_key(:to)
      end
    end

    it "returns empty for non-current player" do
      state = definition.new_game
      actions = adapter.available_actions(state, "black")
      expect(actions).to be_empty
    end
  end
end
