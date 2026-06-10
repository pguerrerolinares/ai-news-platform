import { NavLink, useLocation, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/theme-toggle'
import { useScrollDirection } from '@/hooks/use-scroll-direction'
import { IconLogin, IconLogout, IconSettings } from '@tabler/icons-react'
import { useAuth } from '@/hooks/use-auth'
import { PillTabs } from '@/components/pill-tabs'

const links = [
  { to: '/', label: 'Latest' },
  { to: '/top', label: 'Top' },
  { to: '/timeline', label: 'Timeline' },
  { to: '/briefing', label: 'Briefing' },
  { to: '/search', label: 'Search' },
  { to: '/discover', label: 'Discover' },
  { to: '/admin', label: 'Admin' },
]

const NAV_ITEMS = links.map(({ to, label }) => ({ value: to, label }))

export function AppNav() {
  const { isFullUser, logout } = useAuth()
  const scrollDir = useScrollDirection()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  // Map the current pathname to the nearest nav value.
  // "/" is exact; all others match if pathname starts with the link's path.
  const activeValue =
    links.find(({ to }) => (to === '/' ? pathname === '/' : pathname.startsWith(to)))?.to ?? '/'

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
      {/* Horizontally scrollable pill nav — same PillTabs component as topic filter */}
      <div className="relative mx-auto max-w-2xl">
        <PillTabs
          items={NAV_ITEMS}
          value={activeValue}
          onValueChange={(to) => navigate(to)}
          className="px-4 pb-0 pt-0"
        />
        <div
          className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-background to-transparent sm:hidden"
          aria-hidden
        />
      </div>
    </header>
  )
}
