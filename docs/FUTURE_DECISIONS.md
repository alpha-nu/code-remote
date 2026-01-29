# Future Technical Decisions

This document tracks deferred technical decisions and potential improvements.

---

## Phase 7: Infrastructure & Deployment

**Status:** Planning Complete  
**Date Added:** January 26, 2026

**Architecture Decisions:**
- **Container Orchestration:** EKS (Kubernetes) for gVisor sandbox isolation
- **Region:** Single region (us-east-1), expand later
- **Domain/HTTPS:** Use AWS-provided endpoints initially, no custom domain
- **Cost Strategy:** Spot instances, right-sized resources, auto-scaling

**Implementation Plan:**

### Phase 7A: AWS Foundation (Pulumi)
- VPC + Subnets (public/private)
- ECR (container registry)
- Secrets Manager (GEMINI_API_KEY, Cognito secrets)
- Cognito User Pool deployment

### Phase 7B: EKS Cluster
- EKS cluster with managed node groups
- Spot instances for cost savings
- gVisor runtime for executor pods
- NetworkPolicy for executor isolation

### Phase 7C: CI/CD Deployment
- GitHub Actions deploy workflow
- Branch-based environments (release/dev, release/staging, release/prod)
- Automated rollouts with health checks

---

## Python Version Upgrade

**Status:** Deferred  
**Date Added:** January 26, 2026

**Current State:**
- Project targets Python 3.11 (`requires-python = ">=3.11"`)
- Local development uses Python 3.13.3
- Docker and CI use Python 3.11

**Options:**
1. **Stay with 3.11** - Maximum stability, 2+ years of patches
2. **Bump to 3.12** - Good balance of features and stability (released Oct 2023)
3. **Bump to 3.13** - Latest features but newest release

**Considerations:**
- The `google-generativeai` package is deprecated; migrate to `google-genai` first
- Test all dependencies for compatibility before upgrading
- Update in all locations: `pyproject.toml`, `Dockerfile`, `ci.yml`, ruff target

**Files to update when upgrading:**
- `backend/pyproject.toml` (requires-python, tool.ruff.target-version, tool.mypy.python_version)
- `backend/Dockerfile` (FROM python:X.XX-slim)
- `.github/workflows/ci.yml` (uv python install X.XX)

---

## Migrate google-generativeai to google-genai

**Status:** ✅ Complete  
**Date Completed:** January 26, 2026

**Changes Made:**
- Replaced `google-generativeai` with `google-genai>=1.0.0` in pyproject.toml
- Rewrote `analyzer/providers/gemini.py` to use new Client-based API
- Updated model from `gemini-3-flash-preview` to `gemini-2.5-flash`
- Updated test mocks for new SDK

---

## Auth Backend Proxy (Remove AWS Amplify)

**Status:** Planned  
**Date Added:** January 29, 2026

**Current State:**
- Frontend uses `@aws-amplify/auth` to communicate directly with Cognito
- Cognito User Pool ID and Client ID exposed to frontend
- AWS-specific implementation leaked to client

**Proposed Change:**
Create `/auth/*` routes in the backend to proxy Cognito, removing direct frontend-to-Cognito communication.

**New Routes:**
```
POST /auth/login        → Sign in, return tokens
POST /auth/register     → Create account
POST /auth/confirm      → Verify email code
POST /auth/refresh      → Refresh tokens
POST /auth/logout       → Invalidate session
GET  /auth/me           → Get current user info
```

**Benefits:**
- No AWS SDK in frontend (smaller bundle, ~50KB savings)
- Hide Cognito implementation details from client
- Easier to swap auth providers later (Auth0, Firebase, custom)
- Can add custom logic (rate limiting, audit logging, brute-force protection)
- Single API domain (eliminates CORS to Cognito)

**Drawbacks:**
- Extra network hop for auth requests
- Backend manages token refresh logic
- More backend code to maintain

**Implementation Steps:**
1. Create `backend/api/routers/auth.py` with login/register/confirm/refresh endpoints
2. Create `backend/api/services/auth_service.py` to wrap Cognito boto3 calls
3. Update frontend to call `/auth/*` instead of using Amplify
4. Remove `@aws-amplify/auth` and `aws-amplify` dependencies from frontend
5. Simplify frontend auth store to just manage tokens from API responses

---

## Lambda Architecture (Single vs Multiple)

**Status:** Deferred  
**Date Added:** January 29, 2026

**Current State:**
All routes (`/health`, `/execute`, `/analyze`) are served by a single Lambda running FastAPI via Mangum adapter.

**Options Considered:**

### Option A: Single Lambda (Current ✅)
```
API Gateway → Single Lambda (FastAPI)
              ├── /health
              ├── /execute
              └── /analyze
```
- ✅ Simpler deployment and local development
- ✅ Shared code/dependencies
- ❌ Can't scale routes independently
- ❌ Cold starts affect all routes

### Option B: Lambda per Route
```
API Gateway → /health  → health-func
            → /execute → execute-func
            → /analyze → analyze-func
```
- ✅ Independent scaling and timeouts
- ✅ Isolate failures
- ❌ More deployment complexity
- ❌ Code duplication

