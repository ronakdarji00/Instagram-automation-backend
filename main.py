"""
Instagram Reels Comment & Direct Message Auto-Reply
---------------------------------------------------
Fetches comments and DMs on your Instagram Business account
and replies with customizable template messages.

Requirements:
- Instagram Business account linked to a Facebook Page
- Meta Developer app with:
    - instagram_manage_comments (for comments)
    - instagram_manage_messages (for DMs)
    - pages_show_list, pages_read_engagement
- A valid access token
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
    """Load config from environment variables first, then fall back to config.json."""
    cfg = {
        "access_token": os.environ.get("IG_ACCESS_TOKEN", ""),
        "ig_user_id": os.environ.get("IG_USER_ID", ""),
        "reply_message": os.environ.get("IG_REPLY_MESSAGE", ""),
        "dm_reply_message": os.environ.get("IG_DM_REPLY_MESSAGE", ""),
        "state_file": os.environ.get("IG_STATE_FILE", "replied_comments.json"),
        "max_comments_per_run": int(os.environ.get("IG_MAX_COMMENTS", "50")),
        "max_dms_per_run": int(os.environ.get("IG_MAX_DMS", "20")),
    }

    if not cfg["access_token"] or not cfg["ig_user_id"]:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
            for k in ("access_token", "ig_user_id", "reply_message", "dm_reply_message", "state_file", "max_comments_per_run", "max_dms_per_run"):
                if not cfg.get(k) and file_cfg.get(k):
                    cfg[k] = file_cfg[k]
            if not cfg["reply_message"]:
                cfg["reply_message"] = file_cfg.get("reply_message", "Thanks for watching! 🙏")
            if not cfg["dm_reply_message"]:
                cfg["dm_reply_message"] = file_cfg.get("dm_reply_message", cfg["reply_message"])

    if not cfg.get("dm_reply_message"):
        cfg["dm_reply_message"] = cfg.get("reply_message", "Hey! Thanks for messaging us 🙌")

    missing = [
        k for k in ("access_token", "ig_user_id")
        if not cfg.get(k) or str(cfg[k]).startswith("PASTE_")
    ]
    if missing:
        print(f"[ERROR] Ye fields configure karo: {', '.join(missing)}")
        print("Environment variables (IG_ACCESS_TOKEN, IG_USER_ID) ya config.json use karo.")
        sys.exit(1)
    return cfg


def load_state(state_path: Path):
    """Load tracked replied comment and DM IDs."""
    state = {"comments": set(), "dms": set()}
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "replied" in data and isinstance(data["replied"], list):
                    state["comments"] = set(data["replied"])
                if "replied_comments" in data and isinstance(data["replied_comments"], list):
                    state["comments"].update(data["replied_comments"])
                if "replied_dms" in data and isinstance(data["replied_dms"], list):
                    state["dms"] = set(data["replied_dms"])
        except (json.JSONDecodeError, IOError):
            pass
    return state


def save_state(state_path: Path, replied_comments: set, replied_dms: set = None):
    """Save tracked replied IDs back to state JSON."""
    try:
        data = {
            "replied": sorted(replied_comments),
            "replied_comments": sorted(replied_comments),
            "replied_dms": sorted(replied_dms or set())
        }
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except IOError:
        pass


def parse_meta_error(resp):
    """Extract clean and actionable error message from Meta Graph API response."""
    try:
        err = resp.json().get("error", {})
        msg = err.get("message", resp.text)
        code = err.get("code")
        subcode = err.get("error_subcode")
        if code == 190 or subcode == 463:
            return (
                f"Instagram Access Token Expired (OAuthException 190, subcode {subcode}): {msg}. "
                "Kripya Meta Developer Portal se naya Long-Lived Token generate karke update karein."
            )
        elif code == 100:
            return f"Instagram API Parameter/Permission Error (code 100): {msg}"
        elif code == 200 or code == 230:
            return f"Instagram Permission Error (code {code}): Ensure your token has 'instagram_manage_comments' and 'instagram_manage_messages'. Detail: {msg}"
        return f"Instagram API Error (code {code}): {msg}"
    except Exception:
        return f"HTTP {resp.status_code}: {resp.text}"


def get_recent_media(cfg, limit: int = 25, scan_older: bool = False, max_pages: int = 3):
    """Fetch reels/posts from the IG business account with optional pagination for older media."""
    url = f"{BASE_URL}/{cfg['ig_user_id']}/media"
    params = {
        "fields": "id,media_type,comments_count,timestamp",
        "access_token": cfg["access_token"],
        "limit": min(limit, 100),
    }

    all_media = []
    current_url = url
    current_params = params

    for _ in range(max_pages if scan_older else 1):
        resp = requests.get(current_url, params=current_params, timeout=30)
        if not resp.ok:
            raise RuntimeError(parse_meta_error(resp))
        body = resp.json()
        data = body.get("data", [])
        all_media.extend(data)

        if not scan_older:
            break

        # Check for next page
        next_page = body.get("paging", {}).get("next")
        if not next_page:
            break
        current_url = next_page
        current_params = None

    return all_media


def get_comments(cfg, media_id: str, limit: int = 50, scan_older: bool = False, max_pages: int = 3):
    """Fetch comments on a post, with optional pagination for older comments."""
    url = f"{BASE_URL}/{media_id}/comments"
    params = {
        "fields": "id,text,username,timestamp",
        "access_token": cfg["access_token"],
        "limit": min(limit, 100),
    }

    all_comments = []
    current_url = url
    current_params = params

    for _ in range(max_pages if scan_older else 1):
        resp = requests.get(current_url, params=current_params, timeout=30)
        if not resp.ok:
            raise RuntimeError(parse_meta_error(resp))
        body = resp.json()
        data = body.get("data", [])
        all_comments.extend(data)

        if not scan_older:
            break

        next_page = body.get("paging", {}).get("next")
        if not next_page:
            break
        current_url = next_page
        current_params = None

    return all_comments


def reply_to_comment(cfg, comment_id: str, message: str):
    """Post a reply to a specific comment."""
    url = f"{BASE_URL}/{comment_id}/replies"
    payload = {"message": message, "access_token": cfg["access_token"]}
    resp = requests.post(url, data=payload, timeout=30)
    if resp.status_code != 200:
        err_msg = parse_meta_error(resp)
        print(f"  [WARN] Reply fail hua ({resp.status_code}): {err_msg}")
        return False
    return True


def get_conversations(cfg, limit: int = 20):
    """Fetch recent Instagram Direct Message conversations."""
    url = f"{BASE_URL}/{cfg['ig_user_id']}/conversations"
    params = {
        "platform": "instagram",
        "fields": "id,updated_time,participants,messages.limit(5){id,message,from,created_time}",
        "access_token": cfg["access_token"],
        "limit": limit
    }
    resp = requests.get(url, params=params, timeout=30)
    if not resp.ok:
        raise RuntimeError(parse_meta_error(resp))
    return resp.json().get("data", [])


def send_dm(cfg, recipient_id: str, message: str):
    """Send an Instagram Direct Message to a recipient."""
    url = f"{BASE_URL}/{cfg['ig_user_id']}/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message}
    }
    params = {"access_token": cfg["access_token"]}
    resp = requests.post(url, params=params, json=payload, timeout=30)
    if resp.status_code != 200:
        err_msg = parse_meta_error(resp)
        print(f"  [WARN] DM bhejne me fail hua ({resp.status_code}): {err_msg}")
        return False
    return True


def run_once(cfg, scan_older: bool = False, force_reprocess: bool = False):
    """One-time run to reply to comments on Instagram reels/posts."""
    state_path = Path(__file__).parent / cfg.get("state_file", "replied_comments.json")
    state = load_state(state_path)
    replied = state["comments"]
    max_per_run = cfg.get("max_comments_per_run", 50)
    replied_this_run = 0

    print(f"\n=== Comment Auto-Reply Start: {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    if scan_older:
        print("[INFO] Deep Scan Mode Enabled: Older posts aur older comments fetch honge.")
    if force_reprocess:
        print("[INFO] Force Reprocess Enabled: Previous reply history ignore hogi.")

    try:
        media = get_recent_media(cfg, limit=25, scan_older=scan_older)
    except Exception as e:
        print(f"\n[ERROR] Media fetch nahi ho saka:\n{e}")
        return

    print(f"Total media posts scanned: {len(media)}")

    for post in media:
        if post.get("comments_count", 0) == 0:
            continue
        media_id = post["id"]
        print(f"\nPost {media_id} ({post.get('media_type')}) — {post.get('comments_count')} comments")
        try:
            comments = get_comments(cfg, media_id, limit=50, scan_older=scan_older)
        except Exception as e:
            print(f"  [WARN] Comments fetch fail: {e}")
            continue

        for c in comments:
            cid = c["id"]
            if not force_reprocess and cid in replied:
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
            continue
        break

    save_state(state_path, replied, state["dms"])
    print(f"\nReplied this run: {replied_this_run} | Total tracked comments: {len(replied)}")


def main():
    cfg = load_config()
    run_once(cfg)


if __name__ == "__main__":
    main()
