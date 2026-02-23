# Game Engine Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure the game engine into a 4-layer architecture (GameDefinition, GameAI, Orchestrator, Adapters) with event-based Clara commentary and per-game AI strategy (traditional or LLM).

**Architecture:** Games are self-contained packages (definition, ai, llm_adapter, client_adapter). An Orchestrator coordinates turns, delegates to GameAI for move selection, and fires events to ClaraApi for commentary. The Python endpoint gains a new `/event` route for high-tier commentary.

**Tech Stack:** Ruby/Rails (game logic, orchestrator), Python/FastAPI (LLM endpoints), RSpec (tests), pytest (Python tests)

**Design Doc:** `docs/plans/2026-02-22-game-engine-redesign-design.md`

---

## Task 1: Base Classes — GameResult and GameDefinition

**Files:**
- Create: `web-ui/backend/app/services/games/game_result.rb`
- Create: `web-ui/backend/app/services/games/game_definition.rb`
- Create: `web-ui/backend/spec/services/games/game_definition_spec.rb`

**Step 1: Write tests for GameResult**

Create `web-ui/backend/spec/services/games/game_result_spec.rb`:

```ruby
require "rails_helper"

RSpec.describe Games::GameResult do
  describe "#over?" do
    it "returns false for in_progress" do
      result = Games::GameResult.new(status: :in_progress)
      expect(result.over?).to be false
    end

    it "returns true for win" do
      result = Games::GameResult.new(status: :win, winners: ["red"], losers: ["black"])
      expect(result.over?).to be true
    end

    it "returns true for draw" do
      result = Games::GameResult.new(status: :draw, draws: ["p1", "p2"])
      expect(result.over?).to be true
    end
  end

  describe "#draw?" do
    it "returns true for draw status" do
      result = Games::GameResult.new(status: :draw)
      expect(result.draw?).to be true
    end

    it "returns false for win status" do
      result = Games::GameResult.new(status: :win)
      expect(result.draw?).to be false
    end
  end
end
```

**Step 2: Run test — expect FAIL (class not defined)**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/game_result_spec.rb
```

**Step 3: Implement GameResult**

Create `web-ui/backend/app/services/games/game_result.rb`:

```ruby
module Games
  GameResult = Struct.new(:status, :winners, :losers, :draws, keyword_init: true) do
    def over?
      status != :in_progress
    end

    def draw?
      status == :draw
    end
  end
end
```

**Step 4: Run test — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/game_result_spec.rb
```

**Step 5: Write tests for GameDefinition base class**

Create `web-ui/backend/spec/services/games/game_definition_spec.rb`:

```ruby
require "rails_helper"

RSpec.describe Games::GameDefinition do
  let(:definition) { Games::GameDefinition.new }

  describe "interface methods raise NotImplementedError" do
    it "#game_type" do
      expect { definition.game_type }.to raise_error(NotImplementedError)
    end

    it "#new_game" do
      expect { definition.new_game }.to raise_error(NotImplementedError)
    end

    it "#legal_moves" do
      expect { definition.legal_moves({}, "p1") }.to raise_error(NotImplementedError)
    end

    it "#apply_move" do
      expect { definition.apply_move({}, {}) }.to raise_error(NotImplementedError)
    end

    it "#winner" do
      expect { definition.winner({}) }.to raise_error(NotImplementedError)
    end

    it "#current_player" do
      expect { definition.current_player({}) }.to raise_error(NotImplementedError)
    end

    it "#players" do
      expect { definition.players({}) }.to raise_error(NotImplementedError)
    end
  end

  describe "#game_over?" do
    it "delegates to winner" do
      allow(definition).to receive(:winner).and_return(nil)
      expect(definition.game_over?({})).to be false
    end

    it "returns true when winner returns a result" do
      result = Games::GameResult.new(status: :win)
      allow(definition).to receive(:winner).and_return(result)
      expect(definition.game_over?({})).to be true
    end
  end

  describe "#phase" do
    it "returns nil by default" do
      expect(definition.phase({})).to be_nil
    end
  end
end
```

**Step 6: Run test — expect FAIL**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/game_definition_spec.rb
```

**Step 7: Implement GameDefinition**

Create `web-ui/backend/app/services/games/game_definition.rb`:

```ruby
module Games
  class GameDefinition
    def game_type
      raise NotImplementedError, "#{self.class} must implement game_type"
    end

    def new_game(**options)
      raise NotImplementedError, "#{self.class} must implement new_game"
    end

    def legal_moves(state, player)
      raise NotImplementedError, "#{self.class} must implement legal_moves"
    end

    def apply_move(state, move)
      raise NotImplementedError, "#{self.class} must implement apply_move"
    end

    def game_over?(state)
      result = winner(state)
      result.present? && result.over?
    end

    def winner(state)
      raise NotImplementedError, "#{self.class} must implement winner"
    end

    def current_player(state)
      raise NotImplementedError, "#{self.class} must implement current_player"
    end

    def players(state)
      raise NotImplementedError, "#{self.class} must implement players"
    end

    def phase(state)
      nil
    end

    protected

    def deep_copy_state(state)
      state.deep_dup
    end
  end
end
```

**Step 8: Run tests — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/game_result_spec.rb spec/services/games/game_definition_spec.rb
```

**Step 9: Commit**

```bash
cd web-ui/backend
git add app/services/games/game_result.rb app/services/games/game_definition.rb \
  spec/services/games/game_result_spec.rb spec/services/games/game_definition_spec.rb
git commit -m "feat: add GameResult struct and GameDefinition base class"
```

---

## Task 2: Base Classes — GameAI, LLMAdapter, ClientAdapter

**Files:**
- Create: `web-ui/backend/app/services/games/game_ai.rb`
- Create: `web-ui/backend/app/services/games/llm_adapter.rb`
- Create: `web-ui/backend/app/services/games/client_adapter.rb`
- Create: `web-ui/backend/spec/services/games/game_ai_spec.rb`

**Step 1: Write tests for GameAI base class**

Create `web-ui/backend/spec/services/games/game_ai_spec.rb`:

```ruby
require "rails_helper"

RSpec.describe Games::GameAI do
  let(:definition) { instance_double(Games::GameDefinition) }
  let(:ai) { Games::GameAI.new(definition) }

  describe "#ai_type" do
    it "raises NotImplementedError" do
      expect { ai.ai_type }.to raise_error(NotImplementedError)
    end
  end

  describe "#pick_move" do
    it "raises NotImplementedError" do
      expect { ai.pick_move({}, "p1") }.to raise_error(NotImplementedError)
    end
  end

  describe "#evaluate_position" do
    it "returns 0.0 by default" do
      expect(ai.evaluate_position({}, "p1")).to eq(0.0)
    end
  end

  describe "#explain_move" do
    it "returns empty string by default" do
      expect(ai.explain_move({}, {})).to eq("")
    end
  end
end
```

**Step 2: Run test — expect FAIL**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/game_ai_spec.rb
```

**Step 3: Implement GameAI, LLMAdapter, ClientAdapter**

Create `web-ui/backend/app/services/games/game_ai.rb`:

```ruby
module Games
  class GameAI
    attr_reader :definition

    def initialize(definition)
      @definition = definition
    end

    def ai_type
      raise NotImplementedError, "#{self.class} must implement ai_type"
    end

    def pick_move(state, player, difficulty: :medium)
      raise NotImplementedError, "#{self.class} must implement pick_move"
    end

    def evaluate_position(state, player)
      0.0
    end

    def explain_move(state, move)
      ""
    end
  end
end
```

Create `web-ui/backend/app/services/games/llm_adapter.rb`:

```ruby
module Games
  class LLMAdapter
    attr_reader :definition

    def initialize(definition)
      @definition = definition
    end

    def state_summary(state, perspective:)
      raise NotImplementedError, "#{self.class} must implement state_summary"
    end

    def describe_moves(moves, state:)
      raise NotImplementedError, "#{self.class} must implement describe_moves"
    end

    def relevant_history(history, state:, limit: 5)
      history.last(limit)
    end
  end
end
```

Create `web-ui/backend/app/services/games/client_adapter.rb`:

```ruby
module Games
  class ClientAdapter
    attr_reader :definition

    def initialize(definition)
      @definition = definition
    end

    def state_for_client(state, perspective:)
      raise NotImplementedError, "#{self.class} must implement state_for_client"
    end

    def available_actions(state, player)
      raise NotImplementedError, "#{self.class} must implement available_actions"
    end
  end
