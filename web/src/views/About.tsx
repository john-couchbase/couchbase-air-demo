export default function About() {
 return <div className="fade-in learn-view">
  <div className="eyebrow">Couchbase / Architecture reference</div>
  <h1 style={{marginTop:8,marginBottom:6}}>Data behind the decision</h1>
  <p className="lede">The demo brings passenger context, tool results, and a recommendation into one review flow.</p>
  <div className="reference-grid">
   {[
    ['Operational data','Bookings, passenger records, and flights provide the facts used in a recovery request.'],
    ['Model Service','Classification and reasoning are separate model roles in a connected implementation.'],
    ['Agent Memory','Relevant preferences and prior disruptions provide context. This replay supplies sample notes only.'],
    ['Tool evidence','Inputs, returned results, and failures explain what supports the recommendation.'],
   ].map(([title,body])=><section className="card" key={title}><h3>{title}</h3><p>{body}</p></section>)}
  </div>
  <section className="card reference-section"><h3>Current demo boundary</h3><p className="reference-note">The hosted simulation runs in your browser. It does not connect to Capella, execute tools, or save passenger data. Resource links below provide product documentation.</p></section>
 </div>
}
