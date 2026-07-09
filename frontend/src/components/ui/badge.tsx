import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border border-slate-700/80 bg-slate-800/55 px-2.5 py-1 text-xs font-semibold text-slate-300',
        className,
      )}
      {...props}
    />
  )
}