end
```

**Step 4: Run test — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/game_ai_spec.rb
```

**Step 5: Commit**

```bash
cd web-ui/backend
git add app/services/games/game_ai.rb app/services/games/llm_adapter.rb \
  app/services/games/client_adapter.rb spec/services/games/game_ai_spec.rb
git commit -m "feat: add GameAI, LLMAdapter, and ClientAdapter base classes"
```

---

## Task 3: Checkers Definition (extract from CheckersEngine)

**Files:**
- Create: `web-ui/backend/app/services/games/checkers/definition.rb`
- Create: `web-ui/backend/spec/services/games/checkers/definition_spec.rb`

**Step 1: Write tests**

Create `web-ui/backend/spec/services/games/checkers/definition_spec.rb`:

```ruby
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

      red_count = board.flatten.count { |c| c == "r" }
      black_count = board.flatten.count { |c| c == "b" }

      expect(red_count).to eq(12)
      expect(black_count).to eq(12)
      expect(state[:current_player]).to eq("red")
    end
  end

  describe "#legal_moves" do
    it "returns valid moves for a piece" do
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

    it "kings a piece reaching the opposite end" do
      state = definition.new_game
      state[:board] = Array.new(8) { Array.new(8, nil) }
      state[:board][1][2] = "r"

      move = { from: [1, 2], to: [0, 3] }
      new_state = definition.apply_move(state, move)

      expect(new_state[:board][0][3]).to eq("R")
    end

    it "switches current player" do
      state = definition.new_game
      moves = definition.legal_moves(state, "red")
      new_state = definition.apply_move(state, moves.first)
      expect(new_state[:current_player]).to eq("black")
    end
  end

  describe "#winner" do
    it "returns nil for ongoing game" do
      state = definition.new_game
      expect(definition.winner(state)).to be_nil
    end

    it "returns GameResult when opponent has no pieces" do
      state = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red" }
      state[:board][4][3] = "r"
      result = definition.winner(state)
      expect(result).to be_a(Games::GameResult)
      expect(result.status).to eq(:win)
      expect(result.winners).to eq(["red"])
      expect(result.losers).to eq(["black"])
    end
  end

  describe "#current_player" do
    it "returns current player from state" do
      state = definition.new_game
      expect(definition.current_player(state)).to eq("red")
    end
  end

  describe "#players" do
    it "returns red and black" do
      state = definition.new_game
      expect(definition.players(state)).to eq(%w[red black])
    end
  end
end
```

**Step 2: Run test — expect FAIL**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/checkers/definition_spec.rb
```

**Step 3: Implement Checkers::Definition**

Create `web-ui/backend/app/services/games/checkers/definition.rb`:

This is extracted from `checkers_engine.rb` with these changes:
- Inherits `GameDefinition` instead of `GameEngine`
- Adds `game_type` returning `"checkers"`
- `winner` returns `GameResult` instead of a string
- `apply_move(state, move)` signature (already correct — checkers never used player_id arg)

```ruby
module Games
  module Checkers
    class Definition < GameDefinition
      BOARD_SIZE = 8

      def game_type
        "checkers"
      end

      def new_game(**options)
        board = Array.new(BOARD_SIZE) { Array.new(BOARD_SIZE, nil) }

        (0..2).each do |row|
          BOARD_SIZE.times do |col|
            board[row][col] = "b" if (row + col).odd?
          end
        end

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

        if move[:captures]
          move[:captures].each do |cap_row, cap_col|
            board[cap_row][cap_col] = nil
          end
        end

        if piece == "r" && to_row == 0
          board[to_row][to_col] = "R"
        elsif piece == "b" && to_row == BOARD_SIZE - 1
          board[to_row][to_col] = "B"
        end

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
        when "r"  then [[-1, -1], [-1, 1]]
        when "b"  then [[1, -1], [1, 1]]
        when "R", "B" then [[-1, -1], [-1, 1], [1, -1], [1, 1]]
        else []
        end
      end

      def in_bounds?(row, col)
        row >= 0 && row < BOARD_SIZE && col >= 0 && col < BOARD_SIZE
      end

      def opponent_pieces(piece)
        case piece
        when "r", "R" then %w[b B]
        when "b", "B" then %w[r R]
        else []
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
```

**Step 4: Run test — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/checkers/definition_spec.rb
```

**Step 5: Commit**

```bash
cd web-ui/backend
git add app/services/games/checkers/definition.rb spec/services/games/checkers/definition_spec.rb
git commit -m "feat: extract Checkers::Definition from CheckersEngine"
```

---

## Task 4: Blackjack Definition (extract from BlackjackEngine)

**Files:**
- Create: `web-ui/backend/app/services/games/blackjack/definition.rb`
- Create: `web-ui/backend/spec/services/games/blackjack/definition_spec.rb`

**Step 1: Write tests**

Create `web-ui/backend/spec/services/games/blackjack/definition_spec.rb`:

```ruby
require "rails_helper"

RSpec.describe Games::Blackjack::Definition do
  let(:definition) { Games::Blackjack::Definition.new }

  describe "#game_type" do
    it "returns 'blackjack'" do
      expect(definition.game_type).to eq("blackjack")
    end
  end

  describe "#new_game" do
    it "creates a shuffled deck and empty hands" do
      state = definition.new_game
      expect(state[:deck].length).to eq(52)
      expect(state[:dealer_hand]).to eq([])
      expect(state[:phase]).to eq(:dealing)
    end
  end

  describe "#deal" do
    it "deals two cards to each player and two to dealer" do
      state = definition.new_game
      player_ids = ["player-1", "player-2"]
      state = definition.deal(state, player_ids)

      expect(state[:hands]["player-1"].length).to eq(2)
      expect(state[:hands]["player-2"].length).to eq(2)
      expect(state[:dealer_hand].length).to eq(2)
      expect(state[:phase]).to eq(:player_turns)
      expect(state[:deck].length).to eq(46)
    end
  end

  describe "#hand_value" do
    it "counts number cards at face value" do
      expect(definition.hand_value(["7S", "3H"])).to eq(10)
    end

    it "counts face cards as 10" do
      expect(definition.hand_value(["KS", "QH"])).to eq(20)
    end

    it "counts ace as 11 when safe" do
      expect(definition.hand_value(["AS", "7H"])).to eq(18)
    end

    it "counts ace as 1 when 11 would bust" do
      expect(definition.hand_value(["AS", "7H", "8D"])).to eq(16)
    end

    it "detects blackjack" do
      expect(definition.hand_value(["AS", "KH"])).to eq(21)
    end
  end

  describe "#legal_moves" do
    it "returns hit and stand for normal hand" do
      state = { hands: { "p1" => ["7S", "3H"] }, phase: :player_turns }
      moves = definition.legal_moves(state, "p1")
      expect(moves).to include("hit", "stand")
    end

    it "returns empty for busted hand" do
      state = { hands: { "p1" => ["KS", "QH", "5D"] }, phase: :player_turns }
      moves = definition.legal_moves(state, "p1")
      expect(moves).to eq([])
    end

    it "includes double_down on first two cards" do
      state = { hands: { "p1" => ["7S", "3H"] }, phase: :player_turns }
      moves = definition.legal_moves(state, "p1")
      expect(moves).to include("double_down")
    end

    it "excludes double_down after hit" do
      state = { hands: { "p1" => ["7S", "3H", "2D"] }, phase: :player_turns }
      moves = definition.legal_moves(state, "p1")
      expect(moves).not_to include("double_down")
    end
  end

  describe "#apply_move" do
    it "adds a card on hit" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      hand_before = state[:hands]["p1"].length
      move = { player: "p1", action: "hit" }
      state = definition.apply_move(state, move)
      expect(state[:hands]["p1"].length).to eq(hand_before + 1)
    end

    it "marks player as stood on stand" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      move = { player: "p1", action: "stand" }
      state = definition.apply_move(state, move)
      expect(state[:stood]).to include("p1")
    end
  end

  describe "#phase" do
    it "returns current phase" do
      state = definition.new_game
      expect(definition.phase(state)).to eq(:dealing)
    end
  end

  describe "#resolve" do
    it "determines winners correctly" do
      state = {
        hands: { "p1" => ["KS", "9H"] },
        dealer_hand: ["KD", "7C"],
        deck: [],
        phase: :resolving,
        stood: ["p1"]
      }
      results = definition.resolve(state)
      expect(results["p1"]).to eq("won")
    end

    it "busted players lose" do
      state = {
        hands: { "p1" => ["KS", "QH", "5D"] },
        dealer_hand: ["KD", "7C"],
        deck: [],
        phase: :resolving,
        stood: []
      }
      results = definition.resolve(state)
      expect(results["p1"]).to eq("lost")
    end
  end

  describe "#winner" do
    it "returns nil before resolving phase" do
      state = definition.new_game
      expect(definition.winner(state)).to be_nil
    end

    it "returns GameResult in resolving phase" do
      state = {
        hands: { "p1" => ["KS", "9H"] },
        dealer_hand: ["KD", "7C"],
        deck: [],
        phase: :resolving,
        stood: ["p1"]
      }
      result = definition.winner(state)
      expect(result).to be_a(Games::GameResult)
      expect(result.winners).to include("p1")
    end
  end
end
```

