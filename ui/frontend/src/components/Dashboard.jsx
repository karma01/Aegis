import { useEffect, useState } from 'react'
import { getMetrics } from '../api.js'

const ORDER = ['baseline', 'moderator', 'sandbox', 'combined']
const pct0 = (x) => (x == null ? '—' : `${(x * 100).toFixed(0)}%`)
const pct1 = (x) => (x == null ? '—' : `${(x * 100).toFixed(1)}%`)
const secs = (x) => (x == null ? '—' : `${x.toFixed(2)}s`)
const pp = (x) => (x == null ? '—' : `${x >= 0 ? '+' : ''}${x.toFixed(1)}%`)

function BarRows({ configs, labels, field, kind, fmt }) {
  const vals = labels.map((l) => configs[l]?.[field] ?? 0)
  const max = Math.max(0.0001, ...vals, field === 'asr' || field === 'benign_utility' ? 1 : 0)
  return (
    <div className="chart">
      {labels.map((l) => {
        const v = configs[l]?.[field]
        return (
          <div className="chart-row" key={l}>
            <div className="chart-label">{l}</div>
            <div className="chart-track">
              <div className={`chart-fill ${kind}`} style={{ width: `${((v ?? 0) / max) * 100}%` }} />
            </div>
            <div className="chart-val">{fmt(v)}</div>
          </div>
        )
      })}
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
    return (
      <div className="placeholder">
        No runs found yet. Run an ablation (e.g. <code>--config all</code>) to populate the dashboard.
      </div>
    )
  }

  const base = configs[data.baseline] || configs[labels[0]]
  const defended = labels.filter((l) => l !== data.baseline).map((l) => configs[l])
  const bestAsr = defended.length ? Math.min(...defended.map((c) => (c.asr == null ? 1 : c.asr))) : null
  const minBenign = Math.min(...labels.map((l) => (configs[l].benign_utility == null ? 1 : configs[l].benign_utility)))
  const hasAttacks = labels.some((l) => (configs[l].n_attack || 0) > 0)

  return (
    <div className="dashboard">
      <div className="kpi-row">
        <div className="kpi bad">
          <div className="kpi-label">Baseline ASR</div>
          <div className="kpi-value">{pct0(base?.asr)}</div>
          <div className="kpi-sub">undefended attack success</div>
        </div>
        <div className="kpi good">
          <div className="kpi-label">Aegis ASR</div>
          <div className="kpi-value">{pct0(bestAsr)}</div>
          <div className="kpi-sub">best defended config</div>
        </div>
        <div className="kpi good">
          <div className="kpi-label">Benign utility</div>
          <div className="kpi-value">{pct0(minBenign)}</div>
          <div className="kpi-sub">preserved across configs</div>
        </div>
      </div>

      {hasAttacks && (
        <div className="panel">
          <h2>Attack Success Rate by config</h2>
          <p className="muted small">Lower is better. baseline = <b>{data.baseline}</b>.</p>
          <BarRows configs={configs} labels={labels} field="asr" kind="bad" fmt={pct1} />
        </div>
      )}

      <div className="panel">
        <h2>Benign task utility by config</h2>
        <p className="muted small">Higher is better — a good defense preserves it.</p>
        <BarRows configs={configs} labels={labels} field="benign_utility" kind="good" fmt={pct1} />
      </div>

      <div className="panel">
        <h2>Full metrics</h2>
        <table className="metrics-table">
          <thead>
            <tr>
              <th>Config</th><th>Benign</th><th>ASR</th><th>Atk util</th>
              <th>Latency</th><th>Lat. ovh</th><th>Util. drop</th><th>n (b/a)</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((label) => {
              const m = configs[label]
              return (
                <tr key={label}>
                  <td className="mono">{label}</td>
                  <td>{pct1(m.benign_utility)}</td>
                  <td>{pct1(m.asr)}</td>
                  <td>{pct1(m.attack_utility)}</td>
                  <td>{secs(m.avg_latency)}</td>
                  <td>{pp(m.latency_overhead_pct)}</td>
                  <td>{pp(m.utility_drop_pct)}</td>
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
