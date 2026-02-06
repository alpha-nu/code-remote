# AWS Infrastructure Audit Runbook

Quick reference for auditing AWS resources against Pulumi IaC state.

## Prerequisites

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Verify Pulumi stack
cd infra/pulumi && pulumi stack ls
```

## Step 1: Get Expected State (Pulumi)

```bash
# Get all stack outputs
pulumi stack output --json

# Export full resource state
pulumi stack export | jq '.deployment.resources[] | {type, urn, id}' | head -50

# Check specific resource types
pulumi stack export | jq '.deployment.resources[] | select(.type == "aws:apigatewayv2/api:Api") | {urn, id, name: .outputs.name}'
pulumi stack export | jq '.deployment.resources[] | select(.type == "aws:ec2/vpc:Vpc") | {urn, id, name: .outputs.tags.Name}'
```

## Step 2: Get Actual State (AWS)

### Compute

```bash
# Lambda functions
aws lambda list-functions --region us-east-1 \
  --query "Functions[*].[FunctionName,Runtime,LastModified]" --output table

# EC2 instances (should be 0 for serverless)
aws ec2 describe-instances --region us-east-1 \
  --query "Reservations[*].Instances[*].[InstanceId,State.Name,Tags[?Key=='Name'].Value|[0]]" --output table

# ECS clusters (should be 0)
aws ecs list-clusters --region us-east-1 --output json
```

### Networking

```bash
# API Gateways
aws apigatewayv2 get-apis --region us-east-1 \
  --query "Items[*].[Name,ApiId,ProtocolType,ApiEndpoint]" --output table

# VPCs (check for orphans - compare against Pulumi state)
aws ec2 describe-vpcs --region us-east-1 \
  --query "Vpcs[*].[VpcId,CidrBlock,Tags[?Key=='Name'].Value|[0],IsDefault]" --output table

# NAT Gateways (costly - verify each is needed)
aws ec2 describe-nat-gateways --region us-east-1 \
  --query "NatGateways[*].[NatGatewayId,State,VpcId,Tags[?Key=='Name'].Value|[0]]" --output table

# Load Balancers
aws elbv2 describe-load-balancers --region us-east-1 \
  --query "LoadBalancers[*].[LoadBalancerName,Type,State.Code]" --output table
```

### Databases

```bash
# RDS instances
aws rds describe-db-instances --region us-east-1 \
  --query "DBInstances[*].[DBInstanceIdentifier,Engine,DBInstanceStatus,Endpoint.Address]" --output table

# RDS clusters (Aurora)
aws rds describe-db-clusters --region us-east-1 \
  --query "DBClusters[*].[DBClusterIdentifier,Engine,Status,Endpoint]" --output table

# DynamoDB tables (should be 0 per architecture)
aws dynamodb list-tables --region us-east-1

# ElastiCache
aws elasticache describe-cache-clusters --region us-east-1 --output json | jq '.CacheClusters | length'
```

### Messaging

```bash
# SQS queues
aws sqs list-queues --region us-east-1 --query "QueueUrls" --output table
```

### Storage

```bash
# S3 buckets (filter by project name)
aws s3 ls | grep -E "code-remote|frontend"

# CloudFront distributions
aws cloudfront list-distributions \
  --query "DistributionList.Items[*].[Id,DomainName,Status,Comment]" --output table

# ECR repositories
aws ecr describe-repositories --region us-east-1 \
  --query "repositories[*].[repositoryName,repositoryUri]" --output table
```

### Security

```bash
# Cognito User Pools
aws cognito-idp list-user-pools --max-results 20 --region us-east-1 \
  --query "UserPools[*].[Id,Name]" --output table

# Secrets Manager
aws secretsmanager list-secrets --region us-east-1 \
  --query "SecretList[*].[Name,ARN]" --output table

# IAM roles (filter by project)
aws iam list-roles --output json | jq -r '.Roles[] | select(.RoleName | contains("code-remote") or contains("dev-")) | .RoleName'
```

## Step 3: Cross-Region Check

```bash
# Quick scan for resources in other regions
for region in us-west-2 eu-west-1 ap-southeast-1; do
  echo "=== $region ==="
  aws lambda list-functions --region $region --query "Functions[*].FunctionName" --output text
done
```

## Step 4: Compare & Identify Orphans

For each resource type, compare:
- AWS resource IDs against Pulumi state IDs
- Resources with `ManagedBy: pulumi` tags not in current state = orphaned

### Quick Orphan Detection

```bash
# Get API Gateway details for suspected orphan
aws apigatewayv2 get-api --api-id <API_ID> --region us-east-1 \
  --output json | jq '{Name, ApiId, CreatedDate, Tags}'

# Check VPC for dependencies before deletion
aws ec2 describe-subnets --filters "Name=vpc-id,Values=<VPC_ID>" --region us-east-1
aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=<VPC_ID>" --region us-east-1
aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=<VPC_ID>" --region us-east-1
```

## Output

Document findings in `docs/audits/YYYY-MM-DD-<env>-audit.md` with:
- Resources that match (expected vs actual)
- Orphaned resources found
- Remediation actions taken
- Cost implications
