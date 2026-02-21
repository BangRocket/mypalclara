class Move < ApplicationRecord
  belongs_to :game
  belongs_to :game_player

  validates :move_number, presence: true
  validates :action, presence: true
end
