require "rails_helper"

RSpec.describe Game, type: :model do
  describe "validations" do
    it "requires game_type" do
      game = build(:game, game_type: nil)
      expect(game).not_to be_valid
    end

    it "requires state" do
      game = build(:game, state: nil)
      expect(game).not_to be_valid
    end

    it "only allows valid game_types" do
      expect(build(:game, game_type: "blackjack")).to be_valid
      expect(build(:game, game_type: "checkers")).to be_valid
      expect(build(:game, game_type: "poker")).not_to be_valid
    end

    it "only allows valid states" do
      expect(build(:game, state: "waiting")).to be_valid
      expect(build(:game, state: "in_progress")).to be_valid
      expect(build(:game, state: "resolved")).to be_valid
      expect(build(:game, state: "invalid")).not_to be_valid
    end
  end

  describe "associations" do
    it "belongs to a creator" do
      game = create(:game)
      expect(game.creator).to be_a(User)
    end

    it "has many game_players" do
      game = create(:game)
      expect(game.game_players).to eq([])
    end

    it "has many moves" do
      game = create(:game)
      expect(game.moves).to eq([])
    end
  end
end
