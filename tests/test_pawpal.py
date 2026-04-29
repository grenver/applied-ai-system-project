import json
import tempfile
import unittest
from pathlib import Path

from pawpal_system import Owner, Pet, PetCareSystem, PetHealthKnowledgeBase, Task


class StubLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate_plan(self, user_input: str, context: dict) -> str:
        return self.response


class PawPalSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = Owner(owner_id="owner_001", name="Jordan")
        self.pet = Pet(
            pet_id="pet_001",
            owner_id="owner_001",
            name="Buddy",
            species="dog",
            age_years=3,
        )
        self.owner.add_pet(self.pet)

    def test_knowledge_base_retrieves_matching_guideline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            kb_path = Path(tmp_dir) / "pet_health_data.json"
            kb_path.write_text(
                json.dumps({"lethargy": "Low energy can signal illness."}),
                encoding="utf-8",
            )

            kb = PetHealthKnowledgeBase(file_path=str(kb_path))
            matches = kb.search("Buddy has lethargy today")

            self.assertIn("lethargy", matches)
            self.assertEqual(matches["lethargy"], "Low energy can signal illness.")

    def test_batch_test_cases_cover_common_symptoms(self) -> None:
        cases_path = Path(__file__).with_name("test_cases.json")
        cases = json.loads(cases_path.read_text(encoding="utf-8"))

        kb = PetHealthKnowledgeBase(file_path="pet_health_data.json")

        for case in cases:
            with self.subTest(case=case["name"]):
                matches = kb.search(case["input"])
                self.assertEqual(sorted(matches.keys()), sorted(case["expected_guidelines"]))

    def test_coordinate_pet_care_adds_task_from_plan(self) -> None:
        plan = json.dumps(
            {
                "intent": "health_coordination",
                "summary": "Schedule a follow-up visit.",
                "actions": [
                    {
                        "type": "add_task",
                        "reason": "The symptom is serious enough to warrant a vet check.",
                        "pet_name": "Buddy",
                        "task": {
                            "description": "Schedule Vet Visit",
                            "category": "health",
                            "duration_minutes": 20,
                            "priority": "high",
                            "frequency": "once",
                            "is_mandatory": True,
                        },
                    }
                ],
            }
        )

        system = PetCareSystem(self.owner, llm_client=StubLLMClient(plan))
        response = system.coordinate_pet_care("Buddy has been lethargic")

        self.assertIn("Guideline cited:", response)
        self.assertIn("Schedule Vet Visit", response)
        self.assertEqual(len(self.owner.get_all_tasks(include_completed=True)), 1)
        self.assertEqual(self.owner.get_all_tasks(include_completed=True)[0].description, "Schedule Vet Visit")

    def test_coordinate_pet_care_uses_alias_retrieval(self) -> None:
        system = PetCareSystem(self.owner, llm_client=StubLLMClient(json.dumps({
            "intent": "health_coordination",
            "summary": "Schedule a follow-up visit.",
            "actions": [
                {
                    "type": "add_task",
                    "reason": "Alias-based symptom match should still trigger a task.",
                    "pet_name": "Buddy",
                    "task": {
                        "description": "Schedule Vet Visit",
                        "category": "health",
                        "duration_minutes": 20,
                        "priority": "high",
                        "frequency": "once",
                        "is_mandatory": True,
                    },
                }
            ],
        })))

        response = system.coordinate_pet_care("Mochi has been lethargic and has not eaten in 12 hours")

        self.assertIn("Ensure they are hydrated", response)
        self.assertIn("Schedule Vet Visit", response)

    def test_hybrid_context_includes_uploaded_medical_record(self) -> None:
        system = PetCareSystem(self.owner, llm_client=StubLLMClient(json.dumps({
            "intent": "health_coordination",
            "summary": "Use both the static guideline and uploaded record.",
            "actions": [
                {
                    "type": "add_task",
                    "reason": "The uploaded record supports a follow-up.",
                    "pet_name": "Buddy",
                    "task": {
                        "description": "Review discharge note",
                        "category": "health",
                        "duration_minutes": 15,
                        "priority": "medium",
                        "frequency": "once",
                        "is_mandatory": False,
                    },
                }
            ],
        })))

        system.ingest_medical_record(
            pet_id="pet_001",
            source_name="discharge_note.txt",
            content="Recent discharge note: lethargy and poor appetite observed after treatment.",
        )

        context = system.retrieve_hybrid_context("Buddy has been lethargic and has not eaten", self.pet)
        self.assertIn("lethargy", context["retrieved_guidelines"])
        self.assertIn("record_001", context["medical_records"])

        response = system.coordinate_pet_care("Buddy has been lethargic and has not eaten")
        self.assertIn("Guideline cited:", response)
        self.assertIn("Uploaded record cited:", response)
        self.assertIn("Review discharge note", response)

    def test_coordinate_pet_care_logs_malformed_plan(self) -> None:
        system = PetCareSystem(self.owner, llm_client=StubLLMClient("not-json"))
        response = system.coordinate_pet_care("Buddy has been lethargic")

        self.assertIn("AI_PLANNING_FAILURE", response)

        log_path = Path("system.log")
        self.assertTrue(log_path.exists())
        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn("AI_PLANNING_FAILURE", log_text)


if __name__ == "__main__":
    unittest.main()