/**
 * Auth modal component that contains all auth forms.
 */

import { useState } from 'react';
import { LoginForm } from './LoginForm';
import { RegisterForm } from './RegisterForm';
import { ConfirmationForm } from './ConfirmationForm';
import './AuthModal.css';

type AuthView = 'login' | 'register' | 'confirm';

interface AuthModalProps {
  onClose: () => void;
}

export function AuthModal({ onClose }: AuthModalProps) {
  const [view, setView] = useState<AuthView>('login');
  const [confirmEmail, setConfirmEmail] = useState('');

  const handleNeedConfirmation = (email: string) => {
    setConfirmEmail(email);
    setView('confirm');
  };

  const handleConfirmed = () => {
    // After confirmation, go to login
    setView('login');
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div className="auth-modal-backdrop" onClick={handleBackdropClick}>
      <div className="auth-modal">
        <button className="auth-modal-close" onClick={onClose} aria-label="Close">
          ×
        </button>

        {view === 'login' && (
          <LoginForm onSwitchToRegister={() => setView('register')} />
        )}

        {view === 'register' && (
          <RegisterForm
            onSwitchToLogin={() => setView('login')}
            onNeedConfirmation={handleNeedConfirmation}
          />
        )}

        {view === 'confirm' && (
          <ConfirmationForm
            email={confirmEmail}
            onConfirmed={handleConfirmed}
            onBack={() => setView('login')}
          />
        )}
      </div>
    </div>
  );
}
