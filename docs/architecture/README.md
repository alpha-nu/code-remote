# Architecture Documentation

This directory contains the architecture documentation for Code Remote.

## Documents

| Document | Description |
|----------|-------------|
| [Overview](overview.md) | High-level system architecture, technology stack, design decisions |
| [Backend](backend.md) | Python/FastAPI backend architecture, services, API design |
| [Frontend](frontend.md) | React application architecture, components, state management |
| [Infrastructure](infrastructure.md) | AWS cloud architecture, Pulumi IaC, resource details |
| [Security](security.md) | Security model, sandbox design, import restrictions |
| [Data Model](data-model.md) | Database schemas, PostgreSQL + Neo4j data architecture |

## Diagrams

Visual architecture diagrams are in the [diagrams/](../diagrams/) directory:

- **aws_architecture.png** - Full AWS infrastructure diagram
- **data_flow.png** - Code execution data flow
- **security_layers.png** - Defense in depth visualization

### Regenerating Diagrams

```bash
# Install diagrams library
pip install diagrams

# Generate diagrams
cd docs/diagrams
python aws_architecture.py
```

## Quick Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Code Remote                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────────────┐   │
│  │  Frontend   │    │   API Gateway    │    │   Lambda (FastAPI)      │   │
│  │  React +    │───▶│   HTTP + WS      │───▶│   - /execute            │   │
│  │  Monaco     │    │                  │    │   - /analyze            │   │
│  └─────────────┘    └──────────────────┘    │   - /snippets           │   │
│                                              └───────────┬─────────────┘   │
│                                                          │                  │
│         ┌────────────────────────────────────────────────┼─────────────┐   │
│         │                                                │             │   │
│         ▼                                                ▼             ▼   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  ┌───────────┐   │
│  │  Cognito     │   │  PostgreSQL  │   │  Neo4j       │  │  Gemini   │   │
│  │  (Auth)      │   │  (CRUD)      │───▶  (Search)    │  │  (LLM)    │   │
│  └──────────────┘   └──────────────┘   └──────────────┘  └───────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
