# Nakoba — ECR + ECS Fargate Implementation Walkthrough

**Project:** Pune Real Estate Price Prediction — Production MLOps  
**Author:** Shadrack Nakoba (shadrack.n159@gmail.com)  
**GitHub:** https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction  
**AWS Account:** 211125741068  
**Region:** us-east-1  
**Date completed:** 2026-05-23  

---

## What Was Built

A FastAPI Docker container serving a ML price prediction model, deployed to:
- **Amazon ECR** — private Docker image registry
- **Amazon ECS Fargate** — serverless container hosting (no EC2 to manage)

Live endpoint (IP changes on task restart — see Section 9 for stable URL):
```
http://3.237.74.138:8000/health
http://3.237.74.138:8000/docs
```

---

## Architecture

```
GitHub push
    │
    ▼
GitHub Actions CI/CD
    │  lint → test → docker build → (manual) deploy
    ▼
Amazon ECR
    │  211125741068.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction:latest
    ▼
Amazon ECS Fargate (cluster: pune-mlops, service: pune-price-prediction)
    │  0.5 vCPU / 1 GB RAM, public IP, port 8000
    ▼
FastAPI (src/app.py)
    │  /health  /predict  /model/info  /docs
    ▼
VotingRegressor → predicted price in Rs lakhs
```

---

## Prerequisites (one-time checks)

```powershell
# Verify AWS CLI is installed and configured
aws sts get-caller-identity
# Expected output: Account: 211125741068, Arn: .../user/Prince

# Verify Docker is running
docker version

# Verify you're in the project folder
cd "C:\Users\admin\Desktop\mlops-pune-price-prediction"
```

---

## Step 1 — Set Variables

Run this block at the start of every PowerShell session.
All commands below use these variables.

```powershell
$ACCOUNT  = "211125741068"
$REGION   = "us-east-1"
$ECR_REPO = "pune-price-prediction"
$CLUSTER  = "pune-mlops"
$SERVICE  = "pune-price-prediction"
$ECR_URI  = "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO"
```

---

## Step 2 — Create ECR Repository

```powershell
aws ecr create-repository `
  --repository-name $ECR_REPO `
  --region $REGION
```

**Expected output:** JSON with `repositoryUri`:
`211125741068.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction`

---

## Step 3 — Grant IAM Permissions

### Issue encountered
When running `docker push`, the IAM user `Prince` got:
```
denied: User is not authorized to perform: ecr:InitiateLayerUpload
```

When trying to fix via CLI:
```
AccessDenied: no identity-based policy allows iam:AttachUserPolicy
```

When trying via Console:
```
The selected policies exceed this account's quota
```

### Fix — Inline Policy (bypasses managed policy quota)

1. Go to **AWS Console → IAM → Users → Prince**
2. Click **"Add inline policy"** (small link, not the big "Add permissions" button)
3. Click the **JSON** tab and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage",
        "ecr:CreateRepository",
        "ecr:DescribeRepositories",
        "ecs:*",
        "iam:PassRole",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:CreateSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress"
      ],
      "Resource": "*"
    }
  ]
}
```

4. Name it `mlops-deploy-policy` → **Create policy**

---

## Step 4 — Build and Push Docker Image to ECR

```powershell
# Step 4a — Create stub model files (needed because real model files
# are DVC-tracked and not in git; stubs let the container start)
& "C:\Users\admin\Downloads\MLOps_Pune_Price_Prediction_Project\venv\Scripts\python.exe" `
    scripts\create_model_stubs.py

# Step 4b — Login to ECR
aws ecr get-login-password --region $REGION | `
  docker login --username AWS --password-stdin `
  "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

# Step 4c — Build Docker image
docker build -t "$ECR_URI`:latest" .

# Step 4d — Push to ECR
docker push "$ECR_URI`:latest"
```

**Expected:** All layers push successfully, digest printed at end.

---

## Step 5 — Create ECS Task Execution IAM Role

This role lets ECS pull your image from ECR and write logs to CloudWatch.

```powershell
aws iam create-role `
  --role-name ecsTaskExecutionRole `
  --assume-role-policy-document '{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"ecs-tasks.amazonaws.com\"},\"Action\":\"sts:AssumeRole\"}]}'

aws iam attach-role-policy `
  --role-name ecsTaskExecutionRole `
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

**Note:** If the role already exists (re-running this walkthrough), you'll get
`EntityAlreadyExists` — that is fine, skip to Step 6.

---

## Step 6 — Register ECS Task Definition

### Issue encountered
The original `infra/aws/ecs-task-definition.json` had placeholders:
```
"executionRoleArn": "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:role/ecsTaskExecutionRole"
```
Running `register-task-definition` returned: `Role is not valid`

### Fix
The file was updated with real values. The final working file is at
`infra/aws/ecs-task-definition.json` in this repo (already filled in).

