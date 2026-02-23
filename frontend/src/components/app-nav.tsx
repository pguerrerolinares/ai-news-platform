import { NavLink } from 'react-router'
import { Separator } from '@/components/ui/separator'
import { ThemeToggle } from '@/components/theme-toggle'
import { IconBolt, IconFlame, IconSearch, IconMessageCircle } from '@tabler/icons-react'

const links = [
  { to: '/', label: 'Hoy', icon: IconBolt },
  { to: '/trending', label: 'Trending', icon: IconFlame },
  { to: '/buscar', label: 'Buscar', icon: IconSearch },
  { to: '/chat', label: 'Chat', icon: IconMessageCircle },
]

export function AppNav() {
  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 lg:px-6">
        <NavLink to="/" className="flex items-center gap-2 font-bold tracking-tight">
          AI News
        </NavLink>
        <Separator orientation="vertical" className="h-5" />
        <nav className="flex items-center gap-1">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                }`
              }
            >
              <Icon className="size-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
