# Release & Deployment Workflow

This document describes the Git branching strategy and deployment workflow for Code Remote.

---

## Branch Structure

```
main (master)
 │
 ├── feature/xyz          # Feature development
 ├── bugfix/xyz            # Bug fixes
 │
 └── release/dev           # Auto-deploys to dev environment
     └── release/staging   # Auto-deploys to staging environment
         └── release/prod  # Auto-deploys to production environment
```

---

## Branch Purposes

| Branch | Purpose | Deploys To | Protection |
|--------|---------|------------|------------|
| `main` | Stable, reviewed code | None (manual) | Required reviews, CI pass |
| `feature/*` | New features | None | None |
| `bugfix/*` | Bug fixes | None | None |
| `release/dev` | Development testing | Dev environment | CI pass |
| `release/staging` | Pre-production testing | Staging environment | CI pass, dev verified |
| `release/prod` | Production releases | Production | CI pass, staging verified, approval required |

---

## Development Workflow

### 1. Feature Development

```bash
# Start a new feature from main
git checkout main
git pull origin main
git checkout -b feature/add-execution-timeout

# ... develop and commit ...
git add .
git commit -m "feat: add configurable execution timeout"

# Push and create PR
git push origin feature/add-execution-timeout
```

### 2. Pull Request to Main

- Create PR: `feature/add-execution-timeout` → `main`
- Required checks:
  - ✅ Unit tests pass
  - ✅ Linting pass
  - ✅ Code review approved (1+ reviewer)
- Merge using **Squash and Merge**

### 3. Main Branch CI

When code is merged to `main`, CI runs:
- Unit tests
- Integration tests
- Security scanning
- Build verification

**Note:** Merging to `main` does NOT trigger deployment. This allows accumulating changes before release.

---

## Release Workflow

### Deploy to Dev

```bash
# Ensure main is up to date
git checkout main
git pull origin main

# Update release/dev branch
git checkout release/dev
git merge main
git push origin release/dev

# GitHub Actions automatically deploys to dev environment
```

### Verify Dev & Deploy to Staging

```bash
# After dev verification passes:
git checkout release/staging
git merge release/dev
git push origin release/staging

# GitHub Actions automatically deploys to staging environment
```

### Verify Staging & Deploy to Production

```bash
# After staging verification passes:
git checkout release/prod
git merge release/staging
git push origin release/prod

# GitHub Actions automatically deploys to production environment
```

---

## Quick Reference Commands

```bash
# === DEPLOY TO DEV ===
git checkout main && git pull
git checkout release/dev && git merge main && git push

# === PROMOTE DEV → STAGING ===
git checkout release/staging && git merge release/dev && git push

# === PROMOTE STAGING → PROD ===
git checkout release/prod && git merge release/staging && git push

# === HOTFIX TO PROD ===
git checkout -b hotfix/critical-fix release/prod
# ... fix and commit ...
git checkout release/prod && git merge hotfix/critical-fix && git push
git checkout main && git merge hotfix/critical-fix && git push
```

---

## GitHub Actions Triggers

### CI Workflow (`.github/workflows/ci.yml`)

**Triggers:** All pushes and PRs to `main`

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    # Unit tests, integration tests, linting
  security:
    # Dependency scanning, SAST
  build:
    # Verify Docker builds succeed
```

### Deploy Workflow (`.github/workflows/deploy.yml`)

**Triggers:** Push to `release/*` branches

```yaml
on:
  push:
    branches:
      - 'release/dev'
      - 'release/staging'
      - 'release/prod'

jobs:
  deploy:
    # Pulumi up, Docker build/push, K8s deploy
```

---

## Environment Progression

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DEVELOPMENT CYCLE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   feature/xyz ──PR──► main ──merge──► release/dev ──────────────────►   │
│                         │                  │                             │
│                         │                  ▼                             │
│                         │            ┌──────────┐                        │
│                         │            │   DEV    │  Automated tests       │
│                         │            │   ENV    │  Manual verification   │
│                         │            └────┬─────┘                        │
│                         │                 │                              │
│                         │                 ▼                              │
│                         │         release/staging ──────────────────►    │
│                         │                 │                              │
│                         │                 ▼                              │
│                         │           ┌──────────┐                         │
│                         │           │ STAGING  │  E2E tests              │
│                         │           │   ENV    │  QA verification        │
│                         │           └────┬─────┘                         │
│                         │                │                               │
│                         │                ▼                               │
│                         │          release/prod ───────────────────►     │
│                         │                │                               │
│                         │                ▼                               │
│                         │          ┌──────────┐                          │
│                         │          │   PROD   │  Production traffic      │
│                         │          │   ENV    │  Monitoring              │
│                         │          └──────────┘                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Rollback Procedures

### Rollback via Git Revert

```bash
# Revert the last deployment to prod
git checkout release/prod
git revert HEAD
git push origin release/prod
# GitHub Actions redeploys with reverted code
```

### Rollback via Pulumi

```bash
# List deployment history
cd infra/pulumi
pulumi stack history --stack prod

# Rollback to specific version
pulumi stack export --stack prod --version 42 | pulumi stack import --stack prod
pulumi up --stack prod --yes
```

### Rollback Kubernetes Only

```bash
# Rollback deployment to previous revision
kubectl rollout undo deployment/api -n code-remote
kubectl rollout undo deployment/executor -n code-remote

# Or to specific revision
kubectl rollout undo deployment/api -n code-remote --to-revision=3
```

---

## Branch Protection Rules

### `main` Branch

```
✅ Require pull request before merging
✅ Require 1 approval
✅ Dismiss stale reviews when new commits pushed
✅ Require status checks to pass (ci/test, ci/lint)
✅ Require branches to be up to date
✅ Do not allow bypassing settings
```

### `release/prod` Branch

```
✅ Require pull request before merging (optional, for audit trail)
✅ Require status checks to pass
✅ Restrict who can push (release managers only)
✅ Require deployments to succeed (staging)
```

---

## Semantic Versioning

We use [Semantic Versioning](https://semver.org/) for releases.

```bash
# Tag after successful prod deployment
git checkout release/prod
git tag -a v1.2.3 -m "Release v1.2.3: Add execution timeout feature"
git push origin v1.2.3
```

### Version Bump Guidelines

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| Breaking API change | Major | `v1.0.0` → `v2.0.0` |
| New feature (backward compatible) | Minor | `v1.0.0` → `v1.1.0` |
| Bug fix | Patch | `v1.0.0` → `v1.0.1` |

---

## Troubleshooting

### Deployment Failed

```bash
# Check GitHub Actions logs
# Go to: Repository → Actions → Failed workflow run

# Check Pulumi state
cd infra/pulumi
pulumi stack --stack dev

# Check K8s pod status
kubectl get pods -n code-remote
kubectl describe pod <pod-name> -n code-remote
kubectl logs <pod-name> -n code-remote
```

### Release Branch Out of Sync

```bash
# Reset release/dev to match main exactly
git checkout release/dev
git reset --hard main
git push --force-with-lease origin release/dev
```

### Merge Conflicts on Release Branch

```bash
# Resolve conflicts and continue
git checkout release/staging
git merge release/dev
# ... resolve conflicts ...
git add .
git commit -m "chore: resolve merge conflicts"
git push origin release/staging
```