```powershell
aws ecs register-task-definition `
  --cli-input-json file://infra/aws/ecs-task-definition.json `
  --region $REGION
```

**Expected:** JSON output showing `"status": "ACTIVE"`, `"revision": 1`

---

## Step 7 — Create ECS Cluster

```powershell
aws ecs create-cluster --cluster-name $CLUSTER --region $REGION
```

**Expected:** JSON with `"status": "ACTIVE"`, `"clusterName": "pune-mlops"`

---

## Step 8 — Create Security Group and ECS Service

```powershell
# Step 8a — Get default VPC and subnets
$VPC_ID = aws ec2 describe-vpcs --filters Name=isDefault,Values=true `
  --query "Vpcs[0].VpcId" --output text --region $REGION

# Step 8b — Create security group
$SG_ID = aws ec2 create-security-group `
  --group-name pune-api-sg `
  --description "Allow port 8000 for Pune Price API" `
  --vpc-id $VPC_ID --region $REGION `
  --query "GroupId" --output text

# Step 8c — Open port 8000 to the world
aws ec2 authorize-security-group-ingress `
  --group-id $SG_ID `
  --protocol tcp --port 8000 --cidr 0.0.0.0/0 `
  --region $REGION

echo "Security group: $SG_ID"

# Step 8d — Get two subnet IDs from the default VPC
aws ec2 describe-subnets --filters Name=defaultForAz,Values=true `
  --query "Subnets[*].SubnetId" --output text --region $REGION
```

Your subnet IDs (already discovered):
- `subnet-0a8ba0a09aaffa2f7`
- `subnet-0d5a8a16c7aa5a916`

```powershell
# Step 8e — Create the ECS service
aws ecs create-service `
  --cluster $CLUSTER `
  --service-name $SERVICE `
  --task-definition pune-price-prediction:1 `
  --desired-count 1 `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[subnet-0a8ba0a09aaffa2f7,subnet-0d5a8a16c7aa5a916],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" `
  --region $REGION
```

---

## Step 9 — Fix: CloudWatch Log Group Missing

### Issue encountered
Service events showed:
```
ResourceInitializationError: failed to create Cloudwatch log stream:
ResourceNotFoundException: The specified log group does not exist
```

The task was starting and immediately stopping because it could not write logs.

### Fix

```powershell
aws logs create-log-group `
  --log-group-name "/ecs/pune-price-prediction" `
  --region $REGION
```

ECS automatically retried and started the task after this.

---

## Step 10 — Fix: Model Files Missing in Docker Image

### Issue encountered
After the log group fix, the container started but immediately crashed:
```
FileNotFoundError: model/property_price_prediction_voting.sav
```

The Docker image was built when `model/` was empty (only `.gitkeep`).
The real model files are DVC-tracked and were not on disk.

### Fix — Phase 1: Stub model files (get service running first)

The file `scripts/create_model_stubs.py` generates 6 valid sklearn objects
that inference.py can load. The service starts, all endpoints respond.
**Predictions are not meaningful with stubs** (see Section 13 for real files).

```powershell
# Generate stubs
& "C:\Users\admin\Downloads\MLOps_Pune_Price_Prediction_Project\venv\Scripts\python.exe" `
    scripts\create_model_stubs.py

# Rebuild image (now includes model files)
docker build -t "$ECR_URI`:latest" .
docker push "$ECR_URI`:latest"

# Force ECS to pull new image
aws ecs update-service `
  --cluster $CLUSTER `
  --service $SERVICE `
  --force-new-deployment `
  --region $REGION
```

### Fix — Phase 2: Replace stubs with real trained model files

Searched the machine for `.sav` files and found the real Lab 3 outputs at:
`C:\Users\admin\mlops-pune-price-prediction\model\` (most recent, May 9 2026)

All 6 required files were present:

| File | Size | Notes |
|---|---|---|
| `property_price_prediction_voting.sav` | 5,451 bytes | VotingRegressor |
| `count_vectorizer.pkl` | 47,243 bytes | Real trained vocabulary |
| `all_feature_names.pkl` | 458 bytes | 115 feature names |
| `amenities_score_price_map.pkl` | 71 bytes | Amenity encoding |
| `sub_area_price_map.pkl` | 731 bytes | Location encoding |
| `interval_est.pkl` | 73 bytes | z_score + residual_std |

```powershell
# Copy real model files into the project
Copy-Item "C:\Users\admin\mlops-pune-price-prediction\model\all_feature_names.pkl"        "model\"
Copy-Item "C:\Users\admin\mlops-pune-price-prediction\model\amenities_score_price_map.pkl" "model\"
Copy-Item "C:\Users\admin\mlops-pune-price-prediction\model\count_vectorizer.pkl"          "model\"
Copy-Item "C:\Users\admin\mlops-pune-price-prediction\model\interval_est.pkl"              "model\"
Copy-Item "C:\Users\admin\mlops-pune-price-prediction\model\property_price_prediction_voting.sav" "model\"
Copy-Item "C:\Users\admin\mlops-pune-price-prediction\model\sub_area_price_map.pkl"        "model\"

