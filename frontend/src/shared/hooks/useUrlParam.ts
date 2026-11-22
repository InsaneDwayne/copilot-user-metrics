import { useSearchParams } from 'react-router'

/**
 * The URL's search params, plus a setter for one of them that keeps the others and replaces
 * the history entry. `null` removes the param (its default), so shared links stay short.
 * `reset` names params to remove in the same update, e.g. `['page']` when a filter changes.
 */
export function useUrlParam(): [
  URLSearchParams,
  (key: string, value: string | null, reset?: readonly string[]) => void,
] {
  const [params, setParams] = useSearchParams()
  const setParam = (key: string, value: string | null, reset: readonly string[] = []) =>
    setParams(
      (p) => {
        for (const r of reset) p.delete(r)
        if (value === null) p.delete(key)
        else p.set(key, value)
        return p
      },
      { replace: true },
    )
  return [params, setParam]
}
