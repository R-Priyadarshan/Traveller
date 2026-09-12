#!/bin/bash

# Travel Planner - Quick Deployment Script
# Usage: ./deploy.sh [heroku|docker|aws]

set -e

DEPLOYMENT_TYPE=${1:-docker}
REGION=${2:-us-east-1}
ACCOUNT_ID=${AWS_ACCOUNT_ID:-"YOUR_ACCOUNT_ID"}

echo "🚀 Deploying Travel Planner ($DEPLOYMENT_TYPE)..."

case $DEPLOYMENT_TYPE in
  docker)
    echo "📦 Docker Compose Deployment"
    docker-compose up --build -d
    echo "✅ Running at http://localhost:8000"
    ;;
  
  heroku)
    echo "🔴 Heroku Deployment"
    
    if ! command -v heroku &> /dev/null; then
      echo "Installing Heroku CLI..."
      curl https://cli-assets.heroku.com/install.sh | sh
    fi
    
    # Create app
    heroku create travel-planner || true
    
    # Set environment variables
    heroku config:set GEMINI_API_KEY=$GEMINI_API_KEY
    heroku config:set TAVILY_API_KEY=$TAVILY_API_KEY
    
    # Deploy
    git push heroku main
    
    echo "✅ Deployed to https://travel-planner.herokuapp.com"
    heroku logs --tail
    ;;
  
  aws-apprunner)
    echo "☁️  AWS App Runner Deployment"
    
    if [ "$ACCOUNT_ID" == "YOUR_ACCOUNT_ID" ]; then
      echo "❌ Error: Set AWS_ACCOUNT_ID environment variable"
      exit 1
    fi
    
    # Build & push to ECR
    echo "Building Docker image..."
    docker build -t travel-planner:latest .
    
    echo "Authenticating with ECR..."
    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
    
    echo "Creating ECR repository..."
    aws ecr create-repository --repository-name travel-planner --region $REGION || true
    
    echo "Pushing image..."
    docker tag travel-planner:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/travel-planner:latest
    docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/travel-planner:latest
    
    echo "Creating App Runner service..."
    aws apprunner create-service \
      --service-name travel-planner \
      --region $REGION \
      --source-configuration '{
        "ImageRepository": {
          "ImageRepositoryType": "ECR",
          "ImageIdentifier": "'$ACCOUNT_ID'.dkr.ecr.'$REGION'.amazonaws.com/travel-planner:latest",
          "RepositoryCredentials": {
            "CredentialsProvisioningStatus": "ACTIVE"
          }
        }
      }' \
      --instance-configuration 'Cpu=1,Memory=2048' || true
    
    echo "✅ App Runner service created!"
    echo "Check status with: aws apprunner describe-service --service-arn <arn>"
    ;;
  
  aws-ecs)
    echo "☁️  AWS ECS on Fargate Deployment"
    
    if [ "$ACCOUNT_ID" == "YOUR_ACCOUNT_ID" ]; then
      echo "❌ Error: Set AWS_ACCOUNT_ID environment variable"
      exit 1
    fi
    
    echo "See DEPLOYMENT.md for detailed ECS setup instructions"
    ;;
  
  *)
    echo "❌ Invalid deployment type: $DEPLOYMENT_TYPE"
    echo ""
    echo "Usage: ./deploy.sh [docker|heroku|aws-apprunner|aws-ecs]"
    echo ""
    echo "Examples:"
    echo "  ./deploy.sh docker              # Run locally with Docker Compose"
    echo "  ./deploy.sh heroku              # Deploy to Heroku"
    echo "  ./deploy.sh aws-apprunner       # Deploy to AWS App Runner"
    echo "  ./deploy.sh aws-apprunner us-west-2  # Specify AWS region"
    exit 1
    ;;
esac

echo ""
echo "📋 Next Steps:"
echo "  1. Test API: curl http://localhost:8000/health"
echo "  2. View frontend: http://localhost:8000"
echo "  3. Run tests: pytest tests/"
echo "  4. Check logs: docker logs travel-planner (or heroku logs --tail)"
