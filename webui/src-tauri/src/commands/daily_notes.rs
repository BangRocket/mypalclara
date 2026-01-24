use crate::db::Database;
use crate::models::{DailyNote, Note};
use tauri::State;

/// Get or create a daily note for a specific date.
/// Date format: YYYY-MM-DD (e.g., "2026-01-23")
/// If a daily note exists for that date, returns it.
/// If not, creates one with title "January 23, 2026" format.
#[tauri::command]
#[specta::specta]
pub async fn get_or_create_daily_note(
    db: State<'_, Database>,
    date: String,
) -> Result<Note, String> {
    // Validate date format (basic check)
    if date.len() != 10 || date.chars().nth(4) != Some('-') || date.chars().nth(7) != Some('-') {
        return Err("Invalid date format. Expected YYYY-MM-DD".to_string());
    }

    // Check if daily note exists for this date
    let existing = sqlx::query_as::<_, Note>(
        r#"
        SELECT id, title, content, folder_id, author, is_daily_note, daily_note_date, created_at, updated_at
        FROM notes
        WHERE is_daily_note = 1 AND daily_note_date = ?
        "#,
    )
    .bind(&date)
    .fetch_optional(&db.pool)
    .await
    .map_err(|e| e.to_string())?;

    if let Some(note) = existing {
        return Ok(note);
    }

    // Parse date to create human-readable title
    let title = format_date_title(&date)?;

    // Create new daily note
    let result = sqlx::query(
        r#"
        INSERT INTO notes (title, content, is_daily_note, daily_note_date, author)
        VALUES (?, '', 1, ?, 'user')
        "#,
    )
    .bind(&title)
    .bind(&date)
    .execute(&db.pool)
    .await
    .map_err(|e| e.to_string())?;

    let id = result.last_insert_rowid();

    // Fetch and return the created note
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

/// List all dates that have daily notes (for calendar highlighting)
/// Returns list of DailyNote with id, title, date, timestamps
#[tauri::command]
#[specta::specta]
pub async fn list_daily_note_dates(db: State<'_, Database>) -> Result<Vec<DailyNote>, String> {
    sqlx::query_as::<_, DailyNote>(
        r#"
        SELECT id, title, daily_note_date, created_at, updated_at
        FROM notes
        WHERE is_daily_note = 1 AND daily_note_date IS NOT NULL
        ORDER BY daily_note_date DESC
        "#,
    )
    .fetch_all(&db.pool)
    .await
    .map_err(|e| e.to_string())
}

/// Format a YYYY-MM-DD date as "Month Day, Year" (e.g., "January 23, 2026")
fn format_date_title(date: &str) -> Result<String, String> {
    let parts: Vec<&str> = date.split('-').collect();
    if parts.len() != 3 {
        return Err("Invalid date format".to_string());
    }

    let year = parts[0];
    let month: u32 = parts[1].parse().map_err(|_| "Invalid month")?;
    let day: u32 = parts[2].parse().map_err(|_| "Invalid day")?;

    let month_name = match month {
        1 => "January",
        2 => "February",
        3 => "March",
        4 => "April",
        5 => "May",
        6 => "June",
        7 => "July",
        8 => "August",
        9 => "September",
        10 => "October",
        11 => "November",
        12 => "December",
        _ => return Err("Invalid month number".to_string()),
    };

    Ok(format!("{} {}, {}", month_name, day, year))
}
