# Agent Scope (You)

## Objective
Build the real-time voice **agent loop** from ElevenLabs to Gemini for weather anxiety de-escalation.

## Setup Reference
1. See `setup.md` for local prerequisites, env requirements, tunnel startup, and ElevenLabs endpoint wiring.

## Locked Decisions (2026-02-21)
1. Stack is `Next.js` + `TypeScript`.
2. Agent must ask caller where they are calling from (city/state or ZIP) and use that location for data fetches.
3. All orchestration is API-owned by this project (ElevenLabs tool calls -> local Next.js API -> Gemini -> action execution).
4. Runtime target is local URL for now.
5. Eval handoff is Braintrust, with a placeholder endpoint until teammate shares final ingestion details.

## In Scope
1. ElevenLabs agent setup (voice behavior, tools, post-call webhook).
2. Gemini decision engine (emotion/risk classification, tool choice, response generation).
3. Live data adapters:
   - National Weather Service API (`weather.gov`)
   - USGS RTFI API (`waterdata.usgs.gov/rtfi-api`)
   - OpenFEMA API (`fema.gov/about/openfema/api`)
4. Real-time action execution:
   - `create_safety_plan`
   - `resource_handoff`
   - `emergency_guidance`
5. Structured event output for eval loop handoff.

## Out of Scope
1. Scoring, eval dashboards, and policy mutation logic.
2. Prompt optimization experiments and A/B eval frameworks.
3. Judge analytics dashboards.

## Runtime Agent Loop
1. User speaks to ElevenLabs agent.
2. Agent asks caller location if not already known.
3. Agent sends user text/context + location to Gemini orchestration endpoint.
4. Gemini decides required tool calls.
5. Backend fetches live weather/flood/disaster context.
6. Gemini returns:
   - risk level
   - de-escalation strategy
   - spoken response
   - action decision
7. Agent speaks response and executes chosen action.
8. Backend emits structured event to eval loop storage/queue.

## Tool Contract (ElevenLabs Server Tools)
1. `get_weather_alerts(lat, lon)`
2. `get_flood_context(lat, lon)`
3. `get_fema_context(state, county)`
4. `execute_safety_action(action_type, reason, urgency, user_context)`

## Handoff Contract to Eval Loop
Placeholder target (to be replaced when teammate provides details):
- `BRAINTRUST_INGEST_URL=http://localhost:0/braintrust-placeholder`

```json
{
  "call_id": "string",
  "turn_id": 1,
  "timestamp": "ISO-8601",
  "user_text": "string",
  "emotion_state": "calm|anxious|panicked|agitated",
  "risk_level": "low|medium|high|critical",
  "tool_calls": [],
  "tool_outputs": {},
  "action_taken": "none|safety_plan|resource_handoff|emergency_guidance",
  "spoken_response": "string",
  "latency_ms": 0
}
```

## Pending External Input
1. Final Braintrust ingestion endpoint and auth contract from teammate.

## Definition of Done (Agent Loop)
1. Live call works end-to-end from voice input to spoken output.
2. At least one live data source is used in responses.
3. At least one autonomous action is executed.
4. Each turn emits a valid event payload for eval pipeline.
5. Fallback response works when APIs fail.
