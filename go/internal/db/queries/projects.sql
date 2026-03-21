-- name: GetProject :one
SELECT * FROM projects WHERE id = ? LIMIT 1;

-- name: GetProjectByOwner :one
SELECT * FROM projects WHERE owner_id = ? LIMIT 1;

-- name: CreateProject :one
INSERT INTO projects (id, owner_id, name, created_at, updated_at)
VALUES (?, ?, ?, ?, ?)
RETURNING *;
