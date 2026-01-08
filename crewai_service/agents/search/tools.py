"""Tools for the Search Agent.

Web search using Tavily API.
"""

from __future__ import annotations

import os

from crewai.tools import tool


@tool("web_search")
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information using Tavily.

    Use this tool to find current information, news, documentation,
    or any other web content.

    Args:
        query: Search query
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Search results with titles, URLs, and snippets
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY not configured. Web search is unavailable."

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
        )

        results = response.get("results", [])
        if not results:
            return f"No results found for: {query}"

        # Format results
        formatted = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            content = result.get("content", "")[:300]  # Truncate long content
            formatted.append(f"{i}. **{title}**\n   URL: {url}\n   {content}")

        return "\n\n".join(formatted)

    except ImportError:
        return "Error: tavily package not installed. Run: pip install tavily-python"
    except Exception as e:
        return f"Search error: {str(e)}"


@tool("web_search_deep")
def web_search_deep(query: str, max_results: int = 5) -> str:
    """Perform a deep web search with more comprehensive results.

    Use this for research tasks that need more detailed information.
    Takes longer but provides better quality results.

    Args:
        query: Search query
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Detailed search results with full content
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY not configured. Web search is unavailable."

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=True,
        )

        # Include the AI-generated answer if available
        answer = response.get("answer", "")
        results = response.get("results", [])

        output_parts = []

        if answer:
            output_parts.append(f"**Summary:** {answer}\n")

        if results:
            output_parts.append("**Sources:**")
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                url = result.get("url", "")
                content = result.get("content", "")
                output_parts.append(f"\n{i}. **{title}**\n   URL: {url}\n   {content}")

        return "\n".join(output_parts) if output_parts else f"No results found for: {query}"

    except ImportError:
        return "Error: tavily package not installed. Run: pip install tavily-python"
    except Exception as e:
        return f"Search error: {str(e)}"


# Export all tools as a list for the agent
SEARCH_TOOLS = [
    web_search,
    web_search_deep,
]
