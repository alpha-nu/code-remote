#!/usr/bin/env python3
"""Benchmark Text-to-Cypher generation across Gemini models.

Compares response time, token usage, and query quality across different models.

Usage:
    python scripts/text-to-cypher-benchmark.py gemini-2.5-flash gemini-3-flash-preview
    python scripts/text-to-cypher-benchmark.py --list-models
    python scripts/text-to-cypher-benchmark.py gemini-2.5-flash --runs 3
"""

import argparse
import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Add backend to path for imports
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

# Get API key from environment
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not set in backend/.env")
    sys.exit(1)

PROMPT_PATH = BACKEND_DIR / "analyzer" / "prompts" / "text_to_cypher.txt"
LOG_FILE = SCRIPT_DIR / "text-to-cypher-benchmark.log"

# Global log file handle
_log_file = None


def init_log():
    """Initialize log file (overwrite on each run)."""
    global _log_file
    _log_file = open(LOG_FILE, "w")
    _log_file.write("Text-to-Cypher Benchmark Log\n")
    _log_file.write(f"Started: {datetime.now().isoformat()}\n")
    _log_file.write("=" * 80 + "\n\n")
    _log_file.flush()


def log_failure(
    model: str,
    query: str,
    category: str,
    error: Exception,
    raw_response: str | None = None,
):
    """Log a failure with full stack trace."""
    global _log_file
    if _log_file is None:
        return

    _log_file.write(f"\n{'=' * 80}\n")
    _log_file.write(f"FAILURE: {datetime.now().isoformat()}\n")
    _log_file.write(f"Model: {model}\n")
    _log_file.write(f"Category: {category}\n")
    _log_file.write(f"Query: {query}\n")
    _log_file.write(f"\nError: {error}\n")
    _log_file.write(f"\nStack Trace:\n{traceback.format_exc()}\n")
    if raw_response:
        _log_file.write(f"\nRaw Response:\n{raw_response}\n")
    _log_file.write("=" * 80 + "\n")
    _log_file.flush()


def log_invalid_cypher(
    model: str, query: str, category: str, raw_response: str, cypher: str | None
):
    """Log when Cypher extraction/validation fails."""
    global _log_file
    if _log_file is None:
        return

    _log_file.write(f"\n{'-' * 80}\n")
    _log_file.write(f"INVALID CYPHER: {datetime.now().isoformat()}\n")
    _log_file.write(f"Model: {model}\n")
    _log_file.write(f"Category: {category}\n")
    _log_file.write(f"Query: {query}\n")
    _log_file.write(f"\nRaw Response ({len(raw_response)} chars):\n{raw_response}\n")
    if cypher:
        _log_file.write(f"\nExtracted Cypher:\n{cypher}\n")
    else:
        _log_file.write("\nExtracted Cypher: None (extraction failed)\n")
    _log_file.write("-" * 80 + "\n")
    _log_file.flush()


def close_log():
    """Close log file."""
    global _log_file
    if _log_file:
        _log_file.write(f"\nCompleted: {datetime.now().isoformat()}\n")
        _log_file.close()
        _log_file = None


# Test queries organized by category
TEST_QUERIES = {
    "vector_search": [
        "find sorting algorithms",
        "search for binary tree implementations",
        "show me recursive functions",
    ],
    "complexity_filter": [
        "show me O(n^2) algorithms",
        "find O(1) constant time code",
        "algorithms with O(n log n) complexity",
    ],
    "performance_ordering": [
        "show me my worst performing code",
        "my fastest algorithms",
        "most efficient snippets",
    ],
    "language_filter": [
        "Python sorting algorithms",
        "JavaScript async functions",
    ],
    "aggregation": [
        "count snippets by complexity",
        "how many Python snippets do I have",
    ],
}


@dataclass
class QueryResult:
    """Result from a single query."""

    query: str
    category: str
    success: bool
    time_ms: float
    response_chars: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cypher: str | None = None
    error: str | None = None


