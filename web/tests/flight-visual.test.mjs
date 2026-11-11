import assert from 'node:assert/strict'
import {flightVisual} from '../src/lib/flightVisual.ts'
import {startExample,exampleResponse as api,simulationStory} from '../src/lib/example.ts'
let now=100000;Date.now=()=>now
startExample();api('/api/storm')
assert.equal(flightVisual(simulationStory().current.kind).normal,true)
now+=2000;assert.equal(flightVisual(simulationStory().current.kind).jfk,'Cancelled / help requested')
now+=12000;assert.equal(flightVisual(simulationStory().current.kind).failure,true)
api('/api/pause');now+=30000;assert.equal(flightVisual(simulationStory().current.kind).failure,true)
api('/api/resume');now+=4000
const outcome=flightVisual(simulationStory().current.kind)
assert.equal(outcome.outcome,true);assert.match(outcome.jfk,/not booked/);assert.match(outcome.sea,/staff review/)
now+=30000;assert.equal(flightVisual(simulationStory().current.kind).settled,true)
assert.equal(flightVisual(simulationStory().current.kind).normal,false)
console.log('Passed: map follows cancellation, failure, paused retry, proposed replacement and final handoff without implying a booking.')
