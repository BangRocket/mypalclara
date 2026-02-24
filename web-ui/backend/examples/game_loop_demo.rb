  #!/usr/bin/env ruby
  # Example demonstrating the game engine's turn tracking and game loop capabilities

  require_relative '../config/environment'
  require_relative '../app/services/games/game_engine'
  require_relative '../app/services/games/checkers_engine'
  require_relative '../app/services/games/blackjack_engine'

def demonstrate_checkers_turns
  puts "=== Checkers Game Turn Demonstration ===\n"
  
  game = Games::CheckersEngine.new
  state = game.new_game
  
  puts "Initial state:"
  puts "  Current player: #{game.current_player(state)}"
  puts "  Turn count: #{game.turn_count(state)}"
  puts "  Game over?: #{game.game_over?(state)}"
  puts
  
  # Simulate a few moves
  moves = game.legal_moves(state, "red")
  if moves.any?
    puts "Available moves for red: #{moves.first(2).map { |m| "#{m[:from]} -> #{m[:to]}" }.join(', ')}"
    
    # Make a move
    state = game.apply_move(state, moves.first)
    puts "\nAfter red moves:"
    puts "  Current player: #{game.current_player(state)}"
    puts "  Turn count: #{game.turn_count(state)}"
    puts "  Game over?: #{game.game_over?(state)}"
    puts
    
    # Get black's moves
    moves = game.legal_moves(state, "black")
    if moves.any?
      puts "Available moves for black: #{moves.first(2).map { |m| "#{m[:from]} -> #{m[:to]}" }.join(', ')}"
      
      state = game.apply_move(state, moves.first)
      puts "\nAfter black moves:"
      puts "  Current player: #{game.current_player(state)}"
      puts "  Turn count: #{game.turn_count(state)}"
      puts "  Game over?: #{game.game_over?(state)}"
      puts
    end
  end
  
  # Demonstrate advance_turn method
  puts "Using advance_turn method:"
  state = game.advance_turn(state)
  puts "  Current player: #{game.current_player(state)}"
  puts "  Turn count: #{game.turn_count(state)}"
  
  # Check if it's red's turn
  puts "  Is it red's turn?: #{game.player_turn?(state, 'red')}"
  puts
end

def demonstrate_blackjack_turns
  puts "=== Blackjack Game Turn Demonstration ===\n"
  
  game = Games::BlackjackEngine.new
  state = game.new_game
  
  puts "Initial state:"
  puts "  Current player: #{game.current_player(state)}"
  puts "  Turn count: #{game.turn_count(state)}"
  puts "  Phase: #{state[:phase]}"
  puts
  
  # Deal cards to players
  state = game.deal(state, ["player1", "player2"])
  puts "After dealing:"
  puts "  Current player: #{game.current_player(state)}"
  puts "  Turn count: #{game.turn_count(state)}"
  puts "  Phase: #{state[:phase]}"
  puts "  Players: #{game.players(state).inspect}"
  puts
  
  # Show legal moves for current player
  current = game.current_player(state)
  moves = game.legal_moves(state, current)
  puts "Legal moves for #{current}: #{moves.inspect}"
  puts
  
  # Make a move
  if moves.any?
    state = game.apply_move(state, current, "hit")
    puts "After #{current} hits:"
    puts "  Current player: #{game.current_player(state)}"
    puts "  Turn count: #{game.turn_count(state)}"
    puts "  Hand: #{state[:hands][current]}"
    puts
  end
  
  # Demonstrate advance_turn
  puts "Using advance_turn method:"
  state = game.advance_turn(state)
  puts "  Current player: #{game.current_player(state)}"
  puts "  Turn count: #{game.turn_count(state)}"
  puts "  Is it player1's turn?: #{game.player_turn?(state, 'player1')}"
  puts
end

def demonstrate_base_class_methods
  puts "=== Base GameEngine Methods ===\n"
  
  game = Games::CheckersEngine.new
  state = game.new_game
  
  puts "Available base class methods:"
  puts "  - new_game: #{game.respond_to?(:new_game)}"
  puts "  - legal_moves: #{game.respond_to?(:legal_moves)}"
  puts "  - apply_move: #{game.respond_to?(:apply_move)}"
  puts "  - game_over?: #{game.respond_to?(:game_over?)}"
  puts "  - winner: #{game.respond_to?(:winner)}"
  puts "  - current_player: #{game.respond_to?(:current_player)}"
  puts "  - valid_move?: #{game.respond_to?(:valid_move?)}"
  puts "  - players: #{game.respond_to?(:players)}"
  puts "  - advance_turn: #{game.respond_to?(:advance_turn)}"
  puts "  - turn_count: #{game.respond_to?(:turn_count)}"
  puts "  - player_turn?: #{game.respond_to?(:player_turn?)}"
  puts
end

# Run demonstrations
demonstrate_base_class_methods
demonstrate_checkers_turns
demonstrate_blackjack_turns

puts "=== All demonstrations complete! ==="