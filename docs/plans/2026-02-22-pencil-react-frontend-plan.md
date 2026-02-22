# Pencil + React Frontend Experiment — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up a Vite + React + Shadcn project in `frontend/`, install a dashboard block, port mock data, and validate the Pencil design-to-code workflow.

**Architecture:** Independent SPA in `frontend/` alongside the existing Angular `web/`. Uses Shadcn UI blocks as starting point, Pencil for visual customization, mock data ported from Angular interceptor. No backend dependency.

**Tech Stack:** Vite 6, React 19, TypeScript, Tailwind CSS 4, Shadcn UI, React Router, Pencil

---

### Task 1: Configure Shadcn MCP Server

**Files:**
- Modify: `.mcp.json` (project root, may need to create)

**Step 1: Add the Shadcn UI MCP server to Claude Code**

Run:
```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform && claude mcp add-json "shadcn-ui-server" '{"command":"npx","args":["-y","shadcn-ui-mcp-server"]}'
```
Expected: MCP server added confirmation.

**Step 2: Verify MCP server is registered**

Run:
```bash
claude mcp list
```
Expected: `shadcn-ui-server` appears in the list.

**Step 3: Commit**

```bash
git add .mcp.json
git commit -m "chore: add Shadcn UI MCP server for component registry access"
```

---

### Task 2: Create Vite + React + TypeScript Project

**Files:**
- Create: `frontend/` directory with Vite scaffold

**Step 1: Scaffold the project**

Run:
```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform && npm create vite@latest frontend -- --template react-ts
```
Expected: `frontend/` directory created with Vite + React + TypeScript template.

**Step 2: Install dependencies**

Run:
```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform/frontend && npm install
```
Expected: `node_modules/` created, no errors.

**Step 3: Verify dev server starts**

Run:
```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform/frontend && npm run dev -- --port 3000 &
sleep 3 && curl -s http://localhost:3000 | head -5
kill %1
```
Expected: HTML output from Vite dev server.

**Step 4: Add `frontend/node_modules` to .gitignore**

Check root `.gitignore`. If it doesn't already cover `frontend/node_modules`, add:
```
frontend/node_modules/
```

**Step 5: Commit**

```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform
git add frontend/ .gitignore
git commit -m "feat: scaffold Vite + React + TypeScript project in frontend/"
```

---

### Task 3: Install Tailwind CSS 4

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/index.css`

**Step 1: Install Tailwind CSS and Vite plugin**

Run:
```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform/frontend && npm install -D tailwindcss @tailwindcss/vite
```

**Step 2: Configure Vite plugin**

Replace `frontend/vite.config.ts` with:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

**Step 3: Add Tailwind import to CSS**

Replace `frontend/src/index.css` with:
```css
@import "tailwindcss";
```

**Step 4: Configure TypeScript path aliases**

Add to `frontend/tsconfig.json` compilerOptions:
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

Also add to `frontend/tsconfig.app.json` compilerOptions:
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

**Step 5: Test Tailwind works**

Replace `frontend/src/App.tsx` with:
```tsx
function App() {
  return (
    <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center">
      <h1 className="text-4xl font-bold">Tailwind works!</h1>
    </div>
  )
}

export default App
```

Run dev server and verify visually that dark background + white bold text renders.

**Step 6: Commit**

```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform
git add frontend/
git commit -m "feat: install Tailwind CSS 4 with Vite plugin"
```

---

### Task 4: Initialize Shadcn UI

**Files:**
- Create: `frontend/components.json`
- Create: `frontend/src/lib/utils.ts`
- Modify: `frontend/src/index.css` (Shadcn CSS variables added)

**Step 1: Run Shadcn init**

Run:
```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform/frontend && npx shadcn@latest init -d
```

The `-d` flag uses defaults (New York style, Zinc base color, CSS variables enabled). If prompted, accept defaults.

Expected: `components.json` created, `src/lib/utils.ts` created with `cn()` helper, CSS variables added to `index.css`.

**Step 2: Verify components.json exists**

Run:
```bash
cat frontend/components.json
```
Expected: JSON config with `"style": "new-york"` or similar, `"aliases"` pointing to `@/components`, `@/lib`.

**Step 3: Install a test component to verify the pipeline**

Run:
```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform/frontend && npx shadcn@latest add button
```
Expected: `src/components/ui/button.tsx` created.

**Step 4: Test the component renders**

Update `frontend/src/App.tsx`:
```tsx
import { Button } from '@/components/ui/button'

