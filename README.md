# Memory Wallpaper

Memory Wallpaper is a local-first Chrome/Chromium extension and Windows helper that turns browser activity into an evolving desktop wallpaper.

The project has three parts:

- `extension/`: records active-tab metadata and sends it to the local backend.
- `backend/`: stores compact browser metadata in SQLite, sends selected metadata to Groq for keyword extraction, sends the generated prompt to Hugging Face for image generation, and applies the image as the Windows wallpaper.
- `frontend/`: a Next.js dashboard for stats, stored memories, the latest wallpaper, and manual generation.

This app is not fully private because browser metadata and extracted keyword prompts are processed by cloud AI services. It does reduce the data sent to those services by keeping only metadata and not full page contents.

## How it works

```text
Browser tab metadata
        |
        v
Chrome extension -> FastAPI backend -> SQLite memory
                              |
                              v
                    Groq keyword extraction
                              |
                              v
                 Hugging Face image generation
                              |
                              v
                 Saved wallpaper + Windows desktop
```

Each generation uses recent activity plus the latest stored keyword memory:

1. The extension sends URL path, domain, title, start time, and duration.
2. The backend removes query strings and fragments before storing URLs.
3. The backend sends compact activity metadata and the latest memory keywords to Groq.
4. Groq returns a small JSON object containing visual keywords.
5. The backend merges exact Google search subjects, Groq keywords, and previous keywords.
6. The merged keywords become the Stable Diffusion prompt.
7. The generated image is validated, saved under `backend/data/wallpapers`, recorded in SQLite, and applied on Windows.

No page body, form input, cookies, passwords, downloads, keystrokes, or screenshots are collected locally. However, selected page metadata such as URL paths, domains, titles, and duration is sent to Groq, and the generated image prompt is sent to Hugging Face.

## Requirements

- Windows 10 or 11 for automatic wallpaper application
- Chrome or another Chromium-based browser
- Python 3.11 or newer
- Node.js and npm for the dashboard
- A Groq API key
- A Hugging Face token with inference permission

## Backend setup

From PowerShell at the repository root:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `backend/.env` and replace the placeholder values:

```text
GROQ_API_KEY=your-groq-key
HUGGINGFACE_API_KEY=your-huggingface-token
```

Keep `.env` private. It is ignored by Git.

The provider URLs, model names, generation interval, retention limits, and image dimensions are configured in `backend/config.json`.

Start the backend from inside `backend`:

```powershell
python server.py
```

The local API listens at `http://127.0.0.1:8765`.

The backend files are organized as follows:

- `server.py`: FastAPI routes and automatic scheduler
- `config.py`: paths and JSON configuration
- `models.py`: request validation models
- `database.py`: SQLite connections, memory, retention, and queries
- `activity.py`: privacy sanitization, compaction, and search-term extraction
- `providers.py`: Groq, Hugging Face, and Windows integrations
- `generation.py`: keyword-to-wallpaper workflow

## Browser extension

1. Start the backend.
2. Open `chrome://extensions`.
3. Enable **Developer mode**.
4. Select **Load unpacked**.
5. Choose the repository's `extension` folder.
6. Pin the extension if desired.

The extension sends data only to `http://127.0.0.1:8765`. It ignores browser-internal pages such as `chrome://`, `edge://`, and extension pages. Events shorter than two seconds are discarded.

## Frontend dashboard

Run the dashboard in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

The dashboard uses `http://127.0.0.1:8765` by default. To point it at another backend, create `frontend/.env.local`:

```text
NEXT_PUBLIC_API_URL=https://your-backend.example.com
```

This variable is public and must contain only the backend URL. Never put Groq or Hugging Face keys in a `NEXT_PUBLIC_*` variable.

## Generate a wallpaper

After browsing for a while, use the dashboard button or call the API:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/generate -Method POST
```

Automatic generation is enabled by the backend scheduler. The default threshold is 30 minutes of accumulated new activity. Change `generation_interval_minutes` in `backend/config.json` to adjust it.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Provider and service information |
| `GET` | `/api/stats` | Activity, memory, and generation counts |
| `GET` | `/api/memory` | Stored visual memory records |
| `GET` | `/api/memory/tokens` | Estimated stored-memory token usage |
| `GET` | `/api/wallpaper/latest` | Latest generated PNG |
| `POST` | `/api/activity` | Accept an extension activity batch |
| `POST` | `/api/generate` | Generate and apply a wallpaper |

## Storage and retention

Runtime data is kept in `backend/data/`:

- `memory.db`: SQLite database containing activity, memories, and generation records
- `wallpapers/`: generated PNG files

By default, the backend retains the newest 200 activity records, 20 memory records, and 10 generations. Older wallpaper files are deleted when their generation records are pruned. Do not delete `backend/data` unless you intentionally want to erase the local history and generated wallpapers.

## Hosting the frontend

The Next.js dashboard can be deployed separately on Vercel or another Node-compatible host:

1. Set the project root to `frontend`.
2. Use the existing `npm run build` command.
3. Set `NEXT_PUBLIC_API_URL` to a public HTTPS backend URL.
4. Update backend CORS to allow the deployed frontend origin.

Hosting only the frontend does not host the backend, database, extension activity, or Windows wallpaper application. The default extension still requires the local backend at `127.0.0.1:8765`.

## Security and privacy notes

- This is not end-to-end private or fully local. Browser metadata is sent to cloud inference services.
- The app minimizes exposure by storing compact metadata locally and by avoiding full page content, form inputs, cookies, tokens, and raw browsing bodies.
- The default backend binds to localhost and accepts the local dashboard plus Chrome extension origins.
