import { useEffect, useState } from 'react'
import { getMetrics } from '../api.js'

const ORDER = ['baseline', 'moderator', 'sandbox', 'combined']

function pct(x) {
  return x === null || x === undefined ? '—' : `${(x * 100).toFixed(1)}%`
}
function pctPts(x) {
  return x === null || x === undefined ? '—' : `${x >= 0 ? '+' : ''}${x.toFixed(1)}%`
}
function secs(x) {
  return x === null || x === undefined ? '—' : `${x.toFixed(2)}s`
}

function Bar({ value, kind }) {
  // value is a 0..1 fraction. ASR: lower=better (red); utility: higher=better (green).
  const w = Math.max(0, Math.min(1, value || 0)) * 100
  return (
    <div className="bar-track">
      <div className={`bar-fill ${kind}`} style={{ width: `${w}%` }} />
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getMetrics().then(setData).catch((e) => setError(String(e)))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!data) return <p className="muted">Loading metrics…</p>

  const configs = data.configs || {}
  const labels = [
    ...ORDER.filter((c) => c in configs),
    ...Object.keys(configs).filter((c) => !ORDER.includes(c)),
  ]
  if (labels.length === 0) {
    return <p className="muted">No runs found yet. Run some tasks (ideally <code>--config all</code>) to populate the ablation table.</p>
  }

  return (
    <div className="dashboard">
      <div className="panel">
        <h2>Ablation metrics</h2>
        <p className="muted small">baseline = <b>{data.baseline}</b>. ASR lower is better; utility higher is better.</p>
        <table className="metrics-table">
          <thead>
            <tr>
              <th>Config</th>
              <th>Benign utility</th>
              <th>ASR</th>
              <th>Atk utility</th>
              <th>Latency</th>
              <th>Lat. overhead</th>
              <th>Util. drop</th>
              <th>n (b/a)</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((label) => {
              const m = configs[label]
              return (
                <tr key={label}>
                  <td className="mono">{label}</td>
                  <td>
                    <div className="cell-bar">
                      <span>{pct(m.benign_utility)}</span>
                      <Bar value={m.benign_utility} kind="good" />
                    </div>
                  </td>
                  <td>
                    <div className="cell-bar">
                      <span>{pct(m.asr)}</span>
                      <Bar value={m.asr} kind="bad" />
                    </div>
                  </td>
                  <td>{pct(m.attack_utility)}</td>
                  <td>{secs(m.avg_latency)}</td>
                  <td>{pctPts(m.latency_overhead_pct)}</td>
                  <td>{pctPts(m.utility_drop_pct)}</td>
                  <td className="muted">{m.n_benign}/{m.n_attack}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
