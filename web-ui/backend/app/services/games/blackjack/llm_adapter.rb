module Games
  module Blackjack
    class LLMAdapter < Games::LLMAdapter
      def state_summary(state, perspective:)
        hand = state[:hands][perspective]
        return "Waiting for cards." unless hand

        value = definition.hand_value(hand)
        dealer_showing = state[:dealer_hand]&.first

        parts = ["Your hand: #{hand.join(', ')} (value: #{value})."]
        parts << "Dealer shows: #{dealer_showing}." if dealer_showing
        stood_count = state[:stood]&.length || 0
        parts << "#{stood_count} player#{'s' if stood_count != 1} stood." if stood_count > 0

        parts.join(" ")
      end

      def describe_moves(moves, state:)
        moves.map do |move|
          desc = case move
          when "hit" then "Draw another card"
          when "stand" then "Keep your current hand"
          when "double_down" then "Double your bet and draw exactly one more card"
          else move
          end
          { id: move, description: desc }
        end
      end
    end
  end
end
