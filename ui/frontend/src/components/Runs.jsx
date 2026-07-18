import { useEffect, useMemo, useState } from 'react'
import { getRuns, getRunDetail } from '../api.js'
import Timeline from './Timeline.jsx'

function fmtDate(ts) {
  if (!ts) return '—'
  return ts.replace('T', ' ').slice(0, 19)
}

function trunc(s, n = 48) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '…' : s
}

function isProbe(run) {
  // An injection task run as a standalone task (AgentDojo accomplishability
  // check) — not a genuine user request; its goal is itself an egress action.
  return !run.attack && String(run.user_task).startsWith('injection_task')
}

function AttackCell({ run }) {
  if (run.attack) {
    // security === true => attack succeeded
    return run.security
      ? <span className="verdict v-block">succeeded</span>
      : <span className="verdict v-allow">blocked</span>
  }
  if (isProbe(run)) {
    return (
      <span
        className="badge badge-grey"
        title="Injection task run as a standalone task (accomplishability probe). Under a defended config Aegis blocks its egress action, so utility shows ✗ — expected, and excluded from the benign-utility metric."
      >
        probe
      </span>
    )
  }
  return <span className="muted small">benign</span>
}

export default function Runs() {
  const [runs, setRuns] = useState(null)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState({ suite: '', config: '', kind: '' })
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  useEffect(() => {
    getRuns().then((d) => setRuns(d.runs)).catch((e) => setError(String(e)))
  }, [])

  const suites = useMemo(() => [...new Set((runs || []).map((r) => r.suite))].sort(), [runs])
  const configs = useMemo(() => [...new Set((runs || []).map((r) => r.config))].sort(), [runs])

  const shown = useMemo(() => {
    return (runs || []).filter((r) =>
      (!filter.suite || r.suite === filter.suite) &&
      (!filter.config || r.config === filter.config) &&
      (!filter.kind || (filter.kind === 'attack' ? !!r.attack : !r.attack)))
  }, [runs, filter])

  function open(run) {
    setSelected(run.id)
    setDetail(null)
    setLoadingDetail(true)
    getRunDetail(run.id)
      .then(setDetail)
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingDetail(false))
  }

  if (error) return <p className="error">{error}</p>
  if (!runs) return <p className="muted">Loading runs…</p>
  if (runs.length === 0) {
    return <div className="placeholder">No runs recorded yet. Run a task (Live Tester) or an ablation to populate the report browser.</div>
  }

  const setF = (k) => (e) => setFilter((f) => ({ ...f, [k]: e.target.value }))

  return (
    <div className="runs">
      <section className="panel">
        <div className="runs-head">
          <h2>Run reports <span className="muted small">({shown.length} of {runs.length})</span></h2>
          <div className="runs-filters">
            <select value={filter.suite} onChange={setF('suite')}>
              <option value="">all suites</option>
              {suites.map((s) => <option key={s}>{s}</option>)}
            </select>
            <select value={filter.config} onChange={setF('config')}>
              <option value="">all configs</option>
              {configs.map((c) => <option key={c}>{c}</option>)}
            </select>
            <select value={filter.kind} onChange={setF('kind')}>
              <option value="">benign + attack</option>
              <option value="benign">benign only</option>
              <option value="attack">attack only</option>
            </select>
          </div>
        </div>
        <p className="muted small" style={{ margin: '0 0 10px' }}>
          Rows tagged <span className="badge badge-grey">probe</span> are injection tasks run as standalone
          tasks — a ✗ there means Aegis blocked their egress (expected; excluded from benign utility).
        </p>
        <div className="runs-table-wrap">
          <table className="decisions runs-table">
            <thead>
              <tr>
                <th>Date</th><th>Suite</th><th>Config</th><th>User task</th>
                <th>Injection</th><th>Utility</th><th>Attack</th><th>Time</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id} className={selected === r.id ? 'row-sel' : ''} onClick={() => open(r)}>
                  <td className="small">{fmtDate(r.timestamp)}</td>
                  <td>{r.suite}</td>
                  <td className="mono">{r.config}</td>
                  <td className="small" title={`${r.user_task}: ${r.user_task_prompt || ''}`}>
                    {trunc(r.user_task_prompt) || <span className="mono">{r.user_task}</span>}
                  </td>
                  <td className="small" title={r.attack ? `${r.injection_task}: ${r.injection_task_goal || ''}` : ''}>
                    {r.attack ? (trunc(r.injection_task_goal, 40) || <span className="mono">{r.injection_task}</span>) : '—'}
                  </td>
                  <td>{r.utility ? <span className="verdict v-allow">✓</span> : <span className="verdict v-block">✗</span>}</td>
                  <td><AttackCell run={r} /></td>
                  <td className="small muted">{r.duration ? `${r.duration.toFixed(1)}s` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selected && (
        <section className="panel">
          {loadingDetail && <p className="muted">Loading report…</p>}
          {detail && (
            <>
              <div className="result-head">
                <h2 className="mono">{detail.meta.suite} / {detail.meta.config} / {detail.meta.user_task}</h2>
                <div className="chips">
                  <span className={`chip ${detail.meta.utility ? 'chip-good' : 'chip-bad'}`}>utility: {String(detail.meta.utility)}</span>
                  {detail.meta.attack && (
                    <span className={`chip ${detail.meta.security ? 'chip-bad' : 'chip-good'}`}>
                      attack: {detail.meta.security ? 'succeeded' : 'blocked'}
                    </span>
                  )}
                  {detail.blocked_count > 0 && <span className="chip chip-good">🛡 {detail.blocked_count} blocked</span>}
                  <span className="chip">{fmtDate(detail.meta.timestamp)}</span>
                </div>
              </div>
              <p className="small"><b>User task</b> <span className="mono muted">{detail.meta.user_task}</span> — {detail.meta.user_task_prompt}</p>
              {detail.meta.attack && (
                <p className="small"><b>Injection</b> <span className="mono muted">{detail.meta.injection_task}</span> — {detail.meta.injection_task_goal} <span className="muted">(attack: {detail.meta.attack})</span></p>
              )}
              <h3>Conversation</h3>
              <Timeline messages={detail.messages} />
            </>
          )}
        </section>
      )}
    </div>
  )
}
