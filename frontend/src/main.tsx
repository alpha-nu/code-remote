import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import 'katex/dist/katex.min.css'; // Import katex CSS

// Ensure theme preference is applied synchronously before React mounts so
// components (like Monaco) read the correct theme on initial render.
try {
  const theme = typeof window !== 'undefined' ? localStorage.getItem('theme') : null;
  const root = document.documentElement;
  if (theme === 'light') root.classList.add('light-theme');
  else root.classList.remove('light-theme');
} catch {
  // ignore
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
