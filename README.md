# Engineering Analytics Dashboard

An internal platform tool for engineering teams. Ingests GitHub events via webhooks, computes PR health metrics, runs ML-based risk predictions, and surfaces everything in a real-time dashboard — all within your own infrastructure.

```
GitHub Org (webhook/GitHub App)
        │
        ▼
┌─────────────────┐     Redis      ┌──────────────────┐     PostgreSQL
│ Ingestion :8001 │ ──(dedup)────► │ Aggregation :8002│ ◄──────────────┐
│  FastAPI        │                │  FastAPI + ORM   │                │
└─────────────────┘                └──────────────────┘                │
        │  (local dev: HTTP)               │                           │
        │  (production: Azure Service Bus) │                           │
        ▼                                  ▼                           │
┌─────────────────┐              ┌──────────────────┐                  │
│   ML :8003      │◄─────────────│  Dashboard :5173 │                  │
│  GBC model      │  /predict    │  React + Vite    │──────────────────┘
└─────────────────┘              └──────────────────┘
```

## What it does

- **Ingests** `pull_request`, `push`, `pull_request_review`, and `issues` GitHub webhook events
- **Aggregates** PR lifecycle metrics: age, code churn, review lag, merge time, author velocity (7-day rolling)
- **Predicts** PR risk using a GradientBoostingClassifier trained on PR feature patterns — flags PRs likely to stay open beyond 48h
- **Displays** a live dashboard: PR health table with risk badges, author velocity chart, ML model info

## Architecture

| Service | Stack | Port | Role |
|---------|-------|------|------|
| `ingestion-service` | FastAPI + Redis | 8001 | Webhook receiver, dedup, normalizer, publisher |
| `aggregation-service` | FastAPI + SQLAlchemy + PostgreSQL | 8002 | Metric store and query API |
| `ml-service` | FastAPI + scikit-learn | 8003 | GBC risk prediction, model info |
| `frontend` | React + TypeScript + Vite + Recharts | 5173 | Dashboard |

**Infrastructure dependencies:** PostgreSQL 15, Redis 7, Azure Service Bus (optional — HTTP fallback for local dev)

## Quick start (local)

```bash
docker-compose up --build
```

All six containers start (postgres, redis, ingestion, aggregation, ml, frontend). The ML model is trained at image build time.

Open **http://localhost:5173**

### Inject a test PR

```powershell
$headers = @{
  "X-GitHub-Event"    = "pull_request"
  "X-GitHub-Delivery" = "test-001"
  "Content-Type"      = "application/json"
}
$body = '{"action":"opened","pull_request":{"number":1,"id":1001,"title":"My first PR","user":{"login":"alice"},"state":"open","created_at":"2024-01-15T10:00:00Z","updated_at":"2024-01-15T10:00:00Z","merged_at":null,"closed_at":null,"additions":120,"deletions":30,"changed_files":5,"requested_reviewers":[],"head":{"sha":"abc123"},"base":{"ref":"main"}},"repository":{"full_name":"org/repo"}}'
Invoke-RestMethod -Method POST -Uri http://localhost:8001/webhook -Headers $headers -Body $body
```

The PR appears on the dashboard within seconds with an ML risk prediction.

## Connecting your GitHub organization

### Option A — GitHub App (recommended for teams)

1. Go to `github.com/organizations/<your-org>/settings/apps/new`
2. Set the **Webhook URL** to `https://<your-ingestion-host>/webhook`
3. Generate and store a **Webhook secret** as the `GITHUB_WEBHOOK_SECRET` environment variable
4. Subscribe to: `Pull requests`, `Pull request reviews`, `Pushes`, `Issues`
5. Install the app on your organization — all repos are covered automatically

### Option B — Per-repository webhooks (small teams)

In each repo: **Settings → Webhooks → Add webhook**
- Payload URL: `https://<your-ingestion-host>/webhook`
- Content type: `application/json`
- Secret: matches `GITHUB_WEBHOOK_SECRET`
- Events: Pull requests, Pull request reviews, Pushes

## Production deployment

