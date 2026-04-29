from __future__ import annotations

from collections import defaultdict
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import time
from typing import Any, Optional


SYSTEM_LOG_FILE = "system.log"
PET_HEALTH_DATA_FILE = "pet_health_data.json"

_SYSTEM_LOGGER = logging.getLogger("pawpal.system")
if not _SYSTEM_LOGGER.handlers:
    _SYSTEM_LOGGER.setLevel(logging.INFO)
    _file_handler = logging.FileHandler(SYSTEM_LOG_FILE, encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _SYSTEM_LOGGER.addHandler(_file_handler)
    _SYSTEM_LOGGER.propagate = False


def _default_preferences() -> dict[str, Any]:
    """Return a default preferences dictionary."""
    return {}


def _default_pet_ids() -> list[str]:
    """Return a default empty list of pet IDs."""
    return []


def _default_pets() -> dict[str, Pet]:
    """Return a default pet registry mapping."""
    return {}


def _default_care_notes() -> list[str]:
    """Return a default empty list of pet care notes."""
    return []


def _default_tasks() -> list[Task]:
    """Return a default empty list of tasks."""
    return []


@dataclass
class Owner:
    owner_id: str
    name: str
    available_minutes_per_day: int = 60
    preferences: dict[str, Any] = field(default_factory=_default_preferences)
    pet_ids: list[str] = field(default_factory=_default_pet_ids)
    pets: dict[str, Pet] = field(default_factory=_default_pets)

    def update_preferences(self, preferences: dict[str, Any]) -> None:
        """Merge new preference values into the owner's preferences."""
        self.preferences.update(preferences)

    def set_daily_availability(self, minutes: int) -> None:
        """Update how many minutes the owner can spend on pet care each day."""
        if minutes <= 0:
            raise ValueError("available minutes must be positive")
        self.available_minutes_per_day = minutes

    def add_pet(self, pet: Pet) -> None:
        """Attach a pet to this owner and keep owner/pet linkage consistent."""
        if pet.owner_id != self.owner_id:
            raise ValueError("pet owner_id does not match owner")
        self.pets[pet.pet_id] = pet
        if pet.pet_id not in self.pet_ids:
            self.pet_ids.append(pet.pet_id)

    def get_pet(self, pet_id: str) -> Pet:
        """Fetch one pet by ID."""
        if pet_id not in self.pets:
            raise KeyError(f"pet '{pet_id}' not found")
        return self.pets[pet_id]

    def add_task_to_pet(self, pet_id: str, task: Task) -> None:
        """Add a task to a specific pet."""
        pet = self.get_pet(pet_id)
        pet.add_task(task)

    def get_all_tasks(self, include_completed: bool = True) -> list[Task]:
        """Return tasks across all pets owned by this owner."""
        all_tasks: list[Task] = []
        for pet in self.pets.values():
            all_tasks.extend(pet.get_tasks(include_completed=include_completed))
        return all_tasks


@dataclass
class Pet:
    pet_id: str
    owner_id: str
    name: str
    species: str
    age_years: int
    care_notes: list[str] = field(default_factory=_default_care_notes)
    tasks: list[Task] = field(default_factory=_default_tasks)

    def add_care_note(self, note: str) -> None:
        """Store a new care note for this pet."""
        if note.strip():
            self.care_notes.append(note.strip())

    def add_log(self, note: str) -> None:
        """Compatibility alias for systems that use log terminology."""
        self.add_care_note(note)

    def get_profile_summary(self) -> str:
        """Return a concise profile summary for display in the UI."""
        return f"{self.name} ({self.species}, {self.age_years}y)"

    def add_task(self, task: Task) -> None:
        """Assign a task to this pet."""
        if task.pet_id != self.pet_id:
            raise ValueError("task pet_id does not match pet")
        self.tasks.append(task)

    def get_tasks(self, include_completed: bool = True) -> list[Task]:
        """Return this pet's tasks with optional completion filtering."""
        if include_completed:
            return list(self.tasks)
        return [task for task in self.tasks if not task.completed]


@dataclass
class Task:
    task_id: str
    pet_id: str
    description: str
    category: str
    duration_minutes: int
    priority: str
    frequency: str = "daily"
    due_time: Optional[time] = None
    time_window: Optional[tuple[time, time]] = None
    is_mandatory: bool = False
    completed: bool = False

    def mark_completed(self) -> None:
        """Mark the task as completed."""
        self.completed = True

    def mark_incomplete(self) -> None:
        """Reset completion state for the task."""
        self.completed = False

    def is_feasible(self, available_minutes: int) -> bool:
        """Return True when this task can fit in the available time."""
        return self.duration_minutes <= available_minutes

    def priority_score(self) -> int:
        """Convert textual priority into a numeric score for sorting tasks."""
        priority_to_score = {"low": 1, "medium": 2, "high": 3}
        return priority_to_score.get(self.priority.lower(), 0)


class Scheduler:
    def __init__(self, owner: Owner) -> None:
        """Initialize a scheduler bound to a specific owner."""
        self.owner = owner
        self.tasks: list[Task] = []

    def add_task(self, task: Task) -> None:
        """Add one task to the scheduler pool."""
        self.owner.add_task_to_pet(task.pet_id, task)
        self.tasks.append(task)

    def retrieve_tasks_from_owner(self, include_completed: bool = False) -> list[Task]:
        """Pull all tasks from the owner's pets into scheduler memory."""
        self.tasks = self.owner.get_all_tasks(include_completed=include_completed)
        return list(self.tasks)

    @staticmethod
    def _coerce_time_value(value: Any) -> time:
        """Convert mixed time inputs into a comparable ``datetime.time`` value.

        Accepts native ``time`` objects and ``"HH:MM"`` strings. Invalid or
        missing values are mapped to ``time.max`` so they naturally sort last.
        """
        if value is None:
            return time.max
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            try:
                hour_str, minute_str = value.split(":", maxsplit=1)
                return time(int(hour_str), int(minute_str))
            except (ValueError, TypeError):
                return time.max
        return time.max

    def sort_by_time(self, tasks: Optional[list[Task]] = None) -> list[Task]:
        """Return tasks ordered by due time with deterministic tie-breaks.

        The method supports due times stored as ``time`` objects or ``HH:MM``
        strings and then applies tie-breakers in this order:
        1) higher priority first, 2) task_id ascending.

        Args:
            tasks: Optional subset of tasks to sort. When omitted, scheduler
                memory is used; if empty, tasks are retrieved from the owner.

        Returns:
            A new list of tasks sorted from earliest to latest due time.
        """
        selected_tasks = list(tasks) if tasks is not None else list(self.tasks)
        if not selected_tasks:
            selected_tasks = self.retrieve_tasks_from_owner(include_completed=False)

        return sorted(
            selected_tasks,
            key=lambda task: (
                self._coerce_time_value(task.due_time),
                -task.priority_score(),
                task.task_id,
            ),
        )

    def filter_tasks(
        self,
        tasks: Optional[list[Task]] = None,
        completed: Optional[bool] = None,
        pet_name: Optional[str] = None,
    ) -> list[Task]:
        """Filter tasks by completion state and/or pet name.

        Args:
            tasks: Optional source tasks. Falls back to scheduler memory and
                then owner tasks when no tasks are currently loaded.
            completed: If provided, keeps only tasks whose completed flag
                matches this value.
            pet_name: If provided, keeps only tasks assigned to a pet with an
                exact case-insensitive name match.

        Returns:
            A filtered task list preserving the original order.
        """
        selected_tasks = list(tasks) if tasks is not None else list(self.tasks)
        if not selected_tasks:
            selected_tasks = self.retrieve_tasks_from_owner(include_completed=True)

        filtered = selected_tasks

        if completed is not None:
            filtered = [task for task in filtered if task.completed is completed]

        if pet_name is not None:
            target = pet_name.strip().lower()
            filtered = [
                task
                for task in filtered
                if self.owner.get_pet(task.pet_id).name.lower() == target
            ]

        return filtered

    def detect_time_conflicts(self, tasks: Optional[list[Task]] = None) -> list[str]:
        """Detect exact due-time collisions and return warning messages.

        This is a lightweight conflict check: it only flags tasks that share
        the exact same due time and intentionally does not model duration
        overlaps or interval arithmetic.

        Args:
            tasks: Optional source tasks. Falls back to scheduler memory and
                then owner tasks when none are loaded.

        Returns:
            A list of human-readable warning strings. The list is empty when
            no exact-time conflicts are found.
        """
        selected_tasks = list(tasks) if tasks is not None else list(self.tasks)
        if not selected_tasks:
            selected_tasks = self.retrieve_tasks_from_owner(include_completed=False)

        tasks_by_time: dict[time, list[Task]] = defaultdict(list)
        for task in selected_tasks:
            due = task.due_time
            if due is None:
                continue
            tasks_by_time[due].append(task)

        warnings: list[str] = []
        for due, grouped_tasks in sorted(tasks_by_time.items(), key=lambda item: item[0]):
            if len(grouped_tasks) < 2:
                continue

            task_labels = [
                f"{self.owner.get_pet(task.pet_id).name}: {task.description}"
                for task in grouped_tasks
            ]
            warnings.append(
                (
                    f"Warning: {len(grouped_tasks)} tasks are scheduled at "
                    f"{due.strftime('%H:%M')} -> "
                    f"{'; '.join(task_labels)}"
                )
            )

        return warnings

    def _find_task(self, task_id: str) -> Task:
        """Locate a task by ID across all owner tasks."""
        for task in self.owner.get_all_tasks(include_completed=True):
            if task.task_id == task_id:
                return task
        raise KeyError(f"task '{task_id}' not found")

    def _next_recurring_task_id(self, base_task_id: str) -> str:
        """Create a unique task ID for the next recurring occurrence."""
        existing_ids = {
            task.task_id for task in self.owner.get_all_tasks(include_completed=True)
        }
        index = 1
        while True:
            candidate = f"{base_task_id}__r{index}"
            if candidate not in existing_ids:
                return candidate
            index += 1

    def complete_task(self, task_id: str) -> Optional[Task]:
        """Complete one task and create next occurrence for daily recurrence.

        Returns:
            The newly created recurring task when applicable; otherwise None.
        """
        task = self._find_task(task_id)
        if task.completed:
            return None

        task.mark_completed()
        if task.frequency.lower() != "daily":
            return None

        next_task = Task(
            task_id=self._next_recurring_task_id(task.task_id),
            pet_id=task.pet_id,
            description=task.description,
            category=task.category,
            duration_minutes=task.duration_minutes,
            priority=task.priority,
            frequency=task.frequency,
            due_time=task.due_time,
            time_window=task.time_window,
            is_mandatory=task.is_mandatory,
            completed=False,
        )
        self.add_task(next_task)
        return next_task

    def rank_tasks(self) -> list[Task]:
        """Return tasks sorted by urgency/priority and constraints."""
        if not self.tasks:
            self.retrieve_tasks_from_owner(include_completed=False)

        def due_time_key(task: Task) -> time:
            # Keep tasks without a due time toward the end.
            return task.due_time if task.due_time is not None else time.max

        return sorted(
            self.tasks,
            key=lambda task: (
                not task.is_mandatory,
                -task.priority_score(),
                due_time_key(task),
            ),
        )

    def build_daily_plan(self) -> list[Task]:
        """Select and order tasks that fit the owner's daily constraints."""
        remaining_minutes = self.owner.available_minutes_per_day
        selected: list[Task] = []

        for task in self.rank_tasks():
            if task.completed:
                continue
            if task.is_feasible(remaining_minutes):
                selected.append(task)
                remaining_minutes -= task.duration_minutes

        return selected

    def explain_plan(self, plan: list[Task]) -> str:
        """Describe why each task was included and how ordering was decided."""
        if not plan:
            return "No tasks were scheduled."

        lines: list[str] = ["Today's plan was built by priority, required status, and available time:"]
        for index, task in enumerate(plan, start=1):
            required_tag = "mandatory" if task.is_mandatory else "optional"
            lines.append(
                (
                    f"{index}. {task.description} "
                    f"({task.duration_minutes} min, {task.priority} priority, {required_tag})"
                )
            )
        return "\n".join(lines)


class DailyScheduler(Scheduler):
    """Compatibility alias while transitioning naming to Scheduler."""

    pass


@dataclass
class AgentAction:
    type: str
    reason: str = ""
    pet_name: Optional[str] = None
    task: dict[str, Any] = field(default_factory=dict)
    log_message: str = ""


@dataclass
class AgentPlan:
    intent: str
    summary: str
    actions: list[AgentAction] = field(default_factory=list)


class PetHealthKnowledgeBase:
    def __init__(self, file_path: str = PET_HEALTH_DATA_FILE) -> None:
        self.file_path = file_path
        self.entries = self._load_entries()

    def _load_entries(self) -> dict[str, str]:
        if not os.path.exists(self.file_path):
            return {}
        with open(self.file_path, "r", encoding="utf-8") as file:
            raw_data = json.load(file)
        return {str(key).lower(): str(value) for key, value in raw_data.items()}

    def search(self, user_input: str) -> dict[str, str]:
        user_text = user_input.lower()
        matches: dict[str, str] = {}
        for keyword, guideline in self.entries.items():
            if keyword in user_text:
                matches[keyword] = guideline
        return matches


class OpenAIPlanClient:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model

    @classmethod
    def from_environment(cls) -> Optional["OpenAIPlanClient"]:
        if not os.getenv("OPENAI_API_KEY"):
            return None
        try:
            import openai  # type: ignore[import-not-found]
        except ImportError:
            return None
        return cls(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    def generate_plan(self, user_input: str, context: dict[str, Any]) -> str:
        from openai import OpenAI  # type: ignore[import-not-found]

        client = OpenAI()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a pet health planning agent. Return JSON only with keys "
                    "intent, summary, and actions. Each action should include a type, "
                    "reason, pet_name, and any execution fields."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"user_input": user_input, "context": context}, indent=2),
            },
        ]
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content or "{}"


