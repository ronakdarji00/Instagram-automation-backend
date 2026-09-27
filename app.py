"""
Instagram Auto-Reply Web Service
---------------------------------
Flask API for manual auto-reply from the Vercel frontend.

Endpoints:
  GET  /health      - health check
  GET  /verify      - verify Instagram token and account connection
  POST /verify      - verify provided or configured token
  GET  /settings    - get available settings and configuration status
  POST /run         - run auto-reply once

Configuration (Env vars with config.json fallback):
  IG_ACCESS_TOKEN
  IG_USER_ID
  IG_REPLY_MESSAGE (optional fallback)
  IG_MAX_COMMENTS  (optional, default 50)
  API_KEY          (optional but recommended for security)
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
    reply_message = get_env("IG_REPLY_MESSAGE") or file_cfg.get("reply_message", "Thanks for watching!")
    
    raw_max = get_env("IG_MAX_COMMENTS") or file_cfg.get("max_comments_per_run", "50")
    try:
        max_comments = int(raw_max)
    except (ValueError, TypeError):
        max_comments = 50

    api_key = get_env("API_KEY") or file_cfg.get("api_key", "")

    return {
        "access_token": access_token.strip(),
        "ig_user_id": ig_user_id,
        "reply_message": reply_message,
        "max_comments": max_comments,
        "api_key": api_key.strip()
    }


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
    """Verify whether the Instagram Graph API token and Account ID are working."""
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


@app.route("/settings", methods=["GET"])
def settings():
    auth_error = require_api_key()
    if auth_error:
        return auth_error
        
    cfg = get_base_config()
    uid = cfg["ig_user_id"]
    tok = cfg["access_token"]

    return jsonify({
        "ig_user_id": (uid[:6] + "..." + uid[-4:]) if len(uid) > 10 else uid,
        "has_access_token": bool(tok),
        "token_preview": (tok[:8] + "..." + tok[-6:]) if len(tok) > 14 else "",
        "default_reply_message": cfg["reply_message"],
        "max_comments_per_run": cfg["max_comments"],
        "requires_api_key": bool(cfg["api_key"])
    })


@app.route("/run", methods=["POST"])
def run():
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
    already_replied = set(data.get("already_replied", []))
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
        media = ig.get_recent_media(cfg)
        media_count = len(media)

        for post in media:
            if post.get("comments_count", 0) == 0:
                continue
            media_id = post["id"]
            try:
                comments = ig.get_comments(cfg, media_id)
            except Exception as e:
                print(f"[WARN] Failed fetching comments for post {media_id}: {e}")
                continue

            for c in comments:
                cid = c["id"]
                if cid in already_replied or cid in new_replied_ids:
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

    return jsonify({
        "success": True,
        "replied": new_replies,
        "new_replied_ids": new_replied_ids,
        "stats": {
            "media": media_count,
            "comments_seen": comment_count,
            "replied_this_run": reply_count,
        },
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

