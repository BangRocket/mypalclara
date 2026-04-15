module Games
  class BlackjackEngine
    SUITS = %w[♠ ♥ ♦ ♣].freeze
    RANKS = %w[A 2 3 4 5 6 7 8 9 10 J Q K].freeze

    def new_game
      deck = SUITS.product(RANKS).map { |s, r| "#{r}#{s}" }.shuffle
      {
        deck: deck,
        dealer_hand: [],
        hands: {},
        stood: [],
        phase: "dealing",
      }
    end

    def deal(state, player_ids)
      state = state.deep_dup
      player_ids.each { |pid| state[:hands][pid] = [] }

      2.times do
        player_ids.each { |pid| state[:hands][pid] << state[:deck].shift }
      end
      2.times { state[:dealer_hand] << state[:deck].shift }

      state[:phase] = "player_turns"
      state
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

    def legal_moves(state, player_id)
      hand = state[:hands][player_id]
      return [] if hand.nil?

      value = hand_value(hand)
      return [] if value > 21

      moves = %w[hit stand]
      moves << "double_down" if hand.length == 2
      moves
    end

    def apply_move(state, player_id, move)
      state = state.deep_dup

      case move
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

    def dealer_play(state)
      state = state.deep_dup
      while hand_value(state[:dealer_hand]) < 17
        state[:dealer_hand] << state[:deck].shift
      end
      state[:phase] = "resolving"
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
