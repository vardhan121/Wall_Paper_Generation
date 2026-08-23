from __future__ import annotations

import asyncio
import io
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import httpx
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
WALLPAPERS = DATA / "wallpapers"
DB = DATA / "memory.db"
CONFIG_PATH = ROOT / "config.json"

load_dotenv(ROOT / ".env")

DATA.mkdir(exist_ok=True)
WALLPAPERS.mkdir(exist_ok=True)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CFG = json.load(f)

app = FastAPI(title="Memory Wallpaper Local Agent")

# Only local extension/app clients should use this API.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension://.*|http://localhost:3000|http://127\.0\.0\.1:3000)$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

DB_LOCK = threading.Lock()


def db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with DB_LOCK:
        conn = db()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            url TEXT NOT NULL,
            domain TEXT NOT NULL,
            title TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at REAL NOT NULL,
            summary TEXT NOT NULL,
            visual_memory TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at REAL NOT NULL,
            prompt TEXT NOT NULL,
            image_path TEXT NOT NULL
        );
        """)
        conn.commit()
        conn.close()


init_db()


class Activity(BaseModel):
    url: str = Field(max_length=2048)
    domain: str = Field(max_length=512)
    title: str = Field(max_length=1000)
    started_at: float
    duration_seconds: int = Field(default=0, ge=0, le=86400)


class ActivityBatch(BaseModel):
    events: list[Activity] = Field(max_length=200)


def now():
    return time.time()


def recent_activity(hours: int) -> list[dict[str, Any]]:
    cutoff = now() - hours * 3600
    with DB_LOCK:
        conn = db()
        rows = conn.execute(
            "SELECT * FROM activity WHERE ts >= ? ORDER BY ts ASC", (cutoff,)
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def all_visual_memory() -> list[dict[str, Any]]:
    with DB_LOCK:
        conn = db()
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY created_at ASC"
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def prune_retained_data(conn):
    activity_limit = int(CFG["max_activity_records"])
    memory_limit = int(CFG["max_memory_records"])
    generation_limit = int(CFG["max_generation_records"])

    conn.execute(
        "DELETE FROM activity WHERE id NOT IN "
        "(SELECT id FROM activity ORDER BY ts DESC LIMIT ?)",
        (activity_limit,),
    )
    conn.execute(
        "DELETE FROM memories WHERE id NOT IN "
        "(SELECT id FROM memories ORDER BY created_at DESC LIMIT ?)",
        (memory_limit,),
    )

    old_paths = conn.execute(
        "SELECT image_path FROM generations WHERE id NOT IN "
        "(SELECT id FROM generations ORDER BY created_at DESC LIMIT ?)",
        (generation_limit,),
    ).fetchall()
    conn.execute(
        "DELETE FROM generations WHERE id NOT IN "
        "(SELECT id FROM generations ORDER BY created_at DESC LIMIT ?)",
        (generation_limit,),
    )
    return [Path(row["image_path"]) for row in old_paths]


def delete_old_wallpapers(paths):
    for path in paths:
        try:
            path.resolve().relative_to(WALLPAPERS.resolve())
        except ValueError:
            continue
        if path.is_file():
            path.unlink()


def last_generation_time():
    with DB_LOCK:
        conn = db()
        row = conn.execute(
            "SELECT created_at FROM generations ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
    return row["created_at"] if row else 0


def activity_since(ts: float) -> list[dict[str, Any]]:
    with DB_LOCK:
        conn = db()
        rows = conn.execute(
            "SELECT * FROM activity WHERE ts > ? ORDER BY ts ASC", (ts,)
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def sanitize_activity(events: list[Activity]):
    cleaned = []
    for e in events:
        # Keep metadata only. Do not store query strings/fragments.
        try:
            from urllib.parse import urlsplit, urlunsplit
            p = urlsplit(e.url)
            safe_url = urlunsplit((p.scheme, p.netloc, p.path, "", ""))
        except Exception:
            safe_url = e.url.split("?", 1)[0].split("#", 1)[0]

        cleaned.append({
            "ts": float(e.started_at),
            "url": safe_url[:2048],
            "domain": e.domain[:512],
            "title": e.title[:1000],
            "duration_seconds": int(e.duration_seconds),
        })
    return cleaned


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
        activity_count = conn.execute("SELECT COUNT(*) c FROM activity").fetchone()["c"]
        memory_count = conn.execute("SELECT COUNT(*) c FROM memories").fetchone()["c"]
        generation_count = conn.execute("SELECT COUNT(*) c FROM generations").fetchone()["c"]
        conn.close()
    return {
        "activity_count": activity_count,
        "memory_count": memory_count,
        "generation_count": generation_count,
        "last_generation": last_generation_time(),
    }


@app.get("/api/memory")
def memory():
    return all_visual_memory()


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
            """INSERT INTO activity(ts,url,domain,title,duration_seconds)
               VALUES(?,?,?,?,?)""",
            [
                (
                    e["ts"], e["url"], e["domain"],
                    e["title"], e["duration_seconds"]
                )
                for e in events
            ],
        )
        prune_retained_data(conn)
        conn.commit()
        conn.close()

    return {"accepted": len(events)}


def compact_activity(events):
    # The model receives metadata, not raw page contents.
    by_domain = {}
    for e in events:
        d = e["domain"]
        by_domain.setdefault(d, {"seconds": 0, "titles": []})
        by_domain[d]["seconds"] += e["duration_seconds"]
        if e["title"] and e["title"] not in by_domain[d]["titles"]:
            by_domain[d]["titles"].append(e["title"][:180])

    return [
        {
            "domain": domain,
            "minutes": round(v["seconds"] / 60, 1),
            "titles": v["titles"][:8],
        }
        for domain, v in sorted(
            by_domain.items(),
            key=lambda x: x[1]["seconds"],
            reverse=True,
        )
    ][:50]


async def groq_json(prompt: str) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")

    url = CFG["groq_url"].rstrip("/") + "/chat/completions"
    payload = {
        "model": CFG["groq_model"],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
        "max_completion_tokens": 2048,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a privacy-first personal visual-memory engine. "
                    "You only receive browser metadata. Never claim to know "
                    "private page contents. Return strict JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.is_error and r.status_code == 400 and "json_validate_failed" in r.text:
            payload.pop("response_format")
            r = await client.post(url, headers=headers, json=payload)
        if r.is_error:
            raise RuntimeError(
                f"Groq API error ({r.status_code}): {r.text[:500]}"
            )
        data = r.json()

    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Groq returned invalid JSON: {str(content)[:500]}"
        ) from error


def make_summary_prompt(activity, old_memory):
    return f"""
