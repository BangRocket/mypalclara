require "rails_helper"

RSpec.describe Games::Checkers::AI do
  let(:definition) { Games::Checkers::Definition.new }
  let(:ai) { Games::Checkers::AI.new(definition) }

  describe "#ai_type" do
    it "returns :traditional" do
      expect(ai.ai_type).to eq(:traditional)
    end
  end

  describe "#pick_move" do
    it "returns a legal move" do
      state = definition.new_game
      result = ai.pick_move(state, "red")

      expect(result).to have_key(:move)
      expect(result).to have_key(:reasoning)

      legal = definition.legal_moves(state, "red")
      matching = legal.find { |m| m[:from] == result[:move][:from] && m[:to] == result[:move][:to] }
      expect(matching).not_to be_nil
    end

    it "prefers captures when available" do
      state = definition.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][4][3] = "r"
      state[:board][3][4] = "b"

      result = ai.pick_move(state, "red")
      expect(result[:move][:captures]).not_to be_empty
    end

    it "respects difficulty levels" do
      state = definition.new_game
      %i[easy medium hard].each do |diff|
        result = ai.pick_move(state, "red", difficulty: diff)
        legal = definition.legal_moves(state, "red")
        matching = legal.find { |m| m[:from] == result[:move][:from] && m[:to] == result[:move][:to] }
        expect(matching).not_to be_nil, "difficulty #{diff} returned illegal move"
      end
    end
  end

  describe "#evaluate_position" do
    it "returns 0.0 for even position" do
      state = definition.new_game
      eval_score = ai.evaluate_position(state, "red")
      expect(eval_score).to be_within(0.1).of(0.0)
    end

    it "returns positive when player has more pieces" do
      state = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red" }
      state[:board][4][3] = "r"
      state[:board][4][5] = "r"
      state[:board][3][4] = "b"

      eval_score = ai.evaluate_position(state, "red")
      expect(eval_score).to be > 0.0
    end

    it "returns negative when opponent has more pieces" do
      state = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red" }
      state[:board][4][3] = "r"
      state[:board][3][4] = "b"
      state[:board][3][2] = "b"

      eval_score = ai.evaluate_position(state, "red")
      expect(eval_score).to be < 0.0
    end

    it "values kings higher than men" do
      state_men = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red" }
      state_men[:board][4][3] = "r"
      state_men[:board][4][5] = "r"
      state_men[:board][3][4] = "b"

      state_king = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red" }
      state_king[:board][4][3] = "r"
      state_king[:board][3][4] = "B"  # king

      eval_men = ai.evaluate_position(state_men, "red")
      eval_king = ai.evaluate_position(state_king, "red")

      expect(eval_men).to be > eval_king
    end
  end

  describe "#explain_move" do
    it "mentions captures" do
      state = definition.new_game
      move = { from: [4, 3], to: [2, 5], captures: [[3, 4]] }
      explanation = ai.explain_move(state, move)
      expect(explanation).to include("capture")
    end

    it "mentions kinging" do
      state = definition.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][1][2] = "r"
      move = { from: [1, 2], to: [0, 3] }
      explanation = ai.explain_move(state, move)
      expect(explanation).to include("king")
    end
  end
end
