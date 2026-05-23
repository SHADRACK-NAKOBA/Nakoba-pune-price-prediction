# Nakoba's Production Steps — Complete Deployment Guide

> From zero to a live, production-grade API on AWS in 10 phases.
> Every command is exact. Replace `YOUR_VALUE` placeholders before running.

---

## Before You Start — Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11 | `winget install Python.Python.3.11` |
| Docker Desktop | Latest | https://docs.docker.com/desktop/install/windows-install/ |
| AWS CLI v2 | Latest | `winget install Amazon.AWSCLI` |
| Git | Latest | `winget install Git.Git` |
| GitHub CLI (optional) | Latest | `winget install GitHub.cli` |

Verify installs:
```powershell
# Windows PowerShell
python --version     # Python 3.11.x
docker --version     # Docker version 24.x
aws --version        # aws-cli/2.x
git --version        # git version 2.x
```
```bash
# macOS / Linux
python3 --version && docker --version && aws --version && git --version
```

---

## PHASE 1 — Local Verification

**Goal:** Confirm the app runs correctly on your machine before touching AWS.

### 1.1 — Clone and set up the environment

```powershell
# Windows PowerShell
cd $env:USERPROFILE\Desktop
git clone https://github.com/SHADRACK-NAKOBA/pune-price-prediction.git
cd pune-price-prediction

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
```bash
# macOS / Linux
cd ~/Desktop
git clone https://github.com/SHADRACK-NAKOBA/pune-price-prediction.git
cd pune-price-prediction

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1.2 — Copy and configure .env

```powershell
# Windows PowerShell
Copy-Item .env.example .env
notepad .env    # fill in values (can leave AWS fields blank for local testing)
```
```bash
# macOS / Linux
cp .env.example .env
nano .env       # or code .env
```

### 1.3 — Ensure model artifacts are present

Model files are DVC-tracked and not in the Git repo. Either:

**Option A — Pull from DVC remote** (requires credentials in .env):
```bash
pip install -r requirements-mlops.txt
dvc pull model/ --force
```

**Option B — The models were already on your machine** (the project was built here):
```powershell
ls model/   # should show .sav and .pkl files
```

### 1.4 — Start the API server

```powershell
# Windows PowerShell — from project root
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```
```bash
# macOS / Linux
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

**Success looks like:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### 1.5 — Test the API

Open in browser: http://localhost:8000/docs (Swagger UI should appear)

Or run the test script:
```bash
python src/test_api.py
```

Or test manually:
```powershell
# Windows PowerShell
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET

Invoke-RestMethod -Uri "http://localhost:8000/predict" -Method POST `
  -ContentType "application/json" `
  -Body '{"property_type":2,"area":1000,"sub_area":"kothrud","description":"spacious flat","clubhouse":1,"school":1,"hospital":0,"mall":1,"park":1,"pool":0,"gym":1}'
```
```bash
# macOS / Linux
curl http://localhost:8000/health

curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"property_type":2,"area":1000,"sub_area":"kothrud","description":"spacious flat","clubhouse":1,"school":1,"hospital":0,"mall":1,"park":1,"pool":0,"gym":1}'
```

**Success looks like:**
```json
{"predicted_price": 62.3, "lower_bound": 30.94, "upper_bound": 93.66, "features_used": 115}
```

### 1.6 — Test with Docker locally

```bash
# Build the image
docker build -t pune-price-prediction:local .

# Run it
docker run -p 8000:8000 pune-price-prediction:local

