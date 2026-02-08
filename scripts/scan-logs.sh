#!/bin/bash
# scripts/scan-logs.sh
# Scan AWS Lambda logs for debugging Code Remote issues
#
# Usage:
#   ./scripts/scan-logs.sh [command] [options]
#
# Commands:
#   errors [service] [minutes]  - Show errors from a service (default: all, 30min)
#   sync [minutes]              - Show sync worker activity
#   api [minutes]               - Show API Lambda activity
#   migrate [minutes]           - Show Neo4j migration logs
#   search [pattern] [minutes]  - Search all services for pattern
#   tail [service]              - Live tail a service's logs
#
# Services: api, sync, migrate, search (or 'all')
#
# Examples:
#   ./scripts/scan-logs.sh errors              # All errors in last 30min
#   ./scripts/scan-logs.sh errors sync 60      # Sync errors in last hour
#   ./scripts/scan-logs.sh sync                # Sync worker activity
#   ./scripts/scan-logs.sh search "python"     # Search for "python" in all logs
#   ./scripts/scan-logs.sh tail api            # Live tail API logs

set -e

# Configuration
REGION="${AWS_REGION:-us-east-1}"
ENV="${DEPLOY_ENV:-dev}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Get Lambda function names from Pulumi or environment
get_lambda_log_groups() {
    local pulumi_dir="$SCRIPT_DIR/../infra/pulumi"

    # Try to get from Pulumi stack outputs
    if [[ -d "$pulumi_dir" ]]; then
        local api_func=$(cd "$pulumi_dir" && pulumi stack output api_function_name 2>/dev/null || true)
        local sync_func=$(cd "$pulumi_dir" && pulumi stack output sync_worker_function_name 2>/dev/null || true)
        local migrate_func=$(cd "$pulumi_dir" && pulumi stack output neo4j_migrate_function_name 2>/dev/null || true)

        if [[ -n "$api_func" ]]; then
            API_LOG="/aws/lambda/$api_func"
        fi
        if [[ -n "$sync_func" ]]; then
            SYNC_LOG="/aws/lambda/$sync_func"
        fi
        if [[ -n "$migrate_func" ]]; then
            MIGRATE_LOG="/aws/lambda/$migrate_func"
        fi
    fi
}

# Log group names (can be overridden by environment or auto-detected from Pulumi)
API_LOG="${API_LOG:-}"
SYNC_LOG="${SYNC_LOG:-}"
MIGRATE_LOG="${MIGRATE_LOG:-}"
SEARCH_LOG="${SEARCH_LOG:-}"

# Auto-detect if not set
get_lambda_log_groups

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
log_info() { echo -e "${CYAN}ℹ${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }

get_log_group() {
    case "$1" in
        api)     echo "$API_LOG" ;;
        sync)    echo "$SYNC_LOG" ;;
        migrate) echo "$MIGRATE_LOG" ;;
        search)  echo "$SEARCH_LOG" ;;
        *)       echo "" ;;
    esac
}

# Validation
check_log_group() {
    local name="$1"
    local value="$2"
    if [[ -z "$value" ]]; then
        log_warn "$name log group not configured. Set ${name^^}_LOG env var or ensure Pulumi outputs are available."
        return 1
    fi
    return 0
}

