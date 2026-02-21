module Api
  module V1
    class GamesController < ApplicationController
      before_action :set_game, only: [:show, :move, :ai_move]

      def create
        game = Game.new(
          game_type: params[:game_type],
          state: "waiting",
          creator: current_user,
          game_data: {}
        )

        unless game.valid?
          render json: { error: game.errors.full_messages.join(", ") }, status: :unprocessable_entity
          return
        end

        game.save!

        # Add human player
        game.game_players.create!(
          user: current_user,
          seat_position: 0,
          player_state: "active"
        )

        # Add AI players
        ai_players = params[:ai_players] || []
        ai_players.each_with_index do |personality, i|
          game.game_players.create!(
            ai_personality: personality,
            seat_position: i + 1,
            player_state: "active"
          )
        end

        # Initialize game state
        engine = game_engine(game.game_type)
        state = engine.new_game

        if game.game_type == "blackjack"
          player_ids = game.game_players.order(:seat_position).map { |gp| gp_identifier(gp) }
          state = engine.deal(state, player_ids)
        end

        game.update!(game_data: state, state: "in_progress", started_at: Time.current)

        render json: { game: game_props(game) }, status: :created
      end

      def show
        render json: { game: game_props(@game) }
      end

      def move
        unless @game.state == "in_progress"
          render json: { error: "Game is not in progress" }, status: :unprocessable_entity
          return
        end

        player = @game.game_players.find_by(user: current_user)
        unless player
          render json: { error: "You are not a participant in this game" }, status: :unprocessable_entity
          return
        end

        engine = game_engine(@game.game_type)
        state = load_game_state(@game)
        player_id = gp_identifier(player)

        move_type = params[:move_type]

        if @game.game_type == "checkers"
          # Checkers: move_type is JSON like {"from":[5,2],"to":[4,1]}
          parsed_move = move_type.is_a?(String) ? JSON.parse(move_type).deep_symbolize_keys : move_type.to_unsafe_h.deep_symbolize_keys
          color = player.seat_position == 0 ? "red" : "black"
          legal = engine.legal_moves(state, color)

          matching = legal.find { |m| m[:from] == parsed_move[:from] && m[:to] == parsed_move[:to] }
          unless matching
            render json: { error: "Invalid move" }, status: :unprocessable_entity
            return
          end

          new_state = engine.apply_move(state, matching)
        else
          legal = engine.legal_moves(state, player_id)
          unless legal.include?(move_type)
            render json: { error: "Invalid move: #{move_type}. Legal moves: #{legal.join(', ')}" }, status: :unprocessable_entity
            return
          end

          new_state = engine.apply_move(state, player_id, move_type)
        end

        @game.increment!(:move_count)
        @game.update!(game_data: new_state)

        @game.moves.create!(
          game_player: player,
          move_number: @game.move_count,
          action: { type: move_type },
          game_data_snapshot: new_state
        )

        # Check for game end conditions (all players stood or busted in blackjack)
        check_game_end(@game, engine, new_state)

        @game.reload
        broadcast_game_update(@game)

        render json: { game: game_props(@game) }
      end

      def ai_move
        unless @game.state == "in_progress"
          render json: { error: "Game is not in progress" }, status: :unprocessable_entity
          return
        end

        ai_player = @game.game_players.find_by(id: params[:game_player_id])
        unless ai_player&.ai_personality.present?
          render json: { error: "Not a valid AI player" }, status: :unprocessable_entity
          return
        end

        engine = game_engine(@game.game_type)
        state = load_game_state(@game)
        player_id = gp_identifier(ai_player)

        if @game.game_type == "checkers"
          color = ai_player.seat_position == 0 ? "red" : "black"
          legal = engine.legal_moves(state, color)
        else
          legal = engine.legal_moves(state, player_id)
        end

        # Get AI decision from Clara API
        move_history = @game.moves.order(:move_number).map { |m| m.action }
        api = ClaraApi.new
        response = api.get_move(
          game_type: @game.game_type,
          game_state: state,
          legal_moves: legal,
          personality: ai_player.ai_personality,
          user_id: current_user.canonical_user_id,
          move_history: move_history
        )

        if @game.game_type == "checkers"
          ai_move_data = response[:move].is_a?(Hash) ? response[:move].deep_symbolize_keys : JSON.parse(response[:move]).deep_symbolize_keys rescue legal.first
          matching = legal.find { |m| m[:from] == ai_move_data[:from] && m[:to] == ai_move_data[:to] }
          matching ||= legal.first
          new_state = engine.apply_move(state, matching)
          move_type = matching.to_json
        else
          move_type = response[:move].is_a?(Hash) ? response[:move][:type] : response[:move]
          move_type = legal.first unless legal.include?(move_type)
          new_state = engine.apply_move(state, player_id, move_type)
        end

        @game.increment!(:move_count)
        @game.update!(game_data: new_state)

        @game.moves.create!(
          game_player: ai_player,
          move_number: @game.move_count,
          action: { type: move_type },
          game_data_snapshot: new_state,
          clara_commentary: response[:commentary]
        )

        check_game_end(@game, engine, new_state)

        @game.reload
        broadcast_game_update(@game, commentary: response[:commentary], mood: response[:mood])

        render json: {
          game: game_props(@game),
          commentary: response[:commentary],
          mood: response[:mood]
        }
      end

      private

      def set_game
        @game = Game.find(params[:id])
      end

      def game_engine(type)
        case type
        when "blackjack" then Games::BlackjackEngine.new
        when "checkers" then Games::CheckersEngine.new
        else
          raise ArgumentError, "Unknown game type: #{type}"
        end
      end

      def gp_identifier(game_player)
        game_player.ai_personality || "player-#{game_player.user_id}"
      end

      # Load game state from DB, normalizing keys so the engines work correctly.
      # The engines use string keys for player IDs within the :hands hash,
      # but after JSON round-trip + deep_symbolize_keys, those become symbols.
      # We keep top-level keys as symbols (engine convention) and convert
      # player ID keys back to strings.
      def load_game_state(game)
        state = game.game_data.deep_symbolize_keys

        # Convert hands keys back to strings (player IDs)
        if state[:hands].is_a?(Hash)
          state[:hands] = state[:hands].transform_keys(&:to_s)
        end

        # Convert stood entries back to strings
        if state[:stood].is_a?(Array)
          state[:stood] = state[:stood].map(&:to_s)
        end

        state
      end

      def game_props(game)
        {
          id: game.id,
          game_type: game.game_type,
          state: game.state,
          game_data: game.game_data,
          move_count: game.move_count,
          current_turn: game.current_turn,
          started_at: game.started_at,
          finished_at: game.finished_at,
          players: game.game_players.order(:seat_position).map { |gp|
            {
              id: gp.id,
              user_id: gp.user_id,
              ai_personality: gp.ai_personality,
              seat_position: gp.seat_position,
              player_state: gp.player_state,
              hand_data: gp.hand_data,
              result: gp.result
            }
          },
          moves: game.moves.order(:move_number).map { |m|
            {
              id: m.id,
              move_number: m.move_number,
              action: m.action,
              clara_commentary: m.clara_commentary,
              game_player_id: m.game_player_id
            }
          }
        }
      end

      def broadcast_game_update(game, commentary: nil, mood: nil)
        payload = { type: "game_update", game: game_props(game) }
        payload[:commentary] = commentary if commentary
        payload[:mood] = mood if mood
        GameChannel.broadcast_to(game, payload)
      end

      def check_game_end(game, engine, state)
        if game.game_type == "checkers"
          winner = engine.winner(state)
          if winner
            game.update!(state: "resolved", finished_at: Time.current)
            game.game_players.each do |gp|
              color = gp.seat_position == 0 ? "red" : "black"
              gp.update!(result: color == winner ? "win" : "loss")
            end
          end
          return
        end

        return unless game.game_type == "blackjack"

        player_ids = game.game_players.order(:seat_position).map { |gp| gp_identifier(gp) }

        # Check if all players have stood or busted
        all_done = player_ids.all? { |pid|
          hand = state[:hands][pid] || state[:hands][pid.to_s]
          hand_val = engine.hand_value(hand || [])
          stood = (state[:stood] || []).map(&:to_s).include?(pid.to_s)
          hand_val > 21 || stood
        }

        if all_done
          state = engine.dealer_play(state)
          results = engine.resolve(state)

          game.update!(game_data: state, state: "resolved", finished_at: Time.current)

          # Update player results
          game.game_players.each do |gp|
            pid = gp_identifier(gp)
            result = results[pid] || results[pid.to_s]
            gp.update!(result: result) if result
          end
        end
      end
    end
  end
end
