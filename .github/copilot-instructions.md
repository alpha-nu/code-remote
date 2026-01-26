# Code Remote - AI Coding Agent Instructions

## Project Overview
Remote Code Execution Engine: Users write Python code in a web interface, we execute it securely and return results with AI-powered complexity analysis.

**Architecture:** Hybrid (Managed Services + Self-hosted K8s Execution)  
**Cloud:** AWS (initial), designed for cloud-agnostic migration  
**Auth:** AWS Cognito | **LLM:** Google Gemini | **Timeout:** 30s max

---

## Project Structure
```
code-remote/
├── frontend/          # React + Monaco Editor
├── backend/
│   ├── api/           # FastAPI services
│   ├── executor/      # Sandboxed Python runner
│   ├── analyzer/      # Gemini LLM complexity analysis
│   └── common/        # Shared utilities
├── infra/pulumi/      # Infrastructure as Code (Python)
└── kubernetes/        # K8s manifests for execution cluster
```

---

## Key Conventions

### Python Backend
- **Framework:** FastAPI with async/await throughout
- **Validation:** Pydantic models in `schemas/` directories
- **Config:** Use `pydantic-settings` with `.env` files, never hardcode secrets
- **Imports:** Absolute imports from package root (`from backend.api.services import ...`)

```python
# Example: All API endpoints follow this pattern
@router.post("/execute", response_model=ExecutionResponse)
async def execute_code(
    request: ExecutionRequest,
    user: User = Depends(get_current_user),  # Cognito JWT
    executor: ExecutorService = Depends(get_executor),
):
    return await executor.submit(request.code, user.id)
```

### Infrastructure (Pulumi)
- **Language:** Python (matches backend)
- **Abstraction:** Use provider interfaces for cloud-agnostic components
- **Naming:** `{env}-{service}-{resource}` (e.g., `prod-api-lambda`)

```python
# infra/pulumi/components/ - Always implement cloud abstraction
class QueueProvider(ABC):
    @abstractmethod
    def create_queue(self, name: str) -> Queue: pass

class AWSQueue(QueueProvider):  # Initial implementation
    def create_queue(self, name: str) -> Queue:
        return aws.sqs.Queue(name, ...)
```

### Frontend (React)
- **Editor:** Monaco Editor with Python (possibly more languages) language support, so language support needs to be extensible.
- **State:** React Query for server state, Zustand for UI state
- **Auth:** AWS Amplify for Cognito integration

### Execution Sandbox Security Layers
1. **Container:** gVisor runtime (`runsc`) for kernel isolation
2. **Network:** K8s NetworkPolicy denying all egress
3. **Resources:** CPU 0.1 core, Memory 256MB, Timeout 30s
4. **Python:** Restricted imports whitelist (no `os`, `subprocess`, `socket`)

---

## Critical Workflows

### Local Development
```bash
# Start all services
docker-compose up -d

# Backend with hot reload
cd backend && uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Run sandbox locally (relaxed security for debugging)
docker run --rm -e RELAXED_MODE=true executor:dev
```

### Testing
```bash
# Unit tests (mock external services)
pytest backend/tests/unit/ -v --cov

# Integration tests (real containers via docker-compose.test.yml)
docker-compose -f docker-compose.test.yml up -d
pytest backend/tests/integration/ -v

# E2E (requires staging deployment)
pytest backend/tests/e2e/ --env=staging
```

---

## Infrastructure Deployment

### Prerequisites (One-time Setup)

```bash
# 1. Install tools
brew install pulumi awscli kubectl

# 2. Configure AWS credentials
aws configure  # Enter access key, secret, region (us-east-1)

# 3. Login to Pulumi (use local backend or Pulumi Cloud)
pulumi login --local  # or: pulumi login

# 4. Set up Pulumi secrets provider
export PULUMI_CONFIG_PASSPHRASE="your-passphrase"
```

### Manual Deployment (Step-by-Step)

```bash
# Step 1: Initialize infrastructure stack
cd infra/pulumi
pulumi stack init dev  # or: staging, prod

# Step 2: Configure stack
pulumi config set aws:region us-east-1
pulumi config set --secret geminiApiKey "your-gemini-key"
pulumi config set --secret cognitoClientSecret "your-cognito-secret"

# Step 3: Preview changes
pulumi preview --stack dev

# Step 4: Deploy AWS infrastructure (VPC, RDS, SQS, Cognito, ECR)
pulumi up --stack dev --yes

# Step 5: Build and push container images
export ECR_REPO=$(pulumi stack output ecrRepositoryUrl)
docker build -t $ECR_REPO/api:latest ./backend
docker build -t $ECR_REPO/executor:latest ./backend/executor
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REPO
docker push $ECR_REPO/api:latest
docker push $ECR_REPO/executor:latest

# Step 6: Deploy Kubernetes execution cluster
aws eks update-kubeconfig --name $(pulumi stack output eksClusterName)
kubectl apply -k kubernetes/overlays/dev/

# Step 7: Verify deployment
kubectl get pods -n code-remote
curl $(pulumi stack output apiEndpoint)/health
```

