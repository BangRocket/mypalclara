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
