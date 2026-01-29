#!/bin/bash
# Full API test script

TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id 2ee2uiakro0qkgjv583i0posu7 \
  --auth-parameters USERNAME=testuser@coderemote.dev,PASSWORD='CodeRemote2026!' \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' --output text)

echo "=== Test 1: Simple print ==="
curl -s -X POST https://4mmzhfx6w1.execute-api.us-east-1.amazonaws.com/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"code": "print(\"Hello from Lambda executor!\")"}' | jq '{success, stdout}'

echo ""
echo "=== Test 2: Using allowed math module ==="
curl -s -X POST https://4mmzhfx6w1.execute-api.us-east-1.amazonaws.com/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"code": "import math\nprint(f\"sqrt(16) = {math.sqrt(16)}\")"}' | jq '{success, stdout}'

echo ""
echo "=== Test 3: Security - blocked import (os) ==="
curl -s -X POST https://4mmzhfx6w1.execute-api.us-east-1.amazonaws.com/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"code": "import os\nprint(os.getcwd())"}' | jq '{success, error, error_type}'

echo ""
echo "=== Test 4: Error handling (ZeroDivision) ==="
curl -s -X POST https://4mmzhfx6w1.execute-api.us-east-1.amazonaws.com/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"code": "x = 1/0"}' | jq '{success, error, error_type}'

echo ""
echo "=== Test 5: Analyze endpoint ==="
curl -s -X POST https://4mmzhfx6w1.execute-api.us-east-1.amazonaws.com/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"code": "def fibonacci(n):\n    if n <= 1: return n\n    return fibonacci(n-1) + fibonacci(n-2)"}' | jq '{status, complexity}'
