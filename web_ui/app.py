"""
MyPalClara Web - FastAPI Backend
A lightweight proxy for Anthropic API calls with optional server-side key
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="MyPalClara", version="1.0.0")

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    system_prompt: str
    max_tokens: int = 1024
    model: str = "claude-sonnet-4-20250514"


class ChatResponse(BaseModel):
    content: str
    usage: Optional[Dict[str, int]] = None


class MemoryExtractionRequest(BaseModel):
    user_message: str
    assistant_response: str


class ExtractedMemories(BaseModel):
    facts: List[str] = []
    preferences: List[str] = []
    experiences: List[str] = []
    relationships: List[str] = []
    context: List[str] = []


def get_client(api_key: Optional[str] = None) -> Anthropic:
    """Get Anthropic client with provided key or server default."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(
            status_code=401,
            detail="No API key provided. Set ANTHROPIC_API_KEY or pass via header."
        )
    return Anthropic(api_key=key)


@app.get("/")
async def root():
    """Serve the main page."""
    return FileResponse("templates/index.html")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/config")
async def get_config():
    """Return client configuration."""
    return {
        "has_server_key": bool(os.getenv("ANTHROPIC_API_KEY")),
        "default_model": "claude-sonnet-4-20250514",
        "version": "1.0.0"
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Send a message to Clara and get a response.
    Optionally provide your own API key via X-API-Key header.
    """
    client = get_client(x_api_key)

    try:
        response = client.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            system=request.system_prompt,
            messages=[{"role": m.role, "content": m.content} for m in request.messages]
        )

        return ChatResponse(
            content=response.content[0].text,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extract-memories", response_model=ExtractedMemories)
async def extract_memories(
    request: MemoryExtractionRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Extract memorable information from a conversation exchange.
    """
    client = get_client(x_api_key)

    extraction_prompt = f"""Based on this exchange, extract any new information worth remembering about the user.

User said: {request.user_message}
Assistant responded: {request.assistant_response}

Return a JSON object with these fields (only include fields with actual new information):
- facts: list of factual information about the user (name, job, location, etc.)
- preferences: list of likes/dislikes/preferences
- experiences: list of experiences or events they mentioned
- relationships: list of people mentioned and their relation to user
- context: any ongoing situations or temporary context

Return ONLY valid JSON. If nothing worth remembering, return {{}}.
Example: {{"facts": ["Works as a software engineer"], "preferences": ["Loves coffee"]}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": extraction_prompt}]
        )

        import json
        try:
            # Try to parse the response as JSON
            text = response.content[0].text.strip()
            # Handle markdown code blocks
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            memories = json.loads(text)
            return ExtractedMemories(**memories)
        except (json.JSONDecodeError, TypeError):
            return ExtractedMemories()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
