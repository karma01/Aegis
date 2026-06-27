// Conversation timeline: each message as a card; blocked tool results flagged.

function isBlocked(error) {
  return typeof error === 'string' && (error.startsWith('AEGIS_') || error.startsWith('SANDBOX_'))
}

function RoleTag({ role }) {
  const map = { system: 'r-system', user: 'r-user', assistant: 'r-assistant', tool: 'r-tool' }
  return <span className={`roletag ${map[role] || ''}`}>{role}</span>
}

export default function Timeline({ messages }) {
  if (!messages || messages.length === 0) return <p className="muted">No conversation yet.</p>
  return (
    <div className="timeline">
      {messages.map((m, i) => {
        const blocked = m.role === 'tool' && isBlocked(m.error)
        return (
          <div key={i} className={`msg ${m.role} ${blocked ? 'blocked' : ''}`}>
            <div className="msg-head">
              <RoleTag role={m.role} />
              {blocked && <span className="verdict v-block">BLOCKED</span>}
              {m.role === 'tool' && !blocked && m.error && <span className="verdict v-escalate">error</span>}
            </div>
            {m.text && <div className="msg-text">{m.text.slice(0, 1500)}</div>}
            {m.tool_calls && m.tool_calls.length > 0 && (
              <div className="toolcalls">
                {m.tool_calls.map((tc, j) => (
                  <div key={j} className="toolcall mono">
                    → {tc.function}({Object.keys(tc.args || {}).join(', ')})
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
