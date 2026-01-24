use crate::db::Database;
use crate::models::{CreateFolderInput, Folder, UpdateFolderInput};
use tauri::State;

/// List all folders, optionally filtered by parent
#[tauri::command]
#[specta::specta]
pub async fn list_folders(
    db: State<'_, Database>,
    parent_id: Option<i64>,
) -> Result<Vec<Folder>, String> {
    let folders = match parent_id {
        Some(pid) => {
            sqlx::query_as::<_, Folder>(
                r#"
                SELECT id, name, parent_id, created_at, updated_at
                FROM folders
                WHERE parent_id = ?
                ORDER BY name ASC
                "#,
            )
            .bind(pid)
            .fetch_all(&db.pool)
            .await
        }
        None => {
            sqlx::query_as::<_, Folder>(
                r#"
                SELECT id, name, parent_id, created_at, updated_at
                FROM folders
                ORDER BY name ASC
                "#,
            )
            .fetch_all(&db.pool)
            .await
        }
    };

    folders.map_err(|e| e.to_string())
}

/// Get a single folder by ID
#[tauri::command]
#[specta::specta]
pub async fn get_folder(db: State<'_, Database>, id: i64) -> Result<Folder, String> {
    sqlx::query_as::<_, Folder>(
        r#"
        SELECT id, name, parent_id, created_at, updated_at
        FROM folders
        WHERE id = ?
        "#,
    )
    .bind(id)
    .fetch_one(&db.pool)
    .await
    .map_err(|e| e.to_string())
}

/// Create a new folder
#[tauri::command]
#[specta::specta]
pub async fn create_folder(
    db: State<'_, Database>,
    input: CreateFolderInput,
) -> Result<Folder, String> {
    let result = sqlx::query(
        r#"
        INSERT INTO folders (name, parent_id)
        VALUES (?, ?)
        "#,
    )
    .bind(&input.name)
    .bind(input.parent_id)
    .execute(&db.pool)
    .await
    .map_err(|e| e.to_string())?;

    let id = result.last_insert_rowid();
    get_folder(db, id).await
}

/// Update an existing folder
#[tauri::command]
#[specta::specta]
pub async fn update_folder(
    db: State<'_, Database>,
    id: i64,
    input: UpdateFolderInput,
) -> Result<Folder, String> {
    let current = get_folder(db.clone(), id).await?;

    let name = input.name.unwrap_or(current.name);
    let parent_id = input.parent_id.or(current.parent_id);

    sqlx::query(
        r#"
        UPDATE folders
        SET name = ?, parent_id = ?, updated_at = datetime('now')
        WHERE id = ?
        "#,
    )
    .bind(&name)
    .bind(parent_id)
    .bind(id)
    .execute(&db.pool)
    .await
    .map_err(|e| e.to_string())?;

    get_folder(db, id).await
}

/// Delete a folder (notes in folder will have folder_id set to NULL)
#[tauri::command]
#[specta::specta]
pub async fn delete_folder(db: State<'_, Database>, id: i64) -> Result<(), String> {
    // Don't allow deleting the default "Notes" folder (id=1)
    if id == 1 {
        return Err("Cannot delete the default Notes folder".to_string());
    }

    sqlx::query("DELETE FROM folders WHERE id = ?")
        .bind(id)
        .execute(&db.pool)
        .await
        .map_err(|e| e.to_string())?;

    Ok(())
}
