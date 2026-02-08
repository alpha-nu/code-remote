#!/bin/bash
# scripts/resync-snippets.sh
# Trigger resync of snippets from PostgreSQL to Neo4j
#
# Usage:
#   ./scripts/resync-snippets.sh [options]
#
# Options:
#   --all           Resync all snippets (default: only analyzed)
#   --dry-run       Show what would be synced without syncing
#   --snippet-id    Resync a specific snippet by ID
#
# Examples:
#   ./scripts/resync-snippets.sh                    # Resync all analyzed snippets
#   ./scripts/resync-snippets.sh --dry-run          # Preview what would be synced
#   ./scripts/resync-snippets.sh --snippet-id abc   # Resync specific snippet

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"
PYTHON="$SCRIPT_DIR/../.venv/bin/python"

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${CYAN}ℹ${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }

# Parse arguments
DRY_RUN=false
ALL_SNIPPETS=false
SNIPPET_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --all)
            ALL_SNIPPETS=true
            shift
            ;;
        --snippet-id)
            SNIPPET_ID="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

cd "$BACKEND_DIR"

if [[ "$DRY_RUN" == "true" ]]; then
    log_info "DRY RUN - showing what would be synced..."
fi

# Convert booleans to Python format
if [[ "$DRY_RUN" == "true" ]]; then
    PY_DRY_RUN="True"
else
    PY_DRY_RUN="False"
fi

if [[ "$ALL_SNIPPETS" == "true" ]]; then
    PY_ALL_SNIPPETS="True"
else
    PY_ALL_SNIPPETS="False"
fi

"$PYTHON" << PYTHON_SCRIPT
import asyncio
import sys
from uuid import UUID

# Add backend to path
sys.path.insert(0, '.')

DRY_RUN = ${PY_DRY_RUN}
ALL_SNIPPETS = ${PY_ALL_SNIPPETS}
SNIPPET_ID = "${SNIPPET_ID}" or None

async def main():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    from api.models.snippet import Snippet
    from api.models.user import User
    from api.services.embedding_service import EmbeddingService
    from api.services.neo4j_service import Neo4jService, get_neo4j_driver
    from common.config import settings

    # Connect to PostgreSQL
    engine = create_async_engine(settings.resolved_database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Connect to Neo4j
    driver = get_neo4j_driver()
    if not driver:
        print("❌ Could not connect to Neo4j")
        return 1

    neo4j_service = Neo4jService(driver)
    embedding_service = EmbeddingService()

    async with async_session() as session:
        # Build query
        if SNIPPET_ID:
            query = select(Snippet, User).join(User, Snippet.user_id == User.id).where(Snippet.id == UUID(SNIPPET_ID))
        elif ALL_SNIPPETS:
            query = select(Snippet, User).join(User, Snippet.user_id == User.id)
        else:
            # Only snippets with complexity analysis
            query = select(Snippet, User).join(User, Snippet.user_id == User.id).where(Snippet.time_complexity.isnot(None))

        result = await session.execute(query)
        rows = result.all()

        print(f"Found {len(rows)} snippets to sync")
        print()

        if DRY_RUN:
            for snippet, user in rows:
                complexity = f"{snippet.time_complexity or 'N/A'} / {snippet.space_complexity or 'N/A'}"
                print(f"  📄 {snippet.title[:40]:<40} | {snippet.language:<10} | {complexity}")
            print()
            print("Run without --dry-run to actually sync")
            return 0

        # Perform sync
        success_count = 0
        error_count = 0

        for snippet, user in rows:
            try:
                print(f"Syncing: {snippet.title[:50]}...", end=" ", flush=True)

                # Build embedding input
                embedding_input = embedding_service.build_snippet_embedding_input(
                    title=snippet.title,
                    description=snippet.description,
                    time_complexity=snippet.time_complexity,
                    space_complexity=snippet.space_complexity,
                    code=snippet.code,
                )

                # Generate embedding (sync version)
                embedding = embedding_service.generate_embedding_sync(embedding_input)
                if not embedding:
                    print("❌ (embedding failed)")
                    error_count += 1
                    continue

                # Upsert to Neo4j
                neo4j_service.upsert_snippet(
                    snippet_id=str(snippet.id),
                    user_id=str(user.id),
                    title=snippet.title,
                    code=snippet.code,
                    language=snippet.language,
                    time_complexity=snippet.time_complexity or "O(?)",
                    space_complexity=snippet.space_complexity or "O(?)",
                    embedding=embedding,
                    description=snippet.description,
                )

                print("✓")
                success_count += 1

            except Exception as e:
                print(f"❌ ({e})")
                error_count += 1

        print()
        print(f"=== Sync Complete ===")
        print(f"  ✓ Success: {success_count}")
        print(f"  ✗ Errors:  {error_count}")

    driver.close()
    await engine.dispose()
    return 0 if error_count == 0 else 1

exit_code = asyncio.run(main())
sys.exit(exit_code)
PYTHON_SCRIPT

exit_code=$?

if [[ $exit_code -eq 0 ]]; then
    log_success "Resync completed successfully"
else
    log_error "Resync completed with errors"
fi

exit $exit_code
