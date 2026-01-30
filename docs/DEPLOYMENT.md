# Deployment Guide

## Overview

This project uses GitHub Actions for CI/CD with automated deployments to AWS serverless infrastructure (Lambda + S3/CloudFront).

## Architecture

| Component | AWS Service |
|-----------|-------------|
| API | Lambda + API Gateway |
| Frontend | S3 + CloudFront |
| Auth | Cognito |
| Container Registry | ECR |
| Infrastructure | Pulumi |

## Deployment Triggers

### Automatic Deployments

| Trigger | Environment | Example |
|---------|-------------|---------|
| Push to `main` | **dev** | `git push origin main` |
| Push version tag | **prod** | `git tag v1.0.0 && git push origin v1.0.0` |

```bash
# Deploy to dev (automatic on merge to main)
git checkout main
git merge feature/my-feature
git push origin main
# → Triggers: Deploy to dev environment

# Deploy to prod (create a version tag)
git tag v1.0.0
git push origin v1.0.0
# → Triggers: Deploy to prod environment
```

### Manual Deployments

Use the GitHub Actions UI to trigger a manual deployment:
1. Go to Actions → Deploy
2. Click "Run workflow"
3. Select the target environment (dev or prod)

## Pipeline Stages

1. **Setup** - Determine target environment from trigger (main → dev, tag → prod)
2. **Test** - Run backend and frontend tests
3. **Infrastructure** - Deploy/update AWS resources with Pulumi
4. **Build API Image** - Build and push Lambda container image to ECR
5. **Build Executor Image** - Build and push Fargate executor image to ECR
6. **Deploy Backend** - Update Lambda function with new image
7. **Deploy Frontend** - Build React app, sync to S3, invalidate CloudFront
8. **Smoke Tests** - Verify health endpoints and auth requirements
9. **Summary** - Generate deployment report

## Required GitHub Secrets

Configure these secrets in your repository settings:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS IAM access key with deployment permissions |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |
| `PULUMI_ACCESS_TOKEN` | Pulumi Cloud access token |

## GitHub Environments

Create these environments in repository settings for deployment approvals:

- **dev** - No approval required
- **prod** - Required approval (add reviewers)

## Pulumi Stack Configuration

Stack configs are stored in `infra/pulumi/`:

| File | Environment |
|------|-------------|
| `Pulumi.code-remote-dev.yaml` | dev |
| `Pulumi.code-remote-staging.yaml` | staging (future) |
| `Pulumi.code-remote-prod.yaml` | prod |

## Manual Operations

### Check deployment status

```bash
# View Lambda function
aws lambda get-function --function-name code-remote-dev-api-func-xxxxx

# View Lambda logs
aws logs tail /aws/lambda/code-remote-dev-api-func-xxxxx --follow

# Check API Gateway
curl https://xxxx.execute-api.us-east-1.amazonaws.com/health
```

### Rollback Lambda deployment

```bash
# List Lambda versions
aws lambda list-versions-by-function --function-name <function-name>

# Update to previous version (if using aliases)
aws lambda update-alias \
  --function-name <function-name> \
  --name live \
  --function-version <previous-version>

# Or redeploy previous commit
git checkout <previous-commit>
git tag v1.0.1  # New tag for rollback
git push origin v1.0.1
```

### Pulumi operations

```bash
cd infra/pulumi

# Preview changes
pulumi preview --stack code-remote-dev

# Deploy infrastructure only
pulumi up --stack code-remote-dev --yes

# View outputs
pulumi stack output --stack code-remote-dev

# Refresh state
pulumi refresh --stack code-remote-dev

# Destroy environment (CAUTION)
pulumi destroy --stack code-remote-dev --yes
```

### Frontend operations

```bash
# Manual S3 sync (emergency)
aws s3 sync frontend/dist/ s3://<bucket-name>/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id <distribution-id> \
  --paths "/*"
```

## Troubleshooting

### Lambda cold starts

1. Check function memory/timeout settings in Pulumi
2. Consider provisioned concurrency for prod
3. Monitor with CloudWatch metrics

### Lambda deployment failures

1. Check ECR image exists: `aws ecr describe-images --repository-name <repo>`
2. Verify Lambda execution role permissions
3. Check CloudWatch logs for startup errors

### Frontend not updating

1. Verify S3 sync completed
2. Check CloudFront invalidation status
3. Clear browser cache / test in incognito

### Pulumi state issues

1. Check Pulumi Cloud for state conflicts
2. Run `pulumi refresh` to sync state
3. Use `pulumi stack export/import` for recovery

## Deployed URLs

After deployment, find URLs in:
- GitHub Actions summary
- Pulumi stack outputs: `pulumi stack output --stack code-remote-dev`

Example outputs:
```
api_endpoint: https://xxxx.execute-api.us-east-1.amazonaws.com
frontend_url: https://dxxxxxx.cloudfront.net
cognito_user_pool_id: us-east-1_XXXXXX
cognito_client_id: xxxxxxxxxxxxxxxxx
```
