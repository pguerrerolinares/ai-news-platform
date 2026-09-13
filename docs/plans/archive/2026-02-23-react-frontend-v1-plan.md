# React Frontend v1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the 4 public pages (Latest, Trending, Buscar, Chat) with mock data, responsive mobile nav, and shared components.

**Architecture:** Extends the existing Vite + React + Shadcn POC. Extract shared components (NewsCard, FeaturedCard, constants) from Dashboard.tsx into reusable modules. Each page is a standalone route component using mock data. Mobile nav uses Shadcn Sheet.

**Tech Stack:** Vite 7, React 19, TypeScript, Tailwind CSS 4, Shadcn UI, React Router 7, @tabler/icons-react

---

### Task 1: Extract Shared Components from Dashboard

**Files:**
- Create: `frontend/src/components/news-card.tsx`
- Create: `frontend/src/components/featured-card.tsx`
- Create: `frontend/src/lib/constants.ts`
- Modify: `frontend/src/pages/Dashboard.tsx`

**Step 1: Create constants file**

Create `frontend/src/lib/constants.ts`:
```typescript
export const SOURCE_COLORS: Record<string, string> = {
  hackernews: 'bg-orange-500/10 text-orange-500 border-orange-500/20',
  github: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
  arxiv: 'bg-red-500/10 text-red-500 border-red-500/20',
  reddit: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  rss: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  huggingface: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
}

export const TOPIC_LABELS: Record<string, string> = {
  modelos: 'Modelos',
  herramientas: 'Herramientas',
  papers: 'Papers',
  productos: 'Productos',
  open_source: 'Open Source',
  agentes: 'Agentes',
  regulacion: 'Regulacion',
}

export function formatTime(dateStr: string | null) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
}
```

**Step 2: Create NewsCard component**

Create `frontend/src/components/news-card.tsx` — extract the `NewsCard` function from `Dashboard.tsx` into its own file. Import `SOURCE_COLORS`, `TOPIC_LABELS`, `formatTime` from `@/lib/constants`. Export as named export `NewsCard`.

**Step 3: Create FeaturedCard component**

Create `frontend/src/components/featured-card.tsx` — extract `FeaturedCard` from `Dashboard.tsx`. Same imports pattern.

**Step 4: Refactor Dashboard.tsx**

Remove `NewsCard`, `FeaturedCard`, `SOURCE_COLORS`, `TOPIC_LABELS`, `formatTime` from Dashboard.tsx. Import them from the new files:
```typescript
import { NewsCard } from '@/components/news-card'
import { FeaturedCard } from '@/components/featured-card'
```

**Step 5: Verify it compiles**

Run:
```bash
cd frontend && timeout 10 bun run dev -- --port 3000
```
Expected: Vite starts, no errors.

**Step 6: Commit**

```bash
git add frontend/src/components/news-card.tsx frontend/src/components/featured-card.tsx frontend/src/lib/constants.ts frontend/src/pages/Dashboard.tsx
git commit -m "refactor: extract NewsCard, FeaturedCard, and constants into shared modules"
```

---

### Task 2: Mobile Hamburger Nav

**Files:**
- Modify: `frontend/src/components/app-nav.tsx`

**Step 1: Rewrite AppNav with mobile Sheet**

Replace `frontend/src/components/app-nav.tsx` with a responsive version:
- Desktop (md+): show nav links inline as they are now
- Mobile (<md): hide nav links, show a hamburger button that opens a `Sheet` from the left with the nav links stacked vertically
- Use `useIsMobile()` hook from `@/hooks/use-mobile` (already installed with dashboard-01 block)
- Import `Sheet`, `SheetContent`, `SheetTrigger` from `@/components/ui/sheet`
- Import `IconMenu2` from `@tabler/icons-react` for hamburger icon
- Sheet links should close the sheet on click (use `onOpenChange` state)

**Step 2: Verify on desktop and mobile**

Run dev server. Check:
- Desktop: nav links visible, no hamburger
- Resize to mobile width: hamburger appears, links hidden, clicking hamburger opens Sheet with links

**Step 3: Commit**

```bash
git add frontend/src/components/app-nav.tsx
git commit -m "feat: responsive mobile nav with hamburger menu (Sheet)"
```

---

### Task 3: Rename "Hoy" to "Latest" in Nav

**Files:**
- Modify: `frontend/src/components/app-nav.tsx`

**Step 1: Update nav link label**

In the `links` array, change `{ to: '/', label: 'Hoy' }` to `{ to: '/', label: 'Latest' }`.

**Step 2: Update Dashboard heading**

