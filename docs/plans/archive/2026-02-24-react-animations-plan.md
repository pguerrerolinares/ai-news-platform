# React Frontend Animations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add polished Motion animations across all 4 pages: page transitions, staggered card grids, chat animations, theme circular reveal, and micro-interactions.

**Architecture:** Install `motion` (Framer Motion). Create shared animation wrapper components (`AnimatedOutlet`, `AnimatedCardGrid`). Modify existing pages to use them. Theme toggle uses View Transitions API with `flushSync`. All animations respect `prefers-reduced-motion`.

**Tech Stack:** Motion (framer-motion) v11+, View Transitions API, React 19, TypeScript

---

### Task 1: Install Motion

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install motion**

```bash
cd frontend && bun add motion
```

**Step 2: Verify it compiles**

```bash
cd frontend && bun run build
```
Expected: Clean build, no errors.

**Step 3: Commit**

```bash
git add frontend/package.json frontend/bun.lock
git commit -m "feat: install motion (framer-motion) for animations"
```

---

### Task 2: Reduced Motion Hook

**Files:**
- Create: `frontend/src/hooks/use-reduced-motion.ts`

**Step 1: Create the hook**

Create `frontend/src/hooks/use-reduced-motion.ts`:

```typescript
import { useReducedMotion } from 'motion/react'

export { useReducedMotion }

export const noMotion = {
  initial: false as const,
  animate: false as const,
  exit: undefined,
  transition: { duration: 0 },
}
```

This re-exports Motion's built-in hook and provides a `noMotion` preset to disable animations cleanly.

**Step 2: Verify it compiles**

```bash
cd frontend && bun run build
```

**Step 3: Commit**

```bash
git add frontend/src/hooks/use-reduced-motion.ts
git commit -m "feat: add useReducedMotion hook with noMotion preset"
```

---

### Task 3: Page Transitions (AnimatedOutlet)

**Files:**
- Create: `frontend/src/components/animated-outlet.tsx`
- Modify: `frontend/src/components/layout.tsx`

**Step 1: Create AnimatedOutlet**

Create `frontend/src/components/animated-outlet.tsx`:

```tsx
import { useLocation, useOutlet } from 'react-router'
import { AnimatePresence, motion } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'

export function AnimatedOutlet() {
  const location = useLocation()
  const outlet = useOutlet()
  const reduced = useReducedMotion()

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={reduced ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reduced ? undefined : { opacity: 0, y: -8 }}
        transition={{ duration: reduced ? 0 : 0.2, ease: 'easeOut' }}
      >
        {outlet}
      </motion.div>
    </AnimatePresence>
  )
}
```

**Step 2: Update Layout to use AnimatedOutlet**

Replace `frontend/src/components/layout.tsx`:

```tsx
import { AppNav } from '@/components/app-nav'
import { AnimatedOutlet } from '@/components/animated-outlet'

export function Layout() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <AppNav />
      <main className="mx-auto max-w-6xl px-4 py-6 lg:px-6">
        <AnimatedOutlet />
      </main>
    </div>
  )
}
```

Remove the `Outlet` import from `react-router` — it's no longer used directly.

**Step 3: Verify**

```bash
cd frontend && bun run build
```

Run dev server. Navigate between all 4 routes. Each page should fade+slide in/out.

**Step 4: Commit**

```bash
git add frontend/src/components/animated-outlet.tsx frontend/src/components/layout.tsx
git commit -m "feat: page transitions with fade + slide up via AnimatePresence"
```

---

### Task 4: Staggered Card Grid

**Files:**
- Create: `frontend/src/components/animated-card-grid.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/pages/Trending.tsx`
- Modify: `frontend/src/pages/Buscar.tsx`

**Step 1: Create AnimatedCardGrid**

Create `frontend/src/components/animated-card-grid.tsx`:

```tsx
import { motion, AnimatePresence } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'
import type { ReactNode } from 'react'

interface AnimatedCardGridProps {
  children: ReactNode
  /** Unique key to re-trigger animation on filter/search changes */
  animationKey?: string
  className?: string
}

const container = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.05,
    },
  },
}

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
}

export function AnimatedCardGrid({ children, animationKey, className }: AnimatedCardGridProps) {
  const reduced = useReducedMotion()

  if (reduced) {
    return <div className={className}>{children}</div>
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={animationKey}
        className={className}
        variants={container}
        initial="hidden"
        animate="show"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}

export function AnimatedCardItem({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion()

  if (reduced) {
    return <>{children}</>
  }

  return <motion.div variants={item}>{children}</motion.div>
}
```

**Step 2: Update Dashboard.tsx**

In `frontend/src/pages/Dashboard.tsx`:
- Import `AnimatedCardGrid` and `AnimatedCardItem` from `@/components/animated-card-grid`
- Import `motion` from `motion/react` and `useReducedMotion` from `@/hooks/use-reduced-motion`
- Wrap the FeaturedCard in a `motion.div` with `initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: 'easeOut' }}`
- Replace the news grid `<div className="grid gap-4 ...">` with `<AnimatedCardGrid className="grid gap-4 ..." animationKey={activeTopic}>`
- Wrap each `<NewsCard>` in `<AnimatedCardItem>`
- Close with `</AnimatedCardGrid>`

**Step 3: Update Trending.tsx**

Same pattern for both sections in `frontend/src/pages/Trending.tsx`:
- Import `AnimatedCardGrid`, `AnimatedCardItem`
- Wrap each grid in `<AnimatedCardGrid className="grid gap-4 ...">`
- Wrap each `<NewsCard>` in `<AnimatedCardItem>`

**Step 4: Update Buscar.tsx**

Same pattern for `frontend/src/pages/Buscar.tsx`:
- Import `AnimatedCardGrid`, `AnimatedCardItem`
- Use `animationKey={`${query}-${topic}-${sortBy}`}` so animation re-triggers on filter change
- Wrap each `<NewsCard>` in `<AnimatedCardItem>`

**Step 5: Verify**

```bash
cd frontend && bun run build
```

Run dev server. Check:
- `/` — cards stagger in, FeaturedCard slides in first. Change topic filter — cards re-animate.
- `/trending` — both sections stagger
- `/buscar` — search for "LLM", cards stagger in. Change sort — re-animates.

**Step 6: Commit**

```bash
git add frontend/src/components/animated-card-grid.tsx frontend/src/pages/Dashboard.tsx frontend/src/pages/Trending.tsx frontend/src/pages/Buscar.tsx
git commit -m "feat: staggered card grid animations on all pages"
```

---

### Task 5: Chat Animations

**Files:**
- Modify: `frontend/src/pages/Chat.tsx`

**Step 1: Add message entry animations and typing dots**

Rewrite `frontend/src/pages/Chat.tsx`:
- Import `motion, AnimatePresence` from `motion/react`
- Import `useReducedMotion` from `@/hooks/use-reduced-motion`
- Wrap each message `<div>` in a `<motion.div>`:
  - User messages: `initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}`
  - Assistant messages: `initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}`
  - `transition={{ duration: 0.2, ease: 'easeOut' }}`
- Replace "Escribiendo..." text with animated dots:
  ```tsx
  <div className="flex items-center gap-1">
    {[0, 1, 2].map(i => (
      <motion.span
        key={i}
        className="size-1.5 rounded-full bg-muted-foreground"
        animate={{ scale: [1, 1.4, 1] }}
        transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
      />
    ))}
  </div>
  ```
- Wrap suggestion chips container in `motion.div` with staggerChildren:
  ```tsx
  <motion.div
    className="flex flex-wrap justify-center gap-2"
    initial="hidden"
    animate="show"
    variants={{ hidden: {}, show: { transition: { staggerChildren: 0.08 } } }}
  >
    {SUGGESTIONS.map(s => (
      <motion.div key={s} variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}>
        <Button variant="outline" size="sm" onClick={() => send(s)}>
          {s}
        </Button>
      </motion.div>
    ))}
  </motion.div>
  ```