### Automated Deployment (GitHub Actions)

**Trigger:** Push to `release/dev`, `release/staging`, or `release/prod` branches

```yaml
# .github/workflows/deploy.yml
name: Deploy Infrastructure

on:
  push:
    branches:
      - 'release/dev'
      - 'release/staging'
      - 'release/prod'

env:
  PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Determine environment
        id: env
        run: echo "stack=${GITHUB_REF#refs/heads/release/}" >> $GITHUB_OUTPUT
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install Pulumi
        uses: pulumi/actions@v5
      
      - name: Deploy Infrastructure
        working-directory: infra/pulumi
        run: |
          pip install -r requirements.txt
          pulumi stack select ${{ steps.env.outputs.stack }}
          pulumi up --yes
      
      - name: Build & Push Images
        run: |
          ECR_REPO=$(cd infra/pulumi && pulumi stack output ecrRepositoryUrl)
          aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REPO
          docker build -t $ECR_REPO/api:${{ github.sha }} ./backend
          docker build -t $ECR_REPO/executor:${{ github.sha }} ./backend/executor
          docker push $ECR_REPO/api:${{ github.sha }}
          docker push $ECR_REPO/executor:${{ github.sha }}
      
      - name: Deploy to Kubernetes
        run: |
          aws eks update-kubeconfig --name $(cd infra/pulumi && pulumi stack output eksClusterName)
          kubectl set image deployment/api api=$ECR_REPO/api:${{ github.sha }} -n code-remote
          kubectl set image deployment/executor executor=$ECR_REPO/executor:${{ github.sha }} -n code-remote
          kubectl rollout status deployment/api -n code-remote
```

### Release Branch Workflow

```bash
# Deploy to dev
git checkout -b release/dev
git push origin release/dev

# Promote to staging (after dev verification)
git checkout release/staging
git merge release/dev
git push origin release/staging

# Promote to prod (after staging verification)
git checkout release/prod
git merge release/staging
git push origin release/prod
```

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS IAM access key with deployment permissions |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |
| `PULUMI_ACCESS_TOKEN` | Pulumi Cloud token (or use `PULUMI_CONFIG_PASSPHRASE` for local backend) |
| `GEMINI_API_KEY` | Google Gemini API key |

### Stack Outputs Reference

```bash
# Get all outputs for current stack
pulumi stack output

# Key outputs:
# - apiEndpoint: https://api.coderemote.dev
# - ecrRepositoryUrl: 123456789.dkr.ecr.us-east-1.amazonaws.com/code-remote
# - eksClusterName: dev-code-remote-eks
# - rdsEndpoint: dev-db.xxxxx.us-east-1.rds.amazonaws.com
# - cognitoUserPoolId: us-east-1_XXXXXX
```

---

## LLM Integration (Gemini)

**SDK:** `google-generativeai` — requires only `GEMINI_API_KEY` env var (no GCP project, no service accounts)

```python
# backend/analyzer/providers/gemini.py
import google.generativeai as genai
from backend.common.config import settings

class GeminiProvider(LLMProvider):
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)  # Only API key needed
        self.model = genai.GenerativeModel('gemini-pro')
    
    async def analyze_complexity(self, code: str) -> ComplexityResult:
        prompt = self._load_prompt('complexity.txt').format(code=code)
        response = await self.model.generate_content_async(prompt)
        return self._parse_response(response)
```

**Prompts:** Store in `backend/analyzer/prompts/` as `.txt` files, not inline strings.

**Environment:**
```bash
# .env (local) or AWS Secrets Manager (prod)
GEMINI_API_KEY=your-api-key-here
```

---

## File Naming & Patterns

| Type | Pattern | Example |
|------|---------|---------|
| API Router | `{resource}.py` | `execution.py` |
| Pydantic Schema | `{resource}.py` | `schemas/execution.py` |
| Service | `{resource}_service.py` | `execution_service.py` |
| Test | `test_{module}.py` | `test_execution_service.py` |
| Pulumi Component | `{resource}.py` | `components/database.py` |

---

## Do NOT

- Hardcode AWS-specific services in business logic (use abstractions)
- Store secrets in code or Pulumi config (use AWS Secrets Manager)
- Allow arbitrary imports in executor (whitelist only: `math`, `json`, `collections`, `itertools`, `functools`, `typing`, `dataclasses`)
- Skip input validation on code submissions (max 10KB, UTF-8 only)
- Run executor containers with network access in production

---

## Key Files to Understand

- `backend/api/main.py` - FastAPI app entry, middleware setup
- `backend/executor/runner.py` - Core sandboxed execution logic
- `backend/executor/security.py` - Import restrictions, AST validation
- `infra/pulumi/__main__.py` - Infrastructure entry point
- `kubernetes/base/executor/` - Execution pod specs with gVisor
