import { NextRequest, NextResponse } from "next/server";
import { generateAgentDecision } from "@/lib/gemini";
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
};

export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => ({}))) as AgentTurnRequest;
  const userText = body.userText?.trim();

  if (!userText) {
    return NextResponse.json(
      { error: "Missing userText in request body." },
      { status: 400 }
    );
  }

  const lat = Number(body.location?.lat);
  const lon = Number(body.location?.lon);
  const state = body.location?.state?.trim().toUpperCase();
  const county = body.location?.county?.trim();

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return NextResponse.json({
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
    });
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

  const ingestUrl = process.env.BRAINTRUST_INGEST_URL;
  if (ingestUrl && !ingestUrl.includes("localhost:0")) {
    try {
      await fetch(ingestUrl, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          event_type: "agent_turn",
          timestamp: new Date().toISOString(),
          input: { userText, emotionState: body.emotionState, lat, lon, state, county },
          output: decision,
          context: {
            weather_summary: weatherContext.summary,
            flood_summary: floodContext.summary,
            fema_summary: femaContext.summary,
          },
        }),
      });
    } catch {
      // Keep turn non-blocking while Braintrust endpoint is placeholder.
    }
  }

  return NextResponse.json({
    ...decision,
    context: {
      weather: weatherContext,
      flood: floodContext,
      fema: femaContext,
    },
  });
}