# Rebuild and push with real models
docker build -t "$ECR_URI`:latest" .
docker push "$ECR_URI`:latest"
aws ecs update-service --cluster $CLUSTER --service $SERVICE `
  --force-new-deployment --region $REGION
```

---

## Step 11 — Get the Public IP

### Issue encountered
Running `list-tasks` without `--desired-status RUNNING` returned an empty ARN
even when the service showed `"running": 1`. The `$TASK_ARN` variable was empty,
causing all downstream commands to fail with `taskId length should be one of [32,36]`
and the IP to show as `None`.

### Fix — Always use `--desired-status RUNNING`

Run this 90 seconds after any new deployment:

```powershell
Start-Sleep -Seconds 90

# IMPORTANT: must include --desired-status RUNNING
$TASK_ARN = aws ecs list-tasks --cluster $CLUSTER --service-name $SERVICE `
  --region $REGION --desired-status RUNNING --query "taskArns[0]" --output text

echo "Task ARN: $TASK_ARN"

$ENI = aws ecs describe-tasks --cluster $CLUSTER --tasks $TASK_ARN `
  --region $REGION `
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" `
  --output text

$PUBLIC_IP = aws ec2 describe-network-interfaces --network-interface-ids $ENI `
  --query "NetworkInterfaces[0].Association.PublicIp" --output text --region $REGION

echo "http://$PUBLIC_IP`:8000/health"
echo "http://$PUBLIC_IP`:8000/docs"
echo "http://$PUBLIC_IP`:8000/predict"
```

If `$TASK_ARN` is still empty after 90 seconds, check service events:

```powershell
aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $REGION `
  --query "services[0].{running:runningCount,pending:pendingCount,desired:desiredCount}"

aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $REGION `
  --query "services[0].events[:3]"
```

**Important:** This IP changes every time ECS replaces the task.
See Section 14 for a stable URL using a Load Balancer.

---

## Step 12 — Verify the Service is Healthy

```powershell
# Check task status
aws ecs describe-tasks --cluster $CLUSTER --tasks $TASK_ARN `
  --region $REGION `
  --query "tasks[0].{status:lastStatus,health:healthStatus}"

# Check service events (last 5)
aws ecs describe-services `
  --cluster $CLUSTER --services $SERVICE --region $REGION `
  --query "services[0].events[:5]"

# Hit the health endpoint
curl "http://$PUBLIC_IP`:8000/health"

# Expected response:
# {"status":"ok","model":"VotingRegressor","features":115}
```

---

## Section 13 — Make `/predict` Work with Real Model Files

The stub model always returns 1.0 lakh regardless of input.
To get real predictions you need the 6 model files produced in Lab 3.

### Option A — Find files from your Lab 3 notebook

```powershell
# Search for the .sav file on your machine
Get-ChildItem "C:\Users\admin\" -Recurse -Filter "*.sav" -ErrorAction SilentlyContinue
```

Once you find them, copy to `model/` and rebuild:

```powershell
Copy-Item "C:\path\to\lab3\outputs\*.sav" "model\"
Copy-Item "C:\path\to\lab3\outputs\*.pkl" "model\"

docker build -t "$ECR_URI`:latest" .
docker push "$ECR_URI`:latest"
aws ecs update-service --cluster $CLUSTER --service $SERVICE `
  --force-new-deployment --region $REGION
```

### Option B — Retrain from scratch with DVC

```powershell
# Install MLOps dependencies
pip install -r requirements-mlops.txt

# Copy your raw data (Pune RE Data.xlsx) to project root, then:
dvc repro        # runs clean → features → train pipeline
dvc metrics show # verify r2=0.852

# The 6 model files are now in model/
# Rebuild Docker image
docker build -t "$ECR_URI`:latest" .
docker push "$ECR_URI`:latest"
aws ecs update-service --cluster $CLUSTER --service $SERVICE `
  --force-new-deployment --region $REGION
```

### Option C — Push model files to DagsHub DVC remote first

Once you have a DagsHub account and the model files:

```powershell
$env:DAGSHUB_USER  = "SHADRACK-NAKOBA"
$env:DAGSHUB_TOKEN = "your_token_here"
$env:DAGSHUB_REPO  = "Nakoba-pune-price-prediction"

dvc remote modify origin --local auth basic
dvc remote modify origin --local user $env:DAGSHUB_USER
dvc remote modify origin --local password $env:DAGSHUB_TOKEN
dvc push model/   # upload real files to DagsHub
```

Then in GitHub Actions, add these three as GitHub Secrets and the CI
`docker-build` job will `dvc pull` real files automatically on every push.

### Test `/predict` once real models are deployed

