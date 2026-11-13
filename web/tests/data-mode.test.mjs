import assert from 'node:assert/strict'
import ts from 'typescript'
import {readFileSync,mkdtempSync,writeFileSync,rmSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {pathToFileURL} from 'node:url'
const dir=mkdtempSync(join(tmpdir(),'air-mode-'))
try {
 for(const name of ['example','api']){const code=ts.transpileModule(readFileSync(new URL(`../src/lib/${name}.ts`,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText.replace("'./example'","'./example.mjs'");writeFileSync(join(dir,name+'.mjs'),code)}
 const example=await import(pathToFileURL(join(dir,'example.mjs'))),api=await import(pathToFileURL(join(dir,'api.mjs')))
 globalThis.document={visibilityState:'visible'};let calls=0
 globalThis.fetch=async()=>{calls++;throw Error('Backend offline')}
 example.startExample();await api.storm();assert.equal((await api.getState()).phase,'storm');await api.getFeed();await api.getBill();await api.getResolutions();assert.equal(calls,0)
 example.resetExample();await assert.rejects(api.getState(),/Backend offline/);assert.equal(calls,1)
 example.startExample();await api.getState();assert.equal(calls,1)
 console.log('Passed: simulation works offline without network calls; live uses backend; returning to simulation remains offline.')
} finally {rmSync(dir,{recursive:true,force:true})}