function App() {
  return (
    <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center gap-4">
      <Button variant="default">Default</Button>
      <Button variant="outline">Outline</Button>
      <Button variant="destructive">Destructive</Button>
    </div>
  )
}

export default App
```

Run dev server and verify 3 buttons render with correct styles.

**Step 5: Commit**

```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform
git add frontend/
git commit -m "feat: initialize Shadcn UI with button component"
```

---

### Task 5: Install Shadcn Dashboard Block

**Files:**
- Create: Multiple component files in `frontend/src/components/`

**Step 1: Install dashboard-01 block**

Run:
```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform/frontend && npx shadcn@latest add dashboard-01
```

Expected: Several files created including sidebar, charts, data-table, nav components, section-cards, site-header.

**Step 2: List what was installed**

Run:
```bash
find frontend/src/components -name "*.tsx" | sort
```

Document all installed files.

**Step 3: Wire up the dashboard block to App.tsx**

The dashboard-01 block typically includes a page component. Find it and import it in App.tsx:

```tsx
import Dashboard from '@/components/dashboard-01'
// or wherever the block's main component is

function App() {
  return <Dashboard />
}

export default App
```

Adjust the import path based on what `npx shadcn add dashboard-01` actually created.

**Step 4: Run dev server and verify the dashboard renders**

Run dev server at port 3000 and verify visually that the Shadcn dashboard block renders with sidebar, header, charts, and data table.

**Step 5: Commit**

```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform
git add frontend/
git commit -m "feat: install Shadcn dashboard-01 block as starting point"
```

---

### Task 6: Port Mock Data from Angular

**Files:**
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/mock-data.ts`

**Step 1: Create TypeScript interfaces**

Create `frontend/src/lib/types.ts`:
```typescript
export interface NewsItem {
  id: string;
  title: string;
  summary: string | null;
  url: string | null;
  source: string;
  topic: string | null;
  relevance_score: number | null;
  dev_value_score: number | null;
  credibility_score: number | null;
  priority: number | null;
  trending: boolean;
  published_at: string | null;
  created_at: string;
  author: string | null;
  score: number | null;
}

export interface Briefing {
  date: string;
  total_items: number | null;
  items_extracted: number | null;
  items_after_dedup: number | null;
  items_filtered: number | null;
  trending_count: number | null;
  duration_seconds: number | null;
  sources_used: { sources: string[] } | null;
  generated_at: string;
  items: NewsItem[];
}
```

**Step 2: Create mock data**

Create `frontend/src/lib/mock-data.ts` — copy all 20 `MOCK_ITEMS` from `web/src/app/interceptors/mock-api.interceptor.ts` (lines 21-381), adapted to use the new types. Also port `makeBriefing()` and `MOCK_TOPICS`.

The file should export:
```typescript
export const MOCK_ITEMS: NewsItem[] = [ /* all 20 items */ ];
export const MOCK_TOPICS = ['modelos', 'herramientas', 'papers', 'productos', 'open_source', 'agentes', 'regulacion'];
export const MOCK_BRIEFING: Briefing = makeBriefing(TODAY, true);
```

**Step 3: Verify types compile**

Run:
```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform/frontend && npx tsc --noEmit
```
Expected: No errors.

**Step 4: Commit**

```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform
git add frontend/src/lib/types.ts frontend/src/lib/mock-data.ts
git commit -m "feat: port mock data and types from Angular frontend"
```

---

### Task 7: Build Dashboard Page with Mock Data

**Files:**
- Create: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create the Dashboard page component**

