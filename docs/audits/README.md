# AWS Audits

This folder contains periodic AWS infrastructure audits comparing deployed resources against Pulumi state and documentation.

## Quick Start

See [runbook.md](runbook.md) for step-by-step audit commands.

## Purpose

- Identify orphaned/rogue resources not managed by IaC
- Verify cost optimization (no unused resources running)
- Security review (no exposed endpoints or stale APIs)
- Documentation accuracy validation

## Audit Schedule

Audits should be performed:
- After major infrastructure changes
- Monthly for cost review
- Before production releases

## Audit Reports

| Date | Environment | Status | Notes |
|------|-------------|--------|-------|
| 2026-02-06 | dev | ⚠️ Issues Found | 2 orphaned resources identified and cleaned |
