FactoryBot.define do
  factory :move do
    association :game
    association :game_player
    sequence(:move_number) { |n| n }
    action { { type: "hit" } }
    game_data_snapshot { {} }
    clara_commentary { nil }
  end
end
