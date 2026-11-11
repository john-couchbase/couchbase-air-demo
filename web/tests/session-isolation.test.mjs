import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
// Separate module instances represent the separate JS runtimes of browser tabs.
const a = await import('../src/lib/example.ts?visitor=a')
const b = await import('../src/lib/example.ts?visitor=b')
let now = 100000
Date.now = () => now
for (const run of [a,b]) { run.startExample(); run.exampleResponse('/api/storm') }
now += 18000
a.exampleResponse('/api/pause')
const paused = a.sampleState().elapsed_s
now += 10000
assert.equal(a.sampleState().elapsed_s, paused)
assert.ok(b.sampleState().elapsed_s > paused)
const before = b.sampleState()
a.startExample(); a.exampleResponse('/api/storm')
assert.deepEqual(b.sampleState(), before)
a.exampleResponse('/api/reset')
assert.deepEqual(b.sampleState(), before)
a.resetExample()
assert.equal(b.exampleActive(), true)
assert.deepEqual(b.sampleState(), before)
// A simulation bundle must intercept both reads and writes even after reset.
const source = readFileSync(new URL('../src/lib/api.ts', import.meta.url),'utf8')
for (const name of ['get','post']) {
 const body=source.slice(source.indexOf(`async function ${name}`))
 assert.ok(body.indexOf("import.meta.env.MODE === 'simulation' || exampleActive()") < body.indexOf('await fetch('))
}
console.log('Passed: separate visitors pause, restart and reset independently; simulation reads/writes cannot fall through to shared backend.')
