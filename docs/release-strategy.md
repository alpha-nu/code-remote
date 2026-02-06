# Release Strategy

## Overview

Code Remote uses a trunk-based development model with environment-specific deployments controlled by Git triggers. This document outlines how releases flow from development to production.

## Environments

| Environment | Purpose | Trigger | Approval |
|-------------|---------|---------|----------|
| **dev** | Integration testing, feature validation | Push to `main` | None |
| **staging** | Pre-production validation | Manual / Future | Optional |
| **prod** | Production users | Version tag (`v*`) | Required |

## Release Flow

```
feature/xyz  ──PR──▶  main  ──auto──▶  dev
                        │
                        │ (validate in dev)
                        │
                        └──tag v1.2.3──▶  prod
```

### Development Workflow

1. **Feature Development**
   ```bash
   git checkout -b feature/my-feature
   # ... develop and commit ...
   git push origin feature/my-feature
   # Create PR to main
   ```

2. **PR Checks** (CI workflow)
   - Backend linting (ruff)
   - Frontend linting (eslint)
   - Backend unit tests
   - Frontend type checking
   - All checks must pass before merge

3. **Merge to Main → Dev Deployment**
   ```bash
   # Merge PR (via GitHub UI or CLI)
   git checkout main
   git pull origin main
   ```
   - Automatically triggers deploy to **dev**
   - Full deployment pipeline runs (infra → build → deploy → smoke tests)

### Production Release

1. **Validate in Dev**
   - Test features manually in dev environment
   - Run integration/smoke tests
   - Verify no regressions

2. **Create Version Tag**
   ```bash
   # Semantic versioning: MAJOR.MINOR.PATCH
   git tag v1.2.3
   git push origin v1.2.3
   ```

3. **Production Deployment**
   - Tag push triggers deploy to **prod**
   - Requires GitHub environment approval (if configured)
   - Same pipeline stages as dev

## Versioning Strategy

We follow [Semantic Versioning](https://semver.org/):

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| Breaking API changes | MAJOR | v1.0.0 → v2.0.0 |
| New features (backward compatible) | MINOR | v1.0.0 → v1.1.0 |
| Bug fixes | PATCH | v1.0.0 → v1.0.1 |

### Version Tag Format

```
v<MAJOR>.<MINOR>.<PATCH>[-<prerelease>]

Examples:
  v1.0.0        # Stable release
  v1.1.0        # Feature release
  v1.1.1        # Patch release
  v2.0.0-beta.1 # Pre-release (does NOT trigger prod deploy)
```

**Note:** Only tags matching `v*` (e.g., `v1.0.0`) trigger production deployments. Pre-release tags can be used for documentation purposes.

## Pulumi Stack Management

Each environment has its own Pulumi stack with isolated state:

```
infra/pulumi/
├── Pulumi.yaml           # Project definition
├── Pulumi.dev.yaml       # Dev configuration
├── Pulumi.staging.yaml   # Staging configuration (future)
└── Pulumi.prod.yaml      # Production configuration
```

### Stack Naming Convention

```
{stack-name} = {environment}

Examples:
  dev       # Development stack
  staging   # Staging stack
  prod      # Production stack
```

### Environment-Specific Configuration

| Config Key | Dev | Prod |
|------------|-----|------|
| `aws:region` | us-east-1 | us-east-1 |
| `gemini_model` | gemini-2.5-flash | gemini-2.5-flash |
| `vpc_cidr` | (default) | 10.2.0.0/16 |
| `az_count` | (default) | 3 |

## Rollback Procedures

### Quick Rollback (Redeploy Previous Version)

```bash
# Option 1: Create new patch version pointing to previous commit
git checkout <previous-good-commit>
git tag v1.2.4  # New version for rollback
git push origin v1.2.4

# Option 2: Revert and deploy
git revert <bad-commit>
git push origin main  # Deploys to dev
git tag v1.2.4
git push origin v1.2.4  # Deploys to prod
```

### Infrastructure Rollback

```bash
cd infra/pulumi

# Preview rollback
pulumi preview --stack prod --target-dependents

# If infrastructure change caused issues, check Pulumi history
pulumi stack history --stack prod

# Refresh state and re-apply previous configuration
pulumi refresh --stack prod
pulumi up --stack prod
```

### Lambda Rollback (Emergency)

```bash
# Get previous image tag from ECR
aws ecr describe-images \
  --repository-name code-remote-prod-api \
  --query 'imageDetails[*].imageTags' \
  --output table

# Update Lambda to previous image
aws lambda update-function-code \
  --function-name <function-name> \
  --image-uri <ecr-url>:<previous-tag>
```

## Hotfix Process

For critical production issues:

```bash
# 1. Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-fix

# 2. Apply fix
# ... make changes ...
git commit -m "fix: critical security patch"

# 3. Push and create PR
git push origin hotfix/critical-fix
# Create PR to main (expedited review)

# 4. After merge, immediately tag for prod
git checkout main
git pull origin main
git tag v1.2.4
git push origin v1.2.4
```

## Release Checklist

### Before Tagging for Production

- [ ] All CI checks pass on `main`
- [ ] Feature tested in dev environment
- [ ] No critical errors in dev CloudWatch logs
- [ ] Smoke tests pass in dev
- [ ] Database migrations applied (if any)
- [ ] Breaking changes documented
- [ ] CHANGELOG updated (if maintained)

### After Production Deployment

- [ ] Smoke tests pass
- [ ] Monitor CloudWatch for errors (15-30 min)
- [ ] Verify key user flows work
- [ ] Check Lambda cold start times
- [ ] Notify team of release

## Deployment Timeline

Typical deployment durations:

| Stage | Duration |
|-------|----------|
| Test | ~2 min |
| Infrastructure (Pulumi) | ~1-3 min |
| Build API Image | ~2-3 min |
| Deploy Backend | ~1-2 min |
| Deploy Frontend | ~1 min |
| Smoke Tests | ~1 min |
| CloudFront Propagation | ~5-15 min |
| **Total** | **~15-25 min** |

## Monitoring Releases

### GitHub Actions

- View deployment status: **Actions** → **Deploy**
- Check deployment summary for URLs and status
- Review logs for any failures

### AWS Console

- **Lambda**: Check function metrics, invocations, errors
- **CloudWatch**: View logs, set up alarms
- **CloudFront**: Check invalidation status, cache hit ratio

### Pulumi Cloud

- View stack history and diffs
- Track resource changes over time
- Review deployment audit logs
