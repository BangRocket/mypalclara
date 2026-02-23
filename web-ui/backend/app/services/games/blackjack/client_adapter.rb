module Games
  module Blackjack
    class ClientAdapter < Games::ClientAdapter
      def state_for_client(state, perspective:)
        {
          hands: state[:hands],
          dealer_hand: state[:dealer_hand],
          phase: state[:phase],
          stood: state[:stood],
          current_player_index: state[:current_player_index],
          turn_count: state[:turn_count]
        }
      end

      def available_actions(state, player)
        definition.legal_moves(state, player)
      end
    end
  end
end
