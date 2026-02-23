import { Button } from '@/components/ui/button'
import { useTheme } from '@/hooks/use-theme'
import { IconMoon, IconSun } from '@tabler/icons-react'
import { motion, AnimatePresence } from 'motion/react'

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      aria-label={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme}
          initial={{ rotate: -90, scale: 0, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={{ rotate: 90, scale: 0, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="flex items-center justify-center"
        >
          {theme === 'dark' ? <IconSun className="size-4" /> : <IconMoon className="size-4" />}
        </motion.span>
      </AnimatePresence>
    </Button>
  )
}
