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
