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
        ai_players = Array(params[:ai_players])
        if game.game_type == "blackjack" && ai_players.exclude?("clara")
          ai_players.unshift("clara")
        end
        ai_players.uniq!
        ai_players.each_with_index do |personality, i|
          game.game_players.create!(
            ai_personality: personality,
            seat_position: i + 1,
            player_state: "active"
          )
        end

        # Initialize game state via Definition
        definition = Games::Registry.package_for(game.game_type)[:definition]
        state = definition.new_game

        if game.game_type == "blackjack"
          player_ids = game.game_players.order(:seat_position).map { |gp| gp_identifier(gp) }
          state = definition.deal(state, player_ids)
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

        move_params = parse_move_params(params[:move_type])
        orchestrator = Games::Orchestrator.new(@game)
        result = orchestrator.human_move(player, move_params)

        if result[:error]
          render json: { error: result[:error], legal_moves: result[:legal_moves] }, status: :unprocessable_entity
          return
        end

        @game.reload
        broadcast_game_update(@game, commentary: result[:commentary], mood: result[:mood])

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

        orchestrator = Games::Orchestrator.new(@game)
        result = orchestrator.ai_move(ai_player)

        if result[:error]
          render json: { error: result[:error] }, status: :unprocessable_entity
          return
        end

        @game.reload
        broadcast_game_update(@game, commentary: result[:commentary], mood: result[:mood])

        render json: {
          game: game_props(@game),
          commentary: result[:commentary],
          mood: result[:mood]
        }
      end

      private

      def set_game
        @game = Game.find(params[:id])
      end

      def gp_identifier(game_player)
        game_player.ai_personality || "player-#{game_player.user_id}"
      end

      def parse_move_params(move_type)
        if @game.game_type == "checkers"
          if move_type.is_a?(String)
            JSON.parse(move_type).deep_symbolize_keys
          else
            move_type.to_unsafe_h.deep_symbolize_keys
          end
        else
          move_type
        end
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
    end
  end
end
