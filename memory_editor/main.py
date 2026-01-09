"""Memory Editor - Web-based admin dashboard for mem0 memories.

A simple FastAPI service for viewing, editing, and managing memories
stored in PostgreSQL with pgvector.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuration
DATABASE_URL = os.getenv("MEM0_DATABASE_URL", "")
COLLECTION_NAME = os.getenv("MEM0_COLLECTION_NAME", "memories")
PORT = int(os.getenv("PORT", "8080"))

# Normalize database URL (Railway uses postgres://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Database setup
engine = None
SessionLocal = None

if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# FastAPI app
app = FastAPI(title="Memory Editor", description="Admin dashboard for mem0 memories")

# Templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


def get_db():
    """Get database session."""
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def format_datetime(dt) -> str:
    """Format datetime for display."""
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def truncate(text: str, length: int = 100) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""
    if len(text) <= length:
        return text
    return text[:length] + "..."


# Add template filters
templates.env.filters["format_datetime"] = format_datetime
templates.env.filters["truncate"] = truncate


# Health check
@app.get("/health")
def health():
    """Health check endpoint."""
    db_connected = False
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                db_connected = True
        except Exception:
            pass

    return {
        "status": "healthy" if db_connected else "degraded",
        "service": "memory-editor",
        "database_connected": db_connected,
    }


# Dashboard
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    """Dashboard with stats overview."""
    stats = get_stats()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "stats": stats},
    )


@app.get("/api/stats")
def get_stats():
    """Get memory statistics."""
    if not engine:
        return {"error": "Database not configured"}

    with engine.connect() as conn:
        # Total memories
        result = conn.execute(text(f"SELECT COUNT(*) FROM {COLLECTION_NAME}"))
        total_memories = result.scalar() or 0

        # Unique users
        result = conn.execute(
            text(f"SELECT COUNT(DISTINCT metadata->>'user_id') FROM {COLLECTION_NAME}")
        )
        unique_users = result.scalar() or 0

        # Recent memories (last 24h)
        result = conn.execute(
            text(
                f"""
                SELECT COUNT(*) FROM {COLLECTION_NAME}
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """
            )
        )
        recent_24h = result.scalar() or 0

        # Memories by source type
        result = conn.execute(
            text(
                f"""
                SELECT metadata->>'source_type' as source_type, COUNT(*) as count
                FROM {COLLECTION_NAME}
                GROUP BY metadata->>'source_type'
                ORDER BY count DESC
                LIMIT 10
            """
            )
        )
        by_source = [{"source_type": row[0] or "unknown", "count": row[1]} for row in result]

        # Top users by memory count
        result = conn.execute(
            text(
                f"""
                SELECT metadata->>'user_id' as user_id, COUNT(*) as count
                FROM {COLLECTION_NAME}
                GROUP BY metadata->>'user_id'
                ORDER BY count DESC
                LIMIT 10
            """
            )
        )
        top_users = [{"user_id": row[0] or "unknown", "count": row[1]} for row in result]

    return {
        "total_memories": total_memories,
        "unique_users": unique_users,
        "recent_24h": recent_24h,
        "by_source": by_source,
        "top_users": top_users,
    }


# Memories list
@app.get("/memories", response_class=HTMLResponse)
def list_memories(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    search: Optional[str] = None,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
):
    """List memories with pagination and filtering."""
    if not engine:
        return templates.TemplateResponse(
            "memories.html",
            {"request": request, "memories": [], "error": "Database not configured"},
        )

    offset = (page - 1) * per_page

    # Build query
    where_clauses = []
    params = {"limit": per_page, "offset": offset}

    if search:
        where_clauses.append("memory ILIKE :search")
        params["search"] = f"%{search}%"

    if user_id:
        where_clauses.append("metadata->>'user_id' = :user_id")
        params["user_id"] = user_id

    if project_id:
        where_clauses.append("metadata->>'project_id' = :project_id")
        params["project_id"] = project_id

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    with engine.connect() as conn:
        # Get total count
        count_result = conn.execute(
            text(f"SELECT COUNT(*) FROM {COLLECTION_NAME} WHERE {where_sql}"),
            params,
        )
        total = count_result.scalar() or 0

        # Get memories
        result = conn.execute(
            text(
                f"""
                SELECT id, memory, metadata, created_at, updated_at
                FROM {COLLECTION_NAME}
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """
            ),
            params,
        )

        memories = []
        for row in result:
            memories.append(
                {
                    "id": row[0],
                    "memory": row[1],
                    "metadata": row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}"),
                    "created_at": row[3],
                    "updated_at": row[4],
                }
            )

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse(
        "memories.html",
        {
            "request": request,
            "memories": memories,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "search": search or "",
            "user_id": user_id or "",
            "project_id": project_id or "",
        },
    )


# Single memory view/edit
@app.get("/memories/{memory_id}", response_class=HTMLResponse)
def view_memory(request: Request, memory_id: str):
    """View a single memory."""
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"""
                SELECT id, memory, hash, metadata, created_at, updated_at
                FROM {COLLECTION_NAME}
                WHERE id = :id
            """
            ),
            {"id": memory_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")

    memory = {
        "id": row[0],
        "memory": row[1],
        "hash": row[2],
        "metadata": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
        "created_at": row[4],
        "updated_at": row[5],
    }

    return templates.TemplateResponse(
        "memory.html",
        {"request": request, "memory": memory},
    )


@app.post("/memories/{memory_id}")
def update_memory(
    memory_id: str,
    memory_text: str = Form(...),
    metadata_json: str = Form(...),
):
    """Update a memory's text and metadata."""
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in metadata")

    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"""
                UPDATE {COLLECTION_NAME}
                SET memory = :memory, metadata = :metadata, updated_at = :updated_at
                WHERE id = :id
                RETURNING id
            """
            ),
            {
                "id": memory_id,
                "memory": memory_text,
                "metadata": json.dumps(metadata),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        conn.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Memory not found")

    return RedirectResponse(url=f"/memories/{memory_id}", status_code=303)


@app.delete("/memories/{memory_id}")
def delete_memory(memory_id: str):
    """Delete a single memory."""
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    with engine.connect() as conn:
        result = conn.execute(
            text(f"DELETE FROM {COLLECTION_NAME} WHERE id = :id RETURNING id"),
            {"id": memory_id},
        )
        conn.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Memory not found")

    return {"deleted": True, "id": memory_id}


@app.post("/memories/bulk-delete")
def bulk_delete_memories(
    user_id: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
    older_than_days: Optional[int] = Form(None),
):
    """Bulk delete memories matching criteria."""
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    where_clauses = []
    params = {}

    if user_id:
        where_clauses.append("metadata->>'user_id' = :user_id")
        params["user_id"] = user_id

    if project_id:
        where_clauses.append("metadata->>'project_id' = :project_id")
        params["project_id"] = project_id

    if older_than_days:
        where_clauses.append(f"created_at < NOW() - INTERVAL '{older_than_days} days'")

    if not where_clauses:
        raise HTTPException(status_code=400, detail="At least one filter required")

    where_sql = " AND ".join(where_clauses)

    with engine.connect() as conn:
        result = conn.execute(
            text(f"DELETE FROM {COLLECTION_NAME} WHERE {where_sql} RETURNING id"),
            params,
        )
        conn.commit()
        deleted_count = result.rowcount

    return RedirectResponse(url="/memories?deleted=" + str(deleted_count), status_code=303)


# Users
@app.get("/users", response_class=HTMLResponse)
def list_users(request: Request):
    """List all users with memory counts."""
    if not engine:
        return templates.TemplateResponse(
            "users.html",
            {"request": request, "users": [], "error": "Database not configured"},
        )

    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"""
                SELECT
                    metadata->>'user_id' as user_id,
                    COUNT(*) as memory_count,
                    MIN(created_at) as first_memory,
                    MAX(created_at) as last_memory
                FROM {COLLECTION_NAME}
                WHERE metadata->>'user_id' IS NOT NULL
                GROUP BY metadata->>'user_id'
                ORDER BY memory_count DESC
            """
            )
        )

        users = []
        for row in result:
            users.append(
                {
                    "user_id": row[0],
                    "memory_count": row[1],
                    "first_memory": row[2],
                    "last_memory": row[3],
                }
            )

    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": users},
    )


@app.get("/users/{user_id}", response_class=HTMLResponse)
def view_user(request: Request, user_id: str):
    """View a user's memories."""
    return RedirectResponse(url=f"/memories?user_id={user_id}", status_code=303)


@app.delete("/users/{user_id}")
def delete_user_memories(user_id: str):
    """Delete all memories for a user."""
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"DELETE FROM {COLLECTION_NAME} WHERE metadata->>'user_id' = :user_id RETURNING id"
            ),
            {"user_id": user_id},
        )
        conn.commit()
        deleted_count = result.rowcount

    return {"deleted": True, "user_id": user_id, "count": deleted_count}


if __name__ == "__main__":
    import uvicorn

    print(f"[memory-editor] Starting on port {PORT}")
    print(f"[memory-editor] Database: {'configured' if DATABASE_URL else 'NOT CONFIGURED'}")
    print(f"[memory-editor] Collection: {COLLECTION_NAME}")

    uvicorn.run(app, host="0.0.0.0", port=PORT)