### Option C: Lambda per Domain (Future consideration)
```
API Gateway → /auth/*   → auth-func
            → /execute  → exec-func
            → /*        → api-func (health, analyze, etc.)
```
Groups by responsibility:
- **auth-func**: Auth routes (lightweight, no sandbox needed)
- **exec-func**: Code execution (isolated, strict timeout/memory)
- **api-func**: Everything else

**Decision:** Stay with single Lambda for now. The current architecture is appropriate for our scale. Split when there's a concrete need (e.g., execute needs different timeout than analyze, or specific routes need independent scaling).

---

## Add More Frontend Tests

**Status:** Planned  
**Date Added:** January 26, 2026

**Current State:**
- 16 unit tests for Zustand store
- No component tests yet

**Potential Tests:**
- Component rendering tests (CodeEditor, OutputPanel, ComplexityPanel, Toolbar)
- Integration tests for API calls
- End-to-end tests with Playwright or Cypress

---

## Multi-Language Execution Engine (TypeScript, C#)

**Status:** Planning / Future Vision  
**Date Added:** January 29, 2026

### Current State (Python Only)

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  Monaco Editor (Python mode) → /execute → Python output     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Lambda Executor                           │
│  exec(code, restricted_globals) → stdout/stderr             │
│  - Python-only sandbox via restricted builtins              │
│  - SAFE_IMPORTS whitelist                                   │
└─────────────────────────────────────────────────────────────┘
```

### Target State (Multi-Language)

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  Monaco Editor (auto-detect) → /execute?lang=X → output     │
│  Language selector: Python | TypeScript | C#                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                             │
│  POST /execute { code, language }                           │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ Python Exec  │ │   TS Exec    │ │   C# Exec    │
      │  (Lambda)    │ │  (Lambda)    │ │  (Lambda)    │
      │  Python 3.11 │ │  Node 20 +   │ │  .NET 8      │
      │              │ │  ts-node     │ │  dotnet run  │
      └──────────────┘ └──────────────┘ └──────────────┘
```

### API Layer Changes

**Current Schema:**
```python
class ExecutionRequest(BaseModel):
    code: str
```

**New Schema:**
```python
class Language(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    CSHARP = "csharp"

class ExecutionRequest(BaseModel):
    code: str
    language: Language = Language.PYTHON  # backward compatible
    
class ExecutionResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    language: Language
    runtime_version: str  # "Python 3.11", "Node 20.x", ".NET 8"
```

### Executor Architecture Options

#### Option A: Single Polyglot Lambda (Simple but Limited)
```
┌─────────────────────────────────────────┐
│  Lambda Container (1.5GB image)         │
│  ├── Python 3.11                        │
│  ├── Node 20 + TypeScript               │
│  └── .NET 8 SDK                         │
│                                         │
│  Router dispatches by language          │
└─────────────────────────────────────────┘
```
- ✅ Simple deployment
- ❌ Huge container image (~1.5GB+)
- ❌ Cold starts suffer
- ❌ Can't tune memory/timeout per language

#### Option B: Lambda per Language (Recommended ✅)
```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ python-exec  │  │   ts-exec    │  │  csharp-exec │
│ ~150MB image │  │ ~300MB image │  │ ~400MB image │
│ 256MB memory │  │ 512MB memory │  │ 512MB memory │
│ 30s timeout  │  │ 30s timeout  │  │ 30s timeout  │
└──────────────┘  └──────────────┘  └──────────────┘
```
- ✅ Right-sized containers
- ✅ Independent scaling & cold start optimization
- ✅ Language-specific security hardening
- ❌ More Pulumi resources to manage

#### Option C: Container-per-Execution (Maximum Isolation)
```
API → SQS → ECS Fargate Task (ephemeral)
            └── Fresh container per execution
            └── Destroyed after completion
```
- ✅ Perfect isolation (no state leakage)
- ✅ Can run untrusted code with gVisor
- ❌ Slow (~5-10s cold start per execution)
- ❌ More expensive

**Recommendation:** Start with **Option B** for Lambda, move to **Option C** for premium/enterprise tier.

### Language-Specific Sandbox Strategies

#### Python (Current)
```python
# Restricted builtins + AST validation
SAFE_IMPORTS = {"math", "json", "collections", ...}
exec(code, {"__builtins__": SAFE_BUILTINS})
```

#### TypeScript
```typescript
// Approach: Compile then run in VM2 sandbox
import { VM } from 'vm2';
import * as ts from 'typescript';

const js = ts.transpileModule(code, { 
  compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText;

const vm = new VM({
  timeout: 30000,
  sandbox: { console, Math, JSON, Date },
  eval: false,
  wasm: false,
});
const result = vm.run(js);
```

Blocked capabilities:
- `require()` / `import` (no filesystem access)
- `process`, `child_process`, `fs`, `net`
- `eval()`, `Function()` constructor

