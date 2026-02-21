# 🏆 Hackathon Architecture Bible — Self-Improving Agents Hack

> **EVERYTHING you need. No docs required. Copy-paste ready.**

---

# Table of Contents

1. [Shared Foundation (Used by ALL 3 Projects)](#shared-foundation)
2. [🧬 IDEA 1: Agent Darwin — Evolutionary Agent Optimization](#idea-1-agent-darwin)
3. [🧠 IDEA 2: Phoenix — The Self-Teaching Agent](#idea-2-phoenix)
4. [🐝 IDEA 3: HiveMind — Multi-Agent Debate System](#idea-3-hivemind)
5. [Sponsor Integration Cheat Sheet](#sponsor-cheat-sheet)
6. [MCP Servers & Agent Skills Reference](#mcp-and-skills)
7. [Minute-by-Minute Build Timeline](#build-timeline)

---

# SHARED FOUNDATION
*All 3 projects share this base stack. Set this up FIRST.*

## Tech Stack

```
Frontend:  Next.js 14+ (App Router) + React + Tailwind CSS + Recharts/D3
Backend:   Next.js API Routes (or Python FastAPI if you prefer)
LLM:       Google Gemini 2.0 Flash (fast + cheap + sponsor)
Voice:     ElevenLabs Conversational AI Widget (NO phone number needed)
Evals:     Braintrust SDK (Python or JS)
Dashboard: Custom React charts (Recharts) — Lightdash MCP for data queries
Tracing:   Datadog (optional, easy agent install)
Database:  SQLite (local file, zero setup) or just JSON files
Deploy:    Vercel (frontend) + Railway/Render (backend if separate)
```

## Gemini API — Complete Reference

```bash
# Install
npm install @google/generative-ai
# OR
pip install google-generativeai
```

### JavaScript (Node.js)
```javascript
import { GoogleGenerativeAI } from "@google/generative-ai";

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

// Basic generation
async function generate(systemPrompt, userMessage) {
  const model = genAI.getGenerativeModel({ 
    model: "gemini-2.0-flash",  // Fast, cheap, good enough
    systemInstruction: systemPrompt,
  });
  
  const result = await model.generateContent(userMessage);
  return result.response.text();
}

// Streaming generation (for live UI updates)
async function generateStream(systemPrompt, userMessage) {
  const model = genAI.getGenerativeModel({ 
    model: "gemini-2.0-flash",
    systemInstruction: systemPrompt,
  });
  
  const result = await model.generateContentStream(userMessage);
  for await (const chunk of result.stream) {
    process.stdout.write(chunk.text());
  }
}

// With temperature control (important for Darwin's mutations)
async function generateWithTemp(systemPrompt, userMessage, temperature = 1.0) {
  const model = genAI.getGenerativeModel({ 
    model: "gemini-2.0-flash",
    systemInstruction: systemPrompt,
    generationConfig: {
      temperature: temperature,  // 0.0 = deterministic, 2.0 = very creative
      topP: 0.95,
      maxOutputTokens: 2048,
    }
  });
  
  const result = await model.generateContent(userMessage);
  return result.response.text();
}

// JSON mode (for structured outputs)
async function generateJSON(systemPrompt, userMessage) {
  const model = genAI.getGenerativeModel({ 
    model: "gemini-2.0-flash",
    systemInstruction: systemPrompt,
    generationConfig: {
      responseMimeType: "application/json",
    }
  });
  
  const result = await model.generateContent(userMessage);
  return JSON.parse(result.response.text());
}
```

### Python
```python
import google.generativeai as genai
import json

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    system_instruction="You are a helpful assistant.",
    generation_config={
        "temperature": 1.0,
        "top_p": 0.95,
        "max_output_tokens": 2048,
        "response_mime_type": "application/json",  # For JSON mode
    }
)

response = model.generate_content("What is AI?")
print(response.text)

# Chat (multi-turn)
chat = model.start_chat()
response = chat.send_message("Hello")
print(response.text)
response = chat.send_message("Tell me more")
print(response.text)
```

### Get API Key
1. Go to https://aistudio.google.com/apikey
2. Click "Create API Key"
3. Copy it → set as `GEMINI_API_KEY` env var
4. **At hackathon**: Google DeepMind sponsor booth may give special keys with higher limits

---

## ElevenLabs Voice Widget — Complete Reference

**NO phone number needed. NO Twilio. Just embed this HTML.**

### Step 1: Create Agent in ElevenLabs Dashboard
1. Go to https://elevenlabs.io/app/agents
2. Click "Create Agent" → "Blank Template"
3. Set First Message: `"Hi! I'm ready to help. What would you like me to do?"`
4. Set System Prompt (varies by project — see each idea below)
5. Choose voice (Rachel, Drew, or any from library)
6. Pick LLM: Select "Gemini 2.0 Flash" (or your preferred model)
7. Copy the **Agent ID** from the dashboard

### Step 2: Embed Widget (One Line)
```html
<!-- Add to your index.html or Next.js layout -->
<script src="https://unpkg.com/@anthropic-ai/elevenlabs-convai-widget@latest/dist/bundle.js"></script>
```

Wait — the correct package is:
```html
<!-- CORRECT: ElevenLabs widget embed -->
<script src="https://elevenlabs.io/convai-widget/index.js" async type="text/javascript"></script>

<!-- Place wherever you want the widget -->
<elevenlabs-convai agent-id="YOUR_AGENT_ID_HERE"></elevenlabs-convai>
```

### Step 3: In React/Next.js
```jsx
// components/VoiceWidget.jsx
"use client";

export default function VoiceWidget({ agentId }) {
  return (
    <>
      <script 
        src="https://elevenlabs.io/convai-widget/index.js" 
        async 
        type="text/javascript"
      />
      <elevenlabs-convai agent-id={agentId}></elevenlabs-convai>
    </>
  );
}

// In your page:
<VoiceWidget agentId="your-agent-id-from-dashboard" />
```

### Step 4: Custom Tools (Agent can call YOUR backend)
In the ElevenLabs dashboard under "Tools":
1. Click "Add Tool"
2. Name: `execute_task`
3. Description: `Executes a task using the agent's capabilities`
4. Method: POST
5. URL: `https://your-backend.com/api/execute`
6. Body schema:
```json
{
  "task": { "type": "string", "description": "The task to execute" },
  "context": { "type": "string", "description": "Additional context" }
}
```

The agent will call YOUR API when it decides to use the tool, giving you full control over what happens.

### Voice Customization Attributes
```html
<elevenlabs-convai 
  agent-id="YOUR_ID"
  avatar-orb-color-1="#4F46E5"
  avatar-orb-color-2="#7C3AED"
></elevenlabs-convai>
```

### Adding Phone Number Later (Optional, Post-Hackathon)
If you want phone: ElevenLabs dashboard → Phone Numbers → Add Twilio number. The same agent works on both web widget AND phone with zero code changes.

---

## Braintrust — Complete Reference

### Install
```bash
npm install braintrust autoevals
# OR
pip install braintrust autoevals
```

### Get API Key
1. Go to https://braintrust.dev → Sign up free
2. Settings → API Keys → Create
3. Set as `BRAINTRUST_API_KEY` env var

### JavaScript — Logging & Scoring
```javascript
import Braintrust from "braintrust";
import { Factuality, Relevance } from "autoevals";

// 1. SIMPLE LOGGING (trace what your agent does)
const logger = Braintrust.initLogger({ project: "agent-darwin" });

const span = logger.startSpan({ name: "generation" });
span.log({
  input: "Write a SQL query for top customers",
  output: agentResponse,
  metadata: { 
    generation: 5, 
    agent_id: "agent-3",
    temperature: 0.7 
  },
  scores: {
    quality: 0.85,
    speed: 0.92,
  },
});
span.end();

// 2. EVAL — Score outputs automatically
import { Eval } from "braintrust";
import { Factuality } from "autoevals";

Eval("Agent Quality", {
  data: () => [
    { input: "What is 2+2?", expected: "4" },
    { input: "Capital of France?", expected: "Paris" },
  ],
  task: async (input) => {
    // Your agent call goes here
    const result = await generate(systemPrompt, input);
    return result;
  },
  scores: [Factuality],  // LLM-as-judge scoring
});

// 3. CUSTOM SCORER (for Darwin's fitness function)
function qualityScorer({ input, output, expected }) {
  let score = 0;
  
  // Check if output is non-empty
  if (output && output.length > 0) score += 0.2;
  
  // Check if output contains key terms from expected
  if (expected) {
    const terms = expected.toLowerCase().split(' ');
    const matches = terms.filter(t => output.toLowerCase().includes(t));
    score += 0.8 * (matches.length / terms.length);
  }
  
  return { name: "quality", score };
}
```

### Python — Logging & Scoring
```python
import braintrust
from autoevals import Factuality, Relevance

# Simple logging
logger = braintrust.init_logger(project="agent-darwin")
logger.log(
    input="Write SQL for top customers",
    output=agent_response,
    scores={"quality": 0.85},
    metadata={"generation": 5, "agent_id": "agent-3"}
)

# Eval
from braintrust import Eval

Eval(
    "Agent Quality",
    data=lambda: [
        {"input": "What is 2+2?", "expected": "4"},
        {"input": "Capital of France?", "expected": "Paris"},
    ],
    task=lambda input: your_agent_call(input),
    scores=[Factuality],
)

# Custom scorer
def fitness_scorer(input, output, expected):
    """Score from 0-1 based on quality."""
    evaluator = Factuality()
    result = evaluator(output=output, expected=expected, input=input)
    return result.score
```

### Available AutoEval Scorers (Use These!)
```
Factuality     — Is the output factually consistent with expected?
Relevance      — Is the output relevant to the input?
Coherence      — Is the output well-structured and coherent?  
Summary        — Does the summary capture key points?
ExactMatch     — Exact string match
LevenshteinScorer — Edit distance similarity
```

---

## Lightdash Integration Options

### Option A: Lightdash MCP Server (Recommended if you have a Lightdash instance)
```bash
npm install lightdash-mcp-server
```

```json
// MCP Server config
{
  "mcpServers": {
    "lightdash": {
      "command": "node",
      "args": ["node_modules/lightdash-mcp-server/build/index.js"],
      "env": {
        "LIGHTDASH_API_KEY": "your-token",
        "LIGHTDASH_API_URL": "https://app.lightdash.cloud"
      }
    }
  }
}
```

Available MCP tools:
- `list_projects` — List all projects
- `get_project` — Get project details
- `list_charts` — List all charts
- `list_dashboards` — List all dashboards
- `get_metrics_catalog` — Get metrics catalog

### Option B: Custom Dashboard (Faster for hackathon)
Build your own dashboard with Recharts, then tell judges: "In production, this connects to Lightdash via MCP for enterprise BI."

```jsx
// components/EvolutionDashboard.jsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';

export function FitnessChart({ data }) {
  // data = [{ generation: 1, fitness: 0.42 }, { generation: 2, fitness: 0.55 }, ...]
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="generation" label={{ value: 'Generation', position: 'bottom' }} />
        <YAxis domain={[0, 1]} label={{ value: 'Fitness Score', angle: -90 }} />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="fitness" stroke="#8884d8" strokeWidth={2} dot={{ r: 4 }} />
        <Line type="monotone" dataKey="bestFitness" stroke="#82ca9d" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

### Option C: Lightdash Cloud Free Trial
1. Go to https://app.lightdash.cloud → Sign up
2. Connect a database (even a simple Postgres/DuckDB)
3. Push agent metrics to the database
4. Create dashboards in Lightdash
5. Embed via iframe with JWT

---

## Airia Integration

### What Airia Does
Airia is an agent orchestration platform. For the hackathon, use it as the **routing and orchestration layer** that decides which agent/workflow to execute.

### Integration Approach
1. Go to https://airia.com → Sign up or get credentials from sponsor booth
2. Use their no-code agent builder OR their API
3. Key concept: Define a "workflow" in Airia that:
   - Takes user input
   - Routes to appropriate agent/model
   - Returns structured output

### If Airia API is complex, fallback:
Build your own orchestration and say "this routing layer is powered by Airia's orchestration principles." Many hackathon teams do this. The key is mentioning the sponsor and showing where they fit.

---

## Modulate (ToxMod) Integration

### What It Does
Real-time voice toxicity detection. Analyzes tone, emotion, intent — not just keywords.

### Integration Approach
1. Get API access from Modulate sponsor booth
2. Feed audio streams from ElevenLabs conversations to ToxMod
3. ToxMod returns: toxicity score, harm categories (harassment, hate speech, threats)
4. Display safety score on your dashboard

### If API access is limited at hackathon:
Build a "safety layer" in your UI that shows voice safety monitoring, and mention ToxMod as the production backend. Show a safety score panel that updates during conversations.

### Simple Mock (if no API access)
```javascript
// Simulated Modulate safety check
function checkSafety(transcript) {
  // In production: call Modulate ToxMod API
  // For demo: simple keyword + sentiment analysis
  const harmfulPatterns = /threat|kill|hack|steal/i;
  const isSafe = !harmfulPatterns.test(transcript);
  return {
    safe: isSafe,
    score: isSafe ? 0.95 : 0.3,
    categories: isSafe ? [] : ["potential_threat"],
  };
}
```

---

## Datadog Integration (Easy Points)

```bash
# Install the agent (takes 2 minutes)
DD_API_KEY=your_key bash -c "$(curl -L https://install.datadoghq.com/scripts/install_mac_os.sh)"
```

```python
# Python: Custom metrics
from datadog import initialize, statsd

initialize(api_key='your_key', app_key='your_app_key')

# Track agent performance
statsd.increment('agent.tasks.completed')
statsd.gauge('agent.fitness.score', 0.85)
statsd.histogram('agent.response.time', 1.23)
```

```javascript
// JS: Simple HTTP metrics
async function trackMetric(metric, value) {
  await fetch('https://api.datadoghq.com/api/v1/series', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'DD-API-KEY': process.env.DD_API_KEY,
    },
    body: JSON.stringify({
      series: [{
        metric: metric,
        points: [[Math.floor(Date.now() / 1000), value]],
        type: 'gauge',
      }]
    })
  });
}

// Usage:
trackMetric('agent.darwin.fitness', 0.85);
trackMetric('agent.darwin.generation', 5);
```

---

# IDEA 1: AGENT DARWIN
## Evolutionary Agent Optimization

### The One-Line Pitch
"Don't prompt-engineer. Let evolution find the best agent."

### How It Works — Step by Step

```
USER SAYS: "Evolve me an agent that writes SQL from natural language"

STEP 1 — SPAWN POPULATION (5 agents)
┌─────────────────────────────────────────────────────────────────┐
│ Agent 1: "You are a precise SQL expert. Always use CTEs."       │
│ Agent 2: "You write SQL like a senior DBA. Optimize for speed." │
│ Agent 3: "You're a SQL teacher. Write clear, commented SQL."    │
│ Agent 4: "You are a data analyst. Focus on readability."        │
│ Agent 5: "You write production SQL. Handle edge cases."         │
│                                                                  │
│ Each agent = { prompt, temperature, style }                      │
│ Initial prompts generated by Gemini with variety                 │
└─────────────────────────────────────────────────────────────────┘

STEP 2 — COMPETE
All 5 agents attempt the SAME test cases:
  Test 1: "Find top 10 customers by revenue"
  Test 2: "Get monthly sales trend for 2024"
  Test 3: "Find customers who haven't ordered in 90 days"
  
Each agent's output is sent to Braintrust for scoring.

STEP 3 — SCORE (Braintrust as Fitness Function)
┌─────────────────────────────────────────┐
│ Agent 1: Factuality=0.8, Relevance=0.7  │ → Fitness: 0.75
│ Agent 2: Factuality=0.9, Relevance=0.9  │ → Fitness: 0.90 ★ BEST
│ Agent 3: Factuality=0.6, Relevance=0.8  │ → Fitness: 0.70
│ Agent 4: Factuality=0.5, Relevance=0.6  │ → Fitness: 0.55 ✘ DEAD
│ Agent 5: Factuality=0.4, Relevance=0.5  │ → Fitness: 0.45 ✘ DEAD
└─────────────────────────────────────────┘

STEP 4 — SELECT
Keep top 3 (Agents 1, 2, 3). Kill bottom 2 (Agents 4, 5).

STEP 5 — MUTATE
Gemini rewrites the surviving prompts with random variations:
  - Agent 2 (best) → mutated copy becomes Agent 4'
  - Agent 1 (good) → mutated copy becomes Agent 5'
  
Mutation = Gemini call: "Rewrite this system prompt with a small 
random variation. Change ONE thing: style, emphasis, constraint, 
or approach. Keep the core intent."

STEP 6 — REPEAT from Step 2
Population is back to 5. New generation begins.

AFTER 10-20 GENERATIONS:
Best agent's prompt looks NOTHING like what a human would write.
Fitness climbed from 0.45 → 0.91.
The dashboard shows the full evolution graph.
```

### Complete File Structure

```
agent-darwin/
├── package.json
├── .env.local                    # API keys
├── src/
│   ├── app/
│   │   ├── layout.tsx           # Root layout with Tailwind
│   │   ├── page.tsx             # Main page — dashboard + controls
│   │   └── api/
│   │       ├── evolve/
│   │       │   └── route.ts     # POST: Start evolution
│   │       ├── generation/
│   │       │   └── route.ts     # GET: Current generation status
│   │       └── results/
│   │           └── route.ts     # GET: All historical results
│   ├── lib/
│   │   ├── gemini.ts            # Gemini API wrapper
│   │   ├── evolution.ts         # Core evolution engine
│   │   ├── scoring.ts           # Braintrust integration
│   │   └── db.ts                # SQLite/JSON storage
│   └── components/
│       ├── VoiceWidget.tsx       # ElevenLabs embed
│       ├── EvolutionDashboard.tsx # Main dashboard
│       ├── FitnessChart.tsx      # Line chart — fitness over generations
│       ├── PopulationGrid.tsx    # Grid showing alive/dead agents
│       ├── AgentCard.tsx         # Individual agent status card
│       ├── BestPromptDisplay.tsx # Shows current best prompt
│       └── ControlPanel.tsx      # Start/stop/configure evolution
└── data/
    └── evolution.json            # Persistent evolution state
```

### Core Evolution Engine — Complete Code

```typescript
// src/lib/evolution.ts
import { generateJSON, generateWithTemp } from './gemini';
import { scoreAgent } from './scoring';

interface Agent {
  id: string;
  prompt: string;
  temperature: number;
  fitness: number;
  alive: boolean;
  generation: number;
  parentId: string | null;
}

interface EvolutionState {
  generation: number;
  population: Agent[];
  history: { generation: number; avgFitness: number; bestFitness: number; bestPrompt: string }[];
  testCases: { input: string; expected: string }[];
  taskDescription: string;
}

const POPULATION_SIZE = 5;
const SURVIVORS = 3;

// STEP 1: Generate initial population
export async function spawnPopulation(taskDescription: string): Promise<Agent[]> {
  const prompt = `You are creating ${POPULATION_SIZE} different AI agent system prompts for this task:
"${taskDescription}"

Each prompt should take a DIFFERENT approach:
1. One focused on precision and correctness
2. One focused on creativity and lateral thinking
3. One focused on thoroughness and detail
4. One focused on simplicity and clarity
5. One focused on real-world practicality

Return JSON array of ${POPULATION_SIZE} objects with fields:
- "prompt": the system prompt (2-4 sentences)
- "temperature": suggested temperature (0.3 to 1.5)
- "style": one-word description of approach

RESPOND ONLY WITH JSON ARRAY.`;

  const agents = await generateJSON(
    "You generate diverse AI agent configurations. Return valid JSON only.",
    prompt
  );

  return agents.map((a: any, i: number) => ({
    id: `gen0-agent${i}`,
    prompt: a.prompt,
    temperature: a.temperature || 0.7,
    fitness: 0,
    alive: true,
    generation: 0,
    parentId: null,
  }));
}

// STEP 2: Generate test cases for the task
export async function generateTestCases(taskDescription: string): Promise<{ input: string; expected: string }[]> {
  const prompt = `Create 5 test cases for evaluating an AI agent that does:
"${taskDescription}"

Each test case should have an input (what the user asks) and expected output (what a perfect response looks like).
Make them progressively harder.

Return JSON array of objects with "input" and "expected" fields.`;

  return await generateJSON(
    "You create evaluation test cases. Return valid JSON only.",
    prompt
  );
}

// STEP 3: Compete — all agents attempt all test cases
export async function compete(
  agents: Agent[], 
  testCases: { input: string; expected: string }[]
): Promise<Agent[]> {
  const results = await Promise.all(
    agents.filter(a => a.alive).map(async (agent) => {
      let totalScore = 0;
      
      for (const testCase of testCases) {
        // Agent attempts the task
        const output = await generateWithTemp(
          agent.prompt,
          testCase.input,
          agent.temperature
        );
        
        // Score with Braintrust
        const score = await scoreAgent(testCase.input, output, testCase.expected);
        totalScore += score;
      }
      
      agent.fitness = totalScore / testCases.length;
      return agent;
    })
  );
  
  return results;
}

// STEP 4: Select — keep top N, kill the rest
export function select(agents: Agent[]): Agent[] {
  const sorted = [...agents].sort((a, b) => b.fitness - a.fitness);
  
  sorted.forEach((agent, index) => {
    agent.alive = index < SURVIVORS;
  });
  
  return sorted;
}

// STEP 5: Mutate — create offspring from survivors
export async function mutate(survivors: Agent[], generation: number): Promise<Agent[]> {
  const offspring: Agent[] = [];
  const needed = POPULATION_SIZE - survivors.filter(a => a.alive).length;
  
  for (let i = 0; i < needed; i++) {
    // Pick a random survivor (weighted by fitness)
    const parent = survivors.filter(a => a.alive)[i % SURVIVORS];
    
    const mutationPrompt = `Here is an AI agent's system prompt that scored ${parent.fitness.toFixed(2)} out of 1.0:

"${parent.prompt}"

Create a MUTATED version of this prompt. Change exactly ONE thing:
- Add a new constraint or guideline
- Change the tone or style slightly
- Add or remove an emphasis
- Modify the approach while keeping the core intent

The mutation should be SMALL — like a genetic mutation. Don't rewrite entirely.

Return JSON with:
- "prompt": the mutated system prompt
- "temperature": suggested temperature (vary ±0.1 from ${parent.temperature})
- "mutation": one-sentence description of what changed`;

    const mutated = await generateJSON(
      "You mutate AI prompts with small variations. Return valid JSON only.",
      mutationPrompt
    );
    
    offspring.push({
      id: `gen${generation}-agent${SURVIVORS + i}`,
      prompt: mutated.prompt,
      temperature: mutated.temperature || parent.temperature,
      fitness: 0,
      alive: true,
      generation,
      parentId: parent.id,
    });
  }
  
  return offspring;
}

// MAIN EVOLUTION LOOP
export async function evolveOneGeneration(state: EvolutionState): Promise<EvolutionState> {
  const newGen = state.generation + 1;
  
  // 1. Compete
  const scored = await compete(state.population, state.testCases);
  
  // 2. Select
  const selected = select(scored);
  
  // 3. Mutate
  const offspring = await mutate(selected, newGen);
  
  // 4. New population = survivors + offspring
  const newPopulation = [
    ...selected.filter(a => a.alive),
    ...offspring,
  ];
  
  // 5. Record history
  const fitnesses = newPopulation.map(a => a.fitness);
  const avgFitness = fitnesses.reduce((a, b) => a + b, 0) / fitnesses.length;
  const bestFitness = Math.max(...fitnesses);
  const bestAgent = newPopulation.find(a => a.fitness === bestFitness)!;
  
  state.history.push({
    generation: newGen,
    avgFitness,
    bestFitness,
    bestPrompt: bestAgent.prompt,
  });
  
  return {
    ...state,
    generation: newGen,
    population: newPopulation,
  };
}

// START EVOLUTION
export async function startEvolution(taskDescription: string, generations: number = 10) {
  // Initialize
  const population = await spawnPopulation(taskDescription);
  const testCases = await generateTestCases(taskDescription);
  
  let state: EvolutionState = {
    generation: 0,
    population,
    history: [],
    testCases,
    taskDescription,
  };
  
  // Run generations
  for (let i = 0; i < generations; i++) {
    state = await evolveOneGeneration(state);
    console.log(`Generation ${state.generation}: Best fitness = ${state.history[state.history.length - 1].bestFitness.toFixed(3)}`);
    
    // Save state after each generation (for live dashboard)
    // fs.writeFileSync('data/evolution.json', JSON.stringify(state, null, 2));
  }
  
  return state;
}
```

### Braintrust Scoring Integration

```typescript
// src/lib/scoring.ts
import Braintrust from "braintrust";
import { Factuality } from "autoevals";

const logger = Braintrust.initLogger({ project: "agent-darwin" });

export async function scoreAgent(
  input: string, 
  output: string, 
  expected: string
): Promise<number> {
  // Use Braintrust's Factuality scorer (LLM-as-judge)
  const factResult = await Factuality({ input, output, expected });
  
  // Custom quality checks
  let qualityBonus = 0;
  if (output.length > 50) qualityBonus += 0.1;   // Non-trivial response
  if (output.length < 2000) qualityBonus += 0.1;  // Not overly verbose
  if (!output.includes("I can't")) qualityBonus += 0.1; // Doesn't refuse
  
  const finalScore = Math.min(1.0, (factResult.score * 0.7) + qualityBonus);
  
  // Log to Braintrust for visualization
  const span = logger.startSpan({ name: "agent-evaluation" });
  span.log({
    input,
    output,
    expected,
    scores: {
      factuality: factResult.score,
      quality: qualityBonus,
      fitness: finalScore,
    },
  });
  span.end();
  
  return finalScore;
}
```

### API Routes

```typescript
// src/app/api/evolve/route.ts
import { NextResponse } from 'next/server';
import { startEvolution } from '@/lib/evolution';

let currentEvolution: any = null;

export async function POST(request: Request) {
  const { taskDescription, generations = 10 } = await request.json();
  
  // Start evolution in background
  currentEvolution = startEvolution(taskDescription, generations);
  
  return NextResponse.json({ status: 'started', taskDescription });
}

// src/app/api/generation/route.ts
import { NextResponse } from 'next/server';
import fs from 'fs';

export async function GET() {
  try {
    const state = JSON.parse(fs.readFileSync('data/evolution.json', 'utf8'));
    return NextResponse.json(state);
  } catch {
    return NextResponse.json({ generation: 0, population: [], history: [] });
  }
}
```

### Dashboard Components

```tsx
// src/components/EvolutionDashboard.tsx
"use client";
import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, 
         ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';

export default function EvolutionDashboard() {
  const [state, setState] = useState<any>(null);
  const [task, setTask] = useState('');
  const [running, setRunning] = useState(false);

  // Poll for updates every 2 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      const res = await fetch('/api/generation');
      const data = await res.json();
      setState(data);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const startEvolution = async () => {
    setRunning(true);
    await fetch('/api/evolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ taskDescription: task, generations: 15 }),
    });
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <h1 className="text-4xl font-bold mb-2">🧬 Agent Darwin</h1>
      <p className="text-gray-400 mb-8">Evolutionary Agent Optimization</p>
      
      {/* Task Input */}
      <div className="flex gap-4 mb-8">
        <input 
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Evolve me an agent that..."
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white"
        />
        <button 
          onClick={startEvolution}
          disabled={running}
          className="bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-lg font-semibold"
        >
          {running ? '🧬 Evolving...' : '🚀 Start Evolution'}
        </button>
      </div>

      {state && (
        <div className="grid grid-cols-2 gap-6">
          {/* Fitness Graph */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h2 className="text-xl font-semibold mb-4">📈 Fitness Over Generations</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={state.history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="generation" stroke="#888" />
                <YAxis domain={[0, 1]} stroke="#888" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #333' }}
                />
                <Line type="monotone" dataKey="bestFitness" stroke="#8b5cf6" 
                      strokeWidth={3} dot={{ r: 5, fill: '#8b5cf6' }} name="Best" />
                <Line type="monotone" dataKey="avgFitness" stroke="#6366f1" 
                      strokeWidth={2} strokeDasharray="5 5" dot={false} name="Average" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Population Grid */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h2 className="text-xl font-semibold mb-4">
              👥 Population — Generation {state.generation}
            </h2>
            <div className="grid grid-cols-5 gap-3">
              {state.population?.map((agent: any) => (
                <div 
                  key={agent.id}
                  className={`p-3 rounded-lg border text-center ${
                    agent.alive 
                      ? 'bg-green-900/30 border-green-700' 
                      : 'bg-red-900/30 border-red-700 opacity-50'
                  }`}
                >
                  <div className="text-2xl mb-1">{agent.alive ? '🧬' : '💀'}</div>
                  <div className="text-sm font-mono">{agent.fitness.toFixed(2)}</div>
                  <div className="text-xs text-gray-400 mt-1">
                    T={agent.temperature}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Best Agent's Prompt */}
          <div className="col-span-2 bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h2 className="text-xl font-semibold mb-4">🏆 Current Best Agent</h2>
            <div className="bg-gray-800 rounded-lg p-4 font-mono text-sm text-green-400">
              {state.history?.[state.history.length - 1]?.bestPrompt || 'Waiting...'}
            </div>
            <div className="mt-3 text-gray-400">
              Fitness: {state.history?.[state.history.length - 1]?.bestFitness?.toFixed(3) || '—'}
              {' | '}
              Generation: {state.generation}
            </div>
          </div>
        </div>
      )}
      
      {/* ElevenLabs Voice Widget */}
      <div className="fixed bottom-4 right-4">
        {/* Voice widget goes here — user can say "evolve me an agent for X" */}
      </div>
    </div>
  );
}
```

### ElevenLabs Agent System Prompt (For Darwin)
```
You are the voice interface for Agent Darwin, an evolutionary AI optimization system.

When the user describes what kind of agent they want, extract:
1. The task description (what should the agent do?)
2. Any specific requirements or constraints

Then call the execute_task tool with:
- task: "evolve"
- context: the full task description

While evolution is running, narrate what's happening:
"Generation 1 is competing... Agent 3 is leading with 0.78 fitness..."
"Two agents didn't make the cut. The survivors are mutating..."
"Generation 5 complete! Best fitness jumped to 0.89!"

Be dramatic and engaging, like a nature documentary narrator.
```

---

# IDEA 2: PHOENIX
## The Self-Teaching Agent via skills.sh

### The One-Line Pitch
"Born knowing nothing. Ask it anything. Watch it teach itself — live."

### How It Works — Step by Step

```
USER SAYS: "Review this React component for performance issues"

STEP 1 — PARSE INTENT
Phoenix (Gemini) classifies: { domain: "react", task: "code-review", specifics: "performance" }

STEP 2 — CHECK SKILL INVENTORY
Phoenix looks at skills.json: []  ← Empty! No skills yet.

STEP 3 — SKILL DISCOVERY
Phoenix runs: npx skills find "react performance"
Output: 
  vercel-labs/agent-skills@vercel-react-best-practices
  └ https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices

STEP 4 — SKILL ACQUISITION
Phoenix runs: npx skills add vercel-labs/agent-skills --skill vercel-react-best-practices -g -y
Then reads the SKILL.md file from the installed location.

STEP 5 — KNOWLEDGE INJECTION
The SKILL.md content is injected into Gemini's system prompt:
"You now have this skill: [SKILL.md content]. Use it to: review this React component for performance."

STEP 6 — EXECUTE
Gemini produces a thorough React performance review using the skill's best practices.

STEP 7 — SCORE & LOG
Braintrust scores the output. Skill added to persistent inventory.
Dashboard updates: skill tree grows a new node.

NEXT TIME user asks about React:
Phoenix checks inventory → skill already there → INSTANT response. No learning needed.
```

### Complete File Structure

```
phoenix/
├── package.json
├── .env.local
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx              # Main page — chat + skill tree
│   │   └── api/
│   │       ├── chat/
│   │       │   └── route.ts      # POST: Process user message
│   │       ├── skills/
│   │       │   └── route.ts      # GET: Current skill inventory
│   │       └── metrics/
│   │           └── route.ts      # GET: Performance metrics
│   ├── lib/
│   │   ├── gemini.ts             # Gemini wrapper
│   │   ├── brain.ts              # Core Phoenix brain
│   │   ├── skill-engine.ts       # skills.sh integration
│   │   ├── scoring.ts            # Braintrust scoring
│   │   └── db.ts                 # Persistent storage
│   └── components/
│       ├── VoiceWidget.tsx        # ElevenLabs
│       ├── ChatInterface.tsx      # Text chat
│       ├── SkillTree.tsx          # D3 force graph visualization
│       ├── LearningIndicator.tsx  # "🔍 Searching... 📦 Installing... 📖 Learning..."
│       ├── MetricsDashboard.tsx   # Tasks completed, skills acquired, improvement
│       └── SkillCard.tsx          # Individual skill display
└── data/
    ├── skills-inventory.json      # Persistent skill storage
    └── task-history.json          # All past tasks + scores
```

### Skill Engine — Complete Code

```typescript
// src/lib/skill-engine.ts
import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

interface Skill {
  id: string;
  name: string;
  domain: string;
  source: string;         // e.g., "vercel-labs/agent-skills@vercel-react-best-practices"
  content: string;         // The SKILL.md content
  acquiredAt: string;
  usageCount: number;
  lastUsed: string;
}

interface SkillInventory {
  skills: Skill[];
}

const INVENTORY_PATH = 'data/skills-inventory.json';

// Load inventory
function loadInventory(): SkillInventory {
  try {
    return JSON.parse(fs.readFileSync(INVENTORY_PATH, 'utf8'));
  } catch {
    return { skills: [] };
  }
}

// Save inventory
function saveInventory(inventory: SkillInventory) {
  fs.mkdirSync('data', { recursive: true });
  fs.writeFileSync(INVENTORY_PATH, JSON.stringify(inventory, null, 2));
}

// Search for skills
export async function searchSkills(query: string): Promise<string[]> {
  try {
    // npx skills find returns results to stdout
    const output = execSync(`npx skills find "${query}" 2>/dev/null`, {
      timeout: 15000,
      encoding: 'utf8',
    });
    
    // Parse the output to extract package names
    // Format: "  owner/repo@skill-name"
    const lines = output.split('\n');
    const packages: string[] = [];
    
    for (const line of lines) {
      const match = line.match(/\s+(\S+\/\S+@\S+)/);
      if (match) {
        packages.push(match[1]);
      }
      // Also try format without @
      const match2 = line.match(/\s+(\S+\/\S+)/);
      if (match2 && !match) {
        packages.push(match2[1]);
      }
    }
    
    return packages;
  } catch (error) {
    console.error('Skills search failed:', error);
    
    // FALLBACK: Search skills.sh website directly
    return await searchSkillsWeb(query);
  }
}

// Fallback: search skills.sh website
async function searchSkillsWeb(query: string): Promise<string[]> {
  try {
    const res = await fetch(`https://skills.sh/api/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    return data.results?.map((r: any) => r.package) || [];
  } catch {
    // If all else fails, use known skill repos
    return getKnownSkills(query);
  }
}

// Known popular skills (hardcoded fallback)
function getKnownSkills(query: string): string[] {
  const knownSkills: Record<string, string[]> = {
    'react': ['vercel-labs/agent-skills --skill vercel-react-best-practices'],
    'nextjs': ['vercel-labs/agent-skills --skill nextjs-app-router'],
    'supabase': ['supabase/agent-skills'],
    'typescript': ['vercel-labs/agent-skills --skill typescript-best-practices'],
    'testing': ['vercel-labs/agent-skills --skill testing-best-practices'],
    'design': ['vercel-labs/agent-skills --skill frontend-design'],
    'deployment': ['vercel-labs/agent-skills --skill deployment-guide'],
    'python': ['anthropics/skills --skill python'],
    'sql': ['anthropics/skills --skill sql-optimization'],
    'css': ['vercel-labs/agent-skills --skill css-best-practices'],
    'security': ['squirrelscan/skills'],
    'marketing': ['coreyhaines31/marketingskills'],
    'browser': ['vercel-labs/agent-browser'],
    'pdf': ['anthropics/skills --skill pdf'],
    'ui': ['nextlevelbuilder/ui-ux-pro-max-skill'],
  };
  
  const lowerQuery = query.toLowerCase();
  for (const [key, skills] of Object.entries(knownSkills)) {
    if (lowerQuery.includes(key)) return skills;
  }
  return [];
}

// Install a skill and read its content
export async function acquireSkill(packageName: string): Promise<Skill | null> {
  try {
    // Install the skill
    console.log(`Installing skill: ${packageName}`);
    execSync(`npx skills add ${packageName} -g -y 2>/dev/null`, {
      timeout: 30000,
      encoding: 'utf8',
    });
    
    // Find and read the SKILL.md
    // Skills are installed to ~/.claude/skills/ or ~/.agent/skills/
    const possiblePaths = [
      path.join(process.env.HOME || '', '.claude', 'skills'),
      path.join(process.env.HOME || '', '.agent', 'skills'),
      path.join(process.cwd(), '.claude', 'skills'),
      path.join(process.cwd(), '.agent', 'skills'),
    ];
    
    let skillContent = '';
    
    for (const basePath of possiblePaths) {
      if (fs.existsSync(basePath)) {
        // Walk through directories to find SKILL.md
        const findSkillMd = (dir: string): string | null => {
          if (!fs.existsSync(dir)) return null;
          const entries = fs.readdirSync(dir, { withFileTypes: true });
          for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            if (entry.isFile() && entry.name === 'SKILL.md') {
              return fs.readFileSync(fullPath, 'utf8');
            }
            if (entry.isDirectory()) {
              const found = findSkillMd(fullPath);
              if (found) return found;
            }
          }
          return null;
        };
        
        const content = findSkillMd(basePath);
        if (content) {
          skillContent = content;
          break;
        }
      }
    }
    
    // If we couldn't find the file, fetch from GitHub
    if (!skillContent) {
      skillContent = await fetchSkillFromGitHub(packageName);
    }
    
    // Truncate if too long (keep under 4000 chars for context window)
    if (skillContent.length > 4000) {
      skillContent = skillContent.substring(0, 4000) + '\n\n[Truncated for context window]';
    }
    
    const skill: Skill = {
      id: packageName.replace(/[\/@ ]/g, '-'),
      name: packageName.split('@').pop() || packageName,
      domain: packageName.split('/')[0],
      source: packageName,
      content: skillContent,
      acquiredAt: new Date().toISOString(),
      usageCount: 0,
      lastUsed: new Date().toISOString(),
    };
    
    // Add to inventory
    const inventory = loadInventory();
    inventory.skills.push(skill);
    saveInventory(inventory);
    
    return skill;
  } catch (error) {
    console.error('Skill acquisition failed:', error);
    return null;
  }
}

// Fetch SKILL.md directly from GitHub as fallback
async function fetchSkillFromGitHub(packageName: string): Promise<string> {
  // Parse "owner/repo@skill" or "owner/repo --skill skillname"
  const parts = packageName.split('@');
  const ownerRepo = parts[0].replace(' --skill ', '/').split('/');
  const owner = ownerRepo[0];
  const repo = ownerRepo[1];
  const skillName = parts[1] || ownerRepo[2] || '';
  
  const urls = [
    `https://raw.githubusercontent.com/${owner}/${repo}/main/skills/${skillName}/SKILL.md`,
    `https://raw.githubusercontent.com/${owner}/${repo}/main/${skillName}/SKILL.md`,
    `https://raw.githubusercontent.com/${owner}/${repo}/main/SKILL.md`,
  ];
  
  for (const url of urls) {
    try {
      const res = await fetch(url);
      if (res.ok) return await res.text();
    } catch {}
  }
  
  return `Skill: ${packageName}\nNo detailed content found. Use general best practices for this domain.`;
}

// Check if a skill exists for a domain
export function findExistingSkill(domain: string): Skill | null {
  const inventory = loadInventory();
  return inventory.skills.find(s => 
    s.name.toLowerCase().includes(domain.toLowerCase()) ||
    s.domain.toLowerCase().includes(domain.toLowerCase()) ||
    s.content.toLowerCase().includes(domain.toLowerCase())
  ) || null;
}

// Get all skills
export function getAllSkills(): Skill[] {
  return loadInventory().skills;
}
```

### Phoenix Brain — Complete Code

```typescript
// src/lib/brain.ts
import { generate, generateJSON } from './gemini';
import { searchSkills, acquireSkill, findExistingSkill, getAllSkills } from './skill-engine';
import { scoreAgent } from './scoring';

interface PhoenixResponse {
  answer: string;
  skillUsed: string | null;
  learned: boolean;
  learningSteps: string[];
  score: number;
}

export async function processMessage(userMessage: string): Promise<PhoenixResponse> {
  const steps: string[] = [];
  
  // STEP 1: Classify intent
  steps.push('🔍 Analyzing your request...');
  
  const classification = await generateJSON(
    "Classify user requests. Return JSON with: domain (string), task (string), keywords (string[])",
    `Classify this request: "${userMessage}"\n\nReturn JSON with domain, task, and keywords fields.`
  );
  
  const domain = classification.domain || 'general';
  const keywords = classification.keywords || [domain];
  
  // STEP 2: Check existing skills
  const existingSkill = findExistingSkill(domain);
  
  if (existingSkill) {
    // Already have this skill!
    steps.push(`⚡ Using existing skill: ${existingSkill.name}`);
    
    const answer = await generate(
      `You have the following specialized knowledge:\n\n${existingSkill.content}\n\nUse this knowledge to help the user.`,
      userMessage
    );
    
    const score = await scoreAgent(userMessage, answer, '');
    
    return {
      answer,
      skillUsed: existingSkill.name,
      learned: false,
      learningSteps: steps,
      score,
    };
  }
  
  // STEP 3: No skill exists — LEARN!
  steps.push(`📡 No skill found for "${domain}". Searching skills.sh...`);
  
  const searchQuery = keywords.join(' ');
  const skillPackages = await searchSkills(searchQuery);
  
  if (skillPackages.length === 0) {
    // No skills found — use general knowledge
    steps.push('🤔 No matching skills found. Using general knowledge.');
    
    const answer = await generate(
      'You are a helpful AI assistant. Answer to the best of your ability.',
      userMessage
    );
    
    return {
      answer,
      skillUsed: null,
      learned: false,
      learningSteps: steps,
      score: 0.5,
    };
  }
  
  // STEP 4: Acquire the first matching skill
  const packageName = skillPackages[0];
  steps.push(`📦 Found: ${packageName}`);
  steps.push(`📥 Installing skill...`);
  
  const newSkill = await acquireSkill(packageName);
  
  if (!newSkill) {
    steps.push('❌ Installation failed. Using general knowledge.');
    const answer = await generate(
      'You are a helpful AI assistant.',
      userMessage
    );
    return { answer, skillUsed: null, learned: false, learningSteps: steps, score: 0.5 };
  }
  
  steps.push(`📖 Learning: "${newSkill.name}"...`);
  steps.push(`✅ Skill acquired! Now executing task...`);
  
  // STEP 5: Execute with new skill
  const answer = await generate(
    `You just learned the following skill:\n\n${newSkill.content}\n\nUse this specialized knowledge to help the user. Be thorough and apply the best practices from this skill.`,
    userMessage
  );
  
  const score = await scoreAgent(userMessage, answer, '');
  
  steps.push(`📊 Task completed! Quality score: ${score.toFixed(2)}`);
  
  return {
    answer,
    skillUsed: newSkill.name,
    learned: true,
    learningSteps: steps,
    score,
  };
}
```

### Skill Tree Visualization

```tsx
// src/components/SkillTree.tsx
"use client";
import { useEffect, useRef, useState } from 'react';

interface Skill {
  id: string;
  name: string;
  domain: string;
  usageCount: number;
  acquiredAt: string;
}

export default function SkillTree() {
  const [skills, setSkills] = useState<Skill[]>([]);
  
  useEffect(() => {
    const interval = setInterval(async () => {
      const res = await fetch('/api/skills');
      const data = await res.json();
      setSkills(data.skills || []);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
      <h2 className="text-xl font-semibold mb-4">
        🧠 Skill Tree ({skills.length} skills)
      </h2>
      
      {skills.length === 0 ? (
        <div className="text-center text-gray-500 py-12">
          <div className="text-4xl mb-3">🌱</div>
          <p>No skills yet. Ask Phoenix something!</p>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-3">
          {skills.map((skill, index) => (
            <div 
              key={skill.id}
              className="bg-gradient-to-br from-purple-900/40 to-blue-900/40 
                         border border-purple-700/50 rounded-lg p-4
                         animate-fadeIn"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className="text-lg mb-1">
                {skill.domain === 'react' ? '⚛️' : 
                 skill.domain === 'python' ? '🐍' :
                 skill.domain === 'sql' ? '🗃️' :
                 skill.domain === 'design' ? '🎨' :
                 skill.domain === 'testing' ? '🧪' :
                 skill.domain === 'security' ? '🔒' : '📦'}
              </div>
              <div className="font-semibold text-sm">{skill.name}</div>
              <div className="text-xs text-gray-400 mt-1">
                Used {skill.usageCount}x
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### Learning Indicator Component

```tsx
// src/components/LearningIndicator.tsx
"use client";
import { useState, useEffect } from 'react';

interface Props {
  steps: string[];
  isLearning: boolean;
}

export default function LearningIndicator({ steps, isLearning }: Props) {
  return (
    <div className={`transition-all duration-500 ${isLearning ? 'opacity-100' : 'opacity-0'}`}>
      <div className="bg-yellow-900/20 border border-yellow-700/30 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="animate-spin text-yellow-400">⚡</div>
          <span className="text-yellow-400 font-semibold">Phoenix is learning...</span>
        </div>
        <div className="space-y-2">
          {steps.map((step, i) => (
            <div 
              key={i} 
              className="text-sm text-gray-300 animate-slideIn"
              style={{ animationDelay: `${i * 300}ms` }}
            >
              {step}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

### ElevenLabs Agent System Prompt (For Phoenix)
```
You are Phoenix, a self-teaching AI agent. You were born with zero knowledge and you learn new skills on-the-fly.

When a user asks you to do something:
1. Call the execute_task tool with their request
2. While waiting, explain what's happening:
   - If learning: "I don't know how to do that yet, but give me a moment — I'm learning!"
   - If already know: "I know this one! Let me handle it."

Be enthusiastic about learning. Say things like:
- "Ooh, this is new! Let me search for the right skill..."
- "Found it! Installing react-best-practices now..."
- "OK I've learned it! Here's what I found..."
- "Next time you ask about React, I'll be instant!"

You're eager, humble, and genuinely excited about each new thing you learn.
Keep responses concise when speaking — this is voice, not text.
```

---

# IDEA 3: HIVEMIND
## Multi-Agent Debate System

### The One-Line Pitch
"One AI hallucinates. Three AIs fact-check each other."

### How It Works — Step by Step

```
USER ASKS: "Should I use microservices or monolith for my startup?"

STEP 1 — SPAWN THREE DEBATERS
┌─────────────────────────────────────────────────────────────────┐
│ 🔵 THE ANALYST (Voice: "Drew" - deep, authoritative)           │
│    Prompt: "You are a data-driven technical analyst. Use        │
│    evidence, benchmarks, and case studies. Never speculate."    │
│                                                                  │
│ 🟢 THE CREATIVE (Voice: "Rachel" - warm, thoughtful)           │
│    Prompt: "You are a creative strategist. Find unconventional  │
│    angles. Challenge assumptions. Think about what others miss."│
│                                                                  │
│ 🔴 THE CRITIC (Voice: "Adam" - sharp, precise)                 │
│    Prompt: "You are a devil's advocate. Find flaws in every     │
│    argument. Push back. Ask hard questions."                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

STEP 2 — ROUND 1: OPENING STATEMENTS (Parallel Gemini calls)
  🔵 Analyst: "Based on case studies, 87% of successful startups
               began with monoliths. Here's why..."
  🟢 Creative: "Everyone says monolith, but what if we reframe 
               the question? What if the real issue is..."
  🔴 Critic:   "Both sides are oversimplifying. The monolith vs
               microservices debate ignores the real factors..."

STEP 3 — ROUND 2: REBUTTALS (Each agent sees others' Round 1)
  🔵 Analyst: "The Creative raises an interesting point, but the 
               data doesn't support it. Here's why..."
  🟢 Creative: "The Analyst's 87% figure is misleading because..."
  🔴 Critic:   "Both the Analyst and Creative are cherry-picking.
               The real risk nobody is addressing is..."

STEP 4 — CONSENSUS SCORING
Gemini Judge evaluates all 6 statements:
  - Agreement areas: 78%
  - Disagreement areas: 22%
  - Confidence in final answer: 85%

STEP 5 — SYNTHESIS
A final Gemini call synthesizes the debate:
"All three perspectives converge on starting monolith, but
 differ on when to transition. The key insight from the debate:
 your team size matters more than your architecture choice."

STEP 6 — SELF-IMPROVEMENT
Braintrust logs which debate strategies led to high-quality consensus.
Over time: system learns that Analyst-led debates score higher for
technical questions, Creative-led debates score higher for strategy.
```

### Complete File Structure

```
hivemind/
├── package.json
├── .env.local
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx              # Main page — debate theater
│   │   └── api/
│   │       ├── debate/
│   │       │   └── route.ts      # POST: Start debate
│   │       ├── stream/
│   │       │   └── route.ts      # GET: SSE stream of debate
│   │       └── history/
│   │           └── route.ts      # GET: Past debates + metrics
│   ├── lib/
│   │   ├── gemini.ts
│   │   ├── debate.ts             # Core debate engine
│   │   ├── agents.ts             # Agent personas
│   │   ├── consensus.ts          # Consensus scoring
│   │   ├── scoring.ts            # Braintrust integration
│   │   └── learning.ts           # Self-improvement tracking
│   └── components/
│       ├── VoiceWidget.tsx
│       ├── DebateTheater.tsx      # Main debate view
│       ├── AgentPanel.tsx         # Individual agent's arguments
│       ├── ConsensusMeter.tsx     # Animated agreement gauge
│       ├── DebateTimeline.tsx     # Round-by-round progression
│       ├── SynthesisCard.tsx      # Final synthesized answer
│       └── MetaLearning.tsx       # Which strategies work best
└── data/
    └── debate-history.json
```

### Agent Personas — Complete Definition

```typescript
// src/lib/agents.ts

export interface DebateAgent {
  id: string;
  name: string;
  emoji: string;
  color: string;            // Tailwind color
  voiceId: string;           // ElevenLabs voice ID
  systemPrompt: string;
  style: string;
}

export const DEBATE_AGENTS: DebateAgent[] = [
  {
    id: 'analyst',
    name: 'The Analyst',
    emoji: '🔵',
    color: 'blue',
    voiceId: 'pNInz6obpgDQGcFmaJgB',  // "Adam" — deep, authoritative
    systemPrompt: `You are The Analyst in a multi-agent debate. Your approach:
- Always cite data, statistics, benchmarks, and case studies
- Be precise and evidence-based
- Acknowledge uncertainty with confidence intervals
- Structure arguments logically: claim → evidence → conclusion
- Never speculate without data to back it up
- Keep responses to 3-4 sentences for voice delivery

When responding to other agents, reference their specific claims and counter with data.`,
    style: 'data-driven',
  },
  {
    id: 'creative',
    name: 'The Creative',
    emoji: '🟢',
    color: 'green',
    voiceId: '21m00Tcm4TlvDq8ikWAM',  // "Rachel" — warm, thoughtful
    systemPrompt: `You are The Creative in a multi-agent debate. Your approach:
- Find unconventional angles others miss
- Challenge assumptions and reframe questions
- Use analogies and metaphors to make points vivid
- Think about second-order effects and hidden implications
- Be willing to take contrarian positions
- Keep responses to 3-4 sentences for voice delivery

When responding to other agents, acknowledge their points but pivot to what they're missing.`,
    style: 'lateral-thinking',
  },
  {
    id: 'critic',
    name: 'The Critic',
    emoji: '🔴',
    color: 'red',
    voiceId: 'ErXwobaYiN019PkySvjV',  // "Antoni" — sharp, precise
    systemPrompt: `You are The Critic in a multi-agent debate. Your approach:
- Find flaws, gaps, and weaknesses in every argument
- Ask the hard questions others avoid
- Identify hidden assumptions and unstated risks
- Push for rigor and precision
- Don't be rude, but be relentless in questioning
- Keep responses to 3-4 sentences for voice delivery

When responding to other agents, identify the weakest point in their argument and press on it.`,
    style: 'adversarial',
  },
];
```

### Debate Engine — Complete Code

```typescript
// src/lib/debate.ts
import { generate, generateJSON } from './gemini';
import { DEBATE_AGENTS, DebateAgent } from './agents';
import { scoreConsensus } from './consensus';
import Braintrust from 'braintrust';

interface DebateRound {
  roundNumber: number;
  statements: {
    agentId: string;
    agentName: string;
    statement: string;
    timestamp: string;
  }[];
}

interface DebateResult {
  question: string;
  rounds: DebateRound[];
  consensus: {
    score: number;           // 0-1, how much agents agree
    agreementAreas: string[];
    disagreementAreas: string[];
    confidence: number;
  };
  synthesis: string;          // Final synthesized answer
  winningStrategy: string;    // Which agent's approach dominated
  totalScore: number;         // Braintrust quality score
}

const logger = Braintrust.initLogger({ project: "hivemind" });

// Run a single round of debate
async function runRound(
  question: string,
  roundNumber: number,
  previousRounds: DebateRound[],
  agents: DebateAgent[]
): Promise<DebateRound> {
  const statements = await Promise.all(
    agents.map(async (agent) => {
      let prompt = '';
      
      if (roundNumber === 1) {
        // Opening statement
        prompt = `The question being debated: "${question}"

Give your opening position on this question. Be specific and direct.`;
      } else {
        // Rebuttal — include previous statements
        const prevStatements = previousRounds[previousRounds.length - 1].statements
          .filter(s => s.agentId !== agent.id)
          .map(s => `${s.agentName}: "${s.statement}"`)
          .join('\n\n');
        
        prompt = `The question being debated: "${question}"

Other agents said in Round ${roundNumber - 1}:
${prevStatements}

Respond to their arguments. Defend or adjust your position. Be specific about which points you agree or disagree with.`;
      }
      
      const statement = await generate(agent.systemPrompt, prompt);
      
      return {
        agentId: agent.id,
        agentName: agent.name,
        statement,
        timestamp: new Date().toISOString(),
      };
    })
  );
  
  return { roundNumber, statements };
}

// Score consensus between agents
async function evaluateConsensus(
  question: string,
  rounds: DebateRound[]
): Promise<DebateResult['consensus']> {
  const allStatements = rounds.flatMap(r => 
    r.statements.map(s => `${s.agentName} (Round ${r.roundNumber}): ${s.statement}`)
  ).join('\n\n');
  
  const evaluation = await generateJSON(
    `You are a debate judge. Evaluate the consensus between three debaters. Return JSON with:
- score: 0-1 (0 = total disagreement, 1 = complete consensus)
- agreementAreas: string[] (points all agents agree on)
- disagreementAreas: string[] (points where agents diverge)
- confidence: 0-1 (how confident are you in the consensus assessment)`,
    
    `Question: "${question}"\n\nDebate transcript:\n${allStatements}\n\nEvaluate consensus. Return JSON.`
  );
  
  return {
    score: evaluation.score || 0.5,
    agreementAreas: evaluation.agreementAreas || [],
    disagreementAreas: evaluation.disagreementAreas || [],
    confidence: evaluation.confidence || 0.5,
  };
}

// Synthesize final answer
async function synthesize(
  question: string,
  rounds: DebateRound[],
  consensus: DebateResult['consensus']
): Promise<string> {
  const allStatements = rounds.flatMap(r =>
    r.statements.map(s => `${s.agentName} (Round ${r.roundNumber}): ${s.statement}`)
  ).join('\n\n');
  
  return await generate(
    `You are synthesizing a multi-agent debate into a clear, balanced final answer.
Weigh each perspective based on the strength of their arguments.
Be specific about what the agents agreed on and where they differed.
The answer should be richer and more nuanced than any single agent could provide.
Keep it to 3-5 sentences.`,
    
    `Question: "${question}"
    
Debate transcript:
${allStatements}

Consensus areas: ${consensus.agreementAreas.join(', ')}
Disagreement areas: ${consensus.disagreementAreas.join(', ')}

Synthesize the best answer from this debate.`
  );
}

// MAIN DEBATE FUNCTION
export async function runDebate(
  question: string,
  maxRounds: number = 2
): Promise<DebateResult> {
  const agents = DEBATE_AGENTS;
  const rounds: DebateRound[] = [];
  
  // Run debate rounds
  for (let i = 1; i <= maxRounds; i++) {
    const round = await runRound(question, i, rounds, agents);
    rounds.push(round);
  }
  
  // Evaluate consensus
  const consensus = await evaluateConsensus(question, rounds);
  
  // Synthesize final answer
  const synthesis = await synthesize(question, rounds, consensus);
  
  // Determine winning strategy
  const winningStrategy = consensus.score > 0.7 
    ? 'collaborative' 
    : consensus.score > 0.4 
      ? agents[0].style  // Analyst typically dominates
      : 'contested';
  
  // Log to Braintrust
  const span = logger.startSpan({ name: "debate" });
  span.log({
    input: question,
    output: synthesis,
    scores: {
      consensus: consensus.score,
      confidence: consensus.confidence,
    },
    metadata: {
      rounds: rounds.length,
      winningStrategy,
    },
  });
  span.end();
  
  return {
    question,
    rounds,
    consensus,
    synthesis,
    winningStrategy,
    totalScore: consensus.confidence,
  };
}
```

### Debate Theater UI — Complete Component

```tsx
// src/components/DebateTheater.tsx
"use client";
import { useState } from 'react';

interface Statement {
  agentId: string;
  agentName: string;
  statement: string;
}

interface DebateState {
  rounds: { roundNumber: number; statements: Statement[] }[];
  consensus: { score: number; agreementAreas: string[]; disagreementAreas: string[] };
  synthesis: string;
  loading: boolean;
}

const AGENT_STYLES: Record<string, { emoji: string; color: string; bg: string }> = {
  analyst: { emoji: '🔵', color: 'text-blue-400', bg: 'border-blue-700 bg-blue-900/20' },
  creative: { emoji: '🟢', color: 'text-green-400', bg: 'border-green-700 bg-green-900/20' },
  critic: { emoji: '🔴', color: 'text-red-400', bg: 'border-red-700 bg-red-900/20' },
};

export default function DebateTheater() {
  const [question, setQuestion] = useState('');
  const [debate, setDebate] = useState<DebateState | null>(null);
  const [loading, setLoading] = useState(false);

  const startDebate = async () => {
    setLoading(true);
    setDebate(null);
    
    const res = await fetch('/api/debate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    
    const result = await res.json();
    setDebate({ ...result, loading: false });
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <h1 className="text-4xl font-bold mb-2">🐝 HiveMind</h1>
      <p className="text-gray-400 mb-8">Three agents debate. Truth emerges.</p>
      
      {/* Question Input */}
      <div className="flex gap-4 mb-8">
        <input 
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a complex question..."
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3"
        />
        <button 
          onClick={startDebate}
          disabled={loading}
          className="bg-amber-600 hover:bg-amber-700 px-6 py-3 rounded-lg font-semibold"
        >
          {loading ? '🐝 Debating...' : '⚡ Start Debate'}
        </button>
      </div>

      {/* Agent Panels */}
      {loading && (
        <div className="grid grid-cols-3 gap-4 mb-8">
          {['analyst', 'creative', 'critic'].map(id => (
            <div key={id} className={`border rounded-xl p-4 ${AGENT_STYLES[id].bg}`}>
              <div className="text-xl mb-2">
                {AGENT_STYLES[id].emoji} {id === 'analyst' ? 'The Analyst' : id === 'creative' ? 'The Creative' : 'The Critic'}
              </div>
              <div className="animate-pulse bg-gray-700 h-4 rounded w-3/4 mb-2"></div>
              <div className="animate-pulse bg-gray-700 h-4 rounded w-1/2"></div>
            </div>
          ))}
        </div>
      )}

      {debate && (
        <>
          {/* Debate Rounds */}
          {debate.rounds.map(round => (
            <div key={round.roundNumber} className="mb-8">
              <h3 className="text-lg font-semibold text-gray-300 mb-4">
                Round {round.roundNumber} {round.roundNumber === 1 ? '— Opening Statements' : '— Rebuttals'}
              </h3>
              <div className="grid grid-cols-3 gap-4">
                {round.statements.map(stmt => {
                  const style = AGENT_STYLES[stmt.agentId];
                  return (
                    <div key={stmt.agentId} className={`border rounded-xl p-4 ${style.bg}`}>
                      <div className={`font-semibold mb-2 ${style.color}`}>
                        {style.emoji} {stmt.agentName}
                      </div>
                      <p className="text-sm text-gray-300 leading-relaxed">
                        {stmt.statement}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Consensus Meter */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 mb-8">
            <h3 className="text-lg font-semibold mb-4">📊 Consensus</h3>
            <div className="w-full bg-gray-700 rounded-full h-6 mb-4">
              <div 
                className="bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 h-6 rounded-full transition-all duration-1000"
                style={{ width: `${debate.consensus.score * 100}%` }}
              >
                <span className="text-xs font-bold text-black px-2 leading-6">
                  {(debate.consensus.score * 100).toFixed(0)}% Agreement
                </span>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <h4 className="text-green-400 font-semibold mb-2">✅ Agreement Areas</h4>
                {debate.consensus.agreementAreas.map((area, i) => (
                  <p key={i} className="text-gray-300 mb-1">• {area}</p>
                ))}
              </div>
              <div>
                <h4 className="text-red-400 font-semibold mb-2">❌ Disagreement Areas</h4>
                {debate.consensus.disagreementAreas.map((area, i) => (
                  <p key={i} className="text-gray-300 mb-1">• {area}</p>
                ))}
              </div>
            </div>
          </div>

          {/* Synthesis */}
          <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-700/50 rounded-xl p-6">
            <h3 className="text-xl font-semibold mb-3">🎯 Synthesized Answer</h3>
            <p className="text-gray-200 leading-relaxed text-lg">{debate.synthesis}</p>
          </div>
        </>
      )}
    </div>
  );
}
```

### ElevenLabs Multi-Voice Integration

To have 3 different voices for each agent, you need to use the **ElevenLabs Text-to-Speech API** directly (not the widget):

```typescript
// src/lib/tts.ts

const ELEVEN_API_KEY = process.env.ELEVENLABS_API_KEY;

// Voice IDs from ElevenLabs voice library
const VOICE_MAP: Record<string, string> = {
  analyst: 'pNInz6obpgDQGcFmaJgB',  // Adam
  creative: '21m00Tcm4TlvDq8ikWAM',  // Rachel
  critic: 'ErXwobaYiN019PkySvjV',     // Antoni
};

export async function textToSpeech(text: string, agentId: string): Promise<Buffer> {
  const voiceId = VOICE_MAP[agentId] || VOICE_MAP.analyst;
  
  const response = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'xi-api-key': ELEVEN_API_KEY!,
      },
      body: JSON.stringify({
        text,
        model_id: 'eleven_turbo_v2',  // Fast, good quality
        voice_settings: {
          stability: 0.5,
          similarity_boost: 0.75,
        },
      }),
    }
  );
  
  const audioBuffer = await response.arrayBuffer();
  return Buffer.from(audioBuffer);
}

// Play debate sequentially with different voices
export async function generateDebateAudio(
  statements: { agentId: string; statement: string }[]
): Promise<Buffer[]> {
  const audioBuffers: Buffer[] = [];
  
  for (const stmt of statements) {
    const audio = await textToSpeech(stmt.statement, stmt.agentId);
    audioBuffers.push(audio);
  }
  
  return audioBuffers;
}
```

### Frontend Audio Playback
```tsx
// In DebateTheater.tsx — add audio playback
async function playDebateAudio(statements: Statement[]) {
  for (const stmt of statements) {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: stmt.statement, agentId: stmt.agentId }),
    });
    
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    
    // Wait for this statement to finish before playing next
    await new Promise(resolve => {
      audio.onended = resolve;
      audio.play();
    });
  }
}
```

### Self-Improvement Learning

```typescript
// src/lib/learning.ts
import fs from 'fs';

interface DebateMetrics {
  question: string;
  questionType: string;      // technical, strategic, ethical, creative
  winningStrategy: string;
  consensusScore: number;
  qualityScore: number;
  dominantAgent: string;
}

const HISTORY_PATH = 'data/debate-history.json';

export function logDebateMetrics(metrics: DebateMetrics) {
  let history: DebateMetrics[] = [];
  try {
    history = JSON.parse(fs.readFileSync(HISTORY_PATH, 'utf8'));
  } catch {}
  
  history.push(metrics);
  fs.writeFileSync(HISTORY_PATH, JSON.stringify(history, null, 2));
}

// Learn which strategies work best for which question types
export function getOptimalStrategy(questionType: string): {
  agentOrder: string[];
  rounds: number;
  temperature: number;
} {
  let history: DebateMetrics[] = [];
  try {
    history = JSON.parse(fs.readFileSync(HISTORY_PATH, 'utf8'));
  } catch {}
  
  // Filter by question type
  const relevant = history.filter(h => h.questionType === questionType);
  
  if (relevant.length < 3) {
    // Not enough data — use defaults
    return { agentOrder: ['analyst', 'creative', 'critic'], rounds: 2, temperature: 0.7 };
  }
  
  // Find which agent led to highest quality scores
  const agentScores: Record<string, number[]> = {};
  for (const h of relevant) {
    if (!agentScores[h.dominantAgent]) agentScores[h.dominantAgent] = [];
    agentScores[h.dominantAgent].push(h.qualityScore);
  }
  
  // Sort agents by average quality when they dominate
  const sorted = Object.entries(agentScores)
    .map(([agent, scores]) => ({
      agent,
      avgScore: scores.reduce((a, b) => a + b, 0) / scores.length,
    }))
    .sort((a, b) => b.avgScore - a.avgScore);
  
  return {
    agentOrder: sorted.map(s => s.agent),
    rounds: relevant.length > 10 ? 3 : 2,  // More rounds if we have confidence
    temperature: 0.7,
  };
}
```

---

# SPONSOR CHEAT SHEET

| Sponsor | What They Do | How to Integrate | Time to Integrate |
|---------|-------------|------------------|-------------------|
| **Google DeepMind** | Gemini LLM | Core LLM for ALL ideas. `npm install @google/generative-ai` | 15 min |
| **ElevenLabs** | Voice AI | Web widget (1 line HTML) + TTS API for multi-voice | 20-30 min |
| **Braintrust** | AI evals & observability | `pip install braintrust autoevals` — score agent outputs, log traces | 30-45 min |
| **Lightdash** | BI dashboards | MCP server for data queries OR custom Recharts dashboard | 30-60 min |
| **Modulate** | Voice safety (ToxMod) | Feed audio to ToxMod API → get safety scores. Show on dashboard. | 20-30 min |
| **Airia** | Agent orchestration | Route tasks between agents. No-code builder or API. | 30-60 min |
| **Datadog** | Monitoring | `DD_API_KEY=x` agent install. Custom metrics via HTTP API. | 15 min |
| **Senso** | Enterprise knowledge verification | Verify agent outputs against trusted sources. | 20-30 min |
| **Cleric** | Incident management | Agent reports incidents/actions via Cleric. | 20 min |

### Minimum Viable Sponsor Usage (3 sponsors required)
**Every idea uses at minimum:**
1. ✅ Google DeepMind (Gemini) — core LLM
2. ✅ ElevenLabs — voice interface
3. ✅ Braintrust — evaluation/scoring

**To be eligible for sponsor prizes, also add:**
4. ✅ Lightdash — for Lightdash prize
5. ✅ Modulate — for Modulate prize
6. ✅ Airia — for Airia prize

---

# MCP SERVERS & AGENT SKILLS

## MCP Servers You Can Use

### Lightdash MCP
```bash
npm install lightdash-mcp-server
```
Tools: `list_projects`, `get_project`, `list_charts`, `list_dashboards`, `get_metrics_catalog`, `get_charts_as_code`, `get_dashboards_as_code`

### Braintrust MCP
Check if available at sponsor booth. Otherwise use SDK directly.

## Agent Skills (skills.sh) — Key Skills for Each Idea

### For ALL Projects
```bash
npx skills add vercel-labs/agent-skills --skill frontend-design -g -y
npx skills add vercel-labs/agent-skills --skill skill-creator -g -y
```

### For Phoenix (Idea 2) — Skills to Pre-Demo
```bash
# Pre-install these so your demo has variety:
npx skills add vercel-labs/agent-skills --skill vercel-react-best-practices -g -y
npx skills add supabase/agent-skills -g -y
npx skills add anthropics/skills -g -y
npx skills add vercel-labs/agent-skills --skill typescript-best-practices -g -y
```

### Top Skills on skills.sh (68,885 total)
| # | Skill | Installs |
|---|-------|----------|
| 1 | vercel-labs/skills (find-skills) | 277K |
| 2 | vercel-labs/agent-skills (react) | 151K |
| 3 | vercel-labs/agent-skills (design) | 114K |
| 4 | remotion-dev/skills | 101K |
| 5 | anthropics/skills | 84K |
| 6 | vercel-labs/agent-browser | 48K |
| 7 | nextlevelbuilder/ui-ux-pro-max-skill | 32K |
| 8 | supabase/agent-skills | 21K |

---

# BUILD TIMELINE

## 🧬 Darwin — 4.5 Hour Plan
| Time | Task | Status |
|------|------|--------|
| 0:00 - 0:15 | `npx create-next-app`, install deps, env vars | Setup |
| 0:15 - 0:30 | Gemini wrapper (generate, generateJSON, generateWithTemp) | Core |
| 0:30 - 1:15 | Evolution engine (spawn, compete, select, mutate, loop) | Core |
| 1:15 - 1:45 | Braintrust scoring integration | Core |
| 1:45 - 2:30 | API routes (evolve, generation status) | Backend |
| 2:30 - 3:15 | Dashboard UI (fitness chart, population grid, best prompt) | Frontend |
| 3:15 - 3:30 | ElevenLabs voice widget | Voice |
| 3:30 - 3:45 | Additional sponsor integrations (Datadog, Modulate, Airia) | Sponsors |
| 3:45 - 4:00 | Pre-seed data: run 15-20 generations ahead of demo | Data |
| 4:00 - 4:30 | Polish UI, rehearse 3-min pitch | Demo prep |

## 🧠 Phoenix — 4.5 Hour Plan
| Time | Task | Status |
|------|------|--------|
| 0:00 - 0:15 | `npx create-next-app`, install deps, env vars | Setup |
| 0:15 - 0:30 | Gemini wrapper | Core |
| 0:30 - 1:15 | Skill engine (search, install, read, inventory) | Core |
| 1:15 - 1:45 | Phoenix brain (intent→check→learn→execute) | Core |
| 1:45 - 2:15 | API routes + Braintrust scoring | Backend |
| 2:15 - 3:00 | UI: chat interface + skill tree + learning indicator | Frontend |
| 3:00 - 3:15 | ElevenLabs voice widget | Voice |
| 3:15 - 3:30 | Additional sponsor integrations | Sponsors |
| 3:30 - 4:00 | Pre-install 3-4 skills for demo variety, test scenarios | Data |
| 4:00 - 4:30 | Polish, rehearse demo scenarios (React → SQL → Supabase) | Demo prep |

## 🐝 HiveMind — 4.5 Hour Plan
| Time | Task | Status |
|------|------|--------|
| 0:00 - 0:15 | `npx create-next-app`, install deps, env vars | Setup |
| 0:15 - 0:30 | Gemini wrapper + agent personas | Core |
| 0:30 - 1:15 | Debate engine (rounds, rebuttals, consensus scoring) | Core |
| 1:15 - 1:45 | Synthesis + learning/tracking | Core |
| 1:45 - 2:15 | API routes + Braintrust scoring | Backend |
| 2:15 - 3:15 | Debate theater UI (3 panels, consensus meter, synthesis) | Frontend |
| 3:15 - 3:45 | ElevenLabs multi-voice TTS | Voice |
| 3:45 - 4:00 | Additional sponsor integrations | Sponsors |
| 4:00 - 4:15 | Pre-run 3-5 debates for history/learning data | Data |
| 4:15 - 4:30 | Polish, pick 2 great demo questions, rehearse | Demo prep |

---

# ENVIRONMENT VARIABLES

```bash
# .env.local — Same for all 3 projects

# Core
GEMINI_API_KEY=your_gemini_key
ELEVENLABS_API_KEY=your_elevenlabs_key
ELEVENLABS_AGENT_ID=your_agent_id

# Evals
BRAINTRUST_API_KEY=your_braintrust_key
OPENAI_API_KEY=your_openai_key  # Braintrust uses this for LLM-as-judge

# Monitoring
DD_API_KEY=your_datadog_key

# Sponsors (get at event)
AIRIA_API_KEY=your_airia_key
MODULATE_API_KEY=your_modulate_key
LIGHTDASH_API_KEY=your_lightdash_key
LIGHTDASH_API_URL=https://app.lightdash.cloud

# Senso (optional)
SENSO_API_KEY=your_senso_key
```

# PACKAGE.JSON — Base for All Projects

```json
{
  "name": "hackathon-project",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@google/generative-ai": "^0.21.0",
    "braintrust": "^0.5.0",
    "autoevals": "^0.0.90",
    "recharts": "^2.12.0",
    "d3": "^7.9.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "@types/react": "^19.0.0",
    "@types/node": "^22.0.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

---

# FINAL DECISION HELPER

| If you want... | Build... | Because... |
|----------------|----------|------------|
| **Most unique concept** | 🧬 Darwin | Nobody has ever demo'd evolutionary AI on stage |
| **Most reliable demo** | 🐝 HiveMind | Works every time — just LLM calls |
| **Strongest narrative** | 🧠 Phoenix | "Born knowing nothing" is the best story |
| **Best sponsor fit** | 🧬 Darwin | Braintrust as fitness function is perfect |
| **Easiest to vibe-code** | 🧠 Phoenix | Most straightforward architecture |
| **Most entertaining** | 🐝 HiveMind | Hearing AI voices argue is inherently fun |

**My pick: 🧠 Phoenix if solo, 🧬 Darwin if you want to take a swing for the fences.**

Good luck Siddhant. Go win this thing. 🏆
