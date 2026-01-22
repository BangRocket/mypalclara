//! Backup tools for Clara MCP Server
//!
//! Provides database backup functionality with support for multiple storage backends:
//! - S3-compatible storage (AWS S3, Wasabi, MinIO, etc.)
//! - Google Drive (via OAuth)
//! - FTP/SFTP
//!
//! Features:
//! - Immediate backups
//! - Scheduled backups (cron-style)
//! - Backup listing and restoration info
//! - Multiple storage destinations

use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::env;

/// Backup storage destination types
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum BackupDestination {
    S3 {
        bucket: String,
        endpoint_url: Option<String>,
        region: Option<String>,
        prefix: Option<String>,
    },
    GoogleDrive {
        folder_id: Option<String>,
    },
    Ftp {
        host: String,
        port: Option<u16>,
        path: Option<String>,
        use_sftp: bool,
    },
}

/// Backup schedule configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackupSchedule {
    pub enabled: bool,
    pub cron: String, // e.g., "0 3 * * *" for daily at 3 AM
    pub retention_days: u32,
    pub destinations: Vec<String>, // destination names
}

/// Backup status information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackupStatus {
    pub last_backup: Option<String>,
    pub last_backup_size: Option<u64>,
    pub last_error: Option<String>,
    pub next_scheduled: Option<String>,
    pub total_backups: u32,
    pub schedule: Option<BackupSchedule>,
}

/// Backup entry from listing
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackupEntry {
    pub name: String,
    pub database: String,
    pub timestamp: String,
    pub size_bytes: u64,
    pub destination: String,
}

pub struct BackupTools {
    client: Client,
    api_base_url: String,
}

impl BackupTools {
    pub fn new() -> Self {
        let api_base_url = env::var("CLARA_API_URL")
            .unwrap_or_else(|_| "http://localhost:8000".to_string());

        Self {
            client: Client::new(),
            api_base_url,
        }
    }

    /// Trigger an immediate backup
    pub async fn backup_now(
        &self,
        destination: Option<String>,
        databases: Option<Vec<String>>,
    ) -> Result<String, String> {
        // Build request to backup API
        let mut params = vec![];
        if let Some(dest) = destination {
            params.push(format!("destination={}", dest));
        }
        if let Some(dbs) = databases {
            params.push(format!("databases={}", dbs.join(",")));
        }

        let query = if params.is_empty() {
            String::new()
        } else {
            format!("?{}", params.join("&"))
        };

        let url = format!("{}/api/backup/now{}", self.api_base_url, query);

        match self.client.post(&url).send().await {
            Ok(resp) => {
                if resp.status().is_success() {
                    match resp.json::<serde_json::Value>().await {
                        Ok(data) => {
                            let status = data.get("status").and_then(|v| v.as_str()).unwrap_or("unknown");
                            let message = data.get("message").and_then(|v| v.as_str()).unwrap_or("");
                            let backup_id = data.get("backup_id").and_then(|v| v.as_str());

                            let mut result = format!("Backup {}\n", status);
                            if !message.is_empty() {
                                result.push_str(&format!("Message: {}\n", message));
                            }
                            if let Some(id) = backup_id {
                                result.push_str(&format!("Backup ID: {}\n", id));
                            }

                            // Include details if present
                            if let Some(details) = data.get("details") {
                                if let Some(clara) = details.get("clara") {
                                    result.push_str(&format!("\nClara DB: {}", clara));
                                }
                                if let Some(mem0) = details.get("mem0") {
                                    result.push_str(&format!("\nMem0 DB: {}", mem0));
                                }
                            }

                            Ok(result)
                        }
                        Err(e) => Ok(format!("Backup triggered (response parse error: {})", e)),
                    }
                } else {
                    let status = resp.status();
                    let body = resp.text().await.unwrap_or_default();
                    Err(format!("Backup failed: {} - {}", status, body))
                }
            }
            Err(e) => Err(format!("Failed to connect to backup service: {}", e)),
        }
    }

