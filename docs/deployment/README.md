# Deployment Documentation

This directory contains deployment and operations documentation.

## Documents

| Document | Description |
|----------|-------------|
| [CI/CD Pipeline](ci-cd.md) | GitHub Actions automated deployment |
| [Release Strategy](release-strategy.md) | Versioning, environments, releases |
| [Local Development](local-development.md) | Docker Compose local setup |

## Quick Reference

### Deploy to Dev
```bash
git push origin main  # Auto-deploys to dev
```

### Deploy to Prod
```bash
git tag v1.0.0
git push origin v1.0.0  # Auto-deploys to prod
```

### Manual Deploy
```bash
cd infra/pulumi
pulumi stack select dev
pulumi up --yes
```
