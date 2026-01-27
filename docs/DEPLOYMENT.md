# Deployment Guide

## Overview

This project uses GitHub Actions for CI/CD with automated deployments to AWS EKS.

## Deployment Workflow

### Automatic Deployments

Push to a release branch to trigger automatic deployment:

```bash
# Deploy to dev
git checkout -b release/dev
git push origin release/dev

# Promote to staging
git checkout release/staging
git merge release/dev
git push origin release/staging

# Promote to production
git checkout release/prod
git merge release/staging
git push origin release/prod
```

### Manual Deployments

Use the GitHub Actions UI to trigger a manual deployment:
1. Go to Actions → Deploy
2. Click "Run workflow"
3. Select the target environment

## Pipeline Stages

1. **Setup** - Determine target environment from branch name
2. **Test** - Run all unit tests before deploying
3. **Infrastructure** - Deploy/update AWS resources with Pulumi
4. **Build Images** - Build and push Docker images to ECR
5. **Deploy K8s** - Apply Kubernetes manifests with Kustomize
6. **Smoke Tests** - Run basic health checks (dev/staging only)

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
- **staging** - Optional approval
- **prod** - Required approval (add reviewers)

## Manual Kubernetes Operations

### Check deployment status

```bash
# Configure kubectl
aws eks update-kubeconfig --name <cluster-name> --region us-east-1

# View pods
kubectl get pods -n code-remote

# View logs
kubectl logs -f deployment/api -n code-remote
kubectl logs -f deployment/executor -n code-remote

# Check events
kubectl get events -n code-remote --sort-by='.lastTimestamp'
```

### Rollback deployment

```bash
# Rollback to previous version
kubectl rollout undo deployment/api -n code-remote
kubectl rollout undo deployment/executor -n code-remote

# Rollback to specific revision
kubectl rollout undo deployment/api -n code-remote --to-revision=2
```

### Scale deployments

```bash
# Scale API (horizontal)
kubectl scale deployment/api -n code-remote --replicas=5

# Scale executors
kubectl scale deployment/executor -n code-remote --replicas=10
```

## Pulumi Manual Operations

### Preview changes

```bash
cd infra/pulumi
pulumi preview --stack code-remote-dev
```

### Deploy infrastructure only

```bash
pulumi up --stack code-remote-dev --yes
```

### View outputs

```bash
pulumi stack output --stack code-remote-dev
```

### Destroy environment (CAUTION)

```bash
pulumi destroy --stack code-remote-dev --yes
```

## Troubleshooting

### Pods not starting

1. Check pod events: `kubectl describe pod <pod-name> -n code-remote`
2. Check node resources: `kubectl top nodes`
3. Verify image pull: Check ECR permissions and image tags

### gVisor issues

1. Ensure nodes have gVisor installed
2. Check RuntimeClass: `kubectl get runtimeclass gvisor`
3. Verify node labels: `kubectl get nodes --show-labels`

### Pulumi state issues

1. Check Pulumi Cloud for state conflicts
2. Run `pulumi refresh` to sync state
3. Use `pulumi stack export/import` for recovery
