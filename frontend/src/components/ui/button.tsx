import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-semibold transition disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'border-teal-400/45 bg-teal-400/12 text-teal-100 hover:border-teal-300/65 hover:bg-teal-400/18',
        secondary: 'border-zinc-700/80 bg-zinc-900/68 text-zinc-300 hover:border-zinc-600 hover:bg-zinc-800/76',
        ghost: 'border-transparent bg-transparent text-zinc-400 hover:bg-zinc-800/58 hover:text-zinc-200',
        danger: 'border-rose-500/45 bg-rose-500/10 text-rose-100 hover:bg-rose-500/16',
      },
      size: {
        default: 'h-10 px-4',
        sm: 'h-8 px-3 text-xs',
        icon: 'h-10 w-10 px-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return <Comp ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />
  },
)
Button.displayName = 'Button'
