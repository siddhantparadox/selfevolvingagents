import { GoogleGenAI, type Schema, Type } from "@google/genai";

export type AgentDecision = {
  risk_level: "low" | "medium" | "high" | "critical";
  emotion_state: "calm" | "anxious" | "panicked" | "agitated";
  deescalation_style: "reassure" | "grounding" | "directive";
  spoken_response: string;
  action: {
    type: "none" | "safety_plan" | "resource_handoff" | "emergency_guidance";
    should_execute: boolean;
    reason: string;
    urgency: "low" | "medium" | "high" | "critical";
  };
};

type DecisionInput = {
  userText: string;
  state?: string;
  county?: string;
  weatherSummary: string;
  floodSummary: string;
  femaSummary: string;
};

const MODEL = process.env.GEMINI_MODEL ?? "gemini-3-flash-preview";

const DECISION_SCHEMA: Schema = {
  type: Type.OBJECT,
  required: [
    "risk_level",
    "emotion_state",
    "deescalation_style",
    "spoken_response",
    "action",
  ],
  properties: {
    risk_level: {
      type: Type.STRING,
      enum: ["low", "medium", "high", "critical"],
      description: "Overall risk level for this caller turn.",
    },
    emotion_state: {
      type: Type.STRING,
      enum: ["calm", "anxious", "panicked", "agitated"],
      description: "Estimated caller emotional state.",
    },
    deescalation_style: {
      type: Type.STRING,
      enum: ["reassure", "grounding", "directive"],
      description: "Tone strategy for spoken response.",
    },
    spoken_response: {
      type: Type.STRING,
      description: "A short spoken response for voice output.",
    },
    action: {
      type: Type.OBJECT,
      required: ["type", "should_execute", "reason", "urgency"],
      properties: {
        type: {
          type: Type.STRING,
          enum: ["none", "safety_plan", "resource_handoff", "emergency_guidance"],
          description: "Safety action to execute.",
        },
        should_execute: {
          type: Type.BOOLEAN,
          description: "Whether action should be executed now.",
        },
        reason: {
          type: Type.STRING,
          description: "Reason for the selected action.",
        },
        urgency: {
          type: Type.STRING,
          enum: ["low", "medium", "high", "critical"],
          description: "Urgency of selected action.",
        },
      },
    },
  },
};

function fallbackDecision(): AgentDecision {
  return {
    risk_level: "medium",
    emotion_state: "anxious",
    deescalation_style: "reassure",
    spoken_response:
      "I hear you. I could not fully process live model guidance right now, but I can still help with calm, practical safety steps based on current weather information.",
    action: {
      type: "safety_plan",
      should_execute: true,
      reason: "Fallback safety guidance",
      urgency: "medium",
    },
  };
}

function isValidDecision(value: unknown): value is AgentDecision {
  if (!value || typeof value !== "object") return false;
  const d = value as Record<string, unknown>;
  const validRisk = ["low", "medium", "high", "critical"].includes(
    String(d.risk_level)
  );
  const validEmotion = ["calm", "anxious", "panicked", "agitated"].includes(
    String(d.emotion_state)
  );
  const validStyle = ["reassure", "grounding", "directive"].includes(
    String(d.deescalation_style)
  );
  const action = d.action as Record<string, unknown> | undefined;
  if (!action || typeof action !== "object") return false;
  const validActionType = [
    "none",
    "safety_plan",
    "resource_handoff",
    "emergency_guidance",
  ].includes(String(action.type));
  const validUrgency = ["low", "medium", "high", "critical"].includes(
    String(action.urgency)
  );
  return (
    validRisk &&
    validEmotion &&
    validStyle &&
    typeof d.spoken_response === "string" &&
    typeof action.should_execute === "boolean" &&
    typeof action.reason === "string" &&
    validActionType &&
    validUrgency
  );
}

export async function generateAgentDecision(
  input: DecisionInput
): Promise<AgentDecision> {
  if (!process.env.GEMINI_API_KEY) {
    return fallbackDecision();
  }

  const ai = new GoogleGenAI({
    apiKey: process.env.GEMINI_API_KEY,
  });

  const prompt = `
You are a weather de-escalation voice agent.
Goal: calm the caller with empathy and factual live context.
Do not hallucinate data. Use only provided summaries.
Keep spoken_response under 60 words.

Caller message: ${input.userText}
State: ${input.state ?? "unknown"}
County: ${input.county ?? "unknown"}
Weather summary: ${input.weatherSummary}
Flood summary: ${input.floodSummary}
FEMA summary: ${input.femaSummary}
`;

  try {
    const response = await ai.models.generateContent({
      model: MODEL,
      contents: prompt,
      config: {
        temperature: 0.2,
        responseMimeType: "application/json",
        responseSchema: DECISION_SCHEMA,
      },
    });

    const raw = response.text?.trim() ?? "";
    if (!raw) {
      return fallbackDecision();
    }
    const parsed = JSON.parse(raw);
    if (!isValidDecision(parsed)) {
      return fallbackDecision();
    }
    return parsed;
  } catch {
    return fallbackDecision();
  }
}
