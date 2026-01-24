use serde::{Deserialize, Serialize};
use specta::Type;
use sqlx::FromRow;

/// A note in the knowledge base
#[derive(Debug, Clone, Serialize, Deserialize, Type, FromRow)]
pub struct Note {
    pub id: i64,
    pub title: String,
    pub content: String,
    pub folder_id: Option<i64>,
    pub author: String,
    pub is_daily_note: bool,
    pub daily_note_date: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

/// A daily note entry (used for calendar display)
#[derive(Debug, Clone, Serialize, Deserialize, Type, FromRow)]
pub struct DailyNote {
    pub id: i64,
    pub title: String,
    pub daily_note_date: String,
    pub created_at: String,
    pub updated_at: String,
}

/// Input for creating a new note
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct CreateNoteInput {
    pub title: String,
    pub content: Option<String>,
    pub folder_id: Option<i64>,
}

/// Input for updating a note
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct UpdateNoteInput {
    pub title: Option<String>,
    pub content: Option<String>,
    pub folder_id: Option<i64>,
}
