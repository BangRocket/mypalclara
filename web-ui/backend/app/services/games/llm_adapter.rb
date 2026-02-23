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
