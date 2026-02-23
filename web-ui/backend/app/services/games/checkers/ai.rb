module Games
  module Checkers
    class AI < GameAI
      def ai_type
        :traditional
      end

      def pick_move(state, player, difficulty: :medium)
        legal = definition.legal_moves(state, player)
        return { move: nil, reasoning: "no legal moves" } if legal.empty?

        move = case difficulty
        when :easy   then pick_easy(state, player, legal)
        when :medium then pick_medium(state, player, legal)
        when :hard   then pick_hard(state, player, legal)
        else pick_medium(state, player, legal)
        end

        { move: move, reasoning: explain_move(state, move) }
      end

      def evaluate_position(state, player)
        board = state[:board].flatten.compact

        my_pieces = player == "red" ? %w[r R] : %w[b B]
        opp_pieces = player == "red" ? %w[b B] : %w[r R]

        my_men = board.count { |p| p == my_pieces[0] }
        my_kings = board.count { |p| p == my_pieces[1] }
        opp_men = board.count { |p| p == opp_pieces[0] }
        opp_kings = board.count { |p| p == opp_pieces[1] }

        my_score = my_men + (my_kings * 1.5)
        opp_score = opp_men + (opp_kings * 1.5)
        total = my_score + opp_score

        return 0.0 if total == 0
        ((my_score - opp_score) / total).clamp(-1.0, 1.0)
      end

      def explain_move(state, move)
        parts = []

        if move[:captures]&.any?
          parts << "captures #{move[:captures].length} piece#{'s' if move[:captures].length > 1}"
        end

        piece = state[:board][move[:from][0]][move[:from][1]]
        if piece == "r" && move[:to][0] == 0
          parts << "gets kinged"
        elsif piece == "b" && move[:to][0] == 7
          parts << "gets kinged"
        end

        parts.empty? ? "advances position" : parts.join(" and ")
      end

      private

      def pick_easy(state, player, legal)
        non_captures = legal.reject { |m| m[:captures]&.any? }
        pool = non_captures.any? && rand < 0.4 ? non_captures : legal
        pool.sample
      end

      def pick_medium(state, player, legal)
        scored = legal.map { |m| [m, score_move(state, player, m)] }
        scored.sort_by! { |_, s| -s }
        top = scored.first(3)
        top.sample.first
      end

      def pick_hard(state, player, legal)
        opponent = player == "red" ? "black" : "red"
        best_move = nil
        best_score = -Float::INFINITY

        legal.each do |move|
          new_state = definition.apply_move(state, move)
          score = minimax(new_state, 5, -Float::INFINITY, Float::INFINITY, false, player, opponent)
          if score > best_score
            best_score = score
            best_move = move
          end
        end

        best_move || legal.first
      end

      def score_move(state, player, move)
        score = 0
        score += 3 if move[:captures]&.any?
        score += move[:captures].length if move[:captures]

        piece = state[:board][move[:from][0]][move[:from][1]]
        if (piece == "r" && move[:to][0] == 0) || (piece == "b" && move[:to][0] == 7)
          score += 2
        end

        center_dist = (move[:to][0] - 3.5).abs + (move[:to][1] - 3.5).abs
        score += (4.0 - center_dist) * 0.3

        score
      end

      def minimax(state, depth, alpha, beta, maximizing, player, opponent)
        current = maximizing ? player : opponent

        winner_result = definition.winner(state)
        if winner_result
          return winner_result.winners&.include?(player) ? 100 + depth : -(100 + depth)
        end
        return evaluate_position(state, player) * 10 if depth == 0

        moves = definition.legal_moves(state, current)
        return evaluate_position(state, player) * 10 if moves.empty?

        if maximizing
          max_eval = -Float::INFINITY
          moves.each do |move|
            new_state = definition.apply_move(state, move)
            eval_score = minimax(new_state, depth - 1, alpha, beta, false, player, opponent)
            max_eval = [max_eval, eval_score].max
            alpha = [alpha, eval_score].max
            break if beta <= alpha
          end
          max_eval
        else
          min_eval = Float::INFINITY
          moves.each do |move|
            new_state = definition.apply_move(state, move)
            eval_score = minimax(new_state, depth - 1, alpha, beta, true, player, opponent)
            min_eval = [min_eval, eval_score].min
            beta = [beta, eval_score].min
            break if beta <= alpha
          end
          min_eval
        end
      end
    end
  end
end
