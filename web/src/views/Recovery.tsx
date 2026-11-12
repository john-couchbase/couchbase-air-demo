import { exampleActive, demoResolution, demoOutcome } from '../lib/example'
import { useEffect, useState, useRef } from 'react'
import * as api from '../lib/api'
import type { Resolution, ResolutionRow, State } from '../lib/types'
import { agentName, classifyName } from '../lib/models'
import './Recovery.css'
import SmsConversation from '../components/SmsConversation'

const priority = (urgency: number) => urgency >= 4 ? 'High priority' : urgency >= 2 ? 'Standard priority' : 'Routine'
const paragraphs = (text: string) => text.split(/(?<=[.!?])\s+(?=[A-ZI])/).map((line, i) => <p key={i}>{line}</p>)

/*
  Beat 3: the few messages that need judgment, and what the frontier model did.

  Left, the queue the funnel let through, most urgent first, with the hero
  pinned to the top so the presenter never scrolls for her. Right, one
  decision laid out in the order a person would check it: what they said, what
  the cheap model made of it, what memory said about them, the options that
  were really available, and then the decision and the reply.

  Options are shown with the one chosen highlighted, not just the choice. A
  recommendation without the alternatives it beat is a claim; with them, the
  room can judge it.

  Approve is the only write to Agent Memory. It is there so the room sees the
  loop close: the next storm, the agent will know what was done this time.
*/

export default function Recovery({ state, initialRequest = null, onBackToMap }: { state: State | null; initialRequest?: string | null; onBackToMap: (id: string | null) => void }) {
  const [rows, setRows] = useState<ResolutionRow[]>([])
  const [sel, setSel] = useState<string | null>(initialRequest)
  const [res, setRes] = useState<Resolution | null>(null)
  const requestPanel = useRef<HTMLDivElement>(null)
  const focused = useRef(false)
  const passengerList = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const list=passengerList.current
    const selected=list?.querySelector<HTMLElement>('[aria-current="true"]')
    if (list && selected) list.scrollTo(window.innerWidth<=900 ? {left:selected.offsetLeft-list.offsetLeft,behavior:'instant'} : {top:selected.offsetTop-list.offsetTop,behavior:'instant'})
  }, [sel, rows.length])
  const preview = exampleActive() && initialRequest ? demoResolution(initialRequest) : null
  const [busy, setBusy] = useState(false)
  const [detailView, setDetailView] = useState<'conversation'|'checks'>('conversation')
  const selectRequest = (id: string) => { if(id===sel) return; setSel(id); setRes(null); setDetailView('conversation') }

  useEffect(() => { if(initialRequest) document.querySelector('.stage')?.scrollTo({top:0}) }, [initialRequest])

  useEffect(() => {
    const load = () => api.getResolutions().then((r) => {
      const sorted = [...r].sort((a, b) => Number(!!b.hero) - Number(!!a.hero))
      setRows(sorted)
      setSel((s) => s ?? (sorted.find((x) => x.status !== 'drafting') ?? sorted[0])?.id ?? null)
    }).catch(() => {})
    load()
    const t = window.setInterval(load, 2000)
    return () => window.clearInterval(t)
  }, [])

  // A drafting row has no decision to fetch yet. When the list poll sees it
  // land, its status changes and this runs again, so the panel fills itself in.
  const selRow = rows.find((r) => r.id === sel)
  const selStatus = selRow?.status
  useEffect(() => {
    if (!sel || !selRow) return
    setRes((r) => (r?.id === sel ? r : null))
    if (selStatus === 'drafting') return
    let current = true
    api.getResolution(sel).then(r => { if(current) setRes(r) }).catch(() => {})
    return () => { current = false }
  }, [sel, selStatus])

  useEffect(() => {
    if(initialRequest && rows.length && requestPanel.current && !focused.current) {
      focused.current = true
      requestPanel.current.focus({preventScroll:true})
      document.querySelector('.recovery-layout')?.scrollIntoView({block:'start',behavior:'instant'})
    }
  }, [initialRequest, rows.length])

  const approve = async () => {
    if (!res) return
    setBusy(true)
    try {
      setRes(await api.approve(res.id))
      setRows((rs) => rs.map((r) => (r.id === res.id ? { ...r, status: 'approved' } : r)))
    } finally {
      setBusy(false)
    }
  }

  const backButton = initialRequest ? <button type="button" className="back-to-map" onClick={()=>onBackToMap(sel ?? initialRequest)}>Back to map</button> : null
  const inAgent = state?.funnel.in_agent ?? 0

  return (
    <div className="fade-in recovery-view" data-tour-target="recovery">
      <h1 style={{ marginTop: 8, marginBottom: 6 }}>Passenger inbox</h1>
      <p className="lede" style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)' }}>
        Choose a passenger. Review their request and proposed reply.
      </p>

      {rows.length === 0 ? (
        <div className="card" style={{ marginTop: 24 }}>
          {backButton}
          <h3 style={{ marginBottom: 6 }}>{preview ? preview.name : 'No requests to review'}</h3>
          <p style={{ fontSize: 'var(--ui-body)', marginBottom: 0 }}>
            {preview ? preview.message : state?.phase === 'normal'
              ? 'Trigger a storm to send requests for review.'
              : inAgent ? `Claude is drafting ${inAgent} decision${inAgent === 1 ? '' : 's'} now.`
                : state ? 'Requests needing a decision appear here.' : 'Connect the backend to see recovery requests.'}
          </p>
          {preview && <p className="request-pending">This request is waiting for Recovery. Its checks will appear here as the simulation progresses.</p>}
        </div>
      ) : (
        <div className="recovery-layout">
          <aside className="card recovery-queue" aria-label="Passenger conversations">
            <div className="inbox-list-heading"><h2>Passengers</h2><span>{rows.length} requests</span></div>
            <div className="inbox-passengers" ref={passengerList}>{rows.map((r) => (
              <button type="button" key={r.id} className="recovery-request" aria-current={sel===r.id?true:undefined} aria-label={`View ${r.name}'s request`} onClick={() => selectRequest(r.id)}>
                <span className="passenger-initials" aria-hidden="true">{r.name.split(' ').map(n=>n[0]).slice(0,2).join('')}</span>
                <span className="inbox-preview"><strong className="request-name">{r.name}</strong>
                <span className="request-flight">{r.flight_no} / {r.dest_city}</span>
                <span className="request-status">{r.status==='drafting'?'Preparing reply':r.status==='approved'?'Complete':'Reply ready'}</span></span>
              </button>
            ))}</div>
          </aside>

          <div className="recovery-selected" ref={requestPanel} tabIndex={-1} aria-label="Selected passenger request">{backButton}{res ? <Detail view={detailView} onView={setDetailView} res={res} onApprove={approve} busy={busy}
                                 local={state?.backend.models !== 'model_service'}
                                 reader={classifyName(state)} agent={agentName(state)} />
            : selRow?.status === 'drafting' ? <Drafting row={selRow} reader={classifyName(state)} agent={agentName(state)} />
            : <div className="card">{sel ? 'Loading…'
              : `Claude is drafting ${rows.length} decision${rows.length === 1 ? '' : 's'}. `
                + 'Each one appears here as soon as it lands.'}</div>}</div>
        </div>
      )}
    </div>
  )
}

