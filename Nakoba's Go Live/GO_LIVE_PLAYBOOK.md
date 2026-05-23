# GO LIVE PLAYBOOK
## Pune Real Estate Price Prediction — Production Deployment Guide
### Author: Nakoba (SHADRACK-NAKOBA) · Sole Contributor

---

> **How to use this document:**
> Work top to bottom. Every command is copy-paste ready.
> Replace every `<< VALUE >>` placeholder before running.
> After each major step, confirm the SUCCESS indicator before continuing.
> If you see a known error, jump to the FIX shown inline or Section 14.

---

## SECTION 0 — WHAT THIS PROJECT IS

### 0.1 Plain-English Description

**Problem:** Real estate agents and buyers in Pune, India have no fast, data-driven
way to estimate a fair market price for a residential property. Traditional appraisals
are slow, expensive, and inconsistent.

**Solution:** A machine-learning API that takes the basic facts about a property —
number of bedrooms, area in square feet, neighbourhood, amenities, and a short
description — and returns an estimated price in Indian Rupees (lakhs) together with
a 95% confidence interval in under two seconds.

A property buyer visits `frontend/index.html`, fills in the form, submits, and sees:

```
Predicted price:  ₹ 62.30 lakhs
Confidence range: ₹ 30.94 lakhs  →  ₹ 93.66 lakhs
```

The ML model (a VotingRegressor combining Linear Regression, Ridge, and Lasso) was
trained on 200 Pune residential properties and achieves R² = 0.852 on the test set.
The 95% interval is derived from training-set residuals (z = 1.96 × σ_residuals).

The entire stack — data pipeline, model training, API, Docker image, CI/CD, and
cloud deployment — is managed by one person: Nakoba.

---

### 0.2 Full Architecture Diagram

```
═══════════════════════════════════════════════════════════════════════
  DATA & TRAINING PIPELINE
═══════════════════════════════════════════════════════════════════════

  Pune Real Estate Data.xlsx
        │
        │  mlops/clean_data.py   (DVC stage: clean)
        ▼
  data_cleaned.csv
        │
        │  mlops/build_features.py   (DVC stage: features)
        ▼
  model_features.csv   model_target.npy
  model/count_vectorizer.pkl
  model/sub_area_price_map.pkl
  model/amenities_score_price_map.pkl
  model/all_feature_names.pkl
        │
        │  mlops/train.py   (DVC stage: train)   ← params.yaml
        ▼
  model/property_price_prediction_voting.sav   ← VotingRegressor
  model/interval_est.pkl                       ← z=1.96, σ_residuals
  metrics/train_metrics.json                   ← R²=0.852, RMSE=15.75

═══════════════════════════════════════════════════════════════════════
  MLOPS LAYER
═══════════════════════════════════════════════════════════════════════

  DVC  ──── versions ────► model_features.csv, model/*.pkl, model/*.sav
    │                       stored on DagsHub S3 remote
    │
  MLflow ── tracks ────────► params, metrics, plots, model artifacts
    │                        stored on DagsHub MLflow server
    │
  DagsHub ─────────────────► unified remote: DVC + MLflow in one place
                             https://dagshub.com/SHADRACK-NAKOBA/<< REPO >>

═══════════════════════════════════════════════════════════════════════
  SERVING LAYER
═══════════════════════════════════════════════════════════════════════

  Browser (frontend/index.html)
        │  POST /predict  { property_type, area, sub_area, ... }
        ▼
  [Optional: Nginx reverse proxy  — docker compose --profile proxy]
        │
        ▼
  FastAPI  src/app.py  port 8000
        │
        ▼
  src/inference.py   (loads 6 artifacts once at startup)
    1. Clean + tokenise description text          (NLTK)
    2. POS-tag → noun/verb/adj counts             (NLTK)
    3. Target-encode sub_area                     (sub_area_price_map)
    4. Compute + encode amenity score             (amenities_map)
    5. Vectorise description                      (CountVectorizer)
    6. Assemble 115-dim feature vector
    7. VotingRegressor.predict()  → price (₹ lakhs)
    8. ± z·σ  → 95% prediction interval
        │
        ▼
  JSON response:
  { "predicted_price": 62.3,
    "lower_bound": 30.94, "upper_bound": 93.66, "features_used": 115 }
        │
        ▼
  Browser (frontend/results.html)

═══════════════════════════════════════════════════════════════════════
  CI/CD LAYER
═══════════════════════════════════════════════════════════════════════

  git push → main
        │
        ▼
  GitHub Actions  .github/workflows/ci.yml
    Job 1: lint          ruff + black (every push)
    Job 2: test          pytest 42 tests (every push)
    Job 3: docker-build  build + smoke test (every push)
    Job 4: deploy        ECR push + ECS update  (manual trigger only)

═══════════════════════════════════════════════════════════════════════
  CLOUD LAYER
═══════════════════════════════════════════════════════════════════════

  GitHub Actions
        │  docker build + docker push
        ▼
  AWS ECR  (Elastic Container Registry)
  << AWS_ACCOUNT_ID >>.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction
        │
        ├──────────────────────────────────────┐
        │  Primary (Section 7)                 │  Fast path (Section 6)
        ▼                                      ▼
  AWS ECS Fargate                        AWS App Runner
  Cluster: pune-price-cluster            Service: pune-price-prediction
  Service: pune-price-service            Auto TLS, auto-scale
  ALB → Target Group → Task             https://<id>.awsapprunner.com
  VPC + Security Groups
  IAM Task Role
        │                                      │
        └──────────────┬───────────────────────┘
                       ▼
             AWS Secrets Manager
             pune-price/dagshub-token
             pune-price/mlflow-tracking-uri

═══════════════════════════════════════════════════════════════════════
  MONITORING LAYER
═══════════════════════════════════════════════════════════════════════

  ECS Task / App Runner
        │  stdout / stderr
        ▼
  CloudWatch Logs  /ecs/pune-price-prediction
        │
        ▼
  CloudWatch Alarms
    ├── pune-price-task-stopped     (RunningTaskCount < 1)
    ├── pune-price-high-cpu         (CPUUtilization > 80%)
    ├── pune-price-5xx-errors       (5xx count > 10 / 5 min)
    └── pune-price-billing-alert    (EstimatedCharges > $50/day)
        │
        ▼
  SNS Topic: pune-price-alerts
        │
        ▼
  Email → shadrack.n159@gmail.com
```

---

### 0.3 What "Go Live" Means for This Project

The project is **live in production** when ALL of these are true:

| Check | Definition of Done |
|---|---|
| FastAPI live at HTTPS URL | `curl https://<YOUR_URL>/health` returns HTTP 200 |
| Predictions working | `POST /predict` returns JSON with `predicted_price` |
| Docker image in ECR | `aws ecr describe-images` shows image pushed within 24 h |
| Container running | ECS service or App Runner service status = RUNNING |
| Secrets not in code | `grep -r "dagshub_token" src/` returns nothing |
| Secrets in Secrets Manager | `aws secretsmanager list-secrets` shows at least 2 secrets |
| CloudWatch receiving logs | Log group has events within last 5 minutes |
| CI is green | GitHub Actions shows ✅ on latest main commit |
| DVC artifacts pullable | `dvc pull` on a fresh clone downloads all model files |
| MLflow on DagsHub | Experiments tab shows at least one run |

---

### 0.4 Who Does What

| Role | Responsibility |
|---|---|
| **Nakoba (you)** | Sole owner, deployer, on-call engineer |
| **GitHub Actions** | Lint, test, Docker build, ECR push, ECS update |
| **DVC** | Data + model artifact versioning and remote storage |
| **MLflow / DagsHub** | Experiment tracking, model registry, team visibility |
| **AWS ECR** | Versioned Docker image storage |
| **AWS ECS Fargate** | Running the FastAPI container (production path) |
| **AWS App Runner** | Simpler alternative — one command to a live HTTPS URL |
| **AWS Secrets Manager** | Secure runtime secret delivery to the container |
| **AWS CloudWatch** | Logs, metrics, alarms, billing alerts |
| **AWS Route 53 + ACM** | Custom domain + free TLS certificate |

