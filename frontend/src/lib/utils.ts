import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function safeText(value: unknown, fallback = '') {
  return typeof value === 'string' && value.trim() ? value : fallback
}

export function formatScore(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toFixed(2)
  }
  if (typeof value === 'string' && value.trim()) {
    return value
  }
  return '待 Judge'
}
