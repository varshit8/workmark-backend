# Webhook Event Smoke Test

This repo is being used to verify the GitHub to Render to Supabase flow:

1. GitHub event occurs in `varshit8/workmark-backend`.
2. GitHub sends a webhook to Render at `/webhook/github`.
3. The FastAPI app parses the event.
4. The app inserts a row into Supabase table `work_events`.
5. Rows can be checked in Supabase Table Editor under `work_events`.

## Repo Changes Made So Far

- Removed invalid dependencies from `requirements.txt`: `install==1.3.5` and `comtypes==1.1.11`.
- Replaced `requirements.txt` with the minimal six-package dependency set.
- Added `.python-version` with `3.11.9` so Render uses Python 3.11.
- Added `webhook-smoke-test.md` on branch `agent/webhook-smoke-test-20260719`.
- Opened draft PR #1 from `agent/webhook-smoke-test-20260719` into `main`.
- Created issue #2 as a webhook smoke-test issue.

## Additional Events Triggered

- This file was added to trigger another branch push event.
- Pushing this commit should also trigger a pull request synchronize event for PR #1.
