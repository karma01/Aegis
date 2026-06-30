import { useState } from 'react'
import LiveTester from './components/LiveTester.jsx'
import Dashboard from './components/Dashboard.jsx'
import Compare from './components/Compare.jsx'

const TABS = [
  { id: 'tester', label: 'Live Tester' },
  { id: 'compare', label: 'Baseline vs Aegis' },
  { id: 'dashboard', label: 'Dashboard' },
]

export default function App() {
  const [tab, setTab] = useState('tester')
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo-badge">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2.5l7 2.6v5.4c0 4.5-3 8.3-7 9.5-4-1.2-7-5-7-9.5V5.1l7-2.6z"
                stroke="url(#g)" strokeWidth="1.6" fill="rgba(91,156,255,0.12)" strokeLinejoin="round" />
              <path d="M8.7 12.2l2.2 2.2 4.2-4.4" stroke="url(#g)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              <defs>
                <linearGradient id="g" x1="5" y1="2" x2="19" y2="22" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#5b9cff" /><stop offset="1" stopColor="#7c5cff" />
                </linearGradient>
              </defs>
            </svg>
          </span>
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
        {tab === 'tester' && <LiveTester />}
        {tab === 'compare' && <Compare />}
        {tab === 'dashboard' && <Dashboard />}
      </main>
    </div>
  )
}
