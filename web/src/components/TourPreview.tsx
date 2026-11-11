import { useEffect, useState } from 'react'

const titles = ['Flight disruption', 'Passenger requests', 'Request classification', 'Recovery decision']
const captions = [
  ['Flights approaching ORD', 'Storm reaches the hub', 'Departures placed on hold', 'Cancellation creates a request'],
  ['Passenger opens a conversation', 'Cancelled flight identified', 'Arrival deadline captured', 'Request added to the queue'],
  ['Read the passenger request', 'Match the rebooking intent', 'Identify the arrival deadline', 'Escalate for a recovery decision'],
  ['Check available departures', 'Compare with the deadline', 'Recommend the evening flight', 'Wait for human approval'],
]
export default function TourPreview({ step }: { step: number }) {
  const [frame, setFrame] = useState(0)
  const [run, setRun] = useState(0)
  useEffect(() => {
    setFrame(0)
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setFrame(3); return }
    const timers = [1,2,3].map(n => window.setTimeout(() => setFrame(n), n * 1400))
    return () => timers.forEach(window.clearTimeout)
  }, [step, run])
  return <div className="tour-preview detailed-preview" aria-label={`Sample preview: ${titles[step]}`}>
    <div className="tour-preview-bar"><span>Illustrative example</span><button aria-label="Replay sample preview" onClick={() => setRun(n=>n+1)}>Replay</button></div>
    <div className="tour-preview-screen" key={`${step}-${run}`} data-frame={frame}>
      <div className="mini-title">{titles[step]}</div>
      {step===0 ? <div className="mini-scene">
        <svg viewBox="0 0 260 125" aria-label="Sample storm interrupts flight paths at O’Hare">
          <path d="M10 90 30 25 105 15 150 35 225 20 250 70 215 110 120 100 60 115Z" fill="#E9E7E0"/>
          <path d="M25 85Q75 0 140 65Q195 20 235 85" fill="none" stroke={frame>=2?'#97000F':'#547D91'} strokeWidth="2" strokeDasharray={frame>=2?'5 4':undefined}/>
          <g className="preview-aircraft" style={{animationPlayState:frame>=2?'paused':'running'}}><path d="M6 0 -5 -4 -2 0 -5 4Z" fill="#97000F"/></g>
          <circle cx="140" cy="65" r="6" fill="#EC1218"/>
          <text x="140" y="90" textAnchor="middle">ORD</text><text x="25" y="105" textAnchor="middle">SEA</text><text x="235" y="105" textAnchor="middle">JFK</text>
          <g className={`preview-weather ${frame>=1?'visible':''}`}><ellipse cx="140" cy="37" rx="34" ry="17" fill="#547D91" opacity=".22"/><path d="M120 50l-4 9m24-9-4 9m24-9-4 9" stroke="#547D91" strokeWidth="2"/></g>
        </svg>
        <div className={`preview-event ${frame>=2?'event-alert':''}`}><b>AIR 204</b><span>{frame<2?'Approaching hub':frame===2?'On hold':'Cancelled'}</span></div>
        <div className="preview-quiet">{frame===3?'Passenger support request opened':'Route activity / sample data'}</div>
      </div> : step===1 ? <div className="mini-scene preview-chat">
        <div className="preview-bubble">My flight was cancelled.</div>
        <div className={`preview-bubble reply reveal ${frame>=1?'visible':''}`}>AIR 204 / ORD → JFK</div>
        <div className={`preview-bubble reveal ${frame>=2?'visible':''}`}>I need to arrive tonight.</div>
        <div className={`preview-event reveal ${frame>=3?'visible':''}`}><b>Request 001</b><span>Queued</span></div>
      </div> : step===2 ? <div className="mini-scene">
        <div className="preview-quote">“I need to arrive tonight.”</div>
        {[['Intent','Rebook'],['Constraint','Arrive tonight'],['Route','Recovery agent']].map(([label,value],i)=><div key={label} className={`preview-check ${frame>i?'resolved':''}`}><span>{label}</span><b>{frame>i?value:'Reviewing…'}</b><i /></div>)}
      </div> : <div className="mini-scene">
        <div className={`preview-choice ${frame>=2?'chosen':''}`}><div><b>19:30 tonight</b><span>Before the deadline</span></div><small>{frame>=2?'Selected':'Option A'}</small></div>
        <div className={`preview-choice ${frame>=1?'not-selected':''}`}><div><b>10:00 tomorrow</b><span>{frame>=1?'Misses the deadline':'Next available day'}</span></div><small>Option B</small></div>
        <div className={`preview-event reveal ${frame>=3?'visible':''}`}><b>Draft ready</b><span>Approval needed</span></div>
      </div>}
      <div className="preview-caption" aria-live="polite">{captions[step][frame]}</div>
    </div>
    <div className="preview-segments" aria-hidden="true">{[0,1,2,3].map(n=><span key={n} data-complete={frame>=n}/>)}</div>
    <span className="sr-only">Scripted example. No live data or model calls.</span>
  </div>
}