---

## SECTION 1 — PREREQUISITES

### Tools Required

#### Python 3.11

- **Why:** The project was built and tested on Python 3.11. Other versions may have
  dependency conflicts with scikit-learn 1.3 and pydantic 2.

```powershell
# Windows PowerShell
winget install --id Python.Python.3.11
# Restart terminal after install
python --version   # Python 3.11.x
```
```bash
# macOS
brew install python@3.11
python3.11 --version   # Python 3.11.x

# Linux (Ubuntu/Debian)
sudo apt-get install python3.11 python3.11-venv python3.11-dev -y
```
**Minimum version:** 3.11.0

---

#### Git

- **Why:** Version control + GitHub remote for code, CI/CD, DVC pointer files.

```powershell
# Windows
winget install --id Git.Git
git --version   # git version 2.x
```
```bash
# macOS
brew install git

# Linux
sudo apt-get install git -y
```
**Minimum version:** 2.30

---

#### Docker Desktop

- **Why:** Build and test the container image locally before pushing to ECR.

```powershell
# Windows — download installer
Start-Process "https://docs.docker.com/desktop/install/windows-install/"
# After install, start Docker Desktop from the Start menu
docker --version   # Docker version 24.x
```
```bash
# macOS
brew install --cask docker
# Open Docker.app from Applications first time

# Linux (Ubuntu)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # log out and back in after this
```
**Minimum version:** 24.0

---

#### AWS CLI v2

- **Why:** All AWS operations (ECR, ECS, Secrets Manager, CloudWatch) are done
  via CLI. v2 is required — v1 has incompatible ECR login commands.

```powershell
# Windows
winget install --id Amazon.AWSCLI
aws --version   # aws-cli/2.x Python/3.11.x
```
```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install
```
**Minimum version:** 2.0.0

---

#### DVC

- **Why:** Pull model artifacts (`.pkl`, `.sav`) from DagsHub remote. Without DVC
  you cannot run `dvc pull` and the Docker image build fails.

```powershell
# Windows (inside your virtual environment)
pip install "dvc[s3]"
dvc --version   # 3.x.x
```
```bash
# macOS / Linux (inside virtual environment)
pip install "dvc[s3]"
```
**Minimum version:** 3.0.0

---

### All-in-One Verification Block

Run all 5 lines. Every one must print a version number before continuing.

```powershell
# Windows PowerShell
python --version      # Python 3.11.x
git --version         # git version 2.x.x
docker --version      # Docker version 24.x.x
aws --version         # aws-cli/2.x.x
dvc --version         # 3.x.x
```
```bash
# macOS / Linux
python3 --version && git --version && docker --version && aws --version && dvc --version
```

---

### AWS Account Prerequisites

#### 1. Create an IAM user with programmatic access

1. Open https://console.aws.amazon.com/iam/
2. Users → Add users → Username: `nakoba-deploy`
3. Permissions → Attach policies directly
4. Attach ALL of these:
   - `AmazonEC2ContainerRegistryFullAccess`
   - `AmazonECS_FullAccess`
   - `AmazonS3FullAccess`
   - `SecretsManagerReadWrite`
   - `CloudWatchFullAccess`
   - `AWSAppRunnerFullAccess`
   - `AmazonEC2FullAccess` (needed for VPC/subnets/security groups)
5. Next → Create user
6. Click the user → Security credentials → Create access key → CLI
7. **Download the CSV** — you cannot see the secret key again after this screen

#### 2. Configure AWS CLI

```bash
aws configure
# AWS Access Key ID:     << paste from CSV >>
# AWS Secret Access Key: << paste from CSV >>
# Default region name:   us-east-1
# Default output format: json
```

#### 3. Verify identity

```bash
aws sts get-caller-identity
```

**Expected output:**
```json
{
    "UserId": "AIDA...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/nakoba-deploy"
}
```

**Save your `Account` value** — you will use it as `<< AWS_ACCOUNT_ID >>` throughout.

#### 4. Enable billing alerts (prevents surprise charges)

```bash
# Enable billing metrics — run ONCE per account (must be in us-east-1)
aws cloudwatch enable-insight-rules --region us-east-1 2>/dev/null || true

# Billing alarms only work in us-east-1
# The billing alarm is created in Section 9.6
```

---

## SECTION 2 — GET THE CODE AND TEST LOCALLY

### 2.1 Clone the Repository

```powershell
# Windows PowerShell
git clone https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction.git
cd Nakoba-pune-price-prediction
```
```bash
# macOS / Linux
git clone https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction.git
cd Nakoba-pune-price-prediction
```

**SUCCESS:** You see these folders: `src/  frontend/  tests/  mlops/  infra/  model/`

---

### 2.2 Create Virtual Environment and Install Dependencies

```powershell
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
```bash
# macOS / Linux
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**SUCCESS:** `pip list | grep fastapi` shows `fastapi 0.100+`

**Common error:** `python : The term 'python' is not recognized`
**Fix (Windows):** Use `py -3.11 -m venv .venv` instead.

---

### 2.3 Pull Model Artifacts from DVC

The trained model files (`.pkl`, `.sav`) are too large for Git — they live on DVC
remote storage. You must pull them before the app can start.

```bash
pip install -r requirements-mlops.txt
dvc pull model/ --force
```

**Expected output:**
```
M  model/property_price_prediction_voting.sav
M  model/interval_est.pkl
M  model/count_vectorizer.pkl
M  model/sub_area_price_map.pkl
M  model/amenities_score_price_map.pkl
M  model/all_feature_names.pkl
6 files fetched
```

**Common error:** `Authentication failed` or `ERROR: failed to pull data`
**Fix:** DVC remote credentials not set. Run:
```bash
python -m mlops.dagshub_setup --print-dvc-cmds
# Run the dvc remote modify commands it prints, then retry dvc pull
```

If you do not have DagsHub credentials yet, see Section 10 first.

---

### 2.4 Configure Environment

```powershell
# Windows PowerShell
Copy-Item .env.example .env
notepad .env
```
```bash
# macOS / Linux
cp .env.example .env
nano .env   # or: code .env
```

**Minimum `.env` values for local development** (AWS fields can stay blank):

```dotenv
PORT=8000
CORS_ORIGINS=*
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
MLFLOW_EXPERIMENT_NAME=M2_Pune_Real_Estate_Price

# Leave these blank for local dev — only needed for DagsHub integration
DAGSHUB_USER=
DAGSHUB_TOKEN=
DAGSHUB_REPO=

# Leave blank for local dev — only needed for AWS deploy
AWS_ACCOUNT_ID=
AWS_REGION=us-east-1
ECR_REPO_NAME=pune-price-prediction
```

---

### 2.5 Start the API Locally

```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Started reloader process [12345]
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

### 2.6 Verify All Endpoints Work

**Test /health:**

```powershell
# Windows PowerShell
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET
```
```bash
# macOS / Linux
curl http://localhost:8000/health
```
**Expected:** `{"status":"API is healthy and running."}`

---

**Test /predict:**

```powershell
# Windows PowerShell
$body = '{"property_type":2,"area":1000,"sub_area":"kothrud","description":"spacious 2bhk apartment","clubhouse":1,"school":1,"hospital":0,"mall":1,"park":1,"pool":0,"gym":1}'
Invoke-RestMethod -Uri "http://localhost:8000/predict" `
  -Method POST -Body $body -ContentType "application/json"
```
```bash
# macOS / Linux
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"property_type":2,"area":1000,"sub_area":"kothrud","description":"spacious 2bhk apartment","clubhouse":1,"school":1,"hospital":0,"mall":1,"park":1,"pool":0,"gym":1}'
```
**Expected:**
```json
{"predicted_price":62.3,"lower_bound":30.94,"upper_bound":93.66,"features_used":115}
```

---

**Test browser UIs:**

- Open http://localhost:8000/docs — Swagger UI must load and show 3 routes
- Open `frontend/index.html` in a browser, fill in the form, submit

