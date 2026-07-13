"""
Database connection setup.

DATABASE_URL should point at your Supabase Postgres instance in production
(use the Session pooler connection string — Render's free tier doesn't
reliably route the direct connection's IPv6 address). Falls back to a
local SQLite file if DATABASE_URL isn't set, so the backend can run and be
tested without a real database during development.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local_dev.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