class RuleBasedPlanner:
    def generate_plan(self, prompt: str, context: dict[str, Any]) -> str:
        user_input = context.get("user_input", "").lower()
        retrieved = context.get("retrieved_guidelines", {})
        pet = context.get("pet", {})
        recent_logs = context.get("recent_logs", [])

        actions: list[dict[str, Any]] = []
        for keyword, guideline in retrieved.items():
            if keyword in {"lethargy", "appetite", "itching"}:
                actions.append(
                    {
                        "type": "add_task",
                        "reason": f"Retrieved guideline for {keyword}: {guideline}",
                        "pet_name": pet.get("name"),
                        "task": {
                            "description": "Schedule Vet Visit",
                            "category": "health",
                            "duration_minutes": 20,
                            "priority": "high",
                            "frequency": "once",
                            "is_mandatory": True,
                        },
                    }
                )
                break

        if "log" in user_input or recent_logs:
            actions.append(
                {
                    "type": "add_log",
                    "reason": "Update the pet record with the latest health summary.",
                    "pet_name": pet.get("name"),
                    "log_message": "Recent symptom review completed.",
                }
            )

        if not actions:
            actions.append({"type": "add_log", "reason": "No urgent symptom matched.", "pet_name": pet.get("name"), "log_message": "No care escalation required."})

        return json.dumps(
            {
                "intent": "health_coordination",
                "summary": "Compare retrieved health guidance with recent pet logs and trigger the safest next step.",
                "actions": actions,
            }
        )


