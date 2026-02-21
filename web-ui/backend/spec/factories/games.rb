FactoryBot.define do
  factory :game do
    association :creator, factory: :user
    game_type { "blackjack" }
    state { "waiting" }
    game_data { {} }
    move_count { 0 }
  end
end
