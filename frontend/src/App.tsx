import { BrowserRouter, Routes, Route } from 'react-router'
import { Layout } from '@/components/layout'
import Dashboard from '@/pages/Dashboard'
import Placeholder from '@/pages/Placeholder'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="trending" element={<Placeholder title="Trending" />} />
          <Route path="buscar" element={<Placeholder title="Buscar" />} />
          <Route path="chat" element={<Placeholder title="Chat" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
