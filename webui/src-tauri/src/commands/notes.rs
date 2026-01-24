use crate::db::Database;
use crate::models::{CreateNoteInput, Note, UpdateNoteInput};
use tauri::State;

/// List all notes, optionally filtered by folder
#[tauri::command]
#[specta::specta]
pub async fn list_notes(
    db: State<'_, Database>,
    folder_id: Option<i64>,
) -> Result<Vec<Note>, String> {
    let notes = match folder_id {
        Some(fid) => {
            sqlx::query_as::<_, Note>(
                r#"
                SELECT id, title, content, folder_id, author, is_daily_note, daily_note_date, created_at, updated_at
                FROM notes
                WHERE folder_id = ?
                ORDER BY updated_at DESC
                "#,
            )
            .bind(fid)
            .fetch_all(&db.pool)
            .await
        }
        None => {
            sqlx::query_as::<_, Note>(
                r#"
                SELECT id, title, content, folder_id, author, is_daily_note, daily_note_date, created_at, updated_at
                FROM notes
                ORDER BY updated_at DESC
                "#,
            )
            .fetch_all(&db.pool)
            .await
        }
    };

    notes.map_err(|e| e.to_string())
}

/// Get a single note by ID
#[tauri::command]
#[specta::specta]
pub async fn get_note(db: State<'_, Database>, id: i64) -> Result<Note, String> {
    sqlx::query_as::<_, Note>(
        r#"
        SELECT id, title, content, folder_id, author, is_daily_note, daily_note_date, created_at, updated_at
        FROM notes
        WHERE id = ?
        "#,
    )
    .bind(id)
    .fetch_one(&db.pool)
    .await
    .map_err(|e| e.to_string())
}

/// Create a new note
#[tauri::command]
#[specta::specta]
pub async fn create_note(db: State<'_, Database>, input: CreateNoteInput) -> Result<Note, String> {
    let content = input.content.unwrap_or_default();

    let result = sqlx::query(
        r#"
        INSERT INTO notes (title, content, folder_id, author)
        VALUES (?, ?, ?, 'user')
        "#,
    )
    .bind(&input.title)
    .bind(&content)
    .bind(input.folder_id)
    .execute(&db.pool)
    .await
    .map_err(|e| e.to_string())?;

    let id = result.last_insert_rowid();

    get_note(db, id).await
}

/// Update an existing note
#[tauri::command]
#[specta::specta]
pub async fn update_note(
    db: State<'_, Database>,
    id: i64,
    input: UpdateNoteInput,
) -> Result<Note, String> {
    // Fetch current note to merge updates
    let current = get_note(db.clone(), id).await?;

    let title = input.title.unwrap_or(current.title);
    let content = input.content.unwrap_or(current.content);
    let folder_id = input.folder_id.or(current.folder_id);

    sqlx::query(
        r#"
        UPDATE notes
        SET title = ?, content = ?, folder_id = ?, updated_at = datetime('now')
        WHERE id = ?
        "#,
    )
    .bind(&title)
    .bind(&content)
    .bind(folder_id)
    .bind(id)
    .execute(&db.pool)
    .await
    .map_err(|e| e.to_string())?;

    get_note(db, id).await
}

/// Delete a note
#[tauri::command]
#[specta::specta]
pub async fn delete_note(db: State<'_, Database>, id: i64) -> Result<(), String> {
    sqlx::query("DELETE FROM notes WHERE id = ?")
        .bind(id)
        .execute(&db.pool)
        .await
        .map_err(|e| e.to_string())?;

    Ok(())
}
