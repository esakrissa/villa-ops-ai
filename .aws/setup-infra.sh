#!/usr/bin/env bash
# VillaOps AI — One-time AWS infrastructure setup
# Run from local Mac with AWS credentials configured (profile: gitlab-user)
# Region: us-east-1, Account: 930936105501
set -euo pipefail

AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="930936105501"
PROJECT="villa-ops"

echo "=== VillaOps AI — AWS Infrastructure Setup ==="
echo "Region: $AWS_REGION | Account: $AWS_ACCOUNT_ID"
echo ""

# ---------------------------------------------------------------------------
# 1. VPC + Networking (use default VPC)
# ---------------------------------------------------------------------------
echo ">>> Step 1: VPC + Networking"

VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" --output text \
    --region "$AWS_REGION")
echo "Default VPC: $VPC_ID"

# Get at least 2 subnets (required for ALB)
SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "Subnets[*].SubnetId" --output text \
    --region "$AWS_REGION")
SUBNET_1=$(echo "$SUBNET_IDS" | awk '{print $1}')
SUBNET_2=$(echo "$SUBNET_IDS" | awk '{print $2}')
echo "Subnets: $SUBNET_1, $SUBNET_2"

# ALB security group (allow 80 from internet)
ALB_SG_ID=$(aws ec2 create-security-group \
    --group-name "${PROJECT}-alb-sg" \
    --description "ALB security group for VillaOps" \
    --vpc-id "$VPC_ID" \
    --region "$AWS_REGION" \
    --query "GroupId" --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${PROJECT}-alb-sg" "Name=vpc-id,Values=$VPC_ID" \
        --query "SecurityGroups[0].GroupId" --output text \
        --region "$AWS_REGION")
echo "ALB SG: $ALB_SG_ID"

aws ec2 authorize-security-group-ingress \
    --group-id "$ALB_SG_ID" \
    --protocol tcp --port 80 --cidr 0.0.0.0/0 \
    --region "$AWS_REGION" 2>/dev/null || true

# ECS security group (allow from ALB SG on app ports)
ECS_SG_ID=$(aws ec2 create-security-group \
    --group-name "${PROJECT}-ecs-sg" \
    --description "ECS tasks security group for VillaOps" \
    --vpc-id "$VPC_ID" \
    --region "$AWS_REGION" \
    --query "GroupId" --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${PROJECT}-ecs-sg" "Name=vpc-id,Values=$VPC_ID" \
        --query "SecurityGroups[0].GroupId" --output text \
        --region "$AWS_REGION")
echo "ECS SG: $ECS_SG_ID"

# Allow ALB → ECS on 3000, 8000, 8001
for PORT in 3000 8000 8001; do
    aws ec2 authorize-security-group-ingress \
        --group-id "$ECS_SG_ID" \
        --protocol tcp --port "$PORT" \
        --source-group "$ALB_SG_ID" \
        --region "$AWS_REGION" 2>/dev/null || true
done

# Allow ECS tasks to talk to each other (for MCP → backend connectivity)
aws ec2 authorize-security-group-ingress \
    --group-id "$ECS_SG_ID" \
    --protocol tcp --port 0-65535 \
    --source-group "$ECS_SG_ID" \
    --region "$AWS_REGION" 2>/dev/null || true

# DB security group (allow from ECS SG on 5432)
DB_SG_ID=$(aws ec2 create-security-group \
    --group-name "${PROJECT}-db-sg" \
    --description "RDS security group for VillaOps" \
    --vpc-id "$VPC_ID" \
    --region "$AWS_REGION" \
    --query "GroupId" --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${PROJECT}-db-sg" "Name=vpc-id,Values=$VPC_ID" \
        --query "SecurityGroups[0].GroupId" --output text \
        --region "$AWS_REGION")
echo "DB SG: $DB_SG_ID"

aws ec2 authorize-security-group-ingress \
    --group-id "$DB_SG_ID" \
    --protocol tcp --port 5432 \
    --source-group "$ECS_SG_ID" \
    --region "$AWS_REGION" 2>/dev/null || true

# Allow local machine to reach RDS (for migrations) — your public IP
MY_IP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress \
    --group-id "$DB_SG_ID" \
    --protocol tcp --port 5432 \
    --cidr "${MY_IP}/32" \
    --region "$AWS_REGION" 2>/dev/null || true
echo "Allowed local IP $MY_IP for RDS migrations"

# Redis security group (allow from ECS SG on 6379)
REDIS_SG_ID=$(aws ec2 create-security-group \
    --group-name "${PROJECT}-redis-sg" \
    --description "ElastiCache security group for VillaOps" \
    --vpc-id "$VPC_ID" \
    --region "$AWS_REGION" \
    --query "GroupId" --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${PROJECT}-redis-sg" "Name=vpc-id,Values=$VPC_ID" \
        --query "SecurityGroups[0].GroupId" --output text \
        --region "$AWS_REGION")
echo "Redis SG: $REDIS_SG_ID"

aws ec2 authorize-security-group-ingress \
    --group-id "$REDIS_SG_ID" \
    --protocol tcp --port 6379 \
    --source-group "$ECS_SG_ID" \
    --region "$AWS_REGION" 2>/dev/null || true

echo ""

# ---------------------------------------------------------------------------
# 2. ECR Repositories
# ---------------------------------------------------------------------------
echo ">>> Step 2: ECR Repositories"

aws ecr create-repository \
    --repository-name "${PROJECT}-backend" \
    --region "$AWS_REGION" 2>/dev/null || echo "ECR repo ${PROJECT}-backend already exists"

aws ecr create-repository \
    --repository-name "${PROJECT}-frontend" \
    --region "$AWS_REGION" 2>/dev/null || echo "ECR repo ${PROJECT}-frontend already exists"

echo ""

# ---------------------------------------------------------------------------
# 3. CloudWatch Log Groups
# ---------------------------------------------------------------------------
echo ">>> Step 3: CloudWatch Log Groups"

for SVC in backend frontend mcp; do
    aws logs create-log-group \
        --log-group-name "/ecs/${PROJECT}-${SVC}" \
        --region "$AWS_REGION" 2>/dev/null || echo "Log group /ecs/${PROJECT}-${SVC} already exists"
done

echo ""

# ---------------------------------------------------------------------------
# 4. IAM — ECS Task Execution Role
# ---------------------------------------------------------------------------
echo ">>> Step 4: IAM — ECS Task Execution Role"

TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ecs-tasks.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}'

aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document "$TRUST_POLICY" \
    2>/dev/null || echo "Role ecsTaskExecutionRole already exists"

aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
    2>/dev/null || true

# Custom policy for SSM Parameter Store access
SSM_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameters",
        "ssm:GetParameter"
      ],
      "Resource": "arn:aws:ssm:us-east-1:930936105501:parameter/villaops/prod/*"
    }
  ]
}'

