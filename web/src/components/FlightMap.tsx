import { flightVisual } from '../lib/flightVisual'
import './FlightMap.css'
import { exampleActive, simulationStory } from '../lib/example'
import { useEffect, useState } from 'react'
import type { State } from '../lib/types'

const routes = [
  { city: 'Seattle', code: 'SEA', x: 70, y: 55 },
  { city: 'San Francisco', code: 'SFO', x: 45, y: 160 },
  { city: 'Dallas', code: 'DFW', x: 245, y: 230 },
  { city: 'New York', code: 'JFK', x: 540, y: 95 },
  { city: 'Miami', code: 'MIA', x: 490, y: 235 },
]
export default function FlightMap({ state, onTour, onOpenRequest, returnedRequest }: { state: State | null; returnedRequest: string | null; onTour: () => void; onOpenRequest: (id: string) => void }) {
  const [visible, setVisible] = useState(!document.hidden)
  useEffect(() => {
    const update = () => setVisible(!document.hidden)
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])
  const simulated=exampleActive()
  const story=simulated?simulationStory():null
  const visual=flightVisual(story?.current.kind ?? (state && state.phase !== 'normal' ? 'storm' : 'normal'))
  const disrupted=!visual.normal
  const openFlight = (code: string) => onOpenRequest(code === 'SEA' ? 'sample-002' : code === 'SFO' ? 'sample-003' : code === 'MIA' ? 'sample-004' : 'sample-001')
  const stopped=!visible || !!state?.paused || !!story?.paused
  return <section className={`card flight-map ${stopped?'map-stopped':''}`} data-tour-target="flights" tabIndex={-1} aria-label="Illustrative flight routes">
    <div className="map-heading"><div><h2>Flights around O’Hare</h2></div>
      <div className="map-controls"><button id="start-tour" className="map-motion" onClick={onTour}>Show me around</button></div></div>
    <div className="map-event" data-kind={visual.failure?'failure':visual.outcome?'outcome':'normal'} aria-live="polite" aria-atomic="true">
      <strong>{visual.headline}</strong><span>{visual.detail}</span>
    </div>
    <svg viewBox="0 0 620 285" role="group" aria-label={`${visual.headline}. ${visual.detail}`} className={stopped?'motion-paused':''}>
      <path className="map-land" d="M35 45 L130 30 215 55 300 42 365 70 460 45 565 80 552 145 500 172 510 250 480 245 445 190 360 200 295 260 250 252 195 200 110 205 50 155Z" />
      {routes.map((r, i) => {
        const affected=r.code==='JFK'||r.code==='SEA'
        const cancelled=disrupted&&affected
        const service=r.code==='SFO'||r.code==='MIA'
        const requestId=r.code==='SEA'?'sample-002':r.code==='SFO'?'sample-003':r.code==='MIA'?'sample-004':'sample-001'
        const requestLabel=r.code==='SEA'?'Sam Rivera’s Seattle':r.code==='SFO'?'Jordan Lee’s San Francisco':r.code==='MIA'?'Taylor Brooks’s Miami':'Alex Morgan’s New York'
        const returned=disrupted && (affected||service) && returnedRequest === requestId
        const path=`M340 110 Q${(340+r.x)/2} ${Math.min(110,r.y)-45} ${r.x} ${r.y}`
        return <g key={r.code}>

          <path className={`map-route ${cancelled?'cancelled':disrupted&&!visual.settled?'held':''}`} d={path} />
          {(!disrupted || (visual.settled&&!affected)) && <g className="map-plane" style={{ offsetPath: `path('${path}')`, animationDelay: `${-i*2}s` }}><path d="M7 0 -5 -4 -2 0 -5 4Z" /></g>}
          <circle cx={r.x} cy={r.y} r="4" className="map-airport" />
          <text x={r.x} y={r.y+22} textAnchor="middle">{r.code}</text>
          {cancelled && <g className="route-cancel" transform={`translate(${r.x},${r.y-17})`}><circle r="10"/><path d="M-4-4 4 4 M4-4-4 4"/></g>}
          {cancelled && <text className="flight-number" x={r.x} y={r.y+39} textAnchor="middle">{r.code==='JFK'?'AIR 204':'AIR 410'} ×</text>}
          {disrupted&&!affected&&!service&&!visual.settled && <g className="route-held" transform={`translate(${r.x},${r.y-14})`}><path d="M-3-5v10 M3-5v10"/></g>}
          {disrupted && service && <text className="service-label" x={r.x} y={r.y+38} textAnchor="middle">{r.code==='SFO'?'Lightning delay':'Gate C18'}</text>}
          {disrupted && r.code==='SFO' && <path className="route-lightning" d={`M${r.x+3} ${r.y-32} l-10 14 h8 l-5 12 16-17 h-9 l6-9Z`}/>}
          {disrupted && (affected||service) && <g className={`map-request-target ${returned?'request-returned':''}`} aria-current={returned?true:undefined} role="button" tabIndex={0} aria-label={`Open ${requestLabel} request in Recovery`} onClick={()=>openFlight(r.code)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openFlight(r.code)}}}>
            <rect x={r.x-27} y={r.y-33} width="54" height="78" rx="10"/>
          </g>}
        </g>
      })}
      {disrupted && !visual.settled && <g className="storm-weather">
        <path className="weather-cloud" d="M304 93c-17 0-19-25-2-29 0-23 32-30 43-10 20-5 32 12 26 26 17 9 7 25-8 24h-59z"/>
        <path className="weather-bolt" d="m338 73-14 23 13-3-9 20 27-30-16 3 9-13"/>
        <g className="weather-rain"><path d="m307 108-4 9m55-6-4 9m-35-3-4 9"/></g>
      </g>}
      {visual.outcome && <g className="replacement-route"><path d="M340 110 Q460 192 540 95"/><text x="458" y="174" textAnchor="middle">AIR 218 / offered</text></g>}
      {visual.failure && <g className="lookup-failure map-request-target" role="button" tabIndex={0} aria-label="Open Alex Morgan’s failed flight search in Recovery" onClick={()=>openFlight('JFK')} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openFlight('JFK')}}} transform="translate(453 47)"><rect x="-76" y="-17" width="152" height="30" rx="7"/><text textAnchor="middle" y="3">× Search timeout</text></g>}
      <circle cx="340" cy="110" r="19" className="map-hub-halo"/><circle cx="340" cy="110" r="7" className="map-hub"/>
      <text x="340" y="146" textAnchor="middle" className="hub-label">ORD / O’Hare</text>
    </svg>
  </section>
}
