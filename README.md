# Memory Wallpaper

A privacy-first Chrome/Chromium extension that observes browser activity locally, summarizes the user's session with a local Ollama model, maintains a local SQLite memory, generates an evolving wallpaper through a local ComfyUI server, and applies it on Windows.

## Privacy model

- Browser activity is sent only to `http://127.0.0.1:8765`.
- The extension records metadata only: URL, domain, title, timestamps, active-tab duration, and browser idle state.
- No page body, form input, cookies, passwords, downloads, or keystrokes are collected.
- The local backend stores only compact activity records and AI summaries in SQLite.
- AI inference is local through Ollama.
- Image generation is local through ComfyUI.
- Nothing in this project requires a cloud API.

## Requirements

- Windows 10/11
- Chrome or Chromium-based browser
- Python 3.11+
- Ollama installed locally with a chat model, e.g. `llama3.2:3b`
- ComfyUI running locally with an SDXL/SD1.5-compatible checkpoint

## 1. Install Python dependencies

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Start Ollama

Install Ollama, then:

```powershell
ollama pull llama3.2:3b
```

The backend defaults to `http://127.0.0.1:11434`.

## 3. Start ComfyUI

Run ComfyUI locally on:

`http://127.0.0.1:8188`

Put a model checkpoint into ComfyUI's `models/checkpoints` directory.

Then edit `backend/config.json` and set `comfyui_checkpoint` to the exact checkpoint filename.

The included workflow uses a basic txt2img graph and should be adapted if your ComfyUI checkpoint/node setup differs.

## 4. Start the local backend

```powershell
python server.py
```

The API listens on:

`http://127.0.0.1:8765`

## 5. Install the browser extension

Open:

`chrome://extensions`

Enable **Developer mode** → **Load unpacked** → choose the `extension` folder.

Pin the extension.

## 6. Generate your first wallpaper

After browsing for a while:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/generate -Method POST
```

The backend will:
1. summarize recent activity
2. merge the summary into long-term visual memory
3. build a prompt
4. ask local ComfyUI to generate the image
5. save it under `backend/data/wallpapers`
6. set it as the Windows desktop wallpaper

## 7. Automatic generation

The backend runs a background loop. By default it generates after 30 minutes of accumulated new browsing activity, then waits until there is another 30 minutes of new activity.

Change this in `config.json`.

## API

- `GET /api/health`
- `GET /api/stats`
- `GET /api/memory`
- `POST /api/activity`
- `POST /api/generate`

## Demo

For a hackathon demo:
1. Start the backend.
2. Browse 5–10 sites around a topic.
3. Wait until activity appears in `/api/stats`.
4. Trigger `/api/generate`.
5. Show the generated wallpaper.
6. Browse a second topic and generate again.
7. Show that the new image preserves the previous "world" while adding the new theme.

## Production hardening

This project intentionally binds the backend to `127.0.0.1`. For a real release:
- add extension-to-server authentication with a locally generated secret
- encrypt sensitive local state if needed
- provide a pause/delete-memory UI
- use a proper ComfyUI workflow tailored to the installed checkpoint
- add signed installer/update infrastructure
- consider native messaging instead of a localhost API if stronger browser-to-app isolation is required