---

### 2.7 Run the Full Test Suite

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

**Expected:**
```
tests/test_inference.py::TestGetPredictionInterval::test_symmetric_interval PASSED
...
tests/test_schemas.py::TestModelInfoResponse::test_integer_vocab_size PASSED

============== 36 passed in 0.36s ==============
```

**Common error:** `ModuleNotFoundError: No module named 'fastapi'`
**Fix:** Virtual environment is not activated. Run:
```powershell
# Windows
.venv\Scripts\Activate.ps1
```
```bash
# macOS / Linux
source .venv/bin/activate
```

---

## SECTION 3 — PUSH TO GITHUB AS SOLE CONTRIBUTOR

### 3.1 Configure Git Identity

```bash
git config --global user.name  "Nakoba"
git config --global user.email "<< YOUR_EMAIL >>"
```

Verify:
```bash
git config --global user.name   # Nakoba
git config --global user.email  # << YOUR_EMAIL >>
```

---

### 3.2 Navigate to Project Root

```powershell
# Windows PowerShell
cd "C:\Users\admin\Desktop\mlops-pune-price-prediction"
```
```bash
# macOS / Linux
cd ~/Desktop/mlops-pune-price-prediction
```

---

### 3.3 CRITICAL Security Check — Run Before Staging Anything

```powershell
# Windows PowerShell — verify .env is ignored
Get-Content .gitignore | Select-String ".env"
# Must show: .env

Get-Content .gitignore | Select-String ".pem"
# Must show: *.pem

Get-Content .gitignore | Select-String "mlruns"
# Must show: mlruns/
```
```bash
# macOS / Linux
grep ".env"   .gitignore   # must show: .env
grep ".pem"   .gitignore   # must show: *.pem
grep "mlruns" .gitignore   # must show: mlruns/
```

If `.env` is missing from `.gitignore` — **STOP**. Add it first:
```bash
echo ".env" >> .gitignore
git add .gitignore
```

---

### 3.4 Stage All Files

```bash
git add .
```

---

### 3.5 Verify Staged Files — These Must NOT Appear

```bash
git status
```

**These must NOT be in the staged list:**
```
❌  .env                          (secrets — must be git-ignored)
❌  *.pem                         (SSH keys — must be git-ignored)
❌  mlruns/                       (MLflow local store — must be git-ignored)
❌  model/*.pkl or model/*.sav    (DVC-tracked — only .dvc pointer files go to Git)
❌  mlflow.db                     (local MLflow database — git-ignored)
```

If any of the above appear, unstage them:
```bash
git reset HEAD .env
git reset HEAD model/property_price_prediction_voting.sav
```
Then add the filename to `.gitignore` and re-stage.

---

### 3.6 Commit as Sole Contributor

```bash
git commit -m "feat: production-ready Pune Real Estate Price Prediction MLOps API"
```

---

### 3.7 Add Remote and Push

The repository already exists at:
`https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction`

```bash
# If remote is not yet set:
git remote add origin https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction.git
git branch -M main
git push -u origin main
```

If origin is already set to a different URL:
```bash
git remote set-url origin https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction.git
git push -u origin main
```

---

### 3.8 Verify on GitHub

Open https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction

**Must be visible:**
```
✅  src/                  ✅  frontend/             ✅  tests/
✅  mlops/                ✅  infra/                ✅  .github/workflows/
✅  Nakoba's Go Live/     ✅  Dockerfile            ✅  docker-compose.yml
✅  README.md
```

**Must NOT be visible:**
```
❌  .env                  ❌  *.pem                 ❌  mlruns/
❌  model/*.sav           ❌  model/*.pkl            ❌  mlflow.db
```

---

### 3.9 Add GitHub Actions Secrets

Navigate to:
**https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction/settings/secrets/actions**

Click **"New repository secret"** and add each one:

| Secret Name | Where to Get the Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM → Users → nakoba-deploy → Security credentials |
| `AWS_SECRET_ACCESS_KEY` | Same page — or from the CSV you downloaded |
| `AWS_REGION` | `us-east-1` |
| `AWS_ACCOUNT_ID` | `aws sts get-caller-identity --query Account --output text` |
| `ECR_REPO_NAME` | `pune-price-prediction` |
| `DAGSHUB_USER` | DagsHub → Settings → Account |
| `DAGSHUB_TOKEN` | DagsHub → Settings → Tokens → Create token |
| `DAGSHUB_REPO` | Your DagsHub repo name |
| `ECS_CLUSTER_NAME` | `pune-price-cluster` (after Section 7) |
| `ECS_SERVICE_NAME` | `pune-price-service` (after Section 7) |

---

### 3.10 Trigger CI and Confirm Green

```bash
git commit --allow-empty -m "ci: trigger first CI run"
git push
```

Open: https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction/actions

Wait ~3 minutes. Expected:
```
lint          ✅
test          ✅
docker-build  ✅
```

**If lint fails:** `ruff check src/ tests/ mlops/` locally, fix the shown issues.
**If test fails:** `pytest tests/ -v` locally, check conftest.py mocks are intact.
**If docker-build fails:** `docker build .` locally — most common cause is missing model files.

---

## SECTION 4 — BUILD AND TEST DOCKER LOCALLY

### 4.1 Build the Docker Image

```bash
# From project root (where Dockerfile lives)
docker build -t pune-price-prediction:latest .
```

**Expected last 3 lines:**
```
 => exporting to image
 => => writing image sha256:abc123...
 => => naming to docker.io/library/pune-price-prediction:latest
```

**Common error:** `COPY model/: file not found`
**Fix:** Model artifacts must be present. Run `dvc pull model/ --force` first.

---

### 4.2 Run the Container

```powershell
# Windows PowerShell
docker run --env-file .env -p 8000:8000 pune-price-prediction:latest
```
```bash
# macOS / Linux
docker run --env-file .env -p 8000:8000 pune-price-prediction:latest
```

**Expected:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

### 4.3 Test the Running Container

```bash
curl http://localhost:8000/health
```
**Expected:** `{"status":"API is healthy and running."}`

---

### 4.4 Run the Full Docker Compose Stack

```bash
# API only
docker compose up --build

# API + Nginx reverse proxy
docker compose --profile proxy up

# API + MLflow tracking server
docker compose --profile mlops up
```

| URL | Service |
|---|---|
| http://localhost:8000/docs | FastAPI Swagger UI |
| http://localhost:8000/health | Health check |
| http://localhost:5000 | MLflow UI (mlops profile) |
| http://localhost:80 | API via Nginx (proxy profile) |

---

### 4.5 Check Container Logs

```bash
docker compose logs api --tail=30
```

**Must contain:**
```
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

**Must NOT contain:**
```
Error     Traceback     ModuleNotFoundError     FileNotFoundError
```

---

### 4.6 Stop Everything

```bash
docker compose down
```

---

## SECTION 5 — PUSH DOCKER IMAGE TO AWS ECR

### 5.1 Set Shell Variables (do this once per terminal session)

```powershell
# Windows PowerShell
$AWS_ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$AWS_REGION     = "us-east-1"
$ECR_REPO       = "pune-price-prediction"
$ECR_URI        = "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO"
Write-Host "ECR URI: $ECR_URI"
```
```bash
# macOS / Linux
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION="us-east-1"
export ECR_REPO="pune-price-prediction"
export ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO"
echo "ECR URI: $ECR_URI"
```

---

### 5.2 Create the ECR Repository

```bash
aws ecr create-repository \
  --repository-name $ECR_REPO \
  --region $AWS_REGION \
  --image-scanning-configuration scanOnPush=true
