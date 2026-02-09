/**
 * Zustand store for authentication state management.
 */

import { create } from 'zustand';
import {
  signIn,
  signOut,
  signUp,
  confirmSignUp,
  getCurrentUser,
  fetchAuthSession,
  type SignInInput,
  type SignUpInput,
  type ConfirmSignUpInput,
} from 'aws-amplify/auth';

export interface AuthUser {
  id: string;
  username: string;
  email?: string;
}

interface AuthState {
  // User state
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  // Error state
  error: string | null;

  // Actions
  initialize: () => Promise<void>;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  register: (email: string, password: string) => Promise<boolean>;
  confirmRegistration: (username: string, code: string) => Promise<boolean>;
  getAccessToken: () => Promise<string | null>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  /**
   * Initialize auth state by checking for existing session.
   */
  initialize: async () => {
    set({ isLoading: true, error: null });
    try {
      const currentUser = await getCurrentUser();
      const session = await fetchAuthSession();

      set({
        user: {
          id: currentUser.userId,
          username: currentUser.username,
          email: session.tokens?.idToken?.payload?.email as string | undefined,
        },
        isAuthenticated: true,
        isLoading: false,
      });
    } catch {
      // No authenticated user - this is expected, not an error
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  },

  /**
   * Sign in with username/email and password.
   */
  login: async (username: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const input: SignInInput = { username, password };
      const result = await signIn(input);

      if (result.isSignedIn) {
        // Fetch user details after successful sign-in
        await get().initialize();
        return true;
      } else {
        set({
          isLoading: false,
          error: 'Sign-in requires additional steps',
        });
        return false;
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      set({
        isLoading: false,
        error: message,
      });
      return false;
    }
  },

  /**
   * Sign out the current user.
   */
  logout: async () => {
    set({ isLoading: true, error: null });
    try {
      await signOut();
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Logout failed';
      set({
        isLoading: false,
        error: message,
      });
    }
  },

  /**
   * Register a new user.
   */
  register: async (email: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const input: SignUpInput = {
        username: email,
        password,
        options: {
          userAttributes: {
            email,
          },
        },
      };
      const result = await signUp(input);

      set({ isLoading: false });
      return result.isSignUpComplete || result.nextStep.signUpStep === 'CONFIRM_SIGN_UP';
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      set({
        isLoading: false,
        error: message,
      });
      return false;
    }
  },

  /**
   * Confirm registration with verification code.
   */
  confirmRegistration: async (username: string, code: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const input: ConfirmSignUpInput = {
        username,
        confirmationCode: code,
      };
      const result = await confirmSignUp(input);

      set({ isLoading: false });
      return result.isSignUpComplete;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Confirmation failed';
      set({
        isLoading: false,
        error: message,
      });
      return false;
    }
  },

  /**
   * Get the current ID token for API calls.
   * We use ID token instead of access token because API Gateway JWT authorizer
   * validates the "aud" claim which is only present in ID tokens.
   */
  getAccessToken: async (): Promise<string | null> => {
    try {
      const session = await fetchAuthSession();
      return session.tokens?.idToken?.toString() ?? null;
    } catch {
      return null;
    }
  },

  /**
   * Clear any error message.
   */
  clearError: () => set({ error: null }),
}));
