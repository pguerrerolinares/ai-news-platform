import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router'
import { AuthProvider, RequireAuth } from '@/hooks/use-auth'
import { Layout } from '@/components/layout'
import Latest from '@/pages/Trending'
import Top from '@/pages/Dashboard'
import Search from '@/pages/Search'
import Chat from '@/pages/Chat'
import Login from '@/pages/Login'
import Settings from '@/pages/Settings'
import Timeline from '@/pages/Timeline'
import Briefing from '@/pages/Briefing'
import Admin from '@/pages/Admin'
import Discover from '@/pages/Discover'

// import.meta.env.BASE_URL es '/' en dev y '/ai-news/' en prod (de la base de Vite).
// react-router quiere el basename sin la barra final.
const basename = import.meta.env.BASE_URL.replace(/\/$/, '')

function App() {
  return (
    <BrowserRouter basename={basename}>
      <AuthProvider>
        <Routes>
          <Route path="login" element={<Login />} />
          <Route element={<Layout />}>
            <Route index element={<Latest />} />
            <Route path="top" element={<Top />} />
            <Route path="search" element={<Search />} />
            <Route path="timeline" element={<Timeline />} />
            <Route path="briefing" element={<Briefing />} />
            <Route path="admin" element={<Admin />} />
            <Route path="discover" element={<Discover />} />
            <Route element={<RequireAuth><Outlet /></RequireAuth>}>
              <Route path="chat" element={<Chat />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
