//! Google Workspace tools
//!
//! Google Calendar, Sheets, and Drive integration via OAuth.

use reqwest::Client;
use serde_json::json;

pub struct GoogleTools {
    client: Client,
    api_base: String,
}

impl GoogleTools {
    pub fn new() -> Self {
        let api_base = std::env::var("CLARA_API_URL")
            .unwrap_or_else(|_| "http://localhost:8000".to_string());

        Self {
            client: Client::new(),
            api_base,
        }
    }

    async fn get_token(&self, user_id: &str) -> Result<String, String> {
        // Get OAuth token from Clara API service
        let url = format!("{}/oauth/google/token/{}", self.api_base, user_id);

        let response = self.client
            .get(&url)
            .send()
            .await
            .map_err(|e| format!("Failed to get token: {}", e))?;

        if !response.status().is_success() {
            return Err("Google account not connected. Use google_connect first.".to_string());
        }

        #[derive(serde::Deserialize)]
        struct TokenResponse {
            access_token: String,
        }

        let token: TokenResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse token: {}", e))?;

        Ok(token.access_token)
    }

    // ===== Calendar =====

    pub async fn calendar_list_events(
        &self,
        user_id: String,
        calendar_id: Option<String>,
        max_results: Option<i32>,
    ) -> Result<String, String> {
        let token = self.get_token(&user_id).await?;
        let cal_id = calendar_id.unwrap_or_else(|| "primary".to_string());
        let max = max_results.unwrap_or(10);

        let url = format!(
            "https://www.googleapis.com/calendar/v3/calendars/{}/events?maxResults={}&singleEvents=true&orderBy=startTime&timeMin={}",
            cal_id,
            max,
            chrono::Utc::now().to_rfc3339()
        );

        let response = self.client
            .get(&url)
            .header("Authorization", format!("Bearer {}", token))
            .send()
            .await
            .map_err(|e| format!("Calendar API failed: {}", e))?;

        let body = response.text().await.map_err(|e| e.to_string())?;
        Ok(body)
    }

    pub async fn calendar_create_event(
        &self,
        user_id: String,
        title: String,
        start_time: String,
        end_time: String,
        description: Option<String>,
    ) -> Result<String, String> {
        let token = self.get_token(&user_id).await?;

        let event = json!({
            "summary": title,
            "description": description.unwrap_or_default(),
            "start": { "dateTime": start_time },
            "end": { "dateTime": end_time }
        });

        let response = self.client
            .post("https://www.googleapis.com/calendar/v3/calendars/primary/events")
            .header("Authorization", format!("Bearer {}", token))
            .json(&event)
            .send()
            .await
            .map_err(|e| format!("Calendar API failed: {}", e))?;

        if response.status().is_success() {
            Ok(format!("Created event: {}", title))
        } else {
            let body = response.text().await.unwrap_or_default();
            Err(format!("Failed to create event: {}", body))
        }
    }

    // ===== Sheets =====

    pub async fn sheets_read(
        &self,
        user_id: String,
        spreadsheet_id: String,
        range: String,
    ) -> Result<String, String> {
        let token = self.get_token(&user_id).await?;

        let url = format!(
            "https://sheets.googleapis.com/v4/spreadsheets/{}/values/{}",
            spreadsheet_id, range
        );

        let response = self.client
            .get(&url)
            .header("Authorization", format!("Bearer {}", token))
            .send()
            .await
            .map_err(|e| format!("Sheets API failed: {}", e))?;

        let body = response.text().await.map_err(|e| e.to_string())?;
        Ok(body)
    }

    pub async fn sheets_write(
        &self,
        user_id: String,
        spreadsheet_id: String,
        range: String,
        values: String,
    ) -> Result<String, String> {
        let token = self.get_token(&user_id).await?;

        let values_parsed: serde_json::Value = serde_json::from_str(&values)
            .map_err(|e| format!("Invalid JSON values: {}", e))?;

        let url = format!(
            "https://sheets.googleapis.com/v4/spreadsheets/{}/values/{}?valueInputOption=USER_ENTERED",
            spreadsheet_id, range
        );

        let body = json!({ "values": values_parsed });

        let response = self.client
            .put(&url)
            .header("Authorization", format!("Bearer {}", token))
            .json(&body)
            .send()
            .await
            .map_err(|e| format!("Sheets API failed: {}", e))?;

        if response.status().is_success() {
            Ok(format!("Wrote data to {}", range))
        } else {
            let body = response.text().await.unwrap_or_default();
            Err(format!("Failed to write: {}", body))
        }
    }

    // ===== Drive =====

    pub async fn drive_list(
        &self,
        user_id: String,
        query: Option<String>,
    ) -> Result<String, String> {
        let token = self.get_token(&user_id).await?;

        let mut url = "https://www.googleapis.com/drive/v3/files?pageSize=20".to_string();
        if let Some(q) = query {
            url.push_str(&format!("&q={}", urlencoding::encode(&q)));
        }

        let response = self.client
            .get(&url)
            .header("Authorization", format!("Bearer {}", token))
            .send()
            .await
            .map_err(|e| format!("Drive API failed: {}", e))?;

        let body = response.text().await.map_err(|e| e.to_string())?;
        Ok(body)
    }

    pub async fn drive_download(
        &self,
        user_id: String,
        file_id: String,
    ) -> Result<String, String> {
        let token = self.get_token(&user_id).await?;

        let url = format!(
            "https://www.googleapis.com/drive/v3/files/{}?alt=media",
            file_id
        );

        let response = self.client
            .get(&url)
            .header("Authorization", format!("Bearer {}", token))
            .send()
            .await
            .map_err(|e| format!("Drive API failed: {}", e))?;

        let body = response.text().await.map_err(|e| e.to_string())?;
        Ok(body)
    }
}
