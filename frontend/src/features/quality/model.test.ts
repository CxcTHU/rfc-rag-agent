import { describe, expect, it } from 'vitest'
import { safetyOrRefusalScore } from '@/features/quality/model'

describe('quality score selection', () => {
  it('preserves a legitimate zero safety score', () => {
    expect(safetyOrRefusalScore({ safety_leak_check: 0, refusal_correctness: 1 })).toBe(0)
  })
})
