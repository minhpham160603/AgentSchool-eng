import sys
sys.path.append("../../")

from student.cognitive_module.memory import *
from student.cognitive_module.scratch import *
from student.cognitive_module.student import *
from student.prompt.run_ds_prompt import *
from student.retrieve import *

async def generate_focus(student, n = 3):
    """
    Generate current focus。
    Generate the current focus based on retrieved memories，
    Specifically, it's the basis of the search LLM Generate three related issues
        student: Student Category
        n: int, Number of focus points generated
    OUTPUT:
        focus: list of strings containing generated focus questions
    """
    # Retrieving Current Memory
    nodes = [[i.last_accessed, i]
             for i in student.mem.seq_thought + student.mem.seq_knowledge]
    nodes.sort(key=lambda x: x[0], reverse=True)
    nodes = [i[1] for i in nodes]

    statements = ""
    for node in nodes[0: student.scratch.retention]:
        statements += node.content + "\n"

    return await run_ds_prompt_generate_focus(statements, n)

def reflection_trigger(student):
    """
    Whether to reflect or not。
    """
    if (student.scratch.importance_trigger_curr >= student.scratch.importance_trigger_max and
        [] != student.mem.seq_knowledge + student.mem.seq_thought):
        return True
    return False

def reset_reflection_trigger(student):
    """
    Reset Reflection Trigger。
    Current importance_trigger_current Reset to 0。
    """
    student.scratch.importance_trigger_curr = 0

async def run_reflect(student):
    """
    Practical reflection
    OUTPUT:
        thoughts: dict, {focus_point: ConceptNode Examples of categories(thought)}
    """
    thoughts = {}
    focus_points = await generate_focus(student, n=3)
    retrieved_mem = await further_retrieve(student, focus_points, n_count=10)

    # Each focus, think about it and put it in their memories
    for focus_point, nodes in retrieved_mem.items():
        print(f"Focus point: {focus_point}")
        xx = [i.embedding_key for i in nodes]
        for xxx in xx: print(f"Retrieved Memory: {xxx}")

        thought = await run_ds_prompt_reflect(student, focus_point, nodes)
        # Put the thought into memory
        importance = int(await run_ds_prompt_importance_thought(student, thought))
        student.scratch.accumulate_importance(importance)
        keywords = await run_ds_prompt_thought_keywords(thought)
        embedding_pair = (thought, await get_local_embedding(thought))
        thoughts[focus_point] = student.mem.add_thought(student.scratch.current_time, thought, keywords, importance,
                                embedding_pair)

    return thoughts


async def reflect(student, retrieved_mem):
    """
    Rethinking recovered memories。
    Generate new ideas based on the retrieved memories and keep them in them。
    INPUT:
        student: Student Category
        retrieved_mem: {Description of current node}: {Type of node retrieved: List of retrieved nodes}}
    OUTPUT:
        thoughts: dict mapping each focus point to its generated thought node
    """

    if reflection_trigger(student):
        print(f"--- {student.name} Start rethinking ---")
        thougts = await run_reflect(student)
        reset_reflection_trigger(student)
        for focus_point, thought in thougts.items():
            print(f"Focus point: {focus_point}; reflection: {thought.content}")
        print("Reflection complete. New thoughts have been saved to memory.")
        return thougts
    else:
        print(f"--- {student.name} No reflection ---")
        return None



async def adjust(student, feedback):
    """
    Adapting student learning strategies, stress and attention based on feedback。
    INPUT:
        student: Student Category
        feedback: string, Feedback content
    OUTPUT:
        None
    """
    student.scratch.obstacle_student()

    adjusted = await run_ds_prompt_adjust(student, feedback)
    print(f"Adjustments: {adjusted}")