aws iam put-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-name VillaOpsSSMAccess \
    --policy-document "$SSM_POLICY" \
    2>/dev/null || true

echo ""

# ---------------------------------------------------------------------------
# 5. RDS PostgreSQL
# ---------------------------------------------------------------------------
echo ">>> Step 5: RDS PostgreSQL (db.t3.micro)"

# Create a DB subnet group using default VPC subnets
aws rds create-db-subnet-group \
    --db-subnet-group-name "${PROJECT}-db-subnet" \
    --db-subnet-group-description "VillaOps RDS subnet group" \
    --subnet-ids $SUBNET_IDS \
    --region "$AWS_REGION" 2>/dev/null || echo "DB subnet group already exists"

DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
echo "Generated DB password (save this!): $DB_PASSWORD"

aws rds create-db-instance \
    --db-instance-identifier "${PROJECT}-db" \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 16 \
    --master-username villa \
    --master-user-password "$DB_PASSWORD" \
    --allocated-storage 20 \
    --vpc-security-group-ids "$DB_SG_ID" \
    --db-subnet-group-name "${PROJECT}-db-subnet" \
    --db-name villa_ops \
    --publicly-accessible \
    --backup-retention-period 7 \
    --storage-type gp3 \
    --no-multi-az \
    --region "$AWS_REGION" 2>/dev/null || echo "RDS instance already exists"

echo "Waiting for RDS to become available (this takes 5-10 minutes)..."
aws rds wait db-instance-available \
    --db-instance-identifier "${PROJECT}-db" \
    --region "$AWS_REGION"

RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier "${PROJECT}-db" \
    --query "DBInstances[0].Endpoint.Address" --output text \
    --region "$AWS_REGION")
echo "RDS Endpoint: $RDS_ENDPOINT"

# Store DATABASE_URL in SSM
aws ssm put-parameter \
    --name "/villaops/prod/DATABASE_URL" \
    --type SecureString \
    --value "postgresql+asyncpg://villa:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/villa_ops" \
    --overwrite \
    --region "$AWS_REGION"
echo "Stored DATABASE_URL in SSM"

