require "rails_helper"

RSpec.describe Games::GameResult do
  describe "#over?" do
    it "returns false for in_progress" do
      result = Games::GameResult.new(status: :in_progress)
      expect(result.over?).to be false
    end

    it "returns true for win" do
      result = Games::GameResult.new(status: :win, winners: ["red"], losers: ["black"])
      expect(result.over?).to be true
    end

    it "returns true for draw" do
      result = Games::GameResult.new(status: :draw, draws: ["p1", "p2"])
      expect(result.over?).to be true
    end
  end

  describe "#draw?" do
    it "returns true for draw status" do
      result = Games::GameResult.new(status: :draw)
      expect(result.draw?).to be true
    end

    it "returns false for win status" do
      result = Games::GameResult.new(status: :win)
      expect(result.draw?).to be false
    end
  end
end
