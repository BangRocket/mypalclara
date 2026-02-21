require "rails_helper"

RSpec.describe ClaraApi, type: :service do
  let(:api) { ClaraApi.new }

  before do
    ENV["CLARA_API_URL"] = "https://mypalclara.com"
    ENV["GAME_API_KEY"] = "test-key"
  end

  describe "#get_move" do
    it "returns move, commentary, and mood" do
      stub_request(:post, "https://mypalclara.com/api/v1/game/move")
        .with(
          headers: { "X-Game-API-Key" => "test-key" },
        )
        .to_return(
          status: 200,
          body: {
            move: { type: "stand" },
            commentary: "Nice hand!",
            mood: "happy",
          }.to_json,
          headers: { "Content-Type" => "application/json" },
        )

      result = api.get_move(
        game_type: "blackjack",
        game_state: { player_hand: ["A♠", "7♥"] },
        legal_moves: ["hit", "stand"],
        personality: "clara",
        user_id: "user-123",
      )

      expect(result[:move][:type]).to eq("stand")
      expect(result[:commentary]).to eq("Nice hand!")
      expect(result[:mood]).to eq("happy")
    end

    it "returns fallback on API failure" do
      stub_request(:post, "https://mypalclara.com/api/v1/game/move")
        .to_return(status: 500)

      result = api.get_move(
        game_type: "blackjack",
        game_state: {},
        legal_moves: ["hit", "stand"],
        personality: "clara",
        user_id: "user-123",
      )

      expect(["hit", "stand"]).to include(result[:move][:type])
      expect(result[:commentary]).to be_present
      expect(result[:mood]).to eq("nervous")
    end
  end
end
