## Student system (`student/`)

This package models the student side of a learning process. It manages student memory and cognitive state, retrieves relevant concepts, generates and evaluates exercises, updates mastery, and records learning results for later analysis.

### Package structure

- `knowledge_graph.py`: Knowledge concepts, prerequisites, exercises, and mastery updates.
- `perceive.py`: Processes incoming information and updates the student's state.
- `exercise.py`: Retrieves questions, personalizes them, and evaluates answers.
- `evaluate.py`: Runs questionnaires and calculates profile scores.
- `global_methods.py`: Shared helpers, including grade and knowledge-point lookup.
- `main.py`: Synchronous example entry point.
- `prompt/`: LLM prompt builders and exercise workflows.
- `cognitive_module/`: Student profile, memory, and scratch state.
- `students/`, `saving/`, and `evaluation/`: Runtime data, saved state, and evaluation results.
- `questions/`: Question and knowledge-point data.
- `math_knowledge_points.json`: Math knowledge graph data.
- `big_five_inventory.json`, `cognitive_style_inventory.json`, and `questionnaire.json`: Student assessment data.

### Getting started

Use Python 3.10 or later and install the project dependencies from the repository root:

```bash
pip install -r requirements.txt
```

Run the synchronous example:

```bash
python -m student.main
```

Run the asynchronous exercise workflow:

```bash
python -m student.prompt.async_exercise
```

Runs may save student state under `student/saving/` and `student/students/`, and write orchestrated results under the repository's `results/` directory.

### Core concepts

- **Concept:** A learning point, with metadata such as grade, chapter, tags, and difficulty.
- **Prerequisite:** A dependency between concepts used for learning paths and mastery propagation.
- **Mastery:** The student's estimated proficiency and stability for a concept. New evidence can update mastery over time.
- **Evidence:** An answer or other observed behavior, such as correctness, response time, hints, or solution steps. Evidence supports mastery updates and diagnosis.

### Data flow

1. Load the knowledge graph from `math_knowledge_points.json` or `teaching_knowledge_points.json`.
2. Load student profile data from the inventory and questionnaire files.
3. Retrieve concepts and generate or select exercises.
4. Save answers and evidence under `saving/`, `students/`, or the project-level `results/` directory.
5. Update mastery in `knowledge_graph.py` from the recorded evidence.
6. Produce evaluation reports and visualization data where configured.

The knowledge graph represents concepts, exercises, students, and evidence. Its relationships include concept prerequisites, concepts assessed by an exercise, student mastery of a concept, and evidence linking a student answer to an exercise and concept. Mastery updates can use a probability estimate such as `p_hat = sigmoid(theta_student - b_item)` and adjust student ability with observed outcomes. Stability can increase with supporting answers and decrease after errors or elapsed time.

### Configuration and output

Module-level settings and shared constants are defined near the top of each module or in `global_methods.py`. Model calls, concurrency, logging, and random seeds may also be controlled through environment variables or command-line options where supported. Large question and memory collections are loaded on demand when possible.

Typical logs include `student_log.json` and `broadcast_log.json` in the repository root. Evaluation results and visualization inputs may be written under `results/<StudentName>/`.

### Troubleshooting

- If memory use is high, reduce concurrency or load large collections in batches.
- If mastery changes too quickly, adjust the learning rate, stability update, or exercise-to-concept weights.
- To adapt exercise difficulty, review retrieval filtering and the strategies in the exercise-generation workflow.

### Tests

Student examples and data are under `student/test/` and the `student/test_Student*` directories. Repository-level regression tests use the `test_*.py` naming pattern. Run the project test suite from the repository root with:

```bash
pytest -q
```

### Further development

Useful extension areas include exercise generation, assessment, mastery updates, and visualization. Keep generated run data in the existing save locations so results remain traceable. Knowledge-graph updates should retain enough evidence to support later review and interpretation.
