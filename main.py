import os
import hmac
import hashlib
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

if not all([SUPABASE_URL, SUPABASE_KEY, WEBHOOK_SECRET]):
    raise RuntimeError("Missing required environment variables. Check p1.env.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


def verify_signature(body: bytes, signature: Optional[str]) -> bool:
    if not signature:
        return False
    expected = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_push(payload: dict) -> dict:
    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "")
    commits = payload.get("commits", [])
    return {
        "github_username": payload.get("pusher", {}).get("name"),
        "repo_name": payload.get("repository", {}).get("full_name"),
        "event_type": "push",
        "event_action": "pushed",
        "event_time": payload.get("head_commit", {}).get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "branch_name": branch,
        "commit_count": len(commits),
        "source_url": payload.get("compare"),
    }


def parse_pull_request(payload: dict) -> dict:
    pr = payload.get("pull_request", {})
    action = payload.get("action")
    if action == "closed" and pr.get("merged"):
        action = "merged"
    return {
        "github_username": payload.get("sender", {}).get("login"),
        "repo_name": payload.get("repository", {}).get("full_name"),
        "event_type": "pull_request",
        "event_action": action,
        "event_time": pr.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        "branch_name": pr.get("head", {}).get("ref"),
        "pr_number": pr.get("number"),
        "safe_title": (pr.get("title") or "")[:300],
        "source_url": pr.get("html_url"),
    }


def parse_issues(payload: dict) -> dict:
    issue = payload.get("issue", {})
    return {
        "github_username": payload.get("sender", {}).get("login"),
        "repo_name": payload.get("repository", {}).get("full_name"),
        "event_type": "issues",
        "event_action": payload.get("action"),
        "event_time": issue.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        "issue_number": issue.get("number"),
        "safe_title": (issue.get("title") or "")[:300],
        "source_url": issue.get("html_url"),
    }


def parse_workflow_run(payload: dict) -> dict:
    run = payload.get("workflow_run", {})
    return {
        "github_username": payload.get("sender", {}).get("login"),
        "repo_name": payload.get("repository", {}).get("full_name"),
        "event_type": "workflow_run",
        "event_action": payload.get("action"),
        "event_time": run.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        "branch_name": run.get("head_branch"),
        "safe_title": (run.get("name") or "")[:300],
        "workflow_status": run.get("conclusion") or run.get("status"),
        "source_url": run.get("html_url"),
    }


PARSERS = {
    "push": parse_push,
    "pull_request": parse_pull_request,
    "issues": parse_issues,
    "workflow_run": parse_workflow_run,
}


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default=None),
    x_hub_signature_256: str = Header(default=None),
):
    body = await request.body()

    if not verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="invalid signature")

    if x_github_event not in PARSERS:
        return {"accepted": True, "stored": False, "reason": "unsupported event"}

    payload = json.loads(body)
    event = PARSERS[x_github_event](payload)

    key = f"{event['event_type']}-{event.get('repo_name')}-{event.get('event_time')}-{event.get('pr_number')}-{event.get('issue_number')}"
    event["raw_event_hash"] = hashlib.sha256(key.encode()).hexdigest()

    try:
        supabase.table("work_events").insert(event).execute()
        stored = True
    except Exception as e:
        if "duplicate key" in str(e):
            stored = False  # already recorded, safe to ignore
        else:
            raise

    return {"accepted": True, "stored": stored}


@app.get("/events/user/{username}")
def get_events(username: str):
    result = (
        supabase.table("work_events")
        .select("*")
        .eq("github_username", username)
        .order("event_time", desc=True)
        .limit(200)
        .execute()
    )
    return result.data