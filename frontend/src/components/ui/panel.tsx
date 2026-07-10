import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export function Panel({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <section
      className={cn('rounded-lg border border-zinc-800/70 bg-zinc-950/78 shadow-[0_12px_36px_rgba(0,0,0,0.22)]', className)}
      {...props}
    />
  )
}

export function PanelHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('border-b border-zinc-800/70 px-5 py-4', className)} {...props} />
}
