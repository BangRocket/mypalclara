# Game Engine Redesign — Design Document

Date: 2026-02-22
Status: Approved

## Goal

Restructure the game engine from a monolithic "send everything to the LLM" model into a layered architecture with traditional game AI, an orchestrator, and event-based Clara commentary. Reduce AI move latency, improve reliability (games work without Clara's LLM), and establish a game-package pattern for adding new games.

## Architecture Overview

Four layers, each with a single responsibility:

```
┌──────────────────────────────────────────────────────────┐
│  Games::Orchestrator                                      │
│  Manages instances, coordinates turns, fires events       │
│  Delegates to all layers below                            │
├──────────────────────────────────────────────────────────┤
│  Games::<Game>::AI          │  ClaraApi (event-based)     │
│  Traditional AI per game    │  Commentary, reactions,      │
│  Ruby minimax/strategy/etc  │  chat, game events          │
│  OR LLM-delegating          │  Calls Python endpoint      │
├─────────────────────────────┴─────────────────────────────┤
│  Games::<Game>::Definition                                │
│  Pure rules. No I/O, no AI, no LLM.                      │
│  State in, state out.                                     │
├──────────────────────────────────────────────────────────┤
│  Games::<Game>::LLMAdapter  │  Games::<Game>::ClientAdapter│
│  Formats state/moves/       │  Formats state/moves for     │
│  history for Clara          │  React frontend              │
└──────────────────────────────────────────────────────────┘
```

## Design Decisions

### AI Strategy Per Game

Each game declares its AI type:

- **`:traditional`** — Ruby AI picks moves locally (minimax, heuristic, strategy table). Fast, deterministic, no hallucination. Clara provides commentary only.
- **`:llm`** — LLM picks moves via Python endpoint (mid/low tier). Personality-driven play. Better for games where "interesting" beats "optimal" (card games, social games).

Current assignments:
- Checkers: `:traditional` (minimax — LLM is terrible at board evaluation)
- Blackjack: `:llm` (personality-driven play is more fun than basic strategy)

### LLM Tier Split

- **Move selection (LLM games):** mid/low tier, game-specific prompt, no memories. Fast.
- **Commentary/events (all games):** high tier, full Clara personality, memory-enabled. Rich.

This means Clara's commentary quality is independent of move selection speed.

### Event-Based Commentary

ClaraApi evolves from a single `get_move` method to a generic `game_event` method. Event types:

| Event | When | What Clara Gets |
|---|---|---|
| `game_start` | New game created | Game type, players, initial state |
| `player_move` | Human makes a move | What they did, position evaluation |
| `clara_move` | AI makes a move | What she did, her reasoning, position eval |
| `player_chat` | Player sends chat message | Their message + game context |
| `game_over` | Game ends | Final result, who won/lost |

The `position_eval` (-1.0 to 1.0) from GameAI grounds Clara's emotional response. She knows if she's winning or losing without the LLM having to figure it out.

### Move Format Standardization

`apply_move(state, move)` — player info goes inside the move hash when needed:

- Checkers: `{ from: [r,c], to: [r,c], captures: [...] }`
- Blackjack: `{ player: "clara", action: "hit" }`

State already tracks whose turn it is. No separate `player_id` argument.

### Result Standardization

All games return `GameResult` from `winner()`:

```ruby
Games::GameResult = Struct.new(:status, :winners, :losers, :draws, keyword_init: true)
```

Covers both single-winner (Checkers) and multi-outcome (Blackjack) games.

## Base Interfaces

### GameDefinition (replaces GameEngine)

Pure rules. No side effects, no I/O, no AI decisions.

```ruby
module Games
  class GameDefinition
    def game_type                       # → String
    def new_game(**options)             # → state hash
    def legal_moves(state, player)      # → [Move]
    def apply_move(state, move)         # → new state hash
    def game_over?(state)               # → Boolean
    def winner(state)                   # → GameResult
    def current_player(state)           # → player_id string
    def players(state)                  # → [player_id strings]
    def phase(state)                    # → Symbol (optional)
  end
end
```

### GameAI

Traditional AI or LLM-delegating. Per-game.

```ruby
module Games
  class GameAI
    def initialize(definition)
    def ai_type                                        # → :traditional or :llm
    def pick_move(state, player, difficulty: :medium)   # → { move:, reasoning: }
    def evaluate_position(state, player)                # → Float -1.0..1.0
    def explain_move(state, move)                       # → String
  end
end
```

### LLMAdapter

Formats game state for Clara's context window.

```ruby
module Games
  class LLMAdapter
    def initialize(definition)
    def state_summary(state, perspective:)              # → String
    def describe_moves(moves, state:)                   # → [{ id:, description: }]
    def relevant_history(history, state:, limit: 5)     # → [Hash]
  end
end
```

### ClientAdapter

Formats state for React frontend.

```ruby
module Games
  class ClientAdapter
    def initialize(definition)
    def state_for_client(state, perspective:)           # → Hash
    def available_actions(state, player)                 # → [Hash]
  end
end
```

## Orchestrator

Instantiated per-request with the game. Coordinates the full turn cycle.

```ruby
module Games
  class Orchestrator
    def initialize(game)
      @game = game
      @package = Games.package_for(game.game_type)
      @clara_api = ClaraApi.new
    end

    def human_move(player, move_params)
      # Validate → apply → persist → fire player_move event → check end
    end

    def ai_move(ai_player)
      # Get legal moves → branch on ai_type → apply → persist
      # → fire clara_move event for commentary → check end
    end

    def player_chat(player, message)
      # Fire player_chat event → return Clara's response
    end

    def start_game(players:, ai_players:)
      # Initialize → deal if needed → persist → fire game_start event
    end

    private

    def fire_event(event_type, event_data: {}, perspective: nil)
      # Build payload using llm_adapter
      # Call ClaraApi.game_event (high tier, memory-enabled)
    end
  end
end
```

State normalization (the fragile string/symbol key conversion) moves into the Orchestrator, done once and consistently.

## Per-Game Packages

### Checkers

- **Definition:** Extracted from `checkers_engine.rb`. Nearly identical rules logic. `winner` returns `GameResult`.
- **AI:** `ai_type: :traditional`. Minimax with alpha-beta pruning.
  - Easy: depth 2, random tiebreaking
  - Medium: depth 4, heuristic eval (piece count, kings, center)
  - Hard: depth 6-8, full evaluation
- **LLMAdapter:** Board state to English ("You're playing Black, 8 pieces including 2 kings..."). Coordinates to human notation.
- **ClientAdapter:** Board array, piece counts, legal moves with coordinates.

### Blackjack

- **Definition:** Extracted from `blackjack_engine.rb`. Phase symbols (`:dealing`, `:player_turns`). Move format: `{ player: "clara", action: "hit" }`. Game-specific methods (`deal`, `dealer_play`, `resolve`) stay.
- **AI:** `ai_type: :llm`. Move selection via Python endpoint (mid/low tier). Still provides `evaluate_position` (hand value vs dealer showing card) and `explain_move` for commentary grounding.
- **LLMAdapter:** Hand/card state to English ("Your hand: K♥ 7♠ (17). Dealer shows: 10♦.").
- **ClientAdapter:** Card data, hand values, player status, phase.

## ClaraApi Changes

```ruby
class ClaraApi
  TIMEOUT = 10

  # Existing: LLM move selection (mid/low tier, LLM games only)
  def get_move(game_type:, game_state:, legal_moves:, personality:,
               user_id:, move_history: [])
    post("/api/v1/game/move", { ... })
  end

  # New: Event-based commentary (high tier, all games)
  def game_event(event_type:, game_type:, state_summary:, user_id:,
                 event_data: {}, position_eval: 0.0, recent_history: [])
    post("/api/v1/game/event", { ... })
  end

  private

  def post(path, body)
    # Net::HTTP.new with explicit open/read timeout
  end

  def fallback
    { commentary: nil, mood: "neutral" }
  end
end
```

## Python Endpoint Changes

### Existing: `/api/v1/game/move`

Minor changes:
- Configurable tier via `GAME_MOVE_LLM_TIER` env (default `"mid"`)
- Memory search stays off by default

### New: `/api/v1/game/event`

```python
class GameEventRequest(BaseModel):
    event_type: str        # game_start, player_move, clara_move, player_chat, game_over
    game_type: str
    state_summary: str     # Pre-formatted English from Ruby LLMAdapter
    event_data: dict = {}
    position_eval: float = 0.0
    user_id: str
    recent_history: list[dict] = []

class GameEventResponse(BaseModel):
    commentary: str | None
    mood: str
```

- Uses high tier LLM
- Full personality text from personality files
- Memory-enabled (Rook search for user context)
- Prompt: personality + state_summary + event context + position_eval

## File Layout

### New Files

```
web-ui/backend/app/services/games/
  game_definition.rb
  game_ai.rb
  game_result.rb
  llm_adapter.rb
  client_adapter.rb
  orchestrator.rb
  registry.rb

  checkers/
    definition.rb
    ai.rb
    llm_adapter.rb
    client_adapter.rb

  blackjack/
    definition.rb
    ai.rb
    llm_adapter.rb
    client_adapter.rb
```

### Modified Files

- `web-ui/backend/app/services/clara_api.rb` — Add `game_event`, keep `get_move`
- `web-ui/backend/app/controllers/api/v1/games_controller.rb` — Delegate to Orchestrator
- `mypalclara/adapters/game/engine.py` — Add `GameEventRequest` + handler
- `mypalclara/adapters/game/api.py` — Add `/event` route

### Deleted Files (after migration)

- `web-ui/backend/app/services/games/game_engine.rb`
- `web-ui/backend/app/services/games/checkers_engine.rb`
- `web-ui/backend/app/services/games/blackjack_engine.rb`

## What Does NOT Change

- **Database schema:** Game, GamePlayer, Move models stay as-is. JSONB state storage unchanged.
- **Frontend:** API response shape stays `{ game:, commentary:, mood: }`. Frontend doesn't know about the restructuring. New commentary events are additive.
- **Other services:** GatewayProxy, GatewayWsClient, IdentityProxy, JwtService — untouched.
- **Auth flow:** JWT authentication unchanged.
- **ActionCable:** Game channel broadcasts unchanged.

## Environment Variables

```
GAME_MOVE_LLM_TIER=mid          # Tier for move selection (LLM games)
GAME_EVENT_LLM_TIER=high        # Tier for commentary/reactions
GAME_EVENT_MEMORIES=true         # Commentary uses Rook memories
GAME_MEMORIES_ENABLED=false      # Legacy: move endpoint memories (keep off)
```

## Expected Outcomes

- **Checkers AI moves:** ~0ms (local minimax) + commentary latency (async, non-blocking)
- **Blackjack AI moves:** ~2-4s (mid-tier LLM, no memory search) + commentary (can be async)
- **Reliability:** Games work even if Clara's Python backend is down (traditional AI games continue without commentary)
- **New game addition:** Implement 4 files (definition, ai, llm_adapter, client_adapter), register in registry
