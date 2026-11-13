import type { State, Resolution, FeedRow } from './types'
let active = false
let runId = 0
export const simulationRunId = () => runId
let started = 0
let pausedAt = 0
let approved = false
let handoff = false
let advanced = 0
export const exampleActive = () => active
export const startExample = () => { runId++; active = true; started = 0; pausedAt = 0; approved = false; handoff = false; advanced = 0 }
export const resetExample = () => { active = false; started = 0; pausedAt = 0; approved = false; handoff = false; advanced = 0 }
const count = () => started ? Math.min(24, 5 + Math.floor(((pausedAt || Date.now()) - started) / 2000) + advanced) : 5
export const advanceExample = () => { if (!started) started=Date.now(); const n=count(); advanced += ([6,8,10,12,14,24].find(at=>at>n) ?? n) - n }
export const exampleStep = () => !started ? 0 : count() < 10 ? 1 : count() < 14 ? 2 : 3
const classification = { intent: 'rebook', urgency: 5, sentiment: 'concerned', needs: ['deadline'], language: 'en', summary: 'Needs to reach New York tonight for an early appointment.', model: 'Sample classifier' }
export const sampleResolution = (): Resolution => ({
 id:'sample-001', name:'Alex Morgan', tier:'Gold', flight_no:'AIR 204', dest_city:'New York',
 message:'My flight was cancelled. Can I get to New York tonight? I have an appointment at 9 tomorrow morning.',
 classification, options:[{id:'evening',carrier:'AIDP Air',flight:'AIR 218',when:'Tonight / 19:30',seats:'Available in example'},{id:'morning',carrier:'AIDP Air',flight:'AIR 302',when:'Tomorrow / 10:00',seats:'Available in example'}],
 decision:{recommended_option:'evening',backup_option:'morning',why:'Recommend AIR 218 tonight. Tomorrow’s flight misses the appointment.',goodwill_miles:0,vouchers:['meal'],actions:['Offer the evening flight after the hub reopens.'],reply:'I found AIR 218 tonight with a meal voucher. I’m updating your booking now.',memory_note:'Sample only: evening flight offered.'},
 memory_used:{disruptions:[],preferences:{},notes:['Arrive before morning appointments.'],source:'collection'},
 tool_calls:[{tool:'booking_lookup',args:{flight:'AIR 204'},ms:180,chars:82,error:false,preview:'Flight cancelled; passenger needs to arrive tonight.'},{tool:'flight_search',args:{destination:'JFK',attempt:1},ms:2000,chars:0,error:true,preview:'Simulated timeout; no response received.'},{tool:'flight_search',args:{destination:'JFK',attempt:2},ms:240,chars:110,error:false,preview:'Retry succeeded: AIR 218 tonight; AIR 302 tomorrow.'}],
 prompt:'',model:'Scripted example / no model called',tokens_in:0,tokens_out:0,latency_ms:0,status:(approved || count()>=24)?'approved':'drafted'
})
export function secondResolution(): Resolution {
 const r=sampleResolution()
 return {...r,id:'sample-002',name:'Sam Rivera',tier:'Silver',flight_no:'AIR 410',dest_city:'Seattle',
 message:'My Seattle flight was cancelled. I need two seats together tonight for me and my child.',
 classification:{...classification,summary:'Two seats together required tonight; no suitable inventory.',needs:['two adjacent seats'],urgency:4},options:[],
 decision:{recommended_option:'',backup_option:'',why:'No two seats together are available tonight. Refer to airport staff; keep the current booking.',goodwill_miles:0,vouchers:[],actions:['Send the request to an airport specialist.','Keep the original booking until a replacement is confirmed.'],reply:'I couldn’t find two seats together tonight. I’ll ask airport staff to help. Your booking is unchanged.',memory_note:'Sample handoff requested; no replacement booked.'},
 memory_used:{disruptions:[],preferences:{},notes:['Keep the family seated together.'],source:'collection'},
 tool_calls:[{tool:'flight_search',args:{destination:'SEA',seats:2,adjacent:true},ms:210,chars:36,error:false,preview:'No matching seats available tonight.'}],status:(handoff || count()>=24)?'approved':'drafted'}
}
export function serviceResolution(id: string): Resolution {
 const weather=id==='sample-003'
 const r=sampleResolution()
 return {...r,id,name:weather?'Jordan Lee':'Taylor Brooks',tier:'Standard',flight_no:weather?'AIR 520':'AIR 630',dest_city:weather?'San Francisco':'Miami',
 message:weather?'My SFO flight is delayed by lightning. Should I stay at the gate or find another flight?':'My Miami flight moved to gate C18. I booked wheelchair assistance. Will someone help me get there?',
 classification:{...classification,intent:weather?'delay_status':'accessibility',urgency:weather?3:4,needs:[weather?'updated departure time':'wheelchair assistance'],summary:weather?'Weather delay; confirm departure before changing the booking.':'Gate change; coordinate assistance to the new gate.'},
 options:[{id:'keep',carrier:'AIDP Air',flight:weather?'AIR 520':'AIR 630',when:weather?'Updated departure / 20:15':'Boarding / gate C18',seats:'Existing seat retained'}],
 decision:{recommended_option:'keep',backup_option:'',why:weather?'The flight is delayed, not cancelled. The updated departure is earlier than the available replacement.':'The flight is operating. The gate changed, so assistance needs the new pickup location.',goodwill_miles:0,vouchers:[],actions:[weather?'Keep the booking and enable departure updates.':'Arrange assistance from the current gate to C18.'],reply:weather?'Lightning has paused ramp operations. AIR 520 is now expected at 20:15. Please stay in the terminal. I’ll keep your seat and enable departure updates.':'Your flight is boarding at C18. I found your assistance request. I’m arranging pickup at your current gate, B6. Please wait there for the team.',memory_note:weather?'Demo departure updates enabled.':'Demo assistance pickup arranged at B6.'},
 memory_used:{disruptions:[],preferences:{},notes:weather?[]:['Wheelchair assistance requested.'],source:'collection'},
 tool_calls:weather?[{tool:'weather_status',args:{airport:'SFO'},ms:140,chars:75,error:false,preview:'Lightning restriction; ramp operations paused. Next update in 15 minutes.'},{tool:'flight_status',args:{flight:'AIR 520'},ms:180,chars:65,error:false,preview:'Delayed to 20:15; not cancelled. Seat retained.'},{tool:'flight_search',args:{destination:'SFO'},ms:210,chars:55,error:false,preview:'Next alternative departs at 22:40; later than the current flight.'}]:[{tool:'gate_lookup',args:{flight:'AIR 630'},ms:110,chars:40,error:false,preview:'Gate changed from B6 to C18. Flight operating.'},{tool:'assistance_dispatch',args:{pickup:'B6',destination:'C18',service:'wheelchair'},ms:220,chars:65,error:false,preview:'Demo team assigned to B6; estimated pickup in 10 minutes.'}],status:count()>=24?'approved':'drafted'}
}
export const demoResolution = (id: string) => id==='sample-002'?secondResolution():id==='sample-003'||id==='sample-004'?serviceResolution(id):sampleResolution()
export const demoOutcome = (id: string) => id==='sample-003'
 ? {title:'Departure updates enabled',next:'Keep your seat and watch for the next departure update.',confirmation:'Departure updates are enabled for your flight. Your seat on AIR 520 is unchanged.'}
 : id==='sample-004'
 ? {title:'Assistance arranged',next:'Wait at B6 for the assistance team.',confirmation:'Your assistance pickup is arranged at B6 in about 10 minutes. The team will take you to C18.'}
 : id==='sample-002'
 ? {title:'Airport assistance',next:'Airport staff will review the seating request.',confirmation:'I’ve passed your case to airport staff. Your original booking stays unchanged.'}
 : {title:'Booking updated',next:'Read the confirmation in the conversation.',confirmation:'Your booking is now on AIR 218 tonight. Your meal voucher is included.'}
