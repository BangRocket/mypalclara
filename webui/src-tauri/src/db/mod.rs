use sqlx::{sqlite::SqlitePoolOptions, SqlitePool};
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

pub struct Database {
    pub pool: SqlitePool,
}

impl Database {
    pub async fn new(app: &AppHandle) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        // Get app data directory (platform-specific)
        let app_dir = app.path().app_data_dir()?;
        std::fs::create_dir_all(&app_dir)?;

        let db_path = app_dir.join("notes.db");
        let db_url = format!("sqlite:{}?mode=rwc", db_path.display());

        println!("Database path: {}", db_path.display());

        // Create connection pool
        let pool = SqlitePoolOptions::new()
            .max_connections(5)
            .after_connect(|conn, _meta| {
                Box::pin(async move {
                    // Enable WAL mode for better concurrency
                    sqlx::query("PRAGMA journal_mode=WAL")
                        .execute(&mut *conn)
                        .await?;

                    // Set busy timeout to 5 seconds to avoid "database is locked"
                    sqlx::query("PRAGMA busy_timeout=5000")
                        .execute(&mut *conn)
                        .await?;

                    // Enable foreign keys
                    sqlx::query("PRAGMA foreign_keys=ON")
                        .execute(&mut *conn)
                        .await?;

                    Ok(())
                })
            })
            .connect(&db_url)
            .await?;

        // Run migrations (path relative to CARGO_MANIFEST_DIR, i.e., src-tauri/)
        sqlx::migrate!("../migrations")
            .run(&pool)
            .await?;

        println!("Database initialized successfully");

        Ok(Self { pool })
    }

    /// Get the database path for debugging
    pub fn path(app: &AppHandle) -> Result<PathBuf, Box<dyn std::error::Error + Send + Sync>> {
        let app_dir = app.path().app_data_dir()?;
        Ok(app_dir.join("notes.db"))
    }
}
