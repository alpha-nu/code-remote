/**
 * Unit tests for auth store focusing on reset/cache behavior added to login/logout.
 *
 * Strategy: spy on the real `useEditorStore`, `useSnippetsStore` and `queryClient`
 * rather than trying to factory-mock them (avoids vi.mock hoisting issues).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAuthStore, type AuthUser } from './authStore';
import { useEditorStore } from './editorStore';
import { useSnippetsStore } from './snippetsStore';
import { queryClient } from '../utils/queryClient';
import * as auth from 'aws-amplify/auth';

vi.mock('aws-amplify/auth');

describe('useAuthStore (login/logout side effects)', () => {
  const mockedAuth = vi.mocked(auth, true);

  beforeEach(() => {
    // Reset Zustand store state
    useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });
    // Ensure stores are in a known state (no `any` casts)
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('resets editor state after successful login', async () => {
    // Arrange: spy on the editor reset function
    const editorResetSpy = vi.spyOn(useEditorStore.getState(), 'reset');

    // Mock auth signIn + initialize flow
    mockedAuth.signIn!.mockResolvedValue({ isSignedIn: true, nextStep: { signInStep: 'DONE' } });
    mockedAuth.getCurrentUser!.mockResolvedValue({ userId: 'u1', username: 'bob' });
    mockedAuth.fetchAuthSession!.mockResolvedValue({ tokens: {
        idToken: { payload: { email: 'bob@example.com' }, toString: () => 't' },
        accessToken: { payload: {}, toString: () => 'access-token' }
    } });

    // Act
    const result = await useAuthStore.getState().login('bob', 'pw');

    // Assert
    expect(result).toBe(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(editorResetSpy).toHaveBeenCalled();
  });

  it('clears editor/snippets and removes snippets query on logout', async () => {
    // Arrange: set store as authenticated and spy on resets and queryClient
    useAuthStore.setState({ user: { id: 'u1', username: 'bob' } as AuthUser, isAuthenticated: true });
    const editorResetSpy = vi.spyOn(useEditorStore.getState(), 'reset');
    const snippetsResetSpy = vi.spyOn(useSnippetsStore.getState(), 'clearLoadedSnippet');
    const removeQueriesSpy = vi.spyOn(queryClient, 'removeQueries');

    mockedAuth.signOut!.mockResolvedValue(undefined);

    // Act
    await useAuthStore.getState().logout();

    // Assert
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(editorResetSpy).toHaveBeenCalled();
    expect(snippetsResetSpy).toHaveBeenCalled();
    expect(removeQueriesSpy).toHaveBeenCalledWith({ queryKey: ['snippets'] });
  });
});
