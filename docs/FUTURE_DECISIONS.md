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
