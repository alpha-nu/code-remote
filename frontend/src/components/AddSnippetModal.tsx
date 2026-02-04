/**
 * AddSnippetModal - Modal for creating a new snippet from current code
 */

import { useState } from 'react';
import { useCreateSnippet } from '../hooks/useSnippets';
import { useEditorStore } from '../store/editorStore';
import './AddSnippetModal.css';

interface AddSnippetModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AddSnippetModal({ isOpen, onClose }: AddSnippetModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const { code } = useEditorStore();
  const createSnippet = useCreateSnippet();

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      return; // Title is required
    }

    if (!code.trim()) {
      alert('No code in editor to save');
      return;
    }

    setIsSaving(true);

    try {
      await createSnippet.mutateAsync({
        code: code,
        title: title.trim(),
        description: description.trim() || undefined,
        language: 'python',
      });

      // Success - close modal and reset form
      setTitle('');
      setDescription('');
      onClose();
    } catch (error) {
      console.error('Failed to create snippet:', error);
      alert('Failed to save snippet. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setTitle('');
    setDescription('');
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={handleCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Save Code Snippet</h2>
          <button className="modal-close" onClick={handleCancel} title="Close">
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label htmlFor="snippet-title">
                Title <span className="required">*</span>
              </label>
              <input
                id="snippet-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Binary Search Algorithm"
                maxLength={255}
                required
                autoFocus
              />
            </div>

            <div className="form-group">
              <label htmlFor="snippet-description">Description</label>
              <textarea
                id="snippet-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description of what this code does..."
                rows={3}
                maxLength={2000}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn-secondary"
              onClick={handleCancel}
              disabled={isSaving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={isSaving || !title.trim() || !code.trim()}
            >
              {isSaving ? 'Saving...' : 'Save Snippet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
