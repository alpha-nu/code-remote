# Code Remote Frontend

React web application for the Remote Code Execution Engine.

## Tech Stack

- **React 18** with TypeScript
- **Vite** for build tooling
- **Monaco Editor** - VS Code's editor component
- **Zustand** for state management
- **Axios** for API calls

## Development

### Prerequisites

- Node.js 18+
- npm or yarn

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Default: http://localhost:5173
# Or specify port: npm run dev -- --port 3000
```

### Building

```bash
# Production build
npm run build

# Preview production build
npm run preview
```

### Linting & Type Checking

We use ESLint with TypeScript support for linting.

```bash
# Run ESLint
npm run lint

# Run TypeScript type checking
npm run type-check
```

### Testing

We use Vitest with React Testing Library for unit tests.

```bash
# Run tests once
npm run test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage
```

#### ESLint Configuration

ESLint is configured in `eslint.config.js` with:
- TypeScript-ESLint recommended rules
- React Hooks rules
- React Refresh rules

### Pre-commit Hooks

Pre-commit hooks are configured at the repository root. Hooks run automatically on commit and include:
- ESLint for TypeScript/React
- TypeScript type checking

Install hooks from repo root:

```bash
cd ..
pip install pre-commit
pre-commit install
```

## Project Structure

```
frontend/
├── src/
│   ├── api/           # API client functions
│   ├── assets/        # Static assets
│   ├── components/    # React components
│   │   ├── CodeEditor.tsx      # Monaco editor wrapper
│   │   ├── OutputPanel.tsx     # Execution output display
│   │   ├── ComplexityPanel.tsx # AI analysis results
│   │   └── Toolbar.tsx         # Action buttons
│   ├── store/         # Zustand state stores
│   ├── types/         # TypeScript type definitions
│   ├── App.tsx        # Main application component
│   └── main.tsx       # Entry point
├── public/            # Static files
└── index.html         # HTML template
```

## Features

- **Code Editor** - Full Monaco Editor with Python syntax highlighting
- **Code Execution** - Run Python code securely via backend API
- **Complexity Analysis** - AI-powered Big-O analysis via Gemini LLM
- **Real-time Output** - View stdout, stderr, and execution time

## Environment

The app connects to the backend API. Configure the API URL:

```bash
# Default: http://localhost:8000
# For production, set VITE_API_URL environment variable
```
