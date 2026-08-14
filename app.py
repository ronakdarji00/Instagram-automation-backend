"""
Instagram Auto-Reply Web Service
---------------------------------
Flask API for manual auto-reply from the Vercel frontend.

Endpoints:
  GET  /health      - health check
  POST /run         - run auto-reply once
  GET  /settings    - get available settings fields

Required env vars:
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

import main as ig

app = Flask(__name__)
CORS(app)


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def require_api_key():
    expected = get_env("API_KEY")
    if not expected:
        return None
    provided = request.headers.get("X-API-Key") or request.args.get("api_key", "")
    if provided != expected:
        return jsonify({"error": "Unauthorized"}), 401
    return None


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat()
    })


@app.route("/settings", methods=["GET"])
def settings():
    auth_error = require_api_key()
    if auth_error:
        return auth_error
    return jsonify({
        "ig_user_id": get_env("IG_USER_ID", "")[:6] + "..." if get_env("IG_USER_ID") else "",
        "default_reply_message": get_env("IG_REPLY_MESSAGE", "Thanks for watching!"),
        "max_comments_per_run": int(get_env("IG_MAX_COMMENTS", "50")),
    })


@app.route("/run", methods=["POST"])
def run():
    auth_error = require_api_key()
    if auth_error:
        return auth_error

    access_token = get_env("IG_ACCESS_TOKEN")
    ig_user_id = get_env("IG_USER_ID")

    if not access_token or not ig_user_id:
        return jsonify({"error": "IG_ACCESS_TOKEN and IG_USER_ID not configured"}), 500

    data = request.get_json(silent=True) or {}
    reply_message = data.get("reply_message", get_env("IG_REPLY_MESSAGE", "Thanks for watching!"))
    already_replied = set(data.get("already_replied", []))
    max_comments = int(data.get("max_comments", get_env("IG_MAX_COMMENTS", "50")))

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
        return jsonify({"error": str(e)}), 500

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
