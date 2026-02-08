/**
 * SnippetsPanel - Collapsible sidebar for viewing code snippets
 */

import { useState, useEffect } from 'react';
import { useSnippets, useDeleteSnippet, useUpdateSnippet } from '../hooks/useSnippets';
import { useSearch, useComplexityFilter } from '../hooks/useSearch';
import type { ComplexityType } from '../hooks/useSearch';
import { useEditorStore } from '../store/editorStore';
import { useSnippetsStore } from '../store/snippetsStore';
import { snippetsApi } from '../api/snippets';
import { AddSnippetModal } from './AddSnippetModal';
import type { SnippetSummary } from '../types/api';
import spinner from '../assets/spinner.svg';
import './SnippetsPanel.css';

export function SnippetsPanel() {
  const [isOpen, setIsOpen] = useState(() => {
    // Restore state from localStorage
    const saved = localStorage.getItem('snippetsPanel:isOpen');
    return saved ? JSON.parse(saved) : true; // default to open
  });

  const [selectedSnippet, setSelectedSnippet] = useState<string | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [snippetCodes, setSnippetCodes] = useState<Record<string, string>>({});
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSearchQuery, setActiveSearchQuery] = useState<string | null>(null);

  // Complexity filter state
  const [activeComplexityFilter, setActiveComplexityFilter] = useState<{
    value: string;
    type: ComplexityType;
  } | null>(null);

  // Fetch snippets from API
  const { data: snippetsData, isLoading, error } = useSnippets(50, 0);
  const regularSnippets = snippetsData?.items || [];

  // Search results (only fetches when activeSearchQuery is set)
  const {
    data: searchData,
    isLoading: isSearching,
    error: searchError
  } = useSearch(activeSearchQuery);

  // Complexity filter results
  const {
    data: complexityData,
    isLoading: isFilteringByComplexity,
    error: complexityError,
  } = useComplexityFilter(
    activeComplexityFilter?.value ?? null,
    activeComplexityFilter?.type ?? null
  );

  // Determine which snippets to display
  const isSearchMode = activeSearchQuery !== null;
  const isComplexityFilterMode = activeComplexityFilter !== null;
  const snippets: SnippetSummary[] = isSearchMode
    ? (searchData?.results || []).map(r => ({
        id: r.snippet_id,
        title: r.title || 'Untitled',
        description: r.description,
        timeComplexity: r.time_complexity,
        spaceComplexity: r.space_complexity,
        isStarred: false, // Search results don't include this
        createdAt: new Date().toISOString(), // Not included in search results
        // Fill in missing fields for search results
        language: r.language || 'python',
        executionCount: 0,
        lastExecutionAt: null,
        updatedAt: new Date().toISOString(),
      }))
    : isComplexityFilterMode
    ? (complexityData?.results || []).map(r => ({
        id: r.snippet_id,
        title: r.title || 'Untitled',
        description: r.description,
        timeComplexity: r.time_complexity,
        spaceComplexity: r.space_complexity,
        isStarred: false,
        createdAt: new Date().toISOString(),
        language: r.language || 'python',
        executionCount: 0,
        lastExecutionAt: null,
        updatedAt: new Date().toISOString(),
      }))
    : regularSnippets;

  const deleteSnippet = useDeleteSnippet();
  const updateSnippet = useUpdateSnippet();
  const { code, setCode, setResult } = useEditorStore();
  const {
    loadedSnippetId,
    loadedSnippetCode,
    setLoadedSnippet,
    clearLoadedSnippet
  } = useSnippetsStore();

  // Persist open/close state
  useEffect(() => {
    localStorage.setItem('snippetsPanel:isOpen', JSON.stringify(isOpen));
  }, [isOpen]);

  const togglePanel = () => {
    setIsOpen(!isOpen);
  };

  const handleSnippetClick = async (id: string) => {
    const newSelected = selectedSnippet === id ? null : id;
    setSelectedSnippet(newSelected);

    // Fetch code if expanding and we don't have it cached
    if (newSelected && !snippetCodes[id]) {
      try {
        const snippet = await snippetsApi.get(id);
        setSnippetCodes(prev => ({ ...prev, [id]: snippet.code }));
      } catch (err) {
        console.error('Failed to fetch snippet code:', err);
      }
    }
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

  const handleStarToggle = async (snippetId: string, currentStarred: boolean, e: React.MouseEvent) => {
    e.stopPropagation();

    try {
      await updateSnippet.mutateAsync({
        id: snippetId,
        data: { isStarred: !currentStarred },
      });
    } catch (err) {
      console.error('Failed to toggle star:', err);
      alert('Failed to update favorite status. Please try again.');
    }
  };

  const handleLoad = async (snippetId: string) => {
    // Warn if loading would replace code in editor:
    // - Loading when no snippet is currently loaded, OR
    // - Loading a different snippet than currently loaded, OR
    // - Loading same snippet but code has been modified
    const hasUnsavedChanges = code.trim() && (
      snippetId !== loadedSnippetId || code !== loadedSnippetCode
    );

    if (hasUnsavedChanges) {
      const confirmed = confirm(
        'You have unsaved code in the editor. Loading this snippet will replace it. Continue?'
      );
      if (!confirmed) return;
    }

    try {
      // Fetch full snippet (including code)
      const snippet = await snippetsApi.get(snippetId);
      setCode(snippet.code);
      setResult(null); // Clear output when loading snippet
      setLoadedSnippet(snippetId, snippet.title || 'Untitled', snippet.code);
    } catch (err) {
      console.error('Failed to load snippet:', err);
      alert('Failed to load snippet. Please try again.');
    }
  };

  const handleDelete = async (snippetId: string, title: string) => {
    const confirmed = confirm(
      `Delete "${title}"? This action cannot be undone.`
    );

    if (!confirmed) return;

    try {
      await deleteSnippet.mutateAsync(snippetId);

      // Clear loaded snippet if it was deleted
      if (loadedSnippetId === snippetId) {
        clearLoadedSnippet();
      }
    } catch (err) {
      console.error('Failed to delete snippet:', err);
      alert('Failed to delete snippet. Please try again.');
    }
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
          <button
            className="add-snippet-button"
            title="Create new snippet"
            onClick={() => setIsAddModalOpen(true)}
          >
            <span className="button-icon">✚</span>
            <span>New Snippet</span>
          </button>

          <div className="snippets-header">
            <div className="snippets-search">
              <input
                type="text"
                placeholder="Search snippets... (Enter to search)"
                className="snippets-search-input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && searchQuery.length >= 3) {
                    setActiveComplexityFilter(null); // Clear complexity filter
                    setActiveSearchQuery(searchQuery);
                  } else if (e.key === 'Escape') {
                    setSearchQuery('');
                    setActiveSearchQuery(null);
                  }
                }}
              />
              {(searchQuery || isSearchMode) && (
                <button
                  className="search-clear-btn"
                  onClick={() => {
                    setSearchQuery('');
                    setActiveSearchQuery(null);
                  }}
                  title="Clear search"
                >
                  ×
                </button>
              )}
            </div>
          </div>

          {/* Complexity filter mode indicator */}
          {isComplexityFilterMode && !isSearchMode && (
            <div className="search-mode-indicator complexity-filter">
              <span className="search-mode-label">
                {activeComplexityFilter.type === 'time' ? 'Time' : 'Space'}: {activeComplexityFilter.value}
                {complexityData && ` (${complexityData.total} found)`}
              </span>
              <button
                className="filter-clear-btn"
                onClick={() => setActiveComplexityFilter(null)}
                title="Clear filter"
              >
                ×
              </button>
            </div>
          )}

          <div className="snippets-list">
            {(isLoading || isSearching || isFilteringByComplexity) ? (
              <div className="snippets-loading">
                <img src={spinner} className="spinner-logo small" alt="Loading" />
                {isSearching ? 'Searching...' : isFilteringByComplexity ? 'Filtering...' : 'Loading snippets...'}
              </div>
            ) : (error || searchError || complexityError) ? (
              <div className="snippets-error">
                <p>Failed to load snippets</p>
                <p className="error-message">
                  {(error || searchError || complexityError) instanceof Error
                    ? (error || searchError || complexityError)?.message
                    : 'Unknown error'}
                </p>
              </div>
            ) : snippets.length === 0 ? (
              <div className="snippets-empty">
                <p>{(isSearchMode || isComplexityFilterMode) ? 'No matching snippets found' : 'No snippets yet'}</p>
              </div>
            ) : (
              snippets.map((snippet: SnippetSummary) => (
                <div
                  key={snippet.id}
                  className={`snippet-item ${selectedSnippet === snippet.id ? 'selected' : ''}`}
                  onClick={() => handleSnippetClick(snippet.id)}
                >
                  <div className="snippet-item-header">
                    <div className="snippet-item-title">
                      <span className="snippet-name">{snippet.title || 'Untitled'}</span>
                    </div>
                  </div>
                  {snippet.description && (
                    <p className="snippet-description">{snippet.description}</p>
                  )}
                  {(snippet.timeComplexity || snippet.spaceComplexity) && (
                    <div className="snippet-complexity">
                      {snippet.timeComplexity && (
                        <button
                          className="complexity-badge time clickable"
                          title={`Filter by Time: ${snippet.timeComplexity}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveSearchQuery(null); // Clear search mode
                            setSearchQuery('');
                            setActiveComplexityFilter({
                              value: snippet.timeComplexity!,
                              type: 'time',
                            });
                          }}
                        >
                          Time: {snippet.timeComplexity}
                        </button>
                      )}
                      {snippet.spaceComplexity && (
                        <button
                          className="complexity-badge space clickable"
                          title={`Filter by Space: ${snippet.spaceComplexity}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveSearchQuery(null); // Clear search mode
                            setSearchQuery('');
                            setActiveComplexityFilter({
                              value: snippet.spaceComplexity!,
                              type: 'space',
                            });
                          }}
                        >
                          Space: {snippet.spaceComplexity}
                        </button>
                      )}
                    </div>
                  )}
                  <button
                    className={`snippet-star-wedge ${snippet.isStarred ? 'starred' : ''}`}
                    title={snippet.isStarred ? 'Remove from favorites' : 'Add to favorites'}
                    onClick={(e) => handleStarToggle(snippet.id, snippet.isStarred, e)}
                  >
                    ★
                  </button>
                  <span className="snippet-date">{formatDate(snippet.createdAt)}</span>
                  {selectedSnippet === snippet.id && (
                    <div className="snippet-code-preview">
                      <div className="snippet-preview-code">
                        <pre>{snippetCodes[snippet.id] || 'Loading code...'}</pre>
                      </div>
                      <div className="snippet-actions">
                        <button
                          className="snippet-action-icon load"
                          title="Load snippet into editor"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleLoad(snippet.id);
                          }}
                        >
                          ↻
                        </button>
                        <button
                          className="snippet-action-icon delete"
                          title="Delete snippet"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(snippet.id, snippet.title || 'Untitled');
                          }}
                        >
                          ✕
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

      {/* Add Snippet Modal */}
      <AddSnippetModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
      />
    </div>
  );
}
