# ⚙️ Instagram Auto-Reply — Backend API & Engine

Flask web service & CLI automation engine for Instagram Reels Comments and Direct Messages (DMs).

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | Server health check |
| `/verify` | `GET`, `POST` | Check Meta Graph API token validity and account info |
| `/settings` | `GET`, `POST` | Read or persistently update reply messages and limits |
| `/run` | `POST` | Run comments auto-reply (supports `scan_older` & `force_reprocess`) |
| `/run-dms` | `POST` | Run Instagram Direct Messages (DMs) auto-reply |
| `/reset-history`| `POST` | Clear replied comments or DMs tracking cache |

### POST /run Payload Example
```json
{
  "reply_message": "Thanks for watching! 🙏",
  "scan_older": true,
  "force_reprocess": false,
  "already_replied": ["cid-1", "cid-2"],
  "max_comments": 50
}
```

### POST /run-dms Payload Example
```json
{
  "dm_reply_message": "Hey! Thanks for messaging us 🙌",
  "max_dms": 20,
  "already_replied_dms": ["mid-1"]
}
```

## Deployment on Render

Use the included `render.yaml` blueprint or create manually:
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`
- **Service Type:** Web Service

### Environment Variables
| Key | Required | Description |
|---|---|---|
| `IG_ACCESS_TOKEN` | Yes | 60-day Long-Lived Meta Graph API token |
| `IG_USER_ID` | Yes | Instagram Business/Creator Account ID |
| `IG_REPLY_MESSAGE` | No | Default comments reply message |
| `IG_DM_REPLY_MESSAGE` | No | Default DM reply message |
| `IG_MAX_COMMENTS` | No | Max replies per run (default: 50) |
| `IG_MAX_DMS` | No | Max DMs per run (default: 20) |
| `API_KEY` | No | Secret key for frontend authentication (optional) |

## Local Execution

Run Web Service API:
```bash
python app.py
```

Run Standalone Script:
```bash
python main.py
```
