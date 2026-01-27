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