async def analyze_exercise(student):
    """
    Analysis of students' work, identification of errors, reflections and adjustments。
    INPUT:
        student: Student Category
    OUTPUT:
        None
    """
    import os
    from pathlib import Path

    name = student.name
    results_base = f"results/{name}/"

    # 1. Locate the results folder.
    results_path = Path(results_base)
    if not results_path.exists():
        print(f"Results directory not found for {name}.")
        return None

    # Fetch all date folders, sort by date
    date_folders = [d for d in results_path.iterdir() if d.is_dir() and d.name.count('-') == 2]
    if not date_folders:
        print(f"No dated results folder found for {name}.")
        return None

    latest_date_folder = sorted(date_folders, key=lambda x: x.name)[-1]
    print(f"Using the latest results folder: {latest_date_folder.name}")

    # 2. At the latest date exercises Folder
    exercises_folder = latest_date_folder / "exercises"
    if not exercises_folder.exists():
        print(f"Exercises folder not found: {exercises_folder}")
        return None

    # 3. Find All final_true_concurrent Documentation
    final_files = list(exercises_folder.glob(f"{name}_exercise_results_final_true_concurrent_*.json"))
    if not final_files:
        print("No final concurrent exercise results file was found.")
        return None

    # 4. Sort by time stamp in file name, get latest
    latest_final_file = sorted(final_files, key=lambda x: x.stem.split('_')[-1])[-1]
    print(f"Using the latest concurrent exercise results file: {latest_final_file.name}")

    # 5. Read File Contents
    exercise_data = await read_exercise_file(str(latest_final_file))

    # Analysis of correct answers
    correct_answers = exercise_data['correct_answers']
    correct_answers_content = [answer['thought_process'] for answer in correct_answers]

    # print(f"Example of the reflection process for partial correct answers:{correct_answers_content[0:2]}")

    analyze_1 = await run_ds_prompt_analyze_exercise_correct(correct_answers_content)

    # Section for parsing wrong answers
    wrong_answers = exercise_data['wrong_answers']
    wrong_answers_content = [answer['thought_process'] for answer in wrong_answers]

    print(f"Examples of reasoning from incorrect answers: {wrong_answers_content[0:2]}")

    analyze_2 = await run_ds_prompt_analyze_exercise_wrong(wrong_answers_content)

    return analyze_1, analyze_2

async def read_exercise_file(exercise_file):
    """
    Read student files
    INPUT:
        exercise_file: str, File path for storing student data on the subject
    OUTPUT:
        exercise_data: dict, Include complete problem data
        {
            "correct_answers": [...],  # List of correct answers
            "wrong_answers": [...],     # List of incorrect answers
            "statistics": {...},        # Statistical information
            "raw_data": {...}          # Original complete data
        }
    """
    import json

    with open(exercise_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Extract detailed answers
    detailed_answers = raw_data.get('data', {}).get('detailed_answers', {})

    # Category stores correct and wrong answers
    correct_answers = []
    wrong_answers = []

    for question_id, answer_data in detailed_answers.items():
        if not isinstance(answer_data, dict):
            continue

        # Build a monograph data structure
        question_record = {
            'question_id': answer_data.get('question_id', question_id),
            'question': answer_data.get('question', ''),
            'student_answer': answer_data.get('answer', ''),
            'correct_answer': answer_data.get('correct_answer', ''),
            'is_correct': answer_data.get('correct', False),
            'thought_process': answer_data.get('thought_process', ''),
            'retrieved_memories': answer_data.get('retrieved_memories', []),
            'retrieved_memories_count': answer_data.get('retrieved_memories_count', 0),
            'memory_summary': answer_data.get('memory_summary', ''),
            'misconceptions': answer_data.get('misconceptions', []),
            'processing_time': answer_data.get('processing_time', 0),
            'timestamp': answer_data.get('timestamp', '')
        }

        # By correct or incorrect classification
        if answer_data.get('correct', False):
            correct_answers.append(question_record)
        else:
            wrong_answers.append(question_record)

    # Extract statistical information
    statistics = raw_data.get('data', {}).get('statistics', {})

    # Build structured data for returns
    exercise_data = {
        'correct_answers': correct_answers,
        'wrong_answers': wrong_answers,
        'statistics': {
            'performance': statistics.get('performance', {}),
            'memory_usage': statistics.get('memory_usage', {}),
            'personalization': statistics.get('personalization', {}),
            'total_correct': len(correct_answers),
            'total_wrong': len(wrong_answers),
            'total_questions': len(correct_answers) + len(wrong_answers),
            'accuracy': len(correct_answers) / (len(correct_answers) + len(wrong_answers)) * 100 if (len(correct_answers) + len(wrong_answers)) > 0 else 0
        },
        'metadata': raw_data.get('metadata', {}),
        'raw_data': raw_data  # Keep full raw data for needs
    }

    return exercise_data

async def improve_after_exercise(student, analyze_correct, analyze_wrong):
    """
    Generate error improvement analysis from problem analysis。
    INPUT:
        student: Student Category
        analyze_correct: Analysis of the results of the correct answer
        analyze_wrong: The result of analyzing the wrong answer
    OUTPUT:
        None
    """
    await(student.improve_from_exercise(analyze_correct, analyze_wrong))

    # Save to New saving Medium
    await(student.save_student_state())
