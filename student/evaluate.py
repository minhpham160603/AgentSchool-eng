import os
import json
import demjson3
import time

from student.prompt.run_ds_prompt import *

async def evaluate(student, file, postfix):
    """
    Assess a student using an imported questionnaire.
    INPUT:
        student: Student Category
        file: str, Questionnaire File Path
        postfix: str, Suffix used to distinguish between different assessments
    OUTPUT:

    """
    if not os.path.exists(file):
        print(f"Questionnaire file not found: {file}")
        return

    # Read Questionnaire
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n--- Evaluation begins ---")
    t_start = time.time()
    print(f"{student.name} is answering the questionnaire.")

    personality_description = demjson3.decode(await run_ds_prompt_analyze_personality(student))
    print(f"Personality description: {personality_description}")

    answers = []
    for question in data["scales"]:
        category = question.get("category")
        period = question.get("period", "")
        rate = question.get("rating")
        explanation = question.get("explanation", "")
        print(f"Current category: {question['category']}")
        description = await run_ds_prompt_describe_rate(category, period, rate, explanation)
        print(f"Scoring instructions: {description}")
        if "questions" in question:
            for i in question["questions"]:
                try:
                    a = demjson3.decode(await run_ds_prompt_evaluate(student, i, description, category, personality_description))
                except Exception as e:
                    print(f"Error while answering '{i}': {e}")
                    a = {"answer": "", "reasoning": ""}
                print(f"Question: {i}")
                print(f"Answer: {a}")
                answers.append({
                    "question" : i,
                    "answer": a.get("answer", ""),
                    "reasoning": a.get("reasoning", ""),
                })
        elif "subcategories" in question:
            for sub in question["subcategories"]:
                print(f"Current subcategory: {sub}")
                for i in question["subcategories"][sub]:
                    try:
                        a = demjson3.decode(await run_ds_prompt_evaluate(student, i, description, category, personality_description))
                    except Exception as e:
                        print(f"Error while answering '{i}': {e}")
                        a = {"answer": "", "reasoning": ""}
                    print(f"Question: {i}")
                    print(f"Answer: {a}")
                    answers.append({
                        "question": i,
                        "answer": a.get("answer", ""),
                        "reasoning": a.get("reasoning", ""),
                    })

        save_evaluation_results(student, answers, postfix)
    # Statistics time-consuming
    t_cost = time.time() - t_start
    print(f"[TIME] {student.name} questionnaire duration: {t_cost:.2f}s")

async def evaluate_bfi(student, file, postfix):
    """
    Assess the Big Five inventory and calculate the five trait scores. This implementation sums item scores directly and does not reverse-score items.
    """
    # Item numbers grouped by Big Five trait (one-based).
    BFI_TRAITS = {
        "Extraversion":      [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56],
        "Agreeableness":      [2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57],
        "Conscientiousness":      [3, 8, 13, 18, 23, 28, 33, 38, 43, 48, 53, 58],
        "Negative Emotionality":    [4, 9, 14, 19, 24, 29, 34, 39, 44, 49, 54, 59],
        "Openness to Experience":      [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60],
    }

    if not os.path.exists(file):
        print(f"Questionnaire file not found: {file}")
        return

    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n--- First five personality assessment begins ---")
    print(f"{student.name} is answering the Big Five inventory.")

    scale_info = data["scales"][0]
    rate = scale_info.get("rating", "")
    print(f"Scoring instructions: {rate}")

    answers = []
    trait_scores = {trait: [] for trait in BFI_TRAITS}

    # personality_description = demjson3.decode(await run_ds_prompt_analyze_personality(student))
    personality_description = demjson3.decode(await run_ds_prompt_analyze_personality_MBTI(student))
    print(f"Personality description: {personality_description}")

     # Internal function for single issues
    async def process_question(idx, q_text):
        try:
            # Let the student answer 1-5 Integer，LLM Dealed with the inverse
            a = demjson3.decode(await run_ds_prompt_evaluate_MBTI(student, q_text, rate, "Five", personality_description))
            score = int(float(a.get("answer", 3)))  # Turn first float Turn again int，Compatible decimals
            return {"idx": idx, "q_text": q_text, "score": score, "raw_answer": a, "status": "success"}
        except Exception as e:
            print(f"Error while answering '{q_text}': {e}")
            score = 3
            a = {"answer": str(score), "reasoning": ""}
            return {"idx": idx, "q_text": q_text, "score": score, "raw_answer": a, "status": "error"}

    # Create task for all issues
    tasks = [process_question(idx, q_text) for idx, q_text in enumerate(scale_info["questions"], 1)]

    # All tasks performed in parallel
    results = await asyncio.gather(*tasks)

    # Process and collect results
    answers = []
    trait_scores = {trait: [] for trait in BFI_TRAITS}

    # Sequencing results to ensure consistency with original issues
    results.sort(key=lambda r: r['idx'])

    for result in results:
        idx = result['idx']
        q_text = result['q_text']
        score = result['score']
        a = result['raw_answer']

        print(f"Question {idx}: {q_text}")
        print(f"Answer: {a}")

        answers.append({
            "index": idx,
            "question": q_text,
            "original_question": scale_info["questions"][idx-1],
            "answer": score,
            "reasoning": a.get("reasoning", ""),
        })

        # Statistical Scores
        for trait, qlist in BFI_TRAITS.items():
            if idx in qlist:
                trait_scores[trait].append(score)


    """for idx, question in enumerate(scale_info["questions"], 1):
        q_text = question
        try:
            # Let the student answer 1-5 Integer，LLM Dealed with the inverse
            a = demjson3.decode(await run_ds_prompt_evaluate_MBTI(student, q_text, rate, "Five", personality_description))
            score = int(a.get("answer", 3))  # Default 3 min
        except Exception as e:
            print(f"Addressing issues '{q_text}' Error occurred: {e}")
            score = 3
            a = {"answer": str(score), "reasoning": ""}
        print(f"question {idx}: {q_text}")
        print(f"Answer!: {a}")
        answers.append({
            "index": idx,
            "question": q_text,
            "original_question": question,
            "answer": score,
            "reasoning": a.get("reasoning", ""),
        })
        # Statistical Scores
        for trait, qlist in BFI_TRAITS.items():
            if idx in qlist:
                trait_scores[trait].append(score)"""

    # Calculates the sum and equals of each quality
    trait_summary = {
        trait: {
            "total_score": sum(scores),
            "mean_score": round(sum(scores)/len(scores), 2) if scores else 0,
            "details": scores
        }
        for trait, scores in trait_scores.items()
    }

    # Save Results
    memory_folder = f"student/evaluation/test_{student.name}"
    os.makedirs(memory_folder, exist_ok=True)
    memory_file = f"{memory_folder}/evaluate_results_{postfix}.json"
    with open(memory_file, 'w', encoding='utf-8') as f:
        json.dump({
            "answers": answers,
            "trait_scores": trait_summary
        }, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {memory_file}")
    print("\n--- Big Five assessment complete ---")


def save_evaluation_results(student, answers, postfix):
    # Save answer to json Documentation
    # memory_folder = f"student/evaluation/test_{student.name}"
    # os.makedirs(memory_folder, exist_ok=True)  # Ensure directory exists
    # memory_file = f"{memory_folder}/evaluate_results_{postfix}.json"
    memory_file = f"stu_questionnaire/{student.name}_evaluate_results_{postfix}.json"
    os.makedirs(os.path.dirname(memory_file), exist_ok=True)

    with open(memory_file, 'w', encoding='utf-8') as f:
        json.dump(answers, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {memory_file}")

    print(f"\n--- End of evaluation ---")
