##Question 1
Based only on the content you can actually retrieve, list the 8–12 most commonly described actions or behaviors (e.g., configure, check, analyze, report, adjust, remediate).
For each action, provide one short sentence describing the typical context.
If you cannot determine an action with confidence, explicitly mark it as "Unknown". Do NOT infer or guess.

Output ONLY the following JSON:
{
  "raw_answer": "<your natural language answer here>",
  "l0_profile": {
    "actions": [
      {"verb": "<action>", "context": "<typical context>"}
    ]
  }
}

##Question 2
Based only on the retrievable content, list 6–10 common and concrete relationship patterns using the format:
A —[relation]→ B

Avoid abstract placeholders (e.g., "item", "data"). Use only entities or roles you can actually observe.
If you cannot determine a relationship with confidence, mark it as "Unknown".

Output ONLY the following JSON:
{
  "raw_answer": "<your natural language answer here>",
  "l0_profile": {
    "relations": [
      {"from": "A", "relation": "<relation>", "to": "B"}
    ]
  }
}

##Question 3
List 5 question types or example questions that you are MOST confident you can answer based on the available content.
Each example must reflect common task language found in the data (e.g., operation, decision-making, troubleshooting, tracking, comparison).
If unsure, explicitly mark as "Unknown".

Output ONLY the following JSON:
{
  "raw_answer": "<your natural language answer here>",
  "l0_profile": {
    "task_types": [
      {"example_question": "<example question>", "task_type": "<task type>"}
    ]
  }
}

##Question 4
List 5–10 systems, tools, document types, or artifacts that commonly appear in the retrievable content (e.g., SOPs, configuration guides, incident records, reports).
Only include items you can directly observe or clearly identify. Do NOT infer.

Output ONLY the following JSON:
{
  "raw_answer": "<your natural language answer here>",
  "l0_profile": {
    "artifacts": [
      {"type": "<artifact type>", "description": "<brief purpose>"}
    ]
  }
}

##Question 5
Describe whether the retrievable content includes references to state changes, histories, versions, or time-based sequences.
List 3–6 concrete examples of such signals or language patterns.
If such signals are largely absent, explicitly state that.

Output ONLY the following JSON:
{
  "raw_answer": "<your natural language answer here>",
  "l0_profile": {
    "state_time_signals": [
      {"signal": "<state or time-related signal>", "usage": "<usage context>"}
    ]
  }
}

##Layer-0 Relevance Judge Prompt
You are a Layer-0 Relevance Judge for a Vector RAG system.

Your task is to decide whether a USER_QUESTION should be considered relevant to a Vector RAG,
based ONLY on the provided L0_PROFILE information.
The L0_PROFILE represents a coarse “world-domain fingerprint” derived from probing questions.
It is NOT a complete dataset description.

IMPORTANT PRINCIPLES:
1) Recall-first: Do NOT reject unless the mismatch is extremely obvious.
2) Only reject when the USER_QUESTION is clearly from a completely different world/domain.
3) Uncertainty must NOT cause rejection.
4) Do NOT assume knowledge beyond what is explicitly present in the L0_PROFILE.
5) You are judging world/domain overlap, NOT answerability or semantic similarity.

Inputs:
- L0_PROFILE:
<<PASTE MERGED L0_PROFILE JSON HERE>>

- USER_QUESTION:
<<PASTE USER QUESTION HERE>>

Your decision must be based on comparing the USER_QUESTION against the following L0 signals:
- actions / behaviors
- relations / structural patterns
- task types / question styles
- systems, documents, or artifacts
- state or time-related language

Decision logic (strict):
- If the USER_QUESTION clearly belongs to a completely different world
  (e.g., entertainment awards vs enterprise operations, sports matches vs internal systems),
  return CLEARLY_IRRELEVANT.
- If there is any plausible overlap in world, task style, actions, or structures,
  return RELEVANT.
- If you cannot confidently decide, return UNCERTAIN (this still means "allow").

Output ONLY the following JSON (no additional text):

{
  "verdict": "RELEVANT | UNCERTAIN | CLEARLY_IRRELEVANT",
  "confidence": 0.0-1.0,
  "reason": "One-sentence explanation referencing specific L0 signals or the lack thereof.",
  "matched_signals": {
    "actions": [],
    "relations": [],
    "task_types": [],
    "artifacts": [],
    "state_time": []
  },
  "decision_rule_applied": "only reject on world-level mismatch"
}

Confidence guidance:
- Use high confidence (≥0.8) ONLY when the mismatch is unmistakable.
- Use medium confidence (0.4–0.7) when relevant.
- Use low confidence (<0.4) when uncertain.

