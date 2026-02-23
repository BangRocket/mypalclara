module Games
  class Orchestrator
    attr_reader :game

    def initialize(game)
      @game = game
      @package = Games::Registry.package_for(game.game_type)
      @definition = @package[:definition]
      @ai = @package[:ai]
      @llm_adapter = @package[:llm_adapter]
      @client_adapter = @package[:client_adapter]
      @clara_api = ClaraApi.new
    end

    # Human makes a move
    def human_move(player, move_params)
      state = load_state
      player_id = gp_identifier(player)

      # Validate
      legal = legal_moves_for(state, player)
      matching = find_matching_move(move_params, legal)
      unless matching
        return { error: "Invalid move", legal_moves: legal }
      end

      # Apply
      move = build_move(matching, player)
      new_state = @definition.apply_move(state, move)
      persist_move(player, move_params, new_state)

      # Commentary (async-safe: non-blocking if it fails)
      commentary_response = fire_event("player_move",
        event_data: { move: move_params },
        perspective: gp_identifier(player == game.game_players.first ? game.game_players.last : game.game_players.first)
      )

      # Check end
      check_game_end(new_state)

      game.reload
      {
        game: game,
        commentary: commentary_response&.dig(:commentary),
        mood: commentary_response&.dig(:mood)
      }
    end

    # AI takes a turn
    def ai_move(ai_player)
      state = load_state
      player_id = gp_identifier(ai_player)

      legal = legal_moves_for(state, ai_player)
      return { error: "No legal moves" } if legal.empty?

      if @ai.ai_type == :traditional
        # Ruby AI picks the move
        ai_result = @ai.pick_move(state, player_id_for_engine(ai_player))
        chosen_move = ai_result[:move]
        reasoning = ai_result[:reasoning]
      else
        # LLM picks the move
        move_history = game.moves.order(move_number: :desc).limit(5).reverse.map { |m| m.action }
        llm_response = @clara_api.get_move(
          game_type: game.game_type,
          game_state: state,
          legal_moves: legal,
          personality: ai_player.ai_personality,
          user_id: game.creator&.canonical_user_id || "unknown",
          move_history: move_history
        )
        chosen_move = parse_llm_move(llm_response[:move], legal)
        reasoning = llm_response[:commentary]
      end

      # Apply
      move = build_move(chosen_move, ai_player)
      new_state = @definition.apply_move(state, move)

      # Position evaluation for commentary
      position_eval = @ai.evaluate_position(new_state, player_id_for_engine(ai_player))

      persist_move(ai_player, chosen_move, new_state, commentary: reasoning)

      # Commentary event (high tier)
      commentary_response = fire_event("clara_move",
        event_data: {
          move: chosen_move,
          reasoning: reasoning,
          position_eval: position_eval
        },
        perspective: player_id_for_engine(ai_player)
      )

      # Check end
      check_game_end(new_state)

      game.reload
      {
        game: game,
        move: chosen_move,
        commentary: commentary_response&.dig(:commentary) || reasoning,
        mood: commentary_response&.dig(:mood) || "idle"
      }
    end

    # Player sends a chat message
    def player_chat(player, message)
      state = load_state
      ai_gp = game.game_players.find { |gp| gp.ai_personality.present? }
      ai_perspective = ai_gp ? player_id_for_engine(ai_gp) : nil

      fire_event("player_chat",
        event_data: { message: message },
        perspective: ai_perspective
      )
    end

    private

    def load_state
      state = game.game_data.deep_symbolize_keys

      # Normalize player ID keys to strings (JSONB round-trip fix)
      if state[:hands].is_a?(Hash)
        state[:hands] = state[:hands].transform_keys(&:to_s)
      end
      if state[:stood].is_a?(Array)
        state[:stood] = state[:stood].map(&:to_s)
      end

      state
    end

    def gp_identifier(game_player)
      game_player.ai_personality || "player-#{game_player.user_id}"
    end

    def player_id_for_engine(game_player)
      if game.game_type == "checkers"
        game_player.seat_position == 0 ? "red" : "black"
      else
        gp_identifier(game_player)
      end
    end

    def legal_moves_for(state, game_player)
      @definition.legal_moves(state, player_id_for_engine(game_player))
    end

    def find_matching_move(move_params, legal)
      if move_params.is_a?(Hash) && move_params[:from] && move_params[:to]
        legal.find { |m| m[:from] == move_params[:from] && m[:to] == move_params[:to] }
      elsif move_params.is_a?(String)
        legal.include?(move_params) ? move_params : nil
      else
        legal.include?(move_params) ? move_params : nil
      end
    end

    def build_move(chosen, game_player)
      if game.game_type == "blackjack"
        action = chosen.is_a?(String) ? chosen : (chosen[:action] || chosen[:type])
        { player: gp_identifier(game_player), action: action }
      else
        chosen
      end
    end

    def parse_llm_move(llm_move, legal)
      if llm_move.is_a?(Hash)
        move_data = llm_move.deep_symbolize_keys
        if move_data[:from] && move_data[:to]
          match = legal.find { |m| m[:from] == move_data[:from] && m[:to] == move_data[:to] }
          return match if match
        end
        return move_data[:type] if move_data[:type] && legal.include?(move_data[:type])
      elsif llm_move.is_a?(String) && legal.include?(llm_move)
        return llm_move
      end

      # Fallback: random legal move
      legal.sample
    end

    def persist_move(game_player, move_data, new_state, commentary: nil)
      game.increment!(:move_count)
      game.update!(game_data: new_state)

      action = move_data.is_a?(Hash) ? move_data : { type: move_data }

      game.moves.create!(
        game_player: game_player,
        move_number: game.move_count,
        action: action,
        game_data_snapshot: new_state,
        clara_commentary: commentary
      )
    end

    def fire_event(event_type, event_data: {}, perspective: nil)
      state = load_state
      player_id = perspective || player_id_for_engine(
        game.game_players.find { |gp| gp.ai_personality.present? } || game.game_players.first
      )

      @clara_api.game_event(
        event_type: event_type,
        game_type: game.game_type,
        state_summary: @llm_adapter.state_summary(state, perspective: player_id),
        user_id: game.creator&.canonical_user_id || "unknown",
        event_data: event_data,
        position_eval: @ai.evaluate_position(state, player_id),
        recent_history: @llm_adapter.relevant_history(
          game.moves.order(move_number: :desc).limit(5).reverse.map { |m| m.action },
          state: state
        )
      )
    rescue StandardError => e
      Rails.logger.error("Orchestrator fire_event error: #{e.class} - #{e.message}")
      { commentary: nil, mood: "neutral" }
    end

    def check_game_end(state)
      result = @definition.winner(state)
      return unless result&.over?

      game.update!(state: "resolved", finished_at: Time.current)

      if game.game_type == "checkers"
        game.game_players.each do |gp|
          color = gp.seat_position == 0 ? "red" : "black"
          player_result = result.winners&.include?(color) ? "won" : "lost"
          gp.update!(result: player_result)
        end
      elsif game.game_type == "blackjack"
        resolve_results = @definition.resolve(state)
        game.game_players.each do |gp|
          pid = gp_identifier(gp)
          gp.update!(result: resolve_results[pid]) if resolve_results[pid]
        end
      end

      fire_event("game_over",
        event_data: { result: { winners: result.winners, losers: result.losers } }
      )
    end
  end
end
