mod db;

use db::Database;
use tauri::Manager;

// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
async fn get_db_path(app: tauri::AppHandle) -> Result<String, String> {
    Database::path(&app)
        .map(|p| p.display().to_string())
        .map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            // Initialize database
            let app_handle = app.handle().clone();
            tauri::async_runtime::block_on(async move {
                match Database::new(&app_handle).await {
                    Ok(db) => {
                        // Store database in app state for commands to access
                        app_handle.manage(db);
                        println!("Database ready");
                    }
                    Err(e) => {
                        eprintln!("Failed to initialize database: {}", e);
                        // Don't crash - the app can still run, just without database
                    }
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet, get_db_path])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
