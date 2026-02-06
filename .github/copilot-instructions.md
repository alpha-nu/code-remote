# Code Remote - AI Coding Agent Instructions

## Project Overview
Remote Code Execution Engine: Users write Python code in a web interface, we execute it securely and return results with AI-powered complexity analysis.

**Architecture:** Serverless (Lambda + API Gateway + Aurora PostgreSQL)  
**Cloud:** AWS  
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
└── docs/              # Architecture documentation
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
1. **AST Validation** - Pre-execution import/pattern checking
2. **Restricted Builtins** - No eval, exec, open, __import__
3. **Import Whitelist** - Only safe modules allowed
4. **Lambda Isolation** - Ephemeral execution, timeout enforcement

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
brew install pulumi awscli

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
pulumi stack init dev  # or: prod

# Step 2: Configure stack
pulumi config set aws:region us-east-1

# Step 3: Preview changes
pulumi preview --stack dev

# Step 4: Deploy AWS infrastructure (VPC, Cognito, ECR, Lambda, S3, CloudFront)
pulumi up --stack dev --yes

# Step 5: Build and push container images
export API_ECR=$(pulumi stack output ecr_api_repository_url)
docker buildx build --platform linux/amd64 --provenance=false -t $API_ECR:latest -f backend/Dockerfile.lambda backend/
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $API_ECR
docker push $API_ECR:latest

# Step 6: Update Lambda function
aws lambda update-function-code \
  --function-name $(pulumi stack output api_function_name) \
  --image-uri $API_ECR:latest

# Step 7: Verify deployment
curl $(pulumi stack output api_endpoint)/health
```

### Automated Deployment (GitHub Actions)

The project uses a fully automated CI/CD pipeline with GitHub Actions.

**Architecture:** Lambda + API Gateway + S3/CloudFront (Serverless)

**Triggers:**
- `main` branch push → Deploy to **dev**
- Version tag (`v*`) → Deploy to **prod**
- Manual workflow dispatch → Choose environment

**Pipeline Stages:**
1. **Setup** - Determine environment (dev/prod) from trigger
2. **Test** - Run backend + frontend tests
3. **Infrastructure** - Deploy/update with Pulumi
4. **Build** - Build and push Docker images to ECR
5. **Deploy Backend** - Update Lambda function
6. **Deploy Frontend** - Sync to S3, invalidate CloudFront
7. **Smoke Tests** - Verify health endpoints
8. **Summary** - Generate deployment report

### Release Workflow

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

# Manual deployment (via GitHub UI)
# Go to Actions → Deploy → Run workflow → Select environment
```

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS IAM access key with deployment permissions |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |
| `PULUMI_ACCESS_TOKEN` | Pulumi Cloud token (or use `PULUMI_CONFIG_PASSPHRASE` for local backend) |
| `GEMINI_API_KEY` | Google Gemini API key (stored in AWS Secrets Manager, injected at deploy time) |

### Stack Outputs Reference

```bash
# Get all outputs for current stack
pulumi stack output

# Key outputs:
# - api_endpoint: https://xxxx.execute-api.us-east-1.amazonaws.com
# - api_function_name: code-remote-dev-api-func-xxxxx
# - ecr_api_repository_url: 123456789.dkr.ecr.us-east-1.amazonaws.com/code-remote-xxx-api
# - frontend_url: https://dxxxxxx.cloudfront.net
# - frontend_bucket_name: code-remote-xxx-frontend-xxx
# - cognito_user_pool_id: us-east-1_XXXXXX
# - cognito_user_pool_client_id: xxxxxxxxxxxxxxxxx
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
- Allow arbitrary imports in executor (whitelist only: `math`, `cmath`, `json`, `collections`, `itertools`, `functools`, `typing`, `dataclasses`, `random`, `string`, `re`, `datetime`, `decimal`, `fractions`, `statistics`, `operator`, `copy`, `heapq`, `bisect`, `array`, `enum`, `abc`, `time`, `calendar`, `csv`, `textwrap`, `pprint`)
- Skip input validation on code submissions (max 10KB, UTF-8 only)
- Run executor containers with network access in production

---

## Key Files to Understand

- `backend/api/main.py` - FastAPI app entry, middleware setup
- `backend/executor/runner.py` - Core sandboxed execution logic
- `backend/executor/security.py` - Import restrictions, AST validation
- `infra/pulumi/__main__.py` - Infrastructure entry point
- `infra/pulumi/components/` - Pulumi resource components
