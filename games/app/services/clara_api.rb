class ClaraApi
  TIMEOUT = 10

  def initialize
    @base_url = ENV.fetch("CLARA_API_URL", "https://mypalclara.com")
    @api_key = ENV.fetch("GAME_API_KEY")
  end

  def get_move(game_type:, game_state:, legal_moves:, personality:, user_id:, move_history: [])
    uri = URI("#{@base_url}/api/v1/game/move")

    body = {
      game_type: game_type,
      game_state: game_state,
      legal_moves: legal_moves,
      personality: personality,
      user_id: user_id,
      move_history: move_history,
    }

    response = Net::HTTP.post(
      uri,
      body.to_json,
      "Content-Type" => "application/json",
      "X-Game-API-Key" => @api_key,
    )

    if response.is_a?(Net::HTTPSuccess)
      JSON.parse(response.body, symbolize_names: true)
    else
      fallback_move(legal_moves)
    end
  rescue Net::OpenTimeout, Net::ReadTimeout, StandardError => e
    Rails.logger.error("ClaraApi error: #{e.message}")
    fallback_move(legal_moves)
  end

  private

  def fallback_move(legal_moves)
    {
      move: { type: legal_moves.sample },
      commentary: "Give me a second... okay, here goes.",
      mood: "nervous",
    }
  end
end
