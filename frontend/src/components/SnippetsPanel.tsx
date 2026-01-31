/**
 * SnippetsPanel - Collapsible sidebar for viewing code snippets
 */

import { useState, useEffect } from 'react';
import './SnippetsPanel.css';

// Mock snippet data for prototype
interface Snippet {
  id: string;
  name: string;
  description?: string;
  code: string;
  language: string;
  timeComplexity?: string;
  spaceComplexity?: string;
  isStarred: boolean;
  createdAt: string;
}

const MOCK_SNIPPETS: Snippet[] = [
  {
    id: '1',
    name: 'Binary Search',
    description: 'Classic binary search implementation',
    code: 'def binary_search(arr, target):\n    left, right = 0, len(arr) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1',
    language: 'python',
    timeComplexity: 'O(log n)',
    spaceComplexity: 'O(1)',
    isStarred: true,
    createdAt: '2026-01-30T10:30:00Z',
  },
  {
    id: '2',
    name: 'Fibonacci Memoization',
    description: 'Dynamic programming approach to Fibonacci',
    code: 'def fib(n, memo={}):\n    if n in memo:\n        return memo[n]\n    if n <= 1:\n        return n\n    memo[n] = fib(n-1, memo) + fib(n-2, memo)\n    return memo[n]',
    language: 'python',
    timeComplexity: 'O(n)',
    spaceComplexity: 'O(n)',
    isStarred: false,
    createdAt: '2026-01-29T15:20:00Z',
  },
  {
    id: '3',
    name: 'Merge Sort',
    description: 'Divide and conquer sorting algorithm',
    code: 'def merge_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    mid = len(arr) // 2\n    left = merge_sort(arr[:mid])\n    right = merge_sort(arr[mid:])\n    return merge(left, right)\n\ndef merge(left, right):\n    result = []\n    i = j = 0\n    while i < len(left) and j < len(right):\n        if left[i] <= right[j]:\n            result.append(left[i])\n            i += 1\n        else:\n            result.append(right[j])\n            j += 1\n    result.extend(left[i:])\n    result.extend(right[j:])\n    return result',
    language: 'python',
    timeComplexity: 'O(n log n)',
    spaceComplexity: 'O(n)',
    isStarred: true,
    createdAt: '2026-01-28T09:15:00Z',
  },
  {
    id: '4',
    name: 'Two Sum',
    description: 'Hash map solution for two sum problem',
    code: 'def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in seen:\n            return [seen[complement], i]\n        seen[num] = i\n    return []',
    language: 'python',
    timeComplexity: 'O(n)',
    spaceComplexity: 'O(n)',
    isStarred: false,
    createdAt: '2026-01-27T14:00:00Z',
  },
];

export function SnippetsPanel() {
  const [isOpen, setIsOpen] = useState(() => {
    // Restore state from localStorage
    const saved = localStorage.getItem('snippetsPanel:isOpen');
    return saved ? JSON.parse(saved) : true; // default to open
  });

  const [snippets, setSnippets] = useState<Snippet[]>(MOCK_SNIPPETS);
  const [selectedSnippet, setSelectedSnippet] = useState<string | null>(null);

  // Persist open/close state
  useEffect(() => {
    localStorage.setItem('snippetsPanel:isOpen', JSON.stringify(isOpen));
  }, [isOpen]);

  const togglePanel = () => {
    setIsOpen(!isOpen);
  };

  const handleSnippetClick = (id: string) => {
    setSelectedSnippet(selectedSnippet === id ? null : id);
  };

  const handleStarToggle = (id: string, event: React.MouseEvent) => {
    event.stopPropagation();
    setSnippets(snippets.map(s =>
      s.id === id ? { ...s, isStarred: !s.isStarred } : s
    ));
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div className={`snippets-panel ${isOpen ? 'open' : 'collapsed'}`}>
      {/* Toggle button */}
      <button
        className="snippets-toggle"
        onClick={togglePanel}
        aria-label={isOpen ? 'Collapse snippets panel' : 'Expand snippets panel'}
        title={isOpen ? 'Collapse' : 'Expand'}
      >
        {isOpen ? (
          <>
            <span className="snippets-icon">{'{}'}</span>
            <span className="snippets-title">Snippets</span>
          </>
        ) : (
          <span className="snippets-icon-large">{'{}'}</span>
        )}
      </button>

      {/* Panel content */}
      {isOpen && (
        <div className="snippets-content">
          <div className="snippets-header">
            <div className="snippets-search">
              <input
                type="text"
                placeholder="Search snippets..."
                className="snippets-search-input"
              />
            </div>
            <div className="snippets-actions">
              <button className="snippet-header-btn add-btn" title="Create new snippet">
                <span className="btn-icon">+</span>
                <span>Add</span>
              </button>
              <button className="snippet-header-btn search-btn" title="Advanced search">
                <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="11" cy="11" r="6" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <span>Search</span>
              </button>
            </div>
          </div>

          <div className="snippets-list">
            {snippets.length === 0 ? (
              <div className="snippets-empty">
                <p>No snippets yet</p>
                <button className="create-snippet-btn">Create your first snippet</button>
              </div>
            ) : (
              snippets.map((snippet) => (
                <div
                  key={snippet.id}
                  className={`snippet-item ${selectedSnippet === snippet.id ? 'selected' : ''}`}
                  onClick={() => handleSnippetClick(snippet.id)}
                >
                  <div className="snippet-item-header">
                    <div className="snippet-item-title">
                      <span className="snippet-name">{snippet.name}</span>
                    </div>
                  </div>
                  {snippet.description && (
                    <p className="snippet-description">{snippet.description}</p>
                  )}
                  {(snippet.timeComplexity || snippet.spaceComplexity) && (
                    <div className="snippet-complexity">
                      {snippet.timeComplexity && (
                        <span className="complexity-badge time">
                          Time: {snippet.timeComplexity}
                        </span>
                      )}
                      {snippet.spaceComplexity && (
                        <span className="complexity-badge space">
                          Space: {snippet.spaceComplexity}
                        </span>
                      )}
                    </div>
                  )}
                  <button
                    className={`snippet-star-wedge ${snippet.isStarred ? 'starred' : ''}`}
                    onClick={(e) => handleStarToggle(snippet.id, e)}
                    title={snippet.isStarred ? 'Unstar snippet' : 'Star snippet'}
                  >
                    ★
                  </button>
                  <span className="snippet-date">{formatDate(snippet.createdAt)}</span>
                  {selectedSnippet === snippet.id && (
                    <div className="snippet-code-preview">
                      <pre>{snippet.code}</pre>
                      <div className="snippet-actions">
                        <button className="snippet-action-btn load" title="Load snippet into editor">
                          <span className="btn-icon">⇥</span>
                          <span className="btn-label">Load</span>
                        </button>
                        <button className="snippet-action-btn danger" title="Delete snippet">
                          <span className="btn-icon">×</span>
                          <span className="btn-label">Delete</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
