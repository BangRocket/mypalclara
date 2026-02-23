module Games
  module Checkers
    class ClientAdapter < Games::ClientAdapter
      def state_for_client(state, perspective:)
        {
          board: state[:board],
          current_player: state[:current_player],
          captured: state[:captured],
          turn_count: state[:turn_count]
        }
      end

      def available_actions(state, player)
        return [] unless state[:current_player] == player

        definition.legal_moves(state, player).map do |move|
          {
            from: move[:from],
            to: move[:to],
            captures: move[:captures],
            type: move[:captures]&.any? ? :jump : :move
          }
        end
      end
    end
  end
end
