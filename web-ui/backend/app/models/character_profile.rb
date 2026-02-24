class CharacterProfile < ApplicationRecord
  LAYER_NAMES = %w[base_layer hair_layer eyes_layer eyebrows_layer mouth_layer clothes_layer bg_layer].freeze
  VALID_PERSONALITIES = (%w[dealer] + GamePlayer::VALID_AI_PERSONALITIES).freeze

  validates :personality, presence: true, uniqueness: true,
            inclusion: { in: VALID_PERSONALITIES }
  validates :display_name, presence: true
  validates :base_layer, presence: true
  validate :validate_layer_keys

  private

  def validate_layer_keys
    LAYER_NAMES.each do |layer_name|
      layer = send(layer_name)
      next if layer.blank?

      unless layer.is_a?(Hash)
        errors.add(layer_name, "must be a JSON object")
        next
      end

      unless layer.key?("row") && layer.key?("col")
        errors.add(layer_name, "must include row and col")
      end
    end
  end
end
