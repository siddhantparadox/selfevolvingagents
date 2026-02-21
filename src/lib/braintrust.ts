import {
  SpanKind,
  type AttributeValue,
  type Span,
  type Tracer,
  trace,
} from "@opentelemetry/api";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
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

type OTelSpanInput = {
  spanName: string;
  callId: string;
  turnId?: number;
  startTimestamp: string;
  endTimestamp: string;
  attributes: Record<string, unknown>;
  events?: Array<{
    name: string;
    timestamp: string;
    attributes?: Record<string, unknown>;
  }>;
};

type OTelRuntime = {
  provider: NodeTracerProvider;
  tracer: Tracer;
  projectId: string;
};

const MAX_TRANSCRIPT_TURNS_PER_CALL = 300;
const MAX_TRANSCRIPT_CALLS = 500;
const transcriptStore = new Map<string, TranscriptTurn[]>();
let mostRecentCallId: string | undefined;
let otelRuntime: OTelRuntime | null = null;

function debugBraintrust(message: string, error?: unknown) {
  if (process.env.BRAINTRUST_DEBUG !== "true") {
    return;
  }

  if (error instanceof Error) {
    console.warn(`[braintrust] ${message}: ${error.message}`);
    return;
  }

  if (error) {
    console.warn(`[braintrust] ${message}:`, error);
    return;
  }

  console.warn(`[braintrust] ${message}`);
}

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

function transcriptToMessages(transcript: TranscriptTurn[]) {
  return transcript.flatMap((turn) => [
    {
      role: "user",
      turn_id: turn.turn_id,
      content: turn.user_text,
      timestamp: turn.timestamp,
    },
    {
      role: "assistant",
      turn_id: turn.turn_id,
      content: turn.assistant_text,
      timestamp: turn.timestamp,
    },
  ]);
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
    otelUrl: `${baseUrl}/otel/v1/traces`,
  };
}

function getOtelRuntime() {
  const config = getConfig();
  if (!config) {
    return null;
  }

  if (otelRuntime && otelRuntime.projectId === config.projectId) {
    return otelRuntime;
  }

  const exporter = new OTLPTraceExporter({
    url: config.otelUrl,
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      "x-bt-parent": `project_id:${config.projectId}`,
    },
  });

  const provider = new NodeTracerProvider({
    resource: resourceFromAttributes({
      "service.name": "selfimprovingagents",
      "deployment.environment": process.env.NODE_ENV ?? "development",
    }),
    spanProcessors: [new BatchSpanProcessor(exporter)],
  });

  provider.register();

  otelRuntime = {
    provider,
    tracer: trace.getTracer("selfimprovingagents.braintrust", "0.1.0"),
    projectId: config.projectId,
  };

  return otelRuntime;
}

function toOpenTelemetryAttribute(value: unknown): AttributeValue {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return value;
  }

  if (Array.isArray(value)) {
    const isPrimitiveArray = value.every(
      (item) =>
        typeof item === "string" ||
        typeof item === "number" ||
        typeof item === "boolean"
    );

    if (isPrimitiveArray) {
      return value as AttributeValue;
    }
  }

  if (value === undefined) {
    return "";
  }

  return JSON.stringify(value);
}

function setSpanAttributes(span: Span, attributes: Record<string, unknown>) {
  for (const [key, value] of Object.entries(attributes)) {
    if (value === undefined) continue;
    span.setAttribute(key, toOpenTelemetryAttribute(value));
  }
}

function toDate(isoTime: string) {
  const ms = Date.parse(isoTime);
  if (!Number.isFinite(ms)) {
    return new Date();
  }
  return new Date(ms);
}

