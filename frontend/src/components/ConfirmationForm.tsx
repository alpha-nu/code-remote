/**
 * Confirmation form for email verification after registration.
 */

import { useState } from 'react';
import { useAuthStore } from '../store/authStore';
import './AuthForms.css';

interface ConfirmationFormProps {
  email: string;
  onConfirmed: () => void;
  onBack: () => void;
}

export function ConfirmationForm({ email, onConfirmed, onBack }: ConfirmationFormProps) {
  const [code, setCode] = useState('');
  const { confirmRegistration, isLoading, error, clearError } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    const success = await confirmRegistration(email, code);
    if (success) {
      onConfirmed();
    }
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <h2>Verify Your Email</h2>

      <p className="auth-info">
        We've sent a verification code to <strong>{email}</strong>
      </p>

      {error && <div className="auth-error">{error}</div>}

      <div className="form-group">
        <label htmlFor="code">Verification Code</label>
        <input
          id="code"
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="Enter 6-digit code"
          required
          disabled={isLoading}
          maxLength={6}
          pattern="[0-9]{6}"
        />
      </div>

      <button type="submit" className="auth-button" disabled={isLoading}>
        {isLoading ? 'Verifying...' : 'Verify Email'}
      </button>

      <p className="auth-switch">
        <button type="button" onClick={onBack} className="link-button">
          Back to Sign In
        </button>
      </p>
    </form>
  );
}
