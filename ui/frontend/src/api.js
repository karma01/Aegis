// Thin client for the Aegis FastAPI backend. Vite proxies /api -> :8000.

async function asJson(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || res.statusText)
  }
  return res.json()
}

export const getOptions = () => fetch('/api/options').then(asJson)
export const getSuite = (suite) => fetch(`/api/suite/${suite}`).then(asJson)
export const getMetrics = () => fetch('/api/metrics').then(asJson)
export const getDecisions = (limit = 200) => fetch(`/api/decisions?limit=${limit}`).then(asJson)
export const postRun = (body) =>
  fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(asJson)

export const postCompare = (body) =>
  fetch('/api/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(asJson)

export const getRuns = () => fetch('/api/runs').then(asJson)
export const getRunDetail = (id) => fetch(`/api/runs/detail?id=${encodeURIComponent(id)}`).then(asJson)