echo ""

# ---------------------------------------------------------------------------
# 6. ElastiCache Redis
# ---------------------------------------------------------------------------
echo ">>> Step 6: ElastiCache Redis (cache.t3.micro)"

# Create cache subnet group
aws elasticache create-cache-subnet-group \
    --cache-subnet-group-name "${PROJECT}-redis-subnet" \
    --cache-subnet-group-description "VillaOps Redis subnet group" \
    --subnet-ids $SUBNET_IDS \
    --region "$AWS_REGION" 2>/dev/null || echo "Redis subnet group already exists"

aws elasticache create-cache-cluster \
    --cache-cluster-id "${PROJECT}-redis" \
    --cache-node-type cache.t3.micro \
    --engine redis \
    --engine-version 7.1 \
    --num-cache-nodes 1 \
    --cache-subnet-group-name "${PROJECT}-redis-subnet" \
    --security-group-ids "$REDIS_SG_ID" \
    --region "$AWS_REGION" 2>/dev/null || echo "ElastiCache cluster already exists"

echo "Waiting for ElastiCache to become available..."
aws elasticache wait cache-cluster-available \
    --cache-cluster-id "${PROJECT}-redis" \
    --region "$AWS_REGION"

REDIS_ENDPOINT=$(aws elasticache describe-cache-clusters \
    --cache-cluster-id "${PROJECT}-redis" \
    --show-cache-node-info \
    --query "CacheClusters[0].CacheNodes[0].Endpoint.Address" --output text \
    --region "$AWS_REGION")
echo "Redis Endpoint: $REDIS_ENDPOINT"

aws ssm put-parameter \
    --name "/villaops/prod/REDIS_URL" \
    --type SecureString \
    --value "redis://${REDIS_ENDPOINT}:6379/0" \
    --overwrite \
    --region "$AWS_REGION"
echo "Stored REDIS_URL in SSM"

echo ""

# ---------------------------------------------------------------------------
# 7. SSM Parameters (secrets — placeholder values, update manually)
# ---------------------------------------------------------------------------
echo ">>> Step 7: SSM Parameters (placeholders — update with real values)"

JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
aws ssm put-parameter --name "/villaops/prod/JWT_SECRET_KEY" --type SecureString --value "$JWT_SECRET" --overwrite --region "$AWS_REGION"
echo "Generated and stored JWT_SECRET_KEY"

# Stripe — use placeholder values, update manually with real keys
for PARAM in STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET STRIPE_PUBLISHABLE_KEY STRIPE_PRO_PRICE_ID STRIPE_BUSINESS_PRICE_ID; do
    aws ssm put-parameter \
        --name "/villaops/prod/${PARAM}" \
        --type SecureString \
        --value "PLACEHOLDER_UPDATE_ME" \
        --overwrite \
        --region "$AWS_REGION" 2>/dev/null || true
    echo "Created placeholder for ${PARAM}"
done

# API keys — use placeholder values
for PARAM in GEMINI_API_KEY GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GITHUB_CLIENT_ID GITHUB_CLIENT_SECRET; do
    aws ssm put-parameter \
        --name "/villaops/prod/${PARAM}" \
        --type SecureString \
        --value "PLACEHOLDER_UPDATE_ME" \
        --overwrite \
        --region "$AWS_REGION" 2>/dev/null || true
    echo "Created placeholder for ${PARAM}"
done

echo ""

# ---------------------------------------------------------------------------
# 8. ALB + Target Groups
# ---------------------------------------------------------------------------
echo ">>> Step 8: ALB + Target Groups"

ALB_ARN=$(aws elbv2 create-load-balancer \
    --name "${PROJECT}-alb" \
    --subnets "$SUBNET_1" "$SUBNET_2" \
    --security-groups "$ALB_SG_ID" \
    --scheme internet-facing \
    --type application \
    --region "$AWS_REGION" \
    --query "LoadBalancers[0].LoadBalancerArn" --output text 2>/dev/null || \
    aws elbv2 describe-load-balancers \
        --names "${PROJECT}-alb" \
        --query "LoadBalancers[0].LoadBalancerArn" --output text \
        --region "$AWS_REGION")
echo "ALB ARN: $ALB_ARN"

ALB_DNS=$(aws elbv2 describe-load-balancers \
    --names "${PROJECT}-alb" \
    --query "LoadBalancers[0].DNSName" --output text \
    --region "$AWS_REGION")
echo "ALB DNS: $ALB_DNS"

