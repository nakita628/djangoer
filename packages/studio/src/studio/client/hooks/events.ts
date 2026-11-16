import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { useUiStore } from '../lib/index.js'
import { getClientKey, getDbKey, getDocsQueryKey, getSchemaQueryKey } from './index.js'

/**
 * Follows the server's event stream for as long as the Studio is open.
 *
 * `change` says the models were read again. `ready` opens every connection, and a connection is
 * opened again whenever the server restarts — which is what Django's autoreload does when a
 * `models.py` is saved — so a `ready` after the first means the same thing: whatever was read
 * from the server before may no longer hold.
 */
export function useStudioEvents() {
  const queryClient = useQueryClient()
  const setConnection = useUiStore((s) => s.setConnection)
  useEffect(() => {
    const events = new EventSource('/api/schema/events')
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: getSchemaQueryKey() })
      void queryClient.invalidateQueries({ queryKey: getDocsQueryKey() })
      void queryClient.invalidateQueries({ queryKey: getDbKey() })
      void queryClient.invalidateQueries({ queryKey: getClientKey() })
    }
    const seen = { ready: false }
    events.addEventListener('ready', () => {
      setConnection('live')
      // The first `ready` arrives with the page's own first fetches; only a later one is news.
      if (seen.ready) refresh()
      seen.ready = true
    })
    events.addEventListener('change', refresh)
    events.addEventListener('error', () => {
      setConnection('offline')
    })
    return () => {
      events.close()
    }
  }, [queryClient, setConnection])
}
