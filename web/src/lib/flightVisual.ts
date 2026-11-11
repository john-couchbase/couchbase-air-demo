/** Visual states describe the scripted events, never actual flight telemetry. */
export function flightVisual(kind: string) {
 const normal=kind==='normal'
 const outcome=kind==='decision'||kind==='review'
 const failure=kind==='failure'
 return { normal, outcome, failure, settled:kind==='review',
  headline: normal?'Flights boarding':kind==='storm'?'Storm at O’Hare':kind==='messages'?'Passengers request help':kind==='classify'?'Checking bookings and seats':failure?'New York search timed out':kind==='review'?'Requests resolved':outcome?'Replacement found':'Routes illustrated',
  detail: normal?'Routes shown before the disruption.':kind==='storm'?'Two cancellations, an SFO lightning delay, and a Miami gate change.':kind==='messages'?'Flight changes, weather updates, and gate assistance.':kind==='classify'?'Checking flights, weather, and gate assistance.':failure?'No response. Retrying the search; bookings unchanged.':kind==='review'?'Four conversations updated.':outcome?'AIR 218 found for New York. Seattle needs staff help.':'',
  jfk:normal?'Boarding':failure?'Search timeout / retrying':kind==='review'?'AIR 218 / booking updated':outcome?'AIR 218 offered / not booked':kind==='classify'?'Searching alternatives':'Cancelled / help requested',
  sea:normal?'Boarding':outcome?'No adjacent seats / staff review':kind==='classify'?'Checking two adjacent seats':'Cancelled / help requested',
 }
}
