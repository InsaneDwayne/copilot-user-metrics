import { useEffect, useState } from 'react'

/** `value`, once it has stopped changing for `delayMs` — for inputs that query the API as you type. */
export function useDebouncedValue<T>(value: T, delayMs = 250): T {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return settled
}
