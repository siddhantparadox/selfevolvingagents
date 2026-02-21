"use client";

import { Conversation, type Mode, type Status } from "@elevenlabs/client";
import { useEffect, useRef, useState } from "react";
import { Orb, type AgentState } from "@/components/ui/orb";
import { cn } from "@/lib/utils";

type VoiceAgentCardProps = {
  agentId?: string;
};

type UiState = "idle" | "listening" | "talking";

export function VoiceAgentCard({ agentId }: VoiceAgentCardProps) {
  const conversationRef = useRef<Conversation | null>(null);
  const [status, setStatus] = useState<Status>("disconnected");
  const [agentState, setAgentState] = useState<AgentState>(null);
  const [error, setError] = useState<string | null>(null);

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
    <section className="w-full max-w-3xl rounded-2xl border border-white/10 bg-[#0f1116] p-8 text-white shadow-[0_20px_80px_rgba(0,0,0,0.55)]">
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

      <div className="mt-8 flex items-center justify-center gap-4">
        {(["idle", "listening", "talking"] as UiState[]).map((state) => (
          <div
            key={state}
            className={cn(
              "rounded-xl border px-6 py-3 text-3xl font-medium capitalize transition-colors",
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
    </section>
  );
}
