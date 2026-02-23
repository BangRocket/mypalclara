require "rails_helper"

RSpec.describe Games::GameDefinition do
  let(:definition) { Games::GameDefinition.new }

  describe "interface methods raise NotImplementedError" do
    it "#game_type" do
      expect { definition.game_type }.to raise_error(NotImplementedError)
    end

    it "#new_game" do
      expect { definition.new_game }.to raise_error(NotImplementedError)
    end

    it "#legal_moves" do
      expect { definition.legal_moves({}, "p1") }.to raise_error(NotImplementedError)
    end

    it "#apply_move" do
      expect { definition.apply_move({}, {}) }.to raise_error(NotImplementedError)
    end

    it "#winner" do
      expect { definition.winner({}) }.to raise_error(NotImplementedError)
    end

    it "#current_player" do
      expect { definition.current_player({}) }.to raise_error(NotImplementedError)
    end

    it "#players" do
      expect { definition.players({}) }.to raise_error(NotImplementedError)
    end
  end

  describe "#game_over?" do
    it "delegates to winner" do
      allow(definition).to receive(:winner).and_return(nil)
      expect(definition.game_over?({})).to be false
    end

    it "returns true when winner returns a result" do
      result = Games::GameResult.new(status: :win)
      allow(definition).to receive(:winner).and_return(result)
      expect(definition.game_over?({})).to be true
    end
  end

  describe "#phase" do
    it "returns nil by default" do
      expect(definition.phase({})).to be_nil
    end
  end
end
