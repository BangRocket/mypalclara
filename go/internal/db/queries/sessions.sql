-- name: GetSession :one
SELECT * FROM sessions WHERE id = ? LIMIT 1;

-- name: GetActiveSession :one
SELECT * FROM sessions
WHERE user_id = ?
  AND context_id = ?
  AND project_id = ?
  AND archived != 'true'
ORDER BY last_activity_at DESC
LIMIT 1;

-- name: CreateSession :one
INSERT INTO sessions (id, project_id, user_id, context_id, title, archived, started_at, last_activity_at, previous_session_id, context_snapshot, session_summary)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
RETURNING *;

-- name: UpdateSessionActivity :exec
UPDATE sessions SET last_activity_at = ? WHERE id = ?;

-- name: SetSessionSummary :exec
UPDATE sessions SET session_summary = ? WHERE id = ?;
