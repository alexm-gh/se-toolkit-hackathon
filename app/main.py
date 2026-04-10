from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine, init_db
from app.routers import profiles, match_requests, auth
from app.routers import llm_proxy
import os

app = FastAPI(
    title="Table Tennis Match Matcher (TTMM)",
    description="Find your perfect table tennis partner instantly",
    version="1.0.0"
)

# Session middleware for OAuth state/nonce storage
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production"),
    https_only=False,
    same_site="lax",
)


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/")
async def root():
    return {"message": "TTMM API v1.0", "docs": "/docs"}


# Serve frontend
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/app")
async def serve_frontend():
    return FileResponse(os.path.join(frontend_dir, "index.html"))


app.include_router(profiles.router)
app.include_router(match_requests.router)
app.include_router(llm_proxy.router)
app.include_router(auth.router)
