module Games
  module Checkers
    class Definition < GameDefinition
      BOARD_SIZE = 8

      def game_type
        "checkers"
      end

      def new_game(**options)
        board = Array.new(BOARD_SIZE) { Array.new(BOARD_SIZE, nil) }

        # Black pieces in rows 0-2 on dark squares (row + col is odd)
        (0..2).each do |row|
          BOARD_SIZE.times do |col|
            board[row][col] = "b" if (row + col).odd?
          end
        end

        # Red pieces in rows 5-7 on dark squares (row + col is odd)
        (5..7).each do |row|
          BOARD_SIZE.times do |col|
            board[row][col] = "r" if (row + col).odd?
          end
        end

        { board: board, captured: {}, current_player: "red", turn_count: 0 }
      end

      def players(state)
        %w[red black]
      end

      def current_player(state)
        state[:current_player]
      end

      def legal_moves(state, color)
        board = state[:board]
        pieces = color == "red" ? %w[r R] : %w[b B]

        jumps = []
        simple_moves = []

        BOARD_SIZE.times do |row|
          BOARD_SIZE.times do |col|
            piece = board[row][col]
            next unless pieces.include?(piece)

            piece_jumps = find_jumps(board, row, col, piece)
            jumps.concat(piece_jumps)

            piece_moves = find_simple_moves(board, row, col, piece)
            simple_moves.concat(piece_moves)
          end
        end

        # Mandatory jumps: if any jump exists, only jumps are legal
        jumps.any? ? jumps : simple_moves
      end

      def apply_move(state, move)
        new_state = deep_copy_state(state)

        board = new_state[:board]
        from_row, from_col = move[:from]
        to_row, to_col = move[:to]

        piece = board[from_row][from_col]
        board[from_row][from_col] = nil
        board[to_row][to_col] = piece

        # Remove captured pieces
        if move[:captures]
          move[:captures].each do |cap_row, cap_col|
            board[cap_row][cap_col] = nil
          end
        end

        # King when reaching opposite end
        if piece == "r" && to_row == 0
          board[to_row][to_col] = "R"
        elsif piece == "b" && to_row == BOARD_SIZE - 1
          board[to_row][to_col] = "B"
        end

        # Switch current player
        new_state[:current_player] = piece.start_with?("r") ? "black" : "red"
        new_state[:turn_count] = (new_state[:turn_count] || 0) + 1

        new_state
      end

      def winner(state)
        board = state[:board]
        flat = board.flatten.compact

        red_pieces = flat.count { |c| c == "r" || c == "R" }
        black_pieces = flat.count { |c| c == "b" || c == "B" }

        if black_pieces == 0 && red_pieces > 0
          return GameResult.new(status: :win, winners: ["red"], losers: ["black"])
        end

        if red_pieces == 0 && black_pieces > 0
          return GameResult.new(status: :win, winners: ["black"], losers: ["red"])
        end

        # Check if current player has no moves (stalemate = loss)
        if red_pieces > 0 && legal_moves(state, "red").empty?
          return GameResult.new(status: :win, winners: ["black"], losers: ["red"])
        end

        if black_pieces > 0 && legal_moves(state, "black").empty?
          return GameResult.new(status: :win, winners: ["red"], losers: ["black"])
        end

        nil
      end

      private

      def move_directions(piece)
        case piece
        when "r"
          [[-1, -1], [-1, 1]]  # Red moves toward row 0
        when "b"
          [[1, -1], [1, 1]]    # Black moves toward row 7
        when "R", "B"
          [[-1, -1], [-1, 1], [1, -1], [1, 1]]  # Kings move all directions
        else
          []
        end
      end

      def in_bounds?(row, col)
        row >= 0 && row < BOARD_SIZE && col >= 0 && col < BOARD_SIZE
      end

      def opponent_pieces(piece)
        case piece
        when "r", "R"
          %w[b B]
        when "b", "B"
          %w[r R]
        else
          []
        end
      end

      def find_simple_moves(board, row, col, piece)
        moves = []
        move_directions(piece).each do |d_row, d_col|
          new_row = row + d_row
          new_col = col + d_col
          if in_bounds?(new_row, new_col) && board[new_row][new_col].nil?
            moves << { from: [row, col], to: [new_row, new_col] }
          end
        end
        moves
      end

      def find_jumps(board, row, col, piece)
        jumps = []
        opponents = opponent_pieces(piece)

        move_directions(piece).each do |d_row, d_col|
          mid_row = row + d_row
          mid_col = col + d_col
          land_row = row + (d_row * 2)
          land_col = col + (d_col * 2)

          if in_bounds?(land_row, land_col) &&
             opponents.include?(board[mid_row][mid_col]) &&
             board[land_row][land_col].nil?
            jumps << {
              from: [row, col],
              to: [land_row, land_col],
              captures: [[mid_row, mid_col]]
            }
          end
        end

        jumps
      end
    end
  end
end
