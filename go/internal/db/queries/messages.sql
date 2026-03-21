-- name: GetRecentMessages :many
SELECT * FROM messages
WHERE session_id = ?
ORDER BY created_at DESC
LIMIT ?;

-- name: CreateMessage :one
INSERT INTO messages (session_id, user_id, role, content, created_at)
VALUES (?, ?, ?, ?, ?)
RETURNING *;

-- name: GetChannelMessages :many
SELECT m.* FROM messages m
JOIN sessions s ON m.session_id = s.id
WHERE s.context_id = ?
ORDER BY m.created_at DESC
LIMIT ?;
