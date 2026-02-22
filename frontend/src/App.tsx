import { Button } from '@/components/ui/button'

function App() {
  return (
    <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center gap-4">
      <Button variant="default">Default</Button>
      <Button variant="outline">Outline</Button>
      <Button variant="destructive">Destructive</Button>
    </div>
  )
}

export default App