    /// List available backups
    pub async fn list_backups(
        &self,
        destination: Option<String>,
        database: Option<String>,
        limit: Option<u32>,
    ) -> Result<String, String> {
        let mut params = vec![];
        if let Some(dest) = destination {
            params.push(format!("destination={}", dest));
        }
        if let Some(db) = database {
            params.push(format!("database={}", db));
        }
        if let Some(lim) = limit {
            params.push(format!("limit={}", lim));
        }

        let query = if params.is_empty() {
            String::new()
        } else {
            format!("?{}", params.join("&"))
        };

        let url = format!("{}/api/backup/list{}", self.api_base_url, query);

        match self.client.get(&url).send().await {
            Ok(resp) => {
                if resp.status().is_success() {
                    match resp.json::<serde_json::Value>().await {
                        Ok(data) => {
                            let backups = data.get("backups").and_then(|v| v.as_array());

                            match backups {
                                Some(list) if !list.is_empty() => {
                                    let mut result = format!("Found {} backup(s):\n\n", list.len());

                                    for backup in list {
                                        let name = backup.get("name").and_then(|v| v.as_str()).unwrap_or("unknown");
                                        let db = backup.get("database").and_then(|v| v.as_str()).unwrap_or("unknown");
                                        let ts = backup.get("timestamp").and_then(|v| v.as_str()).unwrap_or("unknown");
                                        let size = backup.get("size_bytes").and_then(|v| v.as_u64()).unwrap_or(0);
                                        let dest = backup.get("destination").and_then(|v| v.as_str()).unwrap_or("default");

                                        let size_str = if size > 1024 * 1024 {
                                            format!("{:.2} MB", size as f64 / (1024.0 * 1024.0))
                                        } else if size > 1024 {
                                            format!("{:.2} KB", size as f64 / 1024.0)
                                        } else {
                                            format!("{} bytes", size)
                                        };

                                        result.push_str(&format!(
                                            "- {} ({})\n  Database: {}\n  Size: {}\n  Destination: {}\n\n",
                                            name, ts, db, size_str, dest
                                        ));
                                    }

                                    Ok(result)
                                }
                                _ => Ok("No backups found.".to_string()),
                            }
                        }
                        Err(e) => Err(format!("Failed to parse backup list: {}", e)),
                    }
                } else {
                    let status = resp.status();
                    let body = resp.text().await.unwrap_or_default();
                    Err(format!("Failed to list backups: {} - {}", status, body))
                }
            }
            Err(e) => Err(format!("Failed to connect to backup service: {}", e)),
        }
    }

    /// Get backup status
    pub async fn get_status(&self) -> Result<String, String> {
        let url = format!("{}/api/backup/status", self.api_base_url);

        match self.client.get(&url).send().await {
            Ok(resp) => {
                if resp.status().is_success() {
                    match resp.json::<serde_json::Value>().await {
                        Ok(data) => {
                            let mut result = String::from("Backup Status:\n\n");

                            if let Some(last) = data.get("last_backup").and_then(|v| v.as_str()) {
                                result.push_str(&format!("Last backup: {}\n", last));
                            } else {
                                result.push_str("Last backup: Never\n");
                            }

                            if let Some(size) = data.get("last_backup_size").and_then(|v| v.as_u64()) {
                                let size_str = if size > 1024 * 1024 {
                                    format!("{:.2} MB", size as f64 / (1024.0 * 1024.0))
                                } else {
                                    format!("{:.2} KB", size as f64 / 1024.0)
                                };
                                result.push_str(&format!("Last backup size: {}\n", size_str));
                            }

                            if let Some(err) = data.get("last_error").and_then(|v| v.as_str()) {
                                if !err.is_empty() {
                                    result.push_str(&format!("Last error: {}\n", err));
                                }
                            }

                            if let Some(next) = data.get("next_scheduled").and_then(|v| v.as_str()) {
                                result.push_str(&format!("Next scheduled: {}\n", next));
                            }

                            if let Some(total) = data.get("total_backups").and_then(|v| v.as_u64()) {
                                result.push_str(&format!("Total backups: {}\n", total));
                            }

                            // Schedule info
                            if let Some(schedule) = data.get("schedule") {
                                result.push_str("\nSchedule:\n");
                                let enabled = schedule.get("enabled").and_then(|v| v.as_bool()).unwrap_or(false);
                                result.push_str(&format!("  Enabled: {}\n", enabled));

                                if let Some(cron) = schedule.get("cron").and_then(|v| v.as_str()) {
                                    result.push_str(&format!("  Cron: {}\n", cron));
                                }

                                if let Some(retention) = schedule.get("retention_days").and_then(|v| v.as_u64()) {
                                    result.push_str(&format!("  Retention: {} days\n", retention));
                                }
                            }

                            // Destinations
                            if let Some(dests) = data.get("destinations").and_then(|v| v.as_array()) {
                                result.push_str("\nConfigured destinations:\n");
                                for dest in dests {
                                    if let Some(name) = dest.get("name").and_then(|v| v.as_str()) {
                                        let dtype = dest.get("type").and_then(|v| v.as_str()).unwrap_or("unknown");
                                        let status = dest.get("status").and_then(|v| v.as_str()).unwrap_or("unknown");
                                        result.push_str(&format!("  - {} ({}) - {}\n", name, dtype, status));
                                    }
                                }
                            }

                            Ok(result)
                        }
                        Err(e) => Err(format!("Failed to parse status: {}", e)),
                    }
                } else {
                    let status = resp.status();
                    let body = resp.text().await.unwrap_or_default();
                    Err(format!("Failed to get status: {} - {}", status, body))
                }
            }
            Err(e) => Err(format!("Failed to connect to backup service: {}", e)),
        }
    }

