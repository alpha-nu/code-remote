/**
 * User menu component showing auth state and actions.
 */

import { useState } from 'react';
import { useAuthStore } from '../store/authStore';
import { AuthModal } from './AuthModal';
import './UserMenu.css';

export function UserMenu() {
  const { user, isAuthenticated, isLoading, logout } = useAuthStore();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);

  if (isLoading) {
    return (
      <div className="user-menu">
        <span className="user-loading">Loading...</span>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return (
      <div className="user-menu">
        <button className="sign-in-button" onClick={() => setShowAuthModal(true)}>
          Sign In
        </button>
        {showAuthModal && <AuthModal onClose={() => setShowAuthModal(false)} />}
      </div>
    );
  }

  const handleLogout = async () => {
    setShowDropdown(false);
    await logout();
  };

  return (
    <div className="user-menu">
      <button
        className="user-button"
        onClick={() => setShowDropdown(!showDropdown)}
        aria-expanded={showDropdown}
      >
        <span className="user-avatar">
          {user.email?.[0]?.toUpperCase() || user.username?.[0]?.toUpperCase() || '?'}
        </span>
        {/* Username/email shown inside dropdown header only; keep button compact */}
        <span className="dropdown-arrow">▼</span>
      </button>

      {showDropdown && (
        <>
          <div className="dropdown-backdrop" onClick={() => setShowDropdown(false)} />
          <div className="user-dropdown">
            <div className="dropdown-header">
              <span className="dropdown-email">{user.email}</span>
            </div>
            <button className="dropdown-item logout" onClick={handleLogout}>
              Sign Out
            </button>
          </div>
        </>
      )}
    </div>
  );
}
