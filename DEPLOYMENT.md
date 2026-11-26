# Private deployment on this Windows PC

The existing React/FastAPI application is served on loopback port 8520. Its research data remains on this PC. No source code or database is published.

## Prepare and verify

Run `prepare_deployment.bat` in this folder. It installs frontend packages from package-lock.json, creates the production build, runs backend tests and runs local authentication/authorization preflight checks. It never starts a public tunnel. Python environment versions are captured in requirements.lock.txt; the existing .venv is used. On another Windows host install Python 3.11, create .venv, and install requirements.lock.txt; securely transfer the required private archive separately. Never transfer credentials in a public repository.

## Start a temporary session

Double-click start_private_demo.bat. Select duration (24 hours default, maximum 48), confirm permission to share the displayed market data, then type SHARE only when you intend to expose the session. A fresh temporary password and HTTPS link appear. Send them separately. Authentication is required before any research API is accessible. Keep the owner console open and the computer awake.

## Stop

Double-click stop_private_demo.bat. Expiration or closing the owner console also revokes access and shuts down its tunnel. The original local dashboard remains available.

## Scope and limitations

This configuration is a private temporary deployment, not unattended cloud hosting. The gateway uses its existing research-only permission set. Full owner controls need a separate access decision; credentials, administration and server files remain blocked. Raw data exports are hidden in shared UI; confirm redistribution permission before starting. Research outputs are not trading probabilities. Historical missing candles remain unavailable. There are no approved prospective prediction models.

The shared UI opens Daily Research and supports full-day KP calculations, exact six-factor slot matches and genuine historical candle charts. Feedback is stored locally outside the market database. Refer to PRIVATE_DEMO.md for storage and security details.

Permanent cloud deployment requires a selected host, domain/TLS, private storage, secrets provisioning, backup and persistent service setup. Do not expose raw uvicorn port 8520 directly or run multiple database-writing workers. No live deployment is performed by preparation.
