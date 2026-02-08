#!/bin/bash
#
# Trace LLM Interactions via AWS X-Ray
#
# Queries X-Ray for all subsegments with gen_ai_operation annotation
# and displays detailed metadata including tokens, cypher queries, etc.
#
# Usage:
#   ./trace-llm.sh [minutes]
#
# Examples:
#   ./trace-llm.sh        # Last 5 minutes (default)
#   ./trace-llm.sh 10     # Last 10 minutes
#   ./trace-llm.sh 30     # Last 30 minutes
#

set -e

# Default to 5 minutes if not specified
MINUTES=${1:-5}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${BOLD}🔍 Tracing LLM interactions from the last ${MINUTES} minutes${NC}"
echo ""

# Calculate time range (macOS compatible)
if [[ "$OSTYPE" == "darwin"* ]]; then
    START_TIME=$(date -u -v-${MINUTES}M +%Y-%m-%dT%H:%M:%SZ)
    END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
else
    START_TIME=$(date -u -d "${MINUTES} minutes ago" +%Y-%m-%dT%H:%M:%SZ)
    END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
fi

echo -e "${CYAN}Time range: ${START_TIME} → ${END_TIME}${NC}"
echo ""

# Get trace summaries with gen_ai_operation annotation
echo -e "${BOLD}Fetching traces with gen_ai_operation...${NC}"

TRACE_IDS=$(aws xray get-trace-summaries \
    --start-time "$START_TIME" \
    --end-time "$END_TIME" \
    --filter-expression 'annotation.gen_ai_operation BEGINSWITH ""' \
    --query 'TraceSummaries[*].Id' \
    --output text 2>/dev/null)

if [ -z "$TRACE_IDS" ]; then
    echo -e "${YELLOW}No LLM traces found in the last ${MINUTES} minutes.${NC}"
    echo ""
    echo "Tips:"
    echo "  - Make sure the Lambda has been invoked recently"
    echo "  - X-Ray traces may take 1-2 minutes to appear"
    echo "  - Try increasing the time window: ./trace-llm.sh 30"
    exit 0
fi

# Convert to array
TRACE_ARRAY=($TRACE_IDS)
TRACE_COUNT=${#TRACE_ARRAY[@]}

echo -e "${GREEN}Found ${TRACE_COUNT} trace(s) with LLM operations${NC}"
echo ""

# Process each trace
for TRACE_ID in "${TRACE_ARRAY[@]}"; do
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Trace ID: ${TRACE_ID}${NC}"

    # Get full trace details
    TRACE_DATA=$(aws xray batch-get-traces \
        --trace-ids "$TRACE_ID" \
        --query 'Traces[0]' \
        --output json 2>/dev/null)

    if [ -z "$TRACE_DATA" ] || [ "$TRACE_DATA" == "null" ]; then
        echo -e "${YELLOW}  Could not fetch trace details${NC}"
        continue
    fi

    # Extract segments and find LLM subsegments
    echo "$TRACE_DATA" | jq -r '
        .Segments[]?.Document | fromjson |

        # Recursive function to find all subsegments
        def find_llm_subsegments:
            if .name and (.name | startswith("llm.")) then
                [.]
            else
                []
            end +
            if .subsegments then
                (.subsegments | map(find_llm_subsegments) | flatten)
            else
                []
            end;

        find_llm_subsegments[] |

        # Format output
        "\n  \u001b[1m\u001b[33m▶ " + .name + "\u001b[0m",
        "    ├─ Start: " + (.start_time | todate),
        "    ├─ Duration: " + ((.end_time - .start_time) * 1000 | floor | tostring) + "ms",

        # Annotations (operation type)
        (if .annotations then
            (.annotations | to_entries | map(
                "    ├─ " + .key + ": \u001b[36m" + (.value | tostring) + "\u001b[0m"
            ) | .[])
        else empty end),

        # Metadata (model, tokens, cypher, etc.)
        (if .metadata then
            (.metadata | to_entries | map(
                .value | to_entries | map(
                    if .key == "generated_cypher" then
                        "    ├─ " + .key + ":\n      \u001b[32m" + (.value | tostring | gsub("\n"; "\n      ")) + "\u001b[0m"
                    elif .key == "raw_response" or .key == "response_truncated" then
                        "    ├─ " + .key + ": " + (.value | tostring | .[0:100]) + "..."
                    elif (.key | test("tokens")) then
                        "    ├─ " + .key + ": \u001b[35m" + (.value | tostring) + "\u001b[0m"
                    elif .key == "cypher_valid" then
                        if .value then
                            "    ├─ " + .key + ": \u001b[32m✓ valid\u001b[0m"
                        else
                            "    ├─ " + .key + ": \u001b[31m✗ invalid\u001b[0m"
                        end
                    else
                        "    ├─ " + .key + ": " + (.value | tostring | .[0:200])
                    end
                ) | .[]
            ) | .[])
        else empty end),

        # Error info if present
        (if .fault or .error then
            "    └─ \u001b[31m⚠ ERROR: " + (.cause?.message // "Unknown error") + "\u001b[0m"
        else
            "    └─ ✓ Success"
        end)
    ' 2>/dev/null || echo -e "${YELLOW}  Could not parse trace segments${NC}"

    echo ""
done

echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}Summary: ${TRACE_COUNT} trace(s) processed${NC}"
echo ""