// Who wrote in and how the classification model read it: the top of the panel, the same
// whether Claude's decision has landed yet or not.
function Header({ name, tier, flight_no, dest_city, message, summary, urgency, needs, reader, checks = false, reply, confirmation }: {
  name: string; tier: string; flight_no: string; dest_city: string; message: string
  summary: string; urgency: number; needs: string[]; reader: string; checks?: boolean; reply?: string; confirmation?: string
}) {
  const shown = needs.filter((n) => n !== 'none')
  return (
    <section className={`card passenger-detail ${checks?'':'sms-thread'}`} aria-label="Passenger request">
      <header className="passenger-identity"><span className="passenger-initials" aria-hidden="true">{name.split(' ').map(n=>n[0]).slice(0,2).join('')}</span><div><h2>{name}</h2><p>Passenger / {flight_no} to {dest_city} / {tier}</p></div></header>
      {!checks && <SmsConversation key={name} name={name} message={message} reply={reply} confirmation={confirmation} />}
      {checks && <div className="request-section"><h3>Request assessment</h3><p>{summary}</p>
        {shown.length>0 && <p className="request-requirements">{shown.join(' / ')}</p>}
        <div className="request-classification"><span className="priority-label" data-high={urgency>=4}>{priority(urgency)}</span><span>Classified by {reader}</span></div>
      </div>}

    </section>
  )
}

function Drafting({ row, reader }: { row: ResolutionRow; reader: string; agent: string }) {
  return (
    <div>
      <nav className="conversation-views" aria-label="Request view"><button type="button" aria-pressed="true">Conversation</button><button type="button" disabled>Checks &amp; tools</button></nav>
      <Header name={row.name} tier={row.tier} flight_no={row.flight_no} dest_city={row.dest_city}
              message={row.message ?? ''} summary={row.summary} urgency={row.urgency}
              needs={row.needs ?? []} reader={reader} />
      <div className="card recovery-preparing" style={{ marginTop: 16 }}>
        <div className="section-label" style={{ marginBottom: 8 }}>Preparing reply</div>
        <div style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)' }}>
          Checking the booking, flights, and passenger history.
        </div>
      </div>
    </div>
  )
}

