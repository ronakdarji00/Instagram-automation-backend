"""
Instagram Auto-Reply Web Service (Comments & DMs)
--------------------------------------------------
Flask API for manual auto-reply from the Vercel frontend.

Endpoints:
  GET  /health          - health check
  GET  /verify          - verify Instagram token and account connection
  POST /verify          - verify provided or configured token
  GET  /settings        - get available settings and configuration status
  POST /settings        - update reply messages and limits from frontend
  POST /run             - run comments auto-reply (supports older comments scan)
  POST /run-dms         - run Instagram direct messages (DMs) auto-reply
  POST /reset-history   - reset comment/DM replied tracking history
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

import main as ig

app = Flask(__name__)
CORS(app)

CONFIG_PATH = Path(__file__).parent / "config.json"
STATE_PATH = Path(__file__).parent / "replied_comments.json"


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def get_base_config():
    """Load configuration from environment variables with config.json fallback."""
    file_cfg = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
        except Exception:
            pass

    access_token = get_env("IG_ACCESS_TOKEN") or file_cfg.get("access_token", "")
    ig_user_id = str(get_env("IG_USER_ID") or file_cfg.get("ig_user_id", "")).strip()
    reply_message = get_env("IG_REPLY_MESSAGE") or file_cfg.get("reply_message", "Thanks for watching! 🙏")
    dm_reply_message = get_env("IG_DM_REPLY_MESSAGE") or file_cfg.get("dm_reply_message", "Hey! Thanks for messaging us 🙌")
    
    raw_max = get_env("IG_MAX_COMMENTS") or file_cfg.get("max_comments_per_run", "50")
    try:
        max_comments = int(raw_max)
    except (ValueError, TypeError):
        max_comments = 50

    raw_max_dms = get_env("IG_MAX_DMS") or file_cfg.get("max_dms_per_run", "20")
    try:
        max_dms = int(raw_max_dms)
    except (ValueError, TypeError):
        max_dms = 20

    api_key = get_env("API_KEY") or file_cfg.get("api_key", "")

    return {
        "access_token": access_token.strip(),
        "ig_user_id": ig_user_id,
        "reply_message": reply_message,
        "dm_reply_message": dm_reply_message,
        "max_comments": max_comments,
        "max_dms": max_dms,
        "api_key": api_key.strip()
    }


def save_config_file(updates: dict):
    """Save persistent settings updates into config.json."""
    data = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    data.update(updates)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError:
        return False


def require_api_key():
    cfg = get_base_config()
    expected = cfg.get("api_key")
    if not expected:
        return None
    provided = request.headers.get("X-API-Key") or request.args.get("api_key", "")
    if provided != expected:
        return jsonify({"error": "Unauthorized: Invalid or missing API key"}), 401
    return None


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat()
    })


@app.route("/verify", methods=["GET", "POST"])
def verify_connection():
    """Verify Instagram Graph API token and Account ID."""
    auth_error = require_api_key()
    if auth_error:
        return auth_error

    data = (request.get_json(silent=True) or {}) if request.method == "POST" else {}
    base_cfg = get_base_config()

    access_token = data.get("access_token") or request.args.get("access_token") or base_cfg["access_token"]
    ig_user_id = data.get("ig_user_id") or request.args.get("ig_user_id") or base_cfg["ig_user_id"]

    if not access_token or not ig_user_id:
        return jsonify({
            "valid": False,
            "error": "IG_ACCESS_TOKEN ya IG_USER_ID configured nahi hai."
        }), 400

    try:
        url = f"{ig.BASE_URL}/{ig_user_id}"
        resp = requests.get(
            url,
            params={"fields": "id,name,username", "access_token": access_token},
            timeout=20
        )
        if resp.ok:
            account_data = resp.json()
            return jsonify({
                "valid": True,
                "account": account_data,
                "message": f"Connected successfully to @{account_data.get('username', account_data.get('name', ig_user_id))}"
            })
        else:
            err_msg = ig.parse_meta_error(resp)
            return jsonify({
                "valid": False,
                "error": err_msg,
                "status_code": resp.status_code
            }), 400
    except Exception as e:
        return jsonify({
            "valid": False,
            "error": f"Connection check failed: {str(e)}"
        }), 500


@app.route("/settings", methods=["GET", "POST"])
def settings():
    auth_error = require_api_key()
    if auth_error:
        return auth_error

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        updates = {}
        if "reply_message" in data:
            updates["reply_message"] = str(data["reply_message"]).strip()
        if "dm_reply_message" in data:
            updates["dm_reply_message"] = str(data["dm_reply_message"]).strip()
        if "max_comments" in data:
            try:
                updates["max_comments_per_run"] = int(data["max_comments"])
            except (ValueError, TypeError):
                pass
        if "max_dms" in data:
            try:
                updates["max_dms_per_run"] = int(data["max_dms"])
            except (ValueError, TypeError):
                pass

        if updates:
            save_config_file(updates)

        cfg = get_base_config()
        return jsonify({
            "success": True,
            "message": "Settings updated successfully",
            "reply_message": cfg["reply_message"],
            "dm_reply_message": cfg["dm_reply_message"],
            "max_comments": cfg["max_comments"],
            "max_dms": cfg["max_dms"]
        })

    # GET request
    cfg = get_base_config()
    uid = cfg["ig_user_id"]
    tok = cfg["access_token"]

    return jsonify({
        "ig_user_id": (uid[:6] + "..." + uid[-4:]) if len(uid) > 10 else uid,
        "has_access_token": bool(tok),
        "token_preview": (tok[:8] + "..." + tok[-6:]) if len(tok) > 14 else "",
        "default_reply_message": cfg["reply_message"],
        "default_dm_reply_message": cfg["dm_reply_message"],
        "max_comments_per_run": cfg["max_comments"],
        "max_dms_per_run": cfg["max_dms"],
        "requires_api_key": bool(cfg["api_key"])
    })


@app.route("/reset-history", methods=["POST"])
def reset_history():
    """Clear local tracking history of replied comments/DMs."""
    auth_error = require_api_key()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    target = data.get("target", "all")  # 'comments', 'dms', or 'all'

    state = ig.load_state(STATE_PATH)
    if target in ("comments", "all"):
        state["comments"].clear()
    if target in ("dms", "all"):
        state["dms"].clear()

    ig.save_state(STATE_PATH, state["comments"], state["dms"])
    return jsonify({
        "success": True,
        "message": f"History for '{target}' successfully reset."
    })


@app.route("/run", methods=["POST"])
def run():
    """Auto-reply to comments on Instagram reels/posts, with optional older comments scan."""
    auth_error = require_api_key()
    if auth_error:
        return auth_error

    base_cfg = get_base_config()
    data = request.get_json(silent=True) or {}

    access_token = data.get("access_token") or base_cfg["access_token"]
    ig_user_id = data.get("ig_user_id") or base_cfg["ig_user_id"]

    if not access_token or not ig_user_id:
        return jsonify({"error": "IG_ACCESS_TOKEN and IG_USER_ID not configured"}), 400

    reply_message = data.get("reply_message") or base_cfg["reply_message"]
    scan_older = bool(data.get("scan_older", False))
    force_reprocess = bool(data.get("force_reprocess", False))

    already_replied = set(data.get("already_replied", []))
    local_state = ig.load_state(STATE_PATH)
    if not force_reprocess:
        already_replied.update(local_state["comments"])

    max_comments = int(data.get("max_comments", base_cfg["max_comments"]))

    cfg = {
        "access_token": access_token,
        "ig_user_id": ig_user_id,
        "reply_message": reply_message,
        "state_file": None,
        "max_comments_per_run": max_comments,
    }

    new_replies = []
    new_replied_ids = []
    media_count = 0
    comment_count = 0
    reply_count = 0

    try:
        # scan_older=True enables deep pagination for older posts
        media = ig.get_recent_media(cfg, limit=50 if scan_older else 25, scan_older=scan_older)
        media_count = len(media)

        for post in media:
            if post.get("comments_count", 0) == 0:
                continue
            media_id = post["id"]
            try:
                comments = ig.get_comments(cfg, media_id, limit=50, scan_older=scan_older)
            except Exception as e:
                print(f"[WARN] Failed fetching comments for post {media_id}: {e}")
                continue

            for c in comments:
                cid = c["id"]
                if not force_reprocess and (cid in already_replied or cid in new_replied_ids):
                    continue
                if reply_count >= max_comments:
                    break

                comment_count += 1
                ok = ig.reply_to_comment(cfg, cid, reply_message)
                if ok:
                    new_replied_ids.append(cid)
                    new_replies.append({
                        "comment_id": cid,
                        "username": c.get("username", "?"),
                        "comment": c.get("text", "")[:120],
                        "reply": reply_message,
                        "time": datetime.now(timezone.utc).isoformat(),
                    })
                    reply_count += 1
            else:
                continue
            break

    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Save to local tracking file
    local_state["comments"].update(new_replied_ids)
    ig.save_state(STATE_PATH, local_state["comments"], local_state["dms"])

    return jsonify({
        "success": True,
        "replied": new_replies,
        "new_replied_ids": new_replied_ids,
        "stats": {
            "media": media_count,
            "comments_seen": comment_count,
            "replied_this_run": reply_count,
            "deep_scan": scan_older
        },
    })


@app.route("/run-dms", methods=["POST"])
def run_dms():
    """Auto-reply to Instagram Direct Messages (DMs)."""
    auth_error = require_api_key()
    if auth_error:
        return auth_error

    base_cfg = get_base_config()
    data = request.get_json(silent=True) or {}

    access_token = data.get("access_token") or base_cfg["access_token"]
    ig_user_id = data.get("ig_user_id") or base_cfg["ig_user_id"]

    if not access_token or not ig_user_id:
        return jsonify({"error": "IG_ACCESS_TOKEN and IG_USER_ID not configured"}), 400

    dm_reply_message = data.get("dm_reply_message") or base_cfg["dm_reply_message"]
    max_dms = int(data.get("max_dms", base_cfg["max_dms"]))

    already_replied_dms = set(data.get("already_replied_dms", []))
    local_state = ig.load_state(STATE_PATH)
    already_replied_dms.update(local_state["dms"])

    cfg = {
        "access_token": access_token,
        "ig_user_id": ig_user_id,
        "dm_reply_message": dm_reply_message,
    }

    new_replies = []
    new_replied_ids = []
    conv_count = 0
    replied_count = 0

    try:
        conversations = ig.get_conversations(cfg, limit=min(max_dms * 2, 50))
        conv_count = len(conversations)

        for conv in conversations:
            if replied_count >= max_dms:
                break

            conv_id = conv.get("id")
            messages = conv.get("messages", {}).get("data", [])
            if not messages:
                continue

            # Latest message in the thread
            latest_msg = messages[0]
            msg_id = latest_msg.get("id")
            sender = latest_msg.get("from", {})
            sender_id = sender.get("id")
            sender_name = sender.get("username", "User")
            msg_text = latest_msg.get("message", "")

            # If sender is our own IG Business account, we already sent the latest message!
            if sender_id == ig_user_id:
                continue

            # If already replied to this specific message or conversation
            if msg_id in already_replied_dms or msg_id in new_replied_ids:
                continue

            ok = ig.send_dm(cfg, sender_id, dm_reply_message)
            if ok:
                new_replied_ids.append(msg_id)
                new_replies.append({
                    "conversation_id": conv_id,
                    "message_id": msg_id,
                    "sender_id": sender_id,
                    "username": sender_name,
                    "message": msg_text[:120],
                    "reply": dm_reply_message,
                    "time": datetime.now(timezone.utc).isoformat(),
                })
                replied_count += 1

    except Exception as e:
        return jsonify({"error": str(e)}), 400

    local_state["dms"].update(new_replied_ids)
    ig.save_state(STATE_PATH, local_state["comments"], local_state["dms"])

    return jsonify({
        "success": True,
        "replied": new_replies,
        "new_replied_ids": new_replied_ids,
        "stats": {
            "conversations_seen": conv_count,
            "dms_replied_this_run": replied_count,
        }
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
