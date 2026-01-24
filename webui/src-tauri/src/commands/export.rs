use crate::db::Database;
use crate::models::Note;
use tauri::State;

/// Export a note to a markdown file at the specified path
/// Returns the path where the file was saved
#[tauri::command]
#[specta::specta]
pub async fn export_note_to_file(
    db: State<'_, Database>,
    note_id: i64,
    file_path: String,
) -> Result<String, String> {
    // Fetch the note
    let note: Note = sqlx::query_as::<_, Note>(
        r#"
        SELECT id, title, content, folder_id, author, created_at, updated_at
        FROM notes
        WHERE id = ?
        "#,
    )
    .bind(note_id)
    .fetch_one(&db.pool)
    .await
    .map_err(|e| format!("Failed to fetch note: {}", e))?;

    // Format as markdown with frontmatter
    let markdown = format!(
        "---\ntitle: {}\nauthor: {}\ncreated: {}\nupdated: {}\n---\n\n# {}\n\n{}",
        note.title,
        note.author,
        note.created_at,
        note.updated_at,
        note.title,
        note.content
    );

    // Write to file
    std::fs::write(&file_path, markdown)
        .map_err(|e| format!("Failed to write file: {}", e))?;

    Ok(file_path)
}
