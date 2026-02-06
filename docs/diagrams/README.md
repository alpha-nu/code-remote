# Architecture Diagrams

This directory contains visual architecture diagrams for Code Remote.

## Generated Diagrams

Run the Python script to generate PNG diagrams:

```bash
# Install diagrams library
pip install diagrams

# Generate diagrams
python aws_architecture.py
```

This creates:
- `aws_architecture.png` - Full AWS infrastructure
- `data_flow.png` - Code execution flow
- `security_layers.png` - Security model

## Mermaid Diagrams

The documentation uses Mermaid diagrams which render natively in:
- GitHub
- VS Code (with Mermaid extension)
- Most documentation tools

## Diagram Files

| File | Type | Description |
|------|------|-------------|
| `aws_architecture.py` | Python | Generates AWS diagrams using `diagrams` library |
| `*.png` | Image | Generated architecture diagrams |

## Updating Diagrams

When architecture changes:

1. Update `aws_architecture.py` with new components
2. Run `python aws_architecture.py`
3. Commit the updated PNG files
4. Update Mermaid diagrams in markdown files

## Requirements

```bash
pip install diagrams graphviz
```

Note: Graphviz must be installed on your system:
- macOS: `brew install graphviz`
- Ubuntu: `apt install graphviz`