```

**Expected:** JSON with `"repositoryUri"` matching your ECR_URI.

**Save the repositoryUri:**
```
<< AWS_ACCOUNT_ID >>.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction
```

---

### 5.3 Authenticate Docker to ECR

```powershell
# Windows PowerShell
aws ecr get-login-password --region $AWS_REGION | `
  docker login --username AWS --password-stdin `
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
```
```bash
# macOS / Linux
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
```

**Expected:** `Login Succeeded`

**Common error:** `Error response from daemon: Get "https://...": no basic auth credentials`
**Fix:** The ECR login token expires after 12 hours. Re-run this command.

---

### 5.4 Tag and Push to ECR

```bash
docker tag pune-price-prediction:latest $ECR_URI:latest
docker push $ECR_URI:latest
```

**Expected:**
```
latest: digest: sha256:abc123... size: 12345678
```

---

### 5.5 Verify Image Is in ECR

```bash
aws ecr describe-images \
  --repository-name $ECR_REPO \
  --region $AWS_REGION
```

**Expected:**
```json
{
  "imageDetails": [{
    "imageTags": ["latest"],
    "imageSizeInBytes": 245000000,
    "imagePushedAt": "2024-01-01T00:00:00+00:00"
  }]
}
```

**Common error:** `No images found`
**Fix:** The push did not complete. Check Docker is running and retry step 5.4.

---

## SECTION 6 — DEPLOY: AWS APP RUNNER (FAST PATH)

App Runner is the simplest AWS deployment: no cluster, no load balancer,
no VPC config. One command → public HTTPS URL. **Do this first.**

---

### 6.1 Create App Runner IAM Role for ECR Access

```bash
# Create the trust policy document
cat > /tmp/apprunner-trust.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "build.apprunner.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create the role
aws iam create-role \
  --role-name AppRunnerECRAccessRole \
  --assume-role-policy-document file:///tmp/apprunner-trust.json

# Attach the ECR read policy
aws iam attach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
```

**Get and save the role ARN:**
```bash
export APP_RUNNER_ROLE_ARN=$(aws iam get-role \
  --role-name AppRunnerECRAccessRole \
  --query "Role.Arn" --output text)
echo "Role ARN: $APP_RUNNER_ROLE_ARN"
```
```powershell
# Windows PowerShell
$APP_RUNNER_ROLE_ARN = (aws iam get-role --role-name AppRunnerECRAccessRole --query "Role.Arn" --output text)
Write-Host "Role ARN: $APP_RUNNER_ROLE_ARN"
```

---

### 6.2 Create the App Runner Service

```bash
# macOS / Linux
aws apprunner create-service \
  --service-name pune-price-prediction \
  --source-configuration "{
    \"ImageRepository\": {
      \"ImageIdentifier\": \"$ECR_URI:latest\",
      \"ImageConfiguration\": {
        \"Port\": \"8000\",
        \"RuntimeEnvironmentVariables\": {
          \"PORT\": \"8000\",
          \"CORS_ORIGINS\": \"*\"
        }
      },
      \"ImageRepositoryType\": \"ECR\"
    },
    \"AutoDeploymentsEnabled\": true,
    \"AuthenticationConfiguration\": {
      \"AccessRoleArn\": \"$APP_RUNNER_ROLE_ARN\"
    }
  }" \
  --instance-configuration "{\"Cpu\":\"1 vCPU\",\"Memory\":\"2 GB\"}" \
  --health-check-configuration "{
    \"Protocol\":\"HTTP\",
    \"Path\":\"/health\",
    \"Interval\":10,
    \"Timeout\":5,
    \"HealthyThreshold\":1,
    \"UnhealthyThreshold\":5
  }" \
  --region $AWS_REGION
```

```powershell
# Windows PowerShell
aws apprunner create-service `
  --service-name pune-price-prediction `
  --source-configuration "{`"ImageRepository`":{`"ImageIdentifier`":`"$ECR_URI`:latest`",`"ImageConfiguration`":{`"Port`":`"8000`",`"RuntimeEnvironmentVariables`":{`"PORT`":`"8000`",`"CORS_ORIGINS`":`"*`"}},`"ImageRepositoryType`":`"ECR`"},`"AutoDeploymentsEnabled`":true,`"AuthenticationConfiguration`":{`"AccessRoleArn`":`"$APP_RUNNER_ROLE_ARN`"}}" `
  --instance-configuration "{`"Cpu`":`"1 vCPU`",`"Memory`":`"2 GB`"}" `
  --health-check-configuration "{`"Protocol`":`"HTTP`",`"Path`":`"/health`",`"Interval`":10,`"Timeout`":5,`"HealthyThreshold`":1,`"UnhealthyThreshold`":5}" `
  --region $AWS_REGION
```

**Save the ServiceArn from the output:**
```bash
# Get and save Service ARN
export SERVICE_ARN=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='pune-price-prediction'].ServiceArn" \
  --output text --region $AWS_REGION)
echo "Service ARN: $SERVICE_ARN"
```

---

### 6.3 Wait for RUNNING State (~3 minutes)

```bash
# Poll every 30 seconds
watch -n 30 "aws apprunner describe-service \
  --service-arn $SERVICE_ARN \
  --region $AWS_REGION \
  --query 'Service.Status' \
  --output text"
```
```powershell
# Windows PowerShell — manual poll
do {
  $status = (aws apprunner describe-service --service-arn $SERVICE_ARN --region $AWS_REGION --query "Service.Status" --output text)
  Write-Host "Status: $status  ($(Get-Date -Format 'HH:mm:ss'))"
  Start-Sleep 30
} while ($status -ne "RUNNING")
Write-Host "Service is RUNNING"
```

**Expected:** `"RUNNING"` after ~3 minutes.

Or watch in the console:
`https://us-east-1.console.aws.amazon.com/apprunner/home?region=us-east-1#/services`

---

### 6.4 Get Your Public URL

```bash
export APP_RUNNER_URL=$(aws apprunner describe-service \
  --service-arn $SERVICE_ARN \
  --region $AWS_REGION \
  --query "Service.ServiceUrl" \
  --output text)
echo "Live URL: https://$APP_RUNNER_URL"
```
```powershell
# Windows PowerShell
$APP_RUNNER_URL = (aws apprunner describe-service --service-arn $SERVICE_ARN --region $AWS_REGION --query "Service.ServiceUrl" --output text)
Write-Host "Live URL: https://$APP_RUNNER_URL"
```

**Format:** `https://xxxxxxxxxx.us-east-1.awsapprunner.com`

---

### 6.5 Test the Live API

```bash
# Health check
curl https://$APP_RUNNER_URL/health
# Expected: {"status":"API is healthy and running."}

# Prediction
curl -X POST "https://$APP_RUNNER_URL/predict" \
  -H "Content-Type: application/json" \
  -d '{"property_type":2,"area":1000,"sub_area":"kothrud","description":"spacious apartment","clubhouse":1,"school":1,"hospital":0,"mall":1,"park":1,"pool":0,"gym":1}'
# Expected: {"predicted_price":62.3,"lower_bound":30.94,"upper_bound":93.66,"features_used":115}
```

Open in browser: `https://<< APP_RUNNER_URL >>/docs` — Swagger UI over HTTPS ✅

---

### 6.6 Auto-Deploy on New ECR Push

`AutoDeploymentsEnabled: true` is already set from step 6.2.
Every `docker push $ECR_URI:latest` automatically triggers a zero-downtime redeploy.

**Manual redeploy trigger:**
```bash
aws apprunner start-deployment \
  --service-arn $SERVICE_ARN \
  --region $AWS_REGION
```

---

## SECTION 7 — DEPLOY: AWS ECS FARGATE (PRODUCTION)

ECS Fargate gives you VPC networking, ALB, fine-grained IAM, and is
the standard for production workloads with variable traffic.

---

### 7.1 Store Secrets in AWS Secrets Manager

```bash
# MLflow tracking URI
aws secretsmanager create-secret \
  --name "pune-price/mlflow-tracking-uri" \
  --description "MLflow tracking URI for Pune Price Prediction API" \
  --secret-string "sqlite:///mlflow.db" \
  --region $AWS_REGION

# DagsHub token
aws secretsmanager create-secret \
  --name "pune-price/dagshub-token" \
  --description "DagsHub API token" \
  --secret-string "<< YOUR_DAGSHUB_TOKEN >>" \
  --region $AWS_REGION
```

