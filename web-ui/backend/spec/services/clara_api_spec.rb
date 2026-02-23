require "rails_helper"
require "webmock/rspec"

RSpec.describe ClaraApi do
  let(:api) { ClaraApi.new }

  before do
    ENV["CLARA_API_URL"] = "https://test.example.com"
    ENV["GAME_API_KEY"] = "test-key"
  end

  describe "#game_event" do
    it "posts to /api/v1/game/event" do
      stub = stub_request(:post, "https://test.example.com/api/v1/game/event")
        .with(
          headers: { "Content-Type" => "application/json", "X-Game-API-Key" => "test-key" },
          body: hash_including(event_type: "clara_move", game_type: "checkers")
        )
        .to_return(
          status: 200,
          body: { commentary: "Nice move!", mood: "smug" }.to_json,
          headers: { "Content-Type" => "application/json" }
        )

      result = api.game_event(
        event_type: "clara_move",
        game_type: "checkers",
        state_summary: "You're playing Red. 12 pieces each.",
        user_id: "user-1",
        event_data: { move: { from: [5, 2], to: [4, 3] } },
        position_eval: 0.3,
        recent_history: []
      )

      expect(stub).to have_been_requested
      expect(result[:commentary]).to eq("Nice move!")
      expect(result[:mood]).to eq("smug")
    end

    it "returns fallback on timeout" do
      stub_request(:post, "https://test.example.com/api/v1/game/event")
        .to_timeout

      result = api.game_event(
        event_type: "clara_move",
        game_type: "checkers",
        state_summary: "test",
        user_id: "user-1"
      )

      expect(result[:commentary]).to be_nil
      expect(result[:mood]).to eq("neutral")
    end

    it "returns fallback on error response" do
      stub_request(:post, "https://test.example.com/api/v1/game/event")
        .to_return(status: 500, body: "Internal Server Error")

      result = api.game_event(
        event_type: "clara_move",
        game_type: "checkers",
        state_summary: "test",
        user_id: "user-1"
      )

      expect(result[:commentary]).to be_nil
      expect(result[:mood]).to eq("neutral")
    end
  end

  describe "#get_move" do
    it "posts to /api/v1/game/move" do
      stub = stub_request(:post, "https://test.example.com/api/v1/game/move")
        .to_return(
          status: 200,
          body: { move: { type: "hit" }, commentary: "Let's go!", mood: "happy" }.to_json,
          headers: { "Content-Type" => "application/json" }
        )

      result = api.get_move(
        game_type: "blackjack",
        game_state: {},
        legal_moves: ["hit", "stand"],
        personality: "clara",
        user_id: "user-1"
      )

      expect(stub).to have_been_requested
      expect(result[:move][:type]).to eq("hit")
    end
  end
end