# Verify
curl http://localhost:8000/health
```

### 1.7 — Run the test suite

```bash
pip install pytest pytest-cov
pytest tests/ -v --cov=src
```

**Success looks like:** `X passed in X.Xs`

---

## PHASE 2 — GitHub Setup

**Goal:** Push the entire project to GitHub with you as sole contributor.

### 2.1 — Create the GitHub repository

Go to https://github.com/new and create a new **private** or **public** repository named `pune-price-prediction`. Do NOT initialise it (no README, no .gitignore — we bring our own).

### 2.2 — Configure Git identity

```powershell
# Windows PowerShell
git config --global user.name  "Shadrack Nakoba"
git config --global user.email "shadrack.n159@gmail.com"
```
```bash
# macOS / Linux
git config --global user.name  "Shadrack Nakoba"
git config --global user.email "shadrack.n159@gmail.com"
```

### 2.3 — Initialise the repo (if not already a git repo)

```bash
# Run from the project root
git init
git branch -M main
```

If it is already a git repo (as in this project), skip `git init`.

### 2.4 — Stage all files

```powershell
# Windows PowerShell
git add Dockerfile docker-compose.yml .env.example
git add src/ tests/ frontend/ mlops/ infra/ metrics/
git add .github/ "Nakoba's Build Steps/" "Nakoba's Production Steps/"
git add params.yaml dvc.yaml requirements.txt requirements-mlops.txt
git add README.md MLOPS_LAB.md .gitignore .dvcignore
# DO NOT add: .env, model/*.pkl, model/*.sav (git-ignored)
git status    # verify nothing sensitive is staged
```
```bash
# macOS / Linux
git add Dockerfile docker-compose.yml .env.example
git add src/ tests/ frontend/ mlops/ infra/ metrics/
git add .github/ "Nakoba's Build Steps/" "Nakoba's Production Steps/"
git add params.yaml dvc.yaml requirements.txt requirements-mlops.txt
git add README.md MLOPS_LAB.md .gitignore .dvcignore
git status
```

### 2.5 — Initial commit

```bash
git commit -m "feat: production-ready Pune Real Estate Price Prediction MLOps project"
```

### 2.6 — Add remote and push

```bash
# Replace SHADRACK-NAKOBA with your GitHub username
git remote add origin https://github.com/SHADRACK-NAKOBA/pune-price-prediction.git
git push -u origin main
```

**Success looks like:**
```
Branch 'main' set up to track remote branch 'main' from 'origin'.
```

### 2.7 — Add GitHub Actions secrets (for CI)

Go to: `https://github.com/SHADRACK-NAKOBA/pune-price-prediction/settings/secrets/actions`

Add these secrets (optional — only needed for Docker build CI job):

| Secret | Value |
|---|---|
| `DAGSHUB_USER` | YOUR_DAGSHUB_USERNAME |
| `DAGSHUB_TOKEN` | YOUR_DAGSHUB_TOKEN |
| `DAGSHUB_REPO` | YOUR_DAGSHUB_REPO_NAME |

---

## PHASE 3 — AWS ECR Setup

**Goal:** Create a private Docker registry in AWS and push your image.

### 3.1 — Configure AWS CLI

```bash
aws configure
# AWS Access Key ID:     YOUR_AWS_ACCESS_KEY_ID
# AWS Secret Access Key: YOUR_AWS_SECRET_ACCESS_KEY
# Default region:        us-east-1
# Default output format: json
```

Verify:
```bash
aws sts get-caller-identity
# Should print your account ID and user ARN
```

### 3.2 — Create the ECR repository

```powershell
# Windows PowerShell
$AWS_ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$AWS_REGION = "us-east-1"
$ECR_REPO = "pune-price-prediction"

aws ecr create-repository `
  --repository-name $ECR_REPO `
  --region $AWS_REGION `
  --image-scanning-configuration scanOnPush=true
```
```bash
# macOS / Linux
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="us-east-1"
ECR_REPO="pune-price-prediction"

aws ecr create-repository \
  --repository-name $ECR_REPO \
  --region $AWS_REGION \
  --image-scanning-configuration scanOnPush=true
```

**Success:** JSON output containing the `repositoryUri`.

### 3.3 — Build and push the Docker image

```powershell
# Windows PowerShell
$ECR_URI = "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO"

# Login
aws ecr get-login-password --region $AWS_REGION | `
  docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Build
docker build -t "${ECR_REPO}:latest" .

# Tag
docker tag "${ECR_REPO}:latest" "${ECR_URI}:latest"

# Push
docker push "${ECR_URI}:latest"
```
```bash
# macOS / Linux
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO"

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker build -t "${ECR_REPO}:latest" .
docker tag "${ECR_REPO}:latest" "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"
```

**Success:** `latest: digest: sha256:... size: ...`

---

## PHASE 4 — AWS ECS Fargate Deployment

**Goal:** Run the container as a managed, auto-restarting service with load balancing.

### 4.1 — Replace placeholders in ecs-task-definition.json

Open `infra/aws/ecs-task-definition.json` and replace:
- `YOUR_AWS_ACCOUNT_ID` → your 12-digit account ID
- `YOUR_REGION` → `us-east-1`

### 4.2 — Create CloudWatch log group

```bash
aws logs create-log-group \
  --log-group-name /ecs/pune-price-prediction \
  --region $AWS_REGION
```

