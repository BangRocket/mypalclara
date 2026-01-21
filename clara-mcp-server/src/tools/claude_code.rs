//! Claude Code integration tools
//!
//! Execute coding tasks using the Claude Code CLI.

use std::process::Command;
use std::sync::RwLock;

pub struct ClaudeCodeTools {
    workdir: RwLock<Option<String>>,
}

impl ClaudeCodeTools {
    pub fn new() -> Self {
        Self {
            workdir: RwLock::new(std::env::var("CLAUDE_CODE_WORKDIR").ok()),
        }
    }

    pub async fn execute(&self, task: String, workdir: Option<String>) -> Result<String, String> {
        let dir = workdir.or_else(|| self.workdir.read().ok()?.clone());

        let mut cmd = Command::new("claude");
        cmd.arg("--print");
        cmd.arg(&task);

        if let Some(ref d) = dir {
            cmd.current_dir(d);
        }

        // Set max turns from env
        if let Ok(turns) = std::env::var("CLAUDE_CODE_MAX_TURNS") {
            cmd.arg("--max-turns").arg(&turns);
        }

        match cmd.output() {
            Ok(output) => {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let stderr = String::from_utf8_lossy(&output.stderr);

                if output.status.success() {
                    Ok(stdout.to_string())
                } else {
                    Err(format!("Claude Code failed: {}\n{}", stdout, stderr))
                }
            }
            Err(e) => Err(format!("Failed to run Claude Code: {}", e)),
        }
    }

    pub async fn get_workdir(&self) -> Result<String, String> {
        let dir = self.workdir.read().map_err(|e| e.to_string())?;
        Ok(dir.clone().unwrap_or_else(|| "Not set".to_string()))
    }

    pub async fn set_workdir(&self, path: String) -> Result<String, String> {
        // Validate path exists
        if !std::path::Path::new(&path).exists() {
            return Err(format!("Path does not exist: {}", path));
        }

        let mut dir = self.workdir.write().map_err(|e| e.to_string())?;
        *dir = Some(path.clone());
        Ok(format!("Working directory set to: {}", path))
    }

    pub async fn status(&self) -> Result<String, String> {
        // Check if claude CLI is available
        let output = Command::new("claude")
            .arg("--version")
            .output();

        match output {
            Ok(o) if o.status.success() => {
                let version = String::from_utf8_lossy(&o.stdout);
                let workdir = self.get_workdir().await?;
                Ok(format!("Claude Code: Available\nVersion: {}\nWorkdir: {}",
                    version.trim(), workdir))
            }
            Ok(_) => Err("Claude Code CLI not authenticated or configured".to_string()),
            Err(_) => Err("Claude Code CLI not installed".to_string()),
        }
    }
}
