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
