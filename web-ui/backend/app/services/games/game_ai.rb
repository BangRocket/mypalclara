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