**Save each SecretArn:**
```bash
export SECRET_ARN_MLFLOW=$(aws secretsmanager describe-secret \
  --secret-id "pune-price/mlflow-tracking-uri" \
  --query "ARN" --output text --region $AWS_REGION)

export SECRET_ARN_DAGSHUB=$(aws secretsmanager describe-secret \
  --secret-id "pune-price/dagshub-token" \
  --query "ARN" --output text --region $AWS_REGION)

echo "MLflow secret ARN:  $SECRET_ARN_MLFLOW"
echo "DagsHub secret ARN: $SECRET_ARN_DAGSHUB"
```

---

### 7.2 Update the ECS Task Definition

Open `infra/aws/ecs-task-definition.json` and replace:

| Placeholder | Replace with |
|---|---|
| `YOUR_AWS_ACCOUNT_ID` | Your 12-digit account ID (from `aws sts get-caller-identity`) |
| `YOUR_REGION` | `us-east-1` |
| Value of `valueFrom` in secrets | Secret ARN from step 7.1 |

**Complete updated file:**

```json
{
  "family": "pune-price-prediction",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<< AWS_ACCOUNT_ID >>:role/ecsTaskExecutionRole",
  "taskRoleArn":      "arn:aws:iam::<< AWS_ACCOUNT_ID >>:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name":      "pune-price-api",
      "image":     "<< AWS_ACCOUNT_ID >>.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction:latest",
      "essential": true,
      "portMappings": [
        { "containerPort": 8000, "protocol": "tcp" }
      ],
      "environment": [
        { "name": "PORT",         "value": "8000" },
        { "name": "API_HOST",     "value": "0.0.0.0" },
        { "name": "CORS_ORIGINS", "value": "*" }
      ],
      "secrets": [
        {
          "name":      "DAGSHUB_TOKEN",
          "valueFrom": "<< SECRET_ARN_DAGSHUB >>"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group":         "/ecs/pune-price-prediction",
          "awslogs-region":        "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command":     ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" || exit 1"],
        "interval":    30,
        "timeout":     10,
        "retries":     3,
        "startPeriod": 60
      }
    }
  ]
}
```

---

### 7.3 Create IAM Roles for ECS

```bash
# Execution role (ECS agent uses this to pull image and write logs)
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Service":"ecs-tasks.amazonaws.com"},
      "Action":"sts:AssumeRole"
    }]
  }'

aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Allow reading Secrets Manager
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite

# Task role (the app itself uses this — for S3, DynamoDB etc. if needed)
aws iam create-role \
  --role-name ecsTaskRole \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Service":"ecs-tasks.amazonaws.com"},
      "Action":"sts:AssumeRole"
    }]
  }'
```

---

### 7.4 Create CloudWatch Log Group

```bash
aws logs create-log-group \
  --log-group-name /ecs/pune-price-prediction \
  --region $AWS_REGION
```

---

### 7.5 Create ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name pune-price-cluster \
  --region $AWS_REGION
```

**Expected:** `"status": "ACTIVE"`

---

### 7.6 Register Task Definition

```bash
aws ecs register-task-definition \
  --cli-input-json file://infra/aws/ecs-task-definition.json \
  --region $AWS_REGION
```

**Expected:** JSON containing `"taskDefinitionArn": "...pune-price-prediction:1"`

---

### 7.7 Create Application Load Balancer

#### a. Create the ALB

```bash
# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text --region $AWS_REGION)

# Get public subnets
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=mapPublicIpOnLaunch,Values=true" \
  --query "Subnets[*].SubnetId" --output text --region $AWS_REGION | tr '\t' ' ')

echo "VPC: $VPC_ID"
echo "Subnets: $SUBNET_IDS"

# Create ALB
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name pune-price-alb \
  --subnets $SUBNET_IDS \
  --security-groups $(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=default" \
    --query "SecurityGroups[0].GroupId" --output text --region $AWS_REGION) \
  --scheme internet-facing \
  --type application \
  --region $AWS_REGION \
  --query "LoadBalancers[0].LoadBalancerArn" --output text)

ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query "LoadBalancers[0].DNSName" --output text --region $AWS_REGION)

echo "ALB ARN: $ALB_ARN"
echo "ALB DNS: $ALB_DNS"
```

#### b. Create Target Group

```bash
TG_ARN=$(aws elbv2 create-target-group \
  --name pune-price-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --region $AWS_REGION \
  --query "TargetGroups[0].TargetGroupArn" --output text)

echo "Target Group ARN: $TG_ARN"
```

#### c. Create HTTP Listener

```bash
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN \
  --region $AWS_REGION
```

#### d. Open ALB Security Group Port 80

```bash
ALB_SG=$(aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=default" \
  --query "SecurityGroups[0].GroupId" --output text --region $AWS_REGION)

aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG \
  --protocol tcp --port 80 --cidr 0.0.0.0/0 \
  --region $AWS_REGION 2>/dev/null || echo "Rule already exists"

aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG \
  --protocol tcp --port 8000 --cidr 0.0.0.0/0 \
  --region $AWS_REGION 2>/dev/null || echo "Rule already exists"
```

---

### 7.8 Create ECS Service

```bash
aws ecs create-service \
  --cluster pune-price-cluster \
  --service-name pune-price-service \
  --task-definition pune-price-prediction:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[$SUBNET_IDS],
    securityGroups=[$ALB_SG],
    assignPublicIp=ENABLED
  }" \
  --load-balancers "targetGroupArn=$TG_ARN,containerName=pune-price-api,containerPort=8000" \
  --region $AWS_REGION
```

---

### 7.9 Wait for Service Stable

```bash
aws ecs wait services-stable \
  --cluster pune-price-cluster \
  --services pune-price-service \
  --region $AWS_REGION

echo "Service is stable"
```

**Expected:** Command returns with exit code 0. No output = success.
Wait up to 10 minutes.

---

### 7.10 Test via ALB

```bash
curl http://$ALB_DNS/health
# Expected: {"status":"API is healthy and running."}

curl -X POST http://$ALB_DNS/predict \
  -H "Content-Type: application/json" \
  -d '{"property_type":2,"area":1000,"sub_area":"kothrud","description":"spacious apartment","clubhouse":1,"school":1,"hospital":0,"mall":1,"park":1,"pool":0,"gym":1}'
```

---

### 7.11 Common ECS Errors and Fixes

**Task keeps stopping → check CloudWatch logs:**
```bash
aws logs tail /ecs/pune-price-prediction --follow --region $AWS_REGION
```

| Error | Cause | Fix |
|---|---|---|
| `CannotPullContainerError` | ECR auth expired or wrong region | Re-run ECR login, verify region |
| `Essential container exited` | App crashed at startup | Check CloudWatch logs for Python traceback |
| Target group Unhealthy | /health not returning 200 | Verify model files are in the image |
| `OutOfMemoryError` | Container needs more RAM | Increase memory in task def to 2048 |

---

## SECTION 8 — CUSTOM DOMAIN + HTTPS

### 8.1 Request ACM Certificate

```bash
aws acm request-certificate \
  --domain-name << YOUR_DOMAIN >> \
  --validation-method DNS \
  --region $AWS_REGION
```

**Expected:** Returns `CertificateArn`.

```bash
export CERT_ARN="arn:aws:acm:us-east-1:<< AWS_ACCOUNT_ID >>:certificate/<< CERT_ID >>"
```

---

### 8.2 Get DNS Validation Record

```bash
aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region $AWS_REGION \
  --query "Certificate.DomainValidationOptions[0].ResourceRecord"
```

**Expected output:**
```json
{
  "Name":  "_acme-challenge.yourdomain.com.",
  "Type":  "CNAME",
  "Value": "_abc123.acm-validations.aws."
}
```

Add this CNAME to your DNS provider.

---

### 8.3 Add CNAME in Route 53

```bash
# Get hosted zone ID
ZONE_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name << YOUR_DOMAIN >> \
  --query "HostedZones[0].Id" --output text | sed 's|/hostedzone/||')