Analyze this browser session metadata.

RECENT ACTIVITY:
{json.dumps(activity, ensure_ascii=False, indent=2)}

EXISTING VISUAL MEMORY:
{json.dumps(old_memory[-12:], ensure_ascii=False, indent=2)}

Return JSON with exactly these fields:
{{
  "summary": "2-4 sentence summary of what the user explored",
  "topics": ["..."],
  "projects": ["..."],
  "visual_motifs": ["..."],
  "mood": "short phrase",
  "new_world_elements": ["..."],
  "preserve_elements": ["..."]
}}

Rules:
- Infer cautiously from domains and titles.
- Do not invent personal facts.
- Keep visual motifs concrete.
- preserve_elements should reference broad visual continuity, not sensitive data.
"""


def make_image_prompt(summary_obj, old_memory):
    return f"""
Create a cinematic desktop wallpaper prompt from a user's evolving visual memory.

CURRENT MEMORY:
{json.dumps(summary_obj, ensure_ascii=False, indent=2)}

PREVIOUS MEMORY:
{json.dumps(old_memory[-8:], ensure_ascii=False, indent=2)}

The image should feel like ONE persistent world that has evolved, not a collage.
Blend today's interests into the existing world.
No text, letters, UI, logos, watermarks, readable screens, or recognizable copyrighted
characters. Use symbolic visual metaphors rather than literal browser screenshots.

