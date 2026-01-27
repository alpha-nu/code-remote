# Code Remote Infrastructure

Pulumi-based Infrastructure as Code for the Code Remote application.

## Prerequisites

- [Pulumi CLI](https://www.pulumi.com/docs/install/)
- [AWS CLI](https://aws.amazon.com/cli/) configured with credentials
- Python 3.11+

## Setup

```bash
# From project root, activate the shared venv
cd /path/to/code-remote
source .venv/bin/activate

# Install Pulumi dependencies into root venv
pip install -r infra/pulumi/requirements.txt

# Navigate to infra directory
cd infra/pulumi

# Login to Pulumi (use local backend or Pulumi Cloud)
pulumi login --local  # or: pulumi login
```

## Stacks

| Stack | Environment | Description |
|-------|-------------|-------------|
| `dev` | Development | Single NAT gateway, 2 AZs, cost-optimized |
| `staging` | Staging | 2 AZs, mirrors prod config |
| `prod` | Production | 3 AZs, HA configuration |

## Deploying

```bash
# Select stack
pulumi stack select dev  # or staging, prod

# Preview changes
pulumi preview

# Deploy
pulumi up

# View outputs
pulumi stack output
```

## Components

### VPC (`components/vpc.py`)
- VPC with configurable CIDR block
- Public subnets (for ALB, NAT Gateway)
- Private subnets (for EKS nodes)
- NAT Gateway (single for dev, per-AZ for prod)
- Route tables for public/private traffic

### ECR (`components/ecr.py`)
- API container repository
- Executor container repository
- Lifecycle policies (keep last 10 images)

### Secrets Manager (`components/secrets.py`)
- Gemini API key secret
- Application secrets placeholder

### Cognito (`components/cognito.py`)
- User Pool for authentication
- User Pool Client for frontend
- Email-based authentication

## Setting Secrets

```bash
# Set Gemini API key (encrypted)
pulumi config set --secret gemini_api_key "your-api-key"

# Verify
pulumi config get gemini_api_key
```

## Outputs

After deployment, the following outputs are available:

```bash
pulumi stack output
```

| Output | Description |
|--------|-------------|
| `vpc_id` | VPC ID |
| `public_subnet_ids` | Public subnet IDs |
| `private_subnet_ids` | Private subnet IDs |
| `ecr_api_repository_url` | ECR URL for API image |
| `ecr_executor_repository_url` | ECR URL for executor image |
| `cognito_user_pool_id` | Cognito User Pool ID |
| `cognito_user_pool_client_id` | Cognito Client ID |

## Cost Optimization

- **Dev environment**: Single NAT gateway (saves ~$30/month)
- **ECR lifecycle**: Auto-delete old images
- **On-demand instances**: Use Spot instances in EKS (Phase 7B)

## Next Steps (Phase 7B)

- EKS cluster with managed node groups
- gVisor runtime for executor isolation
- Kubernetes manifests for API and executor
