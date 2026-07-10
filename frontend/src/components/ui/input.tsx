import * as React from 'react'
import { cn } from '@/lib/utils'

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn('h-10 rounded-lg border border-zinc-700/80 bg-zinc-950/80 px-3 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-teal-400/55', className)}
      {...props}
    />
  ),
)
Input.displayName = 'Input'

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn('min-h-24 rounded-lg border border-zinc-700/80 bg-zinc-950/80 px-3 py-3 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-teal-400/55', className)}
      {...props}
    />
  ),
)
Textarea.displayName = 'Textarea'