Create `frontend/src/pages/Dashboard.tsx`. This page should use components installed from the dashboard-01 block and display:

1. **Header section** — App name, date, status indicator
2. **Stats row** — 5 stat cards showing: Extraidas, Dedup, Filtradas, Trending, Duration (from `MOCK_BRIEFING`)
3. **Topic filters** — Clickable chips for each topic with count
4. **Featured card** — The highest-scored item (item with `score: 2891`)
5. **News grid** — Remaining 19 items in a card grid

Import mock data:
```typescript
import { MOCK_BRIEFING, MOCK_ITEMS, MOCK_TOPICS } from '@/lib/mock-data'
```

Use Shadcn `Card`, `Badge`, `Button` components for the UI.

**Step 2: Update App.tsx to render Dashboard**

```tsx
import Dashboard from '@/pages/Dashboard'

function App() {
  return <Dashboard />
}

export default App
```

**Step 3: Verify it renders**

Run dev server at port 3000. The dashboard should show all 20 mock news items with stats and topic filters.

**Step 4: Commit**

```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform
git add frontend/
git commit -m "feat: build Dashboard page with mock data and Shadcn components"
```

---

### Task 8: Add Dark/Light Mode Toggle

**Files:**
- Create: `frontend/src/hooks/use-theme.ts`
- Create: `frontend/src/components/theme-toggle.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx` (add toggle to header)
- Modify: `frontend/src/index.css` (dark mode CSS variables if not already present)

**Step 1: Create theme hook**

Create `frontend/src/hooks/use-theme.ts`:
```typescript
import { useState, useEffect } from 'react'

type Theme = 'light' | 'dark'

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window !== 'undefined') {
      return (localStorage.getItem('theme') as Theme) || 'dark'
    }
    return 'dark'
  })

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark')

  return { theme, toggleTheme }
}
```

**Step 2: Create toggle component**

Create `frontend/src/components/theme-toggle.tsx` using Shadcn `Button`:
```tsx
import { Button } from '@/components/ui/button'
import { useTheme } from '@/hooks/use-theme'

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  return (
    <Button variant="outline" size="sm" onClick={toggleTheme}>
      {theme === 'dark' ? 'LIGHT' : 'DARK'}
    </Button>
  )
}
```

**Step 3: Add toggle to Dashboard header**

Import `ThemeToggle` in `Dashboard.tsx` and place it in the header area.

**Step 4: Verify dark/light mode works**

Run dev server. Click toggle. Verify colors switch between light and dark.

**Step 5: Commit**

```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform
git add frontend/
git commit -m "feat: add dark/light mode toggle with localStorage persistence"
```

---

### Task 9: Create Pencil Design File

**Files:**
- Create: `frontend/design.pen`

**Step 1: Verify Pencil extension is installed**

Check VS Code/Cursor extensions for "Pencil". If not installed, install it from the marketplace.

**Step 2: Create a .pen file**

In VS Code/Cursor, create a new file `frontend/design.pen`. The Pencil editor should open automatically.

**Step 3: Design the dashboard**

Use Pencil canvas to:
1. Import the existing dashboard layout (screenshot or re-create)
2. Customize the design — experiment with new layouts, colors, typography
3. Use Cmd/Ctrl+K to interact with AI for generating components

This is an interactive/visual step. The user will design in Pencil and generate code.

**Step 4: Commit the .pen file**

```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform
git add frontend/design.pen
git commit -m "feat: add Pencil design file for dashboard experiment"
```

---

### Task 10: Final Verification

**Step 1: Run the dev server**

```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform/frontend && npm run dev -- --port 3000
```

**Step 2: Verify success criteria**

Open `http://localhost:3000` in browser and check:

- [ ] Dashboard page renders 20 mock news items with stats
- [ ] Shadcn components are styled correctly
- [ ] Dark/light mode toggle works
- [ ] Pencil design file exists and can be opened

**Step 3: Final commit**

If any adjustments were made:
```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform
git add frontend/
git commit -m "fix: final adjustments to dashboard experiment"
```
