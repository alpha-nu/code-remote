# Deployment Guide

## Overview

Code Remote uses GitHub Actions for CI/CD with automated deployments to AWS serverless infrastructure. The pipeline handles infrastructure provisioning, container builds, and application deployment.

**Related:** [Release Strategy](release-strategy.md) for versioning and release workflows.

## Architecture

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| API | Lambda + API Gateway (HTTP) | REST endpoints |
| Frontend | S3 + CloudFront | Static hosting + CDN |
| Auth | Cognito | User authentication |
| Container Registry | ECR | Lambda container images |
| Infrastructure | Pulumi | Infrastructure as Code |

## Deployment Triggers

### Automatic Deployments

| Trigger | Environment | Example |
|---------|-------------|---------|
| Push to `main` | **dev** | `git push origin main` |
| Version tag (`v*`) | **prod** | `git tag v1.0.0 && git push origin v1.0.0` |

```bash
# Deploy to dev (automatic on merge)
git checkout main
git merge feature/my-feature
git push origin main
# → Deploys to dev

# Deploy to prod (create version tag)
git tag v1.0.0
git push origin v1.0.0
# → Deploys to prod
```

### Manual Deployments

Via GitHub Actions UI:
1. Go to **Actions** → **Deploy**
2. Click **Run workflow**
3. Select environment (dev or prod)
4. Click **Run workflow**

## Pipeline Stages

The deploy workflow (`.github/workflows/deploy.yml`) runs these stages:

```
┌─────────┐    ┌──────┐    ┌───────────────┐    ┌───────────┐
│  Setup  │───▶│ Test │───▶│Infrastructure │───▶│ Build API │
└─────────┘    └──────┘    └───────────────┘    └───────────┘
                                                      │
┌─────────┐    ┌─────────────┐    ┌────────────────┐  │
│ Summary │◀───│ Smoke Tests │◀───│Deploy Frontend │◀─┤
└─────────┘    └─────────────┘    └────────────────┘  │
                                                      │
                               ┌────────────────┐     │
                               │ Deploy Backend │◀────┘
                               └────────────────┘
```

| Stage | Description |
|-------|-------------|
| **Setup** | Determine environment from trigger (main→dev, tag→prod) |
| **Test** | Run backend pytest + frontend lint/type-check/tests |
| **Infrastructure** | Pulumi preview and deploy AWS resources |
| **Build API** | Docker build, push to ECR with commit SHA tag |
| **Deploy Backend** | Update Lambda function code |
| **Deploy Frontend** | Build React app, sync to S3, invalidate CloudFront |
| **Smoke Tests** | Verify health endpoint, auth requirements |
| **Summary** | Generate deployment report |

## Required GitHub Secrets

Configure in **Settings** → **Secrets and variables** → **Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM access key with deployment permissions |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key |
| `PULUMI_ACCESS_TOKEN` | Pulumi Cloud access token |

### Required IAM Permissions

The deployment IAM user needs:
- Lambda: `lambda:*`
- ECR: `ecr:*`
- S3: `s3:*` (for frontend bucket)
- CloudFront: `cloudfront:*`
- API Gateway: `apigateway:*`
- Cognito: `cognito-idp:*`
- IAM: `iam:*` (for Lambda execution role)
- Logs: `logs:*`
- Secrets Manager: `secretsmanager:*`

## GitHub Environments

Create in **Settings** → **Environments**:

| Environment | Protection Rules |
|-------------|------------------|
| **dev** | None (auto-deploy) |
| **prod** | Required reviewers |

## Pulumi Configuration

Stack configs in `infra/pulumi/`:

| File | Stack | Environment |
|------|-------|-------------|
| `Pulumi.dev.yaml` | dev | Development |
| `Pulumi.staging.yaml` | staging | Staging (future) |
| `Pulumi.prod.yaml` | prod | Production |

### Stack Outputs

After deployment, these outputs are available:

| Output | Description |
|--------|-------------|
| `api_endpoint` | API Gateway URL |
| `api_function_name` | Lambda function name |
| `ecr_api_repository_url` | ECR repository URL |
| `frontend_url` | CloudFront distribution URL |
| `frontend_bucket_name` | S3 bucket name |
| `frontend_distribution_id` | CloudFront distribution ID |
| `cognito_user_pool_id` | Cognito user pool ID |
| `cognito_user_pool_client_id` | Cognito app client ID |