    /// Set backup schedule
    pub async fn set_schedule(
        &self,
        enabled: bool,
        cron: Option<String>,
        retention_days: Option<u32>,
    ) -> Result<String, String> {
        let url = format!("{}/api/backup/schedule", self.api_base_url);

        let mut body = serde_json::json!({
            "enabled": enabled,
        });

        if let Some(c) = cron {
            body["cron"] = serde_json::Value::String(c);
        }
        if let Some(r) = retention_days {
            body["retention_days"] = serde_json::Value::Number(r.into());
        }

        match self.client.post(&url).json(&body).send().await {
            Ok(resp) => {
                if resp.status().is_success() {
                    match resp.json::<serde_json::Value>().await {
                        Ok(data) => {
                            let status = data.get("status").and_then(|v| v.as_str()).unwrap_or("updated");
                            let message = data.get("message").and_then(|v| v.as_str()).unwrap_or("");

                            let mut result = format!("Schedule {}\n", status);
                            if !message.is_empty() {
                                result.push_str(&format!("{}\n", message));
                            }

                            if let Some(schedule) = data.get("schedule") {
                                let enabled = schedule.get("enabled").and_then(|v| v.as_bool()).unwrap_or(false);
                                let cron_val = schedule.get("cron").and_then(|v| v.as_str()).unwrap_or("not set");
                                let retention = schedule.get("retention_days").and_then(|v| v.as_u64()).unwrap_or(7);

                                result.push_str(&format!("\nNew schedule:\n"));
                                result.push_str(&format!("  Enabled: {}\n", enabled));
                                result.push_str(&format!("  Cron: {}\n", cron_val));
                                result.push_str(&format!("  Retention: {} days\n", retention));
                            }

                            Ok(result)
                        }
                        Err(e) => Ok(format!("Schedule updated (response parse error: {})", e)),
                    }
                } else {
                    let status = resp.status();
                    let body = resp.text().await.unwrap_or_default();
                    Err(format!("Failed to update schedule: {} - {}", status, body))
                }
            }
            Err(e) => Err(format!("Failed to connect to backup service: {}", e)),
        }
    }

    /// Configure a backup destination
    pub async fn configure_destination(
        &self,
        name: String,
        dest_type: String,
        config: serde_json::Value,
    ) -> Result<String, String> {
        let url = format!("{}/api/backup/destinations", self.api_base_url);

        let body = serde_json::json!({
            "name": name,
            "type": dest_type,
            "config": config,
        });

        match self.client.post(&url).json(&body).send().await {
            Ok(resp) => {
                if resp.status().is_success() {
                    Ok(format!("Destination '{}' configured successfully as {} storage.", name, dest_type))
                } else {
                    let status = resp.status();
                    let body = resp.text().await.unwrap_or_default();
                    Err(format!("Failed to configure destination: {} - {}", status, body))
                }
            }
            Err(e) => Err(format!("Failed to connect to backup service: {}", e)),
        }
    }

