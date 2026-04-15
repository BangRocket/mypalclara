require "rails_helper"

RSpec.describe GamePlayer, type: :model do
  describe "validations" do
    it "requires seat_position" do
      gp = build(:game_player, seat_position: nil)
      expect(gp).not_to be_valid
    end

    it "requires player_state" do
      gp = build(:game_player, player_state: nil)
      expect(gp).not_to be_valid
    end

    it "requires either user or ai_personality" do
      gp = build(:game_player, user: nil, ai_personality: nil)
      expect(gp).not_to be_valid
    end

    it "accepts a human player" do
      gp = build(:game_player, ai_personality: nil)
      expect(gp).to be_valid
    end

    it "accepts an AI player" do
      gp = build(:ai_game_player)
      expect(gp).to be_valid
    end

    it "validates ai_personality values" do
      expect(build(:ai_game_player, ai_personality: "flo")).to be_valid
      expect(build(:ai_game_player, ai_personality: "clarissa")).to be_valid
      expect(build(:ai_game_player, ai_personality: "unknown")).not_to be_valid
    end
  end
end
