# Security Model

## Overview

Code Remote executes untrusted user code. Security is enforced at multiple layers to prevent malicious code from escaping the sandbox.

## Security Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    Security Defense in Depth                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: API Gateway                                          │
│  ├── JWT Authentication (Cognito)                              │
│  ├── Rate limiting (10 req/min per user)                       │
│  └── Request size limits (10KB max code)                       │
│                                                                 │
│  Layer 2: Input Validation                                     │
│  ├── Pydantic schema validation                                │
│  ├── UTF-8 encoding check                                      │
│  └── Code size limit enforcement                               │
│                                                                 │
│  Layer 3: AST Analysis (Pre-execution)                         │
│  ├── Import whitelist validation                               │
│  ├── Dangerous function detection                              │
│  └── Syntax validation                                         │
│                                                                 │
│  Layer 4: Execution Sandbox                                    │
│  ├── Restricted builtins                                       │
│  ├── No file system access                                     │
│  ├── No network access                                         │
│  └── Memory/time limits via Lambda                             │
│                                                                 │
│  Layer 5: Lambda Container Isolation                           │
│  ├── Ephemeral execution environment                           │
│  ├── No persistent state between executions                    │
│  ├── VPC isolation (no internet egress)                        │
│  └── IAM least-privilege                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Import Whitelist

Only these modules can be imported by user code:

```python
ALLOWED_IMPORTS = {
    # Math & Numbers
    "math", "cmath", "decimal", "fractions", "random", "statistics",
    
    # Data Structures
    "collections", "heapq", "bisect", "array",
    
    # Functional
    "itertools", "functools", "operator",
    
    # Text
    "string", "re", "textwrap",
    
    # Data Formats
    "json", "csv",
    
    # Time
    "datetime", "calendar", "time",
    
    # Type System
    "typing", "dataclasses", "enum", "abc",
    
    # Utilities
    "copy", "pprint",
}
```

> Some modules (`time`, `random`, `functools`, `re`, `decimal`) are wrapped with 
> resource limits to prevent abuse (e.g., max regex input length, max cache size).

### Blocked Modules (Examples)
- `os`, `sys` - System access
- `subprocess`, `shlex` - Process spawning
- `socket`, `urllib`, `requests` - Network access
- `pickle`, `marshal` - Deserialization attacks
- `ctypes`, `cffi` - Native code execution
- `importlib`, `__import__` - Dynamic imports

## Restricted Builtins

```python
SAFE_BUILTINS = {
    # Types
    "bool", "int", "float", "complex", "str", "bytes", "bytearray",
    "list", "tuple", "dict", "set", "frozenset",
    
    # Iteration
    "range", "enumerate", "zip", "map", "filter", "reversed", "sorted",
    "iter", "next",
    
    # Math
    "abs", "divmod", "pow", "round", "sum", "min", "max",
    
    # Comparisons
    "all", "any", "len", "hash",
    
    # Type checking
    "isinstance", "issubclass", "type", "callable",
    
    # String/repr
    "repr", "str", "format", "chr", "ord", "ascii",
    
    # Object access
    "getattr", "hasattr", "setattr", "delattr",
    
    # Containers
    "slice", "object", "super",
    
    # I/O (stdout only)
    "print", "input",  # input() returns empty string
    
    # Exceptions
    "Exception", "BaseException", "ValueError", "TypeError",
    "KeyError", "IndexError", "AttributeError", "RuntimeError",
    "StopIteration", "ZeroDivisionError", "OverflowError",
}
```

### Blocked Builtins
- `exec`, `eval`, `compile` - Dynamic code execution
- `open`, `file` - File system access
- `__import__` - Dynamic imports
- `globals`, `locals` - Scope manipulation
- `breakpoint` - Debugger
- `memoryview` - Memory access

## AST Validation

Before execution, code is parsed and validated:

```python
class SecurityValidator(ast.NodeVisitor):
    """Validates AST for security violations."""
    
    def visit_Import(self, node):
        for alias in node.names:
            if alias.name not in SAFE_IMPORTS:
                raise SecurityError(f"Import not allowed: {alias.name}")
    
    def visit_ImportFrom(self, node):
        if node.module not in SAFE_IMPORTS:
            raise SecurityError(f"Import not allowed: {node.module}")
    
    def visit_Call(self, node):
        # Block dangerous function calls
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_FUNCTIONS:
                raise SecurityError(f"Function not allowed: {node.func.id}")
```

## Resource Limits

| Resource | Limit | Enforcement |
|----------|-------|-------------|
| Execution time | 30 seconds | Lambda timeout + Python signal |
| Memory | 256 MB | Lambda memory limit |
| Code size | 10 KB | API validation |
| Output size | 1 MB | Truncation |
| Stack depth | 1000 | sys.setrecursionlimit |

## Network Isolation

Worker Lambda runs in a VPC with no internet egress:

```python
# Pulumi: VPC configuration for worker
worker_vpc = aws.ec2.Vpc("worker-vpc", ...)

# No NAT gateway = no internet access
worker_subnet = aws.ec2.Subnet(
    "worker-subnet",
    vpc_id=worker_vpc.id,
    # Private subnet, no route to internet
)

# Lambda in isolated subnet
worker_lambda = aws.lambda_.Function(
    "worker",
    vpc_config={
        "subnet_ids": [worker_subnet.id],
        "security_group_ids": [worker_sg.id],
    },
)
```

## Authentication

### JWT Validation
- Tokens issued by Cognito
- Validated on every API request
- Short expiry (1 hour)
- Refresh tokens handled by frontend

### WebSocket Auth
- JWT passed as query parameter on $connect
- Validated by connect handler Lambda
- Connection rejected if invalid

## Audit Logging

All executions are logged:

```python
{
    "timestamp": "2026-02-03T12:00:00Z",
    "job_id": "uuid",
    "user_id": "cognito-sub",
    "action": "execute",
    "code_hash": "sha256:...",  # Not the actual code
    "result": "success|failure|timeout",
    "execution_time_ms": 42,
}
```

## Security Checklist

| Layer | Control | Status |
|-------|---------|--------|
| API | JWT Authentication | ✅ |
| API | Rate limiting | ✅ |
| API | Input validation | ✅ |
| Sandbox | Import whitelist | ✅ |
| Sandbox | Restricted builtins | ✅ |
| Sandbox | AST validation | ✅ |
| Sandbox | Timeout enforcement | ✅ |
| Lambda | Memory limits | ✅ |
| Lambda | VPC isolation | ✅ |
| Lambda | IAM least-privilege | ✅ |
