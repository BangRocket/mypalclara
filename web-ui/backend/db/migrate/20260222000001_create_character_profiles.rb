class CreateCharacterProfiles < ActiveRecord::Migration[8.1]
  def change
    create_table :character_profiles do |t|
      t.string :personality, null: false
      t.string :display_name, null: false
      t.jsonb :base_layer, null: false, default: {}
      t.jsonb :hair_layer, default: {}
      t.jsonb :eyes_layer, default: {}
      t.jsonb :eyebrows_layer, default: {}
      t.jsonb :mouth_layer, default: {}
      t.jsonb :clothes_layer, default: {}
      t.jsonb :bg_layer, default: {}

      t.timestamps
    end
    add_index :character_profiles, :personality, unique: true
  end
end
