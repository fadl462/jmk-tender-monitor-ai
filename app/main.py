from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import os

from .database import Base, engine, SessionLocal
from .routes import opportunities, board, crawl, assistant, settings as settings_routes, notifications, analytics
from . import models
from .crawler import SECTORS
from .config import settings

Base.metadata.create_all(bind=engine)

app = FastAPI(title="JMK Tender Monitor AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_dashboard_visits(request: Request, call_next):
    """Lightweight built-in traffic log for the dashboard page load itself
    (not every API call underneath it — one row per time someone opens the
    app). No login system exists, so this can only measure how often the
    dashboard gets opened, not identify who; the IP is one-way hashed, never
    stored raw."""
    if request.url.path == "/":
        try:
            db = SessionLocal()
            ip = request.client.host if request.client else ""
            ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else ""
            ua = request.headers.get("user-agent", "")[:200]
            db.add(models.PageVisit(path=request.url.path, ip_hash=ip_hash, user_agent=ua))
            db.commit()
            db.close()
        except Exception:
            pass  # never let visit logging break the actual page load
    return await call_next(request)


app.include_router(opportunities.router)
app.include_router(board.router)
app.include_router(crawl.router)
app.include_router(assistant.router)
app.include_router(settings_routes.router)
app.include_router(notifications.router)
app.include_router(analytics.router)

BASE_DIR = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

STATUSES = ["New", "Reviewing", "Go/No-Go", "Proposal Drafting", "Internal Review", "Submitted", "Shortlisted", "Awarded", "Lost", "Archived"]


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, "sectors": SECTORS, "statuses": STATUSES,
        "cron_secret": settings.CRON_SECRET,
    })
