export function safetyOrRefusalScore(scores: Record<string, number | string>) {
  return scores.safety_leak_check ?? scores.refusal_correctness
}
