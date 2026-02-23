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