### 4.3 — Create IAM roles (first time only)

```bash
# Create ECS Task Execution Role
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }'

aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

### 4.4 — Register the task definition

```bash
aws ecs register-task-definition \
  --cli-input-json file://infra/aws/ecs-task-definition.json
```

**Success:** JSON with `taskDefinitionArn`.

### 4.5 — Create the ECS cluster

```bash
aws ecs create-cluster \
  --cluster-name pune-price-cluster \
  --capacity-providers FARGATE \
  --region $AWS_REGION
```

### 4.6 — Get VPC and subnet IDs (use your default VPC)

```bash
# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text)

# Get subnets in that VPC
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[*].SubnetId" --output text | tr '\t' ',')

echo "VPC: $VPC_ID"
echo "Subnets: $SUBNET_IDS"
```

### 4.7 — Create a security group

```bash
SG_ID=$(aws ec2 create-security-group \
  --group-name pune-price-sg \
  --description "Pune Price Prediction API" \
  --vpc-id $VPC_ID \
  --query "GroupId" --output text)

# Allow inbound on port 8000 from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 8000 --cidr 0.0.0.0/0

echo "Security Group: $SG_ID"
```

### 4.8 — Create the ECS service

```bash
# Replace SUBNET_1, SUBNET_2 with actual subnet IDs from step 4.6
aws ecs create-service \
  --cluster pune-price-cluster \
  --service-name pune-price-service \
  --task-definition pune-price-prediction \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[SUBNET_1,SUBNET_2],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --region $AWS_REGION
```

### 4.9 — Find the public IP of the running task

```bash
# Get task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster pune-price-cluster \
  --service-name pune-price-service \
  --query "taskArns[0]" --output text)

# Get network interface
ENI_ID=$(aws ecs describe-tasks \
  --cluster pune-price-cluster \
  --tasks $TASK_ARN \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" \
  --output text)

# Get public IP
PUBLIC_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids $ENI_ID \
  --query "NetworkInterfaces[0].Association.PublicIp" \
  --output text)

echo "API is at: http://$PUBLIC_IP:8000"
echo "Health check: http://$PUBLIC_IP:8000/health"
```

**Success:** `curl http://<PUBLIC_IP>:8000/health` returns `{"status":"API is healthy and running."}`

---

## PHASE 5 — Alternative: AWS App Runner (Simpler)

**Goal:** Deploy the container without managing clusters, VPCs, or load balancers. App Runner handles everything automatically.

### 5.1 — Create an App Runner ECR access role (first time only)

```bash
aws iam create-role \
  --role-name AppRunnerECRAccessRole \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"build.apprunner.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }'

aws iam attach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
```

### 5.2 — Deploy with a single command

```powershell
# Windows PowerShell
$ACCESS_ROLE_ARN = "arn:aws:iam::${AWS_ACCOUNT_ID}:role/AppRunnerECRAccessRole"
$IMAGE_URI = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/pune-price-prediction:latest"

aws apprunner create-service `
  --service-name pune-price-prediction `
  --source-configuration "{
    `"ImageRepository`": {
      `"ImageIdentifier`": `"$IMAGE_URI`",
      `"ImageRepositoryType`": `"ECR`",
      `"ImageConfiguration`": {
        `"Port`": `"8000`",
        `"RuntimeEnvironmentVariables`": {
          `"PORT`": `"8000`",
          `"API_HOST`": `"0.0.0.0`"
        }
      }
    },
    `"AutoDeploymentsEnabled`": true,
    `"AuthenticationConfiguration`": {
      `"AccessRoleArn`": `"$ACCESS_ROLE_ARN`"
    }
  }" `
  --instance-configuration "Cpu=1 vCPU,Memory=2 GB" `
  --health-check-configuration "Protocol=HTTP,Path=/health,Interval=10,Timeout=5,HealthyThreshold=1,UnhealthyThreshold=5" `
  --region $AWS_REGION
```
```bash
# macOS / Linux
ACCESS_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/AppRunnerECRAccessRole"
IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/pune-price-prediction:latest"

