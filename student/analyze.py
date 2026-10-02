import json
import matplotlib.pyplot as plt
import os
import numpy as np
import glob
from pathlib import Path

def find_latest_exercise_files():
    """Find the latest exercise results file for each student."""
    base_path = Path(__file__).parent.parent / "results"
    student_files = {}

    # Find the latest results file for each student.
    for student_dir in base_path.glob("Student*"):
        if student_dir.is_dir():
            student_name = student_dir.name
            # Synchronising folder
            date_dirs = sorted([d for d in student_dir.iterdir() if d.is_dir()], reverse=True)
            if date_dirs:
                latest_date = date_dirs[0]
                exercise_dir = latest_date / "exercises"
                if exercise_dir.exists():
                    # Find the latest final results file.
                    final_files = list(exercise_dir.glob(f"{student_name}_exercise_results_final*.json"))
                    if final_files:
                        # Sort by change time, get latest
                        latest_file = max(final_files, key=lambda f: f.stat().st_mtime)
                        student_files[student_name] = latest_file

    return student_files

def load_exercise_results(file_path):
    """Load exercise results and recalculate their statistics."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Recalculate correct statistical information from detailed answers
    detailed_answers = data["data"]["detailed_answers"]

    # Recount
    total_questions = len(detailed_answers)
    correct_count = 0
    incorrect_count = 0
    modified_count = 0

    for question_id, answer_data in detailed_answers.items():
        # Statistics correct/Error
        if answer_data.get("correct", False):
            correct_count += 1
        else:
            incorrect_count += 1

        # Statistical individualization modifications
        if "question_modification" in answer_data or "personalization_log" in answer_data:
            modified_count += 1

    # Calculate correct rate
    accuracy = (correct_count / total_questions * 100) if total_questions > 0 else 0
    modification_rate = (modified_count / total_questions * 100) if total_questions > 0 else 0

    # Rebuild accurate statistical information
    corrected_stats = {
        "total_questions": total_questions,
        "correct_answers": correct_count,
        "incorrect_answers": incorrect_count,
        "accuracy_percentage": round(accuracy, 2)
    }

    # Personalise Change Information
    personalization_stats = {
        "total_questions": total_questions,
        "modified_questions": modified_count,
        "modification_rate": round(modification_rate, 2),
        "unmodified_questions": total_questions - modified_count
    }

    # Extract raw data for comparison
    original_stats = data["data"]["statistics"]["performance"]
    original_personalization = data["data"]["statistics"].get("personalization", {})

    return {
        "stats": corrected_stats,
        "original_stats": original_stats,
        "answers": detailed_answers,
        "personalization": personalization_stats,
        "original_personalization": original_personalization,
        "test_info": data["data"]["test_info"]
    }

# Find and load the latest student files
student_files = find_latest_exercise_files()
print(f"Found exercise results for {len(student_files)} students:")
for student, file_path in student_files.items():
    print(f"  {student}: {file_path}")

# Storage of statistical information
stats = {}
all_student_data = {}

for student_name, file_path in student_files.items():
    try:
        data = load_exercise_results(file_path)
        all_student_data[student_name] = data

        # Extract data from recalculated statistical information
        performance = data["stats"]
        original_performance = data["original_stats"]

        stats[student_name] = {
            'correct': performance["correct_answers"],
            'wrong': performance["incorrect_answers"],
            'total': performance["total_questions"],
            'accuracy': performance["accuracy_percentage"]
        }

        print(f"\n{student_name} Statistical comparison:")
        print(f"  📊 Correct statistics for recalculation:")
        print(f"     Total number of questions: {performance['total_questions']}")
        print(f"     Correct: {performance['correct_answers']}")
        print(f"     Error: {performance['incorrect_answers']}")
        print(f"     Correct Rate: {performance['accuracy_percentage']:.2f}%")

        print(f"  📋 Original Statistics in File:")
        print(f"     Total number of questions: {original_performance['total_questions']}")
        print(f"     Correct: {original_performance['correct_answers']}")
        print(f"     Error: {original_performance['incorrect_answers']}")
        print(f"     Correct Rate: {original_performance['accuracy_percentage']:.2f}%")

        # Check for consistency in statistics
        if (performance["correct_answers"] != original_performance["correct_answers"] or
            performance["incorrect_answers"] != original_performance["incorrect_answers"]):
            print(f"  ⚠️  Warning: Inconsistent statistics!")
            print(f"     Correct answer difference: {performance['correct_answers'] - original_performance['correct_answers']}")
            print(f"     Wrong answer difference: {performance['incorrect_answers'] - original_performance['incorrect_answers']}")
        else:
            print(f"  ✅ Statistics are consistent")

        # Personalized revision of statistics
        if data["personalization"]:
            print(f"  Change title: {data['personalization'].get('modified_questions', 0)}/{data['personalization'].get('total_questions', 0)}")
            print(f"  Revision Rate: {data['personalization'].get('modification_rate', 0):.2f}%")

    except Exception as e:
        print(f"Error processing results for {student_name}: {e}")
        continue

# Visualize 1：Correct/Error answer distribution
if stats:
    labels = list(stats.keys())
    correct_counts = [stats[name]['correct'] for name in labels]
    wrong_counts = [stats[name]['wrong'] for name in labels]
    accuracies = [stats[name]['accuracy'] for name in labels]

    # Basic statistical charts
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # Left: Correct/An error number stacked column
    x = range(len(labels))
    ax1.bar(x, correct_counts, width=0.6, label='Correct', color='green', alpha=0.7)
    ax1.bar(x, wrong_counts, width=0.6, bottom=correct_counts, label='Wrong', color='red', alpha=0.7)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45)
    ax1.set_ylabel('Number of Questions')
    ax1.set_title('Distribution of Correct/Wrong Answers for Each Student')
    ax1.legend()

    # Add Total Tab
    for i, (correct, wrong) in enumerate(zip(correct_counts, wrong_counts)):
        total = correct + wrong
        ax1.text(i, total + 1, str(total), ha='center', va='bottom', fontweight='bold')

    # Right graph: right strut
    bars = ax2.bar(x, accuracies, width=0.6, color=['green' if acc >= 60 else 'orange' if acc >= 40 else 'red' for acc in accuracies], alpha=0.7)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=45)
    ax2.set_ylabel('Accuracy (%)')
    ax2.set_title('Accuracy Rate for Each Student')
    ax2.set_ylim(0, 100)

    # Add percentage label
    for i, (bar, acc) in enumerate(zip(bars, accuracies)):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{acc:.1f}%', ha='center', va='bottom', fontweight='bold')

    plt.tight_layout()
    plt.show()
else:
    print("No valid student data files found")

# Visualize 2：Detailed analysis of each subject (if available)）
if all_student_data:
    # Collecting all student question-by-issue answers
    all_results = []
    student_names = list(all_student_data.keys())
    max_questions = 0

    for student_name in student_names:
        answers = all_student_data[student_name]["answers"]
        # Will answers Converts the dictionary to a list in order of title number
        student_answers = []
        # Safe resolution question_id，Processing formats including scientific algorithms
        valid_question_ids = []
        for k in answers.keys():
            try:
                # First try to convert directly to integer
                if k.isdigit():
                    valid_question_ids.append(int(k))
                else:
                    # Try to convert scientific algorithms or floating points
                    float_val = float(k)
                    if float_val.is_integer() and 0 <= float_val < 10000:  # Rational title ID Scope
                        valid_question_ids.append(int(float_val))
                    else:
                        print(f"⚠️  Skip invalid title ID: {k} (Value: {float_val})")
            except (ValueError, OverflowError):
                print(f"⚠️  Skip unsolved topics ID: {k}")
                continue

        question_ids = sorted(valid_question_ids)
        max_questions = max(max_questions, max(question_ids) + 1 if question_ids else 0)

        for i in range(max_questions):
            if str(i) in answers:
                student_answers.append(1 if answers[str(i)].get('correct', False) else 0)
            else:
                student_answers.append(np.nan)  # Missing data
        all_results.append(student_answers)

    if max_questions > 0:
        # Convert: Line=Title, column=Students
        all_results = np.array(all_results).T

        # Number of correct persons per subject
        correct_counts_per_question = np.nansum(all_results, axis=1)

        # Visualize 3：The right number of columns per item
        plt.figure(figsize=(15, 6))
        bars = plt.bar(np.arange(len(correct_counts_per_question)),
                       correct_counts_per_question,
                       color=plt.cm.RdYlGn(correct_counts_per_question/len(student_names)))
        plt.xlabel('Question Number')
        plt.ylabel('Number of Students Correct')
        plt.title(f'Number of Students Correct per Question (Total Students: {len(student_names)})')
        plt.yticks(range(len(student_names) + 1))

        # Add Average Line
        avg_correct = np.nanmean(correct_counts_per_question)
        plt.axhline(y=avg_correct, color='blue', linestyle='--', alpha=0.7,
                   label=f'Average: {avg_correct:.1f}')
        plt.legend()

        # The subject of marking difficulties (the correct number is less than half the average)）
        difficult_threshold = avg_correct / 2
        difficult_questions = np.where(correct_counts_per_question <= difficult_threshold)[0]
        if len(difficult_questions) > 0:
            plt.scatter(difficult_questions, correct_counts_per_question[difficult_questions],
                       color='red', s=50, marker='x', label=f'Difficult Questions (≤{difficult_threshold:.1f})')
            plt.legend()

        plt.tight_layout()
        plt.show()

        # Visualize 4：Hot try - Students vs questions
        if len(student_names) <= 10 and max_questions <= 200:  # It's too big
            plt.figure(figsize=(max(12, max_questions//10), max(8, len(student_names))))
            plt.imshow(all_results.T, cmap='RdYlGn', aspect='auto', interpolation='nearest', vmin=0, vmax=1)
            plt.colorbar(label='Correct (1) / Wrong (0)', shrink=0.6)
            plt.xlabel('Question Number')
            plt.ylabel('Student')
            plt.title('Heatmap: Per-Question, Per-Student Correctness')
            plt.yticks(range(len(student_names)), student_names)
            plt.tight_layout()
            plt.show()

# Visualize 5：Individualized revision of statistics (if any)）
personalization_data = {}
for student_name, data in all_student_data.items():
    # More stringent data checks
    if (data.get("personalization") and
        isinstance(data["personalization"], dict) and
        data["personalization"].get('total_questions', 0) > 0):
        personalization_data[student_name] = data["personalization"]

if personalization_data:
    try:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        students = list(personalization_data.keys())
        modification_rates = []
        modified_counts = []
        total_counts = []

        # Securely extract data to ensure the correct type of value
        for s in students:
            pers_data = personalization_data[s]
            try:
                mod_rate = float(pers_data.get('modification_rate', 0))
                mod_count = int(pers_data.get('modified_questions', 0))
                total_count = int(pers_data.get('total_questions', 0))

                modification_rates.append(mod_rate)
                modified_counts.append(mod_count)
                total_counts.append(total_count)
            except (ValueError, TypeError) as e:
                print(f"⚠️  Data conversion error {s}: {e}")
                modification_rates.append(0)
                modified_counts.append(0)
                total_counts.append(0)

        # Left graph: change rate
        bars1 = ax1.bar(range(len(students)), modification_rates, color='skyblue', alpha=0.7)
        ax1.set_xticks(range(len(students)))
        ax1.set_xticklabels(students, rotation=45, ha='right')
        ax1.set_ylabel('Modification Rate (%)')
        ax1.set_title('Question Modification Rate by Student')
        ax1.set_ylim(0, 100)

        # Add numeric labels to left
        for i, (bar, rate) in enumerate(zip(bars1, modification_rates)):
            if rate > 0:  # Show labels only when data are available
                ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        f'{rate:.1f}%', ha='center', va='bottom', fontsize=9)

        # Right graph: number of changes vs Total (Right stack)
        x_pos = np.arange(len(students))
        unmodified_counts = [total - modified for total, modified in zip(total_counts, modified_counts)]

        bars2 = ax2.bar(x_pos, unmodified_counts, width=0.6, label='Unmodified Questions',
                       color='lightgray', alpha=0.7)
        bars3 = ax2.bar(x_pos, modified_counts, width=0.6, bottom=unmodified_counts,
                       label='Modified Questions', color='orange', alpha=0.7)

        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(students, rotation=45, ha='right')
        ax2.set_ylabel('Number of Questions')
        ax2.set_title('Question Modification Count by Student')
        ax2.legend()

        # Add Number Label
        for i, (total, modified, unmodified) in enumerate(zip(total_counts, modified_counts, unmodified_counts)):
            # Total label
            if total > 0:
                ax2.text(i, total + max(total_counts) * 0.02, str(total),
                        ha='center', va='bottom', fontweight='bold', fontsize=9)
            # Modify quantitative labels (if changes to title)）
            if modified > 0:
                label_y = unmodified + modified/2
                ax2.text(i, label_y, str(modified),
                        ha='center', va='center', color='white', fontweight='bold', fontsize=8)

        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"⚠️  Error while visualizing personalizing changes in statistics: {e}")
        print(f"    personalization_data: {personalization_data}")
else:
    print("📝 No valid personalized changes found")

# Print Summary Report
print("\n" + "="*50)
print("Analytical summary report")
print("="*50)
for student_name, data in all_student_data.items():
    print(f"\n{student_name}:")
    performance = data["stats"]
    print(f"  📊 Overall performance: {performance['correct_answers']}/{performance['total_questions']} = {performance['accuracy_percentage']:.1f}%")

    if data["personalization"]:
        pers = data["personalization"]
        print(f"  🔧 Personalization of topics: {pers.get('modified_questions', 0)}/{pers.get('total_questions', 0)} = {pers.get('modification_rate', 0):.1f}%")

        # Analyse the effect of the change
        if 'modification_effectiveness' in pers:
            eff = pers['modification_effectiveness']
            print(f"  ✨ Modify Effects: {eff.get('improved_performance', 'N/A')}")

    print(f"  ⏱️  Test Time: {data['test_info']['test_date']}")
    print(f"  🏷️  Test Type: {data['test_info']['postfix']}")

print("\n Overall statistics:")
if stats:
    avg_accuracy = np.mean([stats[name]['accuracy'] for name in stats])
    total_questions = sum([stats[name]['total'] for name in stats])
    total_correct = sum([stats[name]['correct'] for name in stats])
    print(f"  🎯 Average correct rate: {avg_accuracy:.1f}%")
    print(f"  📝 Total number of topics: {total_questions}")
    print(f"  ✅ Total correct: {total_correct}")

    if personalization_data:
        avg_mod_rate = np.mean([personalization_data[s].get('modification_rate', 0) for s in personalization_data])
        print(f"  🔧 Average change rate: {avg_mod_rate:.1f}%")
