mod commands;
mod db;
mod models;

use commands::{daily_notes, export, folders, notes, search, wiki_links};
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
        folders::list_folders,
        folders::get_folder,
        folders::create_folder,
        folders::update_folder,
        folders::delete_folder,
        export::export_note_to_file,
        daily_notes::get_or_create_daily_note,
        daily_notes::list_daily_note_dates,
        search::search_notes,
        search::get_all_note_titles,
        wiki_links::extract_and_save_wiki_links,
        wiki_links::get_backlinks,
        wiki_links::get_unlinked_mentions,
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
        .plugin(tauri_plugin_dialog::init())
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