**Step 2: Run test — expect FAIL**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/blackjack/definition_spec.rb
```

**Step 3: Implement Blackjack::Definition**

Create `web-ui/backend/app/services/games/blackjack/definition.rb`:

Key changes from BlackjackEngine:
- Inherits `GameDefinition` instead of `GameEngine`
- `apply_move(state, move)` — move is `{ player: "p1", action: "hit" }` instead of separate args
- Phase uses symbols (`:dealing`, `:player_turns`, `:resolving`)
- `winner` returns `GameResult`

```ruby
module Games
  module Blackjack
    class Definition < GameDefinition
      SUITS = %w[S H D C].freeze
      RANKS = %w[A 2 3 4 5 6 7 8 9 10 J Q K].freeze

      def game_type
        "blackjack"
      end

      def new_game(**options)
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

      def legal_moves(state, player_id)
        hand = state[:hands][player_id]
        return [] if hand.nil?

        value = hand_value(hand)
        return [] if value > 21

        moves = %w[hit stand]
        moves << "double_down" if hand.length == 2
        moves
      end

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

      def winner(state)
        return nil unless state[:phase] == :resolving

        results = resolve(state)
        winners = results.select { |_, v| v == "won" }.keys
        losers = results.select { |_, v| v == "lost" }.keys
        draws = results.select { |_, v| v == "draw" }.keys

        GameResult.new(
          status: draws.length == results.length ? :draw : :win,
          winners: winners,
          losers: losers,
          draws: draws
        )
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
```

**Step 4: Run test — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/blackjack/definition_spec.rb
```

**Step 5: Commit**

```bash
cd web-ui/backend
git add app/services/games/blackjack/definition.rb spec/services/games/blackjack/definition_spec.rb
git commit -m "feat: extract Blackjack::Definition from BlackjackEngine"
```

---

## Task 5: Checkers AI (minimax)

**Files:**
- Create: `web-ui/backend/app/services/games/checkers/ai.rb`
- Create: `web-ui/backend/spec/services/games/checkers/ai_spec.rb`

**Step 1: Write tests**

Create `web-ui/backend/spec/services/games/checkers/ai_spec.rb`:

```ruby
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
      # All difficulty levels should return valid moves
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
      # Two men vs one king — king is worth 1.5, so 2 men (2.0) > 1 king (1.5)
      state_men = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red" }
      state_men[:board][4][3] = "r"
      state_men[:board][4][5] = "r"
      state_men[:board][3][4] = "b"

      state_king = { board: Array.new(8) { Array.new(8, nil) }, captured: {}, current_player: "red" }
      state_king[:board][4][3] = "r"
      state_king[:board][3][4] = "B"  # king

      eval_men = ai.evaluate_position(state_men, "red")
      eval_king = ai.evaluate_position(state_king, "red")

      # With 2 men vs 1 man, red is ahead. With 1 man vs 1 king, red is behind.
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
```

**Step 2: Run test — expect FAIL**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/checkers/ai_spec.rb
```

**Step 3: Implement Checkers::AI**

Create `web-ui/backend/app/services/games/checkers/ai.rb`:

```ruby
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
        # Slight preference for non-captures (plays conservatively / makes mistakes)
        non_captures = legal.reject { |m| m[:captures]&.any? }
        pool = non_captures.any? && rand < 0.4 ? non_captures : legal
        pool.sample
      end

      def pick_medium(state, player, legal)
        # Score moves with simple heuristics, pick from top candidates
        scored = legal.map { |m| [m, score_move(state, player, m)] }
        scored.sort_by! { |_, s| -s }

        # Pick from top 3 with weighted randomness
        top = scored.first(3)
        top.sample.first
      end

      def pick_hard(state, player, legal)
        # Minimax with alpha-beta pruning
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

        # Kinging bonus
        piece = state[:board][move[:from][0]][move[:from][1]]
        if (piece == "r" && move[:to][0] == 0) || (piece == "b" && move[:to][0] == 7)
          score += 2
        end

        # Center control bonus
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
```

**Step 4: Run test — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/checkers/ai_spec.rb
```

**Step 5: Commit**

```bash
cd web-ui/backend
git add app/services/games/checkers/ai.rb spec/services/games/checkers/ai_spec.rb
git commit -m "feat: add Checkers::AI with minimax and alpha-beta pruning"
```

---

## Task 6: Blackjack AI (LLM-delegating with evaluate_position)

**Files:**
- Create: `web-ui/backend/app/services/games/blackjack/ai.rb`
- Create: `web-ui/backend/spec/services/games/blackjack/ai_spec.rb`

**Step 1: Write tests**

Create `web-ui/backend/spec/services/games/blackjack/ai_spec.rb`:

```ruby
require "rails_helper"

RSpec.describe Games::Blackjack::AI do
  let(:definition) { Games::Blackjack::Definition.new }
  let(:ai) { Games::Blackjack::AI.new(definition) }

  describe "#ai_type" do
    it "returns :llm" do
      expect(ai.ai_type).to eq(:llm)
    end
  end

  describe "#evaluate_position" do
    it "returns -1.0 for busted hand" do
      state = { hands: { "p1" => ["KS", "QH", "5D"] }, dealer_hand: ["7C"] }
      expect(ai.evaluate_position(state, "p1")).to eq(-1.0)
    end

    it "returns high score for 21" do
      state = { hands: { "p1" => ["AS", "KH"] }, dealer_hand: ["7C"] }
      eval_score = ai.evaluate_position(state, "p1")
      expect(eval_score).to be > 0.8
    end

    it "returns moderate score for 17-19" do
      state = { hands: { "p1" => ["KS", "8H"] }, dealer_hand: ["7C"] }
      eval_score = ai.evaluate_position(state, "p1")
      expect(eval_score).to be_between(-0.5, 0.5)
    end

    it "returns low score for under 17" do
      state = { hands: { "p1" => ["7S", "5H"] }, dealer_hand: ["KD"] }
      eval_score = ai.evaluate_position(state, "p1")
      expect(eval_score).to be < 0.0
    end
  end

  describe "#explain_move" do
    it "explains hit" do
      state = { hands: { "p1" => ["7S", "5H"] }, dealer_hand: ["6C"] }
      explanation = ai.explain_move(state, { player: "p1", action: "hit" })
      expect(explanation).to be_a(String)
      expect(explanation).not_to be_empty
    end

    it "explains stand" do
      state = { hands: { "p1" => ["KS", "8H"] }, dealer_hand: ["6C"] }
      explanation = ai.explain_move(state, { player: "p1", action: "stand" })
      expect(explanation).to be_a(String)
      expect(explanation).not_to be_empty
    end
  end

  describe "#pick_move" do
    it "raises NotImplementedError (LLM-delegated)" do
      state = { hands: { "p1" => ["7S", "5H"] }, dealer_hand: ["6C"], phase: :player_turns }
      expect { ai.pick_move(state, "p1") }.to raise_error(NotImplementedError)
    end
  end
end
```

**Step 2: Run test — expect FAIL**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/blackjack/ai_spec.rb
```

**Step 3: Implement Blackjack::AI**

Create `web-ui/backend/app/services/games/blackjack/ai.rb`:

```ruby
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
```

**Step 4: Run test — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/blackjack/ai_spec.rb
```

**Step 5: Commit**

```bash
cd web-ui/backend
git add app/services/games/blackjack/ai.rb spec/services/games/blackjack/ai_spec.rb
git commit -m "feat: add Blackjack::AI with LLM delegation and position evaluation"
```

