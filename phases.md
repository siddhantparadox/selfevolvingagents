# Implementation Phases

## Status Legend
1. `⬜` Pending
2. `✅` Done

Update rule: replace `⬜` with `✅` as soon as a task is completed.

## Phase Overview
| Phase | Goal | Owner | Status | ETA |
|---|---|---|---|---|
| 0 | Setup and local runtime readiness | You | ✅ | Completed |
| 1 | API contracts and route skeletons | You | ⬜ | 30-45 min |
| 2 | Gemini decision engine | You | ⬜ | 45-60 min |
| 3 | Live data adapters (NWS -> USGS -> FEMA) | You | ⬜ | 45-75 min |
| 4 | ElevenLabs wiring (tools + flow) | You | ⬜ | 30-45 min |
| 5 | Action execution + eval handoff placeholder | You | ⬜ | 30-45 min |
| 6 | Reliability + demo prep | You | ⬜ | 30-45 min |

## Phase 0: Setup and Local Runtime Readiness
### Goal
Project and local tunnel are ready for implementation.

### Tasks
1. ✅ Next.js + TypeScript scaffolded in repo root.
2. ✅ `.env` contains required API keys.
3. ✅ `cloudflared` installed and quick tunnel tested.
4. ✅ `setup.md` and `agents.md` documented.

### Exit Criteria
1. ✅ `npm run lint` passes.
2. ✅ Public tunnel URL is available for ElevenLabs webhook/server tool config.

## Phase 1: API Contracts and Route Skeletons
### Goal
Define interfaces first so implementation and eval can move independently.

### Tasks
1. ⬜ Define request/response schema for `POST /api/agent/turn`.
2. ⬜ Define schema for tool routes:
   - `/api/tools/get_weather_alerts`
   - `/api/tools/get_flood_context`
   - `/api/tools/get_fema_context`
   - `/api/tools/execute_safety_action`
3. ⬜ Define eval event schema (Braintrust placeholder target).
4. ⬜ Add basic route skeletons returning mock-safe responses.

### Exit Criteria
1. ⬜ All routes compile.
2. ⬜ Route schema contracts documented in code comments/types.

## Phase 2: Gemini Decision Engine
### Goal
Implement the core orchestration decision for each user turn.

### Tasks
1. ⬜ Build Gemini client wrapper using `GEMINI_API_KEY`.
2. ⬜ Implement decision output shape:
   - `risk_level`
   - `emotion_state`
   - `deescalation_style`
   - `spoken_response`
   - `action`
3. ⬜ Add fallback behavior for Gemini/API failure.
4. ⬜ Connect `POST /api/agent/turn` to Gemini wrapper.

### Exit Criteria
1. ⬜ Endpoint returns deterministic JSON shape for valid input.
2. ⬜ Fallback path works when LLM call fails.

## Phase 3: Live Data Adapters
### Goal
Attach real-time external data for grounded responses.

### Tasks
1. ⬜ Implement NWS adapter first (`weather.gov`) as MVP-required source.
2. ⬜ Implement USGS RTFI adapter for flood context.
3. ⬜ Implement OpenFEMA adapter for preparedness/disaster context.
4. ⬜ Normalize all adapter outputs into one internal weather-risk object.
5. ⬜ Add timeout + fallback per adapter.

### Exit Criteria
1. ⬜ At least NWS adapter live and used in turn response.
2. ⬜ Adapter errors do not break full agent response.

## Phase 4: ElevenLabs Wiring
### Goal
Integrate ElevenLabs runtime with project API routes.

### Tasks
1. ⬜ Configure/update ElevenLabs agent prompt and behavior.
2. ⬜ Add server tools in ElevenLabs pointing to current tunnel URL.
3. ⬜ Ensure location capture occurs before live data tool calls.
4. ⬜ Validate one full call round-trip (voice -> API -> voice).

### Exit Criteria
1. ⬜ ElevenLabs successfully invokes at least one tool route.
2. ⬜ Agent speaks grounded response using live data.

## Phase 5: Action Execution and Eval Handoff Placeholder
### Goal
Execute meaningful actions and emit structured events for eval.

### Tasks
1. ⬜ Implement `execute_safety_action` logic with safe guardrails.
2. ⬜ Emit turn event payload matching `agents.md` contract.
3. ⬜ Send event to `BRAINTRUST_INGEST_URL` placeholder (or local no-op sink).
4. ⬜ Log request/response correlation IDs for traceability.

### Exit Criteria
1. ⬜ At least one autonomous action executes.
2. ⬜ Event payload is emitted for every agent turn.

## Phase 6: Reliability and Demo Prep
### Goal
Make the system demo-safe under time pressure.

### Tasks
1. ⬜ Add API timeout handling and user-friendly fallback speech.
2. ⬜ Add minimal retry policy for transient external API failures.
3. ⬜ Prepare two scripted demo scenarios:
   - low-risk weather anxiety
   - high-risk weather concern
4. ⬜ Rehearse full 3-minute demo flow twice.

### Exit Criteria
1. ⬜ End-to-end flow is stable across two full dry-runs.
2. ⬜ Demo can proceed even if one external API fails.

## Blocking Dependencies
1. ⬜ Final Braintrust ingestion endpoint/auth from teammate.
