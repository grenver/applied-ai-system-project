# Model Card: PawPal+ Smart Health Coordinator

## Model / System Overview
PawPal+ is not a single trained model. It is an applied AI system that combines:
- A lightweight retrieval layer over `pet_health_data.json`
- A hybrid retrieval layer that also ingests user-uploaded medical records
- An LLM planning step for symptom triage and action selection
- Deterministic fallback logic when the model is unavailable or returns malformed output
- Logging and guardrails for reliability

The system's purpose is to help a pet owner respond to common health-related concerns by retrieving relevant guidance, comparing it with recent pet logs, and deciding whether to add a task or update a log.

## Intended Use
The system is intended for:
- Educational demonstration of RAG and agentic workflows
- Prototyping a pet-care triage assistant
- Generating follow-up tasks or notes from symptom-based input

It is not intended to diagnose pets or replace veterinary advice.

## Base Project
This project extends my original **PawPal+** scheduling assistant from earlier coursework. The original version focused on organizing daily pet-care tasks such as feeding, walks, and playtime. This final version keeps the scheduling foundation but adds retrieval, planning, and safety checks so it behaves more like a smart health coordinator.

## Inputs and Outputs
### Inputs
- Free-form user text describing a pet concern
- Recent pet logs or notes
- Uploaded medical records or discharge notes
- A small health knowledge base in JSON form

### Outputs
- Retrieved health guideline text
- A structured agent plan
- Actions such as `add_task` or `add_log`
- A human-readable explanation of what the system did

## Data and Knowledge Source
The system uses a simple local knowledge base, `pet_health_data.json`, with short symptom-to-guideline entries such as:
- lethargy
- appetite
- itching

The system also accepts user-uploaded medical records, which are stored in-memory during the session and searched alongside the static knowledge base.

This keeps the project reproducible and easy to inspect while still allowing personalized context.

## Guardrails and Reliability
The system includes the following reliability features:
- JSON parsing checks for model output
- A fallback planner when the LLM is unavailable
- A no-match retrieval edge case
- `AI_PLANNING_FAILURE` logging to `system.log`
- Streamlit state initialization checks to prevent runtime errors

## Known Limitations
- The retrieval method is keyword-based rather than semantic, so it can miss related phrases that do not match exact keywords.
- The LLM output depends on the external Gemini API and network availability.
- The knowledge base is intentionally small and should not be treated as medically comprehensive.
- The system does not replace veterinary triage or professional diagnosis.

## Bias, Safety, and Ethics
- The system is designed to be conservative when symptoms may be serious.
- It should not claim certainty about a pet's condition.
- If there is no strong match or the output is malformed, the system falls back to safer behavior instead of guessing aggressively.
- Human review is still important for any health-related recommendation.

## Testing Summary
What I tested:
- The core Python files load without syntax errors.
- The Streamlit app runs after fixing session-state initialization.
- The coordinator can process matched symptom inputs.
- The coordinator can handle a no-match case safely.

What still needs review:
- Gemini responses may vary across runs because they come from an external API.
- The small JSON knowledge base is not enough for real medical advice.

## Human-in-the-Loop Review
Human review is part of the design because the system is making health-related suggestions. A user should inspect the retrieved guideline and the suggested action before treating the output as a real recommendation.

## Evaluation Notes
If I were expanding this project further, I would measure:
- Retrieval precision for symptom keywords
- Frequency of malformed output from the planner
- How often the fallback path is used
- Whether the system adds the correct follow-up action for each example input

## Ethical Reflection
This project taught me that responsible AI is not only about making the model work, but about constraining how it works. The retriever, fallback planner, and logging are as important as the LLM itself because they make the system more explainable, safer, and easier to debug.
