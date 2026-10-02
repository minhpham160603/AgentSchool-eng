# Observer feature testing guide

[Chinese](./TESTING_GUIDE_ZH.md)

New classroom examples, default configuration, and embedding model examples use English. Existing Chinese logs and generated reports remain unchanged, as do the `*_ZH.md` guides and source textbook PDF.

## English data and parser checks

From the repository root, run:

```bash
python -m unittest discover -s tests -v
```

These checks cover English and legacy grade lookup, student personalization, questionnaire prompts and saved response fields, reverse-scoring instructions, question-bank JSON Lines loading, and observer command JSON. They require Python and NumPy but make no LLM calls or embedding-model downloads. Questionnaire checks substitute a fixed model response, so they do not verify a live provider.

Some original question-bank records contain `�` (U+FFFD) from damaged source text. Unresolved damage remains in the English bank; repair or exclude affected items before evaluating their answers.

## Prerequisites

### 1. Environment variables

```bash
# Required: LLM API key (see util/model.py)
export SCHOOLAGENT_API_KEY="sk-xxxxxxxxxxxxxxxx"

# Optional: local embedding model directory or Hugging Face model id
export BGE_MODEL="BAAI/bge-small-en-v1.5"

# Optional: larger model for teacher vector DB
# export BGE_MODEL_L="BAAI/bge-large-en-v1.5"
```

**Windows (PowerShell)**

```powershell
$env:SCHOOLAGENT_API_KEY = "sk-xxxxxxxxxxxxxxxx"
```

### 2. Verify local model path (if set)

```bash
ls -lh "$BGE_MODEL"
```

If the directory does not exist, **unset** `BGE_MODEL` and let the program download from Hugging Face (needs network), or fix the path.

---

## Fast path (method A: helper script)

### Step 1: Edit `test_observer.sh`

```bash
cd /path/to/AgentSchool

# Set your real API key inside test_observer.sh
# Replace: export SCHOOLAGENT_API_KEY="your_api_key_here"
```

### Step 2: Run

```bash
./test_observer.sh
```

### Step 3: Send commands from another terminal

```bash
cd /path/to/AgentSchool

# Option A: helper script
./send_command.sh pause
./send_command.sh status
./send_command.sh resume
./send_command.sh exit
./send_command.sh rollback 12
./send_command.sh rollback 8 2

# Option B: edit observer_cmd.json directly
```

---

## Manual path (method B)

### Terminal 1 — start simulation

```bash
cd /path/to/AgentSchool
export SCHOOLAGENT_API_KEY="sk-xxxxxxxxxxxxxxxx"
# export BGE_MODEL="/path/to/your/embedding/model"

python run.py
```

Expected banner (excerpt): observer mode started, path to `observer_cmd.json`, list of commands including **rollback**.

### Terminal 2 — send commands

**Using the script**

```bash
cd /path/to/AgentSchool
./send_command.sh pause
```

**Editing JSON**

```json
{
  "command": "pause"
}
```

Save the file; terminal 1 should react within ~0.5 s.

---

## Test checklist

### Core commands

1. **pause**

```json
{"command": "pause"}
```

Expect: pause after current round, state printed, hint to resume.

2. **status** (while running)

```json
{"command": "status"}
```

Expect: time, teacher, students; simulation keeps running.

3. **resume** (after pause)

```json
{"command": "resume"}
```

Expect: simulation continues from pause point.

4. **exit**

```json
{"command": "exit"}
```

Expect: clean shutdown and state flush.

### Intervention (stub)

5. **intervene**

```json
{
  "command": "intervene",
  "intervention": {
    "type": "adjust_plan",
    "instruction": "Attention is low; add interaction"
  }
}
```

Expect: pause path engaged, payload printed, `handle_observer_intervention` called, “not fully implemented” style message is OK.

### Rollback

6. **rollback** (when `status_<lesson>_<round>.json` exists)

```json
{
  "command": "rollback",
  "rollback": { "turn": 12 }
}
```

Expect: teacher state restored from checkpoint; terminal notes **students are not rolled back**; run continues automatically on success.

### Robustness

7. **Invalid JSON** (e.g. paste plain text into the file)

Expect: no crash; invalid payload skipped.

8. **Unknown command**

```json
{"command": "unknown"}
```

Expect: ignored safely.

9. **Rapid sequence**

```bash
./send_command.sh pause
./send_command.sh status
./send_command.sh resume
```

Expect: each distinct command handled; remember identical consecutive commands may dedupe—vary commands if testing that path.

---

## Sample console output

### pause

```
======================================================================
📝 [Observer] Received command: pause
======================================================================
⏸️  The simulation will pause after the current round...
...
⏸️  [Observer] Simulation Paused
======================================================================
📊 Current Simulation Status
...
💡 Edit observer_cmd.json and set 'command': 'resume' to continue.
```

### status

```
======================================================================
📝 [Observer] Received command: status
======================================================================

📊 Current Simulation Status
======================================================================
```

### intervene (stub)

```
======================================================================
📝 [Observer] Received command: intervene
======================================================================
...
[Teacher.handle_observer_intervention] Observer intervention received
...
🤖 Teacher response: ⚠️ The observer intervention hook ran, but plan changes are not implemented yet.
```

---

## Troubleshooting

### `SCHOOLAGENT_API_KEY` not set

```bash
export SCHOOLAGENT_API_KEY="your_key"
```

Use the same shell session that runs `python run.py`.

### Embedding / model load errors

- Confirm `BGE_MODEL` points at a real directory, or `unset BGE_MODEL`
- Set `BGE_MODEL_L` only if you use the teacher vector DB path that reads it

### Commands ignored

- Save the file after edits
- Run from project root so `observer_cmd.json` is the one `run.py` watches
- Validate JSON: `python -m json.tool observer_cmd.json`

### Simulation exits immediately

Check configs:

```bash
ls -l config/teacher.json config/schedule.json config/student/
```

---

## Screen recording tips

1. Split view: simulation terminal + `observer_cmd.json` editor
2. Suggested order: start → wait → `pause` → `status` → `resume` → `rollback` (if files exist) → `intervene` → `exit`

---

## Test report template

```markdown
## Observer feature test report

**When**: YYYY-MM-DD HH:MM
**Environment**:
- Python:
- API key: set / not set
- BGE_MODEL:

| Case | Pass | Notes |
|------|------|-------|
| pause | | |
| resume | | |
| status | | |
| exit | | |
| rollback | | teacher-only |
| intervene | | stub |
| bad JSON | | |
| unknown command | | |

### Issues

1.

### Follow-ups

1.
```

---

More command semantics and extension notes: **[OBSERVER_GUIDE.md](./OBSERVER_GUIDE.md)**.

If this guide disagrees with the code, trust **`run.py`**.