Return JSON:
{{
    "statements": [
        "statement 1: the main environment or composition",
        "statement 2: the visual subjects, motifs, and colors",
        "statement 3: the cinematic lighting, style, and atmosphere"
    ],
  "negative_prompt": "one detailed negative prompt"
}}

Rules:
- Return exactly 3 statements.
- Each statement must be one concise sentence of at most 25 words.
- The three statements must describe one coherent image, not separate scenes.
- Do not include text, letters, logos, UI, watermarks, or copyrighted characters.
"""


def huggingface_generate(prompt, negative):
    api_key = os.environ.get("HUGGINGFACE_API_KEY")
    if not api_key:
        raise RuntimeError("HUGGINGFACE_API_KEY is not set.")

    model = CFG["huggingface_image_model"]
    url = CFG["huggingface_url"].rstrip("/") + "/" + model
    payload = {
        "inputs": prompt,
        "parameters": {
            "negative_prompt": negative,
            "width": CFG["wallpaper_width"],
            "height": CFG["wallpaper_height"],
        },
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=300,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Hugging Face API error ({response.status_code}): "
            f"{response.text[:500]}"
        )
    if not response.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError(
            "Hugging Face returned a non-image response: "
            + response.text[:500]
        )
    return response.content


def set_windows_wallpaper(path: Path):
    import ctypes
    SPI_SETDESKWALLPAPER = 20
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02

    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER,
        0,
        str(path),
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
    )
    if not result:
        raise OSError("Windows refused to set the wallpaper.")


async def generate_wallpaper(force=False):
    last = last_generation_time()
    since = last if last else now() - CFG["activity_window_hours"] * 3600
    events = activity_since(since)

    if not events:
        raise HTTPException(400, "No new browser activity since the last generation.")

    compact = compact_activity(events)
    old = all_visual_memory()

    summary = await groq_json(make_summary_prompt(compact, old))
    visual = await groq_json(make_image_prompt(summary, old))

    statements = visual.get("statements")
    if not isinstance(statements, list) or len(statements) != 3:
        raise RuntimeError("Groq must return exactly 3 image prompt statements.")
    if not all(isinstance(statement, str) and statement.strip() for statement in statements):
        raise RuntimeError("Groq returned an invalid image prompt statement.")

    image_prompt = " ".join(statement.strip() for statement in statements)
    image_bytes = huggingface_generate(
        image_prompt,
        visual.get("negative_prompt", "text, watermark, logo, UI, blurry"),
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = WALLPAPERS / f"wallpaper_{stamp}.png"
    path.write_bytes(image_bytes)

    # Validate the image before applying it.
    with Image.open(io.BytesIO(image_bytes)) as im:
        im.verify()

    with DB_LOCK:
        conn = db()
        conn.execute(
            "INSERT INTO memories(created_at,summary,visual_memory) VALUES(?,?,?)",
            (
                now(),
                summary.get("summary", ""),
                json.dumps(
                    {
                        **summary,
                        "generated_prompt": image_prompt,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.execute(
            "INSERT INTO generations(created_at,prompt,image_path) VALUES(?,?,?)",
            (now(), image_prompt, str(path)),
        )
        old_wallpapers = prune_retained_data(conn)
        conn.commit()
        conn.close()

    delete_old_wallpapers(old_wallpapers)

    if os.name == "nt":
        set_windows_wallpaper(path)

    return {
        "summary": summary,
        "visual_prompt": image_prompt,
        "image_path": str(path),
    }


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
            total_seconds = sum(e["duration_seconds"] for e in new_events)

            if total_seconds >= minutes * 60:
                try:
                    await generate_wallpaper()
                except Exception as e:
                    print("[scheduler] generation failed:", e)
        except Exception as e:
            print("[scheduler] error:", e)

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
