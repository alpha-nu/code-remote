#!/usr/bin/env python3
"""Seed snippets with varying complexities for testing.

Usage:
    python scripts/seed_snippets.py --api-url https://api.example.com --username user --password pass

    # Or with environment variables:
    API_URL=https://api.example.com USERNAME=user PASSWORD=pass python scripts/seed_snippets.py
"""

import argparse
import os
import sys
import time

import httpx

# Snippets organized by complexity category
SNIPPETS = [
    # O(1) - Constant time/space
    {
        "title": "Array element access",
        "code": """def get_first(arr):
    \"\"\"O(1) time, O(1) space - direct index access.\"\"\"
    if not arr:
        return None
    return arr[0]

# Test
print(get_first([10, 20, 30]))  # 10
""",
        "description": "Direct array index access - constant time complexity",
    },
    {
        "title": "Hash table lookup",
        "code": """def get_value(data, key):
    \"\"\"O(1) average time, O(1) space - hash lookup.\"\"\"
    return data.get(key, "not found")

# Test
cache = {"user_1": "Alice", "user_2": "Bob"}
print(get_value(cache, "user_1"))  # Alice
""",
        "description": "Dictionary/hash map lookup operation",
    },
    {
        "title": "Stack push/pop",
        "code": """def stack_operations():
    \"\"\"O(1) time for push/pop, O(n) space for stack.\"\"\"
    stack = []
    stack.append(1)  # O(1)
    stack.append(2)  # O(1)
    stack.append(3)  # O(1)
    return stack.pop()  # O(1)

print(stack_operations())  # 3
""",
        "description": "Stack push and pop are constant time operations",
    },
    # O(log n) - Logarithmic
    {
        "title": "Binary search",
        "code": """def binary_search(arr, target):
    \"\"\"O(log n) time, O(1) space - classic binary search.\"\"\"
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

# Test
sorted_arr = [1, 3, 5, 7, 9, 11, 13, 15]
print(binary_search(sorted_arr, 7))  # 3
""",
        "description": "Binary search halves the search space each iteration",
    },
    {
        "title": "Binary search recursive",
        "code": """def binary_search_recursive(arr, target, left, right):
    \"\"\"O(log n) time, O(log n) space (call stack).\"\"\"
    if left > right:
        return -1
    mid = (left + right) // 2
    if arr[mid] == target:
        return mid
    elif arr[mid] < target:
        return binary_search_recursive(arr, target, mid + 1, right)
    else:
        return binary_search_recursive(arr, target, left, mid - 1)

arr = [2, 4, 6, 8, 10, 12]
print(binary_search_recursive(arr, 8, 0, len(arr) - 1))  # 3
""",
        "description": "Recursive binary search uses O(log n) stack space",
    },
    # O(n) - Linear
    {
        "title": "Linear search",
        "code": """def linear_search(arr, target):
    \"\"\"O(n) time, O(1) space - check each element.\"\"\"
    for i, val in enumerate(arr):
        if val == target:
            return i
    return -1

# Test
print(linear_search([4, 2, 7, 1, 9], 7))  # 2
""",
        "description": "Linear search checks each element once",
    },
    {
        "title": "Find maximum",
        "code": """def find_max(arr):
    \"\"\"O(n) time, O(1) space - single pass.\"\"\"
    if not arr:
        return None
    max_val = arr[0]
    for val in arr[1:]:
        if val > max_val:
            max_val = val
    return max_val

print(find_max([3, 1, 4, 1, 5, 9, 2, 6]))  # 9
""",
        "description": "Finding maximum requires checking every element",
    },
    {
        "title": "Two sum with hash map",
        "code": """def two_sum(nums, target):
    \"\"\"O(n) time, O(n) space - hash map approach.\"\"\"
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

print(two_sum([2, 7, 11, 15], 9))  # [0, 1]
""",
        "description": "Hash map trades space for time - O(n) both",
    },
    {
        "title": "Reverse array in place",
        "code": """def reverse_in_place(arr):
    \"\"\"O(n) time, O(1) space - two pointer swap.\"\"\"
    left, right = 0, len(arr) - 1
    while left < right:
        arr[left], arr[right] = arr[right], arr[left]
        left += 1
        right -= 1
    return arr

print(reverse_in_place([1, 2, 3, 4, 5]))  # [5, 4, 3, 2, 1]
""",
        "description": "In-place reversal uses constant extra space",
    },
    {
        "title": "Count frequency",
        "code": """from collections import Counter

def count_frequency(items):
    \"\"\"O(n) time, O(k) space where k = unique items.\"\"\"
    return dict(Counter(items))

chars = "mississippi"
print(count_frequency(chars))
""",
        "description": "Counting frequencies is linear time",
    },
    # O(n log n) - Linearithmic
    {
        "title": "Merge sort",
        "code": """def merge_sort(arr):
    \"\"\"O(n log n) time, O(n) space - divide and conquer.\"\"\"
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)

def merge(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result

print(merge_sort([38, 27, 43, 3, 9, 82, 10]))
""",
        "description": "Merge sort - stable O(n log n) with O(n) space",
    },
    {
        "title": "Quick sort",
        "code": """def quicksort(arr):
    \"\"\"O(n log n) average, O(n²) worst, O(log n) space.\"\"\"
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

print(quicksort([3, 6, 8, 10, 1, 2, 1]))
""",
        "description": "Quick sort - average O(n log n), worst O(n²)",
    },
    {
        "title": "Heap sort",
        "code": """import heapq

def heap_sort(arr):
    \"\"\"O(n log n) time, O(n) space - heap-based sort.\"\"\"
    heapq.heapify(arr)  # O(n)
    return [heapq.heappop(arr) for _ in range(len(arr))]  # O(n log n)

print(heap_sort([4, 1, 3, 2, 16, 9, 10, 14, 8, 7]))
""",
        "description": "Heap sort using Python's heapq module",
    },
    # O(n²) - Quadratic
    {
        "title": "Bubble sort",
        "code": """def bubble_sort(arr):
    \"\"\"O(n²) time, O(1) space - nested loops with swaps.\"\"\"
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

print(bubble_sort([64, 34, 25, 12, 22, 11, 90]))
""",
        "description": "Bubble sort - simple but O(n²) time",
    },
    {
        "title": "Selection sort",
        "code": """def selection_sort(arr):
    \"\"\"O(n²) time, O(1) space - find min repeatedly.\"\"\"
    n = len(arr)
    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            if arr[j] < arr[min_idx]:
                min_idx = j
        arr[i], arr[min_idx] = arr[min_idx], arr[i]
    return arr

print(selection_sort([64, 25, 12, 22, 11]))
""",
        "description": "Selection sort - O(n²) comparisons, O(n) swaps",
    },
    {
        "title": "Two sum brute force",
        "code": """def two_sum_brute(nums, target):
    \"\"\"O(n²) time, O(1) space - check all pairs.\"\"\"
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if nums[i] + nums[j] == target:
                return [i, j]
    return []

print(two_sum_brute([2, 7, 11, 15], 9))  # [0, 1]
""",
        "description": "Brute force two sum - compare every pair",
    },
    {
        "title": "Matrix multiplication naive",
        "code": """def matrix_multiply(A, B):
    \"\"\"O(n³) time for n×n matrices, O(n²) space for result.\"\"\"
    n = len(A)
    result = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            for k in range(n):
                result[i][j] += A[i][k] * B[k][j]
    return result

A = [[1, 2], [3, 4]]
B = [[5, 6], [7, 8]]
print(matrix_multiply(A, B))  # [[19, 22], [43, 50]]
""",
        "description": "Naive matrix multiplication is O(n³)",
    },
    # O(2^n) - Exponential
    {
        "title": "Fibonacci recursive",
        "code": """def fib_recursive(n):
    \"\"\"O(2^n) time, O(n) space (call stack) - naive recursion.\"\"\"
    if n <= 1:
        return n
    return fib_recursive(n - 1) + fib_recursive(n - 2)

# Only test with small n due to exponential time
for i in range(10):
    print(fib_recursive(i), end=" ")
""",
        "description": "Naive recursive Fibonacci has exponential time complexity",
    },
    {
        "title": "Fibonacci memoized",
        "code": """from functools import lru_cache

@lru_cache(maxsize=None)
def fib_memo(n):
    \"\"\"O(n) time, O(n) space - memoization.\"\"\"
    if n <= 1:
        return n
    return fib_memo(n - 1) + fib_memo(n - 2)

print(fib_memo(30))  # 832040 - fast with memoization
""",
        "description": "Memoized Fibonacci reduces to O(n) time",
    },
    {
        "title": "Power set generation",
        "code": """def power_set(items):
    \"\"\"O(2^n) time and space - all subsets.\"\"\"
    result = [[]]
    for item in items:
        result += [subset + [item] for subset in result]
    return result

print(power_set([1, 2, 3]))
# [[], [1], [2], [1, 2], [3], [1, 3], [2, 3], [1, 2, 3]]
""",
        "description": "Power set has 2^n subsets",
    },
    # O(n!) - Factorial
    {
        "title": "Permutations",
        "code": """from itertools import permutations

def all_permutations(items):
    \"\"\"O(n!) time and space - all orderings.\"\"\"
    return list(permutations(items))

result = all_permutations([1, 2, 3])
print(f"Count: {len(result)}")  # 6 = 3!
for p in result:
    print(p)
""",
        "description": "Generating all permutations is O(n!)",
    },
    # Special/Mixed complexity
    {
        "title": "Sliding window maximum",
        "code": """from collections import deque

def max_sliding_window(nums, k):
    \"\"\"O(n) time, O(k) space - monotonic deque.\"\"\"
    result = []
    dq = deque()  # stores indices

    for i, num in enumerate(nums):
        # Remove indices outside window
        while dq and dq[0] < i - k + 1:
            dq.popleft()
        # Remove smaller elements
        while dq and nums[dq[-1]] < num:
            dq.pop()
        dq.append(i)
        if i >= k - 1:
            result.append(nums[dq[0]])
    return result

print(max_sliding_window([1, 3, -1, -3, 5, 3, 6, 7], 3))
""",
        "description": "Sliding window with monotonic deque - O(n) time",
    },
    {
        "title": "LRU Cache",
        "code": """from collections import OrderedDict

class LRUCache:
    \"\"\"O(1) get/put, O(capacity) space.\"\"\"
    def __init__(self, capacity):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key):
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
print(cache.get(1))  # 1
cache.put(3, 3)      # evicts key 2
print(cache.get(2))  # -1
""",
        "description": "LRU Cache with O(1) operations using OrderedDict",
    },
    {
        "title": "BFS graph traversal",
        "code": """from collections import deque

def bfs(graph, start):
    \"\"\"O(V + E) time, O(V) space - level-order traversal.\"\"\"
    visited = set()
    queue = deque([start])
    result = []

    while queue:
        node = queue.popleft()
        if node not in visited:
            visited.add(node)
            result.append(node)
            queue.extend(n for n in graph[node] if n not in visited)
    return result

graph = {
    'A': ['B', 'C'],
    'B': ['A', 'D', 'E'],
    'C': ['A', 'F'],
    'D': ['B'],
    'E': ['B', 'F'],
    'F': ['C', 'E']
}
print(bfs(graph, 'A'))  # ['A', 'B', 'C', 'D', 'E', 'F']
""",
        "description": "BFS visits each vertex and edge once - O(V+E)",
    },
    {
        "title": "DFS graph traversal",
        "code": """def dfs(graph, start, visited=None):
    \"\"\"O(V + E) time, O(V) space - depth-first traversal.\"\"\"
    if visited is None:
        visited = set()
    visited.add(start)
    result = [start]
    for neighbor in graph[start]:
        if neighbor not in visited:
            result.extend(dfs(graph, neighbor, visited))
    return result

graph = {
    'A': ['B', 'C'],
    'B': ['A', 'D', 'E'],
    'C': ['A', 'F'],
    'D': ['B'],
    'E': ['B', 'F'],
    'F': ['C', 'E']
}
print(dfs(graph, 'A'))
""",
        "description": "DFS recursive traversal - O(V+E) time, O(V) stack space",
    },
    {
        "title": "Dynamic programming - coin change",
        "code": """def coin_change(coins, amount):
    \"\"\"O(amount * len(coins)) time, O(amount) space.\"\"\"
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0

    for coin in coins:
        for x in range(coin, amount + 1):
            dp[x] = min(dp[x], dp[x - coin] + 1)

    return dp[amount] if dp[amount] != float('inf') else -1

print(coin_change([1, 2, 5], 11))  # 3 (5+5+1)
print(coin_change([2], 3))         # -1 (impossible)
""",
        "description": "DP coin change - pseudo-polynomial O(amount × coins)",
    },
    {
        "title": "Kadane's algorithm - max subarray",
        "code": """def max_subarray(nums):
    \"\"\"O(n) time, O(1) space - Kadane's algorithm.\"\"\"
    max_sum = current_sum = nums[0]
    for num in nums[1:]:
        current_sum = max(num, current_sum + num)
        max_sum = max(max_sum, current_sum)
    return max_sum

print(max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]))  # 6
""",
        "description": "Kadane's algorithm finds max subarray in O(n)",
    },
]


