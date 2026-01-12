"""
Browser Faculty - Web search and browser automation.

Combines Tavily web search (via official SDK) with agent-browser
for AI-optimized browser automation using accessibility tree refs.

https://github.com/tavily-ai/tavily-python
https://github.com/vercel-labs/agent-browser
"""

import asyncio
import json
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Optional

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)

# Configuration
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Thread pool for sync SDK calls
_executor = ThreadPoolExecutor(max_workers=2)


def _agent_browser_available() -> bool:
    """Check if agent-browser CLI is installed."""
    return shutil.which("agent-browser") is not None


class BrowserFaculty(Faculty):
    """Web search and browser automation faculty."""

    name = "browser"
    description = "Web search via Tavily and browser automation via agent-browser"

    available_actions = [
        # Web Search (Tavily)
        "web_search",
        "search_context",
        "qna_search",
        "extract_urls",
        # Browser (agent-browser)
        "browse",
        "snapshot",
        "click",
        "type",
        "scroll",
        "screenshot",
        "pdf",
    ]

    def __init__(self):
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

    async def _run_agent_browser(self, *args, timeout: int = 30) -> dict:
        """Run agent-browser CLI command and return JSON output."""
        if not _agent_browser_available():
            raise RuntimeError(
                "agent-browser not installed. Run: npm install -g agent-browser && agent-browser install"
            )

        cmd = ["agent-browser", "--json", *args]
        logger.info(f"[browser] Running: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError(f"agent-browser timed out after {timeout}s")

        if proc.returncode != 0:
            error = stderr.decode().strip() if stderr else "Unknown error"
            raise RuntimeError(f"agent-browser failed: {error}")

        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError:
            # Return raw output if not JSON
            return {"raw": stdout.decode().strip()}

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
            # Browser (agent-browser)
            elif action == "browse":
                result = await self._browse(params)
            elif action == "snapshot":
                result = await self._snapshot(params)
            elif action == "click":
                result = await self._click(params)
            elif action == "type":
                result = await self._type(params)
            elif action == "scroll":
                result = await self._scroll(params)
            elif action == "screenshot":
                result = await self._screenshot(params)
            elif action == "pdf":
                result = await self._pdf(params)
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

        # Snapshot (get interactive elements)
        if "snapshot" in intent_lower or "elements" in intent_lower or "interactive" in intent_lower:
            url = self._extract_url(intent)
            return "snapshot", {"url": url}

        # Screenshot
        if "screenshot" in intent_lower:
            url = self._extract_url(intent)
            return "screenshot", {"url": url}

        # PDF
        if "pdf" in intent_lower:
            url = self._extract_url(intent)
            return "pdf", {"url": url}

        # Click (using ref like @e1)
        if "click" in intent_lower:
            ref = self._extract_ref(intent)
            selector = self._extract_selector(intent) if not ref else None
            return "click", {"ref": ref, "selector": selector}

        # Type
        if any(word in intent_lower for word in ["type", "enter", "input", "fill"]):
            ref = self._extract_ref(intent)
            selector = self._extract_selector(intent) if not ref else None
            text = self._extract_text_to_type(intent)
            return "type", {"ref": ref, "selector": selector, "text": text}

        # Scroll
        if "scroll" in intent_lower:
            direction = "down" if "down" in intent_lower else "up" if "up" in intent_lower else "down"
            return "scroll", {"direction": direction}

        # Browse/visit page (default for URLs)
        url = self._extract_url(intent)
        if url:
            return "browse", {"url": url}

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

    def _extract_ref(self, text: str) -> Optional[str]:
        """Extract agent-browser ref (e.g., @e1, @e2) from text."""
        import re
        match = re.search(r'@e\d+', text)
        if match:
            return match.group(0)
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
        match = re.search(r'(?:type|enter|input|fill)\s+["\'](.+?)["\']', text)
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
    # Browser Operations (agent-browser CLI)
    # ==========================================================================

    async def _browse(self, params: dict) -> FacultyResult:
        """Navigate to a URL and get page content."""
        url = params.get("url", "")
        if not url:
            return FacultyResult(success=False, summary="No URL provided", error="Missing url")

        try:
            # Navigate and get snapshot with interactive elements
            result = await self._run_agent_browser("navigate", url, timeout=60)

            # Get text content
            text_result = await self._run_agent_browser("text", timeout=30)
            content = text_result.get("text", text_result.get("raw", ""))[:5000]

            return FacultyResult(
                success=True,
                summary=f"Loaded page: {url}\n\nContent preview:\n{content[:1000]}...",
                data={"url": url, "content": content},
            )
        except Exception as e:
            return FacultyResult(
                success=False,
                summary=f"Failed to browse {url}: {e}",
                error=str(e),
            )

    async def _snapshot(self, params: dict) -> FacultyResult:
        """Get interactive elements snapshot with refs for clicking/typing."""
        url = params.get("url")

        try:
            if url:
                await self._run_agent_browser("navigate", url, timeout=60)

            # Get accessibility tree snapshot with refs
            result = await self._run_agent_browser("snapshot", timeout=30)

            # Format for Clara
            elements = result.get("elements", [])
            if not elements and "raw" in result:
                # Parse raw output if not JSON
                return FacultyResult(
                    success=True,
                    summary=f"Page snapshot:\n{result['raw'][:3000]}",
                    data=result,
                )

            # Format elements nicely
            formatted = []
            for el in elements[:50]:  # Limit to 50 elements
                ref = el.get("ref", "")
                role = el.get("role", "")
                name = el.get("name", "")
                formatted.append(f"{ref}: [{role}] {name}")

            summary = f"Found {len(elements)} interactive elements:\n" + "\n".join(formatted[:20])
            if len(elements) > 20:
                summary += f"\n... and {len(elements) - 20} more"

            return FacultyResult(
                success=True,
                summary=summary,
                data={"elements": elements, "url": url},
            )
        except Exception as e:
            return FacultyResult(
                success=False,
                summary=f"Failed to get snapshot: {e}",
                error=str(e),
            )

    async def _click(self, params: dict) -> FacultyResult:
        """Click an element using ref or selector."""
        ref = params.get("ref")
        selector = params.get("selector")

        if not ref and not selector:
            return FacultyResult(
                success=False,
                summary="No element specified. Use ref (e.g., @e1) or selector.",
                error="Missing ref or selector",
            )

        try:
            target = ref if ref else selector
            await self._run_agent_browser("click", target, timeout=30)

            return FacultyResult(
                success=True,
                summary=f"Clicked {target}",
                data={"target": target},
            )
        except Exception as e:
            return FacultyResult(
                success=False,
                summary=f"Failed to click: {e}",
                error=str(e),
            )

    async def _type(self, params: dict) -> FacultyResult:
        """Type text into an element."""
        ref = params.get("ref")
        selector = params.get("selector")
        text = params.get("text", "")

        if not text:
            return FacultyResult(success=False, summary="No text to type", error="Missing text")

        try:
            if ref or selector:
                target = ref if ref else selector
                await self._run_agent_browser("fill", target, text, timeout=30)
            else:
                await self._run_agent_browser("type", text, timeout=30)

            return FacultyResult(
                success=True,
                summary=f"Typed '{text[:50]}{'...' if len(text) > 50 else ''}'",
                data={"text": text, "target": ref or selector},
            )
        except Exception as e:
            return FacultyResult(
                success=False,
                summary=f"Failed to type: {e}",
                error=str(e),
            )

    async def _scroll(self, params: dict) -> FacultyResult:
        """Scroll the page."""
        direction = params.get("direction", "down")

        try:
            await self._run_agent_browser("scroll", direction, timeout=10)

            return FacultyResult(
                success=True,
                summary=f"Scrolled {direction}",
                data={"direction": direction},
            )
        except Exception as e:
            return FacultyResult(
                success=False,
                summary=f"Failed to scroll: {e}",
                error=str(e),
            )

    async def _screenshot(self, params: dict) -> FacultyResult:
        """Take a screenshot of the current page."""
        url = params.get("url")
        output = params.get("output", "screenshot.png")

        try:
            if url:
                await self._run_agent_browser("navigate", url, timeout=60)

            await self._run_agent_browser("screenshot", output, timeout=30)

            return FacultyResult(
                success=True,
                summary=f"Screenshot saved to {output}",
                data={"path": output, "url": url},
            )
        except Exception as e:
            return FacultyResult(
                success=False,
                summary=f"Failed to take screenshot: {e}",
                error=str(e),
            )

    async def _pdf(self, params: dict) -> FacultyResult:
        """Save page as PDF."""
        url = params.get("url")
        output = params.get("output", "page.pdf")

        try:
            if url:
                await self._run_agent_browser("navigate", url, timeout=60)

            await self._run_agent_browser("pdf", output, timeout=30)

            return FacultyResult(
                success=True,
                summary=f"PDF saved to {output}",
                data={"path": output, "url": url},
            )
        except Exception as e:
            return FacultyResult(
                success=False,
                summary=f"Failed to save PDF: {e}",
                error=str(e),
            )

    async def cleanup(self):
        """Cleanup browser resources."""
        try:
            # Close any open browser sessions
            await self._run_agent_browser("close", timeout=10)
        except Exception:
            pass
        logger.info("[browser] Resources cleaned up")
