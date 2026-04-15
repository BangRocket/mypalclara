module Api
  module V1
    class HistoryController < ApplicationController
      def index
        game_players = current_user.game_players
          .includes(game: :game_players)
          .order("games.created_at DESC")

        render json: {
          games: game_players.map { |gp| history_entry(gp) },
        }
      end

      def show
        game = Game.find(params[:id])
        moves = game.moves.includes(:game_player).order(:move_number)

        render json: {
          game: game_detail(game),
          moves: moves.map { |m| move_props(m) },
        }
      end

      private

      def history_entry(gp)
        game = gp.game
        {
          id: game.id,
          game_type: game.game_type,
          state: game.state,
          created_at: game.created_at.iso8601,
          players: game.game_players.map { |p| p.ai_personality || p.user&.display_name || "Unknown" },
          move_count: game.move_count,
        }
      end

      def game_detail(game)
        {
          id: game.id,
          game_type: game.game_type,
          state: game.state,
          game_data: game.game_data,
          players: game.game_players.order(:seat_position).map { |gp|
            {
              id: gp.id,
              name: gp.ai_personality || gp.user&.display_name || "Unknown",
              seat: gp.seat_position,
              is_ai: gp.ai_personality.present?,
            }
          },
        }
      end

      def move_props(move)
        {
          number: move.move_number,
          player: move.game_player.ai_personality || move.game_player.user&.display_name || "Unknown",
          action: move.action,
          commentary: move.clara_commentary,
          game_data: move.game_data_snapshot,
        }
      end
    end
  end
end
