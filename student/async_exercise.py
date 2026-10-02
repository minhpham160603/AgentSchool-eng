"""
A step-by-step lot processing module
"""
import json
import asyncio
import time
from student.exercise import exercise, save_exercise_results

async def process_questions_in_batches(student, questions_file, batch_size=10):
    """
    Batch processing of topics to improve performance and memory efficiency

    Args:
        student: Student objects
        questions_file: Subject File Path
        batch_size: Number of topics processed per batch

    Returns:
        dict: All the answers
    """
    print(f"Starting batch processing with {batch_size} questions per batch.")

    all_answers = {}
    correct_count = 0
    total_count = 0

    # Read All Subjects
    questions = []
    with open(questions_file, 'r', encoding='utf-8-sig') as f:
        for line_num, line in enumerate(f):
            try:
                question_dict = json.loads(line)
                questions.append((line_num, question_dict))
            except json.JSONDecodeError as e:
                print(f"Skipping line {line_num + 1}: invalid JSON: {e}")

    total_questions = len(questions)
    print(f"Loaded {total_questions} questions.")

    # Batch processing
    for batch_start in range(0, total_questions, batch_size):
        batch_end = min(batch_start + batch_size, total_questions)
        batch = questions[batch_start:batch_end]

        print(f"\nProcessing questions {batch_start + 1}–{batch_end} ({len(batch)} in this batch).")
        batch_start_time = time.time()

        # Step to Current Batch
        batch_results = await process_question_batch(student, batch)

        # Merge Results
        for question_id, result in batch_results.items():
            all_answers[question_id] = result
            total_count += 1
            if result.get('correct', False):
                correct_count += 1

        batch_duration = time.time() - batch_start_time
        current_accuracy = (correct_count / total_count) * 100 if total_count > 0 else 0

        print(f"Time to complete batch: {batch_duration:.2f} sec")
        print(f"Current progress: {total_count}/{total_questions} ({total_count/total_questions*100:.1f}%)")
        print(f"Current accuracy: {correct_count}/{total_count} ({current_accuracy:.2f}%)")

        # Save an intermediate result in case the process is interrupted.
        if total_count % (batch_size * 2) == 0:  # Save every two batches.
            save_exercise_results(student, all_answers, f"progress_{total_count}")
            print(f"Saved progress after {total_count} questions.")

    return all_answers

async def process_question_batch(student, question_batch):
    """
    Process a series of topics by step

    Args:
        student: Student objects
        question_batch: Title Batch [(question_id, question_dict), ...]

    Returns:
        dict: Batch answers
    """
    # In order to avoid excessive simultaneous distribution, limit simultaneous distribution
    semaphore = asyncio.Semaphore(3)  # At most at the same time 3 Topic

    async def process_single_question(question_id, question_dict):
        async with semaphore:
            return await process_one_question_async(student, question_id, question_dict)

    # Create a different task
    tasks = [
        process_single_question(question_id, question_dict)
        for question_id, question_dict in question_batch
    ]

    # Waiting for all tasks to be completed
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collapse Results
    batch_answers = {}
    for i, result in enumerate(results):
        question_id = question_batch[i][0]
        if isinstance(result, Exception):
            print(f"Question {question_id + 1} failed: {result}")
            batch_answers[question_id] = {
                "answer": "",
                "thought_process": "Question processing failed.",
                "correct": False,
                "error": str(result)
            }
        else:
            batch_answers[question_id] = result

    return batch_answers

async def process_one_question_async(student, question_id, question_dict):
    """
    Step-by-step treatment of individual topics
    """
    try:
        from student.retrieve import further_retrieve
        from student.prompt.run_ds_prompt import run_ds_prompt_generate_answer, run_ds_prompt_regenerate_answer
        from student.supervision import supervise_exercise
        import demjson3

        question = question_dict.get("content", "")
        correct_answer = question_dict.get("answer", "")

        # Retrieving relevant memory
        retrieved_mem = await further_retrieve(student, [question], n_count=10)
        mems = [i.embedding_key for i in retrieved_mem[question]]
        mems_str = "\n".join(mems)

        # Generate Answers
        answer_response = await run_ds_prompt_generate_answer(student, question, mems_str)
        answer = demjson3.decode(answer_response)

        # Oversight and inspection
        supervision = await supervise_exercise(student, "student/knowledge_points.json", answer)
        if supervision.get("exceeds_grade", False):
            regenerated_response = await run_ds_prompt_regenerate_answer(student, question, mems_str, supervision)
            answer = demjson3.decode(regenerated_response)

        # Correctness
        answer["correct"] = (str(answer.get('answer', '')).strip() == str(correct_answer).strip())
        answer["question_id"] = question_id
        answer["question"] = question

        return answer

    except Exception as e:
        print(f"Error processing question {question_id + 1}: {e}")
        return {
            "answer": "",
            "thought_process": f"Process error: {str(e)}",
            "correct": False,
            "question_id": question_id,
            "error": str(e)
        }

async def enhanced_exercise_with_progress(student, questions_file, batch_size=5):
    """
    Enhancement of the stept to do a question, including progress display and error recovery
    """
    print(f"=== {student.name} is starting the enhanced exercise workflow ===")

    start_time = time.time()
    print(f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")

    try:
        # Process all topics in batches
        all_answers = await process_questions_in_batches(student, questions_file, batch_size)

        end_time = time.time()
        duration = end_time - start_time

        # Statistical results
        total_questions = len(all_answers)
        correct_answers = sum(1 for answer in all_answers.values() if answer.get('correct', False))
        accuracy_rate = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

        print(f"\n=== It's done ===")
        print(f"Completion time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}")
        print(f"Total time taken: {duration:.2f} sec ({duration/60:.2f} min)")
        print(f"Students: {student.name}")
        print(f"Total questions: {total_questions}")
        print(f"Number of answers: {correct_answers}")
        print(f"Correct Rate: {accuracy_rate:.2f}%")
        print(f"Average time per question: {duration/total_questions:.2f} sec")

        # Save final result
        final_filename = save_exercise_results(student, all_answers, 150)
        print(f"Final result saved to: {final_filename}")

        return all_answers

    except Exception as e:
        print(f"The exercise workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return {}
