"""
Proxy router: forwards LLM agent requests to the separate llm-agent service.
"""
import os
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["agent"])

LLM_AGENT_URL = os.getenv("LLM_AGENT_URL", "http://llm-agent:8001")


@router.post("/chat")
async def proxy_chat(request: Request):
    """Proxy chat requests to the LLM agent service."""
    try:
        body = await request.body()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LLM_AGENT_URL}/api/v1/chat",
                content=body,
                headers={"content-type": request.headers.get("content-type", "application/json")},
                timeout=60.0,
            )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(
            content={"text": f"LLM agent unavailable: {str(e)}", "requires_confirmation": False, "action": None},
            status_code=503,
        )


@router.get("/chat/status")
async def proxy_chat_status():
    """Proxy chat status to the LLM agent service."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{LLM_AGENT_URL}/api/v1/chat/status", timeout=10.0)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(content={"llm_enabled": False, "reachable": False}, status_code=200)
