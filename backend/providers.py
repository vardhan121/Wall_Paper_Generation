from __future__ import annotations

import json
import os

import httpx
import requests

from config import CFG


async def groq_json(prompt: str) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")
    payload = {
        "model": CFG["groq_model"],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "reasoning_effort": "low",
        "max_completion_tokens": 256,
        "messages": [
            {
                "role": "system",
                "content": "Extract concise keywords from browser metadata. Return strict JSON.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    url = CFG["groq_url"].rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        if response.is_error and response.status_code == 400 and "json_validate_failed" in response.text:
            payload.pop("response_format")
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
        if response.is_error:
            raise RuntimeError(f"Groq API error ({response.status_code}): {response.text[:500]}")
        data = response.json()
    choice = data["choices"][0]
    try:
        return json.loads(choice["message"]["content"])
    except (TypeError, json.JSONDecodeError) as error:
        finish_reason = choice.get("finish_reason", "unknown")
        raise RuntimeError(
            f"Groq returned invalid JSON (finish_reason={finish_reason}): "
            f"{str(choice.get('message', {}).get('content'))[:500]}"
        ) from error


def huggingface_generate(prompt, negative):
    api_key = os.environ.get("HUGGINGFACE_API_KEY")
    if not api_key:
        raise RuntimeError("HUGGINGFACE_API_KEY is not set.")
    url = (
        CFG["huggingface_url"].rstrip("/")
        + "/"
        + CFG["huggingface_image_model"]
    )
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "inputs": prompt,
            "parameters": {
                "negative_prompt": negative,
                "width": CFG["wallpaper_width"],
                "height": CFG["wallpaper_height"],
            },
        },
        timeout=300,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Hugging Face API error ({response.status_code}): {response.text[:500]}")
    if not response.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError("Hugging Face returned a non-image response: " + response.text[:500])
    return response.content


def set_windows_wallpaper(path):
    import ctypes

    result = ctypes.windll.user32.SystemParametersInfoW(
        20, 0, str(path), 0x01 | 0x02
    )
    if not result:
        raise OSError("Windows refused to set the wallpaper.")
