import { useEffect, useState } from 'react'
import { Copy } from 'lucide-react'
import commands from '../lib/commands.json'
import { getCommands } from '../lib/api'
import type { State } from '../lib/types'

const groups = [
  { title: 'Workflow', ids: ['classify', 'context', 'partners', 'funnel', 'agent', 'usage', 'save'] },
  { title: 'Policy & prompts', ids: ['policy', 'classify_prompt'] },
]

export default function Sqlpp({ state, example }: { state: State | null; example: boolean }) {
  const [catalogue, setCatalogue] = useState<typeof commands | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let active = true
    setCatalogue(null); setFailed(false)
    if (!example) getCommands().then(value => { if (active) setCatalogue(value) }).catch(() => { if (active) setFailed(true) })
    return () => { active = false }
  }, [example])
  const sections = example ? commands.sections : catalogue?.sections ?? []
  const sqlStatus = example ? 'Sample data' : !state ? 'Checking…' : state.backend.classify_via === 'sqlpp' ? 'Configured' : 'Not configured'

  const [open, setOpen] = useState<string | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const copyCommand = async (id: string, code: string) => {
    try { await navigator.clipboard.writeText(code); setCopied(id) }
    catch { setCopied('error-' + id) }
    window.setTimeout(() => setCopied(null), 2500)
  }
  return <div className="fade-in learn-view command-view">
    <header className="command-heading"><h1>Commands</h1>
      <p className="lede">The queries and rules behind each request.</p></header>
    <aside className="command-context" aria-label="Connection details">
      <dl><div><dt>Model connection</dt><dd>{example ? 'Sample data' : 'Capella Model Service'}</dd></div><div><dt>SQL inference</dt><dd>{sqlStatus}</dd></div><div><dt>Memory</dt><dd>Off</dd></div></dl>
      <p className="command-reference-label">Reference code, not an execution log.</p>
    </aside>
    {!example && !catalogue && <p className="reference-note" role="status">{failed ? 'Could not load current commands. Reopen this page to retry.' : 'Loading current commands…'}</p>}
    {(example || catalogue) && groups.map(group => <section className="command-group" key={group.title} aria-label={group.title}>
      <h2>{group.title}</h2>
      <div className="command-list">
        {sections.filter(section => group.ids.includes(section.id)).map(section => <section className="command-card" data-open={open === section.id} key={section.id}>
          <button className="command-toggle" aria-expanded={open === section.id} aria-controls={`command-${section.id}`} onClick={() => setOpen(open === section.id ? null : section.id)}>
            <span className="command-label"><strong>{section.title}</strong><span>{section.kind}</span></span><span className="command-indicator" aria-hidden="true">{open === section.id ? '−' : '+'}</span>
          </button>
          <div id={`command-${section.id}`} className="command-content" hidden={open !== section.id}>
            <div className="command-code-heading"><p>{section.note}</p><button type="button" className="command-copy" onClick={() => copyCommand(section.id, section.code)} aria-label={`Copy ${section.title} command`}><Copy size={16} aria-hidden="true"/><span aria-live="polite">{copied === section.id ? 'Copied!' : copied === 'error-' + section.id ? 'Try again' : 'Copy'}</span></button></div><pre className="code" tabIndex={0} aria-label={`${section.title} code`}>{section.code}</pre>
          </div>
        </section>)}
      </div>
    </section>)}
  </div>
}