---

## Task 7: LLM Adapters (Checkers + Blackjack)

**Files:**
- Create: `web-ui/backend/app/services/games/checkers/llm_adapter.rb`
- Create: `web-ui/backend/app/services/games/blackjack/llm_adapter.rb`
- Create: `web-ui/backend/spec/services/games/checkers/llm_adapter_spec.rb`
- Create: `web-ui/backend/spec/services/games/blackjack/llm_adapter_spec.rb`

**Step 1: Write Checkers LLM adapter tests**

Create `web-ui/backend/spec/services/games/checkers/llm_adapter_spec.rb`:

```ruby
require "rails_helper"

RSpec.describe Games::Checkers::LLMAdapter do
  let(:definition) { Games::Checkers::Definition.new }
  let(:adapter) { Games::Checkers::LLMAdapter.new(definition) }

  describe "#state_summary" do
    it "describes piece counts and current turn" do
      state = definition.new_game
      summary = adapter.state_summary(state, perspective: "red")

      expect(summary).to include("12")
      expect(summary).to include("Red")
    end

    it "mentions kings when present" do
      state = definition.new_game
      state[:board][0][1] = "R"  # Add a king
      summary = adapter.state_summary(state, perspective: "red")

      expect(summary).to include("king")
    end
  end

  describe "#describe_moves" do
    it "returns descriptions for each move" do
      state = definition.new_game
      moves = definition.legal_moves(state, "red")
      descriptions = adapter.describe_moves(moves, state: state)

      expect(descriptions.length).to eq(moves.length)
      descriptions.each do |desc|
        expect(desc).to have_key(:move)
        expect(desc).to have_key(:description)
        expect(desc[:description]).to be_a(String)
      end
    end

    it "mentions captures in description" do
      move = { from: [4, 3], to: [2, 5], captures: [[3, 4]] }
      descriptions = adapter.describe_moves([move], state: definition.new_game)
      expect(descriptions.first[:description]).to include("captur")
    end
  end
end
```

**Step 2: Write Blackjack LLM adapter tests**

Create `web-ui/backend/spec/services/games/blackjack/llm_adapter_spec.rb`:

```ruby
require "rails_helper"

RSpec.describe Games::Blackjack::LLMAdapter do
  let(:definition) { Games::Blackjack::Definition.new }
  let(:adapter) { Games::Blackjack::LLMAdapter.new(definition) }

  describe "#state_summary" do
    it "describes hand and dealer card" do
      state = {
        hands: { "clara" => ["KS", "7H"] },
        dealer_hand: ["10D", "3C"],
        phase: :player_turns
      }
      summary = adapter.state_summary(state, perspective: "clara")

      expect(summary).to include("17")   # hand value
      expect(summary).to include("10D")  # dealer showing
    end
  end

  describe "#describe_moves" do
    it "returns descriptions for each move" do
      moves = %w[hit stand double_down]
      descriptions = adapter.describe_moves(moves, state: {})

      expect(descriptions.length).to eq(3)
      descriptions.each do |desc|
        expect(desc).to have_key(:id)
        expect(desc).to have_key(:description)
      end
    end
  end
end
```

**Step 3: Run tests — expect FAIL**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/checkers/llm_adapter_spec.rb spec/services/games/blackjack/llm_adapter_spec.rb
```

**Step 4: Implement Checkers::LLMAdapter**

Create `web-ui/backend/app/services/games/checkers/llm_adapter.rb`:

```ruby
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
```

**Step 5: Implement Blackjack::LLMAdapter**

Create `web-ui/backend/app/services/games/blackjack/llm_adapter.rb`:

```ruby
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
```

**Step 6: Run tests — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/checkers/llm_adapter_spec.rb spec/services/games/blackjack/llm_adapter_spec.rb
```

**Step 7: Commit**

```bash
cd web-ui/backend
git add app/services/games/checkers/llm_adapter.rb app/services/games/blackjack/llm_adapter.rb \
  spec/services/games/checkers/llm_adapter_spec.rb spec/services/games/blackjack/llm_adapter_spec.rb
git commit -m "feat: add LLM adapters for Checkers and Blackjack"
```

---

## Task 8: Client Adapters (Checkers + Blackjack)

**Files:**
- Create: `web-ui/backend/app/services/games/checkers/client_adapter.rb`
- Create: `web-ui/backend/app/services/games/blackjack/client_adapter.rb`
- Create: `web-ui/backend/spec/services/games/checkers/client_adapter_spec.rb`
- Create: `web-ui/backend/spec/services/games/blackjack/client_adapter_spec.rb`

**Step 1: Write tests**

Create `web-ui/backend/spec/services/games/checkers/client_adapter_spec.rb`:

```ruby
require "rails_helper"

RSpec.describe Games::Checkers::ClientAdapter do
  let(:definition) { Games::Checkers::Definition.new }
  let(:adapter) { Games::Checkers::ClientAdapter.new(definition) }

  describe "#state_for_client" do
    it "includes board and current player" do
      state = definition.new_game
      client_state = adapter.state_for_client(state, perspective: "red")

      expect(client_state[:board]).to be_a(Array)
      expect(client_state[:current_player]).to eq("red")
    end
  end

  describe "#available_actions" do
    it "returns legal moves for current player" do
      state = definition.new_game
      actions = adapter.available_actions(state, "red")

      expect(actions).not_to be_empty
      actions.each do |action|
        expect(action).to have_key(:from)
        expect(action).to have_key(:to)
      end
    end

    it "returns empty for non-current player" do
      state = definition.new_game
      actions = adapter.available_actions(state, "black")
      expect(actions).to be_empty
    end
  end
end
```

Create `web-ui/backend/spec/services/games/blackjack/client_adapter_spec.rb`:

```ruby
require "rails_helper"

RSpec.describe Games::Blackjack::ClientAdapter do
  let(:definition) { Games::Blackjack::Definition.new }
  let(:adapter) { Games::Blackjack::ClientAdapter.new(definition) }

  describe "#state_for_client" do
    it "includes hands and phase" do
      state = definition.new_game
      state = definition.deal(state, ["p1"])
      client_state = adapter.state_for_client(state, perspective: "p1")

      expect(client_state[:hands]).to be_a(Hash)
      expect(client_state[:phase]).to eq(:player_turns)
      expect(client_state[:dealer_hand]).to be_a(Array)
    end
  end

  describe "#available_actions" do
    it "returns legal moves for player" do
      state = { hands: { "p1" => ["7S", "3H"] }, phase: :player_turns }
      actions = adapter.available_actions(state, "p1")

      expect(actions).to include("hit", "stand", "double_down")
    end
  end
end
```

**Step 2: Run tests — expect FAIL**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/checkers/client_adapter_spec.rb spec/services/games/blackjack/client_adapter_spec.rb
```

**Step 3: Implement adapters**

Create `web-ui/backend/app/services/games/checkers/client_adapter.rb`:

```ruby
module Games
  module Checkers
    class ClientAdapter < Games::ClientAdapter
      def state_for_client(state, perspective:)
        {
          board: state[:board],
          current_player: state[:current_player],
          captured: state[:captured],
          turn_count: state[:turn_count]
        }
      end

      def available_actions(state, player)
        return [] unless state[:current_player] == player

        definition.legal_moves(state, player).map do |move|
          {
            from: move[:from],
            to: move[:to],
            captures: move[:captures],
            type: move[:captures]&.any? ? :jump : :move
          }
        end
      end
    end
  end
end
```

Create `web-ui/backend/app/services/games/blackjack/client_adapter.rb`:

```ruby
module Games
  module Blackjack
    class ClientAdapter < Games::ClientAdapter
      def state_for_client(state, perspective:)
        {
          hands: state[:hands],
          dealer_hand: state[:dealer_hand],
          phase: state[:phase],
          stood: state[:stood],
          current_player_index: state[:current_player_index],
          turn_count: state[:turn_count]
        }
      end

      def available_actions(state, player)
        definition.legal_moves(state, player)
      end
    end
  end
end
```

**Step 4: Run tests — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/checkers/client_adapter_spec.rb spec/services/games/blackjack/client_adapter_spec.rb
```

**Step 5: Commit**

