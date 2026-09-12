# Travel Planner - Deployment Guide

## Quick Start (Local Docker)

### Prerequisites
- Docker & Docker Compose installed
- `.env` with `GEMINI_API_KEY` and `TAVILY_API_KEY`

### Deploy Locally
```bash
docker-compose up --build
```

Server runs at `http://localhost:8000`

---

## AWS Deployment (Recommended)

### Option 1: AWS App Runner (Easiest)

#### Step 1: Push to ECR
```bash
# Create ECR repository
aws ecr create-repository --repository-name travel-planner

# Build & push
docker build -t travel-planner:latest .
docker tag travel-planner:latest <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/travel-planner:latest
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/travel-planner:latest
```

#### Step 2: Create App Runner Service
```bash
aws apprunner create-service \
  --service-name travel-planner \
  --source-configuration '{
    "ImageRepository": {
      "ImageRepositoryType": "ECR",
      "ImageIdentifier": "<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/travel-planner:latest",
      "RepositoryCredentials": {
        "CredentialsProvisioningStatus": "ACTIVE"
      }
    }
  }' \
  --instance-configuration cpu=1,memory=2048 \
  --auto-scaling-configuration MaxConcurrency=100,MaxSize=10,MinSize=1
```

#### Step 3: Set Environment Variables
```bash
aws apprunner update-service \
  --service-arn arn:aws:apprunner:REGION:ACCOUNT:service/travel-planner/UUID \
  --source-configuration '{
    "ImageRepository": {...},
    "AutoDeploymentsEnabled": true
  }' \
  --instance-configuration '{
    "EnvironmentVariables": {
      "GEMINI_API_KEY": "your-key",
      "TAVILY_API_KEY": "your-key"
    }
  }'
```

✅ **Service deployed!** App Runner provides:
- Auto-scaling
- SSL/HTTPS by default
- Load balancing
- Auto-rollback on failure
- CloudWatch logs

---

### Option 2: ECS on Fargate (More Control)

#### Step 1: Create ECR Repository & Push
```bash
aws ecr create-repository --repository-name travel-planner
docker build -t travel-planner:latest .
docker tag travel-planner:latest <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/travel-planner:latest
aws ecr get-login-password --region <REGION> | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/travel-planner:latest
```

#### Step 2: Create ECS Cluster
```bash
aws ecs create-cluster --cluster-name travel-planner
```

#### Step 3: Create Task Definition
```bash
cat > task-definition.json << 'EOF'
{
  "family": "travel-planner",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "travel-planner",
      "image": "<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/travel-planner:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "hostPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "GEMINI_API_KEY",
          "value": "your-key"
        },
        {
          "name": "TAVILY_API_KEY",
          "value": "your-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/travel-planner",
          "awslogs-region": "<REGION>",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
EOF

aws ecs register-task-definition --cli-input-json file://task-definition.json
```

#### Step 4: Create Service
```bash
aws ecs create-service \
  --cluster travel-planner \
  --service-name travel-planner \
  --task-definition travel-planner:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:REGION:ACCOUNT:targetgroup/travel-planner/xxx,containerName=travel-planner,containerPort=8000"
```

#### Step 5: Create Load Balancer
```bash
# Application Load Balancer
aws elbv2 create-load-balancer \
  --name travel-planner-alb \
  --subnets subnet-xxx subnet-yyy \
  --security-groups sg-xxx

# Target Group
aws elbv2 create-target-group \
  --name travel-planner \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --health-check-enabled \
  --health-check-path /health

# Listener
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:...
```

✅ **ECS Service running!** Features:
- Auto-scaling based on CPU/memory
- Rolling deployments
- Health checks
- CloudWatch integration
- RDS for PostgreSQL (optional)

---

### Option 3: Lambda + API Gateway (Serverless)

Not recommended for this use case (LangGraph + long-running tasks)

---

## Database Options

### Local Development
✓ SQLite (included)
```bash
# Located at: travel_planner.db
# Auto-created on first run
```

### Production

#### Option 1: RDS PostgreSQL
```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier travel-planner-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username admin \
  --master-user-password STRONG_PASSWORD \
  --allocated-storage 20

# Update connection string
# DATABASE_URL=postgresql://user:pass@endpoint:5432/travel_planner
```

Update `app/database.py`:
```python
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./travel_planner.db"
)
```

#### Option 2: DynamoDB (NoSQL)
```python
# See AWS Transform power for modernization to DynamoDB
```

---

## CI/CD Pipeline (GitHub Actions)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Travel Planner

