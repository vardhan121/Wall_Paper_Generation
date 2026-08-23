from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from activity import sanitize_activity
from config import CFG
from database import (
    DB_LOCK,
    activity_since,
    all_visual_memory,
    db,
    init_db,
    last_generation_time,
    memory_token_stats,
    now,
    prune_retained_data,
)
from generation import generate_wallpaper
from models import ActivityBatch

load_dotenv(Path(__file__).resolve().parent / ".env")
init_db()

app = FastAPI(title="Memory Wallpaper Local Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension://.*|http://localhost:3000|http://127\.0\.0\.1:3000)$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "groq": CFG["groq_url"],
        "huggingface": CFG["huggingface_url"],
        "huggingface_image_model": CFG["huggingface_image_model"],
    }


@app.get("/api/stats")
def stats():
    with DB_LOCK:
        conn = db()
        counts = {
            "activity_count": conn.execute("SELECT COUNT(*) c FROM activity").fetchone()["c"],
            "memory_count": conn.execute("SELECT COUNT(*) c FROM memories").fetchone()["c"],
            "generation_count": conn.execute("SELECT COUNT(*) c FROM generations").fetchone()["c"],
        }
        conn.close()
    return {**counts, "last_generation": last_generation_time()}


@app.get("/api/memory")
def memory():
    return all_visual_memory()


@app.get("/api/memory/tokens")
def memory_tokens():
    return memory_token_stats()


@app.get("/api/wallpaper/latest")
def latest_wallpaper():
    with DB_LOCK:
        conn = db()
        row = conn.execute(
            "SELECT image_path FROM generations ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
    if not row or not Path(row["image_path"]).is_file():
        raise HTTPException(404, "No wallpaper has been generated yet.")
    return FileResponse(row["image_path"], media_type="image/png")


@app.post("/api/activity")
def receive_activity(batch: ActivityBatch):
    events = sanitize_activity(batch.events)
    if not events:
        return {"accepted": 0}
    with DB_LOCK:
        conn = db()
        conn.executemany(
            "INSERT INTO activity(ts,url,domain,title,duration_seconds) VALUES(?,?,?,?,?)",
            [
                (event["ts"], event["url"], event["domain"], event["title"], event["duration_seconds"])
                for event in events
            ],
        )
        prune_retained_data(conn)
        conn.commit()
        conn.close()
    return {"accepted": len(events)}


@app.post("/api/generate")
async def generate():
    try:
        return await generate_wallpaper(force=True)
    except HTTPException:
        raise
    except Exception as error:
        print("[generate] failed:", error)
        raise HTTPException(502, f"Generation provider failed: {error}") from error


async def scheduler():
    while True:
        try:
            minutes = CFG["generation_interval_minutes"]
            cutoff = last_generation_time() or (now() - minutes * 60)
            new_events = activity_since(cutoff)
            total_seconds = sum(event["duration_seconds"] for event in new_events)
            if total_seconds >= minutes * 60:
                try:
                    await generate_wallpaper()
                except Exception as error:
                    print("[scheduler] generation failed:", error)
        except Exception as error:
            print("[scheduler] error:", error)
        await asyncio.sleep(60)


@app.on_event("startup")
async def startup():
    asyncio.create_task(scheduler())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=CFG["host"],
        port=CFG["port"],
        reload=False,
    )
