import { NextRequest, NextResponse } from "next/server";
import { generateAgentDecision, type AgentDecision } from "@/lib/gemini";
import { getMostRecentCallId, logAgentTurnEvent } from "@/lib/braintrust";
import { getFemaContext } from "@/lib/services/fema";
import { getFloodContext } from "@/lib/services/usgs";
import { getWeatherContext } from "@/lib/services/weather";

type AgentTurnRequest = {
  userText?: string;
  emotionState?: string;
  location?: {
    lat?: number;
    lon?: number;
    state?: string;
    county?: string;
  };
  callId?: string;
  call_id?: string;
  conversationId?: string;
  conversation_id?: string;
  turnId?: number;
  turn_id?: number;
};

const MISSING_LOCATION_DECISION: AgentDecision = {
  risk_level: "medium",
  emotion_state: "anxious",
  deescalation_style: "reassure",
  spoken_response:
    "I can help. Please share where you are calling from so I can check real-time local weather.",
  action: {
    type: "none",
    should_execute: false,
    reason: "Missing location",
    urgency: "low",
  },
};

function readString(value: unknown) {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;
}

function readPositiveInt(value: unknown) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return undefined;
  const intValue = Math.floor(parsed);
  return intValue > 0 ? intValue : undefined;
}

function getCallId(req: NextRequest, body: AgentTurnRequest) {
  return (
    readString(body.call_id) ??
    readString(body.callId) ??
    readString(body.conversation_id) ??
    readString(body.conversationId) ??
    readString(req.headers.get("x-call-id")) ??
    readString(req.headers.get("x-conversation-id")) ??
    getMostRecentCallId() ??
    `call_${Date.now()}`
  );
}

function getTurnId(req: NextRequest, body: AgentTurnRequest) {
  return (
    readPositiveInt(body.turn_id) ??
    readPositiveInt(body.turnId) ??
    readPositiveInt(req.headers.get("x-turn-id")) ??
    1
  );
}

export async function POST(req: NextRequest) {
  const startedAt = Date.now();
  const body = (await req.json().catch(() => ({}))) as AgentTurnRequest;
  const userText = body.userText?.trim();

  if (!userText) {
    return NextResponse.json(
      { error: "Missing userText in request body." },
      { status: 400 }
    );
  }

  const callId = getCallId(req, body);
  const turnId = getTurnId(req, body);

  const lat = Number(body.location?.lat);
  const lon = Number(body.location?.lon);
  const state = body.location?.state?.trim().toUpperCase();
  const county = body.location?.county?.trim();

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    await logAgentTurnEvent({
      callId,
      turnId,
      timestamp: new Date().toISOString(),
      userText,
      inputEmotionState: body.emotionState,
      location: {
        state,
        county,
      },
      decision: MISSING_LOCATION_DECISION,
      toolCalls: [],
      toolOutputs: {
        summary: "Missing location. Agent asked caller for city/state or ZIP.",
      },
      latencyMs: Date.now() - startedAt,
    });

    return NextResponse.json(MISSING_LOCATION_DECISION);
  }

  const [weatherContext, floodContext, femaContext] = await Promise.all([
    getWeatherContext(lat, lon).catch(() => ({
      summary:
        "Weather context unavailable at the moment. Use calm, conservative safety guidance.",
    })),
    getFloodContext(state).catch(() => ({
      summary: "USGS flood context unavailable.",
    })),
    getFemaContext(state, county).catch(() => ({
      summary: "FEMA context unavailable.",
    })),
  ]);

  const decision = await generateAgentDecision({
    userText,
    state,
    county,
    weatherSummary: weatherContext.summary,
    floodSummary: floodContext.summary,
    femaSummary: femaContext.summary,
  });

  await logAgentTurnEvent({
    callId,
    turnId,
    timestamp: new Date().toISOString(),
    userText,
    inputEmotionState: body.emotionState,
    location: {
      lat,
      lon,
      state,
      county,
    },
    decision,
    toolCalls: ["get_weather_alerts", "get_flood_context", "get_fema_context"],
    toolOutputs: {
      weather_summary: weatherContext.summary,
      flood_summary: floodContext.summary,
      fema_summary: femaContext.summary,
    },
    latencyMs: Date.now() - startedAt,
  });

  return NextResponse.json({
    ...decision,
    call_id: callId,
    turn_id: turnId,
    context: {
      weather: weatherContext,
      flood: floodContext,
      fema: femaContext,
    },
  });
}
