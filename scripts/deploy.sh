#!/bin/bash
# deploy.sh - Deploy Code Remote to AWS
#
# Usage:
#   ./deploy.sh [environment]   # Deploy everything (default: dev)
#   ./deploy.sh dev --api-only  # Deploy only the API
#   ./deploy.sh dev --frontend-only  # Deploy only the frontend
#
# Prerequisites:
#   - AWS CLI configured with credentials
#   - Docker running
#   - Pulumi CLI installed and logged in
#   - Node.js and npm installed (for frontend)

set -e  # Exit on error

# Configuration
ENVIRONMENT="${1:-dev}"
REGION="us-east-1"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    command -v aws >/dev/null 2>&1 || { log_error "AWS CLI not found. Install it first."; exit 1; }
    command -v docker >/dev/null 2>&1 || { log_error "Docker not found. Install it first."; exit 1; }
    command -v pulumi >/dev/null 2>&1 || { log_error "Pulumi not found. Install it first."; exit 1; }

    # Check AWS credentials
    aws sts get-caller-identity >/dev/null 2>&1 || { log_error "AWS credentials not configured."; exit 1; }

    # Check Docker daemon
    docker info >/dev/null 2>&1 || { log_error "Docker daemon not running."; exit 1; }

    log_info "All prerequisites met."
}

# Get Pulumi outputs
get_pulumi_outputs() {
    log_info "Getting Pulumi stack outputs..."
    cd "$PROJECT_ROOT/infra/pulumi"

    # Select the stack
    pulumi stack select "$ENVIRONMENT" 2>/dev/null || {
        log_warn "Stack '$ENVIRONMENT' not found. Creating it..."
        pulumi stack init "$ENVIRONMENT"
        pulumi config set aws:region "$REGION"
    }

    # Get outputs
    ECR_API_URL=$(pulumi stack output ecr_api_repository_url 2>/dev/null || echo "")
    FRONTEND_BUCKET=$(pulumi stack output frontend_bucket_name 2>/dev/null || echo "")
    DISTRIBUTION_ID=$(pulumi stack output frontend_distribution_id 2>/dev/null || echo "")
    API_ENDPOINT=$(pulumi stack output api_endpoint 2>/dev/null || echo "")
}

# Deploy infrastructure first (creates ECR repos, etc.)
deploy_infrastructure() {
    log_info "Deploying infrastructure with Pulumi..."
    cd "$PROJECT_ROOT/infra/pulumi"

    # Activate Python venv if it exists
    if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"
    fi

    pulumi up --yes --stack "$ENVIRONMENT"

    # Refresh outputs after deployment
    get_pulumi_outputs
}

# Build and push API Lambda container
build_and_push_api() {
    if [ -z "$ECR_API_URL" ]; then
        log_error "ECR API repository URL not found. Run infrastructure deployment first."
        exit 1
    fi

    log_info "Building API Lambda container..."
    cd "$PROJECT_ROOT/backend"

    # Login to ECR
    aws ecr get-login-password --region "$REGION" | \
        docker login --username AWS --password-stdin "${ECR_API_URL%%/*}"

    # Build the Lambda container
    docker build -f Dockerfile.lambda -t "${ECR_API_URL}:latest" .

    # Tag with git commit for versioning
    GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    docker tag "${ECR_API_URL}:latest" "${ECR_API_URL}:${GIT_SHA}"

    log_info "Pushing API container to ECR..."
    docker push "${ECR_API_URL}:latest"
    docker push "${ECR_API_URL}:${GIT_SHA}"

    log_info "API container pushed: ${ECR_API_URL}:latest"
}

# Build and push Executor container
build_and_push_executor() {
    if [ -z "$ECR_EXECUTOR_URL" ]; then
        log_error "ECR Executor repository URL not found. Run infrastructure deployment first."
        exit 1
    fi

    log_info "Building Executor container..."
    cd "$PROJECT_ROOT/backend"

    # Login to ECR
    aws ecr get-login-password --region "$REGION" | \
        docker login --username AWS --password-stdin "${ECR_EXECUTOR_URL%%/*}"

    # Build the Executor container
    docker build -f Dockerfile.executor -t "${ECR_EXECUTOR_URL}:latest" .

    # Tag with git commit
    GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    docker tag "${ECR_EXECUTOR_URL}:latest" "${ECR_EXECUTOR_URL}:${GIT_SHA}"

    log_info "Pushing Executor container to ECR..."
    docker push "${ECR_EXECUTOR_URL}:latest"
    docker push "${ECR_EXECUTOR_URL}:${GIT_SHA}"

    log_info "Executor container pushed: ${ECR_EXECUTOR_URL}:latest"
}

