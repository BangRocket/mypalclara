class CreateFileSystemEntries < ActiveRecord::Migration[8.1]
  def change
    create_table :file_system_entries, id: :uuid do |t|
      t.references :user, null: false, foreign_key: true
      t.string :name, null: false
      t.uuid :parent_id
      t.string :entry_type, null: false  # 'file', 'directory', 'app-shortcut'
      t.string :extension
      t.string :app_id
      t.text :content
      t.jsonb :icon_position, default: { 'x' => 0, 'y' => 0 }
      t.string :icon
      t.boolean :disable_delete, default: false
      t.boolean :disable_copy, default: false
      t.timestamps
    end

    add_index :file_system_entries, [:user_id, :parent_id]
    add_index :file_system_entries, [:user_id, :name, :parent_id], unique: true
    add_foreign_key :file_system_entries, :file_system_entries, column: :parent_id
  end
end