    /// List configured destinations
    pub async fn list_destinations(&self) -> Result<String, String> {
        let url = format!("{}/api/backup/destinations", self.api_base_url);

        match self.client.get(&url).send().await {
            Ok(resp) => {
                if resp.status().is_success() {
                    match resp.json::<serde_json::Value>().await {
                        Ok(data) => {
                            let destinations = data.get("destinations").and_then(|v| v.as_array());

                            match destinations {
                                Some(list) if !list.is_empty() => {
                                    let mut result = format!("Configured destinations ({}):\n\n", list.len());

                                    for dest in list {
                                        let name = dest.get("name").and_then(|v| v.as_str()).unwrap_or("unknown");
                                        let dtype = dest.get("type").and_then(|v| v.as_str()).unwrap_or("unknown");
                                        let status = dest.get("status").and_then(|v| v.as_str()).unwrap_or("unknown");
                                        let is_default = dest.get("is_default").and_then(|v| v.as_bool()).unwrap_or(false);

                                        result.push_str(&format!("- {} ({}){}\n", name, dtype,
                                            if is_default { " [default]" } else { "" }
                                        ));
                                        result.push_str(&format!("  Status: {}\n", status));

                                        // Type-specific info
                                        if let Some(config) = dest.get("config") {
                                            match dtype {
                                                "s3" => {
                                                    if let Some(bucket) = config.get("bucket").and_then(|v| v.as_str()) {
                                                        result.push_str(&format!("  Bucket: {}\n", bucket));
                                                    }
                                                    if let Some(endpoint) = config.get("endpoint_url").and_then(|v| v.as_str()) {
                                                        result.push_str(&format!("  Endpoint: {}\n", endpoint));
                                                    }
                                                }
                                                "google_drive" => {
                                                    if let Some(folder) = config.get("folder_id").and_then(|v| v.as_str()) {
                                                        result.push_str(&format!("  Folder ID: {}\n", folder));
                                                    }
                                                }
                                                "ftp" => {
                                                    if let Some(host) = config.get("host").and_then(|v| v.as_str()) {
                                                        let port = config.get("port").and_then(|v| v.as_u64()).unwrap_or(21);
                                                        let sftp = config.get("use_sftp").and_then(|v| v.as_bool()).unwrap_or(false);
                                                        result.push_str(&format!("  Host: {}:{} ({})\n", host, port,
                                                            if sftp { "SFTP" } else { "FTP" }
                                                        ));
                                                    }
                                                }
                                                _ => {}
                                            }
                                        }

                                        result.push_str("\n");
                                    }

                                    Ok(result)
                                }
                                _ => Ok("No destinations configured.\n\nUse backup_config to add a destination.".to_string()),
                            }
                        }
                        Err(e) => Err(format!("Failed to parse destinations: {}", e)),
                    }
                } else {
                    let status = resp.status();
                    let body = resp.text().await.unwrap_or_default();
                    Err(format!("Failed to list destinations: {} - {}", status, body))
                }
            }
            Err(e) => Err(format!("Failed to connect to backup service: {}", e)),
        }
    }

    /// Delete a backup destination
    pub async fn delete_destination(&self, name: String) -> Result<String, String> {
        let url = format!("{}/api/backup/destinations/{}", self.api_base_url, name);

        match self.client.delete(&url).send().await {
            Ok(resp) => {
                if resp.status().is_success() {
                    Ok(format!("Destination '{}' deleted.", name))
                } else {
                    let status = resp.status();
                    let body = resp.text().await.unwrap_or_default();
                    Err(format!("Failed to delete destination: {} - {}", status, body))
                }
            }
            Err(e) => Err(format!("Failed to connect to backup service: {}", e)),
        }
    }
}
