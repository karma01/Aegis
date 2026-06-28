import { useEffect, useState } from 'react'
import { getOptions, getSuite, postRun } from '../api.js'
import Timeline from './Timeline.jsx'
import DecisionsTable from './DecisionsTable.jsx'

export default function LiveTester() {
  const [options, setOptions] = useState(null)
  const [tasks, setTasks] = useState({ user_tasks: [], injection_tasks: [] })
  const [form, setForm] = useState({
    suite: 'workspace',
    user_task: '',
    config: 'combined',
    model: 'VLLM_PARSED',
    attack: '',
    injection_task: '',
    escalate: 'block',
  })
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getOptions().then(setOptions).catch((e) => setError(String(e)))
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
    setResult(null)
    try {
      const body = { ...form, attack: form.attack || null }
      if (!body.attack) body.injection_task = null
      setResult(await postRun(body))
    } catch (e) {
      setError(String(e))
    } finally {
      setRunning(false)
    }
  }

  if (!options) return <p className="muted">{error || 'Loading…'}</p>

  return (
    <div className="tester">
      <section className="panel controls">
        <h2>Run a task</h2>
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
        <label>Defense config
          <select value={form.config} onChange={set('config')}>
            {options.configs.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label>Model
          <select value={form.model} onChange={set('model')}>
            {options.models.map((m) => <option key={m}>{m}</option>)}
          </select>
        </label>
        <label>Attack
          <select value={form.attack} onChange={set('attack')}>
            <option value="">none (benign)</option>
            {options.attacks.map((a) => <option key={a}>{a}</option>)}
          </select>
        </label>
        {form.attack && (
          <label>Injection task
            <select value={form.injection_task} onChange={set('injection_task')}>
              {tasks.injection_tasks.map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
        )}
        <label>On escalate
          <select value={form.escalate} onChange={set('escalate')}>
            {options.escalate.map((e) => <option key={e}>{e}</option>)}
          </select>
        </label>
        <button className="run-btn" onClick={run} disabled={running || !form.user_task}>
          {running ? 'Running…' : 'Run'}
        </button>
        {error && <p className="error">{error}</p>}
        <p className="muted small">Needs the model server (Ollama/API) running.</p>
      </section>

      <section className="panel output">
        {result ? (
          <>
            <div className="result-head">
              <h2>{result.pipeline}</h2>
              <div className="chips">
                <Chip label="utility" value={result.result.utility} good={result.result.utility} />
                {result.result.attack && (
                  <Chip
                    label="attack blocked"
                    value={result.result.security === false}
                    good={result.result.security === false}
                  />
                )}
                <span className="chip">{fmtSecs(result.result.duration)}</span>
              </div>
            </div>
            <h3>Decisions</h3>
            <DecisionsTable decisions={result.decisions} />
            <h3>Conversation</h3>
            <Timeline messages={result.messages} />
          </>
        ) : (
          <p className="muted">Configure a run and press <b>Run</b> to see the agent's tool
          calls flow through the four Aegis layers.</p>
        )}
      </section>
    </div>
  )
}

function Chip({ label, value, good }) {
  const cls = value === null || value === undefined ? '' : good ? 'chip-good' : 'chip-bad'
  return <span className={`chip ${cls}`}>{label}: {String(value)}</span>
}

function fmtSecs(s) {
  return s == null ? '—' : `${s.toFixed(2)}s`
}
