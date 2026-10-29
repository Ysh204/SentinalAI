"""Victim checkout service. Run separately on port 8001."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from shop import router as shop_router
except ImportError:
    from victim_app.shop import router as shop_router

SHOP_CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

app = FastAPI(
    title="SentinelAI demo shop",
    description="Deliberately breakable checkout used to demonstrate incident response. Demo environment only.",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=SHOP_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(shop_router)