# Command: errors
cmd_errors() {
    local service="${1:-all}"
    local minutes="${2:-30}"

    log_info "Scanning for errors in last ${minutes} minutes..."

    if [[ "$service" == "all" ]]; then
        log_groups=()
        [[ -n "$API_LOG" ]] && log_groups+=("$API_LOG")
        [[ -n "$SYNC_LOG" ]] && log_groups+=("$SYNC_LOG")
        [[ -n "$MIGRATE_LOG" ]] && log_groups+=("$MIGRATE_LOG")
        if [[ ${#log_groups[@]} -eq 0 ]]; then
            log_error "No log groups configured. Set API_LOG, SYNC_LOG, MIGRATE_LOG env vars."
            exit 1
        fi
    else
        log_group=$(get_log_group "$service")
        if [[ -z "$log_group" ]]; then
            log_error "Unknown service or unconfigured: $service"
            log_info "Set ${service^^}_LOG env var or ensure Pulumi is available"
            exit 1
        fi
        log_groups=("$log_group")
    fi

    for lg in "${log_groups[@]}"; do
        echo ""
        echo -e "${CYAN}=== $(basename "$lg") ===${NC}"
        aws logs tail "$lg" --since "${minutes}m" --format short 2>/dev/null \
            | grep -iE "error|exception|fail|traceback|critical" \
            | head -50 \
            || echo "  (no errors found)"
    done
}

# Command: sync
cmd_sync() {
    local minutes="${1:-30}"

    log_info "Sync worker activity (last ${minutes} minutes)..."
    echo ""

    # Summary stats
    echo -e "${CYAN}=== Summary ===${NC}"
    local total=$(aws logs tail "$SYNC_LOG" --since "${minutes}m" --format short 2>/dev/null | grep -c "Synced snippet" || echo 0)
    local errors=$(aws logs tail "$SYNC_LOG" --since "${minutes}m" --format short 2>/dev/null | grep -ciE "error|fail" || echo 0)
    echo "  Snippets synced: $total"
    echo "  Errors: $errors"

    echo ""
    echo -e "${CYAN}=== Recent Activity ===${NC}"
    aws logs tail "$SYNC_LOG" --since "${minutes}m" --format short 2>/dev/null \
        | grep -E "START|Synced|ERROR|embedding" \
        | tail -30
}

# Command: api
cmd_api() {
    local minutes="${1:-30}"

    log_info "API Lambda activity (last ${minutes} minutes)..."
    echo ""

    echo -e "${CYAN}=== Request Summary ===${NC}"
    aws logs tail "$API_LOG" --since "${minutes}m" --format short 2>/dev/null \
        | grep -E "REPORT|ERROR" \
        | tail -20

    echo ""
    echo -e "${CYAN}=== Errors ===${NC}"
    aws logs tail "$API_LOG" --since "${minutes}m" --format short 2>/dev/null \
        | grep -iE "error|exception|traceback" \
        | head -20 \
        || echo "  (no errors)"
}

# Command: migrate
cmd_migrate() {
    local minutes="${1:-60}"

    log_info "Neo4j migration logs (last ${minutes} minutes)..."
    echo ""

    aws logs tail "$MIGRATE_LOG" --since "${minutes}m" --format short 2>/dev/null \
        | tail -50
}

# Command: search
cmd_search() {
    local pattern="${1:-}"
    local minutes="${2:-30}"

    if [[ -z "$pattern" ]]; then
        log_error "Usage: scan-logs.sh search <pattern> [minutes]"
        exit 1
    fi

    log_info "Searching for '$pattern' in all services (last ${minutes} minutes)..."

    for lg in "$API_LOG" "$SYNC_LOG" "$MIGRATE_LOG"; do
        echo ""
        echo -e "${CYAN}=== $(basename "$lg") ===${NC}"
        aws logs tail "$lg" --since "${minutes}m" --format short 2>/dev/null \
            | grep -i "$pattern" \
            | head -20 \
            || echo "  (no matches)"
    done
}

# Command: tail
cmd_tail() {
    local service="${1:-api}"
    local log_group=$(get_log_group "$service")

    if [[ -z "$log_group" ]]; then
        log_error "Unknown service: $service"
        exit 1
    fi

    log_info "Tailing $service logs (Ctrl+C to stop)..."
    aws logs tail "$log_group" --follow --format short
}

# Command: neo4j-check
cmd_neo4j_check() {
    log_info "Checking Neo4j state via local Python..."

    cd "$(dirname "$0")/../backend"
    ../.venv/bin/python -c "
from api.services.neo4j_service import get_neo4j_driver, Neo4jService

driver = get_neo4j_driver()
if driver:
    svc = Neo4jService(driver)

    # Counts
    snippets = svc.execute_query('MATCH (s:Snippet) RETURN count(s) as cnt')[0]['cnt']
    complexities = svc.execute_query('MATCH (c:Complexity) RETURN count(c) as cnt')[0]['cnt']
    languages = svc.execute_query('MATCH (l:Language) RETURN count(l) as cnt')[0]['cnt']
    time_rels = svc.execute_query('MATCH ()-[r:HAS_TIME_COMPLEXITY]->() RETURN count(r) as cnt')[0]['cnt']
    space_rels = svc.execute_query('MATCH ()-[r:HAS_SPACE_COMPLEXITY]->() RETURN count(r) as cnt')[0]['cnt']

    print('=== Neo4j Node Counts ===')
    print(f'  Snippets:     {snippets}')
    print(f'  Complexities: {complexities}')
    print(f'  Languages:    {languages}')
    print()
    print('=== Relationship Counts ===')
    print(f'  HAS_TIME_COMPLEXITY:  {time_rels}')
    print(f'  HAS_SPACE_COMPLEXITY: {space_rels}')

    # Check for missing python
    python_lang = svc.execute_query(\"MATCH (l:Language {name: 'python'}) RETURN l.name\")
    if not python_lang:
        print()
        print('⚠️  WARNING: python Language node is MISSING!')

    driver.close()
else:
    print('❌ Could not connect to Neo4j')
"
}

# Help
show_help() {
    echo "Code Remote Log Scanner"
    echo ""
    echo "Usage: scan-logs.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  errors [service] [minutes]  - Show errors (default: all services, 30 min)"
    echo "  sync [minutes]              - Show sync worker activity"
    echo "  api [minutes]               - Show API Lambda activity"
    echo "  migrate [minutes]           - Show Neo4j migration logs"
    echo "  search <pattern> [minutes]  - Search all services for pattern"
    echo "  tail <service>              - Live tail a service's logs"
    echo "  neo4j-check                 - Check Neo4j database state"
    echo ""
    echo "Services: api, sync, migrate"
    echo ""
    echo "Examples:"
    echo "  scan-logs.sh errors              # All errors in last 30min"
    echo "  scan-logs.sh errors sync 60      # Sync errors in last hour"
    echo "  scan-logs.sh search Complexity   # Search for 'Complexity'"
    echo "  scan-logs.sh neo4j-check         # Check Neo4j state"
}

# Main
case "${1:-}" in
    errors)     cmd_errors "$2" "$3" ;;
    sync)       cmd_sync "$2" ;;
    api)        cmd_api "$2" ;;
    migrate)    cmd_migrate "$2" ;;
    search)     cmd_search "$2" "$3" ;;
    tail)       cmd_tail "$2" ;;
    neo4j-check) cmd_neo4j_check ;;
    help|--help|-h) show_help ;;
    *)
        if [[ -n "$1" ]]; then
            log_error "Unknown command: $1"
        fi
        show_help
        exit 1
        ;;
esac
