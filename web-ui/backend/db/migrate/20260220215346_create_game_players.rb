class CreateGamePlayers < ActiveRecord::Migration[8.1]
  def change
    create_table :game_players do |t|
      t.references :game, null: false, foreign_key: true
      t.references :user, null: true, foreign_key: true
      t.string :ai_personality
      t.integer :seat_position, null: false
      t.string :player_state, default: "active", null: false
      t.jsonb :hand_data, default: {}, null: false
      t.string :result

      t.timestamps
    end
  end
end
