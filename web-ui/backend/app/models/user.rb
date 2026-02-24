class User < ApplicationRecord
  validates :canonical_user_id, presence: true, uniqueness: true
  validates :display_name, presence: true

  has_many :games, foreign_key: :created_by_id
  has_many :game_players
  has_many :file_system_entries, dependent: :destroy
end