def get_auth_token(api_url: str, username: str, password: str) -> str:
    """Authenticate and get JWT token."""
    # Try Cognito-style auth endpoint
    auth_url = f"{api_url.rstrip('/')}/auth/login"

    try:
        response = httpx.post(
            auth_url,
            json={"username": username, "password": password},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("access_token") or data.get("token") or data.get("id_token")
    except httpx.HTTPStatusError as e:
        print(f"Auth failed: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"Auth error: {e}")
        sys.exit(1)


def create_snippet(api_url: str, token: str, snippet: dict) -> dict | None:
    """Create a snippet via the API."""
    url = f"{api_url.rstrip('/')}/snippets"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = httpx.post(
            url,
            json=snippet,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"  Failed: {e.response.status_code} - {e.response.text[:100]}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def analyze_snippet(
    api_url: str,
    token: str,
    snippet_id: str,
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> dict | None:
    """Trigger complexity analysis for a snippet with exponential backoff."""
    url = f"{api_url.rstrip('/')}/analyze"
    headers = {"Authorization": f"Bearer {token}"}

    for attempt in range(max_retries):
        try:
            # Get snippet code first
            snippet_resp = httpx.get(
                f"{api_url.rstrip('/')}/snippets/{snippet_id}",
                headers=headers,
                timeout=30,
            )
            snippet_resp.raise_for_status()
            code = snippet_resp.json().get("code", "")

            # Analyze
            response = httpx.post(
                url,
                json={"code": code, "snippet_id": snippet_id},
                headers=headers,
                timeout=60,
            )

            # Check for rate limiting (429) or server errors (5xx)
            if response.status_code == 429 or response.status_code >= 500:
                delay = base_delay * (2**attempt)
                if attempt < max_retries - 1:
                    print(f"rate limited, retrying in {delay:.1f}s...", end=" ")
                    time.sleep(delay)
                    continue
                else:
                    print(f"failed after {max_retries} attempts")
                    return None

            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException:
            delay = base_delay * (2**attempt)
            if attempt < max_retries - 1:
                print(f"timeout, retrying in {delay:.1f}s...", end=" ")
                time.sleep(delay)
                continue
            else:
                print(f"timeout after {max_retries} attempts")
                return None
        except Exception as e:
            print(f"error: {e}")
            return None

    return None


def main():
    parser = argparse.ArgumentParser(description="Seed snippets for testing")
    parser.add_argument(
        "--api-url", default=os.environ.get("API_URL"), help="API base URL"
    )
    parser.add_argument(
        "--username", default=os.environ.get("USERNAME"), help="Username"
    )
    parser.add_argument(
        "--password", default=os.environ.get("PASSWORD"), help="Password"
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("AUTH_TOKEN"),
        help="Pre-authenticated token (skip login)",
    )
    parser.add_argument(
        "--analyze", action="store_true", help="Trigger LLM analysis for each snippet"
    )
    parser.add_argument(
        "--delay", type=float, default=0.5, help="Delay between requests (seconds)"
    )
    parser.add_argument(
        "--analyze-delay",
        type=float,
        default=1.0,
        help="Delay before each LLM analysis (seconds)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print snippets without creating"
    )

    args = parser.parse_args()

    if not args.api_url:
        print("Error: --api-url or API_URL environment variable required")
        sys.exit(1)

    if args.dry_run:
        print(f"DRY RUN - Would create {len(SNIPPETS)} snippets:\n")
        for i, s in enumerate(SNIPPETS, 1):
            print(f"{i:2}. {s['title']}")
            print(f"    {s['description']}")
        sys.exit(0)

    # Get auth token
    token = args.token
    if not token:
        if not args.username or not args.password:
            print("Error: --username and --password (or --token) required")
            sys.exit(1)
        print(f"Authenticating as {args.username}...")
        token = get_auth_token(args.api_url, args.username, args.password)

    print(f"\nSeeding {len(SNIPPETS)} snippets to {args.api_url}\n")

    created = 0
    analyzed = 0

    for i, snippet in enumerate(SNIPPETS, 1):
        print(f"[{i:2}/{len(SNIPPETS)}] {snippet['title']}...", end=" ")

        result = create_snippet(args.api_url, token, snippet)
        if result:
            print(f"✓ id={result.get('id', 'unknown')}")
            created += 1

            if args.analyze and result.get("id"):
                # Delay before analysis to avoid rate limiting
                if args.analyze_delay:
                    time.sleep(args.analyze_delay)
                print("       Analyzing...", end=" ")
                analysis = analyze_snippet(args.api_url, token, result["id"])
                if analysis:
                    tc = analysis.get("time_complexity", "?")
                    sc = analysis.get("space_complexity", "?")
                    print(f"✓ Time: {tc}, Space: {sc}")
                    analyzed += 1
                else:
                    print("✗")
        else:
            print("✗")

        if args.delay and i < len(SNIPPETS):
            time.sleep(args.delay)

    print(f"\nDone: {created}/{len(SNIPPETS)} created", end="")
    if args.analyze:
        print(f", {analyzed}/{created} analyzed")
    else:
        print()


if __name__ == "__main__":
    main()


# # Dry run - list snippets without creating
# python scripts/seed_snippets.py --api-url https://api.example.com --dry-run

# # Create snippets
# python scripts/seed_snippets.py --api-url https://api.example.com --token YOUR_JWT

# # Create and analyze (triggers LLM complexity analysis)
# python scripts/seed_snippets.py --api-url https://api.example.com --token YOUR_JWT --analyze

# # With username/password auth
# python scripts/seed_snippets.py --api-url https://api.example.com --username user --password pass
