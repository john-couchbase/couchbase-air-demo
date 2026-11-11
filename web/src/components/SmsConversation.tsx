import { liveGeneration } from '../lib/api'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { exampleActive, simulationRunId, simulationStory } from '../lib/example'

const histories = new Map<string, { shown: number; elapsed: number }>()
const lines = (text: string) => text.split(/(?<=[.!?])\s+(?=[A-ZI])/).filter(Boolean)
export default function SmsConversation({ name, message, reply, confirmation }: { name:string; message:string; reply?:string; confirmation?:string }) {
  const key = `${exampleActive()?simulationRunId():liveGeneration}-${name}-${message}`
  if (!histories.has(key)) histories.set(key, {shown:1,elapsed:0})
  const progress = histories.get(key)!
  const [shown,setShown] = useState(progress.shown)
  const entries = [...lines(message).map(text=>({text,airport:false})), ...lines(reply ?? '').map(text=>({text,airport:true})), ...(confirmation?[{text:confirmation,airport:true}]:[])]
  const signature = JSON.stringify(entries)
  const viewport = useRef<HTMLDivElement>(null)
  const follow = useRef(true)
  useEffect(() => {
    const timer = window.setInterval(() => {
      if(document.hidden || (exampleActive() && simulationStory().paused) || progress.shown>=entries.length) return
      progress.elapsed+=100
      const wait = entries[progress.shown]?.airport ? 1500 : 900
      if(progress.elapsed>=wait) { progress.elapsed=0; progress.shown++; setShown(progress.shown) }
    },100)
    return ()=>window.clearInterval(timer)
  },[key,signature])
  const typing = (entries[shown]?.airport || (!reply && shown>=entries.length)) && !(exampleActive() && simulationStory().paused)
  useLayoutEffect(()=>{ const el=viewport.current; if(el && follow.current) el.scrollTop=el.scrollHeight },[shown,typing])
  return <div ref={viewport} className="sms-viewport" role="log" aria-label={`Conversation with ${name}`} aria-live="polite" aria-relevant="additions" tabIndex={0} onScroll={()=>{const el=viewport.current; if(el) follow.current=el.scrollHeight-el.scrollTop-el.clientHeight<36}}>
    {entries.slice(0,shown).map((entry,i)=><div key={i} className={`sms-message ${entry.airport?'sms-outgoing':'sms-incoming'}`}><span className="sms-sender">{entry.airport?(exampleActive()?'Airport support':'Airport support draft'):name.split(' ')[0]}</span><div className="sms-bubble"><p>{entry.text}</p></div></div>)}
    {typing && <div className="sms-message sms-outgoing sms-typing" role="status" aria-label="Airport support is typing"><span className="sms-sender">Airport support</span><div className="sms-bubble" aria-hidden="true"><i/><i/><i/></div></div>}
  </div>
}
