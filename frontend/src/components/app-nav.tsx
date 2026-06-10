import { NavLink, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/theme-toggle'
import { useScrollDirection } from '@/hooks/use-scroll-direction'
import { IconLogin, IconLogout, IconSettings } from '@tabler/icons-react'
import { motion } from 'motion/react'
import { useAuth } from '@/hooks/use-auth'

const links = [
  { to: '/', label: 'Latest' },
  { to: '/top', label: 'Top' },
  { to: '/timeline', label: 'Timeline' },
  { to: '/briefing', label: 'Briefing' },
  { to: '/search', label: 'Search' },
]

export function AppNav() {
  const { isFullUser, logout } = useAuth()
  const scrollDir = useScrollDirection()
  const navigate = useNavigate()

  return (
    <header
      className={`sticky z-50 bg-background/80 backdrop-blur-sm transition-[top] duration-300 ${
        scrollDir === 'down' ? '-top-24' : 'top-0'
      }`}
    >
      <div className="mx-auto flex h-12 max-w-2xl items-center px-4">
        <NavLink to="/" className="text-lg font-bold tracking-tight">
          AI News
        </NavLink>
        <div className="ml-auto flex items-center gap-1">
          <ThemeToggle />
          {isFullUser ? (
            <>
              <NavLink to="/settings">
                <Button variant="ghost" size="icon" className="size-8" aria-label="Settings">
                  <IconSettings className="size-4" />
                </Button>
              </NavLink>
              <Button variant="ghost" size="icon" className="size-8" onClick={logout} aria-label="Log out">
                <IconLogout className="size-4" />
              </Button>
            </>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-sm"
              onClick={() => navigate('/login')}
            >
              <IconLogin className="size-4" />
              Sign in
            </Button>
          )}
        </div>
      </div>
      {/* Horizontally scrollable on mobile so the nav scales as sections are
          added; a right-edge fade hints there's more to swipe. */}
      <div className="relative mx-auto max-w-2xl">
        <nav className="flex gap-1 overflow-x-auto px-4 pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {links.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `relative shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                  isActive
                    ? 'text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute inset-0 rounded-full bg-primary"
                      transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }}
                    />
                  )}
                  <span className="relative z-10">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div
          className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-background to-transparent sm:hidden"
          aria-hidden
        />
      </div>
    </header>
  )
}
