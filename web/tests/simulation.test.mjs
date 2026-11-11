import assert from 'node:assert/strict'
import {startExample,resetExample,exampleActive,exampleResponse as api,sampleState,simulationStory,advanceExample} from '../src/lib/example.ts'
let now=100000; Date.now=()=>now
startExample(); assert.equal(sampleState().phase,'normal')
api('/api/storm'); now+=14000
assert.equal(simulationStory().current.kind,'failure')
assert.equal(api('/api/resolutions').length,4)
assert.ok(api('/api/resolutions').every(r=>r.status==='drafting'))
assert.throws(()=>api('/api/resolutions/sample-001/approve'))
api('/api/pause'); const elapsed=sampleState().elapsed_s; now+=50000
assert.equal(sampleState().elapsed_s,elapsed)
api('/api/resume'); advanceExample()
assert.equal(simulationStory().current.kind,'decision')
assert.ok(api('/api/resolutions').every(r=>r.status==='drafted'))
assert.ok(api('/api/resolutions/sample-001').tool_calls.some(c=>c.error))
assert.equal(api('/api/resolutions/sample-002').options.length,0)
api('/api/resolutions/sample-002/approve'); assert.equal(sampleState().funnel.approved,1)
assert.equal(api('/api/resolutions/sample-001').status,'drafted')
api('/api/resolutions/sample-001/approve'); assert.equal(sampleState().funnel.approved,2)
now+=60000
const s=sampleState(),t=api('/api/timeline'),b=api('/api/bill')
assert.equal(s.phase,'quiet');assert.equal(s.funnel.inbound,138)
assert.equal(t.rows.reduce((sum,r)=>sum+r.classified,0),s.funnel.classified)
assert.ok(Math.abs(t.rows.at(-1).serverless_cum-s.spend.total)<1e-9)
assert.ok(Math.abs(b.rows.reduce((sum,r)=>sum+r.spend_usd,0)-s.spend.total)<1e-9)
api('/api/reset');assert.equal(sampleState().funnel.approved,0);assert.equal(api('/api/resolutions').length,0)
resetExample();assert.equal(exampleActive(),false)
console.log('Passed: failure/retry, drafting guard, pause/resume, manual advance, independent outcomes, totals and reset.')
startExample(); api('/api/storm'); now+=18000
assert.ok(api('/api/resolutions').every(r=>r.status==='drafted'))
api('/api/pause'); now+=60000
assert.ok(api('/api/resolutions').every(r=>r.status==='drafted'))
api('/api/resume'); now+=20000
assert.ok(api('/api/resolutions').every(r=>r.status==='approved'))
assert.equal(sampleState().funnel.approved,4)
assert.equal(api('/api/resolutions/sample-002').options.length,0)
api('/api/reset'); assert.equal(sampleState().funnel.approved,0)
resetExample()
console.log('Passed: automatic demo outcomes respect pause, complete without approval, and reset.')

startExample(); api('/api/storm'); now+=18000
for (const [id,intent,tool] of [['sample-003','delay_status','weather_status'],['sample-004','accessibility','assistance_dispatch']]) {
 const r=api(`/api/resolutions/${id}`)
 assert.equal(r.id,id); assert.equal(r.classification.intent,intent)
 assert.ok(r.tool_calls.some(c=>c.tool===tool)); assert.ok(!r.message.includes('cancelled'))
 assert.equal(r.options[0].flight,r.flight_no)
}
assert.equal(api('/api/feed').filter(r=>r.escalated).length,4)
now+=40000; assert.equal(sampleState().funnel.approved,4)
assert.equal(api('/api/bill').rows[1].calls,4)
resetExample()
console.log('Passed: distinct weather and assistance cases, original flights retained, four outcomes and costs.')
