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
import { IconMenu2 } from '@tabler/icons-react'

const links = [
  { to: '/', label: 'Latest' },
  { to: '/trending', label: 'Trending' },
  { to: '/buscar', label: 'Buscar' },
  { to: '/chat', label: 'Chat' },
]

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
    isActive
      ? 'bg-primary text-primary-foreground'
      : 'text-muted-foreground hover:text-foreground hover:bg-accent'
  }`

export function AppNav() {
  const isMobile = useIsMobile()
  const [open, setOpen] = useState(false)

  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-sm">
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
                      className={linkClass}
                      onClick={() => setOpen(false)}
                    >
                      {label}
                    </NavLink>
                  ))}
                </nav>
              </SheetContent>
            </Sheet>
            <div className="ml-auto">
              <ThemeToggle />
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
                  className={linkClass}
                >
                  {label}
                </NavLink>
              ))}
            </nav>
            <div className="ml-auto">
              <ThemeToggle />
            </div>
          </>
        )}
      </div>
    </header>
  )
}
