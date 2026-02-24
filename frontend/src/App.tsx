import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { AuthProvider, RequireAuth } from '@/hooks/use-auth'
import { Layout } from '@/components/layout'
import Dashboard from '@/pages/Dashboard'
import Trending from '@/pages/Trending'
import Buscar from '@/pages/Buscar'
import Chat from '@/pages/Chat'
import Login from '@/pages/Login'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="login" element={<Login />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route index element={<Dashboard />} />
            <Route path="trending" element={<Trending />} />
            <Route path="buscar" element={<Buscar />} />
            <Route path="chat" element={<Chat />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
