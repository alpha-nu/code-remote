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
    ├── README.md                # Phase progress summary
    └── phase-10-realtime.md     # Async execution & WebSockets
```

## Quick Links

| Document | Description |
|----------|-------------|
| [Architecture Overview](architecture/overview.md) | System design, tech stack, component overview |
| [Security Model](architecture/security.md) | Sandbox security, import restrictions, resource limits |
| [Phase 10: Real-Time](phases/phase-10-realtime.md) | WebSocket-based async execution (current focus) |
| [Deployment Guide](DEPLOYMENT.md) | How to deploy to AWS |
| [Release Strategy](release-strategy.md) | Versioning, tagging, and release workflows |

## Current Status

| Phase | Name | Status |
|-------|------|--------|
| 1-8 | Foundation through Security | ✅ Complete |
| 9 | Persistence & Code Snippets | 📋 Planning |
| **10** | **Real-Time Async Execution** | **🚀 Ready to Implement** |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + Monaco Editor + AWS Amplify |
| Backend | FastAPI + AWS Lambda (Mangum) |
| Auth | AWS Cognito |
| Queue | AWS SQS FIFO |
| Database | DynamoDB (jobs), Aurora PostgreSQL (future) |
| Real-time | API Gateway WebSocket |
| LLM | Google Gemini API |
| IaC | Pulumi (Python) |
