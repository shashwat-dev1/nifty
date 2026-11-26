# Vercel, Render Free and Firestore

Firebase project: `nifty-kp-research-20261126`. No Firebase Storage or Blaze billing is required by this configuration.

## Architecture

Vercel root directory: `web`. Set `VITE_CLOUD=1`. The same-origin Node gateway checks the access password and forwards allowed research requests to Render using a separate server key. Render uses `Dockerfile` and `render.yaml`, restoring an immutable Firestore snapshot before starting one Uvicorn worker.

Opening the site asks for a password and then wakes Render with health requests. Each request is bounded; retries stop after five minutes or successful readiness. Closing the page cancels polling. There is no idle keep-alive service.

Firestore rules deny browser access. Server credentials use IAM and must remain outside source code. Feedback is durable in `research_feedback`. Historical snapshots use 384 KiB binary chunks encoded below the document-size limit, with a manifest published last. The compressed snapshot budget is 128 MiB. Every cold start consumes one manifest read and one read per chunk. Free-tier suitability depends on measured snapshot size and restart frequency; it is not unlimited.

## Prepare private data

Stop the local dashboard before running `python cloud_snapshot.py` so DuckDB can take an exclusive checkpoint. SQLite is copied with its backup API. Restart the dashboard afterward. Install `requirements-cloud.txt` locally before uploading. With server credentials configured privately and a new `FIREBASE_SNAPSHOT_ID`, run `python cloud_snapshot.py --upload`. Configure the printed checksum independently on Render. No dataset belongs in GitHub.

The cloud snapshot does not persist local changes. Publish a new snapshot to extend historical coverage. On-demand current-day KP calculations still work. Background downloads and prospective generation remain disabled; missing forecasts remain unavailable.

## Render environment

- `BACKEND_API_KEY`: random secret of at least 32 characters.
- `FIREBASE_SERVICE_ACCOUNT_JSON`: server-only credential JSON.
- `FIREBASE_SNAPSHOT_ID`: immutable snapshot ID.
- `FIREBASE_SNAPSHOT_SHA256`: checksum from the snapshot tool.
- `NIFTY_ALLOWED_HOSTS`: configured by the Blueprint.

Health path: `/api/health`. The backend fails startup if the snapshot is missing or corrupt. Administrative and file routes are blocked.

## Vercel environment

- `BACKEND_ORIGIN`: Render HTTPS origin, without a path.
- `BACKEND_API_KEY`: same key as Render.
- `DEMO_PASSWORD_VERIFIER`: salted scrypt verifier.
- `SESSION_SECRET`: independent random signing secret.
- `VITE_CLOUD=1`: public cloud-mode flag; never use VITE-prefixed secrets.

Run `python cloud_secrets.py` locally to generate fresh values. Cookies are Secure, HttpOnly, SameSite=Strict and expire after 24 hours. Rotating SESSION_SECRET revokes access.

## Acceptance

Verify a deployed preview with real calculations, six-factor matches, market candles, chart selection, durable feedback, failed login, denied administration and waking after actual Render sleep before claiming completion. Local simulated wake tests do not establish live provider behavior.
