import { Link2 } from 'lucide-react'
import SiteFooter from './components/SiteFooter'
import { createPortal } from 'react-dom'
import TourPreview from './components/TourPreview'
import { resetExample, startExample, sampleState } from './lib/example'
import { useCallback, useEffect, useState } from 'react'
import * as api from './lib/api'
import type { State } from './lib/types'
import About from './views/About'
import ModelService from './views/ModelService'
import Demo from './views/Demo'
import Storm from './views/Storm'
import Recovery from './views/Recovery'
import Cost from './views/Cost'
import Models from './views/Models'
import Sqlpp from './views/Sqlpp'
import './index.css'
import './toolbar.css'
import './section-surfaces.css'

type View = 'about' | 'model' | 'demo' | 'storm' | 'recovery' | 'cost' | 'models' | 'sqlpp'

/*
  The shell, laid out like AIDP Financial's so an SE who has run one can run
  the other without being shown.

  Left of the bar is the story in the order it is told: what the Model Service
  offers, what to look for, the storm, the people the agent helped, and what it
  all cost. The brand mark opens the platform home, for rooms that do not yet
  know Couchbase. Right of the bar is
  where you go when the room asks a question: the model catalog and the SQL++
  that ran. Then the controls: the storm, pause and the reset.

  State is polled once a second here and handed down, so every screen agrees
  on the numbers at any moment - a funnel on one tab and a cost on another
  computed from different polls would disagree by a message or two, and
  someone would notice.
*/

const PHASE_LABEL: Record<State['phase'], string> = {
  normal: 'Ready',
  storm: 'Storm at ORD',
  recovering: 'Recovering',
  quiet: 'Quiet',
}

