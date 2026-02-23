# React Frontend Animations — Design Doc

## Goal

Add polished animations across the entire React frontend: page transitions, staggered card grids, chat animations, theme circular reveal, and micro-interactions. Single library: Motion (Framer Motion).

## Context

The React frontend v1 has 4 working pages (Latest, Trending, Buscar, Chat) with mock data. All route changes and state updates are instant with no animation. The theme toggle is instant. The UX feels abrupt. This milestone adds motion to make the app feel fluid and professional.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Animation library | Motion (framer-motion) | Standard in React ecosystem. ~33 kB gzip. Covers all needs: layout, presence, gestures, stagger. |
| Theme toggle | Circular reveal (View Transitions API) | Premium feel. Uses `flushSync` for React 19 compat. Fallback to instant. |
| Page transitions | Fade + slide up | Subtle, guides the eye, doesn't distract from content. |
| Card entry | Staggered fade + slide | Makes grids legible — cards appear sequentially, not all at once. |
| Reduced motion | Respect `prefers-reduced-motion` | Accessibility requirement. Disable all motion when user prefers reduced. |

## Animation Spec

### 1. Theme Toggle — Circular Reveal

- `document.startViewTransition()` with `flushSync()` inside callback
- `clip-path: circle()` from click position, expanding to cover viewport
- Duration: 500ms ease-out
- Sun/moon icon: Motion rotate(90deg) + scale(0→1) transition, 300ms
- Fallback: instant toggle + no icon animation on unsupported browsers
- CSS: `::view-transition-old(root)` z-index stacking for proper layering

### 2. Page Transitions — Fade + Slide Up

- `AnimatePresence mode="wait"` wrapping `<Outlet />` in Layout
- Route key: `useLocation().pathname`
- Exit animation: opacity 1→0, y: 0→-8, duration 150ms
- Enter animation: opacity 0→1, y: 12→0, duration 200ms
- Easing: ease-out

### 3. Card Grid — Staggered Entry

- Container: `staggerChildren: 0.05`
- NewsCard: opacity 0→1, y: 20→0, duration 300ms
- FeaturedCard: opacity 0→1, y: 30→0, duration 400ms
- Trigger: on mount and on filter/search changes
- Use `AnimatePresence` for cards leaving/entering on filter change

### 4. Chat Animations

- User messages: slide in from right (x: 20→0) + fade, 200ms
- Assistant messages: slide in from left (x: -20→0) + fade, 200ms
- Typing indicator: pulsing dots with Motion loop
- Suggestion chips: staggered fade in (staggerChildren: 0.08), 200ms each

### 5. Micro-interactions

- Card hover: `whileHover={{ y: -2, boxShadow: "..." }}` via Motion, 200ms
- Card tap: `whileTap={{ scale: 0.98 }}`, 100ms
- Nav active link: bottom border slide via Motion `layoutId`
- Buttons: `whileTap={{ scale: 0.97 }}`, 100ms
- Badge on filter change: `AnimatePresence` fade + scale

### 6. Reduced Motion

- Custom hook: `useReducedMotion()` from Motion
- When active: all durations → 0, all transforms → none
- Applied at the animation variant level, not by removing components

## Components to Create/Modify

### New
- `frontend/src/components/animated-outlet.tsx` — `AnimatePresence` + `motion.div` wrapper for route transitions
- `frontend/src/components/animated-card-grid.tsx` — Staggered grid container
- `frontend/src/components/animated-chat-message.tsx` — Message entry animation

### Modify
- `frontend/src/components/layout.tsx` — Use AnimatedOutlet
- `frontend/src/components/app-nav.tsx` — Motion `layoutId` on active indicator
- `frontend/src/components/news-card.tsx` — Wrap in `motion.div` with hover/tap
- `frontend/src/components/featured-card.tsx` — Wrap in `motion.div`
- `frontend/src/hooks/use-theme.tsx` — Circular reveal with `flushSync`
- `frontend/src/components/theme-toggle.tsx` — Icon morph animation
- `frontend/src/pages/Dashboard.tsx` — Use AnimatedCardGrid
- `frontend/src/pages/Trending.tsx` — Use AnimatedCardGrid
- `frontend/src/pages/Buscar.tsx` — Use AnimatedCardGrid
- `frontend/src/pages/Chat.tsx` — Use AnimatedChatMessage, typing dots, staggered chips
- `frontend/src/index.css` — View Transition CSS for theme toggle

## Out of Scope

- GSAP or other animation libraries
- Scroll-triggered animations (not needed for news reader)
- Text shimmer/scramble effects (distracting for content consumption)
- Lottie/SVG animations
- Page loading skeletons (backlog)

## Success Criteria

1. All page navigations animate with fade + slide up
2. Card grids stagger in on mount and filter change
3. Theme toggle does circular reveal from button position
4. Chat messages animate in from sides
5. Cards have hover lift and tap feedback
6. All animations disabled when `prefers-reduced-motion: reduce`
7. Build stays under 160 kB gzip (current: ~124 kB + Motion ~33 kB)
