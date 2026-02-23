module Games
  module Blackjack
    class AI < GameAI
      def ai_type
        :llm
      end

      def pick_move(state, player, difficulty: :medium)
        raise NotImplementedError,
          "Blackjack uses LLM for move selection. " \
          "The Orchestrator handles this via ClaraApi.get_move."
      end

      def evaluate_position(state, player)
        hand = state[:hands][player]
        return 0.0 if hand.nil?

        value = definition.hand_value(hand)
        return -1.0 if value > 21

        case value
        when 21 then 0.9
        when 20 then 0.7
        when 19 then 0.4
        when 18 then 0.2
        when 17 then 0.0
        else
          # Under 17: scale from -0.1 (16) to -0.5 (low values)
          -0.1 - (0.4 * (1.0 - (value.to_f / 16)))
        end
      end

      def explain_move(state, move)
        player = move[:player]
        action = move[:action]
        hand = state[:hands][player]
        value = definition.hand_value(hand) if hand
        dealer_showing = state[:dealer_hand]&.first

        case action
        when "hit"
          if value && value < 12
            "Drawing — safe to hit at #{value}"
          elsif value && value <= 16
            "Drawing another card — risky at #{value} but the odds favor it"
          else
            "Going for it — bold play at #{value}"
          end
        when "stand"
          "Standing at #{value} — pushing luck further would be risky"
        when "double_down"
          "Doubling down at #{value} — strong hand against dealer's #{dealer_showing}"
        else
          "Making a play"
        end
      end
    end
  end
end