```bash
cd web-ui/backend
git add app/services/games/checkers/client_adapter.rb app/services/games/blackjack/client_adapter.rb \
  spec/services/games/checkers/client_adapter_spec.rb spec/services/games/blackjack/client_adapter_spec.rb
git commit -m "feat: add client adapters for Checkers and Blackjack"
```

---

## Task 9: Game Registry

**Files:**
- Create: `web-ui/backend/app/services/games/registry.rb`
- Create: `web-ui/backend/spec/services/games/registry_spec.rb`

**Step 1: Write tests**

Create `web-ui/backend/spec/services/games/registry_spec.rb`:

```ruby
require "rails_helper"

RSpec.describe Games::Registry do
  describe ".package_for" do
    it "returns checkers package" do
      package = Games::Registry.package_for("checkers")

      expect(package[:definition]).to be_a(Games::Checkers::Definition)
      expect(package[:ai]).to be_a(Games::Checkers::AI)
      expect(package[:llm_adapter]).to be_a(Games::Checkers::LLMAdapter)
      expect(package[:client_adapter]).to be_a(Games::Checkers::ClientAdapter)
    end

    it "returns blackjack package" do
      package = Games::Registry.package_for("blackjack")

      expect(package[:definition]).to be_a(Games::Blackjack::Definition)
      expect(package[:ai]).to be_a(Games::Blackjack::AI)
      expect(package[:llm_adapter]).to be_a(Games::Blackjack::LLMAdapter)
      expect(package[:client_adapter]).to be_a(Games::Blackjack::ClientAdapter)
    end

    it "raises for unknown game type" do
      expect { Games::Registry.package_for("unknown") }.to raise_error(ArgumentError, /Unknown game type/)
    end

    it "shares the definition instance across components" do
      package = Games::Registry.package_for("checkers")
      expect(package[:ai].definition).to equal(package[:definition])
      expect(package[:llm_adapter].definition).to equal(package[:definition])
      expect(package[:client_adapter].definition).to equal(package[:definition])
    end
  end
end
```

**Step 2: Run test — expect FAIL**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/registry_spec.rb
```

**Step 3: Implement Registry**

Create `web-ui/backend/app/services/games/registry.rb`:

```ruby
module Games
  class Registry
    def self.package_for(game_type)
      case game_type
      when "checkers"
        build_package(
          Games::Checkers::Definition,
          Games::Checkers::AI,
          Games::Checkers::LLMAdapter,
          Games::Checkers::ClientAdapter
        )
      when "blackjack"
        build_package(
          Games::Blackjack::Definition,
          Games::Blackjack::AI,
          Games::Blackjack::LLMAdapter,
          Games::Blackjack::ClientAdapter
        )
      else
        raise ArgumentError, "Unknown game type: #{game_type}"
      end
    end

    def self.build_package(definition_class, ai_class, llm_class, client_class)
      definition = definition_class.new
      {
        definition: definition,
        ai: ai_class.new(definition),
        llm_adapter: llm_class.new(definition),
        client_adapter: client_class.new(definition)
      }
    end

    private_class_method :build_package
  end
end
```

**Step 4: Run test — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/registry_spec.rb
```

**Step 5: Commit**

```bash
cd web-ui/backend
git add app/services/games/registry.rb spec/services/games/registry_spec.rb
git commit -m "feat: add Games::Registry for game package lookup"
```

---

## Task 10: ClaraApi — Add game_event method

**Files:**
- Modify: `web-ui/backend/app/services/clara_api.rb`
- Create: `web-ui/backend/spec/services/clara_api_spec.rb`

**Step 1: Write tests**

Create `web-ui/backend/spec/services/clara_api_spec.rb`:

```ruby
require "rails_helper"
require "webmock/rspec"

RSpec.describe ClaraApi do
  let(:api) { ClaraApi.new }

  before do
    ENV["CLARA_API_URL"] = "https://test.example.com"
    ENV["GAME_API_KEY"] = "test-key"
  end

  describe "#game_event" do
    it "posts to /api/v1/game/event" do
      stub = stub_request(:post, "https://test.example.com/api/v1/game/event")
        .with(
          headers: { "Content-Type" => "application/json", "X-Game-API-Key" => "test-key" },
          body: hash_including(event_type: "clara_move", game_type: "checkers")
        )
        .to_return(
          status: 200,
          body: { commentary: "Nice move!", mood: "smug" }.to_json,
          headers: { "Content-Type" => "application/json" }
        )

      result = api.game_event(
        event_type: "clara_move",
        game_type: "checkers",
        state_summary: "You're playing Red. 12 pieces each.",
        user_id: "user-1",
        event_data: { move: { from: [5, 2], to: [4, 3] } },
        position_eval: 0.3,
        recent_history: []
      )

      expect(stub).to have_been_requested
      expect(result[:commentary]).to eq("Nice move!")
      expect(result[:mood]).to eq("smug")
    end

    it "returns fallback on timeout" do
      stub_request(:post, "https://test.example.com/api/v1/game/event")
        .to_timeout

      result = api.game_event(
        event_type: "clara_move",
        game_type: "checkers",
        state_summary: "test",
        user_id: "user-1"
      )

      expect(result[:commentary]).to be_nil
      expect(result[:mood]).to eq("neutral")
    end

    it "returns fallback on error response" do
      stub_request(:post, "https://test.example.com/api/v1/game/event")
        .to_return(status: 500, body: "Internal Server Error")

      result = api.game_event(
        event_type: "clara_move",
        game_type: "checkers",
        state_summary: "test",
        user_id: "user-1"
      )

      expect(result[:commentary]).to be_nil
      expect(result[:mood]).to eq("neutral")
    end
  end

  describe "#get_move" do
    it "posts to /api/v1/game/move" do
      stub = stub_request(:post, "https://test.example.com/api/v1/game/move")
        .to_return(
          status: 200,
          body: { move: { type: "hit" }, commentary: "Let's go!", mood: "happy" }.to_json,
          headers: { "Content-Type" => "application/json" }
        )

      result = api.get_move(
        game_type: "blackjack",
        game_state: {},
        legal_moves: ["hit", "stand"],
        personality: "clara",
        user_id: "user-1"
      )

      expect(stub).to have_been_requested
      expect(result[:move][:type]).to eq("hit")
    end
  end
end
```