```powershell
$body = @{
    property_type = 2
    area          = 1000.0
    sub_area      = "kothrud"
    description   = "spacious 2bhk apartment near park with good ventilation"
    clubhouse     = 1; school = 1; hospital = 0
    mall          = 1; park   = 1; pool    = 0; gym = 1
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://$PUBLIC_IP`:8000/predict" `
  -ContentType "application/json" `
  -Body $body
```

**Expected response with real model:**
```json
{
  "predicted_price": 62.3,
  "lower_bound": 30.94,
  "upper_bound": 93.66,
  "features_used": 115
}
```

---

## Section 14 — Serve to Real Users (Stable HTTPS URL)

Right now the service has two problems for real users:
1. **No stable URL** — IP changes on every task restart
2. **No HTTPS** — browsers warn about insecure connections

### Fix: Application Load Balancer + ACM Certificate

**Prerequisites:** A domain name (buy one in Route 53 for ~$12/yr or use one you own)

#### Step 14a — Request a free HTTPS certificate

```powershell
# Replace with your domain
$DOMAIN = "api.yourdomain.com"

aws acm request-certificate `
  --domain-name $DOMAIN `
  --validation-method DNS `
  --region $REGION
```

Go to **AWS Console → Certificate Manager** and click "Create records in Route 53"
to validate ownership. Wait ~5 minutes until status shows **Issued**.

#### Step 14b — Create the Application Load Balancer

```powershell
# Get all default subnet IDs (need at least 2 AZs for ALB)
$SUBNETS = (aws ec2 describe-subnets `
  --filters Name=defaultForAz,Values=true `
  --query "Subnets[*].SubnetId" --output text --region $REGION) -split "\t"

# Create a security group for the ALB (port 80 and 443)
$ALB_SG = aws ec2 create-security-group `
  --group-name pune-alb-sg `
  --description "ALB security group" `
  --vpc-id $VPC_ID --region $REGION `
  --query "GroupId" --output text

aws ec2 authorize-security-group-ingress `
  --group-id $ALB_SG --protocol tcp --port 80  --cidr 0.0.0.0/0 --region $REGION
aws ec2 authorize-security-group-ingress `
  --group-id $ALB_SG --protocol tcp --port 443 --cidr 0.0.0.0/0 --region $REGION

# Create the ALB
$ALB_ARN = aws elbv2 create-load-balancer `
  --name pune-api-alb `
  --subnets $SUBNETS `
  --security-groups $ALB_SG `
  --region $REGION `
  --query "LoadBalancers[0].LoadBalancerArn" --output text

echo "ALB ARN: $ALB_ARN"
```

#### Step 14c — Create target group (points at your ECS tasks)

```powershell
$TG_ARN = aws elbv2 create-target-group `
  --name pune-api-tg `
  --protocol HTTP --port 8000 `
  --vpc-id $VPC_ID `
  --target-type ip `
  --health-check-path /health `
  --region $REGION `
  --query "TargetGroups[0].TargetGroupArn" --output text

echo "Target Group ARN: $TG_ARN"
```

#### Step 14d — Add HTTPS listener to ALB

```powershell
# Get your certificate ARN from ACM
$CERT_ARN = aws acm list-certificates `
  --query "CertificateSummaryList[0].CertificateArn" --output text --region $REGION

# HTTPS listener (port 443)
aws elbv2 create-listener `
  --load-balancer-arn $ALB_ARN `
  --protocol HTTPS --port 443 `
  --certificates CertificateArn=$CERT_ARN `
  --default-actions Type=forward,TargetGroupArn=$TG_ARN `
  --region $REGION

# HTTP → HTTPS redirect (port 80)
aws elbv2 create-listener `
  --load-balancer-arn $ALB_ARN `
  --protocol HTTP --port 80 `
  --default-actions "Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}" `
  --region $REGION
```

#### Step 14e — Update ECS service to use the ALB

Delete and recreate the service with the load balancer attached:

```powershell
# Delete existing service (scale to 0 first)
aws ecs update-service --cluster $CLUSTER --service $SERVICE `
  --desired-count 0 --region $REGION
aws ecs delete-service --cluster $CLUSTER --service $SERVICE --region $REGION

# Recreate with ALB
aws ecs create-service `
  --cluster $CLUSTER `
  --service-name $SERVICE `
  --task-definition pune-price-prediction:1 `
  --desired-count 1 `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[subnet-0a8ba0a09aaffa2f7,subnet-0d5a8a16c7aa5a916],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" `
  --load-balancers "targetGroupArn=$TG_ARN,containerName=pune-price-api,containerPort=8000" `
  --region $REGION
```

#### Step 14f — Point your domain to the ALB

```powershell
# Get ALB DNS name
aws elbv2 describe-load-balancers --load-balancer-arns $ALB_ARN `
  --query "LoadBalancers[0].DNSName" --output text --region $REGION
