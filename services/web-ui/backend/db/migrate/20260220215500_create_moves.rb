class CreateMoves < ActiveRecord::Migration[8.1]
  def change
    create_table :moves do |t|
      t.references :game, null: false, foreign_key: true
      t.references :game_player, null: false, foreign_key: true
      t.integer :move_number
      t.jsonb :action
      t.jsonb :game_data_snapshot
      t.text :clara_commentary

      t.timestamps
    end
  end
end
