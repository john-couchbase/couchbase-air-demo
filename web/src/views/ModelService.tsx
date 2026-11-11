import Eyebrow from '../components/Eyebrow'
export default function ModelService() {
 return <div className="fade-in learn-view">
  <Eyebrow component="Model Service" tenets={[]} />
  <h1 style={{marginTop:8,marginBottom:6}}>Models in the workflow</h1>
  <p className="lede">Classification and recovery have different jobs. This demo separates them so you can inspect each stage.</p>
  <div className="reference-grid">
   <section className="card"><h3>Classify the request</h3><p>Identify intent, urgency, and constraints before deciding whether a request needs recovery support.</p></section>
   <section className="card"><h3>Review the evidence</h3><p>Use booking details, flight availability, and passenger context to prepare an option or a handoff.</p></section>
   <section className="card"><h3>Reuse an answer</h3><p>The gate-status example illustrates a cache hit. It does not perform a semantic lookup in this replay.</p></section>
   <section className="card"><h3>Keep simulation explicit</h3><p>The demo applies scripted outcomes automatically. No real booking or passenger record is changed.</p></section>
  </div>
  <p className="reference-note">These are workflow roles, not a service-health report. In simulation mode, model outputs and costs are scripted.</p>
 </div>
}
