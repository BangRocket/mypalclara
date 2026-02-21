class GamePlayer < ApplicationRecord
  VALID_AI_PERSONALITIES = %w[clara flo clarissa].freeze
  PLAYER_STATES = %w[active stood busted disconnected].freeze
  RESULTS = %w[won lost draw].freeze

  belongs_to :game
  belongs_to :user, optional: true
  has_many :moves, dependent: :destroy

  validates :seat_position, presence: true
  validates :player_state, presence: true, inclusion: { in: PLAYER_STATES }
  validates :ai_personality, inclusion: { in: VALID_AI_PERSONALITIES }, allow_nil: true
  validates :result, inclusion: { in: RESULTS }, allow_nil: true
  validate :must_have_user_or_ai

  private

  def must_have_user_or_ai
    if user.blank? && ai_personality.blank?
      errors.add(:base, "Must have either a user or an AI personality")
    end
  end
end
