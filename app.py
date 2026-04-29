import streamlit as st
import hashlib
from datetime import time

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

from pawpal_system import Owner, Pet, PetCareSystem, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")


def _format_due_time(value: time | None) -> str:
    """Render due times consistently for tables and warnings."""
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return "No due time"

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

# Persist backend objects across Streamlit reruns.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(owner_id="owner_001", name="Jordan")

if "scheduler" not in st.session_state:
    st.session_state.scheduler = Scheduler(st.session_state.owner)

if "care_system" not in st.session_state:
    st.session_state.care_system = PetCareSystem(st.session_state.owner)

if "uploaded_record_count" not in st.session_state:
    st.session_state.uploaded_record_count = 0

if "uploaded_record_hashes" not in st.session_state:
    st.session_state.uploaded_record_hashes = set()

st.subheader("Smart Health Coordinator")
st.caption("Retrieve pet health guidance, compare it with recent logs and uploaded records, and automate follow-up actions.")

if st.session_state.owner.pets:
    upload_pet_id = st.selectbox(
        "Associate uploaded medical record with pet",
        options=list(st.session_state.owner.pets.keys()),
        format_func=lambda pid: f"{st.session_state.owner.pets[pid].name} ({pid})",
        key="medical_record_pet",
    )
    uploaded_file = st.file_uploader(
        "Upload a medical record or discharge note",
        type=["txt", "md", "json", "csv"],
    )

    if uploaded_file is not None:
        record_bytes = uploaded_file.read()
        record_hash = hashlib.sha256(record_bytes).hexdigest()
        if record_hash not in st.session_state.uploaded_record_hashes:
            record_text = record_bytes.decode("utf-8", errors="ignore")
            st.session_state.care_system.ingest_medical_record(
                pet_id=upload_pet_id,
                source_name=uploaded_file.name,
                content=record_text,
            )
            st.session_state.uploaded_record_hashes.add(record_hash)
            st.session_state.uploaded_record_count += 1
            st.success(f"Uploaded record saved for {st.session_state.owner.get_pet(upload_pet_id).name}.")
        else:
            st.info("This medical record was already loaded during this session.")

    if st.session_state.uploaded_record_count:
        st.info(f"Loaded {st.session_state.uploaded_record_count} uploaded medical record(s) into hybrid RAG.")
else:
    st.info("Add a pet first to attach uploaded medical records to a profile.")

health_request = st.text_area(
    "Describe the concern",
    value="Buddy has been lethargic and has not eaten in 12 hours",
    height=100,
)

if st.button("Coordinate pet care"):
    if not st.session_state.owner.pets:
        st.warning("Add a pet first so the coordinator can act on a real profile.")
    else:
        coordinator_response = st.session_state.care_system.coordinate_pet_care(health_request)
        st.success(coordinator_response)

st.divider()

st.subheader("Owner and Pets")
owner_name = st.text_input("Owner name", value=st.session_state.owner.name)

if "task_counter" not in st.session_state:
    st.session_state.task_counter = 1

if "pet_counter" not in st.session_state:
    st.session_state.pet_counter = 1

if "selected_pet_id" not in st.session_state:
    st.session_state.selected_pet_id = None

# Keep the persistent objects in sync with editable UI fields.
st.session_state.owner.name = owner_name

with st.form("add_pet_form"):
    new_pet_name = st.text_input("Pet name", value="Mochi")
    new_pet_species = st.selectbox("Species", ["dog", "cat", "other"])
    new_pet_age = st.number_input("Pet age (years)", min_value=0, max_value=40, value=1)
    add_pet_clicked = st.form_submit_button("Add pet")

if add_pet_clicked:
    pet_id = f"pet_{st.session_state.pet_counter:03d}"
    pet = Pet(
        pet_id=pet_id,
        owner_id=st.session_state.owner.owner_id,
        name=new_pet_name,
        species=new_pet_species,
        age_years=int(new_pet_age),
    )
    st.session_state.owner.add_pet(pet)
    st.session_state.pet_counter += 1
    st.session_state.selected_pet_id = pet_id
    st.success(f"Added pet: {pet.name}")

if st.session_state.owner.pets:
    pets_table = [
        {
            "pet_id": pet.pet_id,
            "name": pet.name,
            "species": pet.species,
            "age_years": pet.age_years,
        }
        for pet in st.session_state.owner.pets.values()
    ]
    st.write("Current pets:")
    st.table(pets_table)
else:
    st.info("No pets yet. Add one above.")

st.markdown("### Tasks")
st.caption("Add tasks to a selected pet. These are stored in your backend objects.")