@dataclass
class ModelStats:
    """Aggregated stats for a model."""

    model: str
    results: list[QueryResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_count if self.total_count > 0 else 0

    @property
    def avg_time_ms(self) -> float:
        successful = [r.time_ms for r in self.results if r.success]
        return mean(successful) if successful else 0

    @property
    def time_stdev(self) -> float:
        successful = [r.time_ms for r in self.results if r.success]
        return stdev(successful) if len(successful) > 1 else 0

    @property
    def avg_response_chars(self) -> float:
        successful = [r.response_chars for r in self.results if r.success]
        return mean(successful) if successful else 0

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.results if r.success)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.results if r.success)

    def category_stats(self, category: str) -> dict:
        """Get stats for a specific category."""
        cat_results = [r for r in self.results if r.category == category]
        successful = [r for r in cat_results if r.success]
        return {
            "success": len(successful),
            "total": len(cat_results),
            "avg_time_ms": mean([r.time_ms for r in successful]) if successful else 0,
        }


def extract_cypher(response: str) -> str | None:
    """Extract Cypher query from LLM response."""
    code_block_pattern = r"```(?:cypher)?\s*([\s\S]*?)```"
    match = re.search(code_block_pattern, response)
    if match:
        return match.group(1).strip()
    # Try raw response if no code block
    if response.strip().upper().startswith(("MATCH", "CALL", "WITH", "RETURN")):
        return response.strip()
    return None


def validate_cypher(cypher: str) -> bool:
    """Basic validation that Cypher looks reasonable."""
    cypher_upper = cypher.upper()
    # Must have RETURN or be a CALL
    if "RETURN" not in cypher_upper and not cypher_upper.startswith("CALL"):
        return False
    # Must reference user_id for security
    if "$user_id" not in cypher.lower():
        return False
    return True


def run_query(
    client: genai.Client,
    model: str,
    prompt_template: str,
    query: str,
    category: str,
) -> QueryResult:
    """Run a single query and return results."""
    prompt = prompt_template.format(user_query=query)
    start = time.perf_counter()

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=500,
            ),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        raw_text = response.text.strip() if response.text else ""

        # Get token counts
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0

        # Extract and validate Cypher
        cypher = extract_cypher(raw_text)
        is_valid = cypher is not None and validate_cypher(cypher)

        # Log invalid Cypher
        if not is_valid:
            log_invalid_cypher(model, query, category, raw_text, cypher)

        return QueryResult(
            query=query,
            category=category,
            success=is_valid,
            time_ms=elapsed_ms,
            response_chars=len(raw_text),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cypher=cypher,
            error=None if is_valid else "Invalid or missing Cypher",
        )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log_failure(model, query, category, e)
        return QueryResult(
            query=query,
            category=category,
            success=False,
            time_ms=elapsed_ms,
            error=str(e)[:100],
        )


def benchmark_model(
    model: str,
    categories: list[str] | None = None,
    runs: int = 1,
    verbose: bool = True,
) -> ModelStats:
    """Benchmark a model across all test queries."""
    client = genai.Client(api_key=API_KEY)
    prompt_template = PROMPT_PATH.read_text()

    stats = ModelStats(model=model)

    if verbose:
        print(f"\n{'=' * 70}")
        print(f"  Benchmarking: {model}")
        print(f"{'=' * 70}")

    # Filter categories if specified
    test_categories = categories or list(TEST_QUERIES.keys())

    for run in range(runs):
        if runs > 1 and verbose:
            print(f"\n--- Run {run + 1}/{runs} ---")

        for category in test_categories:
            if category not in TEST_QUERIES:
                print(f"  Warning: Unknown category '{category}', skipping")
                continue

            queries = TEST_QUERIES[category]

            if verbose:
                print(f"\n  [{category}]")

            for query in queries:
                result = run_query(client, model, prompt_template, query, category)
                stats.results.append(result)

                if verbose:
                    status = "✓" if result.success else "✗"
                    time_str = f"{result.time_ms:,.0f}ms"
                    tokens_str = f"{result.input_tokens}→{result.output_tokens}"
                    print(
                        f"    {status} {query[:45]:<45} {time_str:>8} {tokens_str:>12}"
                    )
                    if not result.success and result.error:
                        print(f"      └─ {result.error[:60]}")

    return stats


