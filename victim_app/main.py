"""Victim checkout service. Run separately on port 8001."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from victim_app.shop import router as shop_router
except ImportError:
    from shop import router as shop_router

app = FastAPI(
    title="SentinelAI demo shop",
    description="Deliberately breakable checkout used to demonstrate incident response. Demo environment only.",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(shop_router)