aws apprunner create-service \
  --service-name pune-price-prediction \
  --source-configuration "{
    \"ImageRepository\": {
      \"ImageIdentifier\": \"$IMAGE_URI\",
      \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {
        \"Port\": \"8000\",
        \"RuntimeEnvironmentVariables\": {
          \"PORT\": \"8000\",
          \"API_HOST\": \"0.0.0.0\"
        }
      }
    },
    \"AutoDeploymentsEnabled\": true,
    \"AuthenticationConfiguration\": {
      \"AccessRoleArn\": \"$ACCESS_ROLE_ARN\"
    }
  }" \
  --instance-configuration "Cpu=1 vCPU,Memory=2 GB" \
  --health-check-configuration "Protocol=HTTP,Path=/health,Interval=10,Timeout=5,HealthyThreshold=1,UnhealthyThreshold=5" \
  --region $AWS_REGION
```

### 5.3 — Get the App Runner URL

```bash
aws apprunner describe-service \
  --service-arn $(aws apprunner list-services \
    --query "ServiceSummaryList[?ServiceName=='pune-price-prediction'].ServiceArn" \
    --output text) \
  --query "Service.ServiceUrl" \
  --output text
```

**Success:** Returns a URL like `https://xxxxxxxxxxxx.us-east-1.awsapprunner.com`

```bash
curl https://xxxxxxxxxxxx.us-east-1.awsapprunner.com/health
# {"status":"API is healthy and running."}
```

### 5.4 — Update the service after a new push to ECR

```bash
# Get service ARN
SERVICE_ARN=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='pune-price-prediction'].ServiceArn" \
  --output text)

# Trigger redeployment
aws apprunner start-deployment --service-arn $SERVICE_ARN
```

Or enable `AutoDeploymentsEnabled=true` (set above) — then every ECR push triggers a redeploy automatically.

---

## PHASE 6 — Environment Variables and Secrets

**Goal:** Store secrets securely in AWS Secrets Manager, not in environment variables in plain text.

### 6.1 — Create a secret in AWS Secrets Manager

```bash
aws secretsmanager create-secret \
  --name "pune-price-prediction/env" \
  --description "Runtime secrets for the Pune Price Prediction API" \
  --secret-string '{
    "DAGSHUB_TOKEN": "YOUR_DAGSHUB_TOKEN",
    "DAGSHUB_USER":  "YOUR_DAGSHUB_USERNAME",
    "DAGSHUB_REPO":  "YOUR_DAGSHUB_REPO"
  }' \
  --region $AWS_REGION
```

### 6.2 — Update ECS task definition to read from Secrets Manager

The `secrets` block in `infra/aws/ecs-task-definition.json` already references Secrets Manager. Update the ARNs:

```json
"secrets": [
  {
    "name":      "DAGSHUB_TOKEN",
    "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:pune-price-prediction/env:DAGSHUB_TOKEN::"
  }
]
```

Register a new task definition revision and update the service:
```bash
aws ecs register-task-definition --cli-input-json file://infra/aws/ecs-task-definition.json

aws ecs update-service \
  --cluster pune-price-cluster \
  --service pune-price-service \
  --task-definition pune-price-prediction \
  --force-new-deployment
```

### 6.3 — Update a secret value

```bash
aws secretsmanager update-secret \
  --secret-id "pune-price-prediction/env" \
  --secret-string '{"DAGSHUB_TOKEN":"NEW_TOKEN_VALUE"}'
```

---

## PHASE 7 — Custom Domain + HTTPS

**Goal:** Serve the API at `https://api.YOUR_DOMAIN.com` with an SSL certificate.

### 7.1 — Register a domain (if you don't have one)

```bash
# Search for available domain
aws route53domains check-domain-availability \
  --domain-name YOUR_DOMAIN.com

# Register (opens billing — ~$12/year for .com)
aws route53domains register-domain \
  --domain-name YOUR_DOMAIN.com \
  --duration-in-years 1 \
  --auto-renew \
  --admin-contact '{"FirstName":"YOUR_FIRST_NAME","LastName":"YOUR_LAST_NAME","ContactType":"PERSON","Email":"YOUR_EMAIL","PhoneNumber":"+1.5555555555","AddressLine1":"123 Main St","City":"Pune","State":"MH","CountryCode":"IN","ZipCode":"411001"}'
```

### 7.2 — Request an ACM certificate

```bash
aws acm request-certificate \
  --domain-name api.YOUR_DOMAIN.com \
  --validation-method DNS \
  --region $AWS_REGION
```

Note the `CertificateArn` in the output.

```bash
# Get CNAME record for DNS validation
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:us-east-1:YOUR_ACCOUNT:certificate/CERT_ID \
  --query "Certificate.DomainValidationOptions[0].ResourceRecord"
```