on:
  push:
    branches: [ main ]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: travel-planner

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v1
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}
    
    - name: Login to Amazon ECR
      run: |
        aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.$AWS_REGION.amazonaws.com
    
    - name: Build Docker image
      run: |
        docker build -t $ECR_REPOSITORY:latest .
        docker tag $ECR_REPOSITORY:latest ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
    
    - name: Push to Amazon ECR
      run: |
        docker push ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
    
    - name: Update ECS service
      run: |
        aws ecs update-service \
          --cluster travel-planner \
          --service travel-planner \
          --force-new-deployment
```

---

## Monitoring & Logging

### CloudWatch Logs
```bash
# View logs
aws logs tail /ecs/travel-planner --follow

# Create alarms
aws cloudwatch put-metric-alarm \
  --alarm-name travel-planner-errors \
  --alarm-description "Alert on errors" \
  --metric-name Errors \
  --namespace AWS/ECS \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

### DataDog (Optional)
```bash
# Add DataDog agent to Docker
docker run -d \
  -e DD_AGENT_HOST=datadog \
  -e DD_TRACE_ENABLED=true \
  travel-planner
```

### Prometheus + Grafana
```python
# Add to app/main.py
from prometheus_client import Counter, Histogram, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)

# Metrics available at /metrics
```

---

## Domain & SSL

### Custom Domain
```bash
# Route 53
aws route53 create-resource-record-set \
  --hosted-zone-id Z123ABC \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.example.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z35SXDOTRQ7X7K",
          "DNSName": "xxx.cloudfront.net",
          "EvaluateTargetHealth": false
        }
      }
    }]
  }'
```

### SSL Certificate (ACM)
```bash
aws acm request-certificate \
  --domain-name api.example.com \
  --subject-alternative-names "*.example.com" \
  --validation-method DNS
```

---

## Scaling Considerations

| Metric | Limit | Action |
|--------|-------|--------|
| Requests/sec | 100 | Add load balancer |
| Response time > 40s | High | Cache results |
| Database connections | 20 | Connection pooling |
| Memory per container | 1GB | Increase instance size |
| Cost | $200/month | Review resources |

---

## Deployment Checklist

### Before Deployment
- [ ] All tests passing
- [ ] Environment variables set
- [ ] Database initialized
- [ ] API keys validated
- [ ] Security review done
- [ ] Rate limiting enabled
- [ ] Logging configured
- [ ] Health checks set up
- [ ] Monitoring alerts configured
- [ ] Backup strategy defined

### During Deployment
- [ ] Blue-green deployment strategy
- [ ] Rollback plan ready
- [ ] Team notified
- [ ] Monitoring dashboard open

### After Deployment
- [ ] Health check passing
- [ ] Test critical endpoints
- [ ] Monitor error rates
- [ ] Check response times
- [ ] Verify database connectivity
- [ ] Monitor costs

---

## Rollback Plan

```bash
# If deployment fails, rollback to previous version
aws ecs update-service \
  --cluster travel-planner \
  --service travel-planner \
  --task-definition travel-planner:2  # Previous version

# Verify
aws ecs describe-services \
  --cluster travel-planner \
  --services travel-planner
```

---

## Cost Estimation (AWS)

| Service | Size | Monthly Cost |
|---------|------|--------------|
| App Runner | 2 vCPU, 4GB RAM, 1M requests | $30-50 |
| RDS PostgreSQL | db.t3.micro, 20GB | $15-25 |
| Load Balancer | ALB | $20 |
| Data Transfer | 100GB/month | $15 |
| CloudWatch | Logs + metrics | $10 |
| **Total** | | **$90-120** |

---

## Support & Troubleshooting

### Common Issues

**Container won't start**
```bash
docker logs travel-planner
# Check: GEMINI_API_KEY, TAVILY_API_KEY set
```

**Connection timeout**
```bash
# Increase timeout in ECS task
timeout = 120  # seconds
```

**Out of memory**
```bash
# Increase container memory
--memory 2048  # MB
```

**Database locked**
```bash
# Check SQLite connections
# Consider migrating to PostgreSQL RDS
```

---

## Next Steps

1. **Choose deployment option** (App Runner recommended)
2. **Set up AWS account** with credentials
3. **Deploy with CI/CD** or manual steps above
4. **Configure domain** with Route 53
5. **Set up monitoring** with CloudWatch
6. **Configure backups** for database
7. **Scale as needed** based on traffic

**Estimated Time:**
- App Runner: 15 minutes
- ECS + ALB: 30 minutes
- Full CI/CD setup: 1 hour

🚀 **Your Travel Planner is production-ready!**