#### C#
```csharp
// Approach: Roslyn scripting with restricted references
using Microsoft.CodeAnalysis.CSharp.Scripting;
using Microsoft.CodeAnalysis.Scripting;

var options = ScriptOptions.Default
    .WithReferences(typeof(object).Assembly)  // mscorlib only
    .WithImports("System", "System.Linq", "System.Collections.Generic");
    // NO System.IO, System.Net, System.Diagnostics

var result = await CSharpScript.EvaluateAsync(code, options);
```

Blocked namespaces:
- `System.IO` (filesystem)
- `System.Net` (network)
- `System.Diagnostics` (process spawning)
- `System.Reflection.Emit` (runtime code gen)

### Complexity Analysis (Gemini) Changes

**Current prompt structure:**
```
Analyze this Python code for time/space complexity...
```

**New prompt with language awareness:**
```python
COMPLEXITY_PROMPT = """
Analyze this {language} code for algorithmic complexity.

Language-specific considerations:
{language_hints}

Code:
```{language}
{code}
```
"""

LANGUAGE_HINTS = {
    "python": "Consider list comprehensions, generator expressions, dict operations",
    "typescript": "Consider Array methods, spread operators, async/await patterns",
    "csharp": "Consider LINQ operations, async/await, collection initializers",
}
```

### Frontend Changes

#### Monaco Editor Multi-Language Support
```typescript
// Current: hardcoded Python
<Editor language="python" ... />

// New: dynamic language
const [language, setLanguage] = useState<'python' | 'typescript' | 'csharp'>('python');

<LanguageSelector value={language} onChange={setLanguage} />
<Editor 
  language={language === 'csharp' ? 'csharp' : language} 
  value={code}
  ...
/>
```

#### Boilerplate Templates
```typescript
const TEMPLATES = {
  python: 'def main():\n    print("Hello, World!")\n\nmain()',
  typescript: 'function main(): void {\n    console.log("Hello, World!");\n}\n\nmain();',
  csharp: 'using System;\n\nConsole.WriteLine("Hello, World!");',
};
```

### Infrastructure (Pulumi) Changes

```python
# New: One executor Lambda per language
class ExecutorComponent(pulumi.ComponentResource):
    def __init__(self, name: str, language: str, ...):
        
        # Language-specific container
        self.ecr_repo = aws.ecr.Repository(f"{name}-{language}-repo")
        
        # Language-specific Lambda
        self.function = aws.lambda_.Function(
            f"{name}-{language}-executor",
            image_uri=self.ecr_repo.repository_url,
            memory_size=MEMORY_BY_LANGUAGE[language],  # 256, 512, 512
            timeout=30,
            ...
        )

# In __main__.py
python_executor = ExecutorComponent("exec", "python", ...)
typescript_executor = ExecutorComponent("exec", "typescript", ...)
csharp_executor = ExecutorComponent("exec", "csharp", ...)

# API Gateway routes to appropriate Lambda
# POST /execute?lang=python → python_executor
# POST /execute?lang=typescript → typescript_executor
```

### Migration Phases

```
Phase 1: Foundation (1-2 weeks)
├── Add language field to API schema
├── Refactor executor_service to use strategy pattern
├── Update frontend with language selector
└── Keep Python as only working language

Phase 2: TypeScript Support (1-2 weeks)
├── Create TypeScript executor Lambda
├── Implement VM2 sandbox
├── Add TS-specific complexity prompts
├── Integration tests

Phase 3: C# Support (1-2 weeks)
├── Create C# executor Lambda (.NET 8)
├── Implement Roslyn scripting sandbox
├── Add C#-specific complexity prompts
├── Integration tests

Phase 4: Production Hardening (1 week)
├── Per-language rate limiting
├── Monitoring & alerting per language
├── Cost tracking per language
└── Documentation
```

### Cost Implications

| Resource | Python Only | + TypeScript | + C# |
|----------|-------------|--------------|------|
| Lambda invocations | $X | $X (shared) | $X (shared) |
| ECR storage | ~150MB | +300MB | +400MB |
| Container builds | 1 | 2 | 3 |
| Cold starts to optimize | 1 | 2 | 3 |

ECR costs are minimal (~$0.10/GB/month). Main cost driver remains Lambda invocations which are shared across languages.

### Alternative: Use Existing Multi-Language Services

Instead of building custom executors, integrate existing services:

| Service | Pros | Cons |
|---------|------|------|
| **Judge0** | 60+ languages, battle-tested | Self-host or pay per execution |
| **Piston** | Open source, Docker-based | Self-host on ECS/K8s |
| **Sphere Engine** | Enterprise, secure | Expensive |

This would change the architecture to:
```
Your API → Judge0/Piston API → Execution result
```

**Trade-off:** Less control, but faster to market.

### Summary: Recommended Runway

1. **Short-term:** Document multi-language as future goal ✅ (this document)
2. **Phase 1:** Add `language` field to API, strategy pattern in executor
3. **Phase 2:** TypeScript via Node Lambda + VM2 sandbox
4. **Phase 3:** C# via .NET Lambda + Roslyn scripting
5. **Long-term:** Consider managed service (Judge0) for 60+ languages
