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
import { Response } from "@/components/ui/response";
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

function formatAgentMessageAsMarkdown(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return trimmed;

  // Preserve existing markdown if present.
  if (/(^|\n)\s{0,3}([#>*-]|\d+\.)\s|```|\[[^\]]+\]\([^)]+\)/m.test(trimmed)) {
    return trimmed;
  }

  const sentences =
    trimmed
      .match(/[^.!?]+[.!?]+|[^.!?]+$/g)
      ?.map((s) => s.trim())
      .filter(Boolean) ?? [trimmed];

  if (sentences.length < 2) return trimmed;

  const [headline, ...details] = sentences;
  return `**${headline}**\n\n${details.map((d) => `- ${d}`).join("\n")}`;
}

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
    <section className="glass-shell w-full max-w-[1240px] overflow-hidden rounded-3xl p-4 text-[color:var(--foreground)] shadow-[0_28px_84px_rgba(2,6,12,0.48)] sm:p-6">
      <div className="grid gap-4 lg:grid-cols-[380px_1fr] lg:gap-6">
        <aside className="glass-panel rounded-3xl p-5 sm:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[color:var(--accent)]">
            Phoenix
          </p>
          <h1 className="mt-2 font-display text-4xl leading-none sm:text-5xl">
            Calm Through Weather
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-[color:var(--muted-foreground)] sm:text-base">
            Phoenix listens in real time, grounds anxious moments, and gives clear weather-aware
            next steps.
          </p>

          <div className="mx-auto mt-6 flex h-56 w-56 items-center justify-center rounded-full border-4 border-black/25 bg-[radial-gradient(circle_at_32%_28%,rgba(38,61,98,0.9),rgba(16,24,36,0.98))] shadow-[0_0_0_1px_rgba(148,178,217,0.28),0_0_62px_rgba(255,178,102,0.28)]">
            <Orb
              agentState={agentState}
              colors={["#ffd199", "#84c8ff"]}
              getInputVolume={() => conversationRef.current?.getInputVolume() ?? 0}
              getOutputVolume={() => conversationRef.current?.getOutputVolume() ?? 0}
            />
          </div>

          <div className="mt-6 grid grid-cols-3 gap-2">
            {(["idle", "listening", "talking"] as UiState[]).map((state) => (
              <div
                key={state}
                className={cn(
                  "rounded-full border px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide transition sm:text-sm",
                  uiState === state
                    ? "border-[color:var(--primary)] bg-[color:var(--primary)]/20 text-[color:var(--foreground)]"
                    : "border-[color:var(--panel-border)] bg-white/5 text-[color:var(--muted-foreground)]"
                )}
              >
                {state}
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center justify-center">
            <button
              type="button"
              onClick={isConnected ? endConversation : startConversation}
              disabled={!agentId || isBusy}
              className="inline-flex min-h-11 min-w-40 items-center justify-center rounded-xl border border-[color:var(--panel-border)] bg-[linear-gradient(140deg,rgba(255,178,102,0.95),rgba(255,141,87,0.92))] px-7 py-3 text-base font-semibold text-[color:var(--primary-foreground)] shadow-[0_12px_26px_rgba(15,8,4,0.34)] transition hover:brightness-105 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isConnected ? "End Call" : isBusy ? "Connecting..." : "Start Call"}
            </button>
          </div>

          <p className="mt-4 text-center text-sm text-[color:var(--muted-foreground)]">
            Status: <span className="capitalize text-[color:var(--foreground)]">{status}</span>
          </p>
          {error ? (
            <p className="mt-3 rounded-lg border border-[color:var(--destructive)]/35 bg-[color:var(--destructive)]/12 px-3 py-2 text-center text-sm text-[color:var(--destructive)]">
              {error}
            </p>
          ) : null}

          <div className="mt-5 space-y-3 rounded-2xl border border-[color:var(--panel-border)]/70 bg-black/15 p-4 text-sm">
            <p className="font-semibold text-[color:var(--foreground)]">How Phoenix helps</p>
            <ul className="space-y-2 text-[color:var(--muted-foreground)]">
              <li>Uses live weather, flood, and emergency context in responses.</li>
              <li>Adapts tone to calm anxious or panicked moments.</li>
              <li>Can execute safety actions when risk is elevated.</li>
            </ul>
          </div>
        </aside>

        <section className="glass-panel rounded-3xl p-3 sm:p-4">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-3 px-2 pt-1 sm:px-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--accent)]">
                Live Conversation
              </p>
              <h2 className="mt-1 font-display text-3xl leading-none text-[color:var(--foreground)]">
                Transcript
              </h2>
            </div>
            <p className="max-w-xs text-right text-xs leading-relaxed text-[color:var(--muted-foreground)] sm:text-sm">
              For best guidance, share your city/state or ZIP early in the call.
            </p>
          </div>

          <ConversationPanel className="h-[560px] border-[color:var(--panel-border)] bg-black/18 lg:h-[700px]">
            <ConversationContent className="space-y-4 sm:space-y-5">
              {messages.length === 0 ? (
                <ConversationEmptyState
                  title="No transcript yet"
                  description="Start the call and Phoenix will display your live conversation here."
                />
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={cn(
                      "flex w-full items-end gap-2 sm:gap-3",
                      message.role === "user" ? "justify-end" : "justify-start"
                    )}
                  >
                    {message.role === "agent" ? (
                      <div className="h-8 w-8 shrink-0 rounded-full border border-[color:var(--panel-border)] bg-[radial-gradient(circle_at_30%_30%,_#ffe2b8,_#8cc5ff_58%,_#325376)] shadow-[0_8px_18px_rgba(6,10,18,0.35)]" />
                    ) : null}

                    <div
                      className={cn(
                        "max-w-[90%] rounded-3xl border px-4 py-3 shadow-[0_10px_26px_rgba(8,13,20,0.22)] sm:max-w-[78%] sm:px-6 sm:py-4",
                        {
                          "border-white/35 bg-[#f2f6fc] text-[#1a2738]": message.role === "user",
                          "border-[color:var(--panel-border)] bg-[#22344d] text-[#eef2f8]":
                            message.role === "agent",
                        }
                      )}
                    >
                      {message.role === "agent" ? (
                        <Response className="text-base leading-relaxed text-[#eef2f8] sm:text-lg [&_p]:m-0 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-6 [&_strong]:font-semibold">
                          {formatAgentMessageAsMarkdown(message.content)}
                        </Response>
                      ) : (
                        <p className="text-base leading-relaxed sm:text-lg">{message.content}</p>
                      )}
                    </div>
                  </div>
                ))
              )}
            </ConversationContent>
            <ConversationScrollButton />
          </ConversationPanel>
        </section>
      </div>
    </section>
  );
}