async function sendOtelSpan(input: OTelSpanInput) {
  const runtime = getOtelRuntime();
  if (!runtime) {
    debugBraintrust("OTel runtime unavailable; skipping span export");
    return false;
  }

  const span = runtime.tracer.startSpan(
    input.spanName,
    {
      kind: SpanKind.INTERNAL,
      startTime: toDate(input.startTimestamp),
    }
  );

  setSpanAttributes(span, {
    "braintrust.project_id": runtime.projectId,
    call_id: input.callId,
    ...(input.turnId ? { turn_id: input.turnId } : {}),
    ...input.attributes,
  });

  for (const event of input.events ?? []) {
    span.addEvent(
      event.name,
      Object.fromEntries(
        Object.entries(event.attributes ?? {}).map(([key, value]) => [
          key,
          toOpenTelemetryAttribute(value),
        ])
      ),
      toDate(event.timestamp)
    );
  }

  span.end(toDate(input.endTimestamp));

  await runtime.provider.forceFlush();
  debugBraintrust(`Exported OTel span '${input.spanName}'`);
  return true;
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
  const conversationMessages = transcriptToMessages(fullTranscript);

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

  let logInserted = false;
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
    logInserted = true;
  } catch {
    debugBraintrust("Project log insert failed in logAgentTurnEvent");
    // Keep turn processing non-blocking.
  }

  try {
    const endMs = Date.parse(input.timestamp);
    const startMs = Number.isFinite(endMs) ? Math.max(0, endMs - input.latencyMs) : Date.now();
    await sendOtelSpan({
      spanName: "weather_agent.turn",
      callId: input.callId,
      turnId: input.turnId,
      startTimestamp: new Date(startMs).toISOString(),
      endTimestamp: input.timestamp,
      attributes: {
        "openinference.span.kind": "AGENT",
        "input.value": input.userText,
        "output.value": input.decision.spoken_response,
        "gen_ai.prompt": input.userText,
        "gen_ai.completion": input.decision.spoken_response,
        "gen_ai.input.messages": conversationMessages,
        "gen_ai.output.messages": [
          {
            role: "assistant",
            content: input.decision.spoken_response,
            turn_id: input.turnId,
            timestamp: input.timestamp,
          },
        ],
        "braintrust.input_json": {
          messages: conversationMessages,
          input_emotion_state: input.inputEmotionState,
          location: input.location,
        },
        "braintrust.output_json": {
          risk_level: input.decision.risk_level,
          emotion_state: input.decision.emotion_state,
          deescalation_style: input.decision.deescalation_style,
          spoken_response: input.decision.spoken_response,
          action: input.decision.action,
        },
        "weather_agent.tool_calls": input.toolCalls,
        "weather_agent.tool_outputs": input.toolOutputs,
        "weather_agent.full_transcript": fullTranscript,
        "weather_agent.full_transcript_text": fullTranscriptText,
      },
      events: [
        {
          name: "gen_ai.user.message",
          timestamp: input.timestamp,
          attributes: {
            role: "user",
            content: input.userText,
            turn_id: input.turnId,
          },
        },
        {
          name: "gen_ai.assistant.message",
          timestamp: input.timestamp,
          attributes: {
            role: "assistant",
            content: input.decision.spoken_response,
            turn_id: input.turnId,
          },
        },
      ],
    });
  } catch (error) {
    debugBraintrust("OTel span export failed in logAgentTurnEvent", error);
    // Keep turn processing non-blocking.
  }

  if (logInserted) {
    return;
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
  } catch (error) {
    debugBraintrust("Legacy ingest failed in logAgentTurnEvent", error);
    // Best-effort only.
  }
}

export async function logSafetyActionEvent(input: SafetyActionLogInput) {
  mostRecentCallId = input.callId;
  const transcriptFromContext = readTranscriptFromContext(input.userContext);
  const fullTranscript = transcriptFromContext ?? transcriptStore.get(input.callId) ?? [];
  const fullTranscriptText = transcriptToText(fullTranscript);
  const conversationMessages = transcriptToMessages(fullTranscript);

  let logInserted = false;
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
    logInserted = true;
  } catch (error) {
    debugBraintrust("Project log insert failed in logSafetyActionEvent", error);
    // Keep tool execution non-blocking.
  }

  try {
    await sendOtelSpan({
      spanName: "weather_agent.safety_action",
      callId: input.callId,
      turnId: input.turnId,
      startTimestamp: input.timestamp,
      endTimestamp: input.timestamp,
      attributes: {
        "openinference.span.kind": "TOOL",
        "tool.name": "execute_safety_action",
        "input.value": JSON.stringify({
          action_type: input.actionType,
          reason: input.reason,
          urgency: input.urgency,
          full_transcript: fullTranscript,
        }),
        "output.value": input.result,
        "gen_ai.input.messages": conversationMessages,
        "braintrust.input_json": {
          action_type: input.actionType,
          reason: input.reason,
          urgency: input.urgency,
          user_context: input.userContext,
          messages: conversationMessages,
          full_transcript: fullTranscript,
        },
        "braintrust.output_json": {
          result: input.result,
          action: input.action,
        },
        "weather_agent.full_transcript": fullTranscript,
        "weather_agent.full_transcript_text": fullTranscriptText,
      },
      events: [
        {
          name: "gen_ai.user.message",
          timestamp: input.timestamp,
          attributes: {
            role: "user",
            content:
              fullTranscript.length > 0
                ? fullTranscript[fullTranscript.length - 1].user_text
                : input.reason,
          },
        },
        {
          name: "gen_ai.assistant.message",
          timestamp: input.timestamp,
          attributes: {
            role: "assistant",
            content:
              fullTranscript.length > 0
                ? fullTranscript[fullTranscript.length - 1].assistant_text
                : input.result,
          },
        },
      ],
    });
  } catch (error) {
    debugBraintrust("OTel span export failed in logSafetyActionEvent", error);
    // Keep tool execution non-blocking.
  }

  if (logInserted) {
    return;
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
  } catch (error) {
    debugBraintrust("Legacy ingest failed in logSafetyActionEvent", error);
    // Best-effort only.
  }
}