def print_comparison(all_stats: list[ModelStats]):
    """Print comparison summary table."""
    print("\n" + "=" * 80)
    print("  BENCHMARK SUMMARY")
    print("=" * 80)

    # Header
    print(
        f"\n  {'Model':<28} {'Success':>10} {'Avg Time':>12} {'Std Dev':>10} {'Tokens':>12}"
    )
    print("  " + "-" * 72)

    # Model rows
    for s in all_stats:
        success_str = f"{s.success_count}/{s.total_count} ({s.success_rate:.0%})"
        time_str = f"{s.avg_time_ms:,.0f}ms"
        stdev_str = f"±{s.time_stdev:,.0f}ms" if s.time_stdev > 0 else "-"
        tokens_str = f"{s.total_input_tokens}→{s.total_output_tokens}"
        print(
            f"  {s.model:<28} {success_str:>10} {time_str:>12} {stdev_str:>10} {tokens_str:>12}"
        )

    # Category breakdown
    print("\n  Category Breakdown:")
    print(f"  {'Category':<25}", end="")
    for s in all_stats:
        print(f" {s.model[:15]:>18}", end="")
    print()
    print("  " + "-" * (25 + 18 * len(all_stats)))

    for category in TEST_QUERIES.keys():
        print(f"  {category:<25}", end="")
        for s in all_stats:
            cat = s.category_stats(category)
            if cat["total"] > 0:
                print(
                    f" {cat['success']}/{cat['total']} @ {cat['avg_time_ms']:,.0f}ms",
                    end="",
                )
            else:
                print(f" {'N/A':>18}", end="")
        print()

    # Winner
    if len(all_stats) > 1:
        best = max(all_stats, key=lambda s: (s.success_rate, -s.avg_time_ms))
        print(f"\n  🏆 Recommended: {best.model}")
        print(f"     ({best.success_rate:.0%} success, {best.avg_time_ms:,.0f}ms avg)")


def list_models():
    """List available Gemini models."""
    client = genai.Client(api_key=API_KEY)
    print("\nAvailable Gemini Models:")
    print("-" * 40)
    for m in client.models.list():
        if "flash" in m.name or "pro" in m.name:
            # Clean up the name
            name = m.name.replace("models/", "")
            print(f"  {name}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Text-to-Cypher generation across Gemini models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s gemini-2.5-flash gemini-3-flash-preview
  %(prog)s gemini-2.5-flash --runs 3
  %(prog)s gemini-2.5-flash --categories vector_search complexity_filter
  %(prog)s --list-models
        """,
    )
    parser.add_argument("models", nargs="*", help="Gemini model names to benchmark")
    parser.add_argument(
        "--list-models", action="store_true", help="List available models"
    )
    parser.add_argument(
        "--runs", type=int, default=1, help="Number of runs per model (default: 1)"
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=list(TEST_QUERIES.keys()),
        help="Specific categories to test",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress per-query output"
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    if args.list_models:
        list_models()
        return

    if not args.models:
        parser.print_help()
        print("\nQuick start:")
        print("  python scripts/text-to-cypher-benchmark.py gemini-2.5-flash")
        return

    # Initialize log file
    init_log()
    print(f"  Logging failures to: {LOG_FILE}")

    all_stats = []
    for model in args.models:
        stats = benchmark_model(
            model,
            categories=args.categories,
            runs=args.runs,
            verbose=not args.quiet,
        )
        all_stats.append(stats)

    # Close log file
    close_log()

    if args.json:
        output = []
        for s in all_stats:
            output.append(
                {
                    "model": s.model,
                    "success_rate": s.success_rate,
                    "avg_time_ms": s.avg_time_ms,
                    "time_stdev": s.time_stdev,
                    "total_input_tokens": s.total_input_tokens,
                    "total_output_tokens": s.total_output_tokens,
                    "results": [
                        {
                            "query": r.query,
                            "category": r.category,
                            "success": r.success,
                            "time_ms": r.time_ms,
                            "cypher": r.cypher,
                            "error": r.error,
                        }
                        for r in s.results
                    ],
                }
            )
        print(json.dumps(output, indent=2))
    else:
        print_comparison(all_stats)


if __name__ == "__main__":
    main()
