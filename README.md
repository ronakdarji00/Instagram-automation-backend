# Instagram Auto-Reply — Backend

Auto-reply to comments on your Instagram Business reels using the Meta Graph API.

## Deployment Options

### Option 1: GitHub Actions (FREE, recommended)

Completely free for public repos. Runs every 5 minutes automatically.

#### Setup

1. Go to your repo: https://github.com/ronakdarji00/Instagram-automation-backend
2. **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add these:

| Secret Name | Value |
|-------------|-------|
| `IG_ACCESS_TOKEN` | Your long-lived Instagram access token |
| `IG_USER_ID` | Your Instagram Business account ID (e.g. `17841458403136214`) |
| `IG_REPLY_MESSAGE` | Your reply message (e.g. `Thanks for watching!`) |

4. Go to **Actions** tab → **Enable workflows**
5. Click on "Instagram Auto-Reply" → **Run workflow** to test manually

The workflow runs every 5 minutes automatically. State is saved back to the repo in `replied_comments.json`.

### Option 2: Local (laptop/PC)

```bash
cd backend
pip install -r requirements.txt
cp config.example.json config.json
# Edit config.json with your token and IG user ID
python main.py --loop --interval 300
```

## Files

- `main.py` — main script
- `config.example.json` — template config (copy to config.json for local use)
- `replied_comments.json` — state file (auto-updated by GitHub Actions)
- `requirements.txt` — Python dependencies
- `.github/workflows/auto-reply.yml` — GitHub Actions workflow
- `render.yaml` — Render deployment config (paid)

## How it works

1. Fetches recent media from your Instagram Business account
2. Gets comments on each post
3. Skips already-replied comments (tracked in replied_comments.json)
4. Replies to new comments with your configured message
5. Saves updated state

## Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| `IG_ACCESS_TOKEN` | Yes | - |
| `IG_USER_ID` | Yes | - |
| `IG_REPLY_MESSAGE` | Yes | - |
| `IG_MAX_COMMENTS` | No | `50` |
| `IG_STATE_FILE` | No | `replied_comments.json` |
