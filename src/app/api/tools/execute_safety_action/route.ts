import { NextRequest, NextResponse } from "next/server";
import { getMostRecentCallId, logSafetyActionEvent } from "@/lib/braintrust";

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

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const params = getParams(body);

  const actionType = (params.action_type ??
    params.actionType ??
    "none") as ActionType;
  const reason = String(params.reason ?? "No reason provided");
  const urgency = String(params.urgency ?? "low");
  const userContextRaw =
    typeof params.user_context === "object" && params.user_context
      ? params.user_context
      : typeof params.userContext === "object" && params.userContext
        ? params.userContext
        : {};
  const userContext = userContextRaw as Record<string, unknown>;
  const transcriptCandidate =
    params.full_transcript ?? params.transcript ?? params.conversation_transcript;
  if (
    transcriptCandidate !== undefined &&
    userContext.full_transcript === undefined &&
    userContext.transcript === undefined &&
    userContext.conversation_transcript === undefined
  ) {
    userContext.full_transcript = transcriptCandidate;
  }
  if (userContext.user_text === undefined && params.user_text !== undefined) {
    userContext.user_text = params.user_text;
  }
  if (userContext.user_text === undefined && params.userText !== undefined) {
    userContext.user_text = params.userText;
  }
  if (
    userContext.assistant_text === undefined &&
    params.assistant_text !== undefined
  ) {
    userContext.assistant_text = params.assistant_text;
  }
  if (
    userContext.assistant_text === undefined &&
    params.spoken_response !== undefined
  ) {
    userContext.assistant_text = params.spoken_response;
  }

  const action = {
    action_id: `action_${Date.now()}`,
    action_type: actionType,
    reason,
    urgency,
    user_context: userContext,
    executed_at: new Date().toISOString(),
  };

  const result = `Executed action '${actionType}' with ${urgency} urgency.`;

  const callId =
    readString(params.call_id) ??
    readString(params.callId) ??
    readString(userContext.call_id) ??
    readString(userContext.callId) ??
    readString(userContext.conversation_id) ??
    readString(userContext.conversationId) ??
    readString(req.headers.get("x-call-id")) ??
    readString(req.headers.get("x-conversation-id")) ??
    getMostRecentCallId() ??
    `call_${Date.now()}`;

  const turnId =
    readPositiveInt(params.turn_id) ??
    readPositiveInt(params.turnId) ??
    readPositiveInt(userContext.turn_id) ??
    readPositiveInt(userContext.turnId) ??
    readPositiveInt(req.headers.get("x-turn-id"));

  await logSafetyActionEvent({
    callId,
    turnId,
    timestamp: new Date().toISOString(),
    actionType,
    reason,
    urgency,
    userContext,
    result,
    action,
  });

  return NextResponse.json({
    result,
    action,
    call_id: callId,
    turn_id: turnId,
  });
}