# Add validation CNAME (replace NAME and VALUE with output from 8.2)
aws route53 change-resource-record-sets \
  --hosted-zone-id $ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name":  "<< VALIDATION_CNAME_NAME >>",
        "Type":  "CNAME",
        "TTL":   300,
        "ResourceRecords": [{"Value": "<< VALIDATION_CNAME_VALUE >>"}]
      }
    }]
  }'
```

If using another DNS provider: log into your provider dashboard and add:
```
Type:  CNAME
Name:  _acme-challenge.<< YOUR_DOMAIN >>
Value: << VALIDATION_CNAME_VALUE >>
TTL:   300
```

---

### 8.4 Wait for Certificate Validation

```bash
aws acm wait certificate-validated \
  --certificate-arn $CERT_ARN \
  --region $AWS_REGION
echo "Certificate validated"
```

**Expected:** Returns silently (exit code 0 = success). Takes 2–5 minutes.

---

### 8.5 Add HTTPS Listener to ALB (ECS path only — App Runner has automatic HTTPS)

```bash
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=$CERT_ARN \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN \
  --region $AWS_REGION
```

---

### 8.6 Add Route 53 A Record for Your Domain

```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id $ZONE_ID \
  --change-batch "{
    \"Changes\": [{
      \"Action\": \"UPSERT\",
      \"ResourceRecordSet\": {
        \"Name\": \"<< YOUR_DOMAIN >>\",
        \"Type\": \"A\",
        \"AliasTarget\": {
          \"HostedZoneId\": \"Z35SXDOTRQ7X7K\",
          \"DNSName\": \"$ALB_DNS\",
          \"EvaluateTargetHealth\": true
        }
      }
    }]
  }"
```

Note: `Z35SXDOTRQ7X7K` is the hosted zone ID for ALBs in `us-east-1`.
For other regions: https://docs.aws.amazon.com/general/latest/gr/elb.html

---

### 8.7 Test HTTPS

```bash
curl https://<< YOUR_DOMAIN >>/health
# Expected: {"status":"API is healthy and running."}
```

Open in browser: `https://<< YOUR_DOMAIN >>/docs` — Swagger UI over HTTPS ✅

---

## SECTION 9 — CLOUDWATCH MONITORING + ALERTING

### 9.1 Confirm Logs Are Flowing

```bash
aws logs describe-log-groups \
  --log-group-name-prefix /ecs/pune-price \
  --region $AWS_REGION
# Expected: shows /ecs/pune-price-prediction

# Stream live logs
aws logs tail /ecs/pune-price-prediction --follow --region $AWS_REGION
```

---

### 9.2 Create SNS Topic for Alerts

```bash
SNS_ARN=$(aws sns create-topic \
  --name pune-price-alerts \
  --region $AWS_REGION \
  --query TopicArn --output text)
echo "SNS ARN: $SNS_ARN"

aws sns subscribe \
  --topic-arn $SNS_ARN \
  --protocol email \
  --notification-endpoint shadrack.n159@gmail.com \
  --region $AWS_REGION
```

**Check your email and click "Confirm subscription"** — alerts won't send without this.

---

### 9.3 Alarm — ECS Task Stopped

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "pune-price-task-stopped" \
  --alarm-description "Alert when no ECS tasks are running" \
  --namespace AWS/ECS \
  --metric-name RunningTaskCount \
  --dimensions Name=ClusterName,Value=pune-price-cluster \
               Name=ServiceName,Value=pune-price-service \
  --statistic Average \
  --period 60 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator LessThanThreshold \
  --alarm-actions $SNS_ARN \
  --region $AWS_REGION
```

---

### 9.4 Alarm — High CPU

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "pune-price-high-cpu" \
  --alarm-description "Alert when CPU exceeds 80%" \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ClusterName,Value=pune-price-cluster \
               Name=ServiceName,Value=pune-price-service \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions $SNS_ARN \
  --region $AWS_REGION
```

---

### 9.5 Alarm — High Error Rate (ALB 5xx)

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "pune-price-5xx-errors" \
  --alarm-description "Alert when 5xx error count exceeds 10 in 5 minutes" \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=LoadBalancer,Value=$(echo $ALB_ARN | sed 's|.*loadbalancer/||') \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions $SNS_ARN \
  --region $AWS_REGION
```

---

### 9.6 Billing Alarm (CRITICAL — Prevents Surprise Bills)

```bash
# Billing alarms MUST be in us-east-1
aws cloudwatch put-metric-alarm \
  --alarm-name "pune-price-billing-alert" \
  --alarm-description "Alert when estimated charges exceed $50/day" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions $SNS_ARN \
  --region us-east-1
```

**Verify alarm was created:**
```bash
aws cloudwatch describe-alarms \
  --alarm-names "pune-price-billing-alert" \
  --region us-east-1 \
  --query "MetricAlarms[0].StateValue" --output text
# Expected: OK
```

---

## SECTION 10 — DAGSHUB: REMOTE MLFLOW + DVC

### 10.1 Create DagsHub Account and Repository

1. Go to https://dagshub.com and sign up
2. Click **New Repository** → name: `pune-price-prediction`
3. Go to **User Settings** → **Tokens** → **Create new token**
4. Copy these three values you will need:
   - `DAGSHUB_USER` — your DagsHub username
   - `DAGSHUB_TOKEN` — the token you just created
   - `DAGSHUB_REPO` — `pune-price-prediction`

---

### 10.2 Set Environment Variables

```powershell
# Windows PowerShell
$env:DAGSHUB_USER  = "<< YOUR_DAGSHUB_USER >>"
$env:DAGSHUB_TOKEN = "<< YOUR_DAGSHUB_TOKEN >>"
$env:DAGSHUB_REPO  = "<< YOUR_DAGSHUB_REPO >>"
```
```bash
# macOS / Linux
export DAGSHUB_USER="<< YOUR_DAGSHUB_USER >>"
export DAGSHUB_TOKEN="<< YOUR_DAGSHUB_TOKEN >>"
export DAGSHUB_REPO="<< YOUR_DAGSHUB_REPO >>"
```

Also add them to your `.env` file so they persist.

---

### 10.3 Verify DagsHub Connection

```bash
python -m mlops.dagshub_setup --check
```

**Expected:** `DagsHub connection: OK`

---

### 10.4 Configure DVC Remote to DagsHub

```bash
python -m mlops.dagshub_setup --print-dvc-cmds
```

Run the commands it prints. They will look like:

```bash
dvc remote add origin https://dagshub.com/<< DAGSHUB_USER >>/<< DAGSHUB_REPO >>.dvc
dvc remote modify origin --local auth basic
dvc remote modify origin --local user SHADRACK-NAKOBA
dvc remote modify origin --local password << YOUR_DAGSHUB_TOKEN >>
dvc remote default origin
```

---

### 10.5 Push DVC Artifacts to DagsHub

```bash
dvc push
```

**Expected:**
```
6 files pushed
```

---

### 10.6 Log an MLflow Experiment to DagsHub

```bash
python -m mlops.mlflow_train
```

Open: `https://dagshub.com/<< DAGSHUB_USER >>/<< DAGSHUB_REPO >>/experiments`

**Expected:** MLflow run visible with parameters and metrics (R²=0.852, RMSE=15.75).

---

### 10.7 Verify a Teammate Can Pull Artifacts (Fresh Clone Test)

```bash
# macOS / Linux — simulate a fresh environment
git clone https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction.git /tmp/test-clone
cd /tmp/test-clone
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-mlops.txt
export DAGSHUB_USER="<< YOUR_DAGSHUB_USER >>"
export DAGSHUB_TOKEN="<< YOUR_DAGSHUB_TOKEN >>"
dvc pull
ls model/   # Should show all .pkl and .sav files
```

**Expected:** All 6 model files download without any local copies present.

---

## SECTION 11 — AUTOMATED DEPLOYS VIA GITHUB ACTIONS

### 11.1 Complete `.github/workflows/ci.yml`

The workflow file is already at `.github/workflows/ci.yml` in your repo.
It has these four jobs:

