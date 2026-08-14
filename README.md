# Instagram Auto-Reply — Backend

Flask web service for manual Instagram comment auto-reply. Deploys to Render.

## Endpoints

- `GET /health` — health check
- `GET /settings` — show configured settings
- `POST /run` — run auto-reply once

### POST /run body

```json
{
  "reply_message": "Thanks for watching!",
  "already_replied": ["comment-id-1", "comment-id-2"],
  "max_comments": 50
}
```

## Deployment

### Render

Use the `render.yaml` blueprint or create manually:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`
- **Service Type:** Web Service

### Environment Variables

| Key | Required | Description |
|-----|----------|-------------|
| `IG_ACCESS_TOKEN` | Yes | Long-lived Instagram Graph API token |
| `IG_USER_ID` | Yes | Instagram Business account ID |
| `IG_REPLY_MESSAGE` | No | Default reply message |
| `IG_MAX_COMMENTS` | No | Max replies per run (default 50) |
| `API_KEY` | Yes | Secret key for frontend authentication |

## Local

```bash
cd backend
pip install -r requirements.txt
python main.py
```

For web service local:

```bash
python app.py
```
