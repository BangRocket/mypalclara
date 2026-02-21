class LobbyController < ApplicationController
  def index
    games = current_user.games.order(created_at: :desc).limit(10)
    stats = {
      blackjack: game_stats("blackjack"),
      checkers: game_stats("checkers"),
    }
    render inertia: "Lobby", props: {
      user: { name: current_user.display_name, avatar: current_user.avatar_url },
      recent_games: games.map { |g| game_summary(g) },
      stats: stats,
    }
  end

  private

  def game_stats(game_type)
    player_games = current_user.game_players.joins(:game).where(games: { game_type: game_type })
    {
      played: player_games.count,
      won: player_games.where(result: "won").count,
    }
  end

  def game_summary(game)
    {
      id: game.id,
      game_type: game.game_type,
      state: game.state,
      created_at: game.created_at.iso8601,
      players: game.game_players.map { |gp| gp.ai_personality || gp.user&.display_name || "Unknown" },
    }
  end
end
