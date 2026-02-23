module Games
  module Blackjack
    class Definition < GameDefinition
      SUITS = %w[S H D C].freeze
      RANKS = %w[A 2 3 4 5 6 7 8 9 10 J Q K].freeze

      def game_type
        "blackjack"
      end

      def new_game(**_options)
        deck = SUITS.product(RANKS).map { |s, r| "#{r}#{s}" }.shuffle
        {
          deck: deck,
          dealer_hand: [],
          hands: {},
          stood: [],
          phase: :dealing,
          current_player_index: 0,
          turn_count: 0
        }
      end

      def players(state)
        state[:hands].keys
      end

      def current_player(state)
        player_list = players(state)
        return nil if player_list.empty?

        player_list[state[:current_player_index] || 0]
      end

      def phase(state)
        state[:phase]
      end

      def legal_moves(state, player)
        hand = state[:hands][player]
        return [] if hand.nil?

        value = hand_value(hand)
        return [] if value > 21

        moves = %w[hit stand]
        moves << "double_down" if hand.length == 2
        moves
      end

      # move is a hash: { player: "p1", action: "hit" }
      def apply_move(state, move)
        state = deep_copy_state(state)
        player_id = move[:player]
        action = move[:action]

        case action
        when "hit"
          state[:hands][player_id] << state[:deck].shift
        when "stand"
          state[:stood] ||= []
          state[:stood] << player_id unless state[:stood].include?(player_id)
        when "double_down"
          state[:hands][player_id] << state[:deck].shift
          state[:stood] ||= []
          state[:stood] << player_id unless state[:stood].include?(player_id)
        end

        state
      end

      def winner(state)
        return nil unless state[:phase] == :resolving

        dealer_value = hand_value(state[:dealer_hand])
        dealer_bust = dealer_value > 21

        winners = []
        losers = []
        draws = []

        state[:hands].each do |player_id, hand|
          player_value = hand_value(hand)

          if player_value > 21
            losers << player_id
          elsif dealer_bust || player_value > dealer_value
            winners << player_id
          elsif player_value == dealer_value
            draws << player_id
          else
            losers << player_id
          end
        end

        status = if winners.any?
                   :won
                 elsif draws.any? && losers.empty?
                   :draw
                 elsif losers.any?
                   :lost
                 else
                   return nil
                 end

        GameResult.new(
          status: status,
          winners: winners,
          losers: losers,
          draws: draws
        )
      end

      # Game-specific methods (not in base interface)

      def deal(state, player_ids)
        state = deep_copy_state(state)
        player_ids.each { |pid| state[:hands][pid] = [] }

        2.times do
          player_ids.each { |pid| state[:hands][pid] << state[:deck].shift }
        end
        2.times { state[:dealer_hand] << state[:deck].shift }

        state[:phase] = :player_turns
        state
      end

      def dealer_play(state)
        state = deep_copy_state(state)
        while hand_value(state[:dealer_hand]) < 17
          state[:dealer_hand] << state[:deck].shift
        end
        state[:phase] = :resolving
        state
      end

      def resolve(state)
        dealer_value = hand_value(state[:dealer_hand])
        dealer_bust = dealer_value > 21

        results = {}
        state[:hands].each do |player_id, hand|
          player_value = hand_value(hand)

          results[player_id] = if player_value > 21
                                 "lost"
                               elsif dealer_bust
                                 "won"
                               elsif player_value > dealer_value
                                 "won"
                               elsif player_value == dealer_value
                                 "draw"
                               else
                                 "lost"
                               end
        end

        results
      end

      def hand_value(hand)
        values = hand.map { |card| card_value(card) }
        total = values.sum
        aces = hand.count { |c| c.start_with?("A") }

        while total > 21 && aces > 0
          total -= 10
          aces -= 1
        end

        total
      end

      private

      def card_value(card)
        rank = card.match(/\A(\d+|[AJQK])/)[1]

        case rank
        when "A" then 11
        when "K", "Q", "J" then 10
        else rank.to_i
        end
      end
    end
  end
end