# Backend target group
BACKEND_TG_ARN=$(aws elbv2 create-target-group \
    --name "${PROJECT}-backend-tg" \
    --protocol HTTP --port 8000 \
    --vpc-id "$VPC_ID" \
    --target-type ip \
    --health-check-path /health \
    --health-check-interval-seconds 30 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3 \
    --region "$AWS_REGION" \
    --query "TargetGroups[0].TargetGroupArn" --output text 2>/dev/null || \
    aws elbv2 describe-target-groups \
        --names "${PROJECT}-backend-tg" \
        --query "TargetGroups[0].TargetGroupArn" --output text \
        --region "$AWS_REGION")
echo "Backend TG: $BACKEND_TG_ARN"

# Frontend target group
FRONTEND_TG_ARN=$(aws elbv2 create-target-group \
    --name "${PROJECT}-frontend-tg" \
    --protocol HTTP --port 3000 \
    --vpc-id "$VPC_ID" \
    --target-type ip \
    --health-check-path / \
    --health-check-interval-seconds 30 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3 \
    --region "$AWS_REGION" \
    --query "TargetGroups[0].TargetGroupArn" --output text 2>/dev/null || \
    aws elbv2 describe-target-groups \
        --names "${PROJECT}-frontend-tg" \
        --query "TargetGroups[0].TargetGroupArn" --output text \
        --region "$AWS_REGION")
echo "Frontend TG: $FRONTEND_TG_ARN"

# Create HTTP listener (default → frontend)
LISTENER_ARN=$(aws elbv2 create-listener \
    --load-balancer-arn "$ALB_ARN" \
    --protocol HTTP --port 80 \
    --default-actions Type=forward,TargetGroupArn="$FRONTEND_TG_ARN" \
    --region "$AWS_REGION" \
    --query "Listeners[0].ListenerArn" --output text 2>/dev/null || \
    aws elbv2 describe-listeners \
        --load-balancer-arn "$ALB_ARN" \
        --query "Listeners[0].ListenerArn" --output text \
        --region "$AWS_REGION")
echo "Listener ARN: $LISTENER_ARN"

# Rule: /api/* → backend
aws elbv2 create-rule \
    --listener-arn "$LISTENER_ARN" \
    --priority 10 \
    --conditions Field=path-pattern,Values='/api/*' \
    --actions Type=forward,TargetGroupArn="$BACKEND_TG_ARN" \
    --region "$AWS_REGION" 2>/dev/null || echo "Rule /api/* already exists"

# Rule: /health → backend
aws elbv2 create-rule \
    --listener-arn "$LISTENER_ARN" \
    --priority 20 \
    --conditions Field=path-pattern,Values='/health' \
    --actions Type=forward,TargetGroupArn="$BACKEND_TG_ARN" \
    --region "$AWS_REGION" 2>/dev/null || echo "Rule /health already exists"

# Rule: /docs, /redoc, /openapi.json → backend
aws elbv2 create-rule \
    --listener-arn "$LISTENER_ARN" \
    --priority 30 \
    --conditions Field=path-pattern,Values='/docs,/redoc,/openapi.json' \
    --actions Type=forward,TargetGroupArn="$BACKEND_TG_ARN" \
    --region "$AWS_REGION" 2>/dev/null || echo "Rule /docs already exists"

echo ""

# ---------------------------------------------------------------------------
# 9. ECS Cluster + Service Discovery
# ---------------------------------------------------------------------------
echo ">>> Step 9: ECS Cluster + Service Discovery"

aws ecs create-cluster \
    --cluster-name "${PROJECT}-cluster" \
    --region "$AWS_REGION" 2>/dev/null || echo "ECS cluster already exists"

# Create Cloud Map namespace for service discovery (MCP ↔ backend)
NAMESPACE_ID=$(aws servicediscovery create-private-dns-namespace \
    --name villaops.local \
    --vpc "$VPC_ID" \
    --region "$AWS_REGION" \
    --query "OperationId" --output text 2>/dev/null || echo "exists")

if [ "$NAMESPACE_ID" != "exists" ]; then
    echo "Waiting for Cloud Map namespace..."
    sleep 10
    NAMESPACE_ID=$(aws servicediscovery list-namespaces \
        --filters Name=NAME,Values=villaops.local \
        --query "Namespaces[0].Id" --output text \
        --region "$AWS_REGION")
else
    NAMESPACE_ID=$(aws servicediscovery list-namespaces \
        --filters Name=NAME,Values=villaops.local \
        --query "Namespaces[0].Id" --output text \
        --region "$AWS_REGION")