function Detail({ res, onApprove, busy, local, reader, agent, view, onView }: {
  res: Resolution; onApprove: () => void; busy: boolean; local: boolean; reader: string; agent: string; view: 'conversation'|'checks'; onView: (view: 'conversation'|'checks') => void
}) {
  const d = res.decision
  return (
    <div>
      <nav className="conversation-views" aria-label="Request view">
        <button type="button" aria-pressed={view==='conversation'} onClick={()=>onView('conversation')}>Conversation</button>
        <button type="button" aria-pressed={view==='checks'} onClick={()=>onView('checks')}>Checks &amp; tools <span>{res.tool_calls?.length ?? 0}</span></button>
      </nav>
      <Header checks={view==='checks'} name={res.name} tier={res.tier} flight_no={res.flight_no} dest_city={res.dest_city}
              message={res.message} summary={res.classification.summary}
              urgency={res.classification.urgency} needs={res.classification.needs} reader={reader} reply={d.reply}
              confirmation={exampleActive() && res.status==='approved' ? demoOutcome(res.id).confirmation : undefined} />


      {view==='conversation' ? <>
      <section className="card recovery-decision thread-step" aria-label="Proposed solution">
        <div className="decision-heading"><h3>{exampleActive()?res.status==='approved'?demoOutcome(res.id).title:'Preparing outcome':res.options.length?'Proposed flight':'Airport assistance'}</h3><span>Agent</span></div>
        <dl className="outcome-summary"><div><dt>Status</dt><dd>{exampleActive()?res.status==='approved'?'Complete':'Processing automatically':'Ready for review'}</dd></div><div><dt>{res.options.length?'Flight':'Next step'}</dt><dd>{res.options.length?res.options.find(o=>o.id===d.recommended_option)?.flight ?? 'Checking options':'Airport staff assistance'}</dd></div><div><dt>What happens next</dt><dd>{exampleActive()?res.status==='approved'?demoOutcome(res.id).next:'The airport will confirm the outcome in the conversation.':'Review the proposed response.'}</dd></div></dl>
        {(d.goodwill_miles > 0 || d.vouchers.length > 0) && <div className="decision-benefits">
          {d.goodwill_miles > 0 && <span>{d.goodwill_miles.toLocaleString()} goodwill miles</span>}
          {d.vouchers.map(v=><span key={v}>{v} voucher</span>)}
        </div>}
        <details className="decision-details"><summary>Why this outcome</summary><div className="decision-copy">{paragraphs(d.why)}</div>
          {d.actions.length > 0 && <ul>{d.actions.map((a,i)=><li key={i}>{a}</li>)}</ul>}
          {!exampleActive() && <p>{`${agent}${local ? ' / local stand-in' : ''} / ${res.tokens_in.toLocaleString()} input / ${res.tokens_out.toLocaleString()} output tokens / ${(res.latency_ms / 1000).toFixed(1)}s`}</p>}
        </details>
        {!exampleActive() && <div className="reply-action">
          {res.status === 'approved'
            ? <span className="reply-confirmed">{exampleActive() ? res.options.length ? 'Sample approved / not saved' : 'Sample handoff acknowledged' : 'Review saved'}</span>
            : <button className="btn red" onClick={onApprove} disabled={busy}>{busy ? 'Approving…' : exampleActive() ? res.options.length ? 'Accept offer / demo' : 'Confirm assistance / demo' : 'Save review'}</button>}
        </div>}
      </section>

      </> : <div className="conversation-evidence">
      {(res.tool_calls?.length ?? 0) > 0 && (
        <section className="card recovery-tools" aria-label="Tool activity">
          <div className="tools-heading"><h3>Tool activity</h3><span>{res.tool_calls!.length} {res.tool_calls!.length===1?'call':'calls'}{exampleActive() ? ' / simulated' : ''}</span></div>
          {res.tool_calls!.map((c, i) => (
            <article className={`tool-exchange${c.error ? ' failed' : ''}`} key={`${i}-${c.tool}`}>
              <header><strong>{c.tool.replaceAll('_',' ')}</strong><span>{c.error ? 'Failed' : 'Returned'} / {c.ms} ms</span></header>
              <div className="tool-request"><span className="tool-role">Input</span><dl>{Object.entries(c.args).map(([key,value])=><div key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{typeof value === 'string' ? value : JSON.stringify(value)}</dd></div>)}</dl></div>
              <div className="tool-result"><span className="tool-role">{c.error ? 'Error' : 'Result'}</span><p>{c.preview || (c.error ? 'The tool returned an error.' : 'No result preview available.')}</p></div>
            </article>
          ))}
        </section>
      )}

      <div className="card-row recovery-context">
        <div className="card recovery-options">
          <div className="decision-heading"><h3>Available options</h3></div>
          {res.options.length===0 && <p className="empty-note">No suitable flights found. Staff review required.</p>}
          {res.options.map((o) => {
            const pick = o.id === d.recommended_option
            const backup = o.id === d.backup_option
            return (
              <div key={o.id} className={`recovery-option${pick ? ' recommended' : ''}`}>
                <div className="option-heading"><strong>{o.carrier} {o.flight}</strong>{(pick || backup) && <span>{pick ? 'Recommended' : 'Alternative'}</span>}</div>
                <p>{o.when}</p>
                {o.seats && <small>{o.seats}</small>}
              </div>
            )
          })}
          {!exampleActive() && <div style={{ fontSize: 'var(--ui-meta)', color: 'var(--text-muted)', marginTop: 6 }}>Options read from this run’s Couchbase record.</div>}
        </div>
      </div>

      {res.agent_via === 'prefetch_fallback' && (
        <div style={{ fontSize: 'var(--ui-label)', color: 'var(--cb-burgundy)', marginTop: 12 }}>
          MCP was unavailable for this draft; the app gathered the context with SQL++ instead.
        </div>
      )}

      </div>}
    </div>
  )
}
