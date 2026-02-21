FactoryBot.define do
  factory :user do
    sequence(:canonical_user_id) { |n| "user-#{n}" }
    display_name { "Test User" }
    avatar_url { nil }
  end
end
