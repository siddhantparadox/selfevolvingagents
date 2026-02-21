import { VoiceAgentCard } from "@/components/voice-agent-card";

export default function Home() {
  return (
    <main className="relative flex min-h-screen items-center justify-center px-4 py-10 sm:px-8">
      <div className="w-full max-w-[1280px] animate-rise">
        <VoiceAgentCard agentId={process.env.ELEVENLABS_AGENT_ID} />
      </div>
    </main>
  );
}
