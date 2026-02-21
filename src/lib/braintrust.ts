import type { AgentDecision } from "@/lib/gemini";

type BraintrustLogEvent = {
  id: string;
  input: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
  tags?: string[];
  created?: string;
};

type TranscriptTurn = {
  turn_id: number;
  timestamp: string;
  user_text: string;
  assistant_text: string;
  risk_level: AgentDecision["risk_level"];
  emotion_state: AgentDecision["emotion_state"];
  action_taken: AgentDecision["action"]["type"];
};

type AgentTurnLogInput = {
  callId: string;
  turnId: number;
  timestamp: string;
  userText: string;
  inputEmotionState?: string;
  location: {
    lat?: number;
    lon?: number;
    state?: string;
    county?: string;
  };
  decision: AgentDecision;
  toolCalls: string[];
  toolOutputs: Record<string, unknown>;
  latencyMs: number;
};

type SafetyActionLogInput = {
  callId: string;
  turnId?: number;
  timestamp: string;
  actionType: string;
  reason: string;
  urgency: string;
  userContext: Record<string, unknown>;
  result: string;
  action: Record<string, unknown>;
};

const MAX_TRANSCRIPT_TURNS_PER_CALL = 300;
const MAX_TRANSCRIPT_CALLS = 500;
const transcriptStore = new Map<string, TranscriptTurn[]>();
let mostRecentCallId: string | undefined;

function pruneTranscriptStore() {
  while (transcriptStore.size > MAX_TRANSCRIPT_CALLS) {
    const oldestKey = transcriptStore.keys().next().value as string | undefined;
    if (!oldestKey) break;
    transcriptStore.delete(oldestKey);
  }
}

function upsertTranscriptTurn(callId: string, turn: TranscriptTurn) {
  mostRecentCallId = callId;
  const previous = transcriptStore.get(callId) ?? [];
  const withoutCurrentTurn = previous.filter(
    (item) => item.turn_id !== turn.turn_id
  );
  const next = [...withoutCurrentTurn, turn].sort((a, b) => {
    if (a.turn_id === b.turn_id) {
      return a.timestamp.localeCompare(b.timestamp);
    }
    return a.turn_id - b.turn_id;
  });

  if (next.length > MAX_TRANSCRIPT_TURNS_PER_CALL) {
    next.splice(0, next.length - MAX_TRANSCRIPT_TURNS_PER_CALL);
  }

  transcriptStore.set(callId, next);
  pruneTranscriptStore();
  return next;
}

export function getMostRecentCallId() {
  return mostRecentCallId;
}

function transcriptToText(transcript: TranscriptTurn[]) {
  return transcript
    .map(
      (turn) =>
        `Turn ${turn.turn_id} User: ${turn.user_text}\nTurn ${turn.turn_id} Agent: ${turn.assistant_text}`
    )
    .join("\n");
}

function readString(value: unknown) {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;
}

function readTranscriptFromContext(userContext: Record<string, unknown>) {
  const candidate =
    userContext.full_transcript ??
    userContext.transcript ??
    userContext.conversation_transcript;

  if (!Array.isArray(candidate)) {
    return undefined;
  }

  const transcript: TranscriptTurn[] = [];
  for (const entry of candidate) {
    if (!entry || typeof entry !== "object") {
      continue;
    }
    const row = entry as Record<string, unknown>;
    const turnIdRaw = Number(row.turn_id ?? row.turnId);
    const turnId = Number.isFinite(turnIdRaw) ? Math.floor(turnIdRaw) : undefined;
    const userText = readString(row.user_text ?? row.userText);
    const assistantText = readString(
      row.assistant_text ?? row.assistantText ?? row.spoken_response
    );

    if (!turnId || !userText || !assistantText) {
      continue;
    }

    const riskLevel = readString(row.risk_level);
    const emotionState = readString(row.emotion_state);
    const actionTaken = readString(row.action_taken);
    transcript.push({
      turn_id: turnId,
      timestamp: readString(row.timestamp) ?? new Date().toISOString(),
      user_text: userText,
      assistant_text: assistantText,
      risk_level:
        riskLevel === "low" ||
        riskLevel === "medium" ||
        riskLevel === "high" ||
        riskLevel === "critical"
          ? riskLevel
          : "medium",
      emotion_state:
        emotionState === "calm" ||
        emotionState === "anxious" ||
        emotionState === "panicked" ||
        emotionState === "agitated"
          ? emotionState
          : "anxious",
      action_taken:
        actionTaken === "none" ||
        actionTaken === "safety_plan" ||
        actionTaken === "resource_handoff" ||
        actionTaken === "emergency_guidance"
          ? actionTaken
          : "none",
    });
  }

  return transcript.length > 0 ? transcript : undefined;
}

function getConfig() {
  const projectId = process.env.BRAINTRUST_PROJECT_ID?.trim();
  const apiKey = process.env.BRAINTRUST_API_KEY?.trim();

  if (!projectId || !apiKey) {
    return null;
  }

  const baseUrl = (process.env.BRAINTRUST_BASE_URL || "https://api.braintrust.dev").replace(/\/+$/, "");

  return {
    baseUrl,
    projectId,
    apiKey,
  };
}

