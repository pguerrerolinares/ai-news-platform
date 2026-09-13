import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { Layout } from '@/components/layout'
import Latest from '@/pages/Trending'
import Top from '@/pages/Dashboard'
import Search from '@/pages/Search'
import Timeline from '@/pages/Timeline'
import Briefing from '@/pages/Briefing'
import Discover from '@/pages/Discover'

// Admin pulls in recharts; loaded on demand so it doesn't bloat the main bundle.
const Admin = lazy(() => import('@/pages/Admin'))

function RouteFallback() {
  return <div className="mx-auto max-w-2xl px-4 py-12 text-sm text-muted-foreground">Loading…</div>
}

// import.meta.env.BASE_URL es '/' en dev y '/ai-news/' en prod (de la base de Vite).
// react-router quiere el basename sin la barra final.
const basename = import.meta.env.BASE_URL.replace(/\/$/, '')

function App() {
  return (
    <BrowserRouter basename={basename}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Latest />} />
          <Route path="top" element={<Top />} />
          <Route path="search" element={<Search />} />
          <Route path="timeline" element={<Timeline />} />
          <Route path="briefing" element={<Briefing />} />
          <Route
            path="admin"
            element={
              <Suspense fallback={<RouteFallback />}>
                <Admin />
              </Suspense>
            }
          />
          <Route path="discover" element={<Discover />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
