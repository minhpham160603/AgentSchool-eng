import json
import demjson3
import asyncio
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import torch
from sentence_transformers import SentenceTransformer

from student.cognitive_module.memory import *
from student.cognitive_module.scratch import *
from student.cognitive_module.student import *
from student.prompt.run_ds_prompt import *
from student.retrieve import *
from student.supervision import *
from util.file_manager import get_file_manager
from student.exercise_modifiers import PersonalizedQuestionModifier
from student.knowledge_graph import kg

# Examples of global models
_embedding_model = None
_model_cache = {}
_embedding_model_lock = None  # Delay Lock/Avoid early creation
_preprocessed_cache = {}  # Preprocessing Cache

async def get_embedding_model(model_name="BAAI/bge-small-en-v1.5"):
    """GPU Load/Single lock"""
    global _embedding_model, _embedding_model_lock
    if _embedding_model is not None:
        return _embedding_model
    if _embedding_model_lock is None:
        _embedding_model_lock = asyncio.Lock()
    async with _embedding_model_lock:
        if _embedding_model is not None:
            return _embedding_model
        print(f"Loading embedded models: {model_name}")
        # Environmental variable preference
        load_target = os.getenv("BGE_MODEL") or model_name
        _embedding_model = await asyncio.to_thread(
            lambda: SentenceTransformer(load_target, device=("cuda" if torch.cuda.is_available() else "cpu"))
        )
        print("Model loaded successfully")
        return _embedding_model

async def preprocess_questions_embeddings_batch(questions_file):
    """Batch/Cache"""
    print("=== Starting batch embedding ===")
    # mtime Cache
    try:
        mtime = os.path.getmtime(questions_file)
        cache_key = (questions_file, mtime)
        if cache_key in _preprocessed_cache:
            print("Using cached preprocessing results.")
            cached = _preprocessed_cache[cache_key]
            return [dict(item) for item in cached]
    except Exception:
        cache_key = None
    questions_data = []

    # 1. Read All Subjects
    with open(questions_file, 'r', encoding='utf-8-sig') as f:
        for i, line in enumerate(f):
            question_dict = json.loads(line)
            question_content = question_dict.get("content", "")
            correct_answer = question_dict.get("answer", "")

            questions_data.append({
                "index": i,
                "content": question_content,
                "answer": correct_answer,
                "embedding": None
            })

    print(f"Loaded {len(questions_data)} questions.")

    # 2. Ripping all problem text batch calculations embedding
    all_questions_text = [q["content"] for q in questions_data]

    print("Starting batch embedding for all questions...")
    start_time = time.time()

    try:
        model = await get_embedding_model()
        all_embeddings = await asyncio.to_thread(
            lambda: model.encode(
                all_questions_text,
                convert_to_tensor=False,
                show_progress_bar=True,
                batch_size=64
            )
        )

        # Allocation embedding Result
        for i, embedding in enumerate(all_embeddings):
            questions_data[i]["embedding"] = (embedding.tolist() if hasattr(embedding, "tolist") else list(embedding))

        end_time = time.time()
        print(f"Batch embedding completed in {end_time - start_time:.2f} seconds.")

    except Exception as e:
        print(f"Batch embedding failed: {e}")
        # Debug Processing
        for i, q_data in enumerate(questions_data):
            try:
                embedding = await get_local_embedding(q_data["content"])
                q_data["embedding"] = embedding
            except:
                q_data["embedding"] = [0.0] * 384

    if cache_key is not None:
        _preprocessed_cache[cache_key] = [dict(item) for item in questions_data]
    print("=== Embedding model configuration complete ===")
    return questions_data

async def process_single_question_async_optimized(student, q_data, question_id_prefix="", semaphore=None):
    """Single/Parallel"""
    # If there are multiple subject parameters, you can set them up or load them up

    if semaphore:
        async with semaphore:
            return await _process_single_question_core(student, q_data, question_id_prefix)
    else:
        return await _process_single_question_core(student, q_data, question_id_prefix)

