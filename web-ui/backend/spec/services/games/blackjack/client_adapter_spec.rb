require "rails_helper"

RSpec.describe Games::Blackjack::ClientAdapter do
  let(:definition) { Games::Blackjack::Definition.new }
  let(:adapter) { Games::Blackjack::ClientAdapter.new(definition) }

  describe "#state_for_client" do
    it "includes hands and phase" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      client_state = adapter.state_for_client(state, perspective: "p1")

      expect(client_state[:hands]).to be_a(Hash)
      expect(client_state[:phase]).to eq(:player_turns)
      expect(client_state[:dealer_hand]).to be_a(Array)
    end
  end

  describe "#available_actions" do
    it "returns legal moves for player" do
      state = { hands: { "p1" => ["7S", "3H"] }, phase: :player_turns }
      actions = adapter.available_actions(state, "p1")

      expect(actions).to include("hit", "stand", "double_down")
    end
  end
end
