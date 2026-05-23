# Pune Real Estate Price Prediction — Production MLOps Project

A production-ready machine-learning API that predicts residential property prices
in Pune, India. Built with **FastAPI**, **scikit-learn**, **MLflow**, **DVC**, and
packaged as a **Docker** container deployable to **AWS ECS Fargate** or **App Runner**.

[![CI](https://github.com/SHADRACK-NAKOBA/pune-price-prediction/actions/workflows/ci.yml/badge.svg)](https://github.com/SHADRACK-NAKOBA/pune-price-prediction/actions/workflows/ci.yml)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                    DATA & TRAINING PIPELINE                        │
│                                                                    │
│  Pune RE Data.xlsx                                                 │
│        │  (mlops/clean_data.py)                                    │
│        ▼                                                           │
│  data_cleaned.csv                                                  │
│        │  (mlops/build_features.py)                                │
│        ▼                                                           │
│  model_features.csv + helper .pkl files                            │
│        │  (mlops/train.py ← params.yaml)                           │
│        ▼                                                           │
│  VotingRegressor .sav + interval_est.pkl                           │
│        │                                                           │
│        ├──── MLflow tracks every run ────→ mlflow.db / DagsHub    │
│        └──── DVC versions data/models ──→ DVC remote / DagsHub    │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                       SERVING LAYER                                │
│                                                                    │
│  Browser (frontend/index.html)                                     │
│        │  POST /predict  JSON payload                              │
│        ▼                                                           │
│  [Nginx reverse proxy] ← optional                                  │
│        │                                                           │
│        ▼                                                           │
│  FastAPI (src/app.py)                                              │
│        │                                                           │
│        ▼                                                           │
│  src/inference.py                                                  │
│    1. Clean & tokenise description (NLTK)                          │
│    2. Target-encode location + amenities                           │
│    3. CountVectoriser → text features                              │
│    4. Assemble 115-D feature vector                                │
│    5. VotingRegressor.predict() → price (Rs lakhs)                 │
│    6. ±z·sigma → 95% prediction interval                           │
│        │                                                           │
│        ▼                                                           │
│  JSON: predicted_price, lower_bound, upper_bound, features_used    │
│        │                                                           │
│        ▼                                                           │
│  Browser (frontend/results.html)                                   │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                  CLOUD DEPLOYMENT (AWS)                            │
│                                                                    │
│  Docker image → ECR → ECS Fargate  (or App Runner / EC2)          │
│  Secrets → AWS Secrets Manager                                     │
│  Logs    → CloudWatch                                              │
│  Domain  → Route 53 + ACM (HTTPS)                                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Lab History

| Lab | Output |
|---|---|
| Lab 1 | `data_cleaned.csv` — Excel cleaning (DVC stage: `clean`) |
| Lab 2 | `model_features.csv`, `model_target.npy`, helper `.pkl` files (DVC stage: `features`) |
| Lab 3 | `VotingRegressor.sav`, `interval_est.pkl` (DVC stage: `train`) |
| Lab 4 | FastAPI service (`src/`) + browser frontend (`frontend/`) |
| Lab 5 | MLOps tooling — MLflow / DVC / DagsHub (`mlops/`, `dvc.yaml`, `params.yaml`) |
| Production | Docker, CI/CD, AWS ECS / App Runner, monitoring, tests |

---

## Quick Start

### Option A — Run locally (Python)

```bash
# Clone
git clone https://github.com/SHADRACK-NAKOBA/pune-price-prediction.git
cd pune-price-prediction

# Create virtual environment
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt

# Pull model artifacts from DVC remote (if not already on disk)
pip install -r requirements-mlops.txt
dvc pull model/ --force

# Start the API
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/docs (Swagger UI) or open `frontend/index.html` in a browser.

### Option B — Run with Docker (single command)

```bash
cp .env.example .env   # fill in values (AWS fields can be blank for local dev)
docker compose up
```

| URL | Service |
|---|---|
| http://localhost:8000/docs | FastAPI Swagger UI |
| http://localhost:8000/health | Health check |
| http://localhost:5000 | MLflow UI (add `--profile mlops`) |

### Option C — Full stack with Nginx proxy

```bash
docker compose --profile proxy up
# API available at http://localhost:80
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe — used by Docker, ALB, App Runner |
| `GET` | `/model/info` | Model type, vocabulary size, interval margin |
| `POST` | `/predict` | Full inference: price + 95% confidence interval |
| `GET` | `/docs` | Interactive Swagger UI (auto-generated) |
| `GET` | `/redoc` | ReDoc API documentation |

### `POST /predict` — Request

```json
{
  "property_type": 2,
  "area": 1000.0,
  "sub_area": "kothrud",
  "description": "spacious 2bhk apartment near park with good ventilation",
  "clubhouse": 1,
  "school": 1,
  "hospital": 0,
  "mall": 1,
  "park": 1,
  "pool": 0,
  "gym": 1
}
```

| Field | Type | Description |
|---|---|---|
| `property_type` | int | Number of bedrooms (1, 2, 3, …) |
| `area` | float | Area in square feet |
| `sub_area` | string | Neighbourhood name (e.g. "kothrud", "baner") |
| `description` | string (optional) | Free-text property description |
| `clubhouse` … `gym` | int | 1 = amenity present, 0 = absent |

### `POST /predict` — Response

```json
{
  "predicted_price": 62.3,
  "lower_bound": 30.94,
  "upper_bound": 93.66,
  "features_used": 115
}
```

All prices are in **Rs lakhs** (1 lakh = Rs 100,000).

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | Server port |
| `CORS_ORIGINS` | `*` | Comma-separated allowed CORS origins |
| `MLFLOW_TRACKING_URI` | `sqlite:///mlflow.db` | MLflow backend store |
| `MLFLOW_EXPERIMENT_NAME` | `M2_Pune_Real_Estate_Price` | MLflow experiment name |
| `DAGSHUB_USER` | — | DagsHub username (for remote DVC + MLflow) |
| `DAGSHUB_TOKEN` | — | DagsHub access token |
| `DAGSHUB_REPO` | — | DagsHub repository name |
| `AWS_ACCOUNT_ID` | — | 12-digit AWS account ID |
| `AWS_REGION` | `us-east-1` | AWS deployment region |
| `ECR_REPO_NAME` | `pune-price-prediction` | ECR repository name |

Copy `.env.example` to `.env` and fill in values. The `.env` file is git-ignored.

---

## Running Tests

```bash
pip install pytest pytest-cov
pytest tests/ -v --cov=src --cov-report=term-missing
```

Tests run **without model files on disk** — `tests/conftest.py` patches all model
loading with in-memory mocks so CI works on a clean checkout.

```
tests/test_schemas.py    — 20 tests (Pydantic model validation)
tests/test_inference.py  — 22 tests (prediction pipeline, interval math)
```

---

## Model Performance

| Metric | Value |
|---|---|
| Test R² | 0.852 |
| Test RMSE | Rs 15.75 lakhs |
| Test MAE | Rs 11.46 lakhs |
| 95% prediction interval width | ±Rs 31.35 lakhs |
| Train / test split | 159 / 40 (seed=42) |
| Feature dimensions | 115 |

**Model:** VotingRegressor (LinearRegression + Ridge(alpha=10) + Lasso(alpha=0.1)),
equal weights. An alpha sweep finds R²=0.854 at alpha=10, confirming the default
`params.yaml` is near-optimal for this 200-sample dataset.

---

## MLOps Tooling

```bash
pip install -r requirements-mlops.txt

# Reproduce the full pipeline
dvc repro
dvc metrics show

# Track one experiment in MLflow
python -m mlops.mlflow_train

# Sweep Ridge alpha and find the best
python -m mlops.mlflow_sweep
python -m mlops.mlflow_query

# Open MLflow UI
mlflow ui --backend-store-uri sqlite:///mlflow.db
# → http://localhost:5000

# AutoML benchmark
python -m mlops.pycaret_benchmark

# Use DagsHub as remote MLflow + DVC backend
export DAGSHUB_USER=...  DAGSHUB_TOKEN=...  DAGSHUB_REPO=...
python -m mlops.dagshub_setup --check
```

---

## Deploying to AWS

**Fastest path (App Runner):**

```bash
# 1. Build and push to ECR
docker build -t pune-price-prediction .
docker tag pune-price-prediction:latest \
  YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction:latest
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction:latest

# 2. Deploy (one command — no cluster setup required)
aws apprunner create-service \
  --service-name pune-price-prediction \
  --source-configuration "..." \
  --instance-configuration "Cpu=1 vCPU,Memory=2 GB"
```

For the complete guide covering ECS Fargate, EC2, custom domain + HTTPS,
CloudWatch monitoring, Secrets Manager, and DagsHub integration, see:

**[Nakoba's Production Steps/PROD_STEPS.md](Nakoba's%20Production%20Steps/PROD_STEPS.md)**

For deep internals (every file explained, ML math, pipeline walkthrough):

**[Nakoba's Build Steps/BUILD_STEPS.md](Nakoba's%20Build%20Steps/BUILD_STEPS.md)**

---

## Project Structure

```
pune-price-prediction/
├── frontend/                        # Static browser UI (Lab 4)
├── src/                             # FastAPI service (Lab 4)
│   ├── app.py                       # Routes + CORS
│   ├── inference.py                 # Full prediction pipeline
│   └── schemas.py                   # Pydantic I/O models
├── tests/                           # Automated unit tests
│   ├── conftest.py                  # Session-level mocks
│   ├── test_schemas.py              # 20 schema validation tests
│   └── test_inference.py            # 22 inference tests
├── mlops/                           # MLOps scripts (Lab 5)
├── model/                           # Trained artifacts (DVC-tracked)
├── metrics/                         # DVC-readable JSON metrics
├── infra/
│   ├── aws/                         # ECS task def, CodeBuild, App Runner
│   └── docker/                      # Nginx config
├── .github/workflows/ci.yml         # CI: pytest + Docker build
├── Nakoba's Build Steps/BUILD_STEPS.md
├── Nakoba's Production Steps/PROD_STEPS.md
├── Dockerfile                       # Multi-stage, non-root, health check
├── docker-compose.yml               # API + Nginx + MLflow
├── .env.example                     # All environment variables documented
├── params.yaml                      # All hyperparameters
├── dvc.yaml                         # 3-stage DVC pipeline
├── requirements.txt                 # API production dependencies
└── requirements-mlops.txt           # MLOps tooling dependencies
```

---

## Resetting MLflow (start clean)

```powershell
# Windows PowerShell — stop mlflow ui first (Ctrl+C), then:
Remove-Item -Force .\mlflow.db
Remove-Item -Recurse -Force .\mlruns
```
```bash
# macOS / Linux
rm -f mlflow.db && rm -rf mlruns
```

Restart: `mlflow ui --backend-store-uri sqlite:///mlflow.db`

---

## Reproducibility

A teammate can reproduce the entire pipeline with:

```bash
git clone https://github.com/SHADRACK-NAKOBA/pune-price-prediction.git
cd pune-price-prediction
pip install -r requirements.txt -r requirements-mlops.txt
dvc pull         # fetch data + model from DVC remote
dvc repro        # re-run pipeline → identical metrics
dvc metrics show # verify: r2=0.852, rmse=15.75
```

---

## License

For training and educational use as part of the MLOps course (Module 2).
The Pune real estate dataset is proprietary and not redistributed.