```

Go to **Route 53 → your domain → Create record**:
- Type: A (Alias)
- Name: `api` (or whatever subdomain you want)
- Route traffic to: Alias to Application Load Balancer → us-east-1 → select your ALB

After ~2 minutes:
```
https://api.yourdomain.com/health   ← stable HTTPS URL
https://api.yourdomain.com/docs     ← Swagger UI for real users
```

#### ALB cost breakdown

| Resource | Cost |
|---|---|
| ALB hourly | $0.008/hr × 720h = ~$5.76/mo |
| ALB LCU usage (light traffic) | ~$2–3/mo |
| ACM certificate | **Free** |
| Route 53 hosted zone | $0.50/mo |
| **Total extra for HTTPS** | **~$8–9/mo** |

#### Alternative — No domain? Use ALB DNS directly (HTTP only)

If you don't have a domain, skip Steps 14a and 14f.
After creating the ALB and target group, get its DNS name:

```powershell
$ALB_DNS = aws elbv2 describe-load-balancers --load-balancer-arns $ALB_ARN `
  --query "LoadBalancers[0].DNSName" --output text --region $REGION
echo "http://$ALB_DNS/health"
```

This gives you a stable URL like:
`http://pune-api-alb-1234567890.us-east-1.elb.amazonaws.com/health`

It never changes — even when ECS replaces the task. No domain needed.

---

## Section 14g — ECS Auto-Scaling (handle real user load)

Without auto-scaling, you have exactly 1 task running at all times.
Under heavy load it will slow down or crash. This adds automatic scale-out.

```powershell
# Register the ECS service as a scalable target
aws application-autoscaling register-scalable-target `
  --service-namespace ecs `
  --resource-id "service/$CLUSTER/$SERVICE" `
  --scalable-dimension ecs:service:DesiredCount `
  --min-capacity 1 `
  --max-capacity 4 `
  --region $REGION

# Scale OUT when CPU > 70% for 2 minutes
aws application-autoscaling put-scaling-policy `
  --service-namespace ecs `
  --resource-id "service/$CLUSTER/$SERVICE" `
  --scalable-dimension ecs:service:DesiredCount `
  --policy-name pune-api-scale-out `
  --policy-type TargetTrackingScaling `
  --target-tracking-scaling-policy-configuration `
    "TargetValue=70.0,PredefinedMetricSpecification={PredefinedMetricType=ECSServiceAverageCPUUtilization},ScaleOutCooldown=60,ScaleInCooldown=300" `
  --region $REGION
```

This keeps you at 1 task at idle, scales up to 4 tasks under load, and
scales back down automatically. Each extra task costs ~$0.59/day.

---

## Section 15 — MLflow Dashboard

Three options — pick one. DagsHub (Option B) is recommended for this project.

### Option A — Run locally (instant, free, private)

```powershell
cd "C:\Users\admin\Desktop\mlops-pune-price-prediction"
pip install mlflow
mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000
# Open http://localhost:5000
```

**What you'll see in the UI:**
- Every training run with timestamp
- Metrics: R², RMSE, MAE per run
- Parameters: ridge alpha, lasso alpha, test_size, random_state
- Artifacts: model file path

**Log a new training run:**
```powershell
# Activate your venv first
& "C:\Users\admin\Downloads\MLOps_Pune_Price_Prediction_Project\venv\Scripts\Activate.ps1"

# Single training run → logged to mlflow.db
python -m mlops.mlflow_train

# Sweep Ridge alpha 0.01 → 1000, find best
python -m mlops.mlflow_sweep

# Query best run from the sweep
python -m mlops.mlflow_query
```

**Limitation:** Only visible on your laptop. Not shareable.

---

### Option B — DagsHub hosted MLflow (recommended — free + shareable)

DagsHub gives you a hosted MLflow UI at a public URL. No server to manage.

#### Step B1 — Create DagsHub account

1. Go to **https://dagshub.com** → **Sign up with GitHub**
2. Click **"Create"** → **"Connect a repository"**
3. Select `SHADRACK-NAKOBA/Nakoba-pune-price-prediction`
4. You now have:
   - **MLflow UI:** `https://dagshub.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction.mlflow`
   - **DVC remote:** `https://dagshub.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction.dvc`

#### Step B2 — Get your DagsHub token

Go to **https://dagshub.com/user/settings/tokens** → Generate new token → copy it.

#### Step B3 — Configure the project

```powershell
$env:DAGSHUB_USER  = "SHADRACK-NAKOBA"
$env:DAGSHUB_TOKEN = "your_dagshub_token_here"
$env:DAGSHUB_REPO  = "Nakoba-pune-price-prediction"

# Verify credentials are working
python -m mlops.dagshub_setup --check

# Set MLflow URI to DagsHub for this session
python -m mlops.dagshub_setup --configure
```

#### Step B4 — Log experiments to DagsHub

