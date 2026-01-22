//! Clara MCP Server
//!
//! Native tools for Clara exposed via the Model Context Protocol.
//! Run with: cargo run

mod tools;

use rmcp::{
    ErrorData as McpError,
    ServerHandler,
    ServiceExt,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::*,
    tool,
    tool_handler,
    tool_router,
    transport::stdio,
};
use serde::Deserialize;
use schemars::JsonSchema;
use std::sync::Arc;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::tools::{
    backup::BackupTools,
    claude_code::ClaudeCodeTools,
    sandbox::SandboxTools,
    ors_notes::OrsNotesTools,
};

// ========== Parameter Types ==========

#[derive(Debug, Deserialize, JsonSchema)]
pub struct ClaudeCodeParams {
    /// The task to execute
    pub task: String,
    /// Optional working directory path
    pub workdir: Option<String>,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct WorkdirParams {
    /// Path to the working directory
    pub path: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct CodeParams {
    /// Python code to execute
    pub code: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct PackageParams {
    /// Package name to install
    pub package: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct PathParams {
    /// File or directory path
    pub path: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct WriteFileParams {
    /// File path
    pub path: String,
    /// Content to write
    pub content: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct ListFilesParams {
    /// Directory path (optional)
    pub path: Option<String>,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct ShellParams {
    /// Shell command
    pub command: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct UserIdParams {
    /// User ID
    pub user_id: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct AddNoteParams {
    /// User ID
    pub user_id: String,
    /// Note content
    pub content: String,
    /// Category (optional)
    pub category: Option<String>,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct NoteIdParams {
    /// Note ID
    pub note_id: String,
}

// ========== Backup Parameter Types ==========

#[derive(Debug, Deserialize, JsonSchema)]
pub struct BackupNowParams {
    /// Destination name (optional, uses default if not specified)
    pub destination: Option<String>,
    /// Databases to backup (optional, backs up all if not specified)
    pub databases: Option<Vec<String>>,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct BackupListParams {
    /// Filter by destination name
    pub destination: Option<String>,
    /// Filter by database name (e.g., "clara", "mem0")
    pub database: Option<String>,
    /// Maximum number of backups to list
    pub limit: Option<u32>,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct BackupScheduleParams {
    /// Enable or disable scheduled backups
    pub enabled: bool,
    /// Cron expression for schedule (e.g., "0 3 * * *" for daily at 3 AM)
    pub cron: Option<String>,
    /// Number of days to retain backups
    pub retention_days: Option<u32>,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct BackupDestinationParams {
    /// Unique name for this destination
    pub name: String,
    /// Destination type: "s3", "google_drive", or "ftp"
    pub dest_type: String,
    /// Configuration as JSON (type-specific settings)
    pub config: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct BackupDestinationNameParams {
    /// Name of the destination
    pub name: String,
}

// ========== Server Implementation ==========

/// Clara MCP Server
#[derive(Clone)]
pub struct ClaraServer {
    backup: Arc<BackupTools>,
    claude_code: Arc<ClaudeCodeTools>,
    sandbox: Arc<SandboxTools>,
    ors_notes: Arc<OrsNotesTools>,
    tool_router: ToolRouter<Self>,
}

#[tool_router]
impl ClaraServer {
    pub fn new() -> Self {
        Self {
            backup: Arc::new(BackupTools::new()),
            claude_code: Arc::new(ClaudeCodeTools::new()),
            sandbox: Arc::new(SandboxTools::new()),
            ors_notes: Arc::new(OrsNotesTools::new()),
            tool_router: Self::tool_router(),
        }
    }

    // ===== Backup Tools =====

    #[tool(description = "Trigger an immediate database backup. Backs up Clara and Mem0 databases to configured storage.")]
    async fn backup_now(&self, Parameters(p): Parameters<BackupNowParams>) -> Result<CallToolResult, McpError> {
        match self.backup.backup_now(p.destination, p.databases).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "List available database backups with optional filters.")]
    async fn backup_list(&self, Parameters(p): Parameters<BackupListParams>) -> Result<CallToolResult, McpError> {
        match self.backup.list_backups(p.destination, p.database, p.limit).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Get current backup status including last backup time, schedule, and configured destinations.")]
    async fn backup_status(&self) -> Result<CallToolResult, McpError> {
        match self.backup.get_status().await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Configure the backup schedule. Use cron expressions for timing (e.g., '0 3 * * *' for daily at 3 AM).")]
    async fn backup_schedule(&self, Parameters(p): Parameters<BackupScheduleParams>) -> Result<CallToolResult, McpError> {
        match self.backup.set_schedule(p.enabled, p.cron, p.retention_days).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Add or update a backup destination. Supports S3, Google Drive, and FTP/SFTP.")]
    async fn backup_config(&self, Parameters(p): Parameters<BackupDestinationParams>) -> Result<CallToolResult, McpError> {
        let config: serde_json::Value = match serde_json::from_str(&p.config) {
            Ok(v) => v,
            Err(e) => return Ok(CallToolResult::error(vec![Content::text(format!("Invalid config JSON: {}", e))])),
        };

        match self.backup.configure_destination(p.name, p.dest_type, config).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "List all configured backup destinations.")]
    async fn backup_destinations(&self) -> Result<CallToolResult, McpError> {
        match self.backup.list_destinations().await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Remove a backup destination by name.")]
    async fn backup_destination_delete(&self, Parameters(p): Parameters<BackupDestinationNameParams>) -> Result<CallToolResult, McpError> {
        match self.backup.delete_destination(p.name).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    // ===== Claude Code Tools =====

    #[tool(description = "Execute a coding task using Claude Code CLI")]
    async fn claude_code(&self, Parameters(p): Parameters<ClaudeCodeParams>) -> Result<CallToolResult, McpError> {
        match self.claude_code.execute(p.task, p.workdir).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Get the current working directory for Claude Code")]
    async fn claude_code_get_workdir(&self) -> Result<CallToolResult, McpError> {
        match self.claude_code.get_workdir().await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Set the working directory for Claude Code")]
    async fn claude_code_set_workdir(&self, Parameters(p): Parameters<WorkdirParams>) -> Result<CallToolResult, McpError> {
        match self.claude_code.set_workdir(p.path).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Check Claude Code availability and status")]
    async fn claude_code_status(&self) -> Result<CallToolResult, McpError> {
        match self.claude_code.status().await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    // ===== Sandbox Tools =====

    #[tool(description = "Execute Python code in a sandboxed environment")]
    async fn execute_python(&self, Parameters(p): Parameters<CodeParams>) -> Result<CallToolResult, McpError> {
        match self.sandbox.execute_python(p.code).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Install a Python package in the sandbox")]
    async fn install_package(&self, Parameters(p): Parameters<PackageParams>) -> Result<CallToolResult, McpError> {
        match self.sandbox.install_package(p.package).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Read a file from the sandbox")]
    async fn sandbox_read_file(&self, Parameters(p): Parameters<PathParams>) -> Result<CallToolResult, McpError> {
        match self.sandbox.read_file(p.path).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Write content to a file in the sandbox")]
    async fn sandbox_write_file(&self, Parameters(p): Parameters<WriteFileParams>) -> Result<CallToolResult, McpError> {
        match self.sandbox.write_file(p.path, p.content).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "List files in a sandbox directory")]
    async fn sandbox_list_files(&self, Parameters(p): Parameters<ListFilesParams>) -> Result<CallToolResult, McpError> {
        match self.sandbox.list_files(p.path).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Run a shell command in the sandbox")]
    async fn run_shell(&self, Parameters(p): Parameters<ShellParams>) -> Result<CallToolResult, McpError> {
        match self.sandbox.run_shell(p.command).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    // ===== ORS Notes Tools =====

    #[tool(description = "List ORS notes for a user")]
    async fn ors_list_notes(&self, Parameters(p): Parameters<UserIdParams>) -> Result<CallToolResult, McpError> {
        match self.ors_notes.list(p.user_id).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Add an ORS note")]
    async fn ors_add_note(&self, Parameters(p): Parameters<AddNoteParams>) -> Result<CallToolResult, McpError> {
        match self.ors_notes.add(p.user_id, p.content, p.category).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Archive an ORS note")]
    async fn ors_archive_note(&self, Parameters(p): Parameters<NoteIdParams>) -> Result<CallToolResult, McpError> {
        match self.ors_notes.archive(p.note_id).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }
}

#[tool_handler]
impl ServerHandler for ClaraServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::LATEST,
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            server_info: Implementation::from_build_env(),
            instructions: Some("Clara's native tools for coding, sandbox execution, backups, and notes.".into()),
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer().with_writer(std::io::stderr))
        .with(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    // Load environment
    dotenvy::dotenv().ok();

    tracing::info!("Starting Clara MCP Server v{}", env!("CARGO_PKG_VERSION"));

    // Create and run server
    let server = ClaraServer::new();

    // Serve via stdio
    let service = server.serve(stdio()).await?;
    service.waiting().await?;

    Ok(())
}
