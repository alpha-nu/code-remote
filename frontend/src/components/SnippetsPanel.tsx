/**
 * SnippetsPanel - Collapsible sidebar for viewing code snippets
 */

import { useState, useEffect } from 'react';
import { useSnippets, useDeleteSnippet, useUpdateSnippet } from '../hooks/useSnippets';
import { useEditorStore } from '../store/editorStore';
import { useSnippetsStore } from '../store/snippetsStore';
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

  // Fetch snippets from API
  const { data: snippetsData, isLoading, error } = useSnippets(50, 0);
  const snippets = snippetsData?.items || [];

  const deleteSnippet = useDeleteSnippet();
  const updateSnippet = useUpdateSnippet();
  const { code, setCode } = useEditorStore();
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
        const response = await fetch(`http://localhost:8000/snippets/${id}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('authToken') || ''}`,
          },
        });

        if (response.ok) {
          const snippet = await response.json();
          setSnippetCodes(prev => ({ ...prev, [id]: snippet.code }));
        }
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
      const response = await fetch(`http://localhost:8000/snippets/${snippetId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || ''}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to load snippet');
      }

      const snippet = await response.json();
      setCode(snippet.code);
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
          <div className="snippets-header">
            <div className="snippets-search">
              <input
                type="text"
                placeholder="Search snippets..."
                className="snippets-search-input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  className="search-clear-btn"
                  onClick={() => setSearchQuery('')}
                  title="Clear search"
                >
                  ×
                </button>
              )}
            </div>
            <div className="snippets-actions">
              <button
                className="snippet-action-icon add"
                title="Create new snippet"
                onClick={() => setIsAddModalOpen(true)}
              >
                ✚
              </button>
            </div>
          </div>

          <div className="snippets-list">
            {isLoading ? (
              <div className="snippets-loading">
                <img src={spinner} className="spinner-logo small" alt="Loading" /> Loading snippets...
              </div>
            ) : error ? (
              <div className="snippets-error">
                <p>Failed to load snippets</p>
                <p className="error-message">{error instanceof Error ? error.message : 'Unknown error'}</p>
              </div>
            ) : snippets.length === 0 ? (
              <div className="snippets-empty">
                <p>No snippets yet</p>
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
                  <div className="snippet-complexity">
                    <span className="complexity-badge time">
                      Time: {snippet.timeComplexity || 'O(n)'}
                    </span>
                    <span className="complexity-badge space">
                      Space: {snippet.spaceComplexity || 'O(1)'}
                    </span>
                  </div>
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