```powershell
# Single run
python -m mlops.mlflow_train

# Ridge alpha sweep (logs ~10 runs with CV scores)
python -m mlops.mlflow_sweep

# Query: which alpha gave best CV R²?
python -m mlops.mlflow_query
```

Open **https://dagshub.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction.mlflow**
and you'll see all runs, metrics, and parameters in a shareable web UI.

#### Step B5 — Push real model files to DagsHub DVC remote

```powershell
dvc remote modify origin --local auth basic
dvc remote modify origin --local user $env:DAGSHUB_USER
dvc remote modify origin --local password $env:DAGSHUB_TOKEN

# Add model files to DVC tracking and push
dvc add model/property_price_prediction_voting.sav
dvc add model/count_vectorizer.pkl
dvc push
```

Now anyone can `dvc pull` the real model files from DagsHub.

#### Step B6 — Add secrets to GitHub Actions

Go to: **https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction/settings/secrets/actions**

| Secret | Value |
|---|---|
| `DAGSHUB_USER` | `SHADRACK-NAKOBA` |
| `DAGSHUB_TOKEN` | your DagsHub token |
| `DAGSHUB_REPO` | `Nakoba-pune-price-prediction` |

After this, every CI push automatically `dvc pull` real model files and logs
training metrics to DagsHub MLflow.

---

### Option C — Self-hosted MLflow on ECS (same AWS cluster, always-on)

Deploy MLflow as a second ECS service in the `pune-mlops` cluster.
Use S3 for artifact storage and SQLite on EFS for the tracking DB.
This keeps everything in AWS and avoids third-party dependencies.

#### Step C1 — Create S3 bucket for MLflow artifacts