### 7.3 — Add the CNAME to Route 53

```bash
# Get hosted zone ID
ZONE_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name YOUR_DOMAIN.com \
  --query "HostedZones[0].Id" --output text | sed 's|/hostedzone/||')

# Create the validation CNAME (replace NAME and VALUE from step 7.2 output)
aws route53 change-resource-record-sets \
  --hosted-zone-id $ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name":            "_acm-challenge.api.YOUR_DOMAIN.com",
        "Type":            "CNAME",
        "TTL":             300,
        "ResourceRecords": [{"Value": "VALIDATION_VALUE_FROM_ACM"}]
      }
    }]
  }'
```

### 7.4 — For App Runner: associate the custom domain

```bash
aws apprunner associate-custom-domain \
  --service-arn $SERVICE_ARN \
  --domain-name api.YOUR_DOMAIN.com
```

App Runner will return CNAME records to add to Route 53. Follow the same pattern as above.

**Success:** `https://api.YOUR_DOMAIN.com/health` returns the health response.

---

## PHASE 8 — Monitoring

**Goal:** Get alerted before users notice problems.

### 8.1 — View CloudWatch logs

```bash
# Stream live logs from the ECS task
aws logs tail /ecs/pune-price-prediction --follow --region $AWS_REGION
```

```bash
# Or through the AWS Console:
# CloudWatch → Log groups → /ecs/pune-price-prediction
```

### 8.2 — Create a CloudWatch alarm for API errors (5xx)

For App Runner:
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "pune-api-5xx-errors" \
  --alarm-description "Alert when API returns 5xx errors" \
  --metric-name "Http5xxRequests" \
  --namespace "AWS/AppRunner" \
  --dimensions Name=ServiceName,Value=pune-price-prediction \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 5 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --statistic Sum \
  --alarm-actions arn:aws:sns:us-east-1:YOUR_ACCOUNT:YOUR_SNS_TOPIC
```

### 8.3 — Create an SNS topic for email alerts

```bash
# Create SNS topic
SNS_ARN=$(aws sns create-topic \
  --name pune-api-alerts \
  --query TopicArn --output text)

# Subscribe your email
aws sns subscribe \
  --topic-arn $SNS_ARN \
  --protocol email \
  --notification-endpoint shadrack.n159@gmail.com
# Check your email for the confirmation link
```

### 8.4 — Create a CloudWatch dashboard

```bash
aws cloudwatch put-dashboard \
  --dashboard-name "PunePricePrediction" \
  --dashboard-body '{
    "widgets": [
      {
        "type": "metric",
        "properties": {
          "title": "Request Count",
          "metrics": [["AWS/AppRunner","Requests","ServiceName","pune-price-prediction"]],
          "period": 60, "stat": "Sum"
        }
      },
      {
        "type": "metric",
        "properties": {
          "title": "Response Time",
          "metrics": [["AWS/AppRunner","RequestLatency","ServiceName","pune-price-prediction"]],
          "period": 60, "stat": "Average"
        }
      }
    ]
  }'
```

---

## PHASE 9 — DagsHub Integration

**Goal:** Replace local MLflow + DVC with a shared DagsHub remote so any teammate can replicate experiments.

### 9.1 — Create a DagsHub account and repository

1. Go to https://dagshub.com and sign up
2. Create a new repository (name: `pune-price-prediction`)
3. Go to your profile → Settings → Tokens → Create a new token
4. Copy the token

### 9.2 — Set credentials in .env

```
DAGSHUB_USER=YOUR_DAGSHUB_USERNAME
DAGSHUB_TOKEN=YOUR_DAGSHUB_TOKEN
DAGSHUB_REPO=pune-price-prediction
```

### 9.3 — Add DagsHub as DVC remote

```bash
# Get the exact DVC commands for your repo
python -m mlops.dagshub_setup --print-dvc-cmds

# This will print something like:
dvc remote add origin https://dagshub.com/SHADRACK-NAKOBA/pune-price-prediction.dvc
dvc remote modify origin --local auth basic
dvc remote modify origin --local user SHADRACK-NAKOBA
dvc remote modify origin --local password YOUR_DAGSHUB_TOKEN
dvc remote modify origin --local password YOUR_TOKEN
dvc remote default origin
```

Run those commands.

### 9.4 — Point MLflow at DagsHub

```bash
# Check that DagsHub credentials are being detected
python -m mlops.dagshub_setup --check