The repo includes GitHub Actions workflows for deploying each service to **Azure Container Apps**.

### Prerequisites

| Secret | Value |
|--------|-------|
| `ACR_LOGIN_SERVER` | e.g. `myregistry.azurecr.io` |
| `ACR_USERNAME` | ACR admin username |
| `ACR_PASSWORD` | ACR admin password |
| `AZURE_CREDENTIALS` | JSON from `az ad sp create-for-rbac` |
| `AZURE_RESOURCE_GROUP` | Resource group containing Container Apps |

### Workflows

| Workflow | Trigger | Deploys |
|----------|---------|---------|
| `ingestion-deploy.yml` | Push to `main` touching `ingestion-service/**` | `engineering-ingestion` Container App |
| `aggregation-deploy.yml` | Push to `main` touching `aggregation-service/**` | `engineering-aggregation` Container App |
| `ml-deploy.yml` | Push to `main` touching `ml-service/**` | `engineering-ml` Container App |

### Required environment variables (production)

**ingestion-service**
```
GITHUB_WEBHOOK_SECRET=<your-secret>
REDIS_URL=rediss://<azure-redis-host>:6380
AZURE_SERVICE_BUS_CONNECTION_STRING=<connection-string>
AGGREGATION_URL=https://<aggregation-container-app-url>
```

**aggregation-service**
```
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>:5432/analytics
AZURE_SERVICE_BUS_CONNECTION_STRING=<connection-string>
```

**ml-service**
```
MODEL_PATH=model.pkl
PREDICTION_THRESHOLD=0.5
```

### Access control

The dashboard has no built-in auth by design — it is meant to sit behind your company's identity perimeter:

- **Azure AD App Proxy** — publish the frontend container app with Entra ID pre-authentication
- **Cloudflare Access** — add a policy requiring corporate SSO in front of the frontend URL
- **VPN-only** — restrict the Container App ingress to your corporate network CIDR

## ML model

The risk model (`GradientBoostingClassifier`, n_estimators=200) predicts whether a PR will remain open beyond 48 hours. Features:

| Feature | Description |
|---------|-------------|
| `review_assignment_lag_hrs` | Hours between PR open and first reviewer assignment |
| `code_churn` | Total lines added + deleted |
| `author_velocity_7d` | Number of PRs the author opened in the past 7 days |
| `reviewer_load` | Active review requests on the reviewer at the time |
| `hour_of_day` | Hour the PR was opened (0–23) |
| `pr_age_hrs` | Current age of the PR |
| `num_review_rounds` | Number of review cycles so far |

The model trains on synthetic data at Docker image build time (~82% accuracy). To retrain on real historical data from your database, run `python train.py --real-data` with `DATABASE_URL` set (to be implemented).

## API reference

### Ingestion (`localhost:8001`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhook` | Receive GitHub webhook event |
| `GET` | `/health` | Service health |

### Aggregation (`localhost:8002`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/prs/open` | List open PRs (`?repo=org/repo&limit=50`) |
| `GET` | `/metrics/pr/{pr_id}` | Full PR lifecycle metrics |
| `GET` | `/metrics/author/{login}` | Author velocity, open PRs, review lag |
| `GET` | `/metrics/repo/{repo}` | Repo throughput and merge time |
| `POST` | `/events` | Direct event ingestion (dev/local fallback) |
| `GET` | `/health` | Service health |

### ML (`localhost:8003`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/predict` | Predict PR risk from feature vector |
| `GET` | `/model/info` | Model version, accuracy, training date |
| `GET` | `/health` | Service health |

## Local development (without Docker)

```bash
# PostgreSQL
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=analytics postgres:15

# Aggregation
cd aggregation-service && pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://postgres:dev@localhost:5432/analytics uvicorn main:app --port 8002 --reload

# ML
cd ml-service && pip install -r requirements.txt
python train.py
uvicorn main:app --port 8003 --reload

# Ingestion
cd ingestion-service && pip install -r requirements.txt
AGGREGATION_URL=http://localhost:8002 uvicorn main:app --port 8001 --reload

# Frontend
cd frontend && npm install && npm run dev
```
