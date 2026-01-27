# Code Remote - Kubernetes Manifests

Kubernetes deployment manifests for the Code Remote application.

## Structure

```
kubernetes/
├── base/                    # Base manifests (shared across envs)
│   ├── api/                 # API service
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── kustomization.yaml
│   ├── executor/            # Executor service (sandboxed)
│   │   ├── deployment.yaml
│   │   ├── networkpolicy.yaml
│   │   ├── runtimeclass.yaml
│   │   └── kustomization.yaml
│   └── kustomization.yaml
└── overlays/                # Environment-specific patches
    ├── dev/
    ├── staging/
    └── prod/
```

## Deployment

```bash
# Deploy to dev
kubectl apply -k overlays/dev/

# Deploy to staging
kubectl apply -k overlays/staging/

# Deploy to prod
kubectl apply -k overlays/prod/
```

## Security Features

### Executor Isolation

The executor pods run with multiple security layers:

1. **gVisor Runtime** - Kernel isolation via `runsc`
2. **NetworkPolicy** - Blocks all egress traffic
3. **Resource Limits** - CPU 0.1, Memory 256Mi, 30s timeout
4. **Node Taints** - Runs only on dedicated executor nodes

### API Security

- Runs on dedicated API nodes
- Pulls secrets from AWS Secrets Manager
- Health checks for automatic recovery
