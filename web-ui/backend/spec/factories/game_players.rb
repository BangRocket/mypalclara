FactoryBot.define do
  factory :game_player do
    association :game
    association :user
    ai_personality { nil }
    seat_position { 0 }
    player_state { "active" }
    hand_data { {} }
  end

  factory :ai_game_player, parent: :game_player do
    user { nil }
    ai_personality { "clara" }
  end
end
