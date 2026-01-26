/**
 * Main application component.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toolbar } from './components/Toolbar';
import { CodeEditor } from './components/CodeEditor';
import { OutputPanel } from './components/OutputPanel';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
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
    </QueryClientProvider>
  );
}

export default App;
