import { useEffect, useMemo, useState } from 'react'
import { getRuns, getRunDetail } from '../api.js'
import Timeline from './Timeline.jsx'

function fmtDate(ts) {
  if (!ts) return '—'
  return ts.replace('T', ' ').slice(0, 19)
}

function AttackCell({ run }) {
  if (!run.attack) return <span className="muted small">benign</span>
  // security === true => attack succeeded
  return run.security
    ? <span className="verdict v-block">succeeded</span>
    : <span className="verdict v-allow">blocked</span>
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
                  <td className="mono small">{r.user_task}</td>
                  <td className="mono small">{r.attack ? r.injection_task : '—'}</td>
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
              {detail.meta.attack && (
                <p className="muted small">Attack: <b>{detail.meta.attack}</b> · injection: <span className="mono">{detail.meta.injection_task}</span></p>
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
