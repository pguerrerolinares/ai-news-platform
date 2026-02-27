import { useState } from 'react'
import { NavLink } from 'react-router'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { ThemeToggle } from '@/components/theme-toggle'
import { useIsMobile } from '@/hooks/use-mobile'
import { useScrollDirection } from '@/hooks/use-scroll-direction'
import { IconMenu2, IconLogout } from '@tabler/icons-react'
import { motion } from 'motion/react'
import { useAuth } from '@/hooks/use-auth'

const links = [
  { to: '/', label: 'Latest' },
  { to: '/trending', label: 'Trending' },
  { to: '/buscar', label: 'Buscar' },
  { to: '/chat', label: 'Chat' },
]

const mobileLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
    isActive
      ? 'bg-primary text-primary-foreground'
      : 'text-muted-foreground hover:text-foreground hover:bg-accent'
  }`

export function AppNav() {
  const isMobile = useIsMobile()
  const [open, setOpen] = useState(false)
  const { logout } = useAuth()
  const scrollDir = useScrollDirection()

  return (
    <header
      className={`sticky z-50 border-b bg-background/80 backdrop-blur-sm transition-[top] duration-300 ${
        scrollDir === 'down' ? '-top-16' : 'top-0'
      }`}
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 lg:px-6">
        <NavLink to="/" className="text-lg font-bold tracking-tight">
          AI News
        </NavLink>
        <Separator orientation="vertical" className="h-5" />

        {isMobile ? (
          <>
            <Sheet open={open} onOpenChange={setOpen}>
              <Button
                variant="ghost"
                size="icon"
                className="size-9"
                onClick={() => setOpen(true)}
              >
                <IconMenu2 className="size-5" />
                <span className="sr-only">Menu</span>
              </Button>
              <SheetContent side="left">
                <SheetHeader>
                  <SheetTitle>AI News</SheetTitle>
                </SheetHeader>
                <nav className="flex flex-col gap-1 px-4">
                  {links.map(({ to, label }) => (
                    <NavLink
                      key={to}
                      to={to}
                      end={to === '/'}
                      className={mobileLinkClass}
                      onClick={() => setOpen(false)}
                    >
                      {label}
                    </NavLink>
                  ))}
                </nav>
              </SheetContent>
            </Sheet>
            <div className="ml-auto flex items-center gap-1">
              <ThemeToggle />
              <Button variant="ghost" size="icon" onClick={logout} aria-label="Cerrar sesion">
                <IconLogout className="size-4" />
              </Button>
            </div>
          </>
        ) : (
          <>
            <nav className="flex items-center gap-1">
              {links.map(({ to, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
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
                          className="absolute inset-0 rounded-md bg-primary"
                          transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }}
                        />
                      )}
                      <span className="relative z-10">{label}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </nav>
            <div className="ml-auto flex items-center gap-1">
              <ThemeToggle />
              <Button variant="ghost" size="icon" onClick={logout} aria-label="Cerrar sesion">
                <IconLogout className="size-4" />
              </Button>
            </div>
          </>
        )}
      </div>
    </header>
  )
}