- If `reduced`, skip all motion props (render plain divs)

**Step 2: Verify**

```bash
cd frontend && bun run build
```

Run dev server. Navigate to `/chat`. Click a chip — verify stagger animation. Send message — verify slide-in. Verify typing dots pulse.

**Step 3: Commit**

```bash
git add frontend/src/pages/Chat.tsx
git commit -m "feat: chat message animations, typing dots, staggered chips"
```

---

### Task 6: Theme Circular Reveal

**Files:**
- Modify: `frontend/src/hooks/use-theme.tsx`
- Modify: `frontend/src/components/theme-toggle.tsx`
- Modify: `frontend/src/index.css`

**Step 1: Update use-theme.tsx with flushSync + View Transitions**

Replace `frontend/src/hooks/use-theme.tsx`:

```tsx
import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { flushSync } from 'react-dom'
import type { ReactNode, MouseEvent } from 'react'

type Theme = 'light' | 'dark'

interface ThemeContextValue {
  theme: Theme
  toggleTheme: (e?: MouseEvent) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window !== 'undefined') {
      return (localStorage.getItem('theme') as Theme) || 'dark'
    }
    return 'dark'
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = useCallback((e?: MouseEvent) => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'

    if (
      !e ||
      !document.startViewTransition ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      setTheme(next)
      return
    }

    const x = e.clientX
    const y = e.clientY
    const maxRadius = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y),
    )

    const transition = document.startViewTransition(() => {
      flushSync(() => setTheme(next))
    })

    transition.ready.then(() => {
      document.documentElement.animate(
        {
          clipPath: [
            `circle(0px at ${x}px ${y}px)`,
            `circle(${maxRadius}px at ${x}px ${y}px)`,
          ],
        },
        {
          duration: 500,
          easing: 'ease-out',
          pseudoElement: '::view-transition-new(root)',
        },
      )
    })
  }, [theme])

  return (
    <ThemeContext value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
```

The key fix: `flushSync(() => setTheme(next))` forces React to synchronously update the DOM inside the view transition callback, which is required for the screenshot-based animation to capture the new state.

**Step 2: Update theme-toggle.tsx with icon morph**

Replace `frontend/src/components/theme-toggle.tsx`:

```tsx
import { Button } from '@/components/ui/button'
import { useTheme } from '@/hooks/use-theme'
import { IconMoon, IconSun } from '@tabler/icons-react'
import { motion, AnimatePresence } from 'motion/react'

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      aria-label={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme}
          initial={{ rotate: -90, scale: 0, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={{ rotate: 90, scale: 0, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="flex items-center justify-center"
        >
          {theme === 'dark' ? <IconSun className="size-4" /> : <IconMoon className="size-4" />}
        </motion.span>
      </AnimatePresence>
    </Button>
  )
}
```

**Step 3: Add View Transition CSS**

In `frontend/src/index.css`, after the `@layer base` block, add:

```css
/* Theme circular reveal via View Transitions API */
::view-transition-old(root),
::view-transition-new(root) {
  animation: none;
  mix-blend-mode: normal;
}
::view-transition-new(root) {
  z-index: 1;
}
::view-transition-old(root) {
  z-index: 9999;
}
```

The old screenshot stays on top (z-index: 9999) while the new state is clipped with an expanding circle underneath. The JS `animate()` call in use-theme.tsx applies the `clip-path` to `::view-transition-new(root)`, revealing the new theme as the circle expands.

**Step 4: Verify**

```bash
cd frontend && bun run build
```

Run dev server. Click the theme toggle:
- Circle should expand from click position, revealing new theme
- Sun/moon icon should rotate in/out
- With `prefers-reduced-motion: reduce` in OS settings, toggle should be instant

**Step 5: Commit**

```bash
git add frontend/src/hooks/use-theme.tsx frontend/src/components/theme-toggle.tsx frontend/src/index.css
git commit -m "feat: theme circular reveal with flushSync + icon morph animation"
```