# Update Lambda function to use new image
update_lambda() {
    log_info "Updating Lambda function..."

    FUNCTION_NAME=$(cd "$PROJECT_ROOT/infra/pulumi" && pulumi stack output api_function_name 2>/dev/null || echo "")

    if [ -z "$FUNCTION_NAME" ]; then
        log_warn "Lambda function not found. It will be created on next Pulumi deployment."
        return
    fi

    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --image-uri "${ECR_API_URL}:latest" \
        --region "$REGION" >/dev/null

    log_info "Lambda function updated."
}

# Build and deploy frontend
deploy_frontend() {
    if [ -z "$FRONTEND_BUCKET" ]; then
        log_error "Frontend bucket not found. Run infrastructure deployment first."
        exit 1
    fi

    log_info "Building frontend..."
    cd "$PROJECT_ROOT/frontend"

    # Install dependencies if needed
    [ -d "node_modules" ] || npm install

    # Get API endpoint for environment file
    if [ -n "$API_ENDPOINT" ]; then
        echo "VITE_API_URL=$API_ENDPOINT" > .env.production.local

        # Get Cognito config
        COGNITO_POOL_ID=$(cd "$PROJECT_ROOT/infra/pulumi" && pulumi stack output cognito_user_pool_id)
        COGNITO_CLIENT_ID=$(cd "$PROJECT_ROOT/infra/pulumi" && pulumi stack output cognito_user_pool_client_id)

        cat >> .env.production.local <<EOF
VITE_COGNITO_USER_POOL_ID=$COGNITO_POOL_ID
VITE_COGNITO_CLIENT_ID=$COGNITO_CLIENT_ID
VITE_COGNITO_REGION=$REGION

EOF
    fi

    # Build
    npm run build

    log_info "Deploying frontend to S3..."
    aws s3 sync dist/ "s3://${FRONTEND_BUCKET}/" --delete

    # Invalidate CloudFront cache
    if [ -n "$DISTRIBUTION_ID" ]; then
        log_info "Invalidating CloudFront cache..."
        aws cloudfront create-invalidation \
            --distribution-id "$DISTRIBUTION_ID" \
            --paths "/*" >/dev/null
    fi

    FRONTEND_URL=$(cd "$PROJECT_ROOT/infra/pulumi" && pulumi stack output frontend_url 2>/dev/null || echo "")
    log_info "Frontend deployed: $FRONTEND_URL"
}

# Print deployment summary
print_summary() {
    echo ""
    log_info "=========================================="
    log_info "Deployment Complete!"
    log_info "=========================================="
    echo ""

    cd "$PROJECT_ROOT/infra/pulumi"

    API_ENDPOINT=$(pulumi stack output api_endpoint 2>/dev/null || echo "N/A")
    FRONTEND_URL=$(pulumi stack output frontend_url 2>/dev/null || echo "N/A")

    echo "Environment: $ENVIRONMENT"
    echo "API Endpoint: $API_ENDPOINT"
    echo "Frontend URL: $FRONTEND_URL"
    echo ""
    echo "Test the API:"
    echo "  curl $API_ENDPOINT/health"
    echo ""
}

# Main deployment flow
main() {
    echo ""
    log_info "Starting deployment for environment: $ENVIRONMENT"
    echo ""

    check_prerequisites

    # Parse flags
    API_ONLY=false
    FRONTEND_ONLY=false
    INFRA_ONLY=false

    for arg in "$@"; do
        case $arg in
            --api-only) API_ONLY=true ;;
            --frontend-only) FRONTEND_ONLY=true ;;
            --infra-only) INFRA_ONLY=true ;;
        esac
    done

    # Get existing outputs first
    get_pulumi_outputs

    if [ "$FRONTEND_ONLY" = true ]; then
        deploy_frontend
        print_summary
        exit 0
    fi

    if [ "$API_ONLY" = true ]; then
        build_and_push_api
        update_lambda
        print_summary
        exit 0
    fi

    if [ "$INFRA_ONLY" = true ]; then
        deploy_infrastructure
        print_summary
        exit 0
    fi

    # Full deployment
    deploy_infrastructure
    build_and_push_api
    build_and_push_executor
    update_lambda
    deploy_frontend

    print_summary
}

main "$@"
