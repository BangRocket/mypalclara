"""
Browser Faculty - Web search and browser automation.

Combines Tavily web search (via official SDK) with Playwright browser
automation for comprehensive web interaction capabilities.

https://github.com/tavily-ai/tavily-python
https://github.com/microsoft/playwright-python
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Optional

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)

# Configuration
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
BROWSER_SESSIONS_DIR = Path(os.getenv("BROWSER_SESSIONS_DIR", "./data/browser_sessions"))
SESSION_IDLE_TIMEOUT = int(os.getenv("BROWSER_SESSION_IDLE_MINUTES", "30")) * 60

# Thread pool for sync SDK calls
_executor = ThreadPoolExecutor(max_workers=2)


class BrowserFaculty(Faculty):
    """Web search and browser automation faculty."""

    name = "browser"
    description = "Web search via Tavily and browser automation via Playwright"

    available_actions = [
        # Web Search (Tavily)
        "web_search",
        "search_context",
        "qna_search",
        "extract_urls",
        # Stateless Browser (Playwright)
        "browse_page",
        "screenshot_page",
        "extract_page_data",
        # Session-based Browser
        "create_session",
        "navigate",
        "click",
        "type_text",
        "screenshot_session",
        "extract_session",
        "scroll",
        "wait_for",
        "get_page_info",
        "close_session",
        "list_sessions",
    ]

    def __init__(self):
        self._browser = None
        self._sessions: dict[str, dict] = {}  # session_id -> {context, page, last_used}
        self._playwright = None
        self._tavily = None

    def _get_tavily(self):
        """Get or create the Tavily client."""
        if self._tavily is None:
            if not TAVILY_API_KEY:
                raise ValueError("TAVILY_API_KEY not set")
            from tavily import TavilyClient
            self._tavily = TavilyClient(api_key=TAVILY_API_KEY)
        return self._tavily

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, partial(func, *args, **kwargs))

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """Execute browser/search intent."""
        logger.info(f"[browser] Intent: {intent}")

        try:
            # Parse intent to determine action
            action, params = self._parse_intent(intent)
            logger.info(f"[browser] Action: {action}, Params: {params}")

            # Web Search (Tavily)
            if action == "web_search":
                result = await self._web_search(params)
            elif action == "search_context":
                result = await self._search_context(params)
            elif action == "qna_search":
                result = await self._qna_search(params)
            elif action == "extract_urls":
                result = await self._extract_urls(params)
            # Stateless Browser (Playwright)
            elif action == "browse_page":
                result = await self._browse_page(params)
            elif action == "screenshot_page":
                result = await self._screenshot_page(params)
            elif action == "extract_page_data":
                result = await self._extract_page_data(params)
            # Session-based Browser
            elif action == "create_session":
                result = await self._create_session(params)
            elif action == "navigate":
                result = await self._session_navigate(params)
            elif action == "click":
                result = await self._session_click(params)
            elif action == "type_text":
                result = await self._session_type(params)
            elif action == "screenshot_session":
                result = await self._session_screenshot(params)
            elif action == "extract_session":
                result = await self._session_extract(params)
            elif action == "scroll":
                result = await self._session_scroll(params)
            elif action == "wait_for":
                result = await self._session_wait_for(params)
            elif action == "get_page_info":
                result = await self._session_page_info(params)
            elif action == "close_session":
                result = await self._close_session(params)
            elif action == "list_sessions":
                result = self._list_sessions()
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Unknown browser action: {action}",
                    error=f"Action '{action}' not recognized",
                )

            return result

        except Exception as e:
            logger.exception(f"[browser] Error: {e}")
            return FacultyResult(
                success=False,
                summary=f"Browser error: {str(e)}",
                error=str(e),
            )

    def _parse_intent(self, intent: str) -> tuple[str, dict]:
        """Parse natural language intent into action and parameters."""
        intent_lower = intent.lower()

        # QnA search patterns (direct answer)
        if any(phrase in intent_lower for phrase in ["answer", "what is", "who is", "when did", "how do"]):
            query = intent
            for prefix in ["answer", "tell me"]:
                if intent_lower.startswith(prefix):
                    query = intent[len(prefix):].strip()
                    break
            return "qna_search", {"query": query}

        # Context search (for RAG)
        if "context" in intent_lower or "rag" in intent_lower:
            query = self._extract_query(intent)
            return "search_context", {"query": query}

        # Extract from URLs
        if "extract" in intent_lower and "url" in intent_lower:
            urls = self._extract_urls_from_text(intent)
            return "extract_urls", {"urls": urls}

        # Web search patterns
        if any(word in intent_lower for word in ["search", "find", "look up", "google"]):
            query = intent
            for prefix in ["search for", "search", "find", "look up", "google"]:
                if intent_lower.startswith(prefix):
                    query = intent[len(prefix):].strip()
                    break
            return "web_search", {"query": query}

        # Browse/visit page
        if any(word in intent_lower for word in ["browse", "visit", "go to", "open", "navigate to"]):
            url = self._extract_url(intent)
            if url:
                return "browse_page", {"url": url}

        # Screenshot
        if "screenshot" in intent_lower:
            url = self._extract_url(intent)
            session = self._extract_session_name(intent)
            if session:
                return "screenshot_session", {"session": session}
            elif url:
                return "screenshot_page", {"url": url}

        # Session management
        if any(phrase in intent_lower for phrase in ["create session", "start session", "new session"]):
            session = self._extract_session_name(intent) or "default"
            url = self._extract_url(intent)
            return "create_session", {"session": session, "url": url}

        if any(phrase in intent_lower for phrase in ["close session", "end session"]):
            session = self._extract_session_name(intent) or "default"
            return "close_session", {"session": session}

        if "list sessions" in intent_lower:
            return "list_sessions", {}

        # Session actions
        if "click" in intent_lower:
            selector = self._extract_selector(intent)
            session = self._extract_session_name(intent) or "default"
            return "click", {"session": session, "selector": selector}

        if any(word in intent_lower for word in ["type", "enter", "input"]):
            text = self._extract_text_to_type(intent)
            selector = self._extract_selector(intent)
            session = self._extract_session_name(intent) or "default"
            return "type_text", {"session": session, "selector": selector, "text": text}

        if "scroll" in intent_lower:
            session = self._extract_session_name(intent) or "default"
            direction = "down" if "down" in intent_lower else "up" if "up" in intent_lower else "down"
            return "scroll", {"session": session, "direction": direction}

        if "wait" in intent_lower:
            selector = self._extract_selector(intent)
            session = self._extract_session_name(intent) or "default"
            return "wait_for", {"session": session, "selector": selector}

        if "extract" in intent_lower:
            selector = self._extract_selector(intent)
            session = self._extract_session_name(intent) or "default"
            url = self._extract_url(intent)
            if session in self._sessions:
                return "extract_session", {"session": session, "selector": selector}
            elif url:
                return "extract_page_data", {"url": url, "selector": selector}

        # Default to web search
        return "web_search", {"query": intent}

    def _extract_query(self, text: str) -> str:
        """Extract search query from text."""
        import re
        match = re.search(r'(?:for|about|on)\s+["\']?(.+?)["\']?$', text, re.IGNORECASE)
        if match:
            return match.group(1)
        return text

    def _extract_url(self, text: str) -> Optional[str]:
        """Extract URL from text."""
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        match = re.search(url_pattern, text)
        if match:
            return match.group(0)

        domain_pattern = r'\b([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}\b'
        match = re.search(domain_pattern, text)
        if match:
            return f"https://{match.group(0)}"

        return None

    def _extract_urls_from_text(self, text: str) -> list[str]:
        """Extract multiple URLs from text."""
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        return re.findall(url_pattern, text)

    def _extract_session_name(self, text: str) -> Optional[str]:
        """Extract session name from text."""
        import re
        match = re.search(r"session\s+['\"]?(\w+)['\"]?", text.lower())
        if match:
            return match.group(1)
        return None

    def _extract_selector(self, text: str) -> Optional[str]:
        """Extract CSS selector from text."""
        import re
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
        match = re.search(r'(?:click|on)\s+(?:the\s+)?["\']?(.+?)["\']?(?:\s+button|\s+link)?$', text.lower())
        if match:
            return f"text={match.group(1)}"
        return None

    def _extract_text_to_type(self, text: str) -> str:
        """Extract text to type from intent."""
        import re
        match = re.search(r'(?:type|enter|input)\s+["\'](.+?)["\']', text)
        if match:
            return match.group(1)
        return ""

    # ==========================================================================
    # Web Search (Tavily SDK)
    # ==========================================================================

    async def _web_search(self, params: dict) -> FacultyResult:
        """Search the web using Tavily SDK."""
        query = params.get("query", "")
        if not query:
            return FacultyResult(success=False, summary="No search query provided", error="Missing query")

        if not TAVILY_API_KEY:
            return FacultyResult(
                success=False,
                summary="Web search not configured",
                error="TAVILY_API_KEY not set",
            )

        max_results = params.get("max_results", 5)
        search_depth = params.get("search_depth", "basic")
        include_answer = params.get("include_answer", True)

        def _search():
            client = self._get_tavily()
            return client.search(
                query=query,
                search_depth=search_depth,
                include_answer=include_answer,
                max_results=max_results,
            )

        data = await self._run_sync(_search)

        # Format results
        results = []
        answer = data.get("answer", "")

        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500],
                "score": r.get("score"),
            })

        summary_parts = []
        if answer:
            summary_parts.append(f"**Summary:** {answer}")
        summary_parts.append(f"Found {len(results)} results for '{query}'")

        for r in results[:3]:
            summary_parts.append(f"- [{r['title']}]({r['url']})")

        return FacultyResult(
            success=True,
            summary="\n".join(summary_parts),
            data={"answer": answer, "results": results, "query": query},
        )

    async def _search_context(self, params: dict) -> FacultyResult:
        """Get search context for RAG using Tavily SDK."""
        query = params.get("query", "")
        if not query:
            return FacultyResult(success=False, summary="No query provided", error="Missing query")

        if not TAVILY_API_KEY:
            return FacultyResult(success=False, summary="Web search not configured", error="TAVILY_API_KEY not set")

        max_tokens = params.get("max_tokens", 4000)
        search_depth = params.get("search_depth", "advanced")

        def _get_context():
            client = self._get_tavily()
            return client.get_search_context(
                query=query,
                search_depth=search_depth,
                max_tokens=max_tokens,
            )

        context = await self._run_sync(_get_context)

        return FacultyResult(
            success=True,
            summary=f"Generated context for '{query}' ({len(context)} chars)",
            data={"context": context, "query": query},
        )

    async def _qna_search(self, params: dict) -> FacultyResult:
        """Get a direct answer to a question using Tavily SDK."""
        query = params.get("query", "")
        if not query:
            return FacultyResult(success=False, summary="No question provided", error="Missing query")

        if not TAVILY_API_KEY:
            return FacultyResult(success=False, summary="Web search not configured", error="TAVILY_API_KEY not set")

        search_depth = params.get("search_depth", "advanced")

        def _qna():
            client = self._get_tavily()
            return client.qna_search(query=query, search_depth=search_depth)

        answer = await self._run_sync(_qna)

        return FacultyResult(
            success=True,
            summary=f"**Answer:** {answer}",
            data={"answer": answer, "query": query},
        )

    async def _extract_urls(self, params: dict) -> FacultyResult:
        """Extract content from multiple URLs using Tavily SDK."""
        urls = params.get("urls", [])
        if not urls:
            return FacultyResult(success=False, summary="No URLs provided", error="Missing urls")

        if not TAVILY_API_KEY:
            return FacultyResult(success=False, summary="Web search not configured", error="TAVILY_API_KEY not set")

        # Limit to 20 URLs (Tavily limit)
        urls = urls[:20]

        def _extract():
            client = self._get_tavily()
            return client.extract(urls=urls)

        result = await self._run_sync(_extract)

        extracted = []
        for r in result.get("results", []):
            extracted.append({
                "url": r.get("url", ""),
                "raw_content": r.get("raw_content", "")[:2000],
            })

        failed = result.get("failed_results", [])

        summary = f"Extracted content from {len(extracted)} URL(s)"
        if failed:
            summary += f" ({len(failed)} failed)"

        return FacultyResult(
            success=True,
            summary=summary,
            data={"extracted": extracted, "failed": failed},
        )

    # ==========================================================================
    # Stateless Browser Operations (Playwright)
    # ==========================================================================

    async def _get_browser(self):
        """Get or create the Playwright browser instance."""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
                logger.info("[browser] Playwright browser launched")
            except ImportError:
                raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return self._browser

    async def _browse_page(self, params: dict) -> FacultyResult:
        """Navigate to a URL and extract text content."""
        url = params.get("url", "")
        if not url:
            return FacultyResult(success=False, summary="No URL provided", error="Missing url")

        browser = await self._get_browser()
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=10000)

            title = await page.title()
            content = await page.inner_text("body")
            content = content[:5000]  # Limit content size

            return FacultyResult(
                success=True,
                summary=f"Loaded '{title}' from {url}\n\nContent preview:\n{content[:500]}...",
                data={"url": url, "title": title, "content": content},
            )
        finally:
            await context.close()

    async def _screenshot_page(self, params: dict) -> FacultyResult:
        """Take a screenshot of a webpage."""
        url = params.get("url", "")
        if not url:
            return FacultyResult(success=False, summary="No URL provided", error="Missing url")

        browser = await self._get_browser()
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=10000)

            # Save screenshot
            BROWSER_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            filename = f"screenshot_{timestamp}.png"
            filepath = BROWSER_SESSIONS_DIR / filename

            await page.screenshot(path=str(filepath), full_page=False)

            return FacultyResult(
                success=True,
                summary=f"Screenshot saved to {filepath}",
                data={"path": str(filepath), "url": url},
            )
        finally:
            await context.close()

    async def _extract_page_data(self, params: dict) -> FacultyResult:
        """Extract data from a page using CSS selectors."""
        url = params.get("url", "")
        selector = params.get("selector", "body")

        if not url:
            return FacultyResult(success=False, summary="No URL provided", error="Missing url")

        browser = await self._get_browser()
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=10000)

            elements = await page.query_selector_all(selector)
            extracted = []
            for el in elements[:20]:  # Limit to 20 elements
                text = await el.inner_text()
                extracted.append(text.strip()[:500])

            return FacultyResult(
                success=True,
                summary=f"Extracted {len(extracted)} elements matching '{selector}'",
                data={"selector": selector, "elements": extracted},
            )
        finally:
            await context.close()

    # ==========================================================================
    # Session-based Browser Operations (Playwright)
    # ==========================================================================

    async def _create_session(self, params: dict) -> FacultyResult:
        """Create or restore a named browser session."""
        session_name = params.get("session", "default")
        url = params.get("url")

        browser = await self._get_browser()

        # Check for existing session
        if session_name in self._sessions:
            session = self._sessions[session_name]
            session["last_used"] = time.time()
            return FacultyResult(
                success=True,
                summary=f"Session '{session_name}' already exists and is active",
                data={"session": session_name, "restored": True},
            )

        # Create new context and page
        context = await browser.new_context()
        page = await context.new_page()

        self._sessions[session_name] = {
            "context": context,
            "page": page,
            "last_used": time.time(),
        }

        if url:
            await page.goto(url, timeout=30000)
            title = await page.title()
            return FacultyResult(
                success=True,
                summary=f"Session '{session_name}' created and navigated to {title}",
                data={"session": session_name, "url": url, "title": title},
            )

        return FacultyResult(
            success=True,
            summary=f"Session '{session_name}' created",
            data={"session": session_name},
        )

    async def _session_navigate(self, params: dict) -> FacultyResult:
        """Navigate to URL in session."""
        session_name = params.get("session", "default")
        url = params.get("url", "")

        if session_name not in self._sessions:
            return FacultyResult(
                success=False,
                summary=f"Session '{session_name}' not found",
                error="Session not found",
            )

        session = self._sessions[session_name]
        session["last_used"] = time.time()
        page = session["page"]

        await page.goto(url, timeout=30000)
        title = await page.title()

        return FacultyResult(
            success=True,
            summary=f"Navigated to '{title}'",
            data={"url": url, "title": title},
        )

    async def _session_click(self, params: dict) -> FacultyResult:
        """Click an element in session."""
        session_name = params.get("session", "default")
        selector = params.get("selector", "")

        if session_name not in self._sessions:
            return FacultyResult(success=False, summary=f"Session '{session_name}' not found", error="Session not found")

        if not selector:
            return FacultyResult(success=False, summary="No selector provided", error="Missing selector")

        session = self._sessions[session_name]
        session["last_used"] = time.time()
        page = session["page"]

        await page.click(selector, timeout=10000)

        return FacultyResult(
            success=True,
            summary=f"Clicked '{selector}'",
            data={"selector": selector},
        )

    async def _session_type(self, params: dict) -> FacultyResult:
        """Type text into an element in session."""
        session_name = params.get("session", "default")
        selector = params.get("selector", "")
        text = params.get("text", "")

        if session_name not in self._sessions:
            return FacultyResult(success=False, summary=f"Session '{session_name}' not found", error="Session not found")

        session = self._sessions[session_name]
        session["last_used"] = time.time()
        page = session["page"]

        if selector:
            await page.fill(selector, text, timeout=10000)
        else:
            await page.keyboard.type(text)

        return FacultyResult(
            success=True,
            summary=f"Typed text into {'element' if selector else 'page'}",
            data={"selector": selector, "text_length": len(text)},
        )

    async def _session_screenshot(self, params: dict) -> FacultyResult:
        """Take screenshot in session."""
        session_name = params.get("session", "default")

        if session_name not in self._sessions:
            return FacultyResult(success=False, summary=f"Session '{session_name}' not found", error="Session not found")

        session = self._sessions[session_name]
        session["last_used"] = time.time()
        page = session["page"]

        BROWSER_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())
        filename = f"{session_name}_{timestamp}.png"
        filepath = BROWSER_SESSIONS_DIR / filename

        await page.screenshot(path=str(filepath))

        return FacultyResult(
            success=True,
            summary=f"Screenshot saved to {filepath}",
            data={"path": str(filepath)},
        )

    async def _session_extract(self, params: dict) -> FacultyResult:
        """Extract content from session page."""
        session_name = params.get("session", "default")
        selector = params.get("selector", "body")

        if session_name not in self._sessions:
            return FacultyResult(success=False, summary=f"Session '{session_name}' not found", error="Session not found")

        session = self._sessions[session_name]
        session["last_used"] = time.time()
        page = session["page"]

        elements = await page.query_selector_all(selector)
        extracted = []
        for el in elements[:20]:
            text = await el.inner_text()
            extracted.append(text.strip()[:500])

        return FacultyResult(
            success=True,
            summary=f"Extracted {len(extracted)} elements",
            data={"selector": selector, "elements": extracted},
        )

    async def _session_scroll(self, params: dict) -> FacultyResult:
        """Scroll in session."""
        session_name = params.get("session", "default")
        direction = params.get("direction", "down")
        amount = params.get("amount", 500)

        if session_name not in self._sessions:
            return FacultyResult(success=False, summary=f"Session '{session_name}' not found", error="Session not found")

        session = self._sessions[session_name]
        session["last_used"] = time.time()
        page = session["page"]

        delta = amount if direction == "down" else -amount
        await page.mouse.wheel(0, delta)

        return FacultyResult(
            success=True,
            summary=f"Scrolled {direction} {amount}px",
            data={"direction": direction, "amount": amount},
        )

    async def _session_wait_for(self, params: dict) -> FacultyResult:
        """Wait for element in session."""
        session_name = params.get("session", "default")
        selector = params.get("selector", "")
        timeout = params.get("timeout", 10000)

        if session_name not in self._sessions:
            return FacultyResult(success=False, summary=f"Session '{session_name}' not found", error="Session not found")

        if not selector:
            return FacultyResult(success=False, summary="No selector provided", error="Missing selector")

        session = self._sessions[session_name]
        session["last_used"] = time.time()
        page = session["page"]

        await page.wait_for_selector(selector, timeout=timeout)

        return FacultyResult(
            success=True,
            summary=f"Element '{selector}' found",
            data={"selector": selector},
        )

    async def _session_page_info(self, params: dict) -> FacultyResult:
        """Get info about current page in session."""
        session_name = params.get("session", "default")

        if session_name not in self._sessions:
            return FacultyResult(success=False, summary=f"Session '{session_name}' not found", error="Session not found")

        session = self._sessions[session_name]
        session["last_used"] = time.time()
        page = session["page"]

        title = await page.title()
        url = page.url

        return FacultyResult(
            success=True,
            summary=f"Page: '{title}' at {url}",
            data={"title": title, "url": url},
        )

    async def _close_session(self, params: dict) -> FacultyResult:
        """Close a browser session."""
        session_name = params.get("session", "default")

        if session_name not in self._sessions:
            return FacultyResult(
                success=False,
                summary=f"Session '{session_name}' not found",
                error="Session not found",
            )

        session = self._sessions.pop(session_name)
        await session["context"].close()

        return FacultyResult(
            success=True,
            summary=f"Session '{session_name}' closed",
            data={"session": session_name},
        )

    def _list_sessions(self) -> FacultyResult:
        """List active browser sessions."""
        sessions = []
        for name, session in self._sessions.items():
            sessions.append({
                "name": name,
                "last_used": session["last_used"],
                "idle_seconds": int(time.time() - session["last_used"]),
            })

        if not sessions:
            return FacultyResult(
                success=True,
                summary="No active browser sessions",
                data={"sessions": []},
            )

        return FacultyResult(
            success=True,
            summary=f"Active sessions: {', '.join(s['name'] for s in sessions)}",
            data={"sessions": sessions},
        )

    async def cleanup(self):
        """Cleanup browser resources."""
        for session in self._sessions.values():
            try:
                await session["context"].close()
            except Exception:
                pass
        self._sessions.clear()

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        logger.info("[browser] Resources cleaned up")
