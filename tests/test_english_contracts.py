"""Check translated data and parser contracts without model downloads or API calls."""

import ast
import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest

from student.exercise_modifiers import PersonalizedQuestionModifier, extract_numbers
from student.global_methods import (
    compare_grade_terms,
    get_knowledge_points_from_json,
    parse_grade_term,
    translate_student_to_str,
)


ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def load_functions(path, names, namespace):
    """Load actual prompt/evaluation functions without their heavyweight startup imports."""
    source = ROOT / path
    tree = ast.parse(source.read_text())
    definitions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names
    ]
    if {node.name for node in definitions} != set(names):
        raise AssertionError(f"Missing function in {path}: {set(names)}")
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), "exec"), namespace)


class EnglishGradeTests(unittest.TestCase):
    def test_supported_grade_formats(self):
        cases = {
            "Grade 7 Term 1": (7, 1), "Grade 7 Term 2": (7, 2),
            "grade_9_term_2": (9, 2), "Grade 12 Term 1": (12, 1),
            "7": (7, 1), "\u4e03\u5e74\u7ea7\u4e0a": (7, 1),
            "\u4e03\u4e0b": (7, 2),
        }
        for label, expected in cases.items():
            with self.subTest(label=label):
                self.assertEqual(parse_grade_term(label), expected)

    def test_invalid_grade_is_not_a_valid_curriculum_position(self):
        for label in ("unknown", "Grade 0 Term 1", "Grade 99 Term 2", "Grade 7 Term 3"):
            with self.subTest(label=label):
                self.assertEqual(parse_grade_term(label), (-1, -1))

    def test_curriculum_order(self):
        self.assertTrue(compare_grade_terms("Grade 7 Term 1", "Grade 7 Term 2"))
        self.assertTrue(compare_grade_terms("Grade 7 Term 2", "Grade 8 Term 1"))
        self.assertFalse(compare_grade_terms("Grade 8 Term 1", "Grade 7 Term 2"))

    def test_default_profiles_resolve_real_knowledge_graph_nodes(self):
        graph = read_json("student/math_knowledge_points.json")
        expected = {n["id"] for n in graph["grade_7_term_1"]["nodes"]}
        self.assertGreater(len(expected), 10)
        for letter in "ABCD":
            profile = read_json(f"config/student/student{letter}.json")
            student = SimpleNamespace(scratch=SimpleNamespace(**profile))
            actual = get_knowledge_points_from_json(student, ROOT / "student/math_knowledge_points.json")
            self.assertEqual(set(actual), expected)
            self.assertTrue(all(not re.search(r"[\u3400-\u9fff]", name) for name, _ in actual.values()))


class EnglishProfileTests(unittest.TestCase):
    def test_profile_learning_style_contract(self):
        for letter in "ABCD":
            profile = read_json(f"config/student/student{letter}.json")
            self.assertEqual(set(profile["learning_style"]), {"perception", "processing", "understanding"})
            self.assertEqual(profile["grade"], "Grade 7 Term 1")

    def test_english_mistake_descriptions_still_trigger_personalization(self):
        profile = read_json("config/student/studentA.json")
        student = SimpleNamespace(scratch=SimpleNamespace(**profile))
        levels = PersonalizedQuestionModifier(student).mistake_levels
        self.assertEqual(levels, {
            "careless_calculation": 3, "concept_confusion": 3,
            "shallow_understanding": 2, "overconfidence": 2,
            "impatience": 2, "surface_reading": 3,
        })

    def test_modification_preserves_answer_and_identifiers(self):
        profile = read_json("config/student/studentA.json")
        student = SimpleNamespace(scratch=SimpleNamespace(**profile))
        question = {"id": "q1", "question_id": "q1", "index": 4,
                    "content": "A car travels 90 meters. Find the distance.",
                    "answer": "90", "embedding": [0.1, 0.2], "options": ["90", "100"]}
        modified = PersonalizedQuestionModifier(student, base_prob=1.0, seed=2).modify_question(question, 0)
        for key in ("answer", "id", "question_id", "index", "embedding"):
            self.assertEqual(modified[key], question[key])
        self.assertIn("modification_info", modified)
        self.assertNotRegex(modified["content"], r"[\u3400-\u9fff]")

    def test_legacy_numeral_recognition_is_preserved(self):
        self.assertEqual(extract_numbers("12 and \u5341\u4e8c"), [("12", 12.0, False), ("\u5341\u4e8c", 12, True)])
        self.assertEqual(extract_numbers("\u4e24"), [("\u4e24", 2, True)])


