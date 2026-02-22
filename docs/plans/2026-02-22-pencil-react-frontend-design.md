# Pencil + React Frontend Experiment — Design Doc

## Goal

Validate the Pencil design-to-code workflow by building the Dashboard page using Vite + React + Shadcn + Tailwind. Use Shadcn blocks as a starting point, customize visually in Pencil, and generate production-ready React code. Same mock data as the Angular frontend, completely fresh design aesthetic.

## Context

The current Angular frontend (`web/`) works but the design workflow (Stitch → generate → manual CSS) is friction-heavy. Pencil promises a tighter loop: design visually in your IDE, generate pixel-perfect React code via MCP. This experiment validates whether Pencil delivers on that promise before committing to a full migration.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | Vite + React 19 | SPA like current Angular app. No SSR overhead. Fastest dev server. |
| Styling | Tailwind CSS 4 | Pencil's primary styling target. Utility-first, token-based. |
| Components | Shadcn UI | Copy-paste components you own. Best Pencil integration. Blocks for quick starts. |
| Routing | React Router | Only needed if we add more pages later. Dashboard-only for now. |
| Data | Mock data | Port the 20 mock news items + briefing from Angular mock interceptor. No backend needed. |
| Design | Fresh via Pencil | Keep the same data model but explore new aesthetics. Not bound to editorial style. |
| Location | `frontend/` | Independent folder. No shared deps with `web/`. |

## Architecture

### Stack

- **Runtime:** Vite 6 + React 19 + TypeScript
- **Styling:** Tailwind CSS 4
- **Components:** Shadcn UI (Radix primitives underneath)
- **Design:** Pencil (.pen files in repo)
- **MCP Servers:** shadcn-ui-server + Pencil MCP (auto-connects)

### Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── ui/            # Shadcn primitives (button, card, chart, etc.)
│   ├── pages/
│   │   └── Dashboard.tsx  # Main experiment page
│   ├── lib/
│   │   ├── mock-data.ts   # 20 news items + briefing stats (ported from Angular)
│   │   └── utils.ts       # cn() helper, formatters
│   ├── hooks/             # Custom React hooks (if needed)
│   ├── App.tsx            # Router + layout shell
│   └── main.tsx           # Entry point
├── design.pen             # Pencil design file for dashboard
├── components.json        # Shadcn configuration
├── tailwind.config.ts
├── tsconfig.json
├── vite.config.ts
└── package.json
```

### MCP Server Setup (Step 0)

**Shadcn UI MCP Server:**
```bash
claude mcp add-json "shadcn-ui-server" '{"command":"npx","args":["-y","shadcn-ui-mcp-server"]}'
```

**Pencil MCP:** Auto-connects when Pencil extension is installed and a `.pen` file is open.

## Workflow

1. **Setup** — Create Vite + React project, install Tailwind + Shadcn, configure MCP servers
2. **Blocks** — Install Shadcn dashboard block as starting point (`npx shadcn add dashboard-01` or similar)
3. **Mock data** — Port the 20 mock news items + briefing stats from `web/src/app/interceptors/mock-api.interceptor.ts`
4. **Pencil design** — Open the dashboard block in Pencil, customize the design visually (layout, colors, typography)
5. **Code generation** — Generate React code from Pencil design via Cmd/Ctrl+K
6. **Wire data** — Connect mock data to the generated components
7. **Verify** — Run `npm run dev`, verify dashboard renders with data, test dark/light mode

## Data Model (from Angular)

```typescript
interface NewsItem {
  id: string;
  title: string;
  summary: string | null;
  url: string;
  source: string;
  topic: string | null;
  relevance_score: number;
  dev_value_score: number;
  credibility_score: number;
  priority: string;
  is_trending: boolean;
  published_at: string;
  author: string | null;
  score: number | null;
}

interface Briefing {
  id: string;
  date: string;
  total_items: number;
  items_after_dedup: number;
  items_filtered: number;
  trending_count: number;
  pipeline_duration_seconds: number;
  sources_used: string[];
  items: NewsItem[];
}
```

## Scope

### In scope
- Vite + React + Tailwind + Shadcn project setup
- MCP server configuration (Shadcn + Pencil)
- Dashboard page with mock data
- Shadcn block as starting point
- Pencil visual customization
- Dark/light mode toggle

### Out of scope
- Authentication / login page
- Other pages (archive, search, analytics, chat)
- Real API connection / proxy to Python backend
- Deployment / CI
- Shared code between `web/` and `frontend/`
- Angular frontend modifications

## Success Criteria

1. Dashboard page renders 20 mock news items with stats
2. Design was created/customized visually in Pencil
3. Code was generated (at least partially) from Pencil design
4. Dark/light mode works
5. The workflow feels faster and more intuitive than Stitch + Angular Material
