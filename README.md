# Memory Wallpaper

A privacy-first Chrome/Chromium extension that observes browser activity locally, summarizes the user's session with Groq, maintains a local SQLite memory, generates an evolving wallpaper through a hosted Hugging Face image model, and applies it on Windows.

## Privacy model

- Browser activity is sent only to `http://127.0.0.1:8765`.
- The extension records metadata only: URL, domain, title, timestamps, active-tab duration, and browser idle state.
- No page body, form input, cookies, passwords, downloads, or keystrokes are collected.
- The local backend stores only compact activity records and AI summaries in SQLite.
- Browser metadata is sent to Groq for text inference.
- The generated image prompt is sent to Hugging Face for image generation.
- Keep `GROQ_API_KEY` and `HUGGINGFACE_API_KEY` in `backend/.env`; never commit that file.

## Requirements

- Windows 10/11
- Chrome or Chromium-based browser
- Python 3.11+
- Groq API access and a Groq API key
- Hugging Face API access and a Hugging Face token with inference permissions

## 1. Install Python dependencies

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Configure cloud providers

Copy `backend/.env.example` to `backend/.env`, then replace both placeholder values with your keys. The backend loads this file automatically at startup, and `.gitignore` keeps it out of version control.

The defaults use Groq's configured model and Hugging Face's `stabilityai/stable-diffusion-3-medium-diffusers`. Change these in `backend/config.json` when needed.

## 3. Start the local backend

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
1. summarize recent activity with Groq
2. merge the summary into long-term visual memory
3. build a prompt
4. ask Hugging Face to generate the image
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
- choose a Hugging Face image model suited to the desired wallpaper style
- add signed installer/update infrastructure
- consider native messaging instead of a localhost API if stronger browser-to-app isolation is required
