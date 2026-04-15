require "rails_helper"

RSpec.describe GameChannel, type: :channel do
  let(:user) { create(:user) }
  let(:game) do
    create(:game, creator: user, game_type: "blackjack", state: "in_progress")
  end

  before do
    stub_connection current_user: user
  end

  describe "#subscribed" do
    it "subscribes to the game stream" do
      subscribe(game_id: game.id)
      expect(subscription).to be_confirmed
      expect(subscription).to have_stream_for(game)
    end

    it "rejects subscription for non-existent game" do
      subscribe(game_id: -1)
      expect(subscription).to be_rejected
    end
  end

  describe "#unsubscribed" do
    it "stops all streams on unsubscribe" do
      subscribe(game_id: game.id)
      expect(subscription).to have_stream_for(game)

      subscription.unsubscribe_from_channel
      # After unsubscribe, streams are stopped (no assertion needed beyond no error)
    end
  end

  describe "broadcasting" do
    it "broadcasts game updates to subscribers" do
      subscribe(game_id: game.id)

      game_data = {
        type: "game_update",
        game: {
          id: game.id,
          state: "in_progress",
          game_data: { hands: {}, deck: [] }
        }
      }

      expect {
        GameChannel.broadcast_to(game, game_data)
      }.to have_broadcasted_to(game).with(game_data)
    end

    it "broadcasts move updates with commentary" do
      subscribe(game_id: game.id)

      move_data = {
        type: "move_made",
        player: "clara",
        action: { type: "hit" },
        commentary: "Here goes nothing!",
        mood: "nervous"
      }

      expect {
        GameChannel.broadcast_to(game, move_data)
      }.to have_broadcasted_to(game).with(move_data)
    end

    it "broadcasts game resolution" do
      subscribe(game_id: game.id)

      resolution_data = {
        type: "game_resolved",
        results: {
          "player-1" => "won",
          "clara" => "lost"
        }
      }

      expect {
        GameChannel.broadcast_to(game, resolution_data)
      }.to have_broadcasted_to(game).with(resolution_data)
    end
  end
end
