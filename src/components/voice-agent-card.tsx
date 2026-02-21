"use client";

import { Conversation, type Mode, type Role, type Status } from "@elevenlabs/client";
import { useEffect, useRef, useState } from "react";
import { Orb, type AgentState } from "@/components/ui/orb";
import {
  Conversation as ConversationPanel,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ui/conversation";
import { cn } from "@/lib/utils";

type VoiceAgentCardProps = {
  agentId?: string;
};

type UiState = "idle" | "listening" | "talking";

type TranscriptMessage = {
  id: string;
  role: "user" | "agent";
  content: string;
};

export function VoiceAgentCard({ agentId }: VoiceAgentCardProps) {
  const conversationRef = useRef<Conversation | null>(null);
  const [status, setStatus] = useState<Status>("disconnected");
  const [agentState, setAgentState] = useState<AgentState>(null);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);

  const uiState: UiState =
    agentState === "talking"
      ? "talking"
      : agentState === "listening"
        ? "listening"
        : "idle";

  useEffect(() => {
    return () => {
      void conversationRef.current?.endSession();
      conversationRef.current = null;
    };
  }, []);

  function onModeChange(mode: Mode) {
    setAgentState(mode === "speaking" ? "talking" : "listening");
  }

  function onStatusChange(nextStatus: Status) {
    setStatus(nextStatus);
    if (nextStatus === "connecting") {
      setAgentState("thinking");
    }
    if (nextStatus === "disconnected") {
      setAgentState(null);
      conversationRef.current = null;
    }
  }

  function pushMessage(payload: { message: string; role: Role }) {
    const text = payload.message.trim();
    if (!text) return;

    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === payload.role && last.content === text) {
        return prev;
      }
      if (last && last.role === payload.role && text.startsWith(last.content)) {
        return [...prev.slice(0, -1), { ...last, content: text }];
      }
      return [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: payload.role,
          content: text,
        },
      ];
    });
  }

  async function startConversation() {
    if (!agentId) {
      setError("Missing ELEVENLABS_AGENT_ID in .env.");
      return;
    }
    if (conversationRef.current) {
      return;
    }

    setError(null);
    setStatus("connecting");
    setAgentState("thinking");

    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setStatus("disconnected");
      setAgentState(null);
      setError("Microphone permission is blocked. Please allow mic access and retry.");
      return;
    }

    try {
      const conversation = await Conversation.startSession({
        agentId,
        connectionType: "webrtc",
        onModeChange: ({ mode }) => onModeChange(mode),
        onStatusChange: ({ status: nextStatus }) => onStatusChange(nextStatus),
        onMessage: (payload) => pushMessage(payload),
        onError: (message) => setError(message),
        onDisconnect: () => {
          setStatus("disconnected");
          setAgentState(null);
          conversationRef.current = null;
        },
      });
      conversationRef.current = conversation;
    } catch {
      setStatus("disconnected");
      setAgentState(null);
      setError("Could not start the voice session. Please retry.");
    }
  }

  async function endConversation() {
    const current = conversationRef.current;
    if (!current) return;

    setStatus("disconnecting");
    try {
      await current.endSession();
    } finally {
      conversationRef.current = null;
      setStatus("disconnected");
      setAgentState(null);
    }
  }

  const isConnected = status === "connected";
  const isBusy = status === "connecting" || status === "disconnecting";

  return (
    <section className="w-full max-w-[1180px] rounded-2xl border border-white/10 bg-[#0f1116] p-6 text-white shadow-[0_20px_80px_rgba(0,0,0,0.55)]">
      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <div className="rounded-2xl border border-white/10 bg-black/20 p-6">
          <h1 className="text-4xl font-semibold tracking-tight">Agent Orbs</h1>
          <p className="mt-2 text-2xl text-slate-300">
            Interactive orb visualization with agent states
          </p>

          <div className="mx-auto mt-8 h-64 w-64 rounded-full border-4 border-black bg-black shadow-[0_0_45px_rgba(163,182,255,0.25)]">
            <Orb
              agentState={agentState}
              colors={["#d0dcff", "#9fb6ff"]}
              getInputVolume={() => conversationRef.current?.getInputVolume() ?? 0}
              getOutputVolume={() => conversationRef.current?.getOutputVolume() ?? 0}
            />
          </div>

          <div className="mt-8 flex items-center justify-center gap-3">
            {(["idle", "listening", "talking"] as UiState[]).map((state) => (
              <div
                key={state}
                className={cn(
                  "rounded-xl border px-4 py-2 text-lg font-medium capitalize transition-colors",
                  uiState === state
                    ? "border-slate-500 bg-slate-800 text-white"
                    : "border-white/15 bg-white/5 text-slate-400"
                )}
              >
                {state}
              </div>
            ))}
          </div>

          <div className="mt-8 flex items-center justify-center">
            <button
              type="button"
              onClick={isConnected ? endConversation : startConversation}
              disabled={!agentId || isBusy}
              className="rounded-xl border border-white/20 bg-white/10 px-8 py-4 text-2xl font-semibold text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isConnected ? "End Call" : isBusy ? "Connecting..." : "Start Call"}
            </button>
          </div>

          <p className="mt-4 text-center text-lg text-slate-400">
            Status: <span className="capitalize">{status}</span>
          </p>
          {error ? (
            <p className="mt-3 text-center text-base text-rose-300">{error}</p>
          ) : null}
        </div>

        <ConversationPanel className="h-[700px] border-white/10 bg-black/25">
          <ConversationContent className="space-y-6 p-6">
            {messages.length === 0 ? (
              <ConversationEmptyState
                title="No transcript yet"
                description="Start the call and your live conversation transcript will appear here."
              />
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    "flex w-full items-end gap-3",
                    message.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  {message.role === "agent" ? (
                    <div className="h-8 w-8 shrink-0 rounded-full border border-[#6d85d8] bg-[radial-gradient(circle_at_30%_30%,_#d0dcff,_#9fb6ff_55%,_#44538a)]" />
                  ) : null}

                  <div
                    className={cn(
                      "max-w-[78%] rounded-3xl px-6 py-4 text-2xl leading-relaxed shadow-sm",
                      message.role === "user"
                        ? "bg-white text-slate-900"
                        : "bg-[#22252c] text-slate-100"
                    )}
                  >
                    {message.content}
                  </div>
                </div>
              ))
            )}
          </ConversationContent>
          <ConversationScrollButton />
        </ConversationPanel>
      </div>
    </section>
  );
}
