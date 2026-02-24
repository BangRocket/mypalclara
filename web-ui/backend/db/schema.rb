# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# This file is the source Rails uses to define your schema when running `bin/rails
# db:schema:load`. When creating a new database, `bin/rails db:schema:load` tends to
# be faster and is potentially less error prone than running all of your
# migrations from scratch. Old migrations may fail to apply correctly if those
# migrations use external dependencies or application code.
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema[8.1].define(version: 2026_02_23_233129) do
  # These are extensions that must be enabled in order to support this database
  enable_extension "pg_catalog.plpgsql"

  create_table "character_profiles", force: :cascade do |t|
    t.jsonb "base_layer", default: {}, null: false
    t.jsonb "bg_layer", default: {}
    t.jsonb "clothes_layer", default: {}
    t.datetime "created_at", null: false
    t.string "display_name", null: false
    t.jsonb "eyebrows_layer", default: {}
    t.jsonb "eyes_layer", default: {}
    t.jsonb "hair_layer", default: {}
    t.jsonb "mouth_layer", default: {}
    t.string "personality", null: false
    t.datetime "updated_at", null: false
    t.index ["personality"], name: "index_character_profiles_on_personality", unique: true
  end

  create_table "file_system_entries", id: :uuid, default: -> { "gen_random_uuid()" }, force: :cascade do |t|
    t.string "app_id"
    t.text "content"
    t.datetime "created_at", null: false
    t.boolean "disable_copy", default: false
    t.boolean "disable_delete", default: false
    t.string "entry_type", null: false
    t.string "extension"
    t.string "icon"
    t.jsonb "icon_position", default: {"x" => 0, "y" => 0}
    t.string "name", null: false
    t.uuid "parent_id"
    t.datetime "updated_at", null: false
    t.bigint "user_id", null: false
    t.index ["user_id", "name", "parent_id"], name: "index_file_system_entries_on_user_id_and_name_and_parent_id", unique: true
    t.index ["user_id", "parent_id"], name: "index_file_system_entries_on_user_id_and_parent_id"
    t.index ["user_id"], name: "index_file_system_entries_on_user_id"
  end

  create_table "game_players", force: :cascade do |t|
    t.string "ai_personality"
    t.datetime "created_at", null: false
    t.bigint "game_id", null: false
    t.jsonb "hand_data", default: {}, null: false
    t.string "player_state", default: "active", null: false
    t.string "result"
    t.integer "seat_position", null: false
    t.datetime "updated_at", null: false
    t.bigint "user_id"
    t.index ["game_id"], name: "index_game_players_on_game_id"
    t.index ["user_id"], name: "index_game_players_on_user_id"
  end

  create_table "games", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.bigint "created_by_id", null: false
    t.string "current_turn"
    t.datetime "finished_at"
    t.jsonb "game_data", default: {}, null: false
    t.string "game_type", null: false
    t.integer "move_count", default: 0, null: false
    t.datetime "started_at"
    t.string "state", default: "waiting", null: false
    t.datetime "updated_at", null: false
    t.index ["created_by_id"], name: "index_games_on_created_by_id"
  end

  create_table "moves", force: :cascade do |t|
    t.jsonb "action"
    t.text "clara_commentary"
    t.datetime "created_at", null: false
    t.jsonb "game_data_snapshot"
    t.bigint "game_id", null: false
    t.bigint "game_player_id", null: false
    t.integer "move_number"
    t.datetime "updated_at", null: false
    t.index ["game_id"], name: "index_moves_on_game_id"
    t.index ["game_player_id"], name: "index_moves_on_game_player_id"
  end

  create_table "users", force: :cascade do |t|
    t.string "avatar_url"
    t.string "canonical_user_id"
    t.datetime "created_at", null: false
    t.string "display_name"
    t.boolean "is_admin", default: false, null: false
    t.datetime "updated_at", null: false
    t.index ["canonical_user_id"], name: "index_users_on_canonical_user_id", unique: true
  end

  add_foreign_key "file_system_entries", "file_system_entries", column: "parent_id"
  add_foreign_key "file_system_entries", "users"
  add_foreign_key "game_players", "games"
  add_foreign_key "game_players", "users"
  add_foreign_key "games", "users", column: "created_by_id"
  add_foreign_key "moves", "game_players"
  add_foreign_key "moves", "games"
end