pet_options = list(st.session_state.owner.pets.keys())
selected_pet_id = st.selectbox(
    "Assign task to pet",
    options=pet_options,
    format_func=lambda pid: f"{st.session_state.owner.pets[pid].name} ({pid})",
    index=0 if pet_options else None,
    disabled=not pet_options,
)

col1, col2, col3 = st.columns(3)
with col1:
    task_title = st.text_input("Task title", value="Morning walk")
with col2:
    duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
with col3:
    priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

is_mandatory = st.checkbox("Mandatory task", value=False)
set_due_time = st.checkbox("Set due time", value=True)
due_time_value = st.time_input("Due time", value=time(9, 0), disabled=not set_due_time)

if st.button("Add task"):
    if not selected_pet_id:
        st.warning("Add a pet first, then assign a task.")
    else:
        task = Task(
            task_id=f"task_{st.session_state.task_counter:03d}",
            pet_id=selected_pet_id,
            description=task_title,
            category="general",
            duration_minutes=int(duration),
            priority=priority,
            is_mandatory=is_mandatory,
            due_time=due_time_value if set_due_time else None,
        )
        st.session_state.owner.add_task_to_pet(selected_pet_id, task)
        st.session_state.task_counter += 1
        st.session_state.scheduler.retrieve_tasks_from_owner(include_completed=False)
        st.success(f"Added task '{task.description}' to {st.session_state.owner.get_pet(selected_pet_id).name}.")

all_tasks = st.session_state.owner.get_all_tasks(include_completed=True)
if all_tasks:
    status_filter = st.selectbox(
        "Filter by status",
        options=["All", "Incomplete only", "Completed only"],
        index=1,
    )
    pet_filter_options = ["All pets"] + [
        pet.name for pet in st.session_state.owner.pets.values()
    ]
    pet_filter = st.selectbox("Filter by pet", options=pet_filter_options, index=0)

    completed_filter = None
    if status_filter == "Incomplete only":
        completed_filter = False
    elif status_filter == "Completed only":
        completed_filter = True

    selected_pet_name = None if pet_filter == "All pets" else pet_filter
    sorted_tasks = st.session_state.scheduler.sort_by_time(tasks=all_tasks)
    filtered_tasks = st.session_state.scheduler.filter_tasks(
        tasks=sorted_tasks,
        completed=completed_filter,
        pet_name=selected_pet_name,
    )

    task_table = [
        {
            "task_id": task.task_id,
            "pet": st.session_state.owner.get_pet(task.pet_id).name,
            "description": task.description,
            "due_time": _format_due_time(task.due_time),
            "duration_minutes": task.duration_minutes,
            "priority": task.priority,
            "mandatory": task.is_mandatory,
            "completed": task.completed,
        }
        for task in filtered_tasks
    ]

    active_sorted_tasks = st.session_state.scheduler.sort_by_time(
        tasks=st.session_state.owner.get_all_tasks(include_completed=False)
    )
    conflict_warnings = st.session_state.scheduler.detect_time_conflicts(
        tasks=active_sorted_tasks
    )

    if conflict_warnings:
        st.warning("Scheduling conflicts detected. Review these time collisions:")
        for warning in conflict_warnings:
            st.warning(
                f"{warning} Consider staggering one task by 10-15 minutes for smoother care."
            )
    else:
        st.success("No time conflicts detected in active tasks.")

    st.write("Current tasks (sorted and filtered):")
    if task_table:
        st.table(task_table)
    else:
        st.info("No tasks match the selected filters.")
else:
    st.info("No tasks yet. Add one above.")

st.divider()

st.subheader("Build Schedule")
st.caption("Generate a plan from persisted Owner/Pet/Task objects.")

if st.button("Generate schedule"):
    st.session_state.scheduler.retrieve_tasks_from_owner(include_completed=False)
    plan = st.session_state.scheduler.build_daily_plan()
    plan_conflicts = st.session_state.scheduler.detect_time_conflicts(tasks=plan)

    if plan:
        schedule_table = [
            {
                "pet": st.session_state.owner.get_pet(task.pet_id).name,
                "task": task.description,
                "due_time": _format_due_time(task.due_time),
                "duration_minutes": task.duration_minutes,
                "priority": task.priority,
                "mandatory": task.is_mandatory,
            }
            for task in plan
        ]
        st.success("Schedule generated successfully.")
        st.write("Today's Schedule:")
        st.table(schedule_table)
        if plan_conflicts:
            st.warning("Heads up: this plan has time conflicts that may be stressful for pets.")
            for warning in plan_conflicts:
                st.warning(warning)
        st.text(st.session_state.scheduler.explain_plan(plan))
    else:
        st.info("No schedulable tasks found. Add pets/tasks first.")
