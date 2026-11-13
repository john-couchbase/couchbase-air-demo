import type { State } from '../lib/types'
import { agentName, classifyName, viaSqlpp } from '../lib/models'
import './LiveHandoff.css'

export default function LiveHandoff({state, example, onOpenRequest}:{state:State|null;example:boolean;onOpenRequest:(id:string)=>void}) {
  const flow=state?.flow
  const active=flow?.active
  const latest=flow?.events.at(-1)
  const request=active?.request_id ?? latest?.request_id
  const visited=new Set(flow?.events.filter(e=>e.request_id===request).map(e=>e.stage))
  const status=state?.error ? 'Interrupted' : active?.stage==='reason' ? (example ? 'Classification to reasoning' : 'Classification to Claude') : active?.stage==='classify' ? 'Classifying request' : active ? 'Checking routing' : state?.run_status==='complete' ? 'Complete' : state?.paused ? 'Paused' : latest ? 'Between steps' : example ? 'Simulation ready' : 'Ready'
  const cls=state?.funnel.classified ?? 0
  const reasoned=flow?.reasoned ?? 0
  const standard=flow?.standard ?? 0
  const block=(stage:string,title:string,description:string,count:number,model=false)=>
    <div className={`processing-node node-${stage}${model?' model-node':''}${active?.stage===stage?' is-active':''}${visited.has(stage)?' was-reached':''}`} aria-current={active?.stage===stage?'step':undefined}>
      <div className="processing-node-heading"><strong>{title}</strong><span>{count}</span></div>
      <p>{description}</p>
      <div className="processing-indicator"><span className="activity-slot" aria-hidden="true"/><span>{active?.stage===stage?'Running':visited.has(stage)?'Reached':model?'Standby':'Waiting'}</span></div>
    </div>
  return <section className="live-handoff" aria-label={example ? "Simulated model handoff" : "Live model handoff"}>
    <header className="processing-heading"><div><span className="processing-eyebrow">Behind the scenes</span><h2>{example ? "Simulated processing" : "Live processing"}</h2><p>Every request is classified. Only recovery requests reach the reasoning model.</p></div><span className="processing-status" role="status">{status}</span></header>
    <div className="processing-board">
      <div className="processing-column-label">Requests</div><div className="processing-column-label">Couchbase SQL++</div><div className="processing-column-label">Model Service</div>
      <div className="processing-incoming">{block('context','Incoming messages','Request context',state?.funnel.inbound ?? 0)}</div>
      <div className={`processing-classifier${active?.stage==='classify'?' path-active':''}`}>{block('classify',viaSqlpp(state)?'AI Function':'Classification','Identify intent and urgency',cls)}</div>
      <div className="processing-small">{block('classify',classifyName(state),'Smaller model',cls,true)}</div>
      <div className={`processing-router${active?.stage==='reason'?' path-active':''}`}>{block('route','Recovery filter','Urgency 3+ goes to reasoning',reasoned+standard)}</div>
      <div className={`processing-reasoning${active?.stage==='reason'?' handoff-running':''}`}>{block('reason',agentName(state),'Reasoning model',reasoned,true)}</div>
    </div>
    <footer><span className="routing-summary">{standard} finished without reasoning / {reasoned} used {example ? 'reasoning' : 'Claude'}</span><span>{request ? `Current request ${request.replace('sample-','')}` : 'Lighted boxes show the current backend step.'}</span>{request && <button className="btn" onClick={()=>onOpenRequest(request)}>View request</button>}</footer>
  </section>
}
