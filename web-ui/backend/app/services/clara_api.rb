class ClaraApi
  TIMEOUT = 10

  def initialize
    @base_url = ENV.fetch("CLARA_API_URL", "https://mypalclara.com")
    @api_key = ENV.fetch("GAME_API_KEY")
  end

  # LLM move selection (mid/low tier, for ai_type: :llm games)
  def get_move(game_type:, game_state:, legal_moves:, personality:, user_id:, move_history: [])
    post("/api/v1/game/move", {
      game_type: game_type,
      game_state: game_state,
      legal_moves: legal_moves,
      personality: personality,
      user_id: user_id,
      move_history: move_history
    }) || fallback_move(legal_moves)
  end

  # Event-based commentary (high tier, memory-enabled)
  def game_event(event_type:, game_type:, state_summary:, user_id:,
                 event_data: {}, position_eval: 0.0, recent_history: [])
    post("/api/v1/game/event", {
      event_type: event_type,
      game_type: game_type,
      state_summary: state_summary,
      event_data: event_data,
      position_eval: position_eval,
      user_id: user_id,
      recent_history: recent_history
    }) || fallback_commentary
  end

  private

  def post(path, body)
    uri = URI("#{@base_url}#{path}")

    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = uri.scheme == "https"
    http.open_timeout = TIMEOUT
    http.read_timeout = TIMEOUT

    request = Net::HTTP::Post.new(uri)
    request["Content-Type"] = "application/json"
    request["X-Game-API-Key"] = @api_key
    request.body = body.to_json

    response = http.request(request)

    if response.is_a?(Net::HTTPSuccess)
      JSON.parse(response.body, symbolize_names: true)
    else
      Rails.logger.error("ClaraApi error: #{response.code} #{response.body}")
      nil
    end
  rescue Net::OpenTimeout, Net::ReadTimeout, StandardError => e
    Rails.logger.error("ClaraApi error: #{e.class} - #{e.message}")
    nil
  end

  def fallback_move(legal_moves)
    {
      move: { type: legal_moves.sample },
      commentary: "Give me a second... okay, here goes.",
      mood: "nervous"
    }
  end

  def fallback_commentary
    { commentary: nil, mood: "neutral" }
  end
end
