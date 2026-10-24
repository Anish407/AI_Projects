from ddgs import DDGS


def search_web(query: str) -> dict:
    """
    Search the web for current information.

    Args:
        query: Search query describing the information to find.

    Returns:
        Dictionary containing search status and matching results.
    """
    try:
        results = DDGS(timeout=10).text(
            query=query,
            max_results=5,
            backend="duckduckgo"
        )

        return {
            "status": "success",
            "query": query,
            "results": [
                {
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", "")
                }
                for item in results
            ]
        }

    except Exception as exc:
        return {
            "status": "error",
            "query": query,
            "message": str(exc)
        }