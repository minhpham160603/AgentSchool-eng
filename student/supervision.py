import json
import sys
from student.global_methods import *
sys.path.append("../../")

from student.prompt.run_ds_supervisor import *

async def supervise_exercise(student, knowledge_points_file, answer):
    """
    Check whether the student's answer uses knowledge appropriate for their grade.
    INPUT:
        student: student object
        knowledge_points_file: str, path to the knowledge-point data
        answer: dict, the student's answer
    OUTPUT:
        supervision: dict, monitoring results, including knowledge points and grade-level checks
        {
        "exceeds_grade": true or false,
        "used_which_grade_knowledge": "grade-level description",
        }
    """
    # Read knowledge point files
    with open(knowledge_points_file, 'r', encoding='utf-8') as f:
        knowledge_points = json.load(f)

    # Check the student's response against the knowledge-point data.
    print("\n--- Exercise supervision started ---")
    supervision = await run_ds_supervise_exercise(knowledge_points, answer)
    supervision["exceeds_grade"] = compare_grade_terms(student.scratch.grade, supervision["grade"])
    print(f"Supervision results: {supervision}")
    print("--- Exercise supervision finished ---\n")
    return supervision


async def supervise_knowledge_used(knowledge_points, student_answer, question):
    """
    Decide whether the student used each supplied knowledge point appropriately for the question.
    INPUT:
        knowledge_points: list, knowledge points identified in the student's work
        student_answer: str, the student's answer
        question: str, the exercise prompt

    OUTPUT:
        dict, mapping each knowledge point to "used" or "missed". "used" means it was applied appropriately; "missed" means it was not appropriately used for this question.
        {
        "knowledge_point_1": "used",
        "knowledge_point_2": "missed",
        ...
        }
    """
    supervision = await run_ds_check_knowledge_used(knowledge_points, student_answer, question)
    print(f"Knowledge-point usage analysis: {supervision}")
    return supervision
