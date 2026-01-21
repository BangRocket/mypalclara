//! Discord messaging tools
//!
//! Send messages to Discord channels via the bot.

use reqwest::Client;
use serde_json::json;

pub struct DiscordTools {
    client: Client,
    bot_token: Option<String>,
}

impl DiscordTools {
    pub fn new() -> Self {
        Self {
            client: Client::new(),
            bot_token: std::env::var("DISCORD_BOT_TOKEN").ok(),
        }
    }

    pub async fn send_message(&self, channel_id: String, message: String) -> Result<String, String> {
        let token = self.bot_token.as_ref()
            .ok_or("DISCORD_BOT_TOKEN not set")?;

        let url = format!("https://discord.com/api/v10/channels/{}/messages", channel_id);

        let response = self.client
            .post(&url)
            .header("Authorization", format!("Bot {}", token))
            .header("Content-Type", "application/json")
            .json(&json!({ "content": message }))
            .send()
            .await
            .map_err(|e| format!("Request failed: {}", e))?;

        if response.status().is_success() {
            Ok(format!("Message sent to channel {}", channel_id))
        } else {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            Err(format!("Discord API error {}: {}", status, body))
        }
    }
}
