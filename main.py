"""
Instagram Reels Comment Auto-Reply (Personal Use)
--------------------------------------------------
Fetches comments on your own Instagram Business account's reels
and replies with a fixed template message.

Requirements:
- Instagram Business account linked to a Facebook Page
- Meta Developer app with instagram_manage_comments permission
- A long-lived access token

Usage:
    python main.py            # one-time run
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://graph.facebook.com/v19.0"
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config():
    # Try environment variables first (for Render/Railway/etc), then fall back to config.json
    cfg = {
        "access_token": os.environ.get("IG_ACCESS_TOKEN", ""),
        "ig_user_id": os.environ.get("IG_USER_ID", ""),
        "reply_message": os.environ.get("IG_REPLY_MESSAGE", ""),
        "state_file": os.environ.get("IG_STATE_FILE", "replied_comments.json"),
        "max_comments_per_run": int(os.environ.get("IG_MAX_COMMENTS", "50")),
    }

    # If env vars not set, try config.json
    if not cfg["access_token"] or not cfg["ig_user_id"]:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
            for k in ("access_token", "ig_user_id", "reply_message", "state_file", "max_comments_per_run"):
                if not cfg.get(k) and file_cfg.get(k):
                    cfg[k] = file_cfg[k]
            if not cfg["reply_message"]:
                cfg["reply_message"] = file_cfg.get("reply_message", "")

    missing = [
        k for k in ("access_token", "ig_user_id", "reply_message")
        if not cfg.get(k) or str(cfg[k]).startswith("PASTE_")
    ]
    if missing:
        print(f"[ERROR] Ye fields bharo: {', '.join(missing)}")
        print("Environment variables (IG_ACCESS_TOKEN, IG_USER_ID, IG_REPLY_MESSAGE) ya config.json use karo.")
        sys.exit(1)
    return cfg


def load_state(state_path: Path):
    # On cloud platforms, state file may not persist — that's okay, in-memory works
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return set(json.load(f).get("replied", []))
        except (json.JSONDecodeError, IOError):
            return set()
    return set()


def save_state(state_path: Path, replied: set):
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"replied": sorted(replied)}, f, indent=2)
    except IOError:
        # File system read-only (Render) — state stays in-memory only
        pass


def get_recent_media(cfg):
    """Fetch recent reels/media from the IG business account."""
    url = f"{BASE_URL}/{cfg['ig_user_id']}/media"
    params = {
        "fields": "id,media_type,comments_count,timestamp",
        "access_token": cfg["access_token"],
        "limit": 25,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def get_comments(cfg, media_id: str, limit: int = 50):
    """Fetch comments on a given media post."""
    url = f"{BASE_URL}/{media_id}/comments"
    params = {
        "fields": "id,text,username,timestamp",
        "access_token": cfg["access_token"],
        "limit": limit,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def reply_to_comment(cfg, comment_id: str, message: str):
    """Post a reply to a specific comment."""
    url = f"{BASE_URL}/{comment_id}/replies"
    payload = {"message": message, "access_token": cfg["access_token"]}
    resp = requests.post(url, data=payload, timeout=30)
    if resp.status_code != 200:
        print(f"  [WARN] Reply fail hua ({resp.status_code}): {resp.text}")
        return False
    return True


def run_once(cfg):
    state_path = Path(__file__).parent / cfg.get("state_file", "replied_comments.json")
    replied = load_state(state_path)
    max_per_run = cfg.get("max_comments_per_run", 50)
    replied_this_run = 0

    print(f"\n=== Run start: {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    media = get_recent_media(cfg)
    print(f"Recent media fetched: {len(media)}")

    for post in media:
        if post.get("comments_count", 0) == 0:
            continue
        media_id = post["id"]
        print(f"\nPost {media_id} ({post.get('media_type')}) — {post.get('comments_count')} comments")
        try:
            comments = get_comments(cfg, media_id)
        except requests.HTTPError as e:
            print(f"  [WARN] Comments fetch fail: {e}")
            continue

        for c in comments:
            cid = c["id"]
            if cid in replied:
                continue
            if replied_this_run >= max_per_run:
                print(f"  [INFO] max_comments_per_run ({max_per_run}) reach ho gaya, baaki next run me.")
                break
            text = c.get("text", "")[:60]
            print(f"  -> @{c.get('username','?')}: {text!r}")
            ok = reply_to_comment(cfg, cid, cfg["reply_message"])
            if ok:
                replied.add(cid)
                replied_this_run += 1
                print(f"     Replied ✓")
            else:
                # token expire / permission issue — is comment ko retry ke liye track mat karo
                continue
        else:
            continue
        break

    save_state(state_path, replied)
    print(f"\nReplied this run: {replied_this_run} | Total tracked: {len(replied)}")


def main():
    cfg = load_config()
    run_once(cfg)


if __name__ == "__main__":
    main()
