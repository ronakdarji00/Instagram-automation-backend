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
    python main.py --loop     # runs every 10 minutes (set interval in config)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://graph.facebook.com/v19.0"
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    missing = [
        k for k in ("access_token", "ig_user_id", "reply_message")
        if not cfg.get(k) or cfg[k].startswith("PASTE_")
    ]
    if missing:
        print(f"[ERROR] config.json me ye fields bharo: {', '.join(missing)}")
        print("README.md dekho for setup steps.")
        sys.exit(1)
    return cfg


def load_state(state_path: Path):
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            return set(json.load(f).get("replied", []))
    return set()


def save_state(state_path: Path, replied: set):
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump({"replied": sorted(replied)}, f, indent=2)


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Har 10 minute me repeat karo")
    parser.add_argument("--interval", type=int, default=600, help="Loop interval seconds me (default 600)")
    args = parser.parse_args()

    cfg = load_config()

    if args.loop:
        print(f"[LOOP] Har {args.interval}s me run hoga. Ctrl+C se stop.")
        try:
            while True:
                try:
                    run_once(cfg)
                except requests.HTTPError as e:
                    print(f"[ERROR] {e}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[STOP] Loop band kar diya.")
    else:
        run_once(cfg)


if __name__ == "__main__":
    main()
