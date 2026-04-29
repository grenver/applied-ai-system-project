#!/usr/bin/env python3
"""
Demo script for the Smart Health Coordinator upgrade.
Creates a sample owner, pets, tasks, and runs the new care coordination flow.
"""

from datetime import time

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

from pawpal_system import Owner, Pet, PetCareSystem, Task, Scheduler


def main():
    print("=" * 60)
    print("🐾 PawPal+ Demo: Building Today's Schedule")
    print("=" * 60)

    # Create Owner
    owner = Owner(
        owner_id="owner_001",
        name="Jordan",
        available_minutes_per_day=120,
        preferences={"prefer_morning_walks": True},
    )
    print(f"\n📋 Owner: {owner.name} ({owner.available_minutes_per_day} min available)\n")

    # Create Pets
    dog = Pet(
        pet_id="pet_001",
        owner_id="owner_001",
        name="Mochi",
        species="dog",
        age_years=3,
    )
    dog.add_care_note("Needs morning walk before 9 AM")

    cat = Pet(
        pet_id="pet_002",
        owner_id="owner_001",
        name="Whiskers",
        species="cat",
        age_years=5,
    )
    cat.add_care_note("Prefers afternoon play session")

    owner.add_pet(dog)
    owner.add_pet(cat)

    print(f"🐕 Pet 1: {dog.get_profile_summary()}")
    print(f"  Notes: {'; '.join(dog.care_notes)}")
    print(f"\n🐈 Pet 2: {cat.get_profile_summary()}")
    print(f"  Notes: {'; '.join(cat.care_notes)}\n")

    # Create Tasks for Mochi (dog)
    dog_walk = Task(
        task_id="task_001",
        pet_id="pet_001",
        description="Morning walk",
        category="exercise",
        duration_minutes=30,
        priority="high",
        frequency="daily",
        due_time=time(9, 0),
        is_mandatory=True,
    )

    dog_feed = Task(
        task_id="task_002",
        pet_id="pet_001",
        description="Feeding (breakfast)",
        category="feeding",
        duration_minutes=10,
        priority="high",
        frequency="daily",
        due_time=time(8, 0),
        is_mandatory=True,
    )

    dog_play = Task(
        task_id="task_003",
        pet_id="pet_001",
        description="Playtime",
        category="enrichment",
        duration_minutes=20,
        priority="medium",
        frequency="daily",
    )

    # Create Tasks for Whiskers (cat)
    cat_feed = Task(
        task_id="task_004",
        pet_id="pet_002",
        description="Feeding (breakfast)",
        category="feeding",
        duration_minutes=5,
        priority="high",
        frequency="daily",
        due_time=time(9, 0),
        is_mandatory=True,
    )

    cat_play = Task(
        task_id="task_005",
        pet_id="pet_002",
        description="Afternoon play session",
        category="enrichment",
        duration_minutes=25,
        priority="high",
        frequency="daily",
        due_time=time(14, 0),
    )

    # Add tasks intentionally out of order to test sorting.
    owner.add_task_to_pet("pet_001", dog_play)
    owner.add_task_to_pet("pet_002", cat_play)
    owner.add_task_to_pet("pet_001", dog_walk)
    owner.add_task_to_pet("pet_002", cat_feed)
    owner.add_task_to_pet("pet_001", dog_feed)

    print("📝 Tasks loaded:")
    all_tasks = owner.get_all_tasks()
    for task in all_tasks:
        print(f"  - {task.description} ({task.duration_minutes} min, {task.priority})")

    # Mark one task completed so completion filtering has visible behavior.
    dog_play.mark_completed()

    # Create Scheduler and build today's plan
    scheduler = Scheduler(owner)
    scheduler.retrieve_tasks_from_owner(include_completed=True)

    print("\n🕒 Tasks sorted by due time:")
    for task in scheduler.sort_by_time():
        due_label = task.due_time.strftime("%H:%M") if task.due_time else "No due time"
        pet_name = owner.get_pet(task.pet_id).name
        print(f"  - {due_label:>8} | {pet_name:<8} | {task.description}")

    print("\n✅ Completed tasks only:")
    for task in scheduler.filter_tasks(completed=True):
        pet_name = owner.get_pet(task.pet_id).name
        print(f"  - {pet_name}: {task.description}")

    print("\n🐕 Tasks for Mochi only:")
    for task in scheduler.filter_tasks(pet_name="Mochi"):
        status = "done" if task.completed else "pending"
        print(f"  - {task.description} ({status})")

    print("\n⚠️ Conflict check:")
    conflict_warnings = scheduler.detect_time_conflicts()
    if conflict_warnings:
        for warning in conflict_warnings:
            print(f"  - {warning}")
    else:
        print("  - No time conflicts found.")

    scheduler.retrieve_tasks_from_owner(include_completed=False)
    plan = scheduler.build_daily_plan()

    print("\n" + "=" * 60)
    print("📅 TODAY'S SCHEDULE")
    print("=" * 60)

    if plan:
        explanation = scheduler.explain_plan(plan)
        print(explanation)

        total_minutes = sum(task.duration_minutes for task in plan)
        remaining = owner.available_minutes_per_day - total_minutes
        print(f"\n⏱️  Total scheduled: {total_minutes} min")
        print(f"⏱️  Remaining buffer: {remaining} min")
    else:
        print("No tasks fit in today's schedule.")

    print("\n" + "=" * 60)
    print("🩺 SMART HEALTH COORDINATION")
    print("=" * 60)

    care_system = PetCareSystem(owner)
    response = care_system.coordinate_pet_care(
        "Buddy has been lethargic and has not eaten in 12 hours"
    )
    print(response)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