class EnglishQuestionnaireTests(unittest.TestCase):
    def test_item_order_and_reverse_scoring_markers(self):
        bfi = read_json("student/big_five_inventory.json")["scales"][0]
        cognitive = read_json("student/cognitive_style_inventory.json")["scales"][0]
        self.assertEqual(len(bfi["questions"]), 60)
        self.assertEqual(len(cognitive["questions"]), 38)
        self.assertTrue(bfi["questions"][2].startswith("*"))
        self.assertTrue(cognitive["questions"][6].startswith("*"))
        self.assertEqual(cognitive["rating"]["forward_items"], "Yes=2, Uncertain=1, No=0")
        self.assertEqual(cognitive["rating"]["reverse_items"], "Yes=0, Uncertain=1, No=2")

    def test_question_bank_remains_loadable_as_json_lines(self):
        lines = (ROOT / "student/data.jsonl").read_text(encoding="utf-8").splitlines()
        questions = [json.loads(line) for line in lines if line.strip()]
        self.assertEqual(len(questions), 150)
        self.assertTrue(all(isinstance(question, dict) for question in questions))
        self.assertTrue(all("que_id" in question and "content" in question and "answer" in question
                            for question in questions))
        self.assertEqual(len({question["que_id"] for question in questions}), 150)

    def test_every_category_builds_an_english_prompt_and_saves_english_fields(self):
        captured = []

        async def model(role, messages, response_format=None):
            captured.append(messages)
            cognitive = "Category: Cognitive style inventory" in messages[-1]["content"]
            return json.dumps({"answer": "Yes" if cognitive else 4,
                               "reasoning": "The activity fits my learning preferences."})

        async def personality(student):
            return "{}"

        async def describe_rating(*args):
            return json.dumps(args[2])

        namespace = {"call_LLM": model, "translate_student_to_str": translate_student_to_str,
                     "format_req": "Return only valid JSON.", "json": json,
                     "run_ds_prompt_analyze_personality": personality,
                     "run_ds_prompt_describe_rate": describe_rating,
                     "demjson3": SimpleNamespace(decode=json.loads), "os": os, "time": time}
        load_functions("student/prompt/run_ds_prompt.py",
                       ["set_system_content", "_call_student_llm", "run_ds_prompt_evaluate"], namespace)
        load_functions("student/evaluate.py", ["evaluate", "save_evaluation_results"], namespace)
        profile = read_json("config/student/studentA.json")
        student = SimpleNamespace(name=profile["name"], scratch=SimpleNamespace(**profile))
        questionnaire = read_json("student/questionnaire.json")
        # One real item from each category crosses prompt construction, response parsing, and saving.
        scales = []
        for scale in questionnaire["scales"]:
            item = scale["questions"][0] if "questions" in scale else next(iter(scale["subcategories"].values()))[0]
            scales.append({k: v for k, v in scale.items() if k not in ("questions", "subcategories")} | {"questions": [item]})
        previous = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.chdir(directory)
                Path("questionnaire.json").write_text(json.dumps({"scales": scales}))
                with contextlib.redirect_stdout(io.StringIO()):
                    asyncio.run(namespace["evaluate"](student, "questionnaire.json", "test"))
                saved = json.loads(Path("stu_questionnaire/StudentA_evaluate_results_test.json").read_text())
        finally:
            os.chdir(previous)
        self.assertEqual(len(captured), 7)
        self.assertEqual(len(saved), 7)
        for index, (messages, answer) in enumerate(zip(captured, saved)):
            self.assertIn("English", messages[0]["content"])
            self.assertIn('"answer"', messages[-1]["content"])
            self.assertEqual(set(answer), {"question", "answer", "reasoning"})
            self.assertEqual(answer["answer"], "Yes" if index == 6 else 4)
        self.assertIn("Uncertain", captured[-1][-1]["content"])
        self.assertIn("reverse_items", captured[-1][-1]["content"])


class EnglishObserverTests(unittest.TestCase):
    def command(self, *args):
        return subprocess.run(["bash", str(ROOT / "send_command.sh"), *args],
                              text=True, capture_output=True, cwd=self.directory)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_help_is_english_and_does_not_write_a_command(self):
        result = self.command("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Usage:", result.stdout)
        self.assertNotRegex(result.stdout, r"[\u3400-\u9fff]")
        self.assertFalse((self.directory / "observer_cmd.json").exists())

    def test_command_payloads(self):
        cases = [("pause",), ("resume",), ("status",), ("exit",), ("rollback", "8", "2"),
                 ("rollback", "08", "02")]
        for args in cases:
            result = self.command(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads((self.directory / "observer_cmd.json").read_text())
            self.assertEqual(payload["command"], args[0])
            if args[0] == "rollback":
                self.assertEqual(payload["rollback"], {"turn": 8, "class": 2})

    def test_intervention_text_is_json_escaped(self):
        message = 'Ask students: "Why?"\nUse a short discussion.'
        result = self.command("intervene", message)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads((self.directory / "observer_cmd.json").read_text())
        self.assertEqual(payload["intervention"]["instruction"], message)

    def test_invalid_command_does_not_overwrite_existing_payload(self):
        self.command("pause")
        path = self.directory / "observer_cmd.json"
        before = path.read_bytes()
        for args in [("unknown",), ("rollback", "-1"), ("rollback", "8", "invalid"),
                     ("rollback", "0"), ("rollback", "8", "00")]:
            result = self.command(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
