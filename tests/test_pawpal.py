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