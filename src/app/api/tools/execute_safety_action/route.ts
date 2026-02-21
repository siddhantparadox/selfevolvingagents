import { NextRequest, NextResponse } from "next/server";

type ActionType =
  | "none"
  | "safety_plan"
  | "resource_handoff"
  | "emergency_guidance";

function getParams(body: unknown): Record<string, unknown> {
  if (!body || typeof body !== "object") return {};
  const maybe = body as Record<string, unknown>;
  if (maybe.parameters && typeof maybe.parameters === "object") {
    return maybe.parameters as Record<string, unknown>;
  }
  return maybe;
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const params = getParams(body);

  const actionType = (params.action_type ??
    params.actionType ??
    "none") as ActionType;
  const reason = String(params.reason ?? "No reason provided");
  const urgency = String(params.urgency ?? "low");
  const userContext =
    typeof params.user_context === "object" && params.user_context
      ? params.user_context
      : typeof params.userContext === "object" && params.userContext
        ? params.userContext
        : {};

  const action = {
    action_id: `action_${Date.now()}`,
    action_type: actionType,
    reason,
    urgency,
    user_context: userContext,
    executed_at: new Date().toISOString(),
  };

  const ingestUrl = process.env.BRAINTRUST_INGEST_URL;
  if (ingestUrl && !ingestUrl.includes("localhost:0")) {
    try {
      await fetch(ingestUrl, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          event_type: "safety_action_executed",
          action,
        }),
      });
    } catch {
      // Best-effort placeholder handoff only.
    }
  }

  return NextResponse.json({
    result: `Executed action '${actionType}' with ${urgency} urgency.`,
    action,
  });
}