**Step 2: Run test — expect FAIL (game_event method doesn't exist)**

```bash
cd web-ui/backend && bundle exec rspec spec/services/clara_api_spec.rb
```

**Step 3: Rewrite ClaraApi**

Read the current file first (already read above). Replace with:

`web-ui/backend/app/services/clara_api.rb`:

```ruby
class ClaraApi
  TIMEOUT = 10

  def initialize
    @base_url = ENV.fetch("CLARA_API_URL", "https://mypalclara.com")
    @api_key = ENV.fetch("GAME_API_KEY")
  end

  # LLM move selection (mid/low tier, for ai_type: :llm games)
  def get_move(game_type:, game_state:, legal_moves:, personality:, user_id:, move_history: [])
    post("/api/v1/game/move", {
      game_type: game_type,
      game_state: game_state,
      legal_moves: legal_moves,
      personality: personality,
      user_id: user_id,
      move_history: move_history
    }) || fallback_move(legal_moves)
  end

  # Event-based commentary (high tier, memory-enabled)
  def game_event(event_type:, game_type:, state_summary:, user_id:,
                 event_data: {}, position_eval: 0.0, recent_history: [])
    post("/api/v1/game/event", {
      event_type: event_type,
      game_type: game_type,
      state_summary: state_summary,
      event_data: event_data,
      position_eval: position_eval,
      user_id: user_id,
      recent_history: recent_history
    }) || fallback_commentary
  end

  private

  def post(path, body)
    uri = URI("#{@base_url}#{path}")

    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = uri.scheme == "https"
    http.open_timeout = TIMEOUT
    http.read_timeout = TIMEOUT

    request = Net::HTTP::Post.new(uri)
    request["Content-Type"] = "application/json"
    request["X-Game-API-Key"] = @api_key
    request.body = body.to_json

    response = http.request(request)

    if response.is_a?(Net::HTTPSuccess)
      JSON.parse(response.body, symbolize_names: true)
    else
      Rails.logger.error("ClaraApi error: #{response.code} #{response.body}")
      nil
    end
  rescue Net::OpenTimeout, Net::ReadTimeout, StandardError => e
    Rails.logger.error("ClaraApi error: #{e.class} - #{e.message}")
    nil
  end

  def fallback_move(legal_moves)
    {
      move: { type: legal_moves.sample },
      commentary: "Give me a second... okay, here goes.",
      mood: "nervous"
    }
  end

  def fallback_commentary
    { commentary: nil, mood: "neutral" }
  end
end
```

**Step 4: Run test — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/clara_api_spec.rb
```

**Step 5: Commit**

```bash
cd web-ui/backend
git add app/services/clara_api.rb spec/services/clara_api_spec.rb
git commit -m "feat: add ClaraApi.game_event for event-based commentary"
```

---

## Task 11: Orchestrator

**Files:**
- Create: `web-ui/backend/app/services/games/orchestrator.rb`
- Create: `web-ui/backend/spec/services/games/orchestrator_spec.rb`

**Step 1: Write tests**

Create `web-ui/backend/spec/services/games/orchestrator_spec.rb`:

```ruby
require "rails_helper"
require "webmock/rspec"

RSpec.describe Games::Orchestrator do
  let(:user) { create(:user) }
  let(:game) { create(:game, game_type: "checkers", state: "in_progress", creator: user) }
  let(:human_player) { create(:game_player, game: game, user: user, seat_position: 0) }
  let(:ai_player) { create(:ai_game_player, game: game, ai_personality: "clara", seat_position: 1) }
  let(:orchestrator) { Games::Orchestrator.new(game) }

  before do
    ENV["CLARA_API_URL"] = "https://test.example.com"
    ENV["GAME_API_KEY"] = "test-key"

    # Initialize game state
    definition = Games::Checkers::Definition.new
    state = definition.new_game
    game.update!(game_data: state)

    # Stub commentary calls
    stub_request(:post, "https://test.example.com/api/v1/game/event")
      .to_return(
        status: 200,
        body: { commentary: "Nice!", mood: "happy" }.to_json,
        headers: { "Content-Type" => "application/json" }
      )
  end

  describe "#human_move" do
    it "validates and applies a legal move" do
      human_player # ensure created
      legal = Games::Checkers::Definition.new.legal_moves(game.game_data.deep_symbolize_keys, "red")
      move = legal.first

      result = orchestrator.human_move(human_player, move)

      expect(result[:game]).to be_present
      game.reload
      expect(game.game_data.deep_symbolize_keys[:board][move[:from][0]][move[:from][1]]).to be_nil
    end

    it "records the move" do
      human_player
      legal = Games::Checkers::Definition.new.legal_moves(game.game_data.deep_symbolize_keys, "red")

      expect {
        orchestrator.human_move(human_player, legal.first)
      }.to change(Move, :count).by(1)
    end

    it "rejects illegal moves" do
      human_player
      illegal_move = { from: [0, 0], to: [7, 7] }

      result = orchestrator.human_move(human_player, illegal_move)
      expect(result[:error]).to be_present
    end
  end

  describe "#ai_move" do
    context "with traditional AI (checkers)" do
      it "picks and applies a move" do
        ai_player
        # Set it to black's turn
        state = game.game_data.deep_symbolize_keys
        state[:current_player] = "black"
        game.update!(game_data: state)

        result = orchestrator.ai_move(ai_player)

        expect(result[:move]).to be_present
        expect(result[:game]).to be_present
      end

      it "records the move with commentary" do
        ai_player
        state = game.game_data.deep_symbolize_keys
        state[:current_player] = "black"
        game.update!(game_data: state)

        expect {
          orchestrator.ai_move(ai_player)
        }.to change(Move, :count).by(1)

        move_record = Move.last
        expect(move_record.game_player).to eq(ai_player)
      end
    end
  end

  describe "#load_state" do
    it "normalizes string/symbol keys correctly" do
      # Simulate JSONB round-trip with symbol keys
      raw_state = { "board" => [[nil]], "current_player" => "red", "captured" => {} }
      game.update!(game_data: raw_state)

      state = orchestrator.send(:load_state)
      expect(state[:board]).to be_a(Array)
      expect(state[:current_player]).to eq("red")
    end
  end
end
```

**Step 2: Run test — expect FAIL**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/orchestrator_spec.rb
```

**Step 3: Implement Orchestrator**

Create `web-ui/backend/app/services/games/orchestrator.rb`:

```ruby
module Games
  class Orchestrator
    attr_reader :game

    def initialize(game)
      @game = game
      @package = Games::Registry.package_for(game.game_type)
      @definition = @package[:definition]
      @ai = @package[:ai]
      @llm_adapter = @package[:llm_adapter]
      @client_adapter = @package[:client_adapter]
      @clara_api = ClaraApi.new
    end

    # Human makes a move
    def human_move(player, move_params)
      state = load_state
      player_id = gp_identifier(player)

      # Validate
      legal = legal_moves_for(state, player)
      matching = find_matching_move(move_params, legal)
      unless matching
        return { error: "Invalid move", legal_moves: legal }
      end

      # Apply
      move = build_move(matching, player)
      new_state = @definition.apply_move(state, move)
      persist_move(player, move_params, new_state)

      # Commentary (async-safe: non-blocking if it fails)
      commentary_response = fire_event("player_move",
        event_data: { move: move_params },
        perspective: gp_identifier(player == game.game_players.first ? game.game_players.last : game.game_players.first)
      )

      # Check end
      check_game_end(new_state)

      game.reload
      {
        game: game,
        commentary: commentary_response&.dig(:commentary),
        mood: commentary_response&.dig(:mood)
      }
    end

    # AI takes a turn
    def ai_move(ai_player)
      state = load_state
      player_id = gp_identifier(ai_player)

      legal = legal_moves_for(state, ai_player)
      return { error: "No legal moves" } if legal.empty?

      if @ai.ai_type == :traditional
        # Ruby AI picks the move
        ai_result = @ai.pick_move(state, player_id_for_engine(ai_player))
        chosen_move = ai_result[:move]
        reasoning = ai_result[:reasoning]
      else
        # LLM picks the move
        move_history = game.moves.order(move_number: :desc).limit(5).reverse.map { |m| m.action }
        llm_response = @clara_api.get_move(
          game_type: game.game_type,
          game_state: state,
          legal_moves: legal,
          personality: ai_player.ai_personality,
          user_id: game.creator&.canonical_user_id || "unknown",
          move_history: move_history
        )
        chosen_move = parse_llm_move(llm_response[:move], legal)
        reasoning = llm_response[:commentary]
      end

      # Apply
      move = build_move(chosen_move, ai_player)
      new_state = @definition.apply_move(state, move)

      # Position evaluation for commentary
      position_eval = @ai.evaluate_position(new_state, player_id_for_engine(ai_player))

      persist_move(ai_player, chosen_move, new_state, commentary: reasoning)

      # Commentary event (high tier)
      commentary_response = fire_event("clara_move",
        event_data: {
          move: chosen_move,
          reasoning: reasoning,
          position_eval: position_eval
        },
        perspective: player_id_for_engine(ai_player)
      )

      # Check end
      check_game_end(new_state)

      game.reload
      {
        game: game,
        move: chosen_move,
        commentary: commentary_response&.dig(:commentary) || reasoning,
        mood: commentary_response&.dig(:mood) || "idle"
      }
    end

    # Player sends a chat message
    def player_chat(player, message)
      state = load_state
      ai_perspective = game.game_players.find_by(ai_personality: [nil, false].exclude?(ai_personality))
                       &.then { |gp| player_id_for_engine(gp) }

      fire_event("player_chat",
        event_data: { message: message },
        perspective: ai_perspective
      )
    end

    private

    def load_state
      state = game.game_data.deep_symbolize_keys

      # Normalize player ID keys to strings (JSONB round-trip fix)
      if state[:hands].is_a?(Hash)
        state[:hands] = state[:hands].transform_keys(&:to_s)
      end
      if state[:stood].is_a?(Array)
        state[:stood] = state[:stood].map(&:to_s)
      end

      state
    end

    def gp_identifier(game_player)
      game_player.ai_personality || "player-#{game_player.user_id}"
    end

    def player_id_for_engine(game_player)
      if game.game_type == "checkers"
        game_player.seat_position == 0 ? "red" : "black"
      else
        gp_identifier(game_player)
      end
    end

    def legal_moves_for(state, game_player)
      @definition.legal_moves(state, player_id_for_engine(game_player))
    end

    def find_matching_move(move_params, legal)
      if move_params.is_a?(Hash) && move_params[:from] && move_params[:to]
        legal.find { |m| m[:from] == move_params[:from] && m[:to] == move_params[:to] }
      elsif move_params.is_a?(String)
        legal.include?(move_params) ? move_params : nil
      else
        legal.include?(move_params) ? move_params : nil
      end
    end

    def build_move(chosen, game_player)
      if game.game_type == "blackjack"
        action = chosen.is_a?(String) ? chosen : (chosen[:action] || chosen[:type])
        { player: gp_identifier(game_player), action: action }
      else
        chosen
      end
    end

    def parse_llm_move(llm_move, legal)
      if llm_move.is_a?(Hash)
        move_data = llm_move.deep_symbolize_keys
        if move_data[:from] && move_data[:to]
          match = legal.find { |m| m[:from] == move_data[:from] && m[:to] == move_data[:to] }
          return match if match
        end
        return move_data[:type] if move_data[:type] && legal.include?(move_data[:type])
      elsif llm_move.is_a?(String) && legal.include?(llm_move)
        return llm_move
      end

      # Fallback: random legal move
      legal.sample
    end

    def persist_move(game_player, move_data, new_state, commentary: nil)
      game.increment!(:move_count)
      game.update!(game_data: new_state)

      action = move_data.is_a?(Hash) ? move_data : { type: move_data }

      game.moves.create!(
        game_player: game_player,
        move_number: game.move_count,
        action: action,
        game_data_snapshot: new_state,
        clara_commentary: commentary
      )
    end

    def fire_event(event_type, event_data: {}, perspective: nil)
      state = load_state
      player_id = perspective || player_id_for_engine(
        game.game_players.find_by("ai_personality IS NOT NULL") || game.game_players.first
      )

      @clara_api.game_event(
        event_type: event_type,
        game_type: game.game_type,
        state_summary: @llm_adapter.state_summary(state, perspective: player_id),
        user_id: game.creator&.canonical_user_id || "unknown",
        event_data: event_data,
        position_eval: @ai.evaluate_position(state, player_id),
        recent_history: @llm_adapter.relevant_history(
          game.moves.order(move_number: :desc).limit(5).reverse.map { |m| m.action },
          state: state
        )
      )
    rescue StandardError => e
      Rails.logger.error("Orchestrator fire_event error: #{e.class} - #{e.message}")
      { commentary: nil, mood: "neutral" }
    end

    def check_game_end(state)
      result = @definition.winner(state)
      return unless result&.over?

      game.update!(state: "resolved", finished_at: Time.current)

      if game.game_type == "checkers"
        game.game_players.each do |gp|
          color = gp.seat_position == 0 ? "red" : "black"
          player_result = result.winners&.include?(color) ? "win" : "loss"
          gp.update!(result: player_result)
        end
      elsif game.game_type == "blackjack"
        resolve_results = @definition.resolve(state)
        game.game_players.each do |gp|
          pid = gp_identifier(gp)
          gp.update!(result: resolve_results[pid]) if resolve_results[pid]
        end
      end

      fire_event("game_over",
        event_data: { result: { winners: result.winners, losers: result.losers } }
      )
    end
  end
end
```

**Step 4: Run test — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec spec/services/games/orchestrator_spec.rb
```

**Step 5: Commit**

```bash
cd web-ui/backend
git add app/services/games/orchestrator.rb spec/services/games/orchestrator_spec.rb
git commit -m "feat: add Games::Orchestrator for turn coordination and event firing"
```

---

## Task 12: Wire Controller to Orchestrator

**Files:**
- Modify: `web-ui/backend/app/controllers/api/v1/games_controller.rb`
- Modify: `web-ui/backend/spec/controllers/games_controller_spec.rb`

**Step 1: Run existing controller tests to establish baseline**

```bash
cd web-ui/backend && bundle exec rspec spec/controllers/games_controller_spec.rb
```

Note: Record which tests pass. The controller rewrite must not break them.

**Step 2: Rewrite controller actions to delegate to Orchestrator**

The `move` and `ai_move` actions delegate to the Orchestrator. The `create` action delegates to Orchestrator for game initialization. Keep `game_props`, `broadcast_game_update`, and `set_game` as-is — they are controller concerns (serialization, broadcasting, routing).

Key changes in `web-ui/backend/app/controllers/api/v1/games_controller.rb`:

- `move` action: Replace manual engine calls with `orchestrator.human_move(player, move_params)`
- `ai_move` action: Replace ClaraApi + engine calls with `orchestrator.ai_move(ai_player)`
- Remove: `load_game_state` (moved to Orchestrator), `game_engine` (replaced by Registry)
- Remove: `check_game_end` (moved to Orchestrator)
- Keep: `game_props` (serialization concern), `broadcast_game_update`, `set_game`, `gp_identifier`

The `create` action stays mostly the same since it does game-specific initialization (deal for blackjack). This could move to Orchestrator later, but for now keep it in the controller to minimize blast radius.

**Important:** The new `create` action must use the new Definition classes instead of the old engine classes. Replace `game_engine(game.game_type)` calls with `Games::Registry.package_for(game.game_type)[:definition]`.

**Step 3: Run controller tests — expect PASS (same behavior)**

```bash
cd web-ui/backend && bundle exec rspec spec/controllers/games_controller_spec.rb
```

**Step 4: Commit**

```bash
cd web-ui/backend
git add app/controllers/api/v1/games_controller.rb
git commit -m "refactor: wire GamesController to Orchestrator"
```

---

## Task 13: Python Event Endpoint

**Files:**
- Modify: `mypalclara/adapters/game/engine.py`
- Modify: `mypalclara/adapters/game/api.py`
- Create: `tests/adapters/test_game_event.py`

**Step 1: Write Python tests**

Create `tests/adapters/test_game_event.py`:

```python
"""Tests for the game event endpoint."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mypalclara.adapters.game.engine import (
    GameEventRequest,
    GameEventResponse,
    get_clara_commentary,
)


class TestGameEventRequest:
    def test_valid_request(self):
        req = GameEventRequest(
            event_type="clara_move",
            game_type="checkers",
            state_summary="You're playing Red. 12 pieces each.",
            user_id="user-1",
        )
        assert req.event_type == "clara_move"
        assert req.position_eval == 0.0
        assert req.recent_history == []

    def test_all_fields(self):
        req = GameEventRequest(
            event_type="player_chat",
            game_type="blackjack",
            state_summary="Your hand: K, 7 (17).",
            event_data={"message": "nice move!"},
            position_eval=-0.3,
            user_id="user-1",
            recent_history=[{"action": "hit"}],
        )
        assert req.event_data == {"message": "nice move!"}
        assert req.position_eval == -0.3


class TestGetClaraCommentary:
    @pytest.mark.asyncio
    async def test_returns_commentary_and_mood(self):
        mock_llm = MagicMock(return_value='{"commentary": "Nice move!", "mood": "happy"}')

        with patch("mypalclara.adapters.game.engine.make_llm", return_value=mock_llm):
            request = GameEventRequest(
                event_type="clara_move",
                game_type="checkers",
                state_summary="You're winning.",
                user_id="user-1",
                position_eval=0.5,
            )
            result = await get_clara_commentary(request, "Test personality text")

            assert result["commentary"] == "Nice move!"
            assert result["mood"] == "happy"

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        mock_llm = MagicMock(side_effect=Exception("LLM failed"))

        with patch("mypalclara.adapters.game.engine.make_llm", return_value=mock_llm):
            request = GameEventRequest(
                event_type="clara_move",
                game_type="checkers",
                state_summary="test",
                user_id="user-1",
            )
            result = await get_clara_commentary(request, "Personality")

            assert result["mood"] in ("neutral", "idle")
```

**Step 2: Run test — expect FAIL**

```bash
poetry run pytest tests/adapters/test_game_event.py -v
```

**Step 3: Add GameEventRequest and get_clara_commentary to engine.py**

Add to `mypalclara/adapters/game/engine.py` (after existing classes):

```python
class GameEventRequest(BaseModel):
    event_type: str  # game_start, player_move, clara_move, player_chat, game_over
    game_type: str
    state_summary: str
    event_data: dict[str, Any] = {}
    position_eval: float = 0.0
    user_id: str
    recent_history: list[dict[str, Any]] = []


class GameEventResponse(BaseModel):
    commentary: str | None
    mood: str


async def get_clara_commentary(
    request: GameEventRequest,
    personality_text: str,
) -> dict[str, Any]:
    """Generate Clara's commentary for a game event using high-tier LLM."""
    from mypalclara.core.llm import make_llm

    tier = os.getenv("GAME_EVENT_LLM_TIER", "high")
    llm = make_llm(tier=tier)

    # Fetch user memories for richer commentary
    memory_context = ""
    if os.getenv("GAME_EVENT_MEMORIES", "true").lower() in ("true", "1", "yes"):
        try:
            from mypalclara.core.memory import ROOK

            if ROOK:
                results = ROOK.search(
                    f"playing {request.game_type} with user",
                    user_id=request.user_id,
                    agent_id="mypalclara",
                    limit=5,
                )
                memories = [r.get("memory", "") for r in (results or []) if r.get("memory")]
                if memories:
                    memory_context = "\n\nWhat you know about this player:\n" + "\n".join(
                        f"- {m}" for m in memories
                    )
        except Exception:
            logger.debug("Could not fetch user memories for game event", exc_info=True)

    # Build emotional context from position evaluation
    eval_desc = ""
    if request.position_eval > 0.5:
        eval_desc = "You're winning comfortably."
    elif request.position_eval > 0.1:
        eval_desc = "You're slightly ahead."
    elif request.position_eval > -0.1:
        eval_desc = "The game is close."
    elif request.position_eval > -0.5:
        eval_desc = "You're slightly behind."
    else:
        eval_desc = "You're losing."

    history_text = ""
    if request.recent_history:
        history_text = "\n\nRecent moves:\n" + "\n".join(
            f"- {m}" for m in request.recent_history[-5:]
        )

    event_desc = {
        "game_start": "A new game is starting.",
        "player_move": f"The player just made a move: {json.dumps(request.event_data)}",
        "clara_move": f"You just made a move: {json.dumps(request.event_data)}",
        "player_chat": f"The player says: \"{request.event_data.get('message', '')}\"",
        "game_over": f"The game is over. Result: {json.dumps(request.event_data)}",
    }.get(request.event_type, f"Game event: {request.event_type}")

    prompt = f"""{personality_text}
{memory_context}

You are playing {request.game_type}.
{request.state_summary}
{eval_desc}
{history_text}

{event_desc}

React in character. Be natural — trash talk, encouragement, \
nervousness, gloating, whatever fits your personality and the situation.

Respond with ONLY valid JSON (no markdown fences):
{{"commentary": "<your in-character reaction>", "mood": "<one of: idle, happy, nervous, smug, surprised, defeated>"}}"""

    try:
        messages = [{"role": "user", "content": prompt}]
        content = await asyncio.to_thread(llm, messages)

        content = re.sub(r"^```(?:json)?\s*\n?", "", content.strip())
        content = re.sub(r"\n?```\s*$", "", content.strip())

        result = json.loads(content)

        if result.get("mood") not in VALID_MOODS:
            result["mood"] = "idle"

        return result

    except Exception:
        logger.exception("Failed to get LLM game commentary")
        return {"commentary": None, "mood": "neutral"}
```

**Step 4: Add /event route to api.py**

Add to `mypalclara/adapters/game/api.py`:

```python
from mypalclara.adapters.game.engine import (
    GameEventRequest,
    GameEventResponse,
    GameMoveRequest,
    GameMoveResponse,
    _load_personality_text,
    _verify_api_key,
    get_clara_commentary,
    get_clara_move,
)


@router.post("/event", response_model=GameEventResponse)
async def game_event(
    request: GameEventRequest,
    x_game_api_key: str | None = Header(None),
) -> GameEventResponse:
    """Get Clara's commentary on a game event."""
    _verify_api_key(x_game_api_key)
    personality_text = _load_personality_text("clara")  # Always use Clara's personality for events
    result = await get_clara_commentary(request, personality_text)
    return GameEventResponse(**result)
```

**Step 5: Run test — expect PASS**

```bash
poetry run pytest tests/adapters/test_game_event.py -v
```

**Step 6: Commit**

```bash
git add mypalclara/adapters/game/engine.py mypalclara/adapters/game/api.py \
  tests/adapters/test_game_event.py
git commit -m "feat: add /api/v1/game/event endpoint for Clara commentary"
```

---

## Task 14: Delete Old Engine Files

**Files:**
- Delete: `web-ui/backend/app/services/games/game_engine.rb`
- Delete: `web-ui/backend/app/services/games/checkers_engine.rb`
- Delete: `web-ui/backend/app/services/games/blackjack_engine.rb`
- Update: `web-ui/backend/spec/services/games/checkers_engine_spec.rb` → delete
- Update: `web-ui/backend/spec/services/games/blackjack_engine_spec.rb` → delete

**Step 1: Verify no remaining references to old classes**

Search for `CheckersEngine`, `BlackjackEngine`, `GameEngine` in the codebase. Any remaining references must be updated to use the new classes before deleting.

```bash
cd web-ui/backend && grep -rn "CheckersEngine\|BlackjackEngine\|GameEngine" app/ --include="*.rb"
```

Fix any remaining references (likely in the controller if Task 12 is complete, there should be none).

**Step 2: Run full test suite to confirm nothing depends on old files**

```bash
cd web-ui/backend && bundle exec rspec
```

**Step 3: Delete old files**

```bash
cd web-ui/backend
rm app/services/games/game_engine.rb
rm app/services/games/checkers_engine.rb
rm app/services/games/blackjack_engine.rb
rm spec/services/games/checkers_engine_spec.rb
rm spec/services/games/blackjack_engine_spec.rb
```

**Step 4: Run full test suite — expect PASS**

```bash
cd web-ui/backend && bundle exec rspec
```

**Step 5: Commit**

```bash
cd web-ui/backend
git add -A app/services/games/ spec/services/games/
git commit -m "chore: remove old GameEngine, CheckersEngine, BlackjackEngine"
```

---

## Task 15: Full Integration Test

**Step 1: Run all Ruby tests**

```bash
cd web-ui/backend && bundle exec rspec
```

All tests must pass.

**Step 2: Run all Python tests**

```bash
poetry run pytest tests/ -v
```

All tests must pass.

**Step 3: Lint**

```bash
cd web-ui/backend && bundle exec rubocop app/services/games/ --autocorrect 2>/dev/null; true
poetry run ruff check mypalclara/adapters/game/ && poetry run ruff format mypalclara/adapters/game/
```

**Step 4: Final commit if lint changes**

```bash
git add -A && git commit -m "style: lint fixes for game engine redesign" --allow-empty
```

---

## Summary of Files

### New Ruby files (13)
```
app/services/games/game_result.rb
app/services/games/game_definition.rb
app/services/games/game_ai.rb
app/services/games/llm_adapter.rb
app/services/games/client_adapter.rb
app/services/games/registry.rb
app/services/games/orchestrator.rb
app/services/games/checkers/definition.rb
app/services/games/checkers/ai.rb
app/services/games/checkers/llm_adapter.rb
app/services/games/checkers/client_adapter.rb
app/services/games/blackjack/definition.rb
app/services/games/blackjack/ai.rb
app/services/games/blackjack/llm_adapter.rb
app/services/games/blackjack/client_adapter.rb
```

### New test files (12)
```
spec/services/games/game_result_spec.rb
spec/services/games/game_definition_spec.rb
spec/services/games/game_ai_spec.rb
spec/services/games/registry_spec.rb
spec/services/games/orchestrator_spec.rb
spec/services/clara_api_spec.rb
spec/services/games/checkers/definition_spec.rb
spec/services/games/checkers/ai_spec.rb
spec/services/games/checkers/llm_adapter_spec.rb
spec/services/games/checkers/client_adapter_spec.rb
spec/services/games/blackjack/definition_spec.rb
spec/services/games/blackjack/ai_spec.rb
spec/services/games/blackjack/llm_adapter_spec.rb
spec/services/games/blackjack/client_adapter_spec.rb
tests/adapters/test_game_event.py
```

### Modified files (3)
```
app/services/clara_api.rb
app/controllers/api/v1/games_controller.rb
mypalclara/adapters/game/engine.py
mypalclara/adapters/game/api.py
```

### Deleted files (5)
```
app/services/games/game_engine.rb
app/services/games/checkers_engine.rb
app/services/games/blackjack_engine.rb
spec/services/games/checkers_engine_spec.rb
spec/services/games/blackjack_engine_spec.rb
```
