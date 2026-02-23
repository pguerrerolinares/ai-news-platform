import { Button } from '@/components/ui/button'
import { useTheme } from '@/hooks/use-theme'
import { IconMoon, IconSun } from '@tabler/icons-react'

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      aria-label={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
    >
      {theme === 'dark' ? <IconSun className="size-4" /> : <IconMoon className="size-4" />}
    </Button>
  )
}
