# Setup Guide

## Purpose
Local setup required to run the agent loop (`ElevenLabs -> Next.js API -> Gemini`) with a public tunnel URL for webhook/server tools.

## Required
1. Node.js + npm
2. Cloudflared installed
3. API keys in `.env`:
   - `ELEVENLABS_API_KEY`
   - `MODULATE_API_KEY`
   - `GEMINI_API_KEY`
4. Placeholder eval handoff env var (until teammate finalizes Braintrust ingestion):
   - `BRAINTRUST_INGEST_URL=http://localhost:0/braintrust-placeholder`

## Run Locally
1. Start app:
   ```powershell
   cd D:\projects\selfimprovingagents
   npm run dev
   ```
2. Start tunnel in second terminal:
   ```powershell
   cloudflared tunnel --url http://localhost:3000
   ```
3. Copy tunnel URL (example):
   - `https://higher-yukon-sept-gaming.trycloudflare.com`

## ElevenLabs Config Input
Use the tunnel URL as base for webhook/server tool endpoints:
1. `<TUNNEL_URL>/api/tools/get_weather_alerts`
2. `<TUNNEL_URL>/api/tools/get_flood_context`
3. `<TUNNEL_URL>/api/tools/get_fema_context`
4. `<TUNNEL_URL>/api/tools/execute_safety_action`

## Notes
1. Keep both terminals running (`npm run dev` and `cloudflared tunnel ...`).
2. Quick tunnel URLs change if cloudflared restarts.
3. Update ElevenLabs endpoints whenever the tunnel URL changes.

## Pre-Flight Checklist
1. `npm run dev` is running with no startup errors.
2. `cloudflared tunnel --url http://localhost:3000` is running.
3. Tunnel URL loads your app in browser.
4. ElevenLabs webhook/server tool base URLs use the current tunnel URL.
5. `.env` contains:
   - `ELEVENLABS_API_KEY`
   - `MODULATE_API_KEY`
   - `GEMINI_API_KEY`
   - `BRAINTRUST_INGEST_URL` (placeholder is fine for now)
6. One manual API smoke test returns `200` (for any implemented `/api/tools/*` route).
7. Caller location capture is enabled in agent prompt/flow before data tool calls.
