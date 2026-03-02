import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { AuthProvider, RequireAuth } from '@/hooks/use-auth'
import { Layout } from '@/components/layout'
import Latest from '@/pages/Trending'
import Top from '@/pages/Dashboard'
import Search from '@/pages/Search'
import Chat from '@/pages/Chat'
import Login from '@/pages/Login'
import Settings from '@/pages/Settings'
import Timeline from '@/pages/Timeline'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="login" element={<Login />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route index element={<Latest />} />
            <Route path="top" element={<Top />} />
            <Route path="search" element={<Search />} />
            <Route path="chat" element={<Chat />} />
            <Route path="timeline" element={<Timeline />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
