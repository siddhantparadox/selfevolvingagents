import { VoiceAgentCard } from "@/components/voice-agent-card";

export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_#171b24,_#090b10_65%)] p-6">
      <VoiceAgentCard agentId={process.env.ELEVENLABS_AGENT_ID} />
    </main>
  );
}
