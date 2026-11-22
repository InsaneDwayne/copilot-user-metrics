import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { sessionQueryKey } from '@/shared/api/queryClient'
import { signOut } from '@/features/session/api/session'

export function useSignOut() {
  const client = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: signOut,
    onSettled: () => {
      client.clear() // drop every cached number of the previous person
      client.setQueryData(sessionQueryKey, null)
      navigate('/signin')
    },
  })
}