## Manual Operations

### View Deployment Status

```bash
# Check Lambda function
aws lambda get-function --function-name $(pulumi stack output api_function_name --stack dev)

# Tail Lambda logs
aws logs tail /aws/lambda/$(pulumi stack output api_function_name --stack dev) --follow

# Test API health
curl $(pulumi stack output api_endpoint --stack dev)/health
```

### Pulumi Operations

```bash
cd infra/pulumi

# Preview changes
pulumi preview --stack dev

# Deploy infrastructure
pulumi up --stack dev --yes

# View all outputs
pulumi stack output --stack dev

# Refresh state (sync with AWS)
pulumi refresh --stack dev

# View deployment history
pulumi stack history --stack dev

# Export stack state (backup)
pulumi stack export --stack dev > backup.json

# Destroy environment (CAUTION!)
pulumi destroy --stack dev --yes
```

### Frontend Operations

```bash
# Get bucket and distribution from Pulumi
BUCKET=$(pulumi stack output frontend_bucket_name --stack dev)
DIST_ID=$(pulumi stack output frontend_distribution_id --stack dev)

# Manual S3 sync (emergency)
cd frontend && npm run build
aws s3 sync dist/ s3://$BUCKET/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id $DIST_ID \
  --paths "/*"
```

### Lambda Operations

```bash
# Get function name
FUNC=$(pulumi stack output api_function_name --stack dev)

# View function configuration
aws lambda get-function-configuration --function-name $FUNC

# View recent invocations
aws lambda get-function --function-name $FUNC \
  --query 'Configuration.{LastModified:LastModified,State:State}'

# Update function timeout
aws lambda update-function-configuration \
  --function-name $FUNC \
  --timeout 30
```

## Rollback

### Redeploy Previous Version

```bash
# Option 1: Create new tag from previous commit
git checkout <previous-commit>
git tag v1.2.4
git push origin v1.2.4

# Option 2: Revert bad commit
git revert <bad-commit>
git push origin main  # Deploys reverted code to dev
```

### Emergency Lambda Rollback

```bash
# List available images in ECR
aws ecr describe-images \
  --repository-name $(pulumi stack output ecr_api_repository_url --stack dev | cut -d'/' -f2) \
  --query 'imageDetails[*].imageTags'

# Update Lambda to previous image
aws lambda update-function-code \
  --function-name $FUNC \
  --image-uri <ecr-url>:<previous-sha>
```

## Troubleshooting

### Lambda Issues

| Problem | Solution |
|---------|----------|
| Cold start slow | Increase memory (also increases CPU) |
| Timeout errors | Check CloudWatch logs, increase timeout |
| Permission denied | Verify Lambda execution role |
| Image not found | Check ECR image exists |

```bash
# Check CloudWatch logs for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/$FUNC \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s000)
```

### Frontend Issues

| Problem | Solution |
|---------|----------|
| Old content showing | Invalidate CloudFront, clear browser cache |
| 403 Forbidden | Check S3 bucket policy, CloudFront OAI |
| CORS errors | Verify API Gateway CORS settings |

### Pulumi Issues

| Problem | Solution |
|---------|----------|
| State conflict | `pulumi refresh` to sync state |
| Resource in use | Wait and retry, or use `--target` flag |
| Stack locked | Check Pulumi Cloud, cancel stuck operation |

```bash
# Refresh state
pulumi refresh --stack dev

# Cancel stuck operation (use Pulumi Cloud UI or)
pulumi cancel --stack dev
```

## Deployed URLs

Find URLs in:
1. **GitHub Actions** → Deploy → Summary tab
2. **Pulumi outputs**: `pulumi stack output --stack dev`

Example outputs:
```
api_endpoint          : https://abc123.execute-api.us-east-1.amazonaws.com
frontend_url          : https://d1234567890.cloudfront.net
cognito_user_pool_id  : us-east-1_ABC123XYZ
cognito_client_id     : 1abc2def3ghi4jkl5mno6pqr
```

## See Also

- [Release Strategy](release-strategy.md) - Versioning and release workflows
- [Infrastructure](architecture/infrastructure.md) - Pulumi component details
- [Architecture Plan](architecture-plan.md) - System overview
