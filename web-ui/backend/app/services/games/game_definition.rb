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
