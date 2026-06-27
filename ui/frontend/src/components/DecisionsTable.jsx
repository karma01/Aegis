// Renders a list of Aegis decision-log records with layer + verdict chips.

const LAYER_COLOR = {
  moderator: 'badge-blue',
  policy_gate: 'badge-purple',
  taint: 'badge-amber',
  enforcement: 'badge-red',
  sandbox: 'badge-red',
  judge: 'badge-grey',
}

function verdict(rec) {
  return rec.decision || rec.enforced || (rec.untrusted !== undefined ? (rec.untrusted ? 'UNTRUSTED' : 'TRUSTED') : '')
}

function verdictClass(v) {
  if (['BLOCK', 'UNTRUSTED'].includes(v)) return 'v-block'
  if (v === 'ESCALATE') return 'v-escalate'
  if (['ALLOW', 'TRUSTED'].includes(v)) return 'v-allow'
  return ''
}

export default function DecisionsTable({ decisions }) {
  if (!decisions || decisions.length === 0) {
    return <p className="muted">No decisions recorded.</p>
  }
  return (
    <table className="decisions">
      <thead>
        <tr>
          <th>Layer</th>
          <th>Tool</th>
          <th>Verdict</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>
        {decisions.map((d, i) => {
          const v = verdict(d)
          return (
            <tr key={i}>
              <td><span className={`badge ${LAYER_COLOR[d.layer] || 'badge-grey'}`}>{d.layer}</span></td>
              <td className="mono">{d.tool || '—'}</td>
              <td><span className={`verdict ${verdictClass(v)}`}>{v || '—'}</span></td>
              <td className="muted small">{d.reason || (d.risk !== undefined ? `risk ${d.risk}` : '')}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
