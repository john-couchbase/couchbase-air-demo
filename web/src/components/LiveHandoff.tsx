import type { State } from '../lib/types'
import { agentName, classifyName } from '../lib/models'
import './LiveHandoff.css'

export default function LiveHandoff({state, example, onOpenRequest}:{state:State|null;example:boolean;onOpenRequest:(id:string)=>void}) {
  const flow=state?.flow
  const active=flow?.active
  const latest=flow?.events.at(-1)
  const request=active?.request_id ?? latest?.request_id
  const visited=new Set(flow?.events.filter(e=>e.request_id===request).map(e=>e.stage))
  const status=state?.error ? 'Request interrupted' : active ? 'Processing request' : state?.run_status==='complete' ? 'Run complete' : state?.paused ? 'Paused' : latest ? 'Waiting for next step' : example ? 'Live backend required' : 'Ready for the storm'
  const nodes=[
    {id:'context',title:'Message',sub:'Load request',count:state?.funnel.inbound ?? 0},
    {id:'classify',title:'Classify',sub:classifyName(state),count:state?.funnel.classified ?? 0},
    {id:'route',title:'Route',sub:'Urgency 3 or higher',count:(flow?.reasoned ?? 0)+(flow?.standard ?? 0)},
    {id:'reason',title:'Reason',sub:agentName(state),count:flow?.reasoned ?? 0},
    {id:'standard',title:'Standard handling',sub:'No reasoning call',count:flow?.standard ?? 0},
  ]
  return <section className="live-handoff" aria-label="Live model handoff">
    <header><div><h3>Behind the response</h3><p>Classify every request. Use reasoning only when needed.</p></div><span role="status">{status}</span></header>
    <div className="handoff-track">
      {nodes.map(n=><div key={n.id} className={`handoff-node handoff-${n.id}${active?.stage===n.id?' is-active':''}${visited.has(n.id)?' is-visited':''}`} aria-current={active?.stage===n.id?'step':undefined}>
        <div><strong>{n.title}</strong><span className="handoff-count">{n.count}</span></div>
        <p>{n.sub}</p><span className="handoff-state">{active?.stage===n.id?'Running now':visited.has(n.id)?'Reached for this request':n.id==='reason'?'Recovery branch':n.id==='standard'?'Routine branch':'Waiting'}</span>
      </div>)}
    </div>
    <footer><span>{request ? `Request ${request.replace('sample-','')}` : 'Boxes light up as the backend reaches each step.'}</span>{request && <button className="btn" onClick={()=>onOpenRequest(request)}>View request</button>}</footer>
  </section>
}