```powershell
$MLFLOW_BUCKET = "pune-mlops-artifacts-211125741068"
aws s3 mb "s3://$MLFLOW_BUCKET" --region $REGION

# Allow ECS task execution role to access S3
aws iam put-role-policy `
  --role-name ecsTaskExecutionRole `
  --policy-name mlflow-s3-access `
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:*\"],\"Resource\":[\"arn:aws:s3:::$MLFLOW_BUCKET\",\"arn:aws:s3:::$MLFLOW_BUCKET/*\"]}]}"
```

#### Step C2 — Register MLflow task definition

```powershell
$MLFLOW_TASK = @"
{
  "family": "pune-mlflow",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::211125741068:role/ecsTaskExecutionRole",
  "containerDefinitions": [{
    "name": "mlflow",
    "image": "ghcr.io/mlflow/mlflow:latest",
    "essential": true,
    "portMappings": [{"containerPort": 5000, "protocol": "tcp"}],
    "command": [
      "mlflow", "server",
      "--host", "0.0.0.0",
      "--port", "5000",
      "--backend-store-uri", "sqlite:///mlflow.db",
      "--default-artifact-root", "s3://pune-mlops-artifacts-211125741068/mlflow"
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/pune-mlflow",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }]
}
"@

$MLFLOW_TASK | Out-File -FilePath "mlflow-task.json" -Encoding utf8

aws logs create-log-group --log-group-name "/ecs/pune-mlflow" --region $REGION

aws ecs register-task-definition `
  --cli-input-json file://mlflow-task.json `
  --region $REGION
```

#### Step C3 — Create MLflow security group and service

```powershell
# Security group: allow port 5000
$MLFLOW_SG = aws ec2 create-security-group `
  --group-name pune-mlflow-sg `
  --description "MLflow UI port 5000" `
  --vpc-id $VPC_ID --region $REGION `
  --query "GroupId" --output text

aws ec2 authorize-security-group-ingress `
  --group-id $MLFLOW_SG --protocol tcp --port 5000 --cidr 0.0.0.0/0 `
  --region $REGION

# Create MLflow service
aws ecs create-service `
  --cluster $CLUSTER `
  --service-name pune-mlflow `
  --task-definition pune-mlflow:1 `
  --desired-count 1 `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[subnet-0a8ba0a09aaffa2f7,subnet-0d5a8a16c7aa5a916],securityGroups=[$MLFLOW_SG],assignPublicIp=ENABLED}" `
  --region $REGION
```

#### Step C4 — Get MLflow public IP

```powershell
Start-Sleep -Seconds 60

$MLFLOW_TASK_ARN = aws ecs list-tasks --cluster $CLUSTER --service-name pune-mlflow `
  --region $REGION --desired-status RUNNING --query "taskArns[0]" --output text

$MLFLOW_ENI = aws ecs describe-tasks --cluster $CLUSTER --tasks $MLFLOW_TASK_ARN `
  --region $REGION `
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" `
  --output text

$MLFLOW_IP = aws ec2 describe-network-interfaces --network-interface-ids $MLFLOW_ENI `
  --query "NetworkInterfaces[0].Association.PublicIp" --output text --region $REGION

echo "MLflow UI: http://$MLFLOW_IP`:5000"
```

#### Step C5 — Point your training scripts at ECS MLflow

```powershell
$env:MLFLOW_TRACKING_URI = "http://$MLFLOW_IP`:5000"
python -m mlops.mlflow_train   # logs appear in ECS-hosted MLflow
```

**Cost:** ~$1.50/month extra (256 CPU / 512MB Fargate task)

**Note:** The SQLite DB is ephemeral (lost on task restart). For persistence,
use Amazon RDS PostgreSQL as the backend-store-uri instead (~$13/mo extra).

---

## Section 16 — GitHub Actions Auto-Deploy (final wiring)

### Issue encountered — Deploy job ECS step always skipped

The original deploy job had:
```yaml
- name: Force new ECS deployment (if ECS_CLUSTER_NAME secret is set)
  if: ${{ env.ECS_CLUSTER_NAME != '' }}
  env:
    ECS_CLUSTER_NAME: ${{ secrets.ECS_CLUSTER_NAME }}
```

`env.ECS_CLUSTER_NAME` is only set **inside the step scope** — checking it
in the `if:` condition (which runs before the step) always evaluates to empty.
The ECS update step was silently skipped on every deploy run.

### Fix — Reference secrets directly, remove conditional

```yaml
- name: Force new ECS deployment
  run: |
    aws ecs update-service \
      --cluster ${{ secrets.ECS_CLUSTER_NAME }} \
      --service ${{ secrets.ECS_SERVICE_NAME }} \
      --force-new-deployment \
      --region  ${{ secrets.AWS_REGION }}
```

Also added two new steps:
- **Wait for stability** — `aws ecs wait services-stable` blocks the job until
  the new task passes its health check (up to 5 min). Job fails if deploy fails.
- **Live URL step** — queries the running task's public IP and prints
  `/health`, `/docs`, `/predict` URLs directly in the Actions log.

### Step 16a — Add the 6 required secrets

Go to: **https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction/settings/secrets/actions**

Click **"New repository secret"** for each:

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM → Prince → Security credentials → Access key |
| `AWS_SECRET_ACCESS_KEY` | Same page → Secret access key |
| `AWS_REGION` | `us-east-1` |
| `ECR_REPO_NAME` | `pune-price-prediction` |
| `ECS_CLUSTER_NAME` | `pune-mlops` |
| `ECS_SERVICE_NAME` | `pune-price-prediction` |

### Step 16b — Trigger the deploy

Go to:
**https://github.com/SHADRACK-NAKOBA/Nakoba-pune-price-prediction/actions/workflows/ci.yml**

Click **"Run workflow"** → **"Run workflow"** (green button).

Full pipeline that runs:
```
Job 1: Lint (ruff + black)
    ↓
Job 2: pytest (36 tests with coverage)
    ↓
Job 3: Docker build + smoke test (curl /health after 45s)
    ↓
Job 4: Deploy (ECR push → ECS update → wait stable → print live URL)
```

### What the deploy job logs show on success

```
=============================================
DEPLOYMENT COMPLETE
=============================================
Image : 211125741068.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction:abc1234
Latest: 211125741068.dkr.ecr.us-east-1.amazonaws.com/pune-price-prediction:latest

Live endpoints:
  Health : http://<IP>:8000/health
  Swagger: http://<IP>:8000/docs
  Predict: http://<IP>:8000/predict
=============================================
```

Every future `git push` to main runs lint + test + docker build automatically.
Deploy to production requires clicking **"Run workflow"** manually (safety gate).

---

## Quick Reference — Daily Commands

```powershell
# Set variables (run at start of every session)
$ACCOUNT  = "211125741068"
$REGION   = "us-east-1"
$ECR_REPO = "pune-price-prediction"
$CLUSTER  = "pune-mlops"
$SERVICE  = "pune-price-prediction"
$ECR_URI  = "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO"

# Deploy new code
docker build -t "$ECR_URI`:latest" .
docker push "$ECR_URI`:latest"
aws ecs update-service --cluster $CLUSTER --service $SERVICE `
  --force-new-deployment --region $REGION

# Get current public IP  (--desired-status RUNNING is required)
$TASK_ARN = aws ecs list-tasks --cluster $CLUSTER --service-name $SERVICE `
  --region $REGION --desired-status RUNNING --query "taskArns[0]" --output text
$ENI = aws ecs describe-tasks --cluster $CLUSTER --tasks $TASK_ARN `
  --region $REGION `
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" `
  --output text
$PUBLIC_IP = aws ec2 describe-network-interfaces `
  --network-interface-ids $ENI `
  --query "NetworkInterfaces[0].Association.PublicIp" `
  --output text --region $REGION
echo "http://$PUBLIC_IP`:8000"

# Check service health
aws ecs describe-services --cluster $CLUSTER --services $SERVICE `
  --region $REGION --query "services[0].{running:runningCount,desired:desiredCount,status:status}"

# View logs (last 30 lines)
$STREAM = aws logs describe-log-streams `
  --log-group-name "/ecs/pune-price-prediction" `
  --order-by LastEventTime --descending `
  --query "logStreams[0].logStreamName" --output text --region $REGION
aws logs get-log-events `
  --log-group-name "/ecs/pune-price-prediction" `
  --log-stream-name $STREAM --limit 30 `
  --query "events[*].message" --output text --region $REGION

# Scale up (more tasks for load)
aws ecs update-service --cluster $CLUSTER --service $SERVICE `
  --desired-count 2 --region $REGION

# Scale to zero (stop billing — dev/weekend)
aws ecs update-service --cluster $CLUSTER --service $SERVICE `
  --desired-count 0 --region $REGION
```

---

## Issues Encountered — Summary Table

| # | Issue | Root Cause | Fix |
|---|---|---|---|
| 1 | `ecr:InitiateLayerUpload` denied | IAM user had no ECR permission | Add inline policy in IAM Console |
| 2 | `iam:AttachUserPolicy` AccessDenied | User can't self-grant permissions | Use AWS Console (root/admin) |
| 3 | "Selected policies exceed quota" | Managed policy attachment limit hit | Use inline policy instead |
| 4 | `RegisterTaskDefinition: Role is not valid` | Task def JSON had `YOUR_AWS_ACCOUNT_ID` placeholders | Replace with real account ID `211125741068` |
| 5 | Container won't start: `log group does not exist` | CloudWatch log group `/ecs/pune-price-prediction` never created | `aws logs create-log-group` |
| 6 | Container crashes: `FileNotFoundError: model/property_price_prediction_voting.sav` | Docker image built with empty `model/` directory | Run `create_model_stubs.py`, rebuild image |
| 7 | `--service-name` not recognized | ECS update-service uses `--service` not `--service-name` | Use `--service $SERVICE` |
| 8 | Task ARN empty, IP shows `None` (first time) | Task not yet started; script ran too early | `Start-Sleep -Seconds 90` before querying |
| 9 | Task ARN empty even with `running: 1` | `list-tasks` without `--desired-status RUNNING` returns empty | Always add `--desired-status RUNNING` to `list-tasks` |
| 10 | `/predict` returns wrong values (always 1.0) | Docker image built with stub model files | Copy real model files from `C:\Users\admin\mlops-pune-price-prediction\model\`, rebuild and push |
| 11 | ECS update step always skipped in deploy job | `if: ${{ env.ECS_CLUSTER_NAME != '' }}` checks env scope set inside step — always empty at eval time | Reference `${{ secrets.ECS_CLUSTER_NAME }}` directly in `run:`, remove conditional |
| 12 | Deploy job pushes image then exits — no confirmation it worked | No wait step; next task might be failing health checks silently | Added `aws ecs wait services-stable` — job blocks until healthy or fails loudly |
| 13 | `pip` not found — `pyenv` not configured | System Python managed by pyenv with no version set | Use full venv path: `C:\Users\admin\Downloads\MLOps_Pune_Price_Prediction_Project\venv\Scripts\pip.exe` |

---

## Current State and Next Steps

| Item | Status |
|---|---|
| ECR repository | ✅ Created and image pushed |
| ECS cluster (`pune-mlops`) | ✅ Active |
| ECS service (`pune-price-prediction`) | ✅ Running, 1 task |
| CloudWatch logs | ✅ `/ecs/pune-price-prediction` |
| GitHub Actions CI (lint + test + build) | ✅ Passing |
| `/health` endpoint | ✅ Responding |
| `/docs` Swagger UI | ✅ Accessible |
| `/predict` endpoint | ✅ Real model files deployed — returns actual predictions |
| Real model files | ✅ Copied from `C:\Users\admin\mlops-pune-price-prediction\model\` |
| MLflow dashboard (local) | ✅ Runs via venv — `http://localhost:5000` |
| MLflow dashboard (hosted) | ⬜ Optional — DagsHub Option B in Section 15 |
| GitHub Actions CI (lint+test+build) | ✅ Passing on every push |
| GitHub Actions deploy job | ✅ Fixed — ECS always updates, waits for stability, prints live URL |
| GitHub Secrets (6 required) | ⬜ Add via GitHub → Settings → Secrets → Actions |
| Stable HTTPS URL | ⬜ Optional — ALB + ACM + domain (Section 14) |
| ECS Auto-scaling | ⬜ Optional — CPU-based 1→4 tasks (Section 14g) |

**Remaining to activate full auto-deploy:**
1. Add the 6 GitHub Secrets (Section 16a) → click "Run workflow" → fully automated

**Optional next steps:**
2. Set up DagsHub (Section 15B) → hosted MLflow + DVC remote + real models in CI
3. Add ALB + domain (Section 14) → stable HTTPS URL for real users
4. Enable ECS auto-scaling (Section 14g) → handles traffic spikes
