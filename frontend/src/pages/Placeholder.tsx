import { Card } from '@/components/ui/card'
import { IconHammer } from '@tabler/icons-react'

export default function Placeholder({ title }: { title: string }) {
  return (
    <Card className="flex flex-col items-center gap-3 py-20 text-muted-foreground">
      <IconHammer className="size-8" />
      <p className="text-lg font-medium">{title}</p>
      <p className="text-sm">Proximamente</p>
    </Card>
  )
}
