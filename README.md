# Memory Wallpaper

> I built a wallpaper that remembers what I browse and turns it into art.

Memory Wallpaper is a local-first Chrome/Chromium extension, FastAPI backend, and
Next.js dashboard that transforms browser activity into an evolving Windows
desktop wallpaper.

It is a playful visual diary: the extension records lightweight browsing
metadata, Groq turns that metadata into visual keywords and then a polished
image prompt, and Hugging Face generates the wallpaper.

## What it does

- Tracks active-tab metadata such as title, domain, URL path, and time spent.
- Removes URL query strings and fragments before local storage.
- Extracts meaningful visual keywords with Groq.
- Asks Groq to compose the final image prompt from only those keywords.
- Generates a PNG through Hugging Face inference.
- Applies the image as the Windows desktop wallpaper.
- Stores compact memory records and generated prompts in local SQLite.
- Shows activity, memory fragments, prompts, and the latest wallpaper in a dashboard.

## How it works

```text
Browser activity
      |
      v
Chrome extension
      |
      v
FastAPI backend -> SQLite memory
      |
      +-> Groq: extract visual keywords
      |
      +-> Groq: write the final image prompt
                   |
                   v
          Hugging Face image generation
                   |
                   v
        Saved PNG -> Windows wallpaper
```

Each generation:

1. Collects recent activity from the local database.
2. Sends compact metadata and previous keywords to Groq.
3. Merges exact search subjects, Groq keywords, and useful previous keywords.
4. Sends those keywords back to Groq with strict instructions not to invent
   unrelated subjects.
5. Sends Groq's final prompt to Hugging Face.
6. Validates and saves the returned image.
7. Records the keywords and the exact prompt sent to Hugging Face.

## Privacy

This project is local-first, not fully local or end-to-end private.

The extension and database do not collect page bodies, form inputs, cookies,
passwords, downloads, keystrokes, or screenshots. It ignores browser-internal
pages and removes URL query strings and fragments.

Selected metadata, including page titles, domains, URL paths, and durations, is
sent to Groq for keyword and prompt generation. The final image prompt is sent
to Hugging Face. Review the policies of those providers before using the
project with sensitive browsing activity.

The backend binds to `127.0.0.1` by default, and API keys remain in the backend
environment rather than the frontend.

## Requirements

- Windows 10 or 11 for automatic wallpaper application
- Chrome or another Chromium-based browser
- Python 3.11 or newer
- Node.js and npm
- A Groq API key
- A Hugging Face token with inference permission

## Installation

### 1. Configure the backend

From PowerShell at the repository root:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`:

```text
GROQ_API_KEY=your-groq-key
HUGGINGFACE_API_KEY=your-huggingface-token
```

Keep `.env` private. It is ignored by Git.

Provider URLs, model names, generation intervals, retention limits, and image
dimensions are configured in `backend/config.json`.

Start the backend from inside `backend`:

```powershell
python server.py
```

The local API listens at `http://127.0.0.1:8765`.

### 2. Load the browser extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose the repository's `extension` folder.
5. Pin the extension if desired.

The extension sends activity only to the local backend at
`http://127.0.0.1:8765`. Events shorter than two seconds are discarded.

### 3. Start the dashboard

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The dashboard uses `http://127.0.0.1:8765` by default. To use another backend,
create `frontend/.env.local`:

```text
NEXT_PUBLIC_API_URL=https://your-backend.example.com
```

Never put Groq or Hugging Face credentials in a `NEXT_PUBLIC_*` variable.

## Generate a wallpaper

Browse normally for a while, then use **Generate next wallpaper** in the
dashboard. You can also call the API:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/generate -Method POST
```

Automatic generation is enabled by the backend scheduler. The default
threshold is 30 minutes of accumulated new activity. Adjust
`generation_interval_minutes` in `backend/config.json` if needed.

## Project structure

```text
extension/
  background.js     Activity tracking and batching
  manifest.json     Chrome extension configuration
  options.html      Extension settings page

backend/
  server.py         FastAPI routes and scheduler
  generation.py     Keyword-to-prompt-to-wallpaper workflow
  activity.py       Sanitization, compaction, and search-term extraction
  database.py       SQLite storage, memory, and retention
  providers.py      Groq, Hugging Face, and Windows integrations
  config.json       Runtime configuration

frontend/
  src/app/page.tsx  Dashboard UI
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Provider and service information |
| `GET` | `/api/stats` | Activity, memory, and generation counts |
| `GET` | `/api/memory` | Stored memories and generated prompts |
| `GET` | `/api/memory/tokens` | Estimated stored-memory token usage |
| `GET` | `/api/wallpaper/latest` | Latest generated PNG |
| `POST` | `/api/activity` | Accept an extension activity batch |
| `POST` | `/api/generate` | Generate and apply a wallpaper |

## Storage and retention

Runtime data is stored in `backend/data/`:

- `memory.db`: activity, visual memory, and generation records
- `wallpapers/`: generated PNG files

The default limits are:

- 200 activity records
- 20 memory records
- 10 generation records

Older records and their wallpaper files are pruned automatically. Delete
`backend/data` only when you intentionally want to erase local history and
generated wallpapers.

## Development

Backend dependencies are pinned in `backend/requirements.txt`.

Frontend commands:

```powershell
cd frontend
npm run lint
npm run build
```

The frontend can be deployed separately, but a deployed dashboard still needs
an accessible backend and an updated CORS configuration. The default extension
continues to require the local backend at `127.0.0.1:8765`.

## Security and privacy notes

- This is not end-to-end private or fully local. Browser metadata is sent to cloud inference services.
- The app minimizes exposure by storing compact metadata locally and by avoiding full page content, form inputs, cookies, tokens, and raw browsing bodies.
- The default backend binds to localhost and accepts the local dashboard plus Chrome extension origins.

## Contributing

Ideas and contributions are welcome. Useful directions include:

- macOS and Linux wallpaper support
- additional image providers
- more visual styles and prompt controls
- improved activity filtering
- dashboard prompt history and export
- tests and documentation improvements

For changes, please explain the user-facing behavior, keep provider keys out
of commits, and verify the relevant backend or frontend command before opening
a pull request.

## License

No license has been specified yet. If you plan to publish or accept
contributions, add a license that matches how you want others to use the
project.
