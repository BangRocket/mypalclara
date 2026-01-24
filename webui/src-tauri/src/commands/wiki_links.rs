use crate::db::Database;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::sync::LazyLock;
use tauri::State;

/// Matches [[title]] or [[title|display text]]
/// Uses [^\[\]|]+ to avoid catastrophic backtracking
static WIKI_LINK_REGEX: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\[\[(?P<title>[^\[\]|]+)(?:\|[^\[\]]*)?\]\]").unwrap()
});

/// Extract wiki link titles from content
/// Returns titles without the [[]] wrapper, trimmed
pub fn extract_wiki_links(content: &str) -> Vec<String> {
    WIKI_LINK_REGEX
        .captures_iter(content)
        .map(|cap| cap.name("title").unwrap().as_str().trim().to_string())
        .collect()
}

/// Extract wiki links from note content and save to wiki_links table
/// Returns the count of links saved
#[tauri::command]
#[specta::specta]
pub async fn extract_and_save_wiki_links(
    db: State<'_, Database>,
    note_id: i64,
    content: String,
) -> Result<i64, String> {
    // Extract all wiki link titles from content
    let titles = extract_wiki_links(&content);

    // Delete existing links for this source note
    sqlx::query("DELETE FROM wiki_links WHERE source_note_id = ?")
        .bind(note_id)
        .execute(&db.pool)
        .await
        .map_err(|e| e.to_string())?;

    let mut count = 0i64;

    for title in titles {
        // Look up target note by title (case-insensitive)
        let target: Option<(i64,)> = sqlx::query_as(
            "SELECT id FROM notes WHERE title = ? COLLATE NOCASE",
        )
        .bind(&title)
        .fetch_optional(&db.pool)
        .await
        .map_err(|e| e.to_string())?;

        let target_note_id = target.map(|(id,)| id);

        // Insert the wiki link (target_note_id may be NULL if note doesn't exist yet)
        sqlx::query(
            r#"
            INSERT INTO wiki_links (source_note_id, target_note_id, target_title)
            VALUES (?, ?, ?)
            "#,
        )
        .bind(note_id)
        .bind(target_note_id)
        .bind(&title)
        .execute(&db.pool)
        .await
        .map_err(|e| e.to_string())?;

        count += 1;
    }

    Ok(count)
}

/// Backlink information for UI display
#[derive(Debug, Clone, Serialize, Deserialize, specta::Type, sqlx::FromRow)]
pub struct Backlink {
    pub id: i64,
    pub title: String,
    pub updated_at: String,
}

/// Get all notes that link TO the given note
#[tauri::command]
#[specta::specta]
pub async fn get_backlinks(db: State<'_, Database>, note_id: i64) -> Result<Vec<Backlink>, String> {
    let backlinks = sqlx::query_as::<_, Backlink>(
        r#"
        SELECT n.id, n.title, n.updated_at
        FROM wiki_links wl
        JOIN notes n ON wl.source_note_id = n.id
        WHERE wl.target_note_id = ?
        ORDER BY n.updated_at DESC
        "#,
    )
    .bind(note_id)
    .fetch_all(&db.pool)
    .await
    .map_err(|e| e.to_string())?;

    Ok(backlinks)
}

/// Unlinked mention information with snippet context
#[derive(Debug, Clone, Serialize, Deserialize, specta::Type)]
pub struct UnlinkedMention {
    pub id: i64,
    pub title: String,
    pub snippet: String,
}

/// Helper to extract snippet around a mention
fn extract_snippet(content: &str, search_title: &str) -> Option<String> {
    let content_lower = content.to_lowercase();
    let title_lower = search_title.to_lowercase();

    if let Some(pos) = content_lower.find(&title_lower) {
        // Get ~50 chars before and after
        let start = pos.saturating_sub(50);
        let end = (pos + search_title.len() + 50).min(content.len());

        // Find word boundaries to avoid cutting words
        let start = content[..start]
            .rfind(char::is_whitespace)
            .map(|p| p + 1)
            .unwrap_or(start);
        let end = content[end..]
            .find(char::is_whitespace)
            .map(|p| end + p)
            .unwrap_or(end);

        let snippet = content[start..end].trim().to_string();

        // Add ellipsis if truncated
        let prefix = if start > 0 { "..." } else { "" };
        let suffix = if end < content.len() { "..." } else { "" };

        Some(format!("{}{}{}", prefix, snippet, suffix))
    } else {
        None
    }
}

