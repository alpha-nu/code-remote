/**
 * Main application component.
 */

import { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toolbar } from './components/Toolbar';
import { CodeEditor } from './components/CodeEditor';
import { OutputPanel } from './components/OutputPanel';
import { SnippetsPanel } from './components/SnippetsPanel';
import { configureAmplify } from './config/amplify';
import { useAuthStore } from './store/authStore';
import type { ConnectionState } from './hooks/useWebSocket';
import './App.css';

// Configure AWS Amplify at app startup
configureAmplify();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppContent() {
  const initialize = useAuthStore((state) => state.initialize);
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');

  useEffect(() => {
    // Initialize auth state on mount
    initialize();
  }, [initialize]);

  useEffect(() => {
    // Apply persisted theme preference
    const theme = typeof window !== 'undefined' ? localStorage.getItem('theme') : null;
    const root = document.documentElement;
    if (theme === 'light') root.classList.add('light-theme');
    else root.classList.remove('light-theme');
  }, []);

  return (
    <div className="app">
      <Toolbar onConnectionStateChange={setConnectionState} />
      <main className="main-content">
        <SnippetsPanel />
        <div className="editor-pane">
          <CodeEditor connectionState={connectionState} />
        </div>
        <div className="output-pane">
          <OutputPanel />
        </div>
      </main>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;
