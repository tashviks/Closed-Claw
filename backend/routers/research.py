"""
Research router — deep web research with multi-step synthesis
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from tools.executor import execute_tool
import json

router = APIRouter()


class ResearchRequest(BaseModel):
    query: str
    depth: int = 2  # 1=quick, 2=standard, 3=deep
    max_sources: int = 5


@router.post("/")
async def research(req: ResearchRequest):
    """Perform multi-step web research and return synthesized results."""
    async def generate():
        yield f"data: {json.dumps({'type': 'status', 'message': f'Searching for: {req.query}'})}\n\n"

        # Step 1: Search
        search_result = await execute_tool("web_search", {
            "query": req.query,
            "max_results": req.max_sources,
        })

        results = search_result.get("results", [])
        yield f"data: {json.dumps({'type': 'search_results', 'data': results})}\n\n"

        if req.depth >= 2 and results:
            # Step 2: Fetch top pages
            fetched = []
            for r in results[:3]:
                url = r.get("url", "")
                if url:
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Reading: {url}'})}\n\n"
                    page = await execute_tool("fetch_url", {"url": url})
                    if "content" in page:
                        fetched.append({
                            "url": url,
                            "title": r.get("title", ""),
                            "content": page["content"][:2000],
                        })
            yield f"data: {json.dumps({'type': 'pages', 'data': fetched})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
