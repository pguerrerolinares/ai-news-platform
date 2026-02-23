import { motion, AnimatePresence } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'
import type { ReactNode } from 'react'

interface AnimatedCardGridProps {
  children: ReactNode
  animationKey?: string
  className?: string
}

const container = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.05,
    },
  },
}

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' as const } },
}

export function AnimatedCardGrid({ children, animationKey, className }: AnimatedCardGridProps) {
  const reduced = useReducedMotion()

  if (reduced) {
    return <div className={className}>{children}</div>
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={animationKey}
        className={className}
        variants={container}
        initial="hidden"
        animate="show"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}

export function AnimatedCardItem({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion()

  if (reduced) {
    return <>{children}</>
  }

  return <motion.div variants={item}>{children}</motion.div>
}
