require "rails_helper"

RSpec.describe Move, type: :model do
  it "requires move_number" do
    move = build(:move, move_number: nil)
    expect(move).not_to be_valid
  end

  it "requires action" do
    move = build(:move, action: nil)
    expect(move).not_to be_valid
  end

  it "belongs to a game and game_player" do
    move = create(:move)
    expect(move.game).to be_a(Game)
    expect(move.game_player).to be_a(GamePlayer)
  end
end
