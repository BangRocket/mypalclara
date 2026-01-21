//! Local file storage tools
//!
//! Persistent file storage with per-user isolation.

use std::path::PathBuf;
use std::fs;
use walkdir::WalkDir;

pub struct LocalFilesTools {
    base_dir: PathBuf,
}

impl LocalFilesTools {
    pub fn new() -> Self {
        let base_dir = std::env::var("CLARA_FILES_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("./clara_files"));

        // Ensure base directory exists
        fs::create_dir_all(&base_dir).ok();

        Self { base_dir }
    }

    fn user_dir(&self, user_id: &str) -> PathBuf {
        let safe_id = sanitize_filename(user_id);
        let path = self.base_dir.join(&safe_id);
        fs::create_dir_all(&path).ok();
        path
    }

    pub async fn save(&self, filename: String, content: String, user_id: String) -> Result<String, String> {
        let safe_name = sanitize_filename(&filename);
        let path = self.user_dir(&user_id).join(&safe_name);

        fs::write(&path, &content)
            .map_err(|e| format!("Failed to save file: {}", e))?;

        Ok(format!("Saved {} ({} bytes)", safe_name, content.len()))
    }

    pub async fn list(&self, user_id: String) -> Result<String, String> {
        let dir = self.user_dir(&user_id);

        let mut files = Vec::new();
        for entry in WalkDir::new(&dir).max_depth(1).into_iter().filter_map(|e| e.ok()) {
            if entry.file_type().is_file() {
                if let Some(name) = entry.file_name().to_str() {
                    let size = entry.metadata().map(|m| m.len()).unwrap_or(0);
                    files.push(format!("- {} ({} bytes)", name, size));
                }
            }
        }

        if files.is_empty() {
            Ok("No files saved.".to_string())
        } else {
            Ok(format!("**Saved Files:**\n{}", files.join("\n")))
        }
    }

    pub async fn read(&self, filename: String, user_id: String) -> Result<String, String> {
        let safe_name = sanitize_filename(&filename);
        let path = self.user_dir(&user_id).join(&safe_name);

        if !path.exists() {
            return Err(format!("File not found: {}", safe_name));
        }

        fs::read_to_string(&path)
            .map_err(|e| format!("Failed to read file: {}", e))
    }

    pub async fn delete(&self, filename: String, user_id: String) -> Result<String, String> {
        let safe_name = sanitize_filename(&filename);
        let path = self.user_dir(&user_id).join(&safe_name);

        if !path.exists() {
            return Err(format!("File not found: {}", safe_name));
        }

        fs::remove_file(&path)
            .map_err(|e| format!("Failed to delete file: {}", e))?;

        Ok(format!("Deleted: {}", safe_name))
    }

    pub async fn download_from_sandbox(
        &self,
        sandbox_path: String,
        local_filename: Option<String>,
        user_id: String,
    ) -> Result<String, String> {
        // Get the sandbox tools to read the file
        let sandbox = super::sandbox::SandboxTools::new();
        let content = sandbox.read_file(sandbox_path.clone()).await?;

        // Determine local filename
        let filename = local_filename.unwrap_or_else(|| {
            sandbox_path.split('/').last().unwrap_or("file").to_string()
        });

        self.save(filename.clone(), content, user_id).await?;
        Ok(format!("Downloaded {} from sandbox", filename))
    }

    pub async fn upload_to_sandbox(
        &self,
        local_filename: String,
        sandbox_path: Option<String>,
        user_id: String,
    ) -> Result<String, String> {
        // Read local file
        let content = self.read(local_filename.clone(), user_id).await?;

        // Determine sandbox path
        let dest = sandbox_path.unwrap_or_else(|| format!("/home/user/{}", local_filename));

        // Write to sandbox
        let sandbox = super::sandbox::SandboxTools::new();
        sandbox.write_file(dest.clone(), content).await?;

        Ok(format!("Uploaded {} to {}", local_filename, dest))
    }
}

fn sanitize_filename(name: &str) -> String {
    name.chars()
        .map(|c| if c.is_alphanumeric() || c == '.' || c == '-' || c == '_' { c } else { '_' })
        .collect::<String>()
        .trim_start_matches('.')
        .to_string()
}
