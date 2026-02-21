class CreateUsers < ActiveRecord::Migration[8.1]
  def change
    create_table :users do |t|
      t.string :canonical_user_id
      t.string :display_name
      t.string :avatar_url

      t.timestamps
    end
    add_index :users, :canonical_user_id, unique: true
  end
end