fi
echo "Cloud Map Namespace: $NAMESPACE_ID"

# Create service discovery services
for SVC in backend mcp frontend; do
    aws servicediscovery create-service \
        --name "$SVC" \
        --namespace-id "$NAMESPACE_ID" \
        --dns-config "NamespaceId=$NAMESPACE_ID,DnsRecords=[{Type=A,TTL=10}]" \
        --health-check-custom-config FailureThreshold=1 \
        --region "$AWS_REGION" 2>/dev/null || echo "Service discovery for $SVC already exists"
done

# Get service discovery ARNs
MCP_SD_ARN=$(aws servicediscovery list-services \
    --filters Name=NAMESPACE_ID,Values="$NAMESPACE_ID" \
    --query "Services[?Name=='mcp'].Arn | [0]" --output text \
    --region "$AWS_REGION")
echo "MCP Service Discovery ARN: $MCP_SD_ARN"

echo ""

# ---------------------------------------------------------------------------
# 10. Register ECS Task Definitions
# ---------------------------------------------------------------------------
echo ">>> Step 10: Register ECS Task Definitions"

# Update task definitions with real values before registering
# (The task-def files use placeholder images — deploy workflow handles actual images)

aws ecs register-task-definition \
    --cli-input-json file://.aws/backend-task-def.json \
    --region "$AWS_REGION" 2>/dev/null || echo "Failed to register backend task def"

aws ecs register-task-definition \
    --cli-input-json file://.aws/frontend-task-def.json \
    --region "$AWS_REGION" 2>/dev/null || echo "Failed to register frontend task def"

aws ecs register-task-definition \
    --cli-input-json file://.aws/mcp-task-def.json \
    --region "$AWS_REGION" 2>/dev/null || echo "Failed to register MCP task def"

echo ""

# ---------------------------------------------------------------------------
# 11. Create ECS Services
# ---------------------------------------------------------------------------
echo ">>> Step 11: Create ECS Services"

# MCP service (with service discovery)
MCP_SD_SERVICE_ARN=$(aws servicediscovery list-services \
    --filters Name=NAMESPACE_ID,Values="$NAMESPACE_ID" \
    --query "Services[?Name=='mcp'].Id | [0]" --output text \
    --region "$AWS_REGION")

aws ecs create-service \
    --cluster "${PROJECT}-cluster" \
    --service-name "${PROJECT}-mcp" \
    --task-definition villa-ops-mcp \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
    --service-registries "registryArn=arn:aws:servicediscovery:${AWS_REGION}:${AWS_ACCOUNT_ID}:service/${MCP_SD_SERVICE_ARN}" \
    --region "$AWS_REGION" 2>/dev/null || echo "MCP service already exists"

# Backend service (with ALB)
aws ecs create-service \
    --cluster "${PROJECT}-cluster" \
    --service-name "${PROJECT}-backend" \
    --task-definition villa-ops-backend \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=$BACKEND_TG_ARN,containerName=villa-ops-backend,containerPort=8000" \
    --region "$AWS_REGION" 2>/dev/null || echo "Backend service already exists"

# Frontend service (with ALB)
aws ecs create-service \
    --cluster "${PROJECT}-cluster" \
    --service-name "${PROJECT}-frontend" \
    --task-definition villa-ops-frontend \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=$FRONTEND_TG_ARN,containerName=villa-ops-frontend,containerPort=3000" \
    --region "$AWS_REGION" 2>/dev/null || echo "Frontend service already exists"

echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "==========================================="
echo "  VillaOps AI — Infrastructure Ready!"
echo "==========================================="
echo ""
echo "ALB DNS:        http://$ALB_DNS"
echo "RDS Endpoint:   $RDS_ENDPOINT"
echo "Redis Endpoint: $REDIS_ENDPOINT"
echo "DB Password:    $DB_PASSWORD"
echo ""
echo "Next steps:"
echo "  1. Update SSM parameters with real Stripe/OAuth/API keys"
echo "  2. Run Alembic migrations:"
echo "     DATABASE_URL=postgresql+asyncpg://villa:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/villa_ops alembic upgrade head"
echo "  3. Update task definitions with ALB DNS for FRONTEND_URL and CORS_ORIGINS"
echo "  4. Set GitHub Secrets: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
echo "  5. Push code to trigger CI/CD pipeline"
echo "  6. Update Stripe webhook URL to: http://$ALB_DNS/api/v1/webhooks/stripe"
echo ""