| Job | Trigger | What It Does |
|---|---|---|
| `lint` | Every push / PR | `ruff check` + `black --check` on src/, tests/, mlops/ |
| `test` | Every push / PR (needs: lint) | `pytest tests/ -v --cov=src` |
| `docker-build` | Every push / PR (needs: test) | `docker build` + container smoke test hitting `/health` |
| `deploy` | **Manual only** (`workflow_dispatch`) | Build → tag → push to ECR → force new ECS deployment |

The deploy job requires these GitHub Secrets (Settings → Secrets → Actions):
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_ACCOUNT_ID`,
`ECR_REPO_NAME`, `ECS_CLUSTER_NAME` (optional), `ECS_SERVICE_NAME` (optional)

---

### 11.2 How to Trigger the Deploy Job Manually

1. Go to **https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction/actions**
2. In the left sidebar, click **CI/CD — Lint · Test · Build · Deploy**
3. Click the **"Run workflow"** dropdown on the right side
4. Select branch `main`
5. Click the green **"Run workflow"** button
6. Watch the `deploy` job — completes in ~3 minutes
7. In the AWS console, confirm ECS service shows a new deployment

---

### 11.3 What to Do When a Job Fails

**`lint` fails:**
```bash
ruff check src/ tests/ mlops/   # see exact error lines
black --check src/ tests/ mlops/ # see which files need formatting
# Fix locally, then:
git add -u && git commit -m "fix: lint errors" && git push
```

**`test` fails:**
```bash
pytest tests/ -v --tb=long   # run locally to see full traceback
# Most common: conftest.py mock not matching a new function signature
# Check tests/conftest.py and verify the patch paths
```

**`docker-build` fails:**
```bash
docker build .   # run locally, read the build error
# Most common cause: model/ artifacts missing
dvc pull model/ --force   # pull them, then rebuild
```

**`deploy` fails:**
```bash
# 1. Check all 5 GitHub Secrets are set — Settings → Secrets → Actions
# 2. Verify IAM user has all required policies (Section 1)
# 3. Check the step output — click the failing step to expand it
```

---

## SECTION 12 — GO-LIVE VALIDATION CHECKLIST

Print this page. Check every item before declaring the project live.

### CODE AND TESTS
```
□  pytest tests/ runs 36 tests, all green
□  ruff check src/ tests/ mlops/ shows no errors
□  black --check src/ tests/ mlops/ shows no errors
□  docker build . completes without errors
□  docker compose up --build starts the API on port 8000
□  http://localhost:8000/health returns {"status":"API is healthy and running."}
□  http://localhost:8000/predict returns {"predicted_price":..., "features_used":115}
□  frontend/index.html opens in browser and submits a prediction successfully
□  http://localhost:8000/docs Swagger UI loads and shows 3 routes
```

### GITHUB
```
□  Repo visible at https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction
□  These folders visible: src/ frontend/ tests/ mlops/ infra/ .github/
□  "Nakoba's Go Live/" folder is visible in the repo
□  .env is NOT in the repo (search GitHub for "DAGSHUB_TOKEN=" — must find 0 results in .env)
□  model/*.sav and model/*.pkl are NOT in the repo (only .dvc pointer files)
□  GitHub Actions: lint ✅  test ✅  docker-build ✅  on latest commit
□  All 5 core GitHub Secrets are set (check Settings → Secrets → Actions)
```

### AWS ECR
```
□  ECR repository pune-price-prediction exists in us-east-1
□  Latest image pushed within the last 24 hours
□  Image scan shows 0 CRITICAL vulnerabilities
     aws ecr describe-image-scan-findings --repository-name pune-price-prediction \
       --image-id imageTag=latest --region us-east-1
```

### AWS DEPLOYMENT (App Runner OR ECS Fargate)
```
□  Service status is RUNNING
     aws apprunner describe-service --service-arn $SERVICE_ARN \
       --query "Service.Status" --output text
□  https://<< YOUR_URL >>/health returns {"status":"API is healthy and running."} over HTTPS
□  https://<< YOUR_URL >>/predict returns valid JSON with predicted_price
□  https://<< YOUR_URL >>/docs loads Swagger UI
□  Response time for /predict is under 3 seconds
     time curl -X POST https://<< YOUR_URL >>/predict ...
□  CloudWatch logs show no errors in the past 30 minutes
```

### SECRETS AND SECURITY
```
□  No hardcoded secrets in any Python or config file
     grep -r "dagshub_token\|aws_secret\|password" src/ mlops/
□  .env is git-ignored and absent from GitHub
□  Sensitive values are stored in AWS Secrets Manager
□  IAM user has only the listed required policies, NOT AdministratorAccess
```

### MONITORING
```
□  CloudWatch log group /ecs/pune-price-prediction exists and has recent events
□  pune-price-task-stopped alarm is in OK state
□  pune-price-high-cpu alarm is in OK state
□  pune-price-5xx-errors alarm is in OK state
□  pune-price-billing-alert alarm is in OK state (threshold: $50)
□  SNS email subscription confirmed (confirmation email clicked)
```

### MLOPS
```
□  dvc remote list shows a remote (DagsHub or S3)
□  dvc push completes without error
□  DagsHub shows MLflow experiments from mlops/mlflow_train.py
□  dvc pull on a fresh clone downloads all model artifacts
□  dvc metrics show displays r2=0.852, rmse=15.75
```

### SOLE CONTRIBUTOR
```
□  git log --all --format="%an" | sort -u  shows only "Nakoba"
□  GitHub repo Contributors tab shows only SHADRACK-NAKOBA
```

---

## SECTION 13 — TEARDOWN (Avoid Surprise Bills)

Run these commands when you are done using the deployment. Leaving ECS Fargate
running 24/7 costs ~$30/month. App Runner is cheaper (free tier: 2M requests).

### Step 1 — Delete App Runner Service

```bash
aws apprunner delete-service \
  --service-arn $SERVICE_ARN \
  --region $AWS_REGION
echo "App Runner service deletion initiated"
```

### Step 2 — Scale ECS Service to Zero

```bash
aws ecs update-service \
  --cluster pune-price-cluster \
  --service pune-price-service \
  --desired-count 0 \
  --region $AWS_REGION
```

### Step 3 — Delete ECS Service and Cluster

```bash
aws ecs delete-service \
  --cluster pune-price-cluster \
  --service pune-price-service \
  --force \
  --region $AWS_REGION

aws ecs delete-cluster \
  --cluster pune-price-cluster \
  --region $AWS_REGION
```

### Step 4 — Delete ECR Images and Repository

```bash
# Delete all images first
aws ecr batch-delete-image \
  --repository-name pune-price-prediction \
  --image-ids imageTag=latest \
  --region $AWS_REGION

# Delete the repository
aws ecr delete-repository \
  --repository-name pune-price-prediction \
  --force \
  --region $AWS_REGION
```

### Step 5 — Delete Secrets Manager Secrets

```bash
aws secretsmanager delete-secret \
  --secret-id "pune-price/mlflow-tracking-uri" \
  --force-delete-without-recovery \
  --region $AWS_REGION

aws secretsmanager delete-secret \
  --secret-id "pune-price/dagshub-token" \
  --force-delete-without-recovery \
  --region $AWS_REGION
```

### Step 6 — Delete CloudWatch Log Group

```bash
aws logs delete-log-group \
  --log-group-name /ecs/pune-price-prediction \
  --region $AWS_REGION
```

### Step 7 — Delete CloudWatch Alarms

```bash
aws cloudwatch delete-alarms \
  --alarm-names \
    "pune-price-task-stopped" \
    "pune-price-high-cpu" \
    "pune-price-5xx-errors" \
    "pune-price-billing-alert" \
  --region $AWS_REGION
```

### Verify $0 Spend After Teardown

```bash
# Check current month spend (takes up to 24 hours to reflect)
aws ce get-cost-and-usage \
  --time-period Start=$(date -d "first day of this month" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --region us-east-1 \
  --query "ResultsByTime[0].Total.UnblendedCost.Amount" \
  --output text
```

```powershell
# Windows PowerShell version
$start = (Get-Date -Day 1 -Format "yyyy-MM-dd")
$end   = (Get-Date -Format "yyyy-MM-dd")
aws ce get-cost-and-usage `
  --time-period "Start=$start,End=$end" `
  --granularity MONTHLY `
  --metrics UnblendedCost `
  --region us-east-1 `
  --query "ResultsByTime[0].Total.UnblendedCost.Amount" `
  --output text
```

**Expected after full teardown:** Near `0.00` (minor costs like S3 storage may remain)

> **WARNING:** ECS Fargate tasks cost ~$0.04/hour per vCPU.
> An idle task running 24/7 = ~$30/month.
> App Runner costs only when handling requests (free tier: 2M requests/month).
> **Use App Runner for this project to minimise cost.**

---

## SECTION 14 — TROUBLESHOOTING REFERENCE

| # | Error Message | Cause | Fix |
|---|---|---|---|
| 1 | `Could not find a version that satisfies the requirement fastapi` | Python version mismatch or pip is outdated | `pip install --upgrade pip` then retry |
| 2 | `ModuleNotFoundError: No module named 'sklearn'` | Virtual environment not activated | `source .venv/bin/activate` (Mac/Linux) or `.venv\Scripts\Activate.ps1` (Windows) |
| 3 | `dvc pull: ERROR: Authentication failed` | DVC remote credentials not configured | Run `python -m mlops.dagshub_setup --print-dvc-cmds` and execute the output |
| 4 | `docker: Cannot connect to the Docker daemon` | Docker Desktop is not running | Open Docker Desktop from the Start menu / Applications and wait for it to start |
| 5 | `Got permission denied while trying to connect to Docker` (Linux) | User not in docker group | `sudo usermod -aG docker $USER` then log out and back in |
| 6 | `Bind for 0.0.0.0:8000 failed: port is already allocated` | Another process is using port 8000 | `lsof -ti:8000 \| xargs kill` (Mac/Linux) or `Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess` (Windows) |
| 7 | ECS task health check failed | `/health` endpoint not returning 200 | Check CloudWatch logs; verify model artifacts are in the image |
| 8 | `CannotPullContainerError: no basic auth credentials` | ECR login token expired | Re-run the `aws ecr get-login-password` command from Section 5.3 |
| 9 | `Essential container in task exited` | App crashed at startup | `aws logs tail /ecs/pune-price-prediction --follow` — look for Python traceback |
| 10 | `AccessDeniedException: is not authorized to perform: ecr:GetAuthorizationToken` | IAM user missing ECR policy | Attach `AmazonEC2ContainerRegistryFullAccess` in IAM console |
| 11 | `ExpiredTokenException` | AWS CLI session token expired | `aws configure` and re-enter credentials |
| 12 | `FileNotFoundError: model/property_price_prediction_voting.sav` | Model artifacts not in image / not on disk | `dvc pull model/ --force` then rebuild the Docker image |
| 13 | `ResourceNotFoundException` in MLflow | Model not registered in MLflow Registry | Run `python -m mlops.mlflow_train` first to register a model |
| 14 | App Runner: `Service creation failed` | IAM role missing ECR access or trust policy wrong | Verify `AppRunnerECRAccessRole` exists and has `AWSAppRunnerServicePolicyForECRAccess` attached |
| 15 | App Runner: `Deployment failed — Health check failed` | Container image not healthy, `/health` not returning 200 within timeout | Increase `UnhealthyThreshold` to 10, or run the image locally first |
| 16 | CI: `black would reformat src/app.py` | Code is not black-formatted | `black src/ tests/ mlops/` locally, commit, push |
| 17 | CI: `ruff E501 line too long` | A line exceeds 88 characters | Wrap the line, or add `# noqa: E501` for a legitimate long URL |
| 18 | CI: `FileNotFoundError: model/*.pkl` | conftest.py mock not intercepting all model loads | Check `tests/conftest.py` — the `_pickle_side_effect` function must handle all `.pkl` filename patterns |
| 19 | `SSL: CERTIFICATE_VERIFY_FAILED` when calling HTTPS endpoint | ACM certificate not yet validated | Wait 2–5 minutes, then `aws acm wait certificate-validated --certificate-arn $CERT_ARN` |
| 20 | `remote: error: GH001: Large files detected` on git push | A model `.sav` or `.pkl` > 50MB was accidentally committed | `git reset HEAD model/` to unstage, add to `.gitignore`, then push |

---

## FINAL SUMMARY — EVERYTHING THAT WAS BUILT

| File / Folder | Status | Purpose |
|---|---|---|
| `Nakoba's Go Live/GO_LIVE_PLAYBOOK.md` | ✅ | This document — master go-live guide |
| `.github/workflows/ci.yml` | ✅ | 4-job CI/CD: lint + test + docker-build + deploy |
| `Dockerfile` | ✅ | Multi-stage, non-root user, NLTK pre-cached, health check |
| `docker-compose.yml` | ✅ | API + optional Nginx proxy + MLflow tracking server |
| `.env.example` | ✅ | All 14 environment variables documented |
| `tests/conftest.py` | ✅ | Session-level mocks — tests run without model files |
| `tests/test_schemas.py` | ✅ | 20 Pydantic validation unit tests |
| `tests/test_inference.py` | ✅ | 16 inference pipeline unit tests |
| `infra/aws/ecs-task-definition.json` | ✅ | Fargate: 0.5 vCPU / 1 GB, CloudWatch logging, Secrets Manager |
| `infra/aws/buildspec.yml` | ✅ | CodeBuild: ECR login → build → push → imagedefinitions.json |
| `infra/aws/apprunner.yaml` | ✅ | App Runner: 1 vCPU / 2 GB, auto-scale 1–3 |
| `infra/docker/nginx.conf` | ✅ | Reverse proxy: rate limiting 10 req/s, security headers |
| `Nakoba's Build Steps/BUILD_STEPS.md` | ✅ | Deep-dive: every file, ML math, pipeline internals |
| `Nakoba's Production Steps/PROD_STEPS.md` | ✅ | 10-phase AWS guide + EC2 bonus |
| `README.md` | ✅ | ASCII architecture, API reference, quick start |

---

## THE 3 COMMANDS THAT MATTER MOST

```
───────────────────────────────────────────────────────────────────────
START LOCALLY:
  docker compose up --build

DEPLOY A NEW VERSION TO AWS (after git push):
  GitHub Actions → CI/CD workflow → Run workflow → deploy

TEAR DOWN ALL AWS RESOURCES:
  aws apprunner delete-service --service-arn << SERVICE_ARN >> --region us-east-1
───────────────────────────────────────────────────────────────────────
```

---

## YOUR LIVE URLS

```
───────────────────────────────────────────────────────────────────────
API (App Runner):   https://<< APP_RUNNER_ID >>.us-east-1.awsapprunner.com
Swagger UI:         https://<< APP_RUNNER_ID >>.us-east-1.awsapprunner.com/docs
Health check:       https://<< APP_RUNNER_ID >>.us-east-1.awsapprunner.com/health
Predict endpoint:   https://<< APP_RUNNER_ID >>.us-east-1.awsapprunner.com/predict

API (ECS Fargate):  http://<< ALB_DNS_NAME >>
Swagger UI (ECS):   http://<< ALB_DNS_NAME >>/docs

MLflow (DagsHub):   https://dagshub.com/SHADRACK-NAKOBA/<< DAGSHUB_REPO >>/experiments
GitHub repo:        https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction
───────────────────────────────────────────────────────────────────────
```

---

## SOLE CONTRIBUTOR CONFIRMATION

```
═══════════════════════════════════════════════════════════════
  This repository was built and is maintained solely by Nakoba.

  Git author:  Nakoba <shadrack.n159@gmail.com>
  GitHub:      https://github.com/SHADRACK-NAKOBA
  Repository:  https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction

  Verify:
    git log --all --format="%an" | sort -u
    → Nakoba

    git log --all --format="%ae" | sort -u
    → shadrack.n159@gmail.com
═══════════════════════════════════════════════════════════════
```
