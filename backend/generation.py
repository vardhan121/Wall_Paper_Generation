from __future__ import annotations

import io
import json
import os
from datetime import datetime

from fastapi import HTTPException
from PIL import Image

from activity import compact_activity, observed_search_terms
from config import CFG, WALLPAPERS
from database import (
    DB_LOCK,
    activity_since,
    db,
    delete_old_wallpapers,
    last_generation_time,
    latest_memory_keywords,
    now,
    prune_retained_data,
)
from providers import groq_json, huggingface_generate, set_windows_wallpaper


def make_keyword_prompt(activity, previous_keywords):
    return f"""
Extract the most useful visual keywords from this browser activity metadata.

ACTIVITY:
{json.dumps(activity, ensure_ascii=False, indent=2)}

PREVIOUS WALLPAPER KEYWORDS:
{json.dumps(previous_keywords, ensure_ascii=False)}

Return only this JSON:
{{
    "keywords": ["up to 12 short, concrete keywords copied from titles"]
}}

Rules:
- Copy important names and search subjects exactly; do not replace them with broad categories.
- Prefer subjects such as "Batman" or "Hulk" over website names such as "Google".
- Keep useful previous wallpaper keywords when they fit the new activity, so the visual world has continuity.
- Do not invent details or include URLs.
- Keep each keyword short and the list within the limit.
"""


def make_image_prompt(keywords):
    normalized = []
    seen = set()
    for keyword in keywords:
        if not isinstance(keyword, str):
            continue
        value = keyword.strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered not in seen:
            normalized.append(value)
            seen.add(lowered)

    joined = ", ".join(normalized)
    return f"""
Rewrite these keywords into one final image prompt.

KEYWORDS:
{joined}

Strict rules:
- Use ONLY the provided keywords as the subject matter.
- Do not invent or add any new character, object, or celebrity name unless it already appears in the keyword list.
- Do not add Batman, ChatGPT, Hugging Face, or any other extra subject unless it is explicitly present in the keywords.
- Keep the scene coherent and visually clear, with a cozy, colorful cartoon wallpaper mood.
- Include the keywords naturally in one scene, but do not add unrelated named elements.
- Do not include text, letters, logos, UI, watermark, or readable screens.
- Return only valid JSON in this exact format:
  {{"prompt": "<final image prompt>"}}
"""


def build_keyword_prompt_from_keywords(keywords):
    cleaned = []
    seen = set()
    for keyword in keywords:
        if not isinstance(keyword, str):
            continue
        value = keyword.strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered not in seen:
            cleaned.append(value)
            seen.add(lowered)

    if not cleaned:
        return (
            "Cozy wallpaper scene, colorful cartoon style, vibrant colors, playful and adorable, "
            "high quality illustration, no text, no logos, no UI, no watermark."
        )

    joined = ", ".join(cleaned)
    return (
        f"Cozy wallpaper scene featuring {joined}. Use these subjects exactly as the main elements of one "
        "coherent, colorful cartoon illustration. Warm ambient lighting, vibrant colors, playful mood, "
        "high quality illustration, rich details, no text, no letters, no logos, no UI, no watermark."
    )


def merge_keywords(*groups):
    merged = []
    seen = set()
    for group in groups:
        for keyword in group:
            if not isinstance(keyword, str) or not keyword.strip():
                continue
            keyword = keyword.strip()
            if keyword.lower() not in seen:
                merged.append(keyword)
                seen.add(keyword.lower())
    return merged[:12]


async def generate_wallpaper(force=False):
    last = last_generation_time()
    since = last if last else now() - CFG["activity_window_hours"] * 3600
    events = activity_since(since)
    if not events:
        raise HTTPException(400, "No new browser activity since the last generation.")

    compact = compact_activity(events[-20:])
    previous_keywords = latest_memory_keywords()
    keyword_result = await groq_json(make_keyword_prompt(compact, previous_keywords))
    keywords = keyword_result.get("keywords", [])
    if not isinstance(keywords, list):
        raise RuntimeError("Groq returned invalid keywords.")

    keywords = merge_keywords(observed_search_terms(compact), keywords, previous_keywords)
    if not keywords:
        raise RuntimeError("Groq returned no visual keywords.")

    image_prompt_result = await groq_json(make_image_prompt(keywords))
    image_prompt = image_prompt_result.get("prompt") or image_prompt_result.get("image_prompt")

    if not isinstance(image_prompt, str) or not image_prompt.strip():
        image_prompt = build_keyword_prompt_from_keywords(keywords)
    else:
        lowered_keywords = {str(keyword).strip().lower() for keyword in keywords if isinstance(keyword, str) and keyword.strip()}
        forbidden = [
            "batman",
            "chatgpt",
            "hugging face",
            "huggingface",
            "doctor",
            "doctore",
            "trump",
        ]
        lower_prompt = image_prompt.lower()
        if any(term in lower_prompt for term in forbidden) and not any(term in lowered_keywords for term in forbidden):
            image_prompt = build_keyword_prompt_from_keywords(keywords)
    image_bytes = huggingface_generate(
        image_prompt,
        "text, letters, logos, UI, watermark, readable screens, blurry, low quality",
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = WALLPAPERS / f"wallpaper_{stamp}.png"
    path.write_bytes(image_bytes)
    with Image.open(io.BytesIO(image_bytes)) as image:
        image.verify()

    with DB_LOCK:
        conn = db()
        conn.execute(
            "INSERT INTO memories(created_at,summary,visual_memory) VALUES(?,?,?)",
            (
                now(),
                f"Visual keywords: {', '.join(keywords)}",
                json.dumps({"keywords": keywords, "generated_prompt": image_prompt}, ensure_ascii=False),
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
        "summary": {"keywords": keywords},
        "visual_prompt": image_prompt,
        "image_path": str(path),
    }
