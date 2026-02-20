/**
 * Wrapper om fetch() met JSON body en foutafhandeling.
 */
export async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== null) opts.body = JSON.stringify(body)
  const res = await fetch(path, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export const apiGet    = (path)        => api('GET',    path)
export const apiPost   = (path, body)  => api('POST',   path, body)
export const apiDelete = (path)        => api('DELETE', path)
export const apiPut    = (path, body)  => api('PUT',    path, body)