class PetCareSystem:
    def __init__(self, owner: Owner, knowledge_base: Optional[PetHealthKnowledgeBase] = None, llm_client: Any | None = None) -> None:
        self.owner = owner
        self.scheduler = Scheduler(owner)
        self.knowledge_base = knowledge_base or PetHealthKnowledgeBase()
        self.llm_client = llm_client or OpenAIPlanClient.from_environment() or RuleBasedPlanner()

    def add_task(self, task: Task) -> None:
        self.scheduler.add_task(task)

    def add_log(self, pet_id: str, message: str) -> None:
        self.owner.get_pet(pet_id).add_log(message)

    def coordinate_pet_care(self, user_input: str) -> str:
        try:
            retrieved_guidelines = self.knowledge_base.search(user_input)
            pet = self._resolve_pet_from_input(user_input)
            recent_logs = list(pet.care_notes[-5:])

            llm_input = {
                "user_input": user_input,
                "retrieved_guidelines": retrieved_guidelines,
                "recent_logs": recent_logs,
                "pet": {
                    "pet_id": pet.pet_id,
                    "name": pet.name,
                    "species": pet.species,
                    "age_years": pet.age_years,
                },
            }

            raw_plan = self._generate_plan(user_input, llm_input)
            plan = self._parse_plan(raw_plan)

            actions_taken: list[str] = []
            for action in plan.actions:
                if action.type == "add_task":
                    task = self._build_task_from_action(action, pet.pet_id)
                    self.add_task(task)
                    actions_taken.append(f"added task '{task.description}'")
                elif action.type == "add_log":
                    log_message = action.log_message or plan.summary
                    self.add_log(pet.pet_id, log_message)
                    actions_taken.append("updated pet log")
                else:
                    raise ValueError(f"Unsupported action type: {action.type}")

            cited_guideline = next(iter(retrieved_guidelines.values()), "No direct guideline matched.")
            actions_text = ", ".join(actions_taken) if actions_taken else "no actions were needed"
            return (
                f"Guideline cited: {cited_guideline} "
                f"Analysis: {plan.summary}. "
                f"Actions taken: {actions_text}."
            )
        except Exception as exc:
            _SYSTEM_LOGGER.exception("AI_PLANNING_FAILURE")
            return f"I could not complete care coordination safely. AI_PLANNING_FAILURE: {exc}"

    def _generate_plan(self, user_input: str, context: dict[str, Any]) -> str:
        if self.llm_client is None:
            return RuleBasedPlanner().generate_plan(user_input, context)

        return self.llm_client.generate_plan(user_input=user_input, context=context)

    def ask_gemini_for_plan(self, user_question: str) -> dict[str, Any]:
        """Attempt to call Gemini (google-generativeai) with retrieved snippets.

        Edge cases handled:
        - If the KB has no matching snippets, include a short note and still query Gemini
          asking for conservative next steps.
        - If the `google.generativeai` package is missing or the call fails, return
          a structured error and log `AI_PLANNING_FAILURE` to the system log.
        - If the model returns non-JSON or parsing fails, log and return an error.
        """
        retrieved = self.knowledge_base.search(user_question)
        snippets = retrieved if retrieved else {"_note": "No KB match found"}

        try:
            import google.generativeai as genai  # type: ignore
            from google.generativeai.types import GenerationConfig  # type: ignore

            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)

            model = genai.GenerativeModel("gemini-2.5-flash-lite")

            prompt = (
                "You are a conservative pet-health coordinator.\n\n"
                "Knowledge snippets (only include the matching snippets):\n"
                f"{json.dumps(snippets, indent=2)}\n\n"
                "User question:\n"
                f"{user_question}\n\n"
                "Return JSON only with keys: intent, summary, retrieved_guideline, actions."
            )

            gen_cfg = GenerationConfig(response_mime_type="application/json", temperature=0.2)
            response = model.generate_content(prompt, generation_config=gen_cfg)

            # Different client versions expose the content differently; check common attrs.
            text = None
            if hasattr(response, "text"):
                text = response.text
            elif hasattr(response, "content"):
                text = response.content
            elif isinstance(response, str):
                text = response

            if not text:
                raise ValueError("empty response from Gemini")

            try:
                parsed = json.loads(text)
                return parsed
            except json.JSONDecodeError:
                _SYSTEM_LOGGER.exception("AI_PLANNING_FAILURE")
                return {"error": "malformed_json", "raw": text}

        except ImportError:
            _SYSTEM_LOGGER.info("google.generativeai not installed; skipping Gemini call")
            return {"error": "gemini_unavailable", "retrieved": retrieved}
        except Exception as exc:
            _SYSTEM_LOGGER.exception("AI_PLANNING_FAILURE")
            return {"error": "AI_PLANNING_FAILURE", "detail": str(exc)}

    def _parse_plan(self, raw_plan: str) -> AgentPlan:
        try:
            data = json.loads(raw_plan)
        except json.JSONDecodeError as exc:
            raise ValueError("Malformed LLM output") from exc

        actions = [
            AgentAction(
                type=str(action.get("type", "add_log")),
                reason=str(action.get("reason", "")),
                pet_name=action.get("pet_name"),
                task=dict(action.get("task", {})),
                log_message=str(action.get("log_message", "")),
            )
            for action in data.get("actions", [])
        ]
        return AgentPlan(
            intent=str(data.get("intent", "health_coordination")),
            summary=str(data.get("summary", "")),
            actions=actions,
        )

    def _build_task_from_action(self, action: AgentAction, fallback_pet_id: str) -> Task:
        return Task(
            task_id=self._next_task_id(),
            pet_id=self._resolve_pet_id(action.pet_name) or fallback_pet_id,
            description=str(action.task.get("description", "Schedule Vet Visit")),
            category=str(action.task.get("category", "health")),
            duration_minutes=int(action.task.get("duration_minutes", 20)),
            priority=str(action.task.get("priority", "high")),
            frequency=str(action.task.get("frequency", "once")),
            is_mandatory=bool(action.task.get("is_mandatory", True)),
        )

    def _resolve_pet_from_input(self, user_input: str) -> Pet:
        lower_input = user_input.lower()
        for pet in self.owner.pets.values():
            if pet.name.lower() in lower_input:
                return pet
        if self.owner.pets:
            return next(iter(self.owner.pets.values()))
        raise ValueError("No pets are available for care coordination")

    def _resolve_pet_id(self, pet_name: Optional[str]) -> Optional[str]:
        if not pet_name:
            return None
        for pet in self.owner.pets.values():
            if pet.name.lower() == pet_name.lower():
                return pet.pet_id
        return None

    def _next_task_id(self) -> str:
        existing_ids = [task.task_id for task in self.owner.get_all_tasks(include_completed=True)]
        max_index = 0
        for task_id in existing_ids:
            match = re.search(r"(\d+)$", task_id)
            if match:
                max_index = max(max_index, int(match.group(1)))
        return f"task_{max_index + 1:03d}"
