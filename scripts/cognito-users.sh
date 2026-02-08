#!/bin/bash
# scripts/cognito-users.sh
# Query AWS Cognito User Pool for user information
#
# Usage:
#   ./scripts/cognito-users.sh                    # List all users (id, email)
#   ./scripts/cognito-users.sh <user-id>          # Get specific user by sub (UUID)
#   ./scripts/cognito-users.sh --search <query>   # Search by email or name
#
# Examples:
#   ./scripts/cognito-users.sh
#   ./scripts/cognito-users.sh abc123-def456-...
#   ./scripts/cognito-users.sh --search john
#   ./scripts/cognito-users.sh --search @example.com

set -e

# Configuration - get from Pulumi or environment
USER_POOL_ID="${COGNITO_USER_POOL_ID:-}"
REGION="${AWS_REGION:-us-east-1}"

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

log_info() { echo -e "${CYAN}ℹ${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }

# Get User Pool ID from Pulumi if not set
get_user_pool_id() {
    if [[ -n "$USER_POOL_ID" ]]; then
        echo "$USER_POOL_ID"
        return
    fi

    # Try to get from Pulumi stack
    local stack_dir="$(dirname "$0")/../infra/pulumi"
    if [[ -d "$stack_dir" ]]; then
        local pool_id=$(cd "$stack_dir" && pulumi stack output cognito_user_pool_id 2>/dev/null || true)
        if [[ -n "$pool_id" ]]; then
            echo "$pool_id"
            return
        fi
    fi

    # Try backend .env
    local env_file="$(dirname "$0")/../backend/.env"
    if [[ -f "$env_file" ]]; then
        local pool_id=$(grep "^COGNITO_USER_POOL_ID=" "$env_file" | cut -d'=' -f2)
        if [[ -n "$pool_id" ]]; then
            echo "$pool_id"
            return
        fi
    fi

    echo ""
}

# Extract attribute value from user JSON
get_attr() {
    local json="$1"
    local attr="$2"
    echo "$json" | jq -r ".Attributes[] | select(.Name==\"$attr\") | .Value // empty" 2>/dev/null || echo ""
}

# Format user for display
format_user_line() {
    local user_json="$1"
    local sub=$(echo "$user_json" | jq -r '.Attributes[] | select(.Name=="sub") | .Value' 2>/dev/null)
    local email=$(echo "$user_json" | jq -r '.Attributes[] | select(.Name=="email") | .Value' 2>/dev/null)
    local status=$(echo "$user_json" | jq -r '.UserStatus' 2>/dev/null)
    local enabled=$(echo "$user_json" | jq -r '.Enabled' 2>/dev/null)

    # Status indicator
    local status_icon="✓"
    local status_color="$GREEN"
    if [[ "$enabled" != "true" ]]; then
        status_icon="✗"
        status_color="$RED"
    elif [[ "$status" == "UNCONFIRMED" ]]; then
        status_icon="○"
        status_color="$YELLOW"
    fi

    printf "${status_color}${status_icon}${NC} %-36s  %s\n" "$sub" "$email"
}

# List all users
cmd_list() {
    local pool_id=$(get_user_pool_id)
    if [[ -z "$pool_id" ]]; then
        log_error "COGNITO_USER_POOL_ID not set. Set it or run from project with Pulumi."
        exit 1
    fi

    log_info "Listing users from pool: ${DIM}$pool_id${NC}"
    echo ""
    printf "${DIM}%-38s  %s${NC}\n" "USER ID (sub)" "EMAIL"
    printf "${DIM}%-38s  %s${NC}\n" "--------------------------------------" "-----"

    # Get all users and format
    aws cognito-idp list-users \
        --user-pool-id "$pool_id" \
        --region "$REGION" \
        2>/dev/null | jq -r '
        .Users[] |
        {
            sub: (.Attributes[] | select(.Name=="sub") | .Value),
            email: (.Attributes[] | select(.Name=="email") | .Value),
            status: .UserStatus,
            enabled: .Enabled
        } |
        (if .enabled != true then "✗" elif .status == "UNCONFIRMED" then "○" else "✓" end) + " " + .sub + "  " + .email
    '

    local total=$(aws cognito-idp list-users \
        --user-pool-id "$pool_id" \
        --region "$REGION" \
        2>/dev/null | jq '.Users | length')

    echo ""
    log_info "Total: $total users"
}

# Get specific user by sub (UUID)
cmd_get_user() {
    local user_sub="$1"
    local pool_id=$(get_user_pool_id)

    if [[ -z "$pool_id" ]]; then
        log_error "COGNITO_USER_POOL_ID not set."
        exit 1
    fi

    log_info "Looking up user: $user_sub"
    echo ""

    # Search by sub attribute
    local result=$(aws cognito-idp list-users \
        --user-pool-id "$pool_id" \
        --region "$REGION" \
        --filter "sub = \"$user_sub\"" \
        2>/dev/null)

    local user=$(echo "$result" | jq -c '.Users[0]' 2>/dev/null)

    if [[ -z "$user" || "$user" == "null" ]]; then
        log_error "User not found: $user_sub"
        exit 1
    fi

    # Display detailed info
    echo -e "${CYAN}=== User Details ===${NC}"
    echo ""

    local username=$(echo "$user" | jq -r '.Username')
    local status=$(echo "$user" | jq -r '.UserStatus')
    local enabled=$(echo "$user" | jq -r '.Enabled')
    local created=$(echo "$user" | jq -r '.UserCreateDate')
    local modified=$(echo "$user" | jq -r '.UserLastModifiedDate')

    echo "  Username:     $username"
    echo "  Status:       $status"
    echo "  Enabled:      $enabled"
    echo "  Created:      $created"
    echo "  Modified:     $modified"
    echo ""

    echo -e "${CYAN}=== Attributes ===${NC}"
    echo ""
    echo "$user" | jq -r '.Attributes[] | "  \(.Name): \(.Value)"' 2>/dev/null
}

# Search users by email or name
cmd_search() {
    local query="$1"
    local pool_id=$(get_user_pool_id)

    if [[ -z "$pool_id" ]]; then
        log_error "COGNITO_USER_POOL_ID not set."
        exit 1
    fi

    if [[ -z "$query" ]]; then
        log_error "Search query required"
        exit 1
    fi

    log_info "Searching for: $query"
    echo ""
    printf "${DIM}%-38s  %s${NC}\n" "USER ID (sub)" "EMAIL"
    printf "${DIM}%-38s  %s${NC}\n" "--------------------------------------" "-----"

    local count=0

    # Search by email (contains)
    if [[ "$query" == *"@"* ]]; then
        # Email search - use prefix match
        local result=$(aws cognito-idp list-users \
            --user-pool-id "$pool_id" \
            --region "$REGION" \
            --filter "email ^= \"$query\"" \
            2>/dev/null)

        local users=$(echo "$result" | jq -c '.Users[]' 2>/dev/null)
        while IFS= read -r user; do
            if [[ -n "$user" ]]; then
                format_user_line "$user"
                ((count++))
            fi
        done <<< "$users"
    fi

    # Also search by username prefix
    local result=$(aws cognito-idp list-users \
        --user-pool-id "$pool_id" \
        --region "$REGION" \
        --filter "username ^= \"$query\"" \
        2>/dev/null || true)

    if [[ -n "$result" ]]; then
        local users=$(echo "$result" | jq -c '.Users[]' 2>/dev/null)
        while IFS= read -r user; do
            if [[ -n "$user" ]]; then
                # Check if we already showed this user (avoid duplicates)
                local sub=$(echo "$user" | jq -r '.Attributes[] | select(.Name=="sub") | .Value')
                format_user_line "$user"
                ((count++))
            fi
        done <<< "$users"
    fi

    # If no results with filters, do a full scan with local filtering
    if [[ $count -eq 0 ]]; then
        log_info "No exact matches, scanning all users..."

        local query_lower=$(echo "$query" | tr '[:upper:]' '[:lower:]')

        local all_result=$(aws cognito-idp list-users \
            --user-pool-id "$pool_id" \
            --region "$REGION" \
            2>/dev/null)

        local users=$(echo "$all_result" | jq -c '.Users[]' 2>/dev/null)
        while IFS= read -r user; do
            if [[ -n "$user" ]]; then
                local email=$(echo "$user" | jq -r '.Attributes[] | select(.Name=="email") | .Value' 2>/dev/null | tr '[:upper:]' '[:lower:]')
                local name=$(echo "$user" | jq -r '.Attributes[] | select(.Name=="name") | .Value' 2>/dev/null | tr '[:upper:]' '[:lower:]')
                local username=$(echo "$user" | jq -r '.Username' 2>/dev/null | tr '[:upper:]' '[:lower:]')

                # Case-insensitive search
                if [[ "$email" == *"$query_lower"* ]] || \
                   [[ "$name" == *"$query_lower"* ]] || \
                   [[ "$username" == *"$query_lower"* ]]; then
                    format_user_line "$user"
                    ((count++))
                fi
            fi
        done <<< "$users"
    fi

    echo ""
    if [[ $count -eq 0 ]]; then
        log_info "No users found matching: $query"
    else
        log_info "Found: $count users"
    fi
}

# Help
show_help() {
    echo "Cognito User Query Tool"
    echo ""
    echo "Usage:"
    echo "  cognito-users.sh                    List all users"
    echo "  cognito-users.sh <user-id>          Get user by sub (UUID)"
    echo "  cognito-users.sh --search <query>   Search by email/name"
    echo ""
    echo "Options:"
    echo "  --help, -h    Show this help"
    echo ""
    echo "Environment:"
    echo "  COGNITO_USER_POOL_ID   User pool ID (auto-detected from .env or Pulumi)"
    echo "  AWS_REGION             AWS region (default: us-east-1)"
    echo ""
    echo "Examples:"
    echo "  cognito-users.sh"
    echo "  cognito-users.sh 12345678-abcd-efgh-ijkl-123456789012"
    echo "  cognito-users.sh --search john@example.com"
    echo "  cognito-users.sh --search john"
}

# Check for jq
if ! command -v jq &> /dev/null; then
    log_error "jq is required but not installed. Install with: brew install jq"
    exit 1
fi

# Main
case "${1:-}" in
    --help|-h)
        show_help
        ;;
    --search|-s)
        cmd_search "$2"
        ;;
    "")
        cmd_list
        ;;
    *)
        # Check if it looks like a UUID
        if [[ "$1" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
            cmd_get_user "$1"
        else
            # Treat as search query
            cmd_search "$1"
        fi
        ;;
esac