async function insertProjectLogs(events: BraintrustLogEvent[]) {
  if (events.length === 0) return false;

  const config = getConfig();
  if (!config) {
    return false;
  }

  const response = await fetch(
    `${config.baseUrl}/v1/project_logs/${config.projectId}/insert`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${config.apiKey}`,
      },
      body: JSON.stringify({ events }),
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(`Braintrust insert failed with HTTP ${response.status}`);
  }

  return true;
}

async function postLegacyIngest(payload: unknown) {
  const ingestUrl = process.env.BRAINTRUST_INGEST_URL;
  if (!ingestUrl || ingestUrl.includes("localhost:0")) {
    return;
  }

  await fetch(ingestUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
}

export async function logAgentTurnEvent(input: AgentTurnLogInput) {
  const fullTranscript = upsertTranscriptTurn(input.callId, {
    turn_id: input.turnId,
    timestamp: input.timestamp,
    user_text: input.userText,
    assistant_text: input.decision.spoken_response,
    risk_level: input.decision.risk_level,
    emotion_state: input.decision.emotion_state,
    action_taken: input.decision.action.type,
  });
  const fullTranscriptText = transcriptToText(fullTranscript);

  const payload = {
    call_id: input.callId,
    turn_id: input.turnId,
    timestamp: input.timestamp,
    user_text: input.userText,
    emotion_state: input.decision.emotion_state,
    risk_level: input.decision.risk_level,
    tool_calls: input.toolCalls,
    tool_outputs: input.toolOutputs,
    action_taken: input.decision.action.type,
    spoken_response: input.decision.spoken_response,
    latency_ms: input.latencyMs,
    full_transcript: fullTranscript,
    full_transcript_text: fullTranscriptText,
  };

  try {
    await insertProjectLogs([
      {
        id: crypto.randomUUID(),
        input: {
          user_text: input.userText,
          input_emotion_state: input.inputEmotionState,
          location: input.location,
          transcript_turn: fullTranscript.find((turn) => turn.turn_id === input.turnId),
          full_transcript: fullTranscript,
          full_transcript_text: fullTranscriptText,
        },
        output: {
          risk_level: input.decision.risk_level,
          emotion_state: input.decision.emotion_state,
          deescalation_style: input.decision.deescalation_style,
          spoken_response: input.decision.spoken_response,
          action: input.decision.action,
        },
        metadata: {
          call_id: input.callId,
          turn_id: input.turnId,
          transcript_turn_count: fullTranscript.length,
          full_transcript: fullTranscript,
          full_transcript_text: fullTranscriptText,
          weather_agent_event: payload,
        },
        tags: ["voice-agent", "weather-anxiety", "agent-turn"],
        created: input.timestamp,
      },
    ]);
    return;
  } catch {
    // Keep turn processing non-blocking.
  }

  try {
    await postLegacyIngest({
      event_type: "agent_turn",
      timestamp: input.timestamp,
      input: {
        userText: input.userText,
        emotionState: input.inputEmotionState,
        ...input.location,
      },
      output: input.decision,
      context: input.toolOutputs,
      call_id: input.callId,
      turn_id: input.turnId,
      latency_ms: input.latencyMs,
      full_transcript: fullTranscript,
      full_transcript_text: fullTranscriptText,
    });
  } catch {
    // Best-effort only.
  }
}

export async function logSafetyActionEvent(input: SafetyActionLogInput) {
  mostRecentCallId = input.callId;
  const transcriptFromContext = readTranscriptFromContext(input.userContext);
  const fullTranscript = transcriptFromContext ?? transcriptStore.get(input.callId) ?? [];
  const fullTranscriptText = transcriptToText(fullTranscript);

  try {
    await insertProjectLogs([
      {
        id: crypto.randomUUID(),
        input: {
          action_type: input.actionType,
          reason: input.reason,
          urgency: input.urgency,
          user_context: input.userContext,
          full_transcript: fullTranscript,
          full_transcript_text: fullTranscriptText,
        },
        output: {
          result: input.result,
          action: input.action,
        },
        metadata: {
          call_id: input.callId,
          turn_id: input.turnId,
          action_type: input.actionType,
          transcript_turn_count: fullTranscript.length,
          full_transcript: fullTranscript,
          full_transcript_text: fullTranscriptText,
        },
        tags: ["voice-agent", "weather-anxiety", "safety-action"],
        created: input.timestamp,
      },
    ]);
    return;
  } catch {
    // Keep tool execution non-blocking.
  }

  try {
    await postLegacyIngest({
      event_type: "safety_action_executed",
      action: input.action,
      call_id: input.callId,
      turn_id: input.turnId,
      timestamp: input.timestamp,
      full_transcript: fullTranscript,
      full_transcript_text: fullTranscriptText,
    });
  } catch {
    // Best-effort only.
  }
}
