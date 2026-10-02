import sys
import ast
import json
from sentence_transformers import SentenceTransformer

sys.path.append("../../")

from student.global_methods import *
from student.prompt.utils import *
from student.prompt.utils import *
from util.model import call_LLM

system_content = """
You are an education research specialist. Assess student answers and use of knowledge based only on the student response, exercise, and knowledge-point data provided. The available curriculum data covers grades 1–9.

Follow the requested task and output schema exactly. Use only the supplied knowledge-point list when identifying concepts or grade levels. Do not invent concepts or infer unsupported curriculum details. Be neutral, concise, and precise. Write all natural-language output in English. Use canonical grade labels such as "Grade 7 Term 1"; keep JSON keys and enum values exactly as specified. When JSON is requested, return only valid JSON without comments, trailing commas, or text outside the JSON object.
"""

async def run_ds_supervise_exercise(knowledge_points, student_answer):
    """
    On the basis of the student' s answers and summary of knowledge points, it is judged whether the student used a knowledge point beyond his or her grade。
    INPUT:
        knowledge_points: dict，Outline of knowledge points covering compulsory education throughout the country
        student_answer: str，Students' answers
    OUTPUT:
        dict，Include knowledge points and reasons for overstepping, using grade
        {
        "exceeds_grade": true or false,
        "used_which_grade_knowledge": "X Grade",
        "reason": "Simplicity and clear explanation of why it has crossed or not"
        }
    """
    prompt = f"""
Determine which supplied knowledge points the student used and the grade and term assigned to those points in the provided data.

Knowledge-point data: {knowledge_points}
Student answer: {student_answer}

Use only the supplied data. Return a JSON object with exactly these fields:
{{
  "grade": "Grade N Term 1" or "Grade N Term 2",
  "knowledge_points": "The matching knowledge point or points"
}}

Use a canonical English grade label, such as "Grade 7 Term 1". If the data does not support a grade or concept, state that briefly in the corresponding value. Return only the JSON object.
"""

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt}
    ]


    # Read json , return the error message if the format is wrong
    try:
        # response = call_deepseek(messages, response_format=True)
        response_format = {
        'type': 'json_object'
        }

        response = await call_LLM("student", messages, response_format)
        result = json.loads(response)
    except json.JSONDecodeError as e:
        print(response)
        return {"error": "Returned JSON format error, check input data and model output。", "details": str(e)}

    return result

async def run_ds_check_knowledge_used(knowledge_points, student_answer, question):
    """
    Based on the students' answers, and the knowledge points they use, the question of whether this knowledge point should be used。
    INPUT:
        knowledge_points: list, List of knowledge points used by students on this topic
        student_answer: str，Students' answers
        question: str，Subject content

    OUTPUT:
        dict, Key as each knowledge point entered, the value is enum[used, missed]。used Delegates used the right knowledge points on the topic，missed Explain that this knowledge point should not be used in this topic。
        {
        "knowledge_point_1": "used",
        "knowledge_point_2": "missed",
        ...
        }
    """
    prompt = f"""
For each listed knowledge point, decide whether it is needed to solve the exercise and whether the student used it appropriately.

Knowledge-point list: {knowledge_points}
Student answer: {student_answer}
Exercise: {question}

Return a JSON object whose keys are the knowledge points exactly as listed and whose values are exactly "used" or "missed". Use "used" when the student applied that point appropriately; otherwise use "missed". Return only valid JSON, with no comments or text outside the object.
"""

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt}
    ]


    # Read json , return the error message if the format is wrong
    try:
        # response = call_deepseek(messages, response_format=True)
        response_format = {
        'type': 'json_object'
        }

        response = await call_LLM("student", messages, response_format)
        result = json.loads(response)
        return result
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parsing error [run_ds_check_knowledge_used]: {e}")
        if 'response' in locals():
            print(f"Original Response: {response}")
        return {"error": "Returned JSON format error, check input data and model output。", "details": str(e)}
    except Exception as e:
        print(f"❌ LLM Call Failed [run_ds_check_knowledge_used]: {e}")
        return {"error": "LLM Call Failed", "details": str(e)}
