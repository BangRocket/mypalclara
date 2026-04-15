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

ActiveRecord::Schema[8.1].define(version: 2026_02_20_215500) do
  # These are extensions that must be enabled in order to support this database
  enable_extension "pg_catalog.plpgsql"

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
    t.datetime "updated_at", null: false
    t.index ["canonical_user_id"], name: "index_users_on_canonical_user_id", unique: true
  end

  add_foreign_key "game_players", "games"
  add_foreign_key "game_players", "users"
  add_foreign_key "games", "users", column: "created_by_id"
  add_foreign_key "moves", "game_players"
  add_foreign_key "moves", "games"
end
