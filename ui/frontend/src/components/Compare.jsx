import { useEffect, useState } from 'react'
import { getOptions, getSuite, postCompare } from '../api.js'
import Timeline from './Timeline.jsx'
import DecisionsTable from './DecisionsTable.jsx'
import PipelineFlow from './PipelineFlow.jsx'

export default function Compare() {
  const [options, setOptions] = useState(null)
  const [tasks, setTasks] = useState({ user_tasks: [], injection_tasks: [] })
  const [form, setForm] = useState({
    suite: 'workspace',
    user_task: '',
    model: 'VLLM_PARSED',
    attack: 'ignore_previous',
    injection_task: '',
    escalate: 'block',
  })
  const [running, setRunning] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getOptions()
      .then((o) => {
        setOptions(o)
        setForm((f) => ({ ...f, attack: o.attacks[0] || 'ignore_previous' }))
      })
      .catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    if (!form.suite) return
    getSuite(form.suite)
      .then((t) => {
        setTasks(t)
        setForm((f) => ({
          ...f,
          user_task: t.user_tasks[0] || '',
          injection_task: t.injection_tasks[0] || '',
        }))
      })
      .catch((e) => setError(String(e)))
  }, [form.suite])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function run() {
    setRunning(true)
    setError(null)
    setData(null)
    try {
      setData(await postCompare(form))
    } catch (e) {
      setError(String(e))
    } finally {
      setRunning(false)
    }
  }

  if (!options) return <p className="muted">{error || 'Loading…'}</p>

  return (
    <div className="compare">
      <section className="panel controls-row">
        <div className="controls-row-fields">
          <label>Suite
            <select value={form.suite} onChange={set('suite')}>
              {options.suites.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label>User task
            <select value={form.user_task} onChange={set('user_task')}>
              {tasks.user_tasks.map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <label>Attack
            <select value={form.attack} onChange={set('attack')}>
              {options.attacks.map((a) => <option key={a}>{a}</option>)}
            </select>
          </label>
          <label>Injection task
            <select value={form.injection_task} onChange={set('injection_task')}>
              {tasks.injection_tasks.map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <label>Model
            <select value={form.model} onChange={set('model')}>
              {options.models.map((m) => <option key={m}>{m}</option>)}
            </select>
          </label>
        </div>
        <button className="run-btn compare-btn" onClick={run} disabled={running || !form.user_task}>
          {running ? 'Running both…' : 'Run baseline vs combined'}
        </button>
        {error && <p className="error">{error}</p>}
        <p className="muted small">Runs the same task + attack undefended, then with all Aegis layers. Needs the model server up.</p>
      </section>

      {data && (
        <div className="compare-grid">
          <Pane title="Baseline (undefended)" side="left" run={data.left} />
          <Pane title="Aegis (combined)" side="right" run={data.right} />
        </div>
      )}
    </div>
  )
}

function aegisBlocks(decisions) {
  return (decisions || []).filter(
    (d) => (d.layer === 'enforcement' || d.layer === 'sandbox') && d.enforced === 'BLOCK',
  )
}

function Pane({ title, side, run }) {
  // AgentDojo `security` is the attack-success flag: True => injection accomplished.
  const succeeded = run.result.security === true // attack succeeded
  const defended = run.result.security === false // attack failed / blocked
  const banner =
    succeeded ? { cls: 'banner-bad', text: '⚠ Attack succeeded' }
    : defended ? { cls: 'banner-good', text: '🛡 Attack blocked' }
    : { cls: 'banner-neutral', text: 'No attack result' }

  // Reliable, decision-log-derived signal of what Aegis actually did — robust to
  // the noisy `security` metric on weak models.
  const blocks = aegisBlocks(run.decisions)
  const blockedTools = [...new Set(blocks.map((b) => b.tool))]

  return (
    <section className={`panel pane ${side}`}>
      <div className="pane-head">
        <h2>{title}</h2>
        <span className="mono small muted">{run.pipeline}</span>
      </div>
      <div className={`aegis-summary ${blocks.length ? 'as-blocked' : 'as-none'}`}>
        {blocks.length
          ? `🛡 Aegis blocked ${blocks.length} high-risk call${blocks.length > 1 ? 's' : ''}: ${blockedTools.join(', ')}`
          : 'No calls blocked by Aegis'}
      </div>
      <div className="chips">
        <span className={`chip ${run.result.utility ? 'chip-good' : 'chip-bad'}`}>
          task utility: {String(run.result.utility)}
        </span>
        <span className={`chip ${banner.cls === 'banner-bad' ? 'chip-bad' : banner.cls === 'banner-good' ? 'chip-good' : ''}`}>
          AgentDojo security: {banner.text.replace(/^[^ ]+ /, '')}
        </span>
        <span className="chip">{run.result.duration?.toFixed?.(2)}s</span>
      </div>
      <div style={{ marginTop: 12 }}>
        <PipelineFlow decisions={run.decisions} />
      </div>
      <h3>Decisions</h3>
      <DecisionsTable decisions={run.decisions} />
      <h3>Conversation</h3>
      <Timeline messages={run.messages} />
    </section>
  )
}
