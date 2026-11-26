# Source repository and local runtime data

GitHub should contain source code, frontend package-lock.json, tests and project configuration. Do not upload the whole Windows folder as a ZIP.

The local .venv, web/node_modules, web/dist, archive, databases, model bundles, credentials and verification outputs are excluded by .gitignore. Install dependencies and rebuild the frontend on the deployment host. The Git-tracked content measured approximately 1.43 MiB after this cleanup, rather than the size shown for the entire working folder.

Historical KP archive and genuine market candles are required runtime data and must be transferred privately to a backend with persistent storage. Excluding these from GitHub does not mean the cloud app automatically receives them. Vercel frontend deployment still needs the backend/storage architecture resolved.

Candidate legacy artifacts: archive/ml (first-generation classification), archive/movement (first-generation endpoint models), UI/screen*.png (old UI references), baseline-20261120-124619.zip and migration-baseline.zip. Physical cleanup was blocked by the execution approval policy; these files have not been deleted or moved. Existing research endpoints still refer to first-generation movement artifacts, so deleting them requires accepting unavailable results there or removing those legacy endpoints. Current KP slot matching depends on archive/full-day-kp and archive/research.duckdb; preserve both. Current historical forecast routes also use archive/movement-v2 and archive/trajectory.

No GitHub remote was configured when preparing this repository. Supply the destination repository URL and authenticate with GitHub before pushing. Prefer private visibility. Never commit provider tokens or licensed raw market datasets.

Destination: https://github.com/shashwat-dev1/nifty.git. Generated reports and old UI screenshots were removed from Git tracking but preserved locally.
