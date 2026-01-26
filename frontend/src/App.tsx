/**
 * Main application component.
 */

import { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toolbar } from './components/Toolbar';
import { CodeEditor } from './components/CodeEditor';
import { OutputPanel } from './components/OutputPanel';
import { configureAmplify } from './config/amplify';
import { useAuthStore } from './store/authStore';
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

  useEffect(() => {
    // Initialize auth state on mount
    initialize();
  }, [initialize]);

  return (
    <div className="app">
      <Toolbar />
      <main className="main-content">
        <div className="editor-pane">
          <CodeEditor />
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
