module Games
  module Checkers
    class LLMAdapter < Games::LLMAdapter
      def state_summary(state, perspective:)
        board = state[:board].flatten.compact

        red_men = board.count { |p| p == "r" }
        red_kings = board.count { |p| p == "R" }
        black_men = board.count { |p| p == "b" }
        black_kings = board.count { |p| p == "B" }

        red_total = red_men + red_kings
        black_total = black_men + black_kings

        you = perspective == "red" ? "Red" : "Black"
        them = perspective == "red" ? "Black" : "Red"
        your_total = perspective == "red" ? red_total : black_total
        their_total = perspective == "red" ? black_total : red_total
        your_kings = perspective == "red" ? red_kings : black_kings

        parts = ["You're playing #{you}."]
        parts << "You have #{your_total} piece#{'s' if your_total != 1}"
        parts[-1] += " (#{your_kings} king#{'s' if your_kings != 1})" if your_kings > 0
        parts[-1] += "."
        parts << "#{them} has #{their_total} piece#{'s' if their_total != 1}."
        parts << "#{state[:current_player]&.capitalize}'s turn."

        parts.join(" ")
      end

      def describe_moves(moves, state:)
        moves.map.with_index do |move, i|
          desc = "Move from #{coord(move[:from])} to #{coord(move[:to])}"
          if move[:captures]&.any?
            desc += ", capturing at #{move[:captures].map { |c| coord(c) }.join(', ')}"
          end
          { id: i, move: move, description: desc }
        end
      end

      private

      def coord(pos)
        "#{('a'.ord + pos[1]).chr}#{8 - pos[0]}"
      end
    end
  end
end
