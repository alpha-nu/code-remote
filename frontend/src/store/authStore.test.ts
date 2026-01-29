/**
 * Unit tests for auth store.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuthStore, type AuthUser } from './authStore';

// Mock AWS Amplify auth functions
vi.mock('aws-amplify/auth', () => ({
  signIn: vi.fn(),
  signOut: vi.fn(),
  signUp: vi.fn(),
  confirmSignUp: vi.fn(),
  getCurrentUser: vi.fn(),
  fetchAuthSession: vi.fn(),
}));

describe('useAuthStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('should have correct initial values', () => {
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('clearError', () => {
    it('should clear error state', () => {
      useAuthStore.setState({ error: 'Some error' });

      useAuthStore.getState().clearError();

      expect(useAuthStore.getState().error).toBeNull();
    });
  });

  describe('initialize', () => {
    it('should set user when authenticated', async () => {
      const { getCurrentUser, fetchAuthSession } = await import('aws-amplify/auth');

      vi.mocked(getCurrentUser).mockResolvedValue({
        userId: 'user-123',
        username: 'testuser',
        signInDetails: undefined,
      });

      vi.mocked(fetchAuthSession).mockResolvedValue({
        tokens: {
          idToken: {
            payload: { email: 'test@example.com' },
            toString: () => 'mock-id-token',
          },
          accessToken: {
            toString: () => 'mock-access-token',
            payload: {},
          },
        },
        credentials: undefined,
        identityId: undefined,
        userSub: undefined,
      });

      await useAuthStore.getState().initialize();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.user?.id).toBe('user-123');
      expect(state.user?.username).toBe('testuser');
      expect(state.isLoading).toBe(false);
    });

    it('should handle no authenticated user', async () => {
      const { getCurrentUser } = await import('aws-amplify/auth');

      vi.mocked(getCurrentUser).mockRejectedValue(new Error('Not authenticated'));

      await useAuthStore.getState().initialize();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull(); // Not an error, just not logged in
    });
  });

  describe('login', () => {
    it('should return true on successful login', async () => {
      const { signIn, getCurrentUser, fetchAuthSession } = await import('aws-amplify/auth');

      vi.mocked(signIn).mockResolvedValue({
        isSignedIn: true,
        nextStep: { signInStep: 'DONE' },
      });

      vi.mocked(getCurrentUser).mockResolvedValue({
        userId: 'user-456',
        username: 'loggedin',
        signInDetails: undefined,
      });

      vi.mocked(fetchAuthSession).mockResolvedValue({
        tokens: {
          idToken: {
            payload: { email: 'loggedin@example.com' },
            toString: () => 'mock-id-token',
          },
          accessToken: {
            toString: () => 'mock-access-token',
            payload: {},
          },
        },
        credentials: undefined,
        identityId: undefined,
        userSub: undefined,
      });

      const result = await useAuthStore.getState().login('test@example.com', 'password');

      expect(result).toBe(true);
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    it('should return false and set error on failed login', async () => {
      const { signIn } = await import('aws-amplify/auth');

      vi.mocked(signIn).mockRejectedValue(new Error('Invalid credentials'));

      const result = await useAuthStore.getState().login('test@example.com', 'wrong');

      expect(result).toBe(false);
      expect(useAuthStore.getState().error).toBe('Invalid credentials');
      expect(useAuthStore.getState().isLoading).toBe(false);
    });
  });

  describe('logout', () => {
    it('should clear user state on logout', async () => {
      const { signOut } = await import('aws-amplify/auth');

      vi.mocked(signOut).mockResolvedValue(undefined);

      // Set up authenticated state first
      const mockUser: AuthUser = { id: 'user-123', username: 'test', email: 'test@example.com' };
      useAuthStore.setState({
        user: mockUser,
        isAuthenticated: true,
      });

      await useAuthStore.getState().logout();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
    });
  });

  describe('register', () => {
    it('should return true when confirmation needed', async () => {
      const { signUp } = await import('aws-amplify/auth');

      vi.mocked(signUp).mockResolvedValue({
        isSignUpComplete: false,
        nextStep: {
          signUpStep: 'CONFIRM_SIGN_UP',
          codeDeliveryDetails: {
            deliveryMedium: 'EMAIL',
            destination: 'test@example.com',
            attributeName: 'email',
          },
        },
        userId: 'new-user-id',
      });

      const result = await useAuthStore.getState().register('new@example.com', 'password123');

      expect(result).toBe(true);
      expect(useAuthStore.getState().isLoading).toBe(false);
    });

    it('should return false and set error on failure', async () => {
      const { signUp } = await import('aws-amplify/auth');

      vi.mocked(signUp).mockRejectedValue(new Error('Email already exists'));

      const result = await useAuthStore.getState().register('existing@example.com', 'password');

      expect(result).toBe(false);
      expect(useAuthStore.getState().error).toBe('Email already exists');
    });
  });

  describe('confirmRegistration', () => {
    it('should return true on successful confirmation', async () => {
      const { confirmSignUp } = await import('aws-amplify/auth');

      vi.mocked(confirmSignUp).mockResolvedValue({
        isSignUpComplete: true,
        nextStep: { signUpStep: 'DONE' },
      });

      const result = await useAuthStore.getState().confirmRegistration('test@example.com', '123456');

      expect(result).toBe(true);
    });

    it('should return false on invalid code', async () => {
      const { confirmSignUp } = await import('aws-amplify/auth');

      vi.mocked(confirmSignUp).mockRejectedValue(new Error('Invalid verification code'));

      const result = await useAuthStore.getState().confirmRegistration('test@example.com', '000000');

      expect(result).toBe(false);
      expect(useAuthStore.getState().error).toBe('Invalid verification code');
    });
  });

  describe('getAccessToken', () => {
    it('should return token when authenticated', async () => {
      const { fetchAuthSession } = await import('aws-amplify/auth');

      // Note: getAccessToken actually returns the ID token (not access token)
      // because API Gateway JWT authorizer requires the 'aud' claim which is
      // only present in the ID token
      vi.mocked(fetchAuthSession).mockResolvedValue({
        tokens: {
          accessToken: {
            toString: () => 'access-token-123',
            payload: {},
          },
          idToken: {
            toString: () => 'id-token-123',
            payload: {},
          },
        },
        credentials: undefined,
        identityId: undefined,
        userSub: undefined,
      });

      const token = await useAuthStore.getState().getAccessToken();

      // Returns ID token, not access token
      expect(token).toBe('id-token-123');
    });

    it('should return null when not authenticated', async () => {
      const { fetchAuthSession } = await import('aws-amplify/auth');

      vi.mocked(fetchAuthSession).mockRejectedValue(new Error('Not authenticated'));

      const token = await useAuthStore.getState().getAccessToken();

      expect(token).toBeNull();
    });
  });
});
