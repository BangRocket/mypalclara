use serde::{Deserialize, Serialize};
use specta::Type;
use sqlx::FromRow;

/// A folder for organizing notes
#[derive(Debug, Clone, Serialize, Deserialize, Type, FromRow)]
pub struct Folder {
    pub id: i64,
    pub name: String,
    pub parent_id: Option<i64>,
    pub created_at: String,
    pub updated_at: String,
}

/// Input for creating a new folder
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct CreateFolderInput {
    pub name: String,
    pub parent_id: Option<i64>,
}

/// Input for updating a folder
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct UpdateFolderInput {
    pub name: Option<String>,
    pub parent_id: Option<i64>,
}