async def _process_single_question_core(student, q_data, question_id_prefix=""):
    """Core processing logic"""
    try:
        # Secure indexing to make sure it's integer
        raw_index = q_data["index"]

        if isinstance(raw_index, str):
            try:
                if raw_index.isdigit():
                    i = int(raw_index)
                else:
                    float_val = float(raw_index)
                    i = int(float_val)
            except (ValueError, TypeError) as e:
                print(f"⚠️ Index conversion failed: '{raw_index}' -> {e}")
                i = 0
        elif isinstance(raw_index, (int, float)):
            # Directly converted to integer (this is the most common case)）
            i = int(raw_index)
        else:
            print(f"⚠️ Unknown index type: {type(raw_index)} = {raw_index}")
            i = 0

        question = q_data["content"]
        correct_answer = q_data["answer"]
        question_embedding = q_data["embedding"]

        # Add Task ID For tracking
        task_id = f"{question_id_prefix}Q{i+1}"
        print(f"[{task_id}] Starting work for {student.name}...")
        start_time = time.time()

        # Record pre-exercise knowledge flashes
        mastery_before = {}

        # Initializing variables to prevent anomalies not defined
        retrieved_memories = []
        mems_str = ""
        mems_misconceptions = []
        supervision = {}

        # 1. Index
        print(f"[{task_id}] Retrieving related memories...")
        # Reuse Expected Vector
        retrieved_mem = await further_retrieve_with_precomputed_embedding(
            student,
            question,
            question_embedding,
            n_count=10
        )

        # Extract memory information for saving
        retrieved_memories = []
        for node in retrieved_mem:
            memory_info = {
                "node_id": node.node_id,
                "content": node.embedding_key,  # Specifics of memory
                "importance": getattr(node, 'importance', 0),  # Importance
                "keywords": getattr(node, 'keywords', []),     # Keyword
                "last_accessed": str(getattr(node, 'last_accessed', '')),
                "node_type": getattr(node, 'type', ""),  # Node Type
            }
            # If knowledge nodes, add knowledge labels
            if hasattr(node, 'knowledge_tag'):
                knowledge_tag = node.knowledge_tag
                if knowledge_tag is None:
                    memory_info["knowledge_tag"] = []
                else:
                    memory_info["knowledge_tag"] = knowledge_tag

            retrieved_memories.append(memory_info)

        mems = [node.embedding_key for node in retrieved_mem]
        mems_str = "\n".join(mems)
        mems_misconceptions = [node.misconceptions for node in retrieved_mem if hasattr(node, 'misconceptions')]

        # 2. Answer Generation
        print(f"[{task_id}] Generating answers...")
        try:
            answer_response = await run_ds_prompt_generate_answer(student, question, mems_str, mems_misconceptions)
            answer = demjson3.decode(answer_response)
            print(f"[{task_id}] Initial answer: {answer.get('answer', 'N/A')}")
            answer["correct"] = (str(answer.get('answer', '')).strip() == str(correct_answer).strip())

            # 3. Oversight
            print(f"[{task_id}] Checking knowledge use...")
            supervision = await supervise_exercise(student, "student/knowledge_points.json", answer)

            # 4. Monitoring the use of knowledge points
            print(f"[{task_id}] Monitoring the use of knowledge points.")
            # I need two dictionaries, one for each knowledge point，
            # The other one is used to store every knowledge point correctly or wrongly
            knowledge_tags_times = dict()
            knowledge_tags_to_check = dict()
            if retrieved_memories:
                for memory in retrieved_memories:
                    if 'knowledge_tag' in memory:
                        tags = memory['knowledge_tag']
                        # Defensive inspection: ensuring tags It's an iterative list
                        if tags is not None and isinstance(tags, (list, tuple)):
                            for tag in tags:
                                if tag not in knowledge_tags_times:
                                    knowledge_tags_times[tag] = 0
                                knowledge_tags_times[tag] += 1
                        else:
                            print(f"⚠️ Warning: memory node knowledge_tag is not a list: {tags}")

            if knowledge_tags_times:
                try:
                    knowledge_tags_to_check = await supervise_knowledge_used(
                        list(knowledge_tags_times.keys()),
                        answer.get("answer", ""),
                        question
                    )
                    # Check if return values are valid
                    if knowledge_tags_to_check is None:
                        print("⚠️ Warning: supervise_knowledge_used returned no result.")
                        knowledge_tags_to_check = {}
                    elif "error" in knowledge_tags_to_check:
                        print(f"⚠️ Knowledge-use monitor returned an error: {knowledge_tags_to_check.get('error')}")
                        knowledge_tags_to_check = {}
                except Exception as e:
                    print(f"⚠️ Knowledge-use monitoring failed: {e}")
                    knowledge_tags_to_check = {}

            # Proficiency of knowledge points in knowledge mapping
            # Policy：
            # 1. Knowledge points used correctly(used) -> Enhanced ownership(Learning)
            # 2. Wrong used knowledge point(missed) -> Minor punishment(Exposure Misunderstanding)
            # 3. Correct Title -> Add
            # 4. More times used -> To show that this knowledge point is important and has a higher weight

            # Knowledge before record updating
            if knowledge_tags_to_check and knowledge_tags_times:
                for tag_name in knowledge_tags_to_check.keys():
                    tag_id = kg.get_id_by_name(tag_name, student.knowledge_points_of_the_grade)
                    if tag_id:
                        mastery_before[tag_name] = {
                            "id": tag_id,
                            "mastery": kg.get_mastery(student.name, tag_id)
                        }

            # Implement knowledge point updates
            mastery_changes = []

            # Change logic: even if LLM Oversight failure,Should be updated as soon as knowledge points are detected
            if knowledge_tags_times:
                # If there is LLM Oversight results,Use Priority;Otherwise use the default policy
                if knowledge_tags_to_check:
                    # scene 1: LLM Successfully returned monitoring results,According to used/missed processing
                    for tag_name, usage_status in knowledge_tags_to_check.items():
                        # Change first the name of the knowledge point to ID
                        tag_id = kg.get_id_by_name(tag_name, student.knowledge_points_of_the_grade)
                        if tag_id is None:
                            print(f"⚠️ Warning: No ID found for knowledge point '{tag_name}'; skipping.")
                            continue

                        # Number of times a knowledge point is acquired in memory (weight of importance)）
                        times = knowledge_tags_times.get(tag_name, 1)

                        # Basic learning intensity (adjusted for number of times used)）
                        base_strength = 0.03 * min(times / 3.0, 2.0)  # The more weight there are, the more weight there is

                        if usage_status == "used":
                            # Use knowledge points correctly
                            strength = base_strength * (1.5 if answer["correct"] else 1.0)
                            # Add an additional item to the correct title
                            print(f"[{task_id}] Correct use of knowledge point '{tag_name}' (ID: {tag_id}); strength={strength:.3f}")
                            kg.passive_learn(
                                student.name,
                                tag_id,  # Use ID Not a name
                                strength=strength,
                                config_kg=student.knowledge_points_of_the_grade
                            )
                        elif usage_status == "missed":
                            # Misuse knowledge point (discussion of misunderstanding)）
                            # Very small negative adjustments (through reduced enhancement)）
                            strength = base_strength * 0.2  # Keep only 20%Positive effect
                            print(f"[{task_id}] Misuse of knowledge point '{tag_name}' (ID: {tag_id}); applying a small penalty, strength={strength:.3f}")
                            kg.passive_learn(
                                student.name,
                                tag_id,  # Use ID Not a name
                                strength=strength,
                                config_kg=student.knowledge_points_of_the_grade
                            )

                        # up-to-date knowledge and changes
                        mastery_after = kg.get_mastery(student.name, tag_id)
                        mastery_before_value = mastery_before.get(tag_name, {}).get("mastery", None)

                        change_info = {
                            "knowledge_point": tag_name,
                            "knowledge_point_id": tag_id,
                            "usage_status": usage_status,
                            "usage_times": times,
                            "learning_strength": strength,
                            "mastery_before": round(mastery_before_value, 4) if mastery_before_value else None,
                            "mastery_after": round(mastery_after, 4) if mastery_after else None,
                            "mastery_change": round(mastery_after - mastery_before_value, 4) if (mastery_after and mastery_before_value) else None
                        }
                        mastery_changes.append(change_info)
                else:
                    # scene 2: LLM Oversight failure,Use conservative default policies
                    # Let's assume that all the points of knowledge detected are"Could be used correctly"(Give me a medium strength)
                    print(f"[{task_id}] ⚠️ LLM monitoring failed; applying the default policy to {len(knowledge_tags_times)} knowledge points.")
                    for tag_name, times in knowledge_tags_times.items():
                        tag_id = kg.get_id_by_name(tag_name, student.knowledge_points_of_the_grade)
                        if tag_id is None:
                            print(f"⚠️ Warning: No ID found for knowledge point '{tag_name}'; skipping.")
                            continue

                        # Use conservative default strength(That's right"used"Weak,That's right"missed"Strong)
                        base_strength = 0.03 * min(times / 3.0, 2.0)
                        strength = base_strength * 0.6  # 60%Basic strength(Between used and missed Between)

                        print(f"[{task_id}] Default update for knowledge point '{tag_name}' (ID: {tag_id}; monitoring unavailable); strength={strength:.3f}")
                        kg.passive_learn(
                            student.name,
                            tag_id,
                            strength=strength,
                            config_kg=student.knowledge_points_of_the_grade
                        )

                        # up-to-date knowledge and changes
                        mastery_after = kg.get_mastery(student.name, tag_id)
                        mastery_before_value = mastery_before.get(tag_name, {}).get("mastery", None)

                        change_info = {
                            "knowledge_point": tag_name,
                            "knowledge_point_id": tag_id,
                            "usage_status": "default_update",  # Mark as Default Update
                            "usage_times": times,
                            "learning_strength": strength,
                            "mastery_before": round(mastery_before_value, 4) if mastery_before_value else None,
                            "mastery_after": round(mastery_after, 4) if mastery_after else None,
                            "mastery_change": round(mastery_after - mastery_before_value, 4) if (mastery_after and mastery_before_value) else None
                        }
                        mastery_changes.append(change_info)

            # Add knowledge points to oversight results
            if knowledge_tags_times:
                supervision["knowledge_points_cnt"] = knowledge_tags_times

            if knowledge_tags_to_check:
                supervision["knowledge_points_used"] = knowledge_tags_to_check

            # Add a record of changes in knowledge point mastery
            if mastery_changes:
                supervision["knowledge_mastery_changes"] = mastery_changes


            # Record oversight information
            supervision_info = {
                "grade": supervision.get("grade", ""),
                "knowledge_points": supervision.get("knowledge_points", ""),
                "exceeds_grade": supervision.get("exceeds_grade", False),
                "supervision_triggered": supervision.get("exceeds_grade", False)
            }

            if supervision.get("exceeds_grade", False):
                print(f"[{task_id}] Regenerating the answer...")
                try:
                    regenerated_response = await run_ds_prompt_regenerate_answer(
                        student, question, mems_str, supervision
                    )
                    original_answer = answer.copy()  # Save original answer
                    answer = demjson3.decode(regenerated_response)

                    # Regenerated
                    supervision_info["original_answer"] = original_answer.get("answer", "")
                    supervision_info["regenerated_answer"] = answer.get("answer", "")
                    supervision_info["regeneration_successful"] = True

                    print(f"[{task_id}] Answer after supervision: {answer.get('answer', 'N/A')}")
                except Exception as e:
                    print(f"[{task_id}] Failed to regenerate the answer after monitoring: {e}")
                    supervision_info["regeneration_successful"] = False
                    supervision_info["regeneration_error"] = str(e)

        except Exception as e:
            print(f"[{task_id}] Failed to generate an answer: {e}")
            answer = {
                "answer": "A",
                "thought_process": f"Process error: {e}",
                "correct": False  # Ensure correct Field exists
            }

        # 4. Result processing
        # If answer Not yet correct Fields (normal processes set up, abnormal processes just set) to make sure they exist
        if "correct" not in answer:
            answer["correct"] = (str(answer.get('answer', '')).strip() == str(correct_answer).strip())

        answer["question_id"] = i
        answer["question"] = question
        answer["correct_answer"] = correct_answer

        # Add memory
        answer["retrieved_memories"] = retrieved_memories
        answer["retrieved_memories_count"] = len(retrieved_memories)
        answer["memory_summary"] = mems_str if retrieved_memories else "No relevant memory"

        # Records monitoring
        answer["supervision"] = supervision

        duration = time.time() - start_time
        answer["processing_time"] = round(duration, 2)
        answer["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        answer["misconceptions"] = mems_misconceptions
        result_msg = "✓" if answer["correct"] else f"✗Wrong(Correct: {correct_answer})"
        print(f"[{task_id}] Completed - {result_msg} (Time-consuming: {duration:.2f}s)")

        return i, answer

    except Exception as e:
        print(f"[{task_id}] Unexpected error: {e}")
        return q_data["index"], {
            "answer": "",
            "thought_process": f"Abnormal error: {str(e)}",
            "correct": False,
            "question_id": q_data["index"],
            "question": q_data.get("content", ""),
            "correct_answer": q_data.get("answer", ""),
            "error": str(e),
            "retrieved_memories": [],
            "retrieved_memories_count": 0,
            "memory_summary": "Processing anomaly, unable to index",
            "supervision": {"error": str(e)},
            "processing_time": 0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "midsconceptions": []
        }

async def process_single_question_with_personalization(student, question_data, question_index, semaphore=None):
    """Process one question, applying student-specific modifications first."""

    # 1. Initialize the question modifier.
    modifier = PersonalizedQuestionModifier(student)

    # 2. Modify the question according to the student's learning profile.
    modified_question = modifier.modify_question(question_data, question_index)

    # 3. Record the modification details.
    modification_log = {
        "student_name": student.name,
        "question_index": question_data.get("index", question_index),
        "original_content": question_data["content"],
        "modified_content": modified_question["content"],
        "modifications": modified_question.get("modification_info", {}),
        "timestamp": datetime.now().isoformat()
    }

    # 4. Process and supervise the modified question.
    question_id, answer_result = await process_single_question_async_optimized(
        student, modified_question, question_index, semaphore
    )

    # 5. Record changes in results
    if "modification_info" in modified_question:
        answer_result["question_modification"] = {
            "was_modified": True,
            "original_question": question_data["content"],
            "modified_question": modified_question["content"],
            "modification_details": modified_question["modification_info"]
        }
        # answer_result["personalization_log"] = modification_log
    else:
        answer_result["question_modification"] = {
            "was_modified": False,
            "original_question": question_data["content"],
            "modified_question": question_data["content"]
        }

    return question_id, answer_result

async def process_questions_batch_async_optimized(student, questions_batch, max_concurrent=5):
    """Batch Schedule/Parallel"""
    # Reduced co-production to avoid excessive competition
    semaphore = asyncio.Semaphore(max_concurrent)

    # Safely print batch information to avoid index Error
    safe_indices = []
    for q in questions_batch:
        try:
            idx = q['index']
            if isinstance(idx, str):
                if idx.isdigit():
                    safe_indices.append(int(idx) + 1)
                else:
                    safe_indices.append(int(float(idx)) + 1)
            else:
                safe_indices.append(int(idx) + 1)
        except (ValueError, TypeError) as e:
            print(f"🔍 Debug Information - Default Index Error: {q['index']}, Error: {e}")
            safe_indices.append(f"ERROR({q['index']})")

    print(f"=== Processing batch for question indices: {safe_indices} ===")

    # Create a task without immediate execution
    tasks = []
    for q_data in questions_batch:
        # It's also about getting the first one safely index Used for batch naming
        try:
            first_idx = questions_batch[0]['index']
            if isinstance(first_idx, str):
                if first_idx.isdigit():
                    batch_num = int(first_idx) // 20 + 1
                else:
                    batch_num = int(float(first_idx)) // 20 + 1
            else:
                batch_num = int(first_idx) // 20 + 1
        except (ValueError, TypeError) as e:
            print(f"🔍 Could not determine the batch number for index {questions_batch[0]['index']}: {e}")
            batch_num = 1

        task = asyncio.create_task(
            process_single_question_async_optimized(
                student, q_data, f"Batch{batch_num}-", semaphore
            )
        )
        tasks.append(task)
        # It's smaller
        await asyncio.sleep(0.01)

    print(f"Created {len(tasks)} tasks; starting them...")

    # Waiting for all tasks to be completed
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collapse Results
    batch_answers = {}
    successful_count = 0

    for result in results:
        if isinstance(result, Exception):
            print(f"Task failed with an unexpected error: {result}")
            continue

        question_id, answer = result
        batch_answers[question_id] = answer
        if answer.get('correct', False):
            successful_count += 1

    success_rate = (successful_count / len(batch_answers)) * 100 if batch_answers else 0
    print(f"=== Batch processing completed, success rate: {success_rate:.1f}% ({successful_count}/{len(batch_answers)}) ===")

    return batch_answers

async def exercise_with_true_concurrency(student, questions_data, batch_size=20, max_concurrent=5):
    """Run the exercise using concurrent batches."""
    print(f"=== Starting exercise for {student.name} ===")
    print(f"Configuration: batch size={batch_size}, maximum concurrent tasks={max_concurrent}")

    all_answers = {}
    total_questions = len(questions_data)
    total_correct = 0
    processed_count = 0

    start_time = time.time()

    # Batch processing, but smaller batch size to improve co-production
    for batch_start in range(0, total_questions, batch_size):
        batch_end = min(batch_start + batch_size, total_questions)
        questions_batch = questions_data[batch_start:batch_end]

        batch_num = batch_start // batch_size + 1
        print(f"\n*** Processing batch {batch_num}: questions {batch_start+1}–{batch_end} ***")
        batch_start_time = time.time()

        # Process the current batch.
        batch_answers = await process_questions_batch_async_optimized(
            student, questions_batch, max_concurrent
        )

        # Statistical results
        batch_correct = sum(1 for ans in batch_answers.values() if ans.get('correct', False))
        total_correct += batch_correct
        processed_count += len(batch_answers)

        # Add this batch's answers to the results.
        all_answers.update(batch_answers)

        batch_duration = time.time() - batch_start_time
        overall_accuracy = (total_correct / processed_count) * 100 if processed_count > 0 else 0

        print(f"*** Batch {batch_num} complete ***")
        print(f"Batch time: {batch_duration:.2f}s; average per question: {batch_duration/len(batch_answers):.2f}s")
        print(f"Progress: {processed_count}/{total_questions} ({processed_count/total_questions*100:.1f}%)")
        print(f"Overall accuracy: {total_correct}/{processed_count} ({overall_accuracy:.1f}%)")

        # Reduce the frequency of permanence
        if batch_num % 3 == 0:
            save_exercise_results(student, all_answers, f"progress_batch_{batch_num}")

    total_duration = time.time() - start_time
    final_accuracy = (total_correct / processed_count) * 100 if processed_count > 0 else 0

    print("\n🎉 === Exercise complete === 🎉")
    print(f"Total time: {total_duration:.2f}s ({total_duration/60:.2f} min)")
    print(f"Average time per question: {total_duration/processed_count:.2f}s")
    print(f"Final accuracy: {final_accuracy:.2f}%")

    return all_answers

async def exercise(student, questions_file, batch_size=20, max_concurrent=5):
    """Run the full exercise workflow with parallel question processing."""
    overall_start_time = time.time()

    # 1: Batch preprocessing embedding
    print("=== Step 1: Prepare question embeddings in batches ===")
    questions_data = await preprocess_questions_embeddings_batch(questions_file)

    preprocess_time = time.time()
    preprocess_duration = preprocess_time - overall_start_time
    print(f"Preprocessing completed in {preprocess_duration:.2f} seconds.")

    # Step 2: Generate and evaluate answers.
    print("=== Step 2: Generate and evaluate answers ===")
    answers = await exercise_with_true_concurrency(
        student, questions_data, batch_size, max_concurrent
    )

    answer_time = time.time()
    answer_duration = answer_time - preprocess_time
    total_duration = answer_time - overall_start_time

    print(f"Answer generation completed in {answer_duration:.2f} seconds.")
    print(f"Total elapsed time: {total_duration:.2f} seconds ({total_duration/60:.2f} min)")

    # Save final result
    save_exercise_results(student, answers, "final_true_concurrent")
    save_memory_analysis(student, answers, "final_with_memory")

    return answers


def save_exercise_results(student, answers, postfix):
    """
    Save the result of the exercise to json Documentation
    """
    file_mgr = get_file_manager()

    # Compute statistics
    total_questions = len(answers)
    correct_count = sum(1 for ans in answers.values() if ans.get('correct', False))
    accuracy = (correct_count / total_questions * 100) if total_questions > 0 else 0

    # Use of statistical memory
    total_memories_used = sum(ans.get('retrieved_memories_count', 0) for ans in answers.values())
    avg_memories_per_question = total_memories_used / total_questions if total_questions > 0 else 0

    # Statistical monitoring triggers
    supervision_triggered = sum(1 for ans in answers.values()
                              if ans.get('supervision', {}).get('supervision_triggered', False))

    # Statistical individualization modifications
    modification_stats = _analyze_question_modifications(answers)

    # Outcome data
    result_data = {
        "test_info": {
            "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "postfix": postfix,
            "total_duration_seconds": getattr(student, '_test_duration', 0),
            "environment": "concurrent_processing_with_personalization"
        },
        "statistics": {
            "performance": {
                "total_questions": total_questions,
                "correct_answers": correct_count,
                "incorrect_answers": total_questions - correct_count,
                "accuracy_percentage": round(accuracy, 2),
                "difficulty_distribution": _analyze_difficulty_distribution(answers)
            },
            "memory_usage": {
                "total_memories_retrieved": total_memories_used,
                "avg_memories_per_question": round(avg_memories_per_question, 2),
                "memory_efficiency_score": _calculate_memory_efficiency(answers)
            },
            "supervision": {
                "supervision_triggered_count": supervision_triggered,
                "supervision_rate": round(supervision_triggered / total_questions * 100, 2) if total_questions > 0 else 0,
                "supervision_effectiveness": _analyze_supervision_effectiveness(answers)
            },
            "personalization": modification_stats
        },
        "detailed_answers": answers
    }

    # Use file manager Save Results
    filepath = file_mgr.save_exercise_results(student.name, result_data, postfix)

    # Save progress checkpoint (for restoration)）
    if total_questions > 50:  # Large Test to Save Checkpoint
        checkpoint_data = {
            "completed_questions": total_questions,
            "current_accuracy": accuracy,
            "timestamp": datetime.now().isoformat()
        }
        file_mgr.save_progress_checkpoint(student.name, checkpoint_data, f"checkpoint_{postfix}")

    print(f"Exercise results saved to: {filepath}")
    print(f"📊 Accuracy: {accuracy:.1f}%; average retrieved memories per question: {avg_memories_per_question:.1f}")
    print(f"🎯 Personalized questions: {modification_stats['modified_questions']}/{modification_stats['total_questions']} ({modification_stats['modification_rate']:.1f}%)")
    if modification_stats['modified_questions'] > 0:
        print(f"   Accuracy on personalized questions: {modification_stats['effectiveness']['modified_accuracy']:.1f}%; other questions: {modification_stats['effectiveness']['unmodified_accuracy']:.1f}%")
    print(f"📂 Results directory: results/{student.name}/{datetime.now().strftime('%Y-%m-%d')}/exercises/")

    return str(filepath)

def save_memory_analysis(student, answers, postfix):
    """
    Analysis of the use of separate memory
    """
    file_mgr = get_file_manager()

    memory_analysis = {
        "summary": {
            "total_questions_analyzed": len(answers),
            "memory_retrieval_stats": _calculate_memory_stats(answers),
            "knowledge_coverage": _analyze_knowledge_coverage(answers),
            "personalization_stats": _analyze_question_modifications(answers)
        },
        "detailed_analysis": {
            "memory_usage_by_question": [],
            "frequently_used_memories": {},
            "knowledge_gaps": [],
            "memory_effectiveness": _analyze_memory_effectiveness(answers),
            "personalization_effectiveness": []
        }
    }

    all_used_memories = []

    for q_id, answer in answers.items():
        question_analysis = {
            "question_id": q_id,
            "question": answer.get("question", ""),
            "correct": answer.get("correct", False),
            "memories_count": answer.get("retrieved_memories_count", 0),
            "memory_types": {},
            "key_memories": [],
            "memory_relevance_score": _calculate_memory_relevance(answer)
        }

        # Analysis of the type of memory used and the significant memory
        for memory in answer.get("retrieved_memories", []):
            memory_type = memory.get("node_type", "Unknown")
            question_analysis["memory_types"][memory_type] = question_analysis["memory_types"].get(memory_type, 0) + 1

            # Important memory (materiality)>=7）
            if memory.get("importance", 0) >= 7:
                question_analysis["key_memories"].append({
                    "content": memory.get("content", ""),
                    "importance": memory.get("importance", 0),
                    "keywords": memory.get("keywords", []),
                    "relevance_score": memory.get("relevance_score", 0)
                })

            # Memory for frequent statistical use
            content = memory.get("content", "")
            if content:
                all_used_memories.append(content)

        # Add personalized information
        question_mod = answer.get("question_modification", {})
        if question_mod.get("was_modified", False):
            question_analysis["personalization"] = {
                "was_modified": True,
                "original_question": question_mod.get("original_question", ""),
                "modification_types": list(question_mod.get("modification_details", {}).keys())
            }
        else:
            question_analysis["personalization"] = {"was_modified": False}

        # Check knowledge gaps (titles not guided by relevant memory but not answered correctly)）
        if not answer.get("correct", False) and answer.get("retrieved_memories_count", 0) == 0:
            memory_analysis["detailed_analysis"]["knowledge_gaps"].append({
                "question_id": q_id,
                "question": answer.get("question", ""),
                "correct_answer": answer.get("correct_answer", ""),
                "student_answer": answer.get("answer", ""),
                "potential_knowledge_area": _identify_knowledge_area(answer.get("question", "")),
                "was_modified": question_mod.get("was_modified", False)
            })

        memory_analysis["detailed_analysis"]["memory_usage_by_question"].append(question_analysis)

    # Analysis of the effects of individualisation
    for answer in answers.values():
        question_mod = answer.get("question_modification", {})
        if question_mod.get("was_modified", False):
            memory_analysis["detailed_analysis"]["personalization_effectiveness"].append({
                "question_id": answer.get("question_id", "unknown"),
                "correct": answer.get("correct", False),
                "memory_count": answer.get("retrieved_memories_count", 0),
                "modification_types": list(question_mod.get("modification_details", {}).keys()),
                "effectiveness_score": 1.0 if answer.get("correct", False) else 0.0
            })

    # Statistically used memory
    from collections import Counter
    memory_counter = Counter(all_used_memories)
    memory_analysis["detailed_analysis"]["frequently_used_memories"] = dict(memory_counter.most_common(10))

    # Save analysis using file manager
    analysis_filepath = file_mgr.save_memory_analysis(student.name, memory_analysis, postfix)

    # Generate visualized data
    viz_data = {
        "memory_type_distribution": {},
        "performance_vs_memory_usage": [],
        "knowledge_gap_areas": [],
        "frequently_used_memories": memory_analysis["detailed_analysis"]["frequently_used_memories"],
        "personalization_analysis": {
            "modification_distribution": {},
            "effectiveness_comparison": [],
            "modification_memory_correlation": []
        }
    }

    # Fill visualized data
    for question_data in memory_analysis["detailed_analysis"]["memory_usage_by_question"]:
        # Memory type distribution
        for mem_type, count in question_data["memory_types"].items():
            viz_data["memory_type_distribution"][mem_type] = viz_data["memory_type_distribution"].get(mem_type, 0) + count

        # Performance and memory use relationships
        viz_data["performance_vs_memory_usage"].append({
            "memories_used": question_data["memories_count"],
            "correct": question_data["correct"],
            "relevance_score": question_data["memory_relevance_score"],
            "was_modified": question_data["personalization"]["was_modified"]
        })

        # Personalized analysis
        if question_data["personalization"]["was_modified"]:
            for mod_type in question_data["personalization"]["modification_types"]:
                viz_data["personalization_analysis"]["modification_distribution"][mod_type] = \
                    viz_data["personalization_analysis"]["modification_distribution"].get(mod_type, 0) + 1

            viz_data["personalization_analysis"]["modification_memory_correlation"].append({
                "memories_used": question_data["memories_count"],
                "correct": question_data["correct"],
                "modification_types": question_data["personalization"]["modification_types"]
            })

    # Effect Comparison Data
    personalization_stats = memory_analysis["summary"]["personalization_stats"]
    viz_data["personalization_analysis"]["effectiveness_comparison"] = {
        "modified_accuracy": personalization_stats["effectiveness"]["modified_accuracy"],
        "unmodified_accuracy": personalization_stats["effectiveness"]["unmodified_accuracy"],
        "modification_rate": personalization_stats["modification_rate"]
    }

    # Knowledge gap area
    viz_data["knowledge_gap_areas"] = [gap["potential_knowledge_area"]
                                     for gap in memory_analysis["detailed_analysis"]["knowledge_gaps"]]
    viz_dir = file_mgr.get_category_dir(student.name, "visualizations")
    viz_filename = file_mgr.generate_unique_filename(student.name, "viz_data", postfix)
    viz_filepath = viz_dir / viz_filename

    with open(viz_filepath, 'w', encoding='utf-8') as f:
        json.dump(viz_data, f, ensure_ascii=False, indent=2)

    print(f"Memory use analysis saved to: {analysis_filepath}")
    print(f"📈 Visual data saving: {viz_filepath}")

    return str(analysis_filepath)

# Support function definition
def _analyze_question_modifications(answers):
    """Statistical data modified by analytical title"""
    modification_stats = {
        "total_questions": len(answers),
        "modified_questions": 0,
        "modification_rate": 0.0,
        "modification_types": {},
        "effectiveness": {
            "modified_correct": 0,
            "modified_incorrect": 0,
            "unmodified_correct": 0,
            "unmodified_incorrect": 0
        },
        "common_modifications": []
    }

    modification_details = []

    for answer in answers.values():
        question_mod = answer.get("question_modification", {})
        was_modified = question_mod.get("was_modified", False)
        is_correct = answer.get("correct", False)

        if was_modified:
            modification_stats["modified_questions"] += 1

            # Statistical change type
            mod_details = question_mod.get("modification_details", {})
            mod_types = mod_details.get("applied", [])
            for mod_type in mod_types:
                if mod_type not in modification_stats["modification_types"]:
                    modification_stats["modification_types"][mod_type] = 0
                modification_stats["modification_types"][mod_type] += 1

            # Statistical Effects
            if is_correct:
                modification_stats["effectiveness"]["modified_correct"] += 1
            else:
                modification_stats["effectiveness"]["modified_incorrect"] += 1

            # Collect detailed changes to the record
            modification_details.append({
                "question_id": answer.get("question_id", "unknown"),
                "original": question_mod.get("original_question", ""),
                "modified": question_mod.get("modified_question", ""),
                "correct": is_correct,
                "modification_types": list(mod_types)
            })
        else:
            if is_correct:
                modification_stats["effectiveness"]["unmodified_correct"] += 1
            else:
                modification_stats["effectiveness"]["unmodified_incorrect"] += 1

    # Calculate change rate
    if modification_stats["total_questions"] > 0:
        modification_stats["modification_rate"] = round(
            modification_stats["modified_questions"] / modification_stats["total_questions"] * 100, 2
        )

    # Calculate effects comparison
    modified_total = modification_stats["effectiveness"]["modified_correct"] + modification_stats["effectiveness"]["modified_incorrect"]
    unmodified_total = modification_stats["effectiveness"]["unmodified_correct"] + modification_stats["effectiveness"]["unmodified_incorrect"]

    if modified_total > 0:
        modification_stats["effectiveness"]["modified_accuracy"] = round(
            modification_stats["effectiveness"]["modified_correct"] / modified_total * 100, 2
        )
    else:
        modification_stats["effectiveness"]["modified_accuracy"] = 0

    if unmodified_total > 0:
        modification_stats["effectiveness"]["unmodified_accuracy"] = round(
            modification_stats["effectiveness"]["unmodified_correct"] / unmodified_total * 100, 2
        )
    else:
        modification_stats["effectiveness"]["unmodified_accuracy"] = 0

    # Identify the most common types of changes
    if modification_stats["modification_types"]:
        sorted_mods = sorted(modification_stats["modification_types"].items(),
                           key=lambda x: x[1], reverse=True)
        modification_stats["common_modifications"] = [
            {"type": mod_type, "count": count, "percentage": round(count/modification_stats["modified_questions"]*100, 1)}
            for mod_type, count in sorted_mods[:5]
        ]

    # Add detailed changes to the record (maximum) 10 Article）
    modification_stats["detailed_modifications"] = modification_details[:10]

    return modification_stats

def _analyze_difficulty_distribution(answers):
    """Analysis of difficulty distribution of topics"""
    difficulty_levels = {"easy": 0, "medium": 0, "hard": 0}

    for answer in answers.values():
        memories_used = answer.get("retrieved_memories_count", 0)
        is_correct = answer.get("correct", False)

        # Simple rules: Use of less memorable and correct topics as simple
        if memories_used <= 2 and is_correct:
            difficulty_levels["easy"] += 1
        elif memories_used <= 5:
            difficulty_levels["medium"] += 1
        else:
            difficulty_levels["hard"] += 1

    return difficulty_levels

def _calculate_memory_efficiency(answers):
    """Calculate efficiency points for memory use"""
    total_questions = len(answers)
    if total_questions == 0:
        return 0

    efficiency_scores = []
    for answer in answers.values():
        memories_used = answer.get("retrieved_memories_count", 0)
        is_correct = answer.get("correct", False)

        # Efficiency scores: cases with less memory = Efficient
        if is_correct:
            if memories_used <= 3:
                efficiency_scores.append(10)  # Efficient
            elif memories_used <= 6:
                efficiency_scores.append(7)   # Moderate efficiency
            else:
                efficiency_scores.append(5)   # Inefficiency
        else:
            efficiency_scores.append(0)  # Wrong answer

    return round(sum(efficiency_scores) / len(efficiency_scores), 2)

def _analyze_supervision_effectiveness(answers):
    """Analysis of the effectiveness of oversight"""
    supervision_cases = [ans for ans in answers.values()
                        if ans.get('supervision', {}).get('supervision_triggered', False)]

    if not supervision_cases:
        return {"effectiveness_rate": 0, "improvement_count": 0}

    improvement_count = sum(1 for case in supervision_cases
                          if case.get('supervision', {}).get('improved_after_supervision', False))

    return {
        "effectiveness_rate": round(improvement_count / len(supervision_cases) * 100, 2),
        "improvement_count": improvement_count,
        "total_supervised": len(supervision_cases)
    }

def _calculate_memory_stats(answers):
    """Compute statistics on the use of memory"""
    total_retrievals = sum(ans.get("retrieved_memories_count", 0) for ans in answers.values())
    questions_with_memories = sum(1 for ans in answers.values() if ans.get("retrieved_memories_count", 0) > 0)

    return {
        "total_memory_retrievals": total_retrievals,
        "questions_with_memories": questions_with_memories,
        "avg_memories_per_question": round(total_retrievals / len(answers), 2) if answers else 0,
        "memory_usage_rate": round(questions_with_memories / len(answers) * 100, 2) if answers else 0
    }

def _analyze_knowledge_coverage(answers):
    """Analysis of knowledge coverage"""
    knowledge_areas = set()
    for answer in answers.values():
        for memory in answer.get("retrieved_memories", []):
            keywords = memory.get("keywords", [])
            knowledge_areas.update(keywords)

    return {
        "unique_knowledge_areas": len(knowledge_areas),
        "knowledge_diversity_score": min(len(knowledge_areas) / 20, 1.0)
    }

def _analyze_memory_effectiveness(answers):
    """Analysis of the effectiveness of memory use"""
    effective_cases = 0
    total_cases = 0

    for answer in answers.values():
        if answer.get("retrieved_memories_count", 0) > 0:
            total_cases += 1
            if answer.get("correct", False):
                effective_cases += 1

    return {
        "effectiveness_rate": round(effective_cases / total_cases * 100, 2) if total_cases > 0 else 0,
        "effective_cases": effective_cases,
        "total_memory_usage_cases": total_cases
    }

def _calculate_memory_relevance(answer):
    """Calculates memory correlation fractions"""
    memories = answer.get("retrieved_memories", [])
    if not memories:
        return 0

    relevance_scores = [mem.get("relevance_score", 0.5) for mem in memories]
    return round(sum(relevance_scores) / len(relevance_scores), 3)

def _identify_knowledge_area(question):
    """Identification of areas of knowledge of the subject"""
    # Simple Keyword Match Recognition
    knowledge_keywords = {
        "math": ["Calculate", "Equation", "Functions", "Multiple", "Decimal", "Numbers", "Operations"],
        "physics": ["Mechanical", "Electrical", "Optical", "Thermal", "Speed", "Speed up"],
        "chemistry": ["Elements", "Compounds", "Response", "Molecular", "Atom"],
        "language_arts": ["Reading", "Writing", "Syntax:", "Literature", "Terms"]
    }

    question_lower = question.lower()
    for area, keywords in knowledge_keywords.items():
        if any(keyword in question_lower for keyword in keywords):
            return area

    return "uncategorized"
