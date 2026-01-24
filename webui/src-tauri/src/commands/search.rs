use crate::db::Database;
use serde::{Deserialize, Serialize};
use tauri::State;

/// A search result with FTS5 ranking and snippet
#[derive(Debug, Clone, Serialize, Deserialize, specta::Type, sqlx::FromRow)]
pub struct SearchResult {
    pub id: i64,
    pub title: String,
    pub snippet: String,
    pub rank: f64,
}

/// A lightweight note title for autocomplete
#[derive(Debug, Clone, Serialize, Deserialize, specta::Type, sqlx::FromRow)]
pub struct NoteTitle {
    pub id: i64,
    pub title: String,
}

/// Search notes using FTS5 full-text search
/// Returns results ranked by BM25 with highlighted snippets
#[tauri::command]
#[specta::specta]
pub async fn search_notes(
    db: State<'_, Database>,
    query: String,
    limit: Option<i64>,
) -> Result<Vec<SearchResult>, String> {
    // Handle empty query - return empty results
    let query = query.trim();
    if query.is_empty() {
        return Ok(vec![]);
    }

    let limit = limit.unwrap_or(50);

    // FTS5 query with BM25 ranking and snippet generation
    // snippet(table, column_idx, start_mark, end_mark, ellipsis, max_tokens)
    // Column 1 is content (0-indexed: title=0, content=1)
    let results = sqlx::query_as::<_, SearchResult>(
        r#"
        SELECT
            n.id,
            n.title,
            snippet(notes_fts, 1, '<mark>', '</mark>', '...', 32) as snippet,
            bm25(notes_fts) as rank
        FROM notes_fts
        JOIN notes n ON notes_fts.rowid = n.id
        WHERE notes_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        "#,
    )
    .bind(&query)
    .bind(limit)
    .fetch_all(&db.pool)
    .await
    .map_err(|e| e.to_string())?;

    Ok(results)
}

/// Get all note titles for autocomplete
/// Returns notes ordered by most recently updated
#[tauri::command]
#[specta::specta]
pub async fn get_all_note_titles(db: State<'_, Database>) -> Result<Vec<NoteTitle>, String> {
    let titles = sqlx::query_as::<_, NoteTitle>(
        r#"
        SELECT id, title
        FROM notes
        ORDER BY updated_at DESC
        "#,
    )
    .fetch_all(&db.pool)
    .await
    .map_err(|e| e.to_string())?;

    Ok(titles)
}
