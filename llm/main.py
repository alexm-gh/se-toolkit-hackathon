"""
TTMM LLM Agent Service — standalone entry point.
"""
from fastapi import FastAPI
import os

from llm.chat import router as agent_router

app = FastAPI(
    title="TTMM LLM Agent",
    description="AI-powered agent for Table Tennis Match Matcher",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {"message": "TTMM LLM Agent v1.0", "health": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(agent_router)
