# Braintrust Strategy Report

Generated: 2026-02-21 19:39:20Z
Project: ElevenLabs Dataset Agent Eval

## Variant Ranking
1. flood-fuzzy-eval-r4-cli-2 | overall=0.2194 | cases=15
2. flood-fuzzy-eval-r4-cli-1 | overall=0.1965 | cases=15

## Experiment: flood-fuzzy-eval-r4-cli-1

### Metrics
- de_escalation_language_score: 0.0286
- de_escalation_turn_efficiency: 0.0157
- emergency_help_turn_efficiency: 0.2133
- fuzzy_crisis_support: 0.1914
- mentions_emergency_services: 0.5333
- avg_turn_count: 19.40

### Proposed Strategies
- Hard-Code Emergency Escalation Trigger: Emergency routing is not consistent enough in danger scenarios.
  prompt_patch: If user describes immediate physical danger (flood, fire, trapped, life risk), your first response must include contacting emergency services (e.g. call 911) before any additional guidance.
  target: mentions_emergency_services >= 0.85
- Force Two-Step De-Escalation Lead: Calming language is weak or inconsistent.
  prompt_patch: First sentence: emotional validation. Second sentence: calming instruction (one breathing or grounding step). Then provide actions.
  target: de_escalation_language_score >= 0.55
- Reduce To Immediate Action Template: Helpful behaviors are arriving too late in the conversation.
  prompt_patch: Within first response include: (1) safety reassurance, (2) emergency escalation if risk, (3) exactly 3 immediate steps, (4) one confirmation question.
  target: turn-efficiency metrics improve by >= 0.10
- Improve Crisis Action Specificity: Responses lack concrete high-utility crisis instructions.
  prompt_patch: Prioritize location-based actionable guidance: move to higher ground, avoid floodwater, cut electricity if safe, and state nearest safe shelter action.
  target: fuzzy_crisis_support >= 0.45
- Create Targeted Regression Slice: A subset of cases repeatedly fails across multiple metrics.
  action: Create a focused eval subset and require pass before full-run promotion.
  priority_cases: ef87d23f-d566-4feb-8fd1-ee203eaadf9e, 38140ee8-c297-47a2-931a-3b45d9e16752, d71574df-5f0d-4523-af64-072ab0790cf6, bb1cfcbb-b12b-44b4-a4ce-c95b96f57641, 1a673daf-e5b3-4190-8277-1b21d567c19a

## Experiment: flood-fuzzy-eval-r4-cli-2

### Metrics
- de_escalation_language_score: 0.0381
- de_escalation_turn_efficiency: 0.0210
- emergency_help_turn_efficiency: 0.2400
- fuzzy_crisis_support: 0.1981
- mentions_emergency_services: 0.6000
- avg_turn_count: 19.40

### Proposed Strategies
- Hard-Code Emergency Escalation Trigger: Emergency routing is not consistent enough in danger scenarios.
  prompt_patch: If user describes immediate physical danger (flood, fire, trapped, life risk), your first response must include contacting emergency services (e.g. call 911) before any additional guidance.
  target: mentions_emergency_services >= 0.85
- Force Two-Step De-Escalation Lead: Calming language is weak or inconsistent.
  prompt_patch: First sentence: emotional validation. Second sentence: calming instruction (one breathing or grounding step). Then provide actions.
  target: de_escalation_language_score >= 0.55
- Reduce To Immediate Action Template: Helpful behaviors are arriving too late in the conversation.
  prompt_patch: Within first response include: (1) safety reassurance, (2) emergency escalation if risk, (3) exactly 3 immediate steps, (4) one confirmation question.
  target: turn-efficiency metrics improve by >= 0.10
- Improve Crisis Action Specificity: Responses lack concrete high-utility crisis instructions.
  prompt_patch: Prioritize location-based actionable guidance: move to higher ground, avoid floodwater, cut electricity if safe, and state nearest safe shelter action.
  target: fuzzy_crisis_support >= 0.45
- Create Targeted Regression Slice: A subset of cases repeatedly fails across multiple metrics.
  action: Create a focused eval subset and require pass before full-run promotion.
  priority_cases: 0b3810a9-029e-4469-ae23-53b247fb121b, 45f96631-5db2-4c2d-af93-05b85fac75ed, be5187c7-49af-4dc2-aff7-2f9914124e35, 1dd09535-aa76-41b1-bf2c-e21416e6ed8c, 2e5514d4-7498-4afd-bf44-40d1926275ed
