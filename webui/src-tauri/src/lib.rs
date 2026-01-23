mod commands;
mod db;
mod models;

use commands::notes;
use db::Database;
use tauri::Manager;
use tauri_specta::{collect_commands, Builder};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Build specta command registry
    let builder = Builder::<tauri::Wry>::new().commands(collect_commands![
        notes::list_notes,
        notes::get_note,
        notes::create_note,
        notes::update_note,
        notes::delete_note,
    ]);

    // Generate TypeScript bindings in debug mode
    #[cfg(debug_assertions)]
    builder
        .export(
            specta_typescript::Typescript::default()
                .bigint(specta_typescript::BigIntExportBehavior::Number),
            "../src/lib/bindings.ts",
        )
        .expect("Failed to export TypeScript bindings");

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(builder.invoke_handler())
        .setup(move |app| {
            // Register specta types for runtime
            builder.mount_events(app);

            // Initialize database
            let app_handle = app.handle().clone();
            tauri::async_runtime::block_on(async move {
                match Database::new(&app_handle).await {
                    Ok(db) => {
                        app_handle.manage(db);
                        println!("Database ready");
                    }
                    Err(e) => {
                        eprintln!("Failed to initialize database: {}", e);
                    }
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
