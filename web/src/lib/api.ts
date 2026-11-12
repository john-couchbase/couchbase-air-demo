import { exampleActive, exampleResponse } from './example'
import type {
  Bill, FeedRow, ModelsInfo, Resolution, ResolutionRow, Sqlpp, State, Timeline,
} from './types'

let session: Promise<string> | undefined
export let liveGeneration = ''
async function headers() {
  session ??= fetch('/api/session', {method:'POST'}).then(async r => {
    if(!r.ok) throw new Error('Could not start a private run')
    return (await r.json()).token as string
  }).catch(e => { session=undefined; throw e })
  return {Authorization:`Bearer ${await session}`}
}

async function get<T>(path: string): Promise<T> {
  if (import.meta.env.MODE === 'simulation' || exampleActive()) return exampleResponse(path) as T
  const r = await fetch(path, {headers:await headers()})
  if (import.meta.env.MODE === 'simulation' || exampleActive()) return exampleResponse(path) as T
  if (!r.ok) { const error=await r.json().catch(()=>({})); throw new Error(error.error || error.detail || `Request failed (${r.status})`) }
  return r.json()
}

async function post<T>(path: string): Promise<T> {
  if (import.meta.env.MODE === 'simulation' || exampleActive()) return exampleResponse(path) as T
  const r = await fetch(path, { method: 'POST', headers:await headers() })
  if (!r.ok) { const error=await r.json().catch(()=>({})); throw new Error(error.error || error.detail || `Request failed (${r.status})`) }
  return r.json()
}

// Only a tab in front of someone counts as watching; the server pauses the
// demo when nobody has been, so a forgotten background tab does not keep it running.
export const getState = async () => { const s=await get<State>(`/api/state?watching=${document.visibilityState === 'visible'}`); liveGeneration=s.generation ?? ''; return s }
export const getTimeline = () => get<Timeline>('/api/timeline')
export const getFeed = (limit = 14) => get<FeedRow[]>(`/api/feed?limit=${limit}`)
export const getResolutions = () => get<ResolutionRow[]>('/api/resolutions')
export const getResolution = (id: string) => get<Resolution>(`/api/resolutions/${id}`)
export const approve = (id: string) => post<Resolution>(`/api/resolutions/${id}/approve`)
export const getBill = () => get<Bill>('/api/bill')
export const getSqlpp = () => get<Sqlpp>('/api/sqlpp')
export const getModels = () => get<ModelsInfo>('/api/models')
export const storm = () => post<{ phase: string }>('/api/storm')
export const reset = () => post<{ phase: string }>('/api/reset')
export const pause = () => post<{ paused: string | null }>('/api/pause')
export const resume = () => post<{ paused: string | null }>('/api/resume')

export const advance = () => post<{advanced:boolean}>('/api/advance')

export const getCommands = () => get<{mode:string;sections:{id:string;title:string;kind:string;note:string;code:string}[]}>('/api/commands')
