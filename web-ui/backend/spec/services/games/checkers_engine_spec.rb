require "rails_helper"

RSpec.describe Games::CheckersEngine do
  let(:engine) { Games::CheckersEngine.new }

  describe "#new_game" do
    it "creates a standard 8x8 board with 12 pieces each" do
      state = engine.new_game
      board = state[:board]

      red_count = board.flatten.count { |c| c == "r" }
      black_count = board.flatten.count { |c| c == "b" }

      expect(red_count).to eq(12)
      expect(black_count).to eq(12)
    end
  end

  describe "#legal_moves" do
    it "returns valid moves for a piece" do
      state = engine.new_game
      moves = engine.legal_moves(state, "red")
      expect(moves).not_to be_empty
      moves.each do |move|
        expect(move).to have_key(:from)
        expect(move).to have_key(:to)
      end
    end

    it "forces jumps when available" do
      state = engine.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][4][3] = "r"
      state[:board][3][4] = "b"

      moves = engine.legal_moves(state, "red")
      expect(moves.length).to eq(1)
      expect(moves[0][:to]).to eq([2, 5])
    end
  end

  describe "#apply_move" do
    it "moves a piece to a new position" do
      state = engine.new_game
      moves = engine.legal_moves(state, "red")
      move = moves.first

      new_state = engine.apply_move(state, move)
      expect(new_state[:board][move[:from][0]][move[:from][1]]).to be_nil
      expect(new_state[:board][move[:to][0]][move[:to][1]]).to eq("r")
    end

    it "removes captured pieces on jump" do
      state = engine.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][4][3] = "r"
      state[:board][3][4] = "b"

      move = { from: [4, 3], to: [2, 5], captures: [[3, 4]] }
      new_state = engine.apply_move(state, move)

      expect(new_state[:board][3][4]).to be_nil
      expect(new_state[:board][2][5]).to eq("r")
    end

    it "kings a piece reaching the opposite end" do
      state = engine.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][1][2] = "r"

      move = { from: [1, 2], to: [0, 3] }
      new_state = engine.apply_move(state, move)

      expect(new_state[:board][0][3]).to eq("R")
    end
  end

  describe "#winner" do
    it "returns nil for ongoing game" do
      state = engine.new_game
      expect(engine.winner(state)).to be_nil
    end

    it "returns winner when opponent has no pieces" do
      state = { board: Array.new(8) { Array.new(8, nil) }, captured: {} }
      state[:board][4][3] = "r"
      expect(engine.winner(state)).to eq("red")
    end
  end
end
