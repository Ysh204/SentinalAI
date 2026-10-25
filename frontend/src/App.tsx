import { useEffect, useState } from 'react'
import './App.css'
import Console from './Console'
import Landing from './Landing'

function currentView() {
  return window.location.hash.startsWith('#console') ? 'console' : 'landing'
}

export default function App() {
  const [view, setView] = useState(currentView)

  useEffect(() => {
    const onHash = () => setView(currentView())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return view === 'console' ? <Console /> : <Landing />
}
