# Code Remote - Documentation

## Overview

Remote Code Execution Engine: Users write Python code in a web interface, we execute it securely and return results with AI-powered complexity analysis.

## Documentation Structure

```
docs/
├── README.md                    # This file - documentation index
├── architecture-plan.md         # High-level architecture overview
├── DEPLOYMENT.md                # Deployment procedures
├── release-strategy.md          # Versioning and release workflows
├── future-decisions.md          # Deferred decisions and future plans
│
├── architecture/                # Detailed architecture documents
│   ├── overview.md              # System architecture & decisions
│   ├── security.md              # Security model & sandbox design
│   ├── data-model.md            # Database schemas & data flow
│   └── infrastructure.md        # AWS/Pulumi infrastructure details
│
└── phases/                      # Implementation phase details
    └── README.md                # Phase progress & implementation details
```

## Quick Links

| Document | Description |
|----------|-------------|
| [Architecture Overview](architecture/overview.md) | System design, tech stack, component overview |
| [Security Model](architecture/security.md) | Sandbox security, import restrictions, resource limits |
| [Phase Progress](phases/README.md) | Implementation phases, current: Phase 9 |
| [Deployment Guide](DEPLOYMENT.md) | How to deploy to AWS |
| [Release Strategy](release-strategy.md) | Versioning, tagging, and release workflows |

## Current Status

| Phase | Name | Status |
|-------|------|--------|
| 1-8 | Foundation through Security | ✅ Complete |
| **9** | **Persistence (PostgreSQL + Neo4j)** | **🔄 In Progress** |
| 10 | Real-Time Async Execution | ✅ Complete |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + Monaco Editor + AWS Amplify |
| Backend | FastAPI + AWS Lambda (Mangum) |
| Auth | AWS Cognito |
| Queue | AWS SQS FIFO |
| Database | Aurora PostgreSQL (CRUD) + Neo4j AuraDB (search) |
| Real-time | API Gateway WebSocket |
| LLM | Google Gemini API |
| IaC | Pulumi (Python) |
