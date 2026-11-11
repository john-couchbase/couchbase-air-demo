"""
Build the storm-day dataset, once, deterministically.

    .venv/bin/python scripts/build_dataset.py

Writes data/*.json, which is committed. Provisioning loads those files, so the
sandbox is rebuilt from the same bytes every time it is scrubbed, and a run on
Monday reads exactly like a run on Friday.

The network is real: AIDP Air's routes out of ORD are United's routes in the
`travel-sample` bucket, re-badged, with city names taken from the airport
documents. The carrier, the passengers and every message are invented.

Nothing here decides which messages escalate. `expected` fields are written
for scripts/eval_classify.py to score the model against; the running demo never
reads them. The funnel is decided by what the cheap model says at runtime.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aidpair.db import query  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data"
RNG = random.Random(20260210)

HUB = "ORD"
STORM_DAY = "2026-02-10"
# Departures inside this local window are cancelled; the hour either side is
# delayed. The storm is the only reason anything changes.
CANCEL_FROM, CANCEL_TO = 7 * 60, 16 * 60
DELAY_FROM, DELAY_TO = 6 * 60, 18 * 60

N_PASSENGERS = 2400

FIRST = """Maya James Sofia Liam Aisha Noah Elena Mateo Priya Lucas Hana Omar Grace Diego Chloe
Ethan Fatima Leo Ava Hiroshi Nora Samuel Isabel Kwame Zoe Daniel Lena Arjun Olivia Marcus Mei
Andre Ruth Tomas Ingrid Caleb Amara Victor Julia Rafael Keiko Owen Lucia Malik Clara Ibrahim
Emma Felipe Sarah Jonah Rosa Theo Yara Benjamin Nadia Adrian Wren Kofi Leila Henry Camila""".split()
LAST = """Chen Okafor Rossi Nguyen Patel Garcia Kim Novak Haddad Silva Johnson Tanaka Schmidt
Dubois Mensah Kowalski Alvarez Murphy Singh Costa Andersen Ibrahim Lopez Park Fischer Moreau
Walker Yamamoto Rahman Oliveira Brooks Petrov Hughes Mendes Larsen Ahmed Reyes Cohen Sato Byrne
Martin Diaz Wright Kaur Ferreira Taylor Suzuki Jensen Ortiz Bennett Ali Romero Clarke Das""".split()

TIERS = [("Member", 0.70), ("Silver", 0.14), ("Gold", 0.10), ("Platinum", 0.05),
         ("Concierge", 0.01)]
LANGS = [("en", 0.80), ("es", 0.08), ("fr", 0.03), ("pt", 0.03), ("de", 0.02),
         ("ja", 0.02), ("zh", 0.02)]
CHANNELS = [("app", 0.42), ("chat", 0.25), ("email", 0.18), ("social", 0.10), ("sms", 0.05)]
SEAT_PREFS = ["aisle", "window", "exit row", "front of cabin", None]


def pick(weighted):
    r, acc = RNG.random(), 0.0
    for v, w in weighted:
        acc += w
        if r <= acc:
            return v
    return weighted[-1][0]


# ------------------------------------------------------------------ network
def build_network() -> tuple[list[dict], dict[str, dict]]:
    routes = query(
        """
        SELECT r.destinationairport AS dest, r.equipment, r.distance, r.schedule
        FROM `travel-sample`.inventory.route r
        WHERE r.sourceairport = $hub AND r.airline = "UA" AND r.stops = 0
        ORDER BY r.destinationairport
        """,
        hub=HUB,
    )
    codes = sorted({r["dest"] for r in routes} | {HUB})
    airports = {
        a["faa"]: a
        for a in query(
            """
            SELECT a.faa, a.city, a.country, a.airportname AS name, a.tz
            FROM `travel-sample`.inventory.airport a WHERE a.faa IN $codes
            """,
            codes=codes,
        )
    }

    flights = []
    seen: set[str] = set()
    number = 400
    for r in routes:
        dest = r["dest"]
        if dest in seen or dest not in airports:
            continue
        seen.add(dest)
        # One departure per destination, two for the busiest. Times come from the
        # route's own Tuesday schedule, read as local departure times.
        slots = sorted({s["utc"] for s in r["schedule"] if s["day"] == 2}) or ["09:00:00"]
        count = 2 if r["distance"] < 1800 and len(slots) > 3 and RNG.random() < 0.35 else 1
        for utc in RNG.sample(slots, min(count, len(slots))):
            hh, mm = (int(x) for x in utc.split(":")[:2])
            dep = max(5 * 60 + 30, min(22 * 60, hh * 60 + mm))
            minutes = int(r["distance"] / 780 * 60) + 25
            number += RNG.randint(3, 17)
            if CANCEL_FROM <= dep < CANCEL_TO:
                status, delay = "cancelled", None
            elif DELAY_FROM <= dep < DELAY_TO:
                status, delay = "delayed", RNG.choice([95, 120, 150, 180, 240])
            else:
                status, delay = "on_time", None
            flights.append({
                "type": "flight",
                "id": f"AD{number}",
                "flight_no": f"AD {number}",
                "origin": HUB,
                "dest": dest,
                "dest_city": airports[dest]["city"],
                "dest_country": airports[dest]["country"],
                "equipment": (r["equipment"] or "320").split()[0],
                "dep_local": f"{dep // 60:02d}:{dep % 60:02d}",
                "block_minutes": minutes,
                "distance_km": round(r["distance"]),
                "scheduled_status": "on_time",
                "storm_status": status,
                "storm_delay_min": delay,
                "seats": 76 if r["distance"] < 900 else 166 if r["distance"] < 4000 else 276,
            })
    # The hero's flight is the evening London widebody. Its inbound aircraft is
    # stuck in the storm, so it cancels even though it departs after the window.
    for f in flights:
        if f["dest"] == "LHR":
            f.update(dep_local="18:25", storm_status="cancelled", storm_delay_min=None,
                     cancel_reason="inbound aircraft grounded by the storm")
    flights.sort(key=lambda f: f["dep_local"])
    return flights, airports


# --------------------------------------------------------------- passengers
def build_people(flights: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    passengers, bookings, memory = [], [], []
    # Weight toward cancelled and delayed flights: those are the people who
    # write in. Everyone else is the normal day's trickle.
    weights = [5 if f["storm_status"] == "cancelled" else 3 if f["storm_status"] == "delayed"
               else 1 for f in flights]
    for i in range(N_PASSENGERS):
        pid = f"pax_{i:05d}"
        tier = pick(TIERS)
        lang = pick(LANGS)
        flight = RNG.choices(flights, weights)[0]
        party = RNG.choices([1, 2, 3, 4], [0.62, 0.24, 0.08, 0.06])[0]
        prior = RNG.choices([0, 1, 2, 3], [0.6, 0.25, 0.1, 0.05])[0]
        if tier in ("Platinum", "Concierge"):
            prior = max(prior, RNG.choice([0, 1, 1, 2]))
        name = f"{RNG.choice(FIRST)} {RNG.choice(LAST)}"
        passengers.append({
            "type": "passenger", "id": pid, "name": name, "tier": tier, "language": lang,
            "home_airport": RNG.choice([HUB, HUB, flight["dest"]]),
            "lifetime_flights": RNG.randint(2, 40) * (6 if tier in ("Platinum", "Concierge")
                                                       else 3 if tier == "Gold" else 1),
        })
        pnr = "".join(RNG.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        bookings.append({
            "type": "booking", "id": pnr, "pnr": pnr, "passenger_id": pid,
            "flight_id": flight["id"], "party_size": party,
            "cabin": "business" if tier in ("Platinum", "Concierge") and RNG.random() < 0.5
            else "economy",
            "fare": RNG.choice(["basic", "main", "main", "flexible"]),
        })
        history = []
        for _ in range(prior):
            history.append({
                "when": f"2025-{RNG.randint(3, 12):02d}-{RNG.randint(1, 28):02d}",
                "what": RNG.choice([
                    "4h delay, missed connection at DEN",
                    "cancellation at LGA, rebooked next morning",
                    "delayed bag, delivered after 2 days",
                    "6h delay, ATC ground stop at ORD",
                    "downgraded from business on SFO route",
                ]),
                "goodwill": RNG.choice(["none", "5,000 miles", "10,000 miles", "$50 voucher",
                                        "meal voucher"]),
            })
        memory.append({
            "type": "memory", "id": pid, "passenger_id": pid,
            "preferences": {
                "seat": RNG.choice(SEAT_PREFS),
                "contact": RNG.choice(["app", "email", "sms"]),
            },
            "disruptions": history,
            "notes": [],
        })
    return passengers, bookings, memory


# ------------------------------------------------------------------ phrasing
# Near-duplicate phrasings are deliberate. In a storm thousands of people ask the
# same few questions in slightly different words, which is what makes the cache
# pay. The cache rate this data produces is a property of these lists, so it is
# quoted as a shape, never as a benchmark.
TEMPLATES: dict[str, dict[str, list[str]]] = {
    "status": {
        "en": [
            "Is {flight} to {city} still going?",
            "is my flight to {city} cancelled??",
            "What's the status of {flight}? The app just says delayed.",
            "Hi, is {flight} going to leave today or not",
            "Is my flight cancelled because of the snow?",
            "Any update on {flight}? Board still says delayed.",
            "is {flight} delayed or cancelled",
            "Hello, can you tell me if my {city} flight is still on?",
        ],
        "es": ["¿Mi vuelo {flight} a {city} está cancelado?",
               "Hola, ¿sale hoy el vuelo {flight}?"],
        "fr": ["Mon vol {flight} pour {city} est-il annulé ?"],
        "pt": ["Meu voo {flight} para {city} foi cancelado?"],
        "de": ["Ist mein Flug {flight} nach {city} gestrichen?"],
        "ja": ["{city}行きの{flight}便は欠航ですか？"],
        "zh": ["我去{city}的{flight}航班取消了吗？"],
    },
    "rebook": {
        "en": [
            "My flight {flight} to {city} was cancelled. Can you get me on the next one?",
            "{flight} got cancelled, I need to get to {city} today. What are my options?",
            "Flight cancelled. Please rebook me on anything to {city} tonight.",
            "Cancelled again. Need the next available flight to {city}.",
            "Hi, my {flight} was cancelled due to weather, can I be rebooked for tomorrow morning?",
            "The app won't let me rebook {flight}. I need to get to {city}.",
            "Can you put me on a flight to {city} through another city? {flight} is cancelled.",
            "my flight got canceled what do i do now",
            "Please rebook {flight}. Any flight to {city} works, even with a connection.",
        ],
        "es": ["Cancelaron mi vuelo {flight} a {city}. ¿Me pueden cambiar al siguiente?",
               "Necesito llegar a {city} hoy, mi vuelo {flight} fue cancelado."],
        "fr": ["Mon vol {flight} a été annulé. Pouvez-vous me réserver le prochain vol pour {city} ?"],
        "pt": ["Meu voo {flight} foi cancelado. Preciso de outro voo para {city}."],
        "de": ["Mein Flug {flight} wurde gestrichen. Bitte buchen Sie mich auf den nächsten Flug nach {city} um."],
        "ja": ["{flight}便が欠航になりました。{city}行きの次の便に振り替えてください。"],
        "zh": ["我的{flight}航班被取消了，请帮我改签到去{city}的下一班。"],
    },
    "refund": {
        "en": [
            "{flight} was cancelled and I no longer need to travel. I want a refund.",
            "I'd like a full refund for my cancelled flight to {city}.",
            "Cancel my trip and refund me please, {flight} is not happening.",
            "How do I get my money back for {flight}?",
            "Refund please. Flight to {city} cancelled and I'm driving instead.",
        ],
        "es": ["Quiero un reembolso por mi vuelo cancelado a {city}."],
        "fr": ["Je voudrais un remboursement pour le vol {flight} annulé."],
        "pt": ["Quero o reembolso do voo {flight}."],
        "de": ["Ich möchte eine Erstattung für den gestrichenen Flug {flight}."],
    },
    "hotel": {
        "en": [
            "I'm stuck at ORD overnight, {flight} cancelled. Do you provide a hotel?",
            "Can I get a hotel voucher? My flight to {city} isn't until tomorrow now.",
            "Where am I supposed to sleep tonight? {flight} cancelled.",
            "Need hotel and meal vouchers, stranded at O'Hare.",
        ],
        "es": ["Estoy atrapado en O'Hare esta noche. ¿Me dan hotel?"],
        "pt": ["Preciso de hotel, meu voo para {city} foi cancelado."],
    },
    "baggage": {
        "en": [
            "My bag was checked on {flight} which got cancelled. Where is it?",
            "Flight cancelled but my checked bag is somewhere. How do I get it back?",
            "Can I get my luggage back? I'm going home, {flight} is cancelled.",
        ],
        "es": ["Mi maleta estaba en el vuelo {flight}. ¿Dónde está?"],
    },
    "complaint": {
        "en": [
            "This is the worst airline. {flight} cancelled with no notice and no one at the desk.",
            "Two hours on hold. Absolutely unacceptable. Fix this.",
            "Why did you cancel {flight} when other airlines are still flying to {city}?",
            "Your app keeps crashing and the line at the counter is 300 people long.",
            "Never flying AIDP Air again after today.",
        ],
        "es": ["Es inaceptable. Cancelaron {flight} y nadie nos ayuda."],
        "fr": ["C'est inacceptable, personne ne répond et mon vol est annulé."],
    },
}

# Appended to English messages at random. Most are noise; a few change what
# the right answer is, which is the model's job to notice.
TAILS = [
    "", "", "", "", "", "", "",
    " Thanks.", " Please help.", " Thank you!", " ASAP please.",
    " I have two kids with me.", " Traveling with my elderly mother.",
    " I have a connection in {city2} tonight.",
    " I have a meeting tomorrow morning.",
]

# Hand-written. Every one of these is a case where the right answer turns on a
# detail a keyword rule would miss. They are the reason the frontier model is in
# the funnel at all, and the hero is the one the presenter opens.
SPECIALS = [
    {"hero": True, "tier": "Platinum", "dest": "LHR",
     "text": "My flight {flight} to London tonight is cancelled. I'm giving the opening "
             "keynote at a conference in London on Thursday at 9am. This is the third time "
             "you've stranded me this year. I need a real answer, not a chatbot."},
    {"tier": "Member", "text": "My 12 year old daughter is flying alone on {flight} to {city} as "
     "an unaccompanied minor. Your agent told me the flight is cancelled. Where is she right now "
     "and who is with her?"},
    {"tier": "Gold", "text": "I use a wheelchair and my flight {flight} was cancelled. I've been "
     "at gate C18 for three hours and nobody has come to help me get to a rebooking desk."},
    {"tier": "Member", "text": "My father passed away and the funeral in {city} is tomorrow at 11am. "
     "{flight} is cancelled. Is there anything at all tonight? I'll take any seat."},
    {"tier": "Silver", "text": "I'm type 1 diabetic and my insulin is in my checked bag on {flight}. "
     "The flight is cancelled and I can't get the bag back. I need it tonight."},
    {"tier": "Concierge", "text": "Cancelled on {flight}. I have a board meeting in {city} at 8am "
     "tomorrow that I cannot miss. Please call me."},
    {"tier": "Member", "text": "I'm 36 weeks pregnant, {flight} was cancelled and I'm not allowed to "
     "fly after tomorrow. I need to get home to {city} tonight or tomorrow first thing."},
    {"tier": "Gold", "text": "Traveling with my service dog. The rebooking offered is on a regional "
     "jet with no room for her. {flight} cancelled. Need a mainline flight."},
    {"tier": "Member", "text": "I'm getting married in {city} on Saturday and my whole wedding party "
     "of 9 was on {flight}. We're split across three different rebookings now."},
    {"tier": "Platinum", "text": "Cancelled {flight}. I'm connecting to an international flight in "
     "{city} that is the only one this week. If I miss it I lose a 12 day cruise."},
    {"tier": "Member", "text": "I'm active duty and must report to base near {city} by 0600 "
     "tomorrow. {flight} is cancelled. I have orders I can send you."},
    {"tier": "Silver", "text": "My son has severe autism and we've been in the terminal for 6 hours. "
     "He is overwhelmed. {flight} is cancelled. Is there somewhere quiet or a hotel we can go to now?"},
    {"tier": "Member", "text": "Mi vuelo {flight} fue cancelado y viajo con mi madre de 84 años que "
     "necesita oxígeno. Se le está acabando. ¿Qué hacemos?", "language": "es"},
    {"tier": "Gold", "text": "Mon vol {flight} est annulé. Je dois passer une greffe de rein à {city} "
     "demain matin, l'hôpital m'a appelé ce soir.", "language": "fr"},
    {"tier": "Member", "text": "Transplant patient here. I'm immunocompromised and the terminal is "
     "packed. {flight} cancelled. Can I wait somewhere other than the gate area?"},
    {"tier": "Platinum", "text": "{flight} cancelled. Third disruption in two months. I've been loyal "
     "for 15 years. I'd like to speak to someone who can actually make a decision."},
    {"tier": "Member", "text": "My passport is in my checked bag on {flight} and I fly out "
     "internationally from {city} tomorrow. The flight's cancelled. I need that bag."},
    {"tier": "Member", "text": "I'm a nurse and I'm due on shift at the hospital in {city} at 7am. "
     "They are short staffed because of the storm. {flight} is cancelled."},
]

BASELINE = [
    "Can I change my seat on {flight}?",
    "What's the checked bag allowance to {city}?",
    "How do I add my Known Traveler Number?",
    "Is there wifi on {flight}?",
    "Can I bring a stroller on board?",
    "I'd like to upgrade to business on {flight}.",
    "Do you have vegetarian meals to {city}?",
    "My miles didn't post from last week's trip.",
    "Can I get on an earlier flight to {city}?",
    "How early should I get to O'Hare for {flight}?",
]

EXPECTED_INTENT_URGENCY = {
    "status": 2, "rebook": 3, "refund": 2, "hotel": 3, "baggage": 3, "complaint": 3,
}


def fill(text: str, flight: dict, flights_by_dest: dict) -> str:
    city2 = RNG.choice(["Denver", "Newark", "San Francisco", "Houston", "Washington"])
    return text.format(flight=flight["flight_no"], city=flight["dest_city"], city2=city2)


def build_messages(flights, passengers, bookings):
    fl = {f["id"]: f for f in flights}
    by_pax = {b["passenger_id"]: b for b in bookings}
    disrupted = [p for p in passengers
                 if fl[by_pax[p["id"]]["flight_id"]]["storm_status"] in ("cancelled", "delayed")]
    calm = [p for p in passengers if p not in disrupted]
    RNG.shuffle(disrupted)

    surge = []
    used: set[str] = set()

    # Specials first, each attached to a passenger whose flight fits the story.
    for i, sp in enumerate(SPECIALS):
        pool = [p for p in disrupted if p["id"] not in used
                and fl[by_pax[p["id"]]["flight_id"]]["storm_status"] == "cancelled"
                and (not sp.get("dest") or fl[by_pax[p["id"]]["flight_id"]]["dest"] == sp["dest"])]
        p = pool[0]
        used.add(p["id"])
        p["tier"] = sp["tier"]
        if sp.get("language"):
            p["language"] = sp["language"]
        f = fl[by_pax[p["id"]]["flight_id"]]
        surge.append({
            "passenger_id": p["id"], "pnr": by_pax[p["id"]]["pnr"], "flight_id": f["id"],
            "channel": "chat" if not sp.get("hero") else "app",
            "language": p["language"] if sp.get("language") else "en",
            "text": fill(sp["text"], f, None),
            "hero": bool(sp.get("hero")),
            "expected": {"escalate": True},
        })

    # Then the crowd. Some passengers write twice, which is also what happens.
    intents = [("rebook", 0.36), ("status", 0.24), ("hotel", 0.12), ("refund", 0.10),
               ("complaint", 0.10), ("baggage", 0.08)]
    while len(surge) < 2000:
        p = RNG.choice(disrupted)
        f = fl[by_pax[p["id"]]["flight_id"]]
        intent = pick(intents)
        if f["storm_status"] == "delayed" and intent in ("refund", "hotel"):
            intent = "status"
        lang = p["language"]
        bank = TEMPLATES[intent].get(lang) or TEMPLATES[intent]["en"]
        if lang not in TEMPLATES[intent]:
            lang = "en"
        text = fill(RNG.choice(bank), f, None)
        if lang == "en":
            text += fill(RNG.choice(TAILS), f, None)
        surge.append({
            "passenger_id": p["id"], "pnr": by_pax[p["id"]]["pnr"], "flight_id": f["id"],
            "channel": pick(CHANNELS), "language": lang, "text": text, "hero": False,
            "expected": {"intent": intent, "escalate": False},
        })

    # Specials are spread through the first two thirds of the surge rather than
    # front-loaded, so escalations arrive while the crowd is still arriving.
    specials, crowd = surge[: len(SPECIALS)], surge[len(SPECIALS):]
    for sp in specials:
        crowd.insert(RNG.randint(20, 380), sp)
    surge = crowd

    baseline = []
    for _ in range(400):
        p = RNG.choice(calm)
        f = fl[by_pax[p["id"]]["flight_id"]]
        baseline.append({
            "passenger_id": p["id"], "pnr": by_pax[p["id"]]["pnr"], "flight_id": f["id"],
            "channel": pick(CHANNELS), "language": "en",
            "text": fill(RNG.choice(BASELINE), f, None), "hero": False,
            "expected": {"escalate": False},
        })
    return surge, baseline


def main() -> None:
    OUT.mkdir(exist_ok=True)
    flights, airports = build_network()
    passengers, bookings, memory = build_people(flights)
    surge, baseline = build_messages(flights, passengers, bookings)

    # The hero's memory is written by hand so the agent has something specific
    # to reason over: two prior disruptions, and what was already given.
    hero = next(m for m in surge if m["hero"])
    for mem in memory:
        if mem["passenger_id"] == hero["passenger_id"]:
            mem["preferences"] = {"seat": "aisle", "contact": "app"}
            mem["disruptions"] = [
                {"when": "2025-11-18", "what": "6h delay, ATC ground stop at ORD",
                 "goodwill": "10,000 miles"},
                {"when": "2026-01-06", "what": "cancellation at LGA, rebooked next morning",
                 "goodwill": "meal voucher"},
            ]
            mem["notes"] = ["Prefers a direct flight over an earlier connection.",
                            "Asked to be contacted in the app, not by phone."]
    for p in passengers:
        if p["id"] == hero["passenger_id"]:
            p["name"] = "Maya Chen"
            p["lifetime_flights"] = 212

    for name, rows in [("flights", flights), ("passengers", passengers),
                       ("bookings", bookings), ("memory", memory),
                       ("surge", surge), ("baseline", baseline)]:
        (OUT / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    cancelled = sum(f["storm_status"] == "cancelled" for f in flights)
    print(f"{len(flights)} flights ({cancelled} cancelled), {len(passengers)} passengers, "
          f"{len(surge)} surge messages, {len(baseline)} baseline")
    print("hero:", hero["passenger_id"], hero["flight_id"], hero["text"][:60])


if __name__ == "__main__":
    main()
