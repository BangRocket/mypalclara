require "rails_helper"

RSpec.describe Games::Checkers::Definition do
  let(:definition) { Games::Checkers::Definition.new }

  describe "#game_type" do
    it "returns 'checkers'" do
      expect(definition.game_type).to eq("checkers")
    end
  end

  describe "#new_game" do
    it "creates a standard 8x8 board with 12 pieces each" do
      state = definition.new_game
      board = state[:board]

      expect(board.length).to eq(8)
      board.each { |row| expect(row.length).to eq(8) }

      red_count = board.flatten.count { |c| c == "r" }
      black_count = board.flatten.count { |c| c == "b" }

      expect(red_count).to eq(12)
      expect(black_count).to eq(12)
    end

    it "sets current_player to 'red'" do
      state = definition.new_game
      expect(state[:current_player]).to eq("red")
    end

    it "places black pieces in rows 0-2 on dark squares" do
      state = definition.new_game
      board = state[:board]

      (0..2).each do |row|
        8.times do |col|
          if (row + col).odd?
            expect(board[row][col]).to eq("b"), "Expected 'b' at [#{row}][#{col}]"
          else
            expect(board[row][col]).to be_nil, "Expected nil at [#{row}][#{col}]"
          end
        end
      end
    end

    it "places red pieces in rows 5-7 on dark squares" do
      state = definition.new_game
      board = state[:board]

      (5..7).each do |row|
        8.times do |col|
          if (row + col).odd?
            expect(board[row][col]).to eq("r"), "Expected 'r' at [#{row}][#{col}]"
          else
            expect(board[row][col]).to be_nil, "Expected nil at [#{row}][#{col}]"
          end
        end
      end
    end
  end

  describe "#players" do
    it "returns red and black" do
      state = definition.new_game
      expect(definition.players(state)).to eq(%w[red black])
    end
  end

  describe "#current_player" do
    it "returns current_player from state" do
      state = definition.new_game
      expect(definition.current_player(state)).to eq("red")
    end

    it "reflects player change after a move" do
      state = definition.new_game
      moves = definition.legal_moves(state, "red")
      new_state = definition.apply_move(state, moves.first)
      expect(definition.current_player(new_state)).to eq("black")
    end
  end

  describe "#legal_moves" do
    it "returns valid moves with from and to keys" do
      state = definition.new_game
      moves = definition.legal_moves(state, "red")

      expect(moves).not_to be_empty
      moves.each do |move|
        expect(move).to have_key(:from)
        expect(move).to have_key(:to)
      end
    end

    it "forces jumps when available" do
      state = definition.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][4][3] = "r"
      state[:board][3][4] = "b"

      moves = definition.legal_moves(state, "red")
      expect(moves.length).to eq(1)
      expect(moves[0][:to]).to eq([2, 5])
      expect(moves[0][:captures]).to eq([[3, 4]])
    end

    it "returns simple moves when no jumps exist" do
      state = definition.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][4][3] = "r"

      moves = definition.legal_moves(state, "red")
      expect(moves.length).to eq(2)
      expect(moves.map { |m| m[:to] }).to contain_exactly([3, 2], [3, 4])
    end

    it "returns moves for kings in all four directions" do
      state = definition.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][3][4] = "R"

      moves = definition.legal_moves(state, "red")
      expect(moves.length).to eq(4)
      destinations = moves.map { |m| m[:to] }
      expect(destinations).to contain_exactly([2, 3], [2, 5], [4, 3], [4, 5])
    end

    it "returns empty array when player has no pieces" do
      state = definition.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][4][3] = "r"

      moves = definition.legal_moves(state, "black")
      expect(moves).to be_empty
    end
  end

  describe "#apply_move" do
    it "moves a piece to a new position" do
      state = definition.new_game
      moves = definition.legal_moves(state, "red")
      move = moves.first

      new_state = definition.apply_move(state, move)
      expect(new_state[:board][move[:from][0]][move[:from][1]]).to be_nil
      expect(new_state[:board][move[:to][0]][move[:to][1]]).to eq("r")
    end

    it "removes captured pieces on jump" do
      state = definition.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][4][3] = "r"
      state[:board][3][4] = "b"

      move = { from: [4, 3], to: [2, 5], captures: [[3, 4]] }
      new_state = definition.apply_move(state, move)

      expect(new_state[:board][3][4]).to be_nil
      expect(new_state[:board][2][5]).to eq("r")
    end

    it "kings a red piece reaching row 0" do
      state = definition.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][1][2] = "r"

      move = { from: [1, 2], to: [0, 3] }
      new_state = definition.apply_move(state, move)

      expect(new_state[:board][0][3]).to eq("R")
    end

    it "kings a black piece reaching row 7" do
      state = definition.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][6][3] = "b"

      move = { from: [6, 3], to: [7, 4] }
      new_state = definition.apply_move(state, move)

      expect(new_state[:board][7][4]).to eq("B")
    end

    it "switches current player after a move" do
      state = definition.new_game
      moves = definition.legal_moves(state, "red")
      new_state = definition.apply_move(state, moves.first)

      expect(new_state[:current_player]).to eq("black")
    end

    it "increments turn count" do
      state = definition.new_game
      moves = definition.legal_moves(state, "red")
      new_state = definition.apply_move(state, moves.first)

      expect(new_state[:turn_count]).to eq(1)
    end

    it "does not mutate the original state" do
      state = definition.new_game
      original_board = state[:board].map(&:dup)
      moves = definition.legal_moves(state, "red")
      definition.apply_move(state, moves.first)

      expect(state[:board]).to eq(original_board)
      expect(state[:current_player]).to eq("red")
    end
  end

  describe "#winner" do
    it "returns nil for ongoing game" do
      state = definition.new_game
      expect(definition.winner(state)).to be_nil
    end

    it "returns GameResult with red as winner when black has no pieces" do
      state = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red", turn_count: 0 }
      state[:board][4][3] = "r"

      result = definition.winner(state)
      expect(result).to be_a(Games::GameResult)
      expect(result.status).to eq(:win)
      expect(result.winners).to eq(["red"])
      expect(result.losers).to eq(["black"])
    end

    it "returns GameResult with black as winner when red has no pieces" do
      state = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red", turn_count: 0 }
      state[:board][4][3] = "b"

      result = definition.winner(state)
      expect(result).to be_a(Games::GameResult)
      expect(result.status).to eq(:win)
      expect(result.winners).to eq(["black"])
      expect(result.losers).to eq(["red"])
    end

    it "returns GameResult when current player has no legal moves (stalemate)" do
      # Red piece blocked by edge and black pieces
      state = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red", turn_count: 0 }
      state[:board][0][1] = "r"  # Red at top edge, can't move forward (already at row 0)
      # Actually a non-king red at row 0 has no forward moves (would need to go to row -1)
      state[:board][4][3] = "b"

      result = definition.winner(state)
      expect(result).to be_a(Games::GameResult)
      expect(result.status).to eq(:win)
      expect(result.winners).to eq(["black"])
      expect(result.losers).to eq(["red"])
    end

    it "returns result that responds to over?" do
      state = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red", turn_count: 0 }
      state[:board][4][3] = "r"

      result = definition.winner(state)
      expect(result.over?).to be true
    end
  end

  describe "#game_over?" do
    it "returns false for ongoing game" do
      state = definition.new_game
      expect(definition.game_over?(state)).to be false
    end

    it "returns true when a player has won" do
      state = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red", turn_count: 0 }
      state[:board][4][3] = "r"

      expect(definition.game_over?(state)).to be true
    end
  end
end
