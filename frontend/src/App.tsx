import { BrowserRouter, Routes, Route } from 'react-router'
import { Layout } from '@/components/layout'
import Dashboard from '@/pages/Dashboard'
import Trending from '@/pages/Trending'
import Buscar from '@/pages/Buscar'
import Chat from '@/pages/Chat'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="trending" element={<Trending />} />
          <Route path="buscar" element={<Buscar />} />
          <Route path="chat" element={<Chat />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