---

### Task 7: Card Micro-interactions (Hover + Tap)

**Files:**
- Modify: `frontend/src/components/news-card.tsx`
- Modify: `frontend/src/components/featured-card.tsx`

**Step 1: Add hover/tap to NewsCard**

In `frontend/src/components/news-card.tsx`:
- Import `motion` from `motion/react`
- Import `useReducedMotion` from `@/hooks/use-reduced-motion`
- Wrap the `<Card>` in `motion.create(Card)` or wrap the entire return in a `<motion.div>` with:
  ```tsx
  const reduced = useReducedMotion()
  // ...
  <motion.div
    whileHover={reduced ? undefined : { y: -2 }}
    whileTap={reduced ? undefined : { scale: 0.98 }}
    transition={{ duration: 0.2 }}
  >
    <Card className="...">
      ...
    </Card>
  </motion.div>
  ```

**Step 2: Add hover to FeaturedCard**

Same pattern in `frontend/src/components/featured-card.tsx`:
```tsx
<motion.div
  whileHover={reduced ? undefined : { y: -3 }}
  whileTap={reduced ? undefined : { scale: 0.99 }}
  transition={{ duration: 0.2 }}
>
  <Card className="...">
    ...
  </Card>
</motion.div>
```

**Step 3: Verify**

```bash
cd frontend && bun run build
```

Run dev server. Hover cards — should lift slightly. Click — subtle scale.

**Step 4: Commit**

```bash
git add frontend/src/components/news-card.tsx frontend/src/components/featured-card.tsx
git commit -m "feat: card hover lift and tap feedback animations"
```

---

### Task 8: Nav Active Indicator Animation

**Files:**
- Modify: `frontend/src/components/app-nav.tsx`

**Step 1: Add Motion layoutId for active nav indicator**

In `frontend/src/components/app-nav.tsx`, for the **desktop** nav links section:
- Import `motion` from `motion/react`
- Instead of applying `bg-primary text-primary-foreground` via className on active links, render a separate `motion.span` with `layoutId="nav-active"` behind the active link:

```tsx
{links.map(({ to, label }) => (
  <NavLink
    key={to}
    to={to}
    end={to === '/'}
    className={({ isActive }) =>
      `relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        isActive
          ? 'text-primary-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-accent'
      }`
    }
  >
    {({ isActive }) => (
      <>
        {isActive && (
          <motion.span
            layoutId="nav-active"
            className="absolute inset-0 rounded-md bg-primary"
            transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }}
          />
        )}
        <span className="relative z-10">{label}</span>
      </>
    )}
  </NavLink>
))}
```

This makes the active background smoothly slide between nav items when navigating.

Keep the mobile Sheet links as-is (no animation needed in the drawer).

**Step 2: Verify**

```bash
cd frontend && bun run build
```

Run dev server (desktop width). Click between nav items — active pill should slide smoothly.

**Step 3: Commit**

```bash
git add frontend/src/components/app-nav.tsx
git commit -m "feat: animated nav active indicator with Motion layoutId"
```

---

### Task 9: Final Verification

**Step 1: Build check**

```bash
cd frontend && bun run build
```

Expected: Clean build, no errors. Bundle should be under 160 kB gzip.

**Step 2: Visual verification**

Run dev server. Check each item:
- [ ] Page transitions: fade + slide between all 4 routes
- [ ] Card stagger: cards animate in on Latest, Trending, Buscar
- [ ] Filter re-animation: change topic on Latest, sort on Buscar — cards re-stagger
- [ ] Chat: messages slide in, typing dots pulse, chips stagger on mount
- [ ] Theme toggle: circular reveal from button, icon rotates
- [ ] Card hover: lift on hover, scale on tap
- [ ] Nav indicator: active pill slides between items
- [ ] Reduced motion: enable in OS settings, all animations should be instant/disabled

**Step 3: Commit if any fixes needed**

```bash
git add frontend/
git commit -m "fix: final adjustments to React frontend animations"
```