/// Get notes that mention this note's title without a wiki link wrapper
#[tauri::command]
#[specta::specta]
pub async fn get_unlinked_mentions(
    db: State<'_, Database>,
    note_id: i64,
) -> Result<Vec<UnlinkedMention>, String> {
    // Get the current note's title
    let note_title: (String,) =
        sqlx::query_as("SELECT title FROM notes WHERE id = ?")
            .bind(note_id)
            .fetch_one(&db.pool)
            .await
            .map_err(|e| e.to_string())?;

    let title = note_title.0;

    // Skip very short titles to avoid false positives
    if title.len() < 3 {
        return Ok(vec![]);
    }

    // Query notes where content contains the title (case-insensitive)
    // but don't already have a wiki link to this note
    // Exclude the note itself
    #[derive(sqlx::FromRow)]
    struct PotentialMention {
        id: i64,
        title: String,
        content: String,
    }

    let candidates = sqlx::query_as::<_, PotentialMention>(
        r#"
        SELECT n.id, n.title, n.content
        FROM notes n
        WHERE n.id != ?
          AND n.content LIKE '%' || ? || '%' COLLATE NOCASE
          AND NOT EXISTS (
            SELECT 1 FROM wiki_links wl
            WHERE wl.source_note_id = n.id AND wl.target_note_id = ?
          )
        LIMIT 50
        "#,
    )
    .bind(note_id)
    .bind(&title)
    .bind(note_id)
    .fetch_all(&db.pool)
    .await
    .map_err(|e| e.to_string())?;

    // Filter and extract snippets
    let mentions: Vec<UnlinkedMention> = candidates
        .into_iter()
        .filter_map(|candidate| {
            // Double-check the match isn't inside a wiki link [[...]]
            let content = &candidate.content;
            let title_lower = title.to_lowercase();

            // Find all occurrences
            let content_lower = content.to_lowercase();
            if let Some(pos) = content_lower.find(&title_lower) {
                // Check if this position is inside [[...]]
                let before = &content[..pos];
                let _after = &content[pos..];

                // Simple check: count [[ before vs ]] before
                let open_brackets = before.matches("[[").count();
                let close_brackets = before.matches("]]").count();

                // If more open than close, we're inside a link - skip
                if open_brackets > close_brackets {
                    return None;
                }

                // Check if immediately preceded by [[ (within a few chars due to whitespace)
                if before.ends_with("[[") || before.trim_end().ends_with("[[") {
                    return None;
                }

                // Extract snippet
                if let Some(snippet) = extract_snippet(content, &title) {
                    return Some(UnlinkedMention {
                        id: candidate.id,
                        title: candidate.title,
                        snippet,
                    });
                }
            }

            None
        })
        .collect();

    Ok(mentions)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_simple_link() {
        let content = "Hello [[World]]";
        let links = extract_wiki_links(content);
        assert_eq!(links, vec!["World"]);
    }

    #[test]
    fn test_extract_link_with_display() {
        let content = "See [[Target|display text]] here";
        let links = extract_wiki_links(content);
        assert_eq!(links, vec!["Target"]);
    }

    #[test]
    fn test_extract_multiple_links() {
        let content = "Hello [[World]] and [[Test|display]] plus [[Another]]";
        let links = extract_wiki_links(content);
        assert_eq!(links, vec!["World", "Test", "Another"]);
    }

    #[test]
    fn test_extract_multi_word_title() {
        let content = "See [[Multi Word Title]] here";
        let links = extract_wiki_links(content);
        assert_eq!(links, vec!["Multi Word Title"]);
    }

    #[test]
    fn test_extract_trims_whitespace() {
        let content = "See [[ Padded Title ]] here";
        let links = extract_wiki_links(content);
        assert_eq!(links, vec!["Padded Title"]);
    }

    #[test]
    fn test_no_links() {
        let content = "No links here, just [brackets] and some text";
        let links = extract_wiki_links(content);
        assert!(links.is_empty());
    }

    #[test]
    fn test_snippet_extraction() {
        let content = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. The word Example appears here in the text. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam.";
        let snippet = extract_snippet(content, "Example").unwrap();
        assert!(snippet.contains("Example"));
        // Snippet should be shorter and contain ellipsis
        assert!(snippet.contains("..."));
    }
}
