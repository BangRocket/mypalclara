class Game < ApplicationRecord
  GAME_TYPES = %w[blackjack checkers].freeze
  STATES = %w[waiting in_progress resolved].freeze

  belongs_to :creator, class_name: "User", foreign_key: :created_by_id
  has_many :game_players, dependent: :destroy
  has_many :moves, dependent: :destroy

  validates :game_type, presence: true, inclusion: { in: GAME_TYPES }
  validates :state, presence: true, inclusion: { in: STATES }
end
