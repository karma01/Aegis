// Visual of the four-layer defense. Given a run's decision records, each stage
// lights up: green = allowed/active, amber = flagged/tainted, red = blocked.

const STAGES = [
  { key: 'taint', icon: '🏷️', name: 'Taint', sub: 'trust labels', layers: ['taint'] },
  { key: 'moderator', icon: '🧭', name: 'Moderator', sub: 'risk + judge', layers: ['moderator', 'judge'] },
  { key: 'gate', icon: '⚖️', name: 'Policy Gate', sub: 'lethal trifecta', layers: ['policy_gate'] },
  { key: 'sandbox', icon: '📦', name: 'Sandbox', sub: 'enforce + isolate', layers: ['enforcement', 'sandbox'] },
]

const verdictOf = (d) => d.decision || d.enforced

function stageStatus(decisions, stage) {
  const recs = decisions.filter((d) => stage.layers.includes(d.layer))
  if (recs.length === 0) return { cls: 'idle', stat: '—' }
  if (recs.some((d) => verdictOf(d) === 'BLOCK')) return { cls: 'block', stat: 'blocked' }
  if (stage.key === 'taint') {
    const u = recs.filter((d) => d.untrusted).length
    return u ? { cls: 'flag', stat: `${u} untrusted` } : { cls: 'pass', stat: 'trusted' }
  }
  if (recs.some((d) => verdictOf(d) === 'ESCALATE')) return { cls: 'flag', stat: 'escalated' }
  return { cls: 'pass', stat: 'allowed' }
}

export default function PipelineFlow({ decisions = [] }) {
  const tainted = decisions.some((d) => d.layer === 'taint' && d.untrusted)
  const blocked = decisions.some((d) => ['enforcement', 'sandbox'].includes(d.layer) && d.enforced === 'BLOCK')

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span className="muted small">Defense pipeline</span>
        <span className={`taint-pill ${tainted ? 'tainted' : 'clean'}`}>
          {tainted ? '⚠ context tainted' : '✓ context clean'}
        </span>
      </div>
      <div className="flow">
        <div className="flow-endpoint">
          <div className="fn-icon">🌐</div>
          <div className="fn-name">Untrusted<br />input</div>
        </div>
        <div className="flow-arrow">→</div>
        {STAGES.map((stage, i) => {
          const s = stageStatus(decisions, stage)
          return (
            <div key={stage.key} style={{ display: 'contents' }}>
              <div className={`flow-node ${s.cls}`}>
                <div className="fn-icon">{stage.icon}</div>
                <div className="fn-name">{stage.name}</div>
                <div className="fn-sub">{stage.sub}</div>
                <div className="fn-stat">{s.stat}</div>
              </div>
              <div className="flow-arrow">→</div>
            </div>
          )
        })}
        <div className="flow-endpoint" style={blocked ? { borderColor: 'var(--red)' } : { borderColor: 'var(--green)' }}>
          <div className="fn-icon">{blocked ? '🛡️' : '🤖'}</div>
          <div className="fn-name">{blocked ? <>Exfil<br />stopped</> : <>Agent /<br />tools</>}</div>
        </div>
      </div>
    </div>
  )
}
