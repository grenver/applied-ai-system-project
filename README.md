# PawPal+ Smart Health Coordinator

## Project Summary
PawPal+ began as a pet-care scheduling project for organizing daily tasks such as feeding, walks, and playtime. In this final version, it has been extended into a Smart Health Coordinator that combines retrieval, agentic planning, and reliability guardrails to help a pet owner respond to symptom-based health concerns.

This project matters because it turns a simple planning app into a practical applied AI workflow. The system looks up pet health guidance, compares that guidance to the owner's recent notes and logs, decides whether to add a follow-up task or update a log, and explains what happened in plain language.

## Original Project
The original project was **PawPal+**, a pet scheduling assistant built to organize daily care tasks for one or more pets. It could represent owners, pets, and tasks, then generate a simple schedule based on time, priority, and feasibility constraints.

## What Changed in This Version
This version extends the original scheduler into a smarter applied AI system with:
- **Retrieval-Augmented Generation (RAG):** keyword search over `pet_health_data.json`
- **Hybrid RAG:** static expert guidance plus user-uploaded medical records
- **Agentic workflow:** plan, act, and verify loop inside `PetCareSystem`
- **Reliability guardrails:** structured error handling and `AI_PLANNING_FAILURE` logging
- **Automated actions:** the system can call `add_task` or `add_log` on the user's behalf

In practice, that means the AI does more than summarize text. A single call to `coordinate_pet_care()` orchestrates retrieval, planning, and action execution. It uses retrieved health guidance to shape the next action and then confirms that action back to the user. The system gracefully falls back to rule-based planning if no LLM is available.

## Architecture Overview
The system is organized as a unified pipeline that runs with a single call to `care_system.coordinate_pet_care()`:

1. **User input** enters the Streamlit UI or command-line demo.
2. **Retriever** searches `pet_health_data.json` for symptom keywords such as lethargy, appetite, or itching.
3. **Medical record store** ingests uploaded notes or discharge summaries and searches them for related context.
4. **Planner client** (`GeminiPlanClient` or `RuleBasedPlanner`) receives the retrieved guideline, uploaded records, and the pet's recent logs, then decides what to do next. The planner is chosen at initialization based on available API keys:
   - If `GOOGLE_API_KEY` is set → uses `GeminiPlanClient` (enforces JSON output to eliminate malformed responses)
   - Else → falls back to `RuleBasedPlanner` (always available)
5. **Actuator** automatically adds a task or updates the pet log based on the planner's decision.
6. **Response layer** explains the guideline and record evidence that were used, along with the actions taken.
7. **Logging and guardrails** capture failures and malformed outputs in `system.log`.

Architecture diagram source: [assets/system_architecture.mmd](assets/system_architecture.mmd)

Supporting reflection artifact: [model_card.md](model_card.md)

## Setup Instructions
1. Create and activate a virtual environment.
2. Install the dependencies.
3. Add your Gemini API key to `.env` as `GOOGLE_API_KEY=...`.
4. Run the console demo or the Streamlit app.
5. Optional but recommended: clear `system.log` before the first run so the reliability data you see starts fresh.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

```powershell
python main.py
```

```powershell
streamlit run app.py
```

## Sample Interactions
### Example 1: Lethargy
**Input:**
`Mochi has been lethargic and has not eaten in 12 hours`

**Expected behavior:**
- Retrieves the lethargy guideline from `pet_health_data.json`
- Compares it to recent logs
- Adds a follow-up task such as `Schedule Vet Visit` if needed
- Returns a response that cites the retrieved guideline

### Example 2: Itching
**Input:**
`Mochi keeps itching his skin at night`

**Expected behavior:**
- Retrieves the itching guideline
- Flags a likely follow-up action
- Adds a note or task depending on the agent plan

### Example 3: No direct match
**Input:**
`Mochi seems uncomfortable but I am not sure why`

**Expected behavior:**
- Handles the no-match edge case safely
- Produces a conservative response
- Logs planning issues if the model output is malformed or unavailable

## Design Decisions
- I kept the project modular so the original scheduler still works independently of the new AI coordinator.
- I used a small JSON knowledge base instead of a database to keep the project reproducible and easy to grade.
- I added fallback planning so the system still behaves safely when Gemini is unavailable.
- I chose keyword retrieval because the project needs a simple, explainable RAG layer rather than a heavy search stack.

## Reliability and Testing Summary
The system includes several reliability checks:
- Structured JSON parsing for model output
- A no-match retrieval fallback
- Logging to `system.log` when planning fails
- Streamlit session-state validation to avoid runtime initialization errors

Testing checklist:
- [x] Retrieve the correct guideline from the JSON knowledge base
- [x] Add a follow-up task when the plan requests one
- [x] Log and surface malformed LLM output safely
- [x] Handle a no-match symptom case conservatively

Testing results to report:
- Core Python files run without syntax errors.
- The Streamlit app launches successfully after session-state initialization was fixed.
- The coordinator handles both matched and unmatched symptom inputs.
- The unit test suite passes with 3/3 tests green.
- Remaining risk: Gemini output quality depends on the external API and network availability.

This testing approach gives the project a small but meaningful reliability story: retrieval works, action execution works, malformed plans are handled safely, and the UI no longer crashes on startup.

Quick test command:

```powershell
.venv\Scripts\python -m unittest discover -s tests
```

## Reflection
This project taught me how to combine retrieval, reasoning, and automation into a single application instead of treating AI as a standalone feature. It also reinforced that reliability matters as much as model quality, because the system needs guardrails, fallback behavior, and clear explanations to be trustworthy in practice.

## Demo Walkthrough
Loom video: _add your link here_

The walkthrough should show:
- End-to-end system execution
- At least 2-3 example inputs
- Retrieval behavior
- Agent actions or fallback behavior
- Logging / guardrail behavior

## Portfolio Note
PawPal+ demonstrates that I can take an earlier prototype and extend it into a more complete applied AI system with retrieval, planning, logging, and user-facing explanation.

This project shows that I can work from a smaller prototype, identify the missing production pieces, and turn it into a documented system with clear behavior and verification.

## Repository Contents
- `app.py` - Streamlit interface
- `main.py` - console demo
- `pawpal_system.py` - core models and coordinator
- `pet_health_data.json` - lightweight health knowledge base
- `requirements.txt` - dependencies
- `model_card.md` - ethics, limitations, and reflection
- `assets/system_architecture.mmd` - architecture diagram source