export default function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    try { return localStorage.getItem('air-theme') === 'dark' ? 'dark' : 'light' } catch { return 'light' }
  })
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('air-theme', theme) } catch { /* Private browsing may block storage. */ }
  }, [theme])
  const [example, setExample] = useState(import.meta.env.MODE === 'simulation')
  const [tour, setTour] = useState<number | null>(null)
  const [tourHost, setTourHost] = useState<HTMLDivElement | null>(null)
  const [spot, setSpot] = useState({top:0,left:0,width:0,height:0, noteTop:0,noteLeft:0,previewTop:0,previewLeft:0})
  const [recoveryRequest, setRecoveryRequest] = useState<string | null>(null)
  const openRecoveryRequest = (id: string) => { setRecoveryRequest(id); setTour(null); setView('recovery') }
  const [view, setView] = useState<View>('storm')
  const [returnedRequest, setReturnedRequest] = useState<string | null>(null)
  const [returnToMap, setReturnToMap] = useState(false)
  const backToMap = (id: string | null) => { setReturnedRequest(id); setRecoveryRequest(null); setView('storm'); setReturnToMap(true) }
  useEffect(() => {
    if (!returnToMap || view !== 'storm') return
    const map = document.querySelector<HTMLElement>('[data-tour-target="flights"]')
    map?.focus({preventScroll:true})
    map?.scrollIntoView({block:'start',behavior:'instant'})
    setReturnToMap(false)
  }, [returnToMap, view])
  const [state, setState] = useState<State | null>(null)
  const [armed, setArmed] = useState(false)
  const [nonce, setNonce] = useState(0)

  const tourSteps = [
    { target: 'flights', title: 'A storm disrupts flights', text: 'O’Hare is the hub. The map illustrates the routes affected by the scenario.' },
    { target: 'requests', title: 'Passengers ask for help', text: 'Incoming messages enter the support queue shown here.' },
    { target: 'classification', title: 'AI sorts the requests', text: 'A smaller model identifies intent and urgency; complex cases move to Recovery.' },
    { target: 'recovery', title: 'Review the recommendation', text: 'Follow the airport’s replies and automatic demo adjustments.' },
  ]
  useEffect(() => {
    if (tour === null) return
    const region = document.querySelector<HTMLElement>(`[data-tour-target="${tourSteps[tour].target}"]`)
    const target = tour === 3 ? region?.querySelector<HTMLElement>('.card') ?? region : region
    if (!target) return
    const host = document.createElement('div')
    host.className = 'tour-floating-host'
    document.body.appendChild(host)
    setTourHost(host)
    target.scrollIntoView({ block: 'start', behavior: 'instant' })
    const measure = () => {
      const r = target.getBoundingClientRect()
      const stage = document.querySelector('.stage')!.getBoundingClientRect()
      const top = Math.max(r.top, stage.top + 6)
      const bottom = Math.min(r.bottom, stage.bottom - 6)
      const rightSpace = window.innerWidth - r.right - 28
      const leftSpace = r.left - 28
      const beside = Math.max(rightSpace, leftSpace) >= 520
      const noteWidth = beside ? Math.min(640, Math.max(rightSpace,leftSpace)) : Math.min(720, window.innerWidth - 32)
      host.style.width = `${noteWidth}px`
      const cardTop = beside ? Math.max(stage.top+8,top) : bottom + 14
      host.style.top = `${cardTop}px`
      host.style.left = `${beside ? (rightSpace >= leftSpace ? r.right+14 : r.left-noteWidth-14) : Math.max(16,Math.min(r.left+(r.width-noteWidth)/2,window.innerWidth-noteWidth-16))}px`
      host.style.setProperty('--tour-available-height', `${Math.max(80,window.innerHeight-cardTop-12)}px`)
      setSpot({top, left:r.left, width:r.width, height:Math.max(40,bottom-top),
        previewTop:beside ? top+10 : Math.max(stage.top+8, Math.min(top+10, Math.min(bottom+12, window.innerHeight-180)-216)), previewLeft:Math.max(16, r.right-Math.min(280,window.innerWidth-48)-10),
        noteTop:beside ? Math.max(16,top) : Math.min(bottom+12, window.innerHeight-180),
        noteLeft:beside ? r.right+16 : Math.max(16,Math.min(r.left,window.innerWidth-noteWidth-16))})
    }
    measure()
    const stage = document.querySelector('.stage')!
    stage.addEventListener('scroll', measure)
    window.addEventListener('resize', measure)
    const observer = new ResizeObserver(measure); observer.observe(target); observer.observe(host)
    return () => { stage.removeEventListener('scroll', measure); window.removeEventListener('resize', measure); observer.disconnect(); host.remove() }
  }, [tour, view])
  const moveTour = (step: number) => { setView(step === 3 ? 'recovery' : 'storm'); setTour(step) }
  const closeTour = () => { setTour(null); setView('storm'); requestAnimationFrame(() => document.getElementById('start-tour')?.focus()) }
  useEffect(() => {
    if (tour === null) return
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape') closeTour() }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [tour])

  const [liveError,setLiveError] = useState('')
  const [copyStatus,setCopyStatus] = useState('Copy link')
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText('https://couchbase-air-simulation.vercel.app/')
      setCopyStatus('Copied!')
    } catch { setCopyStatus('Try again') }
    window.setTimeout(()=>setCopyStatus('Copy link'),2500)
  }

  const refresh = useCallback(() => {
    if (example) { setState(sampleState()); return }
    let active = true
    api.getState().then(s => { if(active) { setState(s); if(s.error) setLiveError('A backend step failed. Restart the run to retry.'); } }).catch(e => setLiveError(e.message))
    return () => { active = false }
  }, [example])

  useEffect(() => {
    const cancel = refresh()
    const t = window.setInterval(refresh, 1000)
    return () => { cancel?.(); window.clearInterval(t) }
  }, [refresh])

  useEffect(() => {
    if(example || state?.run_status !== 'running' || state?.paused || liveError) return
    let stopped=false, working=false
    const advance=async()=>{
      if(stopped || working || document.hidden) return
      working=true
      try { await api.advance(); if(!stopped) refresh() }
      catch(e) { if(!stopped) setLiveError(e instanceof Error ? e.message : 'Backend unavailable') }
      finally { working=false }
    }
    const timer=window.setInterval(advance,1500); advance()
    return ()=>{stopped=true;window.clearInterval(timer)}
  },[example,state?.run_status,state?.paused,liveError,refresh])

  // The storm is the one control pressed during the demo, so it takes you to
  // where the storm is visible. A presenter should never trigger it from the
  // Models tab and then have to go looking.
  const trigger = async () => {
    try {
      await api.storm()
      setView('storm')
      refresh()
    } catch(e) { setLiveError(e instanceof Error ? e.message : 'Could not start the storm') }
  }

  // Click to arm, click again within five seconds to do it. A modal mid-pitch
  // is worse than the accident it prevents.
  const reset = async () => {
    setReturnedRequest(null)
    if (!armed) {
      setArmed(true)
      window.setTimeout(() => setArmed(false), 5000)
      return
    }
    setArmed(false)
    await api.reset()
    setLiveError('')
    setNonce((n) => n + 1)
    refresh()
  }

  // Stops arrivals and model calls until Resume, so a demo left open between
  // meetings is not filling the Model Service's cache.
  const togglePause = async () => {
    await (state?.paused === 'user' ? api.resume() : api.pause())
    refresh()
  }

  const beginExample = () => { setReturnedRequest(null); startExample(); api.storm(); setExample(true); setState(sampleState()); setTour(null); setNonce(n=>n+1) }
  const endExample = () => { setReturnedRequest(null); resetExample(); setExample(false); setState(null); setView('storm'); setNonce(n=>n+1) }
  const phase = state?.phase ?? 'normal'
  const paused = state?.paused ?? null
  const local = state?.backend.models === 'local_standin'
  const gateway = state?.backend.models === 'gateway_standin'

  return (
    <div className="app" data-tour={tour === null ? undefined : tourSteps[tour].target}>
      {liveError && !example && <div role="alert" className="reference-note">{liveError}</div>}
      <div className="presenter">
        <a className="brand" href="https://www.couchbase.com/" target="_blank" rel="noreferrer" aria-label="Couchbase website"><img src={theme === 'dark' ? '/brand/couchbase-logo-dark.svg' : '/brand/couchbase-logo.svg'} alt="Couchbase" /></a>

        <nav className="nav" aria-label="Demo views">
          {([['storm', 'Dashboard'], ['recovery', 'Recovery'], ['cost', 'Cost']] as const).map(([id, label]) => (
            <button key={id} data-active={view === id} aria-current={view === id ? 'page' : undefined}
              onClick={() => { setTour(null); setRecoveryRequest(null); setView(id) }}>{label}</button>
          ))}
        </nav>

        <div className="spacer" />

        <div className="demo-controls">
          <details className="demo-menu" onKeyDown={e => {
            if(e.key === 'Escape') { e.currentTarget.open=false; e.currentTarget.querySelector('summary')?.focus() }
          }} onBlur={e => { if(!e.currentTarget.contains(e.relatedTarget as Node)) e.currentTarget.open=false }}>
            <summary>More</summary>
            <div className="toolbar-menu">
              {import.meta.env.MODE !== 'simulation' && <button onClick={e=>{example ? endExample() : beginExample(); e.currentTarget.closest('details')!.open=false}}>{example ? 'Exit sample data' : 'Show sample data'}</button>}
              {example && <button onClick={e=>{beginExample();e.currentTarget.closest('details')!.open=false}}>Restart simulation</button>}
              <button onClick={e => {setTour(null); setView('sqlpp'); e.currentTarget.closest('details')!.open=false}}>Commands</button>
              <span className="menu-label menu-divider">Run controls</span>
              {phase === 'normal' && <button disabled={!state} onClick={e => {trigger(); e.currentTarget.closest('details')!.open=false}}>{example ? 'Run simulation' : 'Trigger storm'}</button>}
              <button disabled={!state} onClick={togglePause}>{paused==='user'?'Resume demo':'Pause demo'}</button>
              <button disabled={!state} onClick={reset}>{armed?'Confirm reset':'Reset demo'}</button>
            </div>
          </details>
          <button type="button" className="share-link" onClick={copyLink} aria-label={copyStatus} title={copyStatus} data-copied={copyStatus === 'Copied!'}><Link2 size={17} aria-hidden="true" /><span aria-live="polite">{copyStatus}</span></button>
          <button className="appearance-toggle" role="switch" aria-checked={theme === 'dark'} aria-label="Dark mode" title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
            <span className="appearance-track" aria-hidden="true"><span>☀</span><span>☾</span><span className="appearance-thumb" /></span>
          </button>
        </div>
      </div>

      <div className="stage">
        <div className="stage-inner" key={nonce}>
          {['about', 'model', 'demo'].includes(view) && <nav className="learn-nav" aria-label="How it works">
            {([['demo', 'The scenario'], ['model', 'Model Service'], ['about', 'Couchbase platform']] as const).map(([id, label]) =>
              <button key={id} aria-current={view === id ? 'page' : undefined} onClick={() => { setTour(null); setRecoveryRequest(null); setView(id) }}>{label}</button>)}
          </nav>}
          {!example && state && (phase !== 'normal' || paused === 'user') && <div className="run-note" role="status">{paused === 'user' ? 'Paused' : PHASE_LABEL[phase]}</div>}
          {!state && <div className="connection-note" role="status">Local preview / Backend not connected. Live results appear when connected.</div>}
          {view === 'about' && <About />}
          {view === 'model' && <ModelService />}
          {view === 'demo' && <Demo state={state} />}
          {view === 'storm' && <Storm state={state} onTrigger={trigger} onTour={() => moveTour(0)} example={example} returnedRequest={returnedRequest} onOpenRequest={openRecoveryRequest} />}
          {view === 'recovery' && <Recovery key={`${example ? 'sample' : 'live'}-${recoveryRequest ?? 'queue'}`} state={state} initialRequest={recoveryRequest} onBackToMap={backToMap} />}
          {view === 'cost' && <Cost state={state} />}
          {view === 'models' && <Models />}
          {view === 'sqlpp' && <Sqlpp />}
          <SiteFooter />
        </div>
      </div>

      {tour !== null && <div className="tour-overlay">
        <div className="tour-spotlight" aria-hidden="true" style={{top:spot.top-5,left:spot.left-5,width:spot.width+10,height:spot.height+10}} />

        {tourHost && createPortal(<aside className="tour-guide tour-combined" aria-label="Guided walkthrough">
          <div className="tour-copy" aria-live="polite" aria-atomic="true"><span className="tour-count">{tour + 1} of 4</span><h2>{tourSteps[tour].title}</h2><p>{tourSteps[tour].text}</p></div>
          <div className="tour-preview-side"><TourPreview step={tour} /></div>
          <div className="tour-actions"><button onClick={closeTour} aria-label="Close walkthrough">Close</button><button disabled={tour===0} aria-label="Back" onClick={() => moveTour(tour-1)}>Back</button><button className="tour-next" aria-label={tour===3?'Finish walkthrough':'Next'} onClick={() => tour===3 ? closeTour() : moveTour(tour+1)}>{tour===3?'Done':'Next'}</button></div>
        </aside>, tourHost)}
      </div>}

      {paused && (
        <div className="paused-bar">
          {paused === 'user'
            ? 'Paused: no new messages and no model calls. Resume, trigger the storm or reset to carry on.'
            : `Paused: nobody had the demo open for ${state?.idle_pause_min ?? 10} minutes. Picking up again now.`}
        </div>
      )}

      {/* Always visible while the models are stand-ins. The alternative is an
          SE forgetting to say it, which is how a laptop demo turns into a
          claim about Bedrock. */}
      {gateway && (
        <div className="standin-bar">
          Sandbox-like local mode: the Model Service is a local stand-in at {state?.backend.endpoint},
          imitating sbx-27 (exact-match cache, x-cache on hits, semantic not stored), over LM Studio
          models{state?.backend.classify_via === 'sqlpp' ? '; ai_completion is a local UDF' : ''}.
          Token counts are measured; prices are Bedrock list prices.
        </div>
      )}
      {local && !example && (
        <div className="standin-bar">
          Local stand-ins: models served by LM Studio at {state?.backend.endpoint}; AI Functions
          and the semantic cache emulated by the demo backend. Token counts are measured; prices
          are Bedrock list prices.
        </div>
      )}
    </div>
  )
}
