# Future Technical Decisions

This document tracks deferred technical decisions and potential improvements.

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

**Status:** Deferred  
**Date Added:** January 26, 2026

**Current State:**
- Using deprecated `google-generativeai` package
- FutureWarning displayed on import

**Action Required:**
- Replace `google-generativeai` with `google-genai` package
- Update `analyzer/providers/gemini.py` to use new API
- See: https://github.com/google-gemini/deprecated-generative-ai-python/blob/main/README.md

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
