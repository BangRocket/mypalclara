# MyPalClara Web

A web-based version of MyPalClara - your AI companion with persistent memory.

## Features

- Chat with Clara in your browser
- Memories stored locally in your browser (privacy-first)
- Export/import your memories
- Bring your own API key

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set your API key:
```bash
export ANTHROPIC_API_KEY=your-key-here
```

3. Run the server:
```bash
python app.py
```

4. Open http://localhost:8000

## Architecture

- Backend: FastAPI (proxies Anthropic API calls)
- Frontend: Vanilla JS (lightweight, no build step)
- Storage: Browser localStorage (your memories never leave your device)

## Privacy

Your memories are stored in your browser's localStorage. The server only proxies
API calls to Anthropic - it never sees or stores your conversation history or memories.