export function simulationStory() {
 const n=count()
 const events=[
  {at:5,title:'Flights operating normally',detail:'AIR 204 to New York and AIR 410 to Seattle are boarding. Two routine messages arrive per interval.',kind:'normal'},
  {at:6,title:'Storm closes departures',detail:'O’Hare pauses takeoffs. AIR 204 and AIR 410 are cancelled; SFO has a lightning delay. Miami changes gates.',kind:'storm'},
  {at:8,title:'Passenger messages surge',detail:'Alex needs New York tonight. Sam needs two seats together. Jordan asks about the SFO delay. Taylor needs help reaching Miami’s new gate.',kind:'messages'},
  {at:10,title:'Urgent requests go to Recovery',detail:'Deadline and family-seating needs require decisions. Weather and accessibility checks use different tools. The routine gate question uses the cache.',kind:'classify'},
  {at:12,title:'Flight lookup times out',detail:'The first New York search returns no response. No booking is changed; a retry is scheduled.',kind:'failure'},
  {at:14,title:'Retry succeeds; one case is blocked',detail:'Alex can take AIR 218 tonight. No suitable Seattle seats exist for Sam, so the agent prepares a staff handoff.',kind:'decision'},
  {at:24,title:'Demo adjustments complete',detail:'Alex’s demo booking moves to AIR 218. Sam’s demo case goes to airport staff; the original booking stays unchanged. SFO keeps its seat with departure updates. Miami gets assistance to C18. No real booking is changed.',kind:'review'},
 ]
 const reached=events.filter(e=>e.at<=n)
 return {current:reached.at(-1)!,events:reached,finished:n===24,started:!!started,paused:!!pausedAt}
}
const timeline = Array.from({length:24}, (_,i) => {
 const surge = i >= 5 && i < 14 ? [4,8,16,20,16,12,8,4,2][i-5] : 0
 return {t:i*5,baseline:2,surge,classified:2+surge,hits:1,classify_usd:.001,agent_usd:i===10?.048:0,agent_calls:i===10?4:0,reserved_rate:.003,serverless_cum:(i+1)*.001+(i>=10?.048:0),reserved_cum:(i+1)*.003}
})
export function sampleState(): State {
 const n=count(), step=exampleStep(), rows=timeline.slice(0,n)
 const inbound=rows.reduce((v,r)=>v+r.baseline+r.surge,0), calls=inbound-n
 const classify=n*.001, agent=n>10?.048:0
 const stages=['context','classify','route','reason'];const stageIndex=n<10?Math.min(2,Math.max(0,n-5)%3):Math.min(3,(n-10)%4);const request_id='sample-'+String(Math.min(4,Math.max(1,Math.floor((n-10)/4)+1))).padStart(3,'0');
 return {flow:{active:started&&n<24&&!pausedAt?{stage:stages[stageIndex],request_id}:null,events:started?stages.slice(0,stageIndex+1).map(stage=>({stage,request_id,ts:Date.now()})):[],reasoned:step>=2?4:0,standard:Math.max(0,inbound-(step>=2?4:0))},phase:!started?'normal':n<10?'storm':n<24?'recovering':'quiet',paused:pausedAt?'user':null,elapsed_s:n*5,storm_at_s:started?25:null,quiet_at_s:n===24?120:null,
 funnel:{inbound,classified:inbound,surge:inbound-n*2,escalated:step>=2?4:0,in_agent:step===2?4:0,approved:count()>=24?4:Number(approved)+Number(handoff)},
 cache:{hits:n,misses:calls,entries:n,avoided_usd:n/24*.005},spend:{classify,agent,total:classify+agent},tokens:{classify:{in:calls*100,out:calls*20,calls},agent:{in:agent?7200:0,out:agent?1680:0,calls:agent?4:0}},reserved:{label:'Illustrative GPU',per_hour:2.16,so_far:n*.003},models:{classify:'sample',agent:'sample'},model_names:{classify:{name:'Sample classifier',short:'Sample classifier'},agent:{name:'Sample reasoning',short:'Sample reasoning'}},backend:{endpoint:'Scripted locally',models:'local_standin',cache:'local_standin',ai_functions:'local_standin',classify_via:'backend',stand_ins:{sample:'Scripted example'},memory:'collection'},live:{window_s:10,arrivals_per_s:0,classify_per_s:0,cache_per_s:0,classify_in_flight:0,classify_slots:4,agent_in_flight:0,agent_slots:1,spend_per_min:.018,reserved_per_min:.036}}
}
export function exampleResponse(path:string) {
 if(path==='/api/storm') { runId++; started=Date.now(); pausedAt=0; approved=false; handoff=false; advanced=0; return {phase:'storm'} }
 if(path==='/api/reset') { startExample(); return {phase:'normal'} }
 if(path==='/api/pause') { if(started && !pausedAt) pausedAt=Date.now(); return {paused:'user'} }
 if(path==='/api/resume') { if(pausedAt) { started+=Date.now()-pausedAt; pausedAt=0 }; return {paused:null} }
 const step=exampleStep(), r=sampleResolution(), second=secondResolution(), s=sampleState()
 if(path.startsWith('/api/state')) return sampleState()
 if(path==='/api/timeline') return {bucket_s:5,storm_at_s:s.storm_at_s,quiet_at_s:s.quiet_at_s,rows:timeline.slice(0,count())}
 if(path.startsWith('/api/feed')) return step<1?[]:[r,second,serviceResolution('sample-003'),serviceResolution('sample-004')].map<FeedRow>((item)=>({id:item.id,ts:0,kind:'surge',channel:'chat',language:'en',text:item.message,classification:step>=2?item.classification:undefined,escalated:step>=2,tier:item.tier,flight_no:item.flight_no,dest_city:item.dest_city})).concat(step>=2?[{id:'sample-cache',ts:0,kind:'baseline',channel:'chat',language:'en',text:'Where can I check my departure gate?',classification:{...classification,intent:'gate_status',urgency:1,needs:[],summary:'Use the departures board; gate assignments may change.',cache:'hit'},escalated:false,tier:'Standard',flight_no:'AIR 110',dest_city:'Dallas'}] as FeedRow[]:[])
 if(path==='/api/resolutions') return step<2?[]:[r,second,serviceResolution('sample-003'),serviceResolution('sample-004')].map(item=>({...item,status:step===2?'drafting':item.status,created:0,urgency:item.classification.urgency,summary:item.classification.summary,needs:item.classification.needs,chosen:item.decision.recommended_option}))
 if(path.endsWith('/approve')) {if(step<3) throw new Error('Sample decision is still drafting'); if(path.includes('sample-002')) {handoff=true;return secondResolution()} approved=true;return sampleResolution()}
 if(path.startsWith('/api/resolutions/')) return demoResolution(path.split('/')[3])
 if(path==='/api/sqlpp') return {classify:'-- Scripted preview. No query executed.',classify_prompt:'',funnel:'',context:'',partners:'',policy:'Sample: offer an available flight that meets the passenger’s deadline. Automatically apply the scripted demo outcome. SFO keeps its seat with departure updates. Miami gets assistance to C18. No real booking is changed.'}
 if(path==='/api/bill') return {statement:'',rows:[
  {job:'Classification',model:'Sample classifier',calls:s.tokens.classify.calls,cache_hits:s.cache.hits,tokens_in:s.tokens.classify.in,tokens_out:s.tokens.classify.out,spend_usd:s.spend.classify,avoided_usd:s.cache.avoided_usd,estimated:false},
  {job:'Decisions',model:'Sample reasoning',calls:s.tokens.agent.calls,cache_hits:0,tokens_in:s.tokens.agent.in,tokens_out:s.tokens.agent.out,spend_usd:s.spend.agent,avoided_usd:0,estimated:false}
 ]}
 if(path==='/api/models') return {catalog:[],backend:sampleState().backend}
 return {}
}