# Run a training + logging run
python -m mlops.mlflow_train
```

Open your DagsHub repo → Experiments tab — you should see the run logged there.

### 9.5 — Push model artifacts to DagsHub DVC remote

```bash
dvc push
```

Now any teammate can run `dvc pull` (with the token) to get the exact same model files.

---

## PHASE 10 — Go-Live Validation Checklist

Work through this after every deployment to confirm everything is working.

```
INFRASTRUCTURE
[ ] docker build completes without errors
[ ] docker run starts the container and /health returns 200
[ ] ECR repository exists and has the latest image
[ ] ECS service or App Runner service is in "RUNNING" state
[ ] CloudWatch log group is receiving log lines

API FUNCTIONALITY
[ ] GET  /health          → {"status": "API is healthy and running."}
[ ] GET  /model/info      → {"model_type": "VotingRegressor", ...}
[ ] POST /predict         → valid JSON with predicted_price, lower_bound, upper_bound
[ ] POST /predict (bad input) → 422 Unprocessable Entity (Pydantic rejects it)
[ ] GET  /docs            → Swagger UI loads

SECURITY
[ ] .env is NOT committed to GitHub (git log -- .env returns nothing)
[ ] model/*.pkl files are NOT committed to GitHub (DVC-tracked)
[ ] Docker container runs as non-root user (docker inspect | grep User)
[ ] CORS_ORIGINS is restricted to your domain in production

PERFORMANCE
[ ] /predict responds in < 2 seconds for a normal request
[ ] /health responds in < 100ms

OBSERVABILITY
[ ] CloudWatch alarm is active and notification email received
[ ] At least one MLflow run is visible in the tracking UI
[ ] dvc status shows "Data and pipelines are up to date."

REPRODUCIBILITY
[ ] git clone + dvc pull + dvc repro produces identical metrics
[ ] params.yaml ridge.alpha change → dvc repro re-trains and updates metrics
```

---

## BONUS PHASE — EC2 Deployment

For learners who want full control or to run a cheaper persistent instance.

### EC2.1 — Launch an EC2 instance

```bash
# Launch Amazon Linux 2023, t3.medium (2 vCPU, 4 GB — enough for Python + sklearn)
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.medium \
  --key-name YOUR_KEY_PAIR_NAME \
  --security-group-ids $SG_ID \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=pune-price-api}]' \
  --query "Instances[0].InstanceId" --output text)

echo "Instance ID: $INSTANCE_ID"
```

### EC2.2 — Get the public IP and SSH in

```bash
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text)

ssh -i YOUR_KEY_PAIR_FILE.pem ec2-user@$PUBLIC_IP
```

### EC2.3 — Install Docker on EC2

```bash
# Run ON the EC2 instance (after SSH)
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -aG docker ec2-user
exit   # logout and SSH back in for group change to take effect
ssh -i YOUR_KEY_PAIR_FILE.pem ec2-user@$PUBLIC_IP
```

### EC2.4 — Pull and run the container from ECR

```bash
# On EC2 instance — authenticate to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Pull the image
docker pull YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction:latest

# Run it (automatically restart on reboot/crash)
docker run -d \
  --name pune-price-api \
  --restart unless-stopped \
  -p 80:8000 \
  YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction:latest
```

### EC2.5 — Open port 80 in the security group

```bash
# On your LOCAL machine (not EC2)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0
```

**Access:** `http://$PUBLIC_IP/health`

### EC2.6 — Auto-start on reboot (systemd service)

Create `/etc/systemd/system/pune-price.service` on EC2:

```ini
[Unit]
Description=Pune Price Prediction API
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStart=/usr/bin/docker start -a pune-price-api
ExecStop=/usr/bin/docker stop pune-price-api

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable pune-price.service
sudo systemctl start  pune-price.service
sudo systemctl status pune-price.service
```

### EC2 vs ECS vs App Runner — When to use which

| Deployment | Pros | Cons | Best for |
|---|---|---|---|
| **EC2** | Full control, cheapest sustained cost | Manual OS patching, no auto-scaling out-of-box | Learning, demos, steady traffic |
| **ECS Fargate** | Fully managed containers, auto-scaling, ALB integration | More setup steps | Production with variable traffic |
| **App Runner** | One command, auto TLS, auto-scaling | Less control, slightly higher cost | Fastest path to production |
