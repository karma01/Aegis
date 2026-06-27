import { useState } from 'react'
import LiveTester from './components/LiveTester.jsx'
import Dashboard from './components/Dashboard.jsx'

const TABS = [
  { id: 'tester', label: 'Live Tester' },
  { id: 'dashboard', label: 'Dashboard' },
]

export default function App() {
  const [tab, setTab] = useState('tester')
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">▢</span>
          <div>
            <h1>Aegis</h1>
            <p className="subtitle">Taint-aware moderator &amp; sandbox vs. prompt injection</p>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? 'tab active' : 'tab'}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="content">
        {tab === 'tester' ? <LiveTester /> : <Dashboard />}
      </main>
    </div>
  )
}
