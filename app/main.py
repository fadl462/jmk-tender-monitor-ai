from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os

from .database import Base, engine
from .routes import opportunities, board, crawl, assistant
from .crawler import SECTORS

Base.metadata.create_all(bind=engine)

app = FastAPI(title="JMK Tender Monitor AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(opportunities.router)
app.include_router(board.router)
app.include_router(crawl.router)
app.include_router(assistant.router)

BASE_DIR = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

STATUSES = ["New", "Reviewing", "Preparing Bid", "Submitted", "Won", "Lost", "Archived"]


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "sectors": SECTORS, "statuses": STATUSES})
