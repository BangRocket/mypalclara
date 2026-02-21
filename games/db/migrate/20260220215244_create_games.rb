class CreateGames < ActiveRecord::Migration[8.1]
  def change
    create_table :games do |t|
      t.string :game_type, null: false
      t.string :state, default: "waiting", null: false
      t.string :current_turn
      t.jsonb :game_data, default: {}, null: false
      t.integer :move_count, default: 0, null: false
      t.references :created_by, null: false, foreign_key: { to_table: :users }
      t.datetime :started_at
      t.datetime :finished_at

      t.timestamps
    end
  end
end
