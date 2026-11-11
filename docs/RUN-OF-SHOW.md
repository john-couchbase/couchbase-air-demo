# Run of show: Part 2, the storm

The beats to hold in the room for the AIDP Air app, which is Part 2 of the Serverless Models
field demo. Mark Gamble owns the overall script and the video; this is written to be folded
into it. Part 1 (deploying a serverless model in Capella and swapping it live) is his and is
only referenced here, at the handoff.

**Audience:** a second call. Technical enough to follow a SQL++ statement, not yet
practitioners. Every beat has to land as business value first and mechanism second.

**The one sentence:** a storm nobody forecast sends ten times the traffic; a cheap model
reads all of it where it lands, a frontier model decides only for the few who need
judgment, and when the storm passes the bill goes back to zero.

**The three tenets** (stated on the Demo tab, repeated in each screen's eyebrow):
**Burst**, **Model per task**, **Inside the data**. Say the words; the screens repeat them.

**Length:** about 12 minutes, 15 with questions. The storm itself runs about four minutes
from trigger to quiet, and the talk track is built around that clock.

---

## Before the call

- [ ] Start the app from your own terminal: `./scripts/present.sh`. Never from the editor,
      never Vite on :5174 (see README, Presenting).
- [ ] Open **http://localhost:8010**, browser zoom 125-150%. The layout is built for about
      1280px of width over a screen share.
- [ ] Press **Reset** (twice: it arms, then confirms). Then **leave it on a normal morning for
      at least 30 seconds** before the storm, so the chart has normal traffic to compare the
      surge against. A storm triggered straight after a reset has no baseline to show.
- [ ] Laptop only: LM Studio has Llama 3.1 8B and the nomic embedding model loaded
      (README, step 3). The peach banner at the bottom must be visible.
- [ ] Sandbox only: `deploy_models.py status` shows every model on. Afterwards run
      `deploy_models.py off`.
- [ ] Close anything else using the GPU. Locally, inference speed decides whether
      classification keeps up with the surge.

**On the laptop, say it plainly.** The peach banner stays on screen for a reason: models are
local stand-ins, AI Functions and the cache are emulated, token counts are measured, and
prices are Bedrock list. Say that once at the start and nobody feels misled later. On the
sandbox the banner is gone and so is the caveat.

---

## Beat 0 · Handoff from Part 1 (30s)

*Mark has just deployed a serverless model in Capella and swapped Nova for Claude on the same
statement, with no redeploy.*

> "So choosing a model is now a setting. The question is why you'd want more than one, and
> what serverless actually buys you. Let me show you on a bad day for an airline."

## Beat 1 · Home: what Couchbase is (1 min)

**Screen:** the Couchbase mark, top left. "One data layer for production agents."

Most rooms don't know Couchbase. Don't read the page; give them the frame.

> "Couchbase is the operational database underneath a lot of apps you've used. The AI Data
> Plane is one layer of it: models, agent memory, a cache and your live data, in one governed
> place. That matters today because the model gets called from where the data already is."

**Point at:** *What it replaces*. Six systems on the left, including a GPU fleet and a
pipeline to move data to it; one endpoint on the right.

## Beat 2 · Model Service: what's new (1 min)

**Screen:** Model Service tab.

> "What's new is that Bedrock models (Claude, Llama, Nova, Mistral, Cohere) run serverless
> inside the Model Service. You pay for tokens. There's no GPU to size and no floor cost when
> nothing is happening."

**Point at:** the *What it replaces* table, the "Cost when idle" row: *the full hourly rate,
around the clock* versus *zero*. Then the two cards at the bottom:

> "Provisioned NIM is still there, same endpoint, for steady or air-gapped workloads. You're
> not choosing one forever."

## Beat 3 · Demo: set up the storm (1 min)

**Screen:** Demo tab. Read the three tenet cards as the agenda, one line each.

> "AIDP Air runs its hub at O'Hare. Normally the support queue is a trickle. Today a winter
> storm closes the airport and fifty-two flights cancel. Watch for three things: a burst
> nobody planned for, a different model for each job, and all of it happening inside the
> data."

**Point at** the live diagram, *What happens when the storm hits*. On a normal morning it's
nearly dark: maybe one Nova Micro slot flickering, Claude dark, spend a fraction of a cent a
minute.

> "Each lit square is one request in flight. There are no servers in this picture, because
> there aren't any to size."

## Beat 4 · Trigger the storm (5s)

Press **Trigger storm** (red, top right). The app jumps to the Storm tab by itself.

> "Ground stop, then cancellations."

## Beat 5 · Storm: the burst, and the cheap model reading all of it (2 min)

**Screen:** Storm. Let the chart build for 20-30 seconds before talking over it.

**Point at, in order:**

1. **Peak vs normal** (the red number; 25x in rehearsal). *Burst.*
   > "That's the storm against a normal morning. Nobody reserves capacity for twenty-five
   > times normal."
2. **The chart:** grey normal traffic under red storm traffic, with the black *Classified*
   line tracking it. *(On the laptop the line can lag the peak for a few seconds: one GPU. On
   Bedrock it doesn't. Say so if anyone looks.)*
3. **Just classified:** real messages with what the cheap model made of each one: rebook,
   hotel, urgency, a language chip, **cache hit**.
   > "A small, cheap model, Nova Micro, reads every message and classifies it: what the
   > passenger wants and how urgent it is. A lot of people ask the same thing in slightly
   > different words, and those are answered from the semantic cache without calling the
   > model at all."
4. **The statement doing it.** *Inside the data.*
   > "This is the whole mechanism: one SQL++ UPDATE, with the model called from inside it.
   > No pipeline and no export. The messages stay where they landed."

## Beat 6 · Recovery: the few who need judgment (3 min)

**Screen:** Recovery. By now there are drafts; **Maya Chen** is pinned at the top with a ★.
She's scheduled to arrive early in the surge and the agent takes her first, so she's ready
within a minute of the trigger. *Model per task.*

> "Out of hundreds of messages, only these reach a frontier model: a deadline that matters, a
> health or safety need, a child travelling alone, a top-tier customer at the end of their
> patience. That's decided by a SQL++ query joining what the cheap model said with who the
> passenger is."

**Walk down Maya's card, top to bottom:**

1. **Her message:** a keynote in London, Thursday 9 a.m., third disruption this year.
2. **Nova Micro read it as:** the cheap model's one-line summary and urgency.
3. **Agent Memory:** her two prior disruptions and what she was given, plus her notes
   (prefers direct flights, wants contact in the app).
4. **Options it could choose from:** AIDP Air's own flight tomorrow evening, and partner
   flights tonight read live from the `travel-sample` route data.
   > "It can't invent a flight. These are the real options, and you can see which one it
   > picked and which it rejected."
5. **Claude Sonnet's decision:** which flight, the goodwill, the actions, the reply.

**Read the decision before you narrate it.** It's generated live and the wording changes every
run. In rehearsal it chose **British Airways tonight** over AIDP Air tomorrow evening, which
lands too close to a 9 a.m. keynote, and gave goodwill within the Platinum cap. If it chooses
differently, narrate what it did and why; the options are on screen to judge it by.

> "Nova Micro costs about one eighty-fifth of Claude per input token. So Claude only sees
> this handful, where judgment is worth paying for."

Press **Approve and send**.

> "A person signs off, and that's the only thing that writes to Agent Memory. Next storm, the
> agent knows what we did for her this time."

*(On the laptop the draft is written by an 8B stand-in and its reasoning can be rough. That
is fine to say. It is also exactly why a person approves.)*

## Beat 7 · Back to the diagram (30s, optional)

If the storm is still running, go to **Demo** and scroll to the diagram: Nova Micro's slots
full, Claude's lit, the spend meter above zero against the reserved GPU's flat rate.

> "This is serverless under load: capacity appeared with the requests. Watch what happens when
> they stop."

## Beat 8 · Cost: going quiet, the finish (2 min)

**Screen:** Cost. Best once the bar says **Quiet**, about four minutes after the trigger. If
you get there early, talk through *The bill* table first and come back to the charts.

1. **Spend per 5 seconds.** *Burst.* The bars rise with the storm and fall back to the floor;
   the blue reserved-GPU line stays flat the whole time.
   > "That flat line is what a GPU sized for this peak costs every minute, busy or idle. The
   > red is what we actually spent, and it goes back to zero."
2. **Summed over the run.** The reserved line keeps climbing; serverless flattens.
   The caption under the heading tells you whether serverless beat the reserved rate even at
   the peak in this run. Read it rather than assuming.
3. **The bill, read back from the cluster.** *Model per task.* In rehearsal, classifying every
   message cost well under a cent, and the Claude decisions were most of the bill.
   > "Every call is a document in the cluster, so the bill is a SQL++ query."
4. **When provisioned is the right answer.** Say this before anyone asks:
   > "If this ran hot all day, every day, provisioned NIM would be cheaper per token. You
   > can start serverless and move a workload over when it gets steady, with no change to
   > the application."

**Close:**

> "A burst nobody forecast, absorbed without reserving anything. Two models, each chosen for
> its job. Inference called from inside the data. And when the storm passed, the bill went
> back to zero."

---

## Questions you will get

**"Isn't serverless more expensive?"**
Per token at steady high load, yes, and the Cost tab says so. The comparison that matters is
over a day that's mostly quiet: a reserved GPU charges for every idle hour. Steady, sensitive
workloads belong on provisioned NIM, which is in the same service behind the same endpoint.

**"Why not call Bedrock directly?"**
You could, from an app tier that pulls the data out, holds the keys, builds a cache and meters
the tokens. Here the model is called from a SQL++ statement over the data where it lives,
the cache is a deployment setting, and the bill is a query. **Be precise:** the message text
still reaches the model; what goes away is an app tier extracting and shipping data. Don't
claim "the data never leaves" for a Bedrock model without confirming the residency story
with product first.

**"What if the cheap model misclassifies someone who needs help?"**
Three answers. The funnel doesn't rely on urgency alone; it also joins passenger tier and
flags like "child travelling alone" or "medical". In testing, all 18 of the hand-written
hard cases reached the agent while only 3% of routine messages did
(`scripts/eval_classify.py`). And the rule is a SQL++ WHERE clause, so tightening it is an
edit, not a retrain.

**"Is the cache safe? Couldn't one passenger get another's answer?"**
Only the classification is cached, and it never contains a name, flight or city. Two people
who say the same words get the same classification; the flight and booking come from the
join, not from the model. Nothing a passenger reads comes from the cache.

**"Why Claude for the decisions?"**
The decision weighs real options against a policy and the passenger's history, and the reply
goes to a person. That's where a frontier model earns its price, and because only a small
share of messages get there, the price stays small.

**"Is this running live?"**
On the sandbox: yes, Bedrock models through the Model Service, and the Demo tab's table shows
every component as Live. On a laptop: the models are local stand-ins and the banner says so.
The workflow, data, SQL++, funnel and metering are the real thing either way.

**"How many messages is this? Would it scale?"**
On a laptop the surge is sized to what one GPU can classify (about 320 messages in four
minutes) so the demo keeps pace. The ratio to normal traffic is the point, and on the sandbox
the surge can be several times larger.

**"Can I change the models?"**
Yes; that was Part 1. The Models tab shows the catalog, prices and which job uses which.

---

## If something goes wrong

- **Anything looks stuck:** press **Reset** twice. You're back on a normal morning in about a
  second. Give it 30 seconds of normal traffic, then trigger again. A full storm is about four
  minutes.
- **The page stops updating:** the server probably died. Rerun `./scripts/present.sh` in your
  terminal and refresh. A restart always comes back as a fresh normal morning.
- **Maya isn't on Recovery yet:** go back to Storm for thirty seconds; she arrives early and
  is drafted first.
- **Recovery is slow to fill on the laptop:** that's the local GPU shared between both models.
  Narrate the drafts that are there; you only need Maya's.
- **Last resort:** the recorded video (Mark's).
