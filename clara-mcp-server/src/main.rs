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
    claude_code::ClaudeCodeTools,
    discord::DiscordTools,
    sandbox::SandboxTools,
    local_files::LocalFilesTools,
    google::GoogleTools,
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
pub struct ChannelMessageParams {
    /// Discord channel ID
    pub channel_id: String,
    /// Message content
    pub message: String,
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
pub struct LocalFileParams {
    /// Filename
    pub filename: String,
    /// User ID
    pub user_id: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct SaveFileParams {
    /// Filename
    pub filename: String,
    /// Content to save
    pub content: String,
    /// User ID
    pub user_id: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct UserIdParams {
    /// User ID
    pub user_id: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct DownloadFromSandboxParams {
    /// Sandbox file path
    pub sandbox_path: String,
    /// Local filename (optional)
    pub local_filename: Option<String>,
    /// User ID
    pub user_id: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct UploadToSandboxParams {
    /// Local filename
    pub local_filename: String,
    /// Sandbox destination path (optional)
    pub sandbox_path: Option<String>,
    /// User ID
    pub user_id: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct CalendarListParams {
    /// User ID
    pub user_id: String,
    /// Calendar ID (default: primary)
    pub calendar_id: Option<String>,
    /// Maximum results
    pub max_results: Option<i32>,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct CalendarCreateParams {
    /// User ID
    pub user_id: String,
    /// Event title
    pub title: String,
    /// Start time (ISO 8601)
    pub start_time: String,
    /// End time (ISO 8601)
    pub end_time: String,
    /// Description (optional)
    pub description: Option<String>,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct SheetsReadParams {
    /// User ID
    pub user_id: String,
    /// Spreadsheet ID
    pub spreadsheet_id: String,
    /// Range in A1 notation
    pub range: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct SheetsWriteParams {
    /// User ID
    pub user_id: String,
    /// Spreadsheet ID
    pub spreadsheet_id: String,
    /// Range in A1 notation
    pub range: String,
    /// Data as JSON array
    pub values: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct DriveListParams {
    /// User ID
    pub user_id: String,
    /// Search query (optional)
    pub query: Option<String>,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct DriveDownloadParams {
    /// User ID
    pub user_id: String,
    /// File ID
    pub file_id: String,
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

// ========== Server Implementation ==========

/// Clara MCP Server
#[derive(Clone)]
pub struct ClaraServer {
    claude_code: Arc<ClaudeCodeTools>,
    discord: Arc<DiscordTools>,
    sandbox: Arc<SandboxTools>,
    local_files: Arc<LocalFilesTools>,
    google: Arc<GoogleTools>,
    ors_notes: Arc<OrsNotesTools>,
    tool_router: ToolRouter<Self>,
}

#[tool_router]
impl ClaraServer {
    pub fn new() -> Self {
        Self {
            claude_code: Arc::new(ClaudeCodeTools::new()),
            discord: Arc::new(DiscordTools::new()),
            sandbox: Arc::new(SandboxTools::new()),
            local_files: Arc::new(LocalFilesTools::new()),
            google: Arc::new(GoogleTools::new()),
            ors_notes: Arc::new(OrsNotesTools::new()),
            tool_router: Self::tool_router(),
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

    // ===== Discord Tools =====

    #[tool(description = "Send a message to a Discord channel")]
    async fn send_message_to_channel(&self, Parameters(p): Parameters<ChannelMessageParams>) -> Result<CallToolResult, McpError> {
        match self.discord.send_message(p.channel_id, p.message).await {
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

    // ===== Local Files Tools =====

    #[tool(description = "Save content to local file storage")]
    async fn save_to_local(&self, Parameters(p): Parameters<SaveFileParams>) -> Result<CallToolResult, McpError> {
        match self.local_files.save(p.filename, p.content, p.user_id).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "List files in local storage for a user")]
    async fn list_local_files(&self, Parameters(p): Parameters<UserIdParams>) -> Result<CallToolResult, McpError> {
        match self.local_files.list(p.user_id).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Read a file from local storage")]
    async fn read_local_file(&self, Parameters(p): Parameters<LocalFileParams>) -> Result<CallToolResult, McpError> {
        match self.local_files.read(p.filename, p.user_id).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Delete a file from local storage")]
    async fn delete_local_file(&self, Parameters(p): Parameters<LocalFileParams>) -> Result<CallToolResult, McpError> {
        match self.local_files.delete(p.filename, p.user_id).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Download a file from sandbox to local storage")]
    async fn download_from_sandbox(&self, Parameters(p): Parameters<DownloadFromSandboxParams>) -> Result<CallToolResult, McpError> {
        match self.local_files.download_from_sandbox(p.sandbox_path, p.local_filename, p.user_id).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Upload a file from local storage to sandbox")]
    async fn upload_to_sandbox(&self, Parameters(p): Parameters<UploadToSandboxParams>) -> Result<CallToolResult, McpError> {
        match self.local_files.upload_to_sandbox(p.local_filename, p.sandbox_path, p.user_id).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    // ===== Google Calendar Tools =====

    #[tool(description = "List upcoming Google Calendar events")]
    async fn google_calendar_list_events(&self, Parameters(p): Parameters<CalendarListParams>) -> Result<CallToolResult, McpError> {
        match self.google.calendar_list_events(p.user_id, p.calendar_id, p.max_results).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Create a Google Calendar event")]
    async fn google_calendar_create_event(&self, Parameters(p): Parameters<CalendarCreateParams>) -> Result<CallToolResult, McpError> {
        match self.google.calendar_create_event(p.user_id, p.title, p.start_time, p.end_time, p.description).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    // ===== Google Sheets Tools =====

    #[tool(description = "Read data from a Google Sheets range")]
    async fn google_sheets_read(&self, Parameters(p): Parameters<SheetsReadParams>) -> Result<CallToolResult, McpError> {
        match self.google.sheets_read(p.user_id, p.spreadsheet_id, p.range).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Write data to a Google Sheets range")]
    async fn google_sheets_write(&self, Parameters(p): Parameters<SheetsWriteParams>) -> Result<CallToolResult, McpError> {
        match self.google.sheets_write(p.user_id, p.spreadsheet_id, p.range, p.values).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    // ===== Google Drive Tools =====

    #[tool(description = "List files in Google Drive")]
    async fn google_drive_list(&self, Parameters(p): Parameters<DriveListParams>) -> Result<CallToolResult, McpError> {
        match self.google.drive_list(p.user_id, p.query).await {
            Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
        }
    }

    #[tool(description = "Download a file from Google Drive")]
    async fn google_drive_download(&self, Parameters(p): Parameters<DriveDownloadParams>) -> Result<CallToolResult, McpError> {
        match self.google.drive_download(p.user_id, p.file_id).await {
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
            instructions: Some("Clara's native tools for coding, file management, Google Workspace, and more.".into()),
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