In `frontend/src/pages/Dashboard.tsx`, change the `<h2>` from "Hoy en IA" to "Latest".

**Step 3: Commit**

```bash
git add frontend/src/components/app-nav.tsx frontend/src/pages/Dashboard.tsx
git commit -m "refactor: rename Hoy to Latest in nav and page heading"
```

---

### Task 4: Trending Page

**Files:**
- Create: `frontend/src/pages/Trending.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create Trending page**

Create `frontend/src/pages/Trending.tsx`:

```tsx
import { MOCK_ITEMS } from '@/lib/mock-data'
import { NewsCard } from '@/components/news-card'

export default function Trending() {
  const trendingItems = MOCK_ITEMS.filter(i => i.trending)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
  const topScored = [...MOCK_ITEMS]
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 10)

  return (
    <div className="space-y-8">
      {/* Trending section */}
      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">En movimiento</h2>
          <p className="text-sm text-muted-foreground">
            {trendingItems.length} noticias generando traccion ahora
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {trendingItems.map(item => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
      </section>

      {/* Top scored section */}
      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Top puntuados</h2>
          <p className="text-sm text-muted-foreground">
            Las noticias con mayor puntuacion
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {topScored.map(item => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
      </section>
    </div>
  )
}
```

**Step 2: Wire route in App.tsx**

In `frontend/src/App.tsx`, replace the Trending Placeholder import/route with:
```tsx
import Trending from '@/pages/Trending'
// ...
<Route path="trending" element={<Trending />} />
```

**Step 3: Verify**

Run dev server. Navigate to `/trending`. Should show two sections with cards.

**Step 4: Commit**

```bash
git add frontend/src/pages/Trending.tsx frontend/src/App.tsx
git commit -m "feat: Trending page with 'En movimiento' and 'Top puntuados' sections"
```

---

### Task 5: Buscar Page

**Files:**
- Create: `frontend/src/pages/Buscar.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create Buscar page**

Create `frontend/src/pages/Buscar.tsx`:

```tsx
import { useState } from 'react'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { MOCK_ITEMS, MOCK_TOPICS } from '@/lib/mock-data'
import { TOPIC_LABELS } from '@/lib/constants'
import { NewsCard } from '@/components/news-card'
import { IconSearch } from '@tabler/icons-react'

export default function Buscar() {
  const [query, setQuery] = useState('')
  const [topic, setTopic] = useState('all')
  const [sortBy, setSortBy] = useState('relevancia')

  const q = query.toLowerCase()
  let results = q
    ? MOCK_ITEMS.filter(
        i => i.title.toLowerCase().includes(q) || (i.summary ?? '').toLowerCase().includes(q)
      )
    : []

  if (topic !== 'all') {
    results = results.filter(i => i.topic === topic)
  }

  if (sortBy === 'fecha') {
    results.sort((a, b) => (b.published_at ?? '').localeCompare(a.published_at ?? ''))
  } else if (sortBy === 'score') {
    results.sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Buscar</h2>
        <p className="text-sm text-muted-foreground">Busca entre las noticias de IA</p>
      </div>

      {/* Search controls */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <IconSearch className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar noticias..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={topic} onValueChange={setTopic}>
          <SelectTrigger className="w-full sm:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            {MOCK_TOPICS.map(t => (
              <SelectItem key={t} value={t}>{TOPIC_LABELS[t] ?? t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={sortBy} onValueChange={setSortBy}>
          <SelectTrigger className="w-full sm:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="relevancia">Relevancia</SelectItem>
            <SelectItem value="fecha">Fecha</SelectItem>
            <SelectItem value="score">Score</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Results */}
      {query && (
        <p className="text-sm text-muted-foreground">
          {results.length} resultado{results.length !== 1 ? 's' : ''} para "{query}"
        </p>
      )}

      {results.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {results.map(item => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
      )}

      {query && results.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No se encontraron resultados para "{query}"</p>
        </div>
      )}

      {!query && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <IconSearch className="size-8" />
          <p>Escribe para buscar noticias</p>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Wire route in App.tsx**

Replace the Buscar Placeholder with the real component.

**Step 3: Verify**

Run dev server. Navigate to `/buscar`. Type "LLM" — should show filtered results. Change topic and sort.

**Step 4: Commit**

```bash
git add frontend/src/pages/Buscar.tsx frontend/src/App.tsx
git commit -m "feat: Buscar page with search input, topic filter, and sort options"
```

---

### Task 6: Chat Page (Mock)

**Files:**
- Create: `frontend/src/pages/Chat.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create Chat page**

Create `frontend/src/pages/Chat.tsx` — full-page chat interface:
- State: `messages` array of `{ role: 'user' | 'assistant', content: string }`
- Message list in a `ScrollArea` that grows to fill available space
- User messages right-aligned with primary background
- Assistant messages left-aligned with muted background
- Input bar at bottom: `Textarea` (auto-height, max 4 rows) + Send `Button`
- Submit on Enter (without Shift), Shift+Enter for new line
- 3 suggestion chips shown when no messages: "Que noticias hay de LLMs?", "Resume el trending de hoy", "Que herramientas nuevas hay?"
- Mock assistant response: after user sends, wait 500ms, then add a mock response based on the query (simple string match or generic response)
- Auto-scroll to bottom on new message

Mock responses (hardcoded):
```typescript
const MOCK_RESPONSES: Record<string, string> = {
  default: 'Basandome en las noticias de hoy, puedo decirte que el mundo de la IA sigue en constante movimiento. Hay avances importantes en modelos open-source, nuevas herramientas de desarrollo, y cambios regulatorios tanto en Europa como en Asia. Quieres que profundice en algun tema en particular?',
  llm: 'Hoy hay varias noticias sobre LLMs: DeepSeek R2 supera a GPT-4o en razonamiento matematico, Anthropic lanza Claude 3.5 Haiku con 200K tokens de contexto, y Phi-4 de Microsoft logra estado del arte en matematicas con solo 14B parametros. El trend principal es que los modelos mas pequeños estan cerrando la brecha con los grandes.',
  trending: 'Las noticias con mas traccion hoy son: Mixtral 8x22B open-source (2,341 puntos), Llama 3.2 multimodal (2,891 puntos), DeepSeek R2 (1,847 puntos), y Gemini 2.0 Ultra (1,243 puntos). El tema dominante es el avance de modelos open-source que compiten con los cerrados.',
  herramientas: 'En herramientas destacan: LangGraph 0.3 con soporte multi-modal, Ollama 0.7 con cuantizacion de 2 bits, Hugging Face Inference Endpoints con cuantizacion dinamica, y DSPy alcanzando 10K estrellas. La tendencia es hacer modelos mas accesibles y faciles de desplegar.',
}
```

**Step 2: Wire route in App.tsx**

Replace the Chat Placeholder.

**Step 3: Verify**

Run dev server. Navigate to `/chat`. Click suggestion chip. Verify mock response appears. Type a message and send.

**Step 4: Commit**

```bash
git add frontend/src/pages/Chat.tsx frontend/src/App.tsx
git commit -m "feat: Chat page with mock AI responses and suggestion chips"
```

---

### Task 7: Clean Up Unused Files

**Files:**
- Delete: `frontend/src/pages/Placeholder.tsx`
- Delete: `frontend/src/app/dashboard/data.json`
- Delete: unused dashboard-01 block components that are no longer imported (check imports first)

**Step 1: Remove Placeholder.tsx**

Delete `frontend/src/pages/Placeholder.tsx` — no longer used since all 4 pages are real.

**Step 2: Remove unused dashboard-01 block files**

Check which of these are still imported anywhere:
- `frontend/src/components/app-sidebar.tsx`
- `frontend/src/components/chart-area-interactive.tsx`
- `frontend/src/components/data-table.tsx`
- `frontend/src/components/nav-documents.tsx`
- `frontend/src/components/nav-main.tsx`
- `frontend/src/components/nav-secondary.tsx`
- `frontend/src/components/nav-user.tsx`
- `frontend/src/components/section-cards.tsx`
- `frontend/src/components/site-header.tsx`
- `frontend/src/app/dashboard/data.json`

If none of these are imported by the current App.tsx, Dashboard, Trending, Buscar, or Chat pages, delete them all.

**Step 3: Verify**

Run dev server. All 4 routes should still work.

**Step 4: Commit**

```bash
git add -A frontend/
git commit -m "chore: remove unused Placeholder and dashboard-01 block files"
```

---

### Task 8: Final Verification

**Step 1: Build check**

Run:
```bash
cd frontend && bun run build
```
Expected: Clean build, no errors. Note bundle size.

**Step 2: Visual verification**

Run dev server at port 3000. Check each route:
- [ ] `/` (Latest) — featured card + grid, topic filter works
- [ ] `/trending` — two sections render
- [ ] `/buscar` — search works, filters work
- [ ] `/chat` — suggestion chips work, mock responses appear
- [ ] Mobile nav — hamburger shows on narrow viewport, Sheet opens with links
- [ ] Dark/light toggle works on all pages

**Step 3: Commit if any fixes needed**

```bash
git add frontend/
git commit -m "fix: final adjustments to React frontend v1"
```
