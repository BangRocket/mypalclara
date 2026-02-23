require "rails_helper"

RSpec.describe Games::Registry do
  describe ".package_for" do
    it "returns checkers package" do
      package = Games::Registry.package_for("checkers")

      expect(package[:definition]).to be_a(Games::Checkers::Definition)
      expect(package[:ai]).to be_a(Games::Checkers::AI)
      expect(package[:llm_adapter]).to be_a(Games::Checkers::LLMAdapter)
      expect(package[:client_adapter]).to be_a(Games::Checkers::ClientAdapter)
    end

    it "returns blackjack package" do
      package = Games::Registry.package_for("blackjack")

      expect(package[:definition]).to be_a(Games::Blackjack::Definition)
      expect(package[:ai]).to be_a(Games::Blackjack::AI)
      expect(package[:llm_adapter]).to be_a(Games::Blackjack::LLMAdapter)
      expect(package[:client_adapter]).to be_a(Games::Blackjack::ClientAdapter)
    end

    it "raises for unknown game type" do
      expect { Games::Registry.package_for("unknown") }.to raise_error(ArgumentError, /Unknown game type/)
    end

    it "shares the definition instance across components" do
      package = Games::Registry.package_for("checkers")
      expect(package[:ai].definition).to equal(package[:definition])
      expect(package[:llm_adapter].definition).to equal(package[:definition])
      expect(package[:client_adapter].definition).to equal(package[:definition])
    end
  end
end
