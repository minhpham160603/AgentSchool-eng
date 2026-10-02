import asyncio
import os
import sys
import json
import random
import time
from datetime import datetime, timedelta, time as dt_time

from util.BroadcastSys import BroadcastSys
from util.Events import Event
from util.Recorder import Recorder
from util.TimeManager import *
from student.cognitive_module.student import Student
from teacher.teacher import Teacher
from util.BroadcastMessage import *
from student.exercise import *
from student.evaluate import *


# Tee output to both the terminal and the log file.
class Tee:
    def __init__(self, file):
        self.file = file
        self.original_stdout = sys.__stdout__

    def write(self, data):
        self.file.write(data)
        self.file.flush()
        self.original_stdout.write(data)
        self.original_stdout.flush()

    def flush(self):
        self.file.flush()
        self.original_stdout.flush()


def initialize_students_from_config(config_dir, broadcast_system, recorder):
    students = {}
    for filename in os.listdir(config_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(config_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception as e:
                print(f"Could not load file {filename}: {e}")
                continue

            folder_path = config.get("folder")
            if not folder_path:
                print(f"Warning: {filename} is missing the 'folder' field; skipping.")
                continue

            os.makedirs(folder_path, exist_ok=True)

            scratch_content = {k: v for k, v in config.items() if k != "folder"}
            scratch_path = os.path.join(folder_path, "scratch.json")
            with open(scratch_path, "w", encoding="utf-8") as f:
                json.dump(scratch_content, f, ensure_ascii=False, indent=4)

            for fname in ["nodes.json", "embeddings.json"]:
                path = os.path.join(folder_path, fname)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({}, f)

            student_name = config.get("name")
            if not student_name:
                print(f"Warning: {filename} is missing the 'name' field; skipping.")
                continue

            student_instance = Student(
                name=student_name,
                broadcast_sys=broadcast_system,
                recorder=recorder,
                folder_mem_saved=folder_path
            )
            students[student_name] = student_instance
            print(f"Initialized student {student_name}; state directory: {folder_path}")
    return students


# Global Variables
log_file = None
action_recorder = None
broadcast_recorder = None
student_recorder = None
base_log_dir = None


def switch_log_file(event_id=None):
    global log_file, action_recorder, broadcast_recorder, student_recorder, base_log_dir

    if log_file:
        log_file.close()

    current_log_dir = f"{base_log_dir}/{event_id}" if event_id else base_log_dir
    os.makedirs(current_log_dir, exist_ok=True)
    log_path = f'{current_log_dir}/output.txt'
    log_file = open(log_path, 'w', encoding='utf-8')
    sys.stdout = Tee(log_file)

    if action_recorder:
        action_recorder.set_file_path(f"{current_log_dir}/action_log.jsonl")
    if broadcast_recorder:
        broadcast_recorder.set_file_path(f"{current_log_dir}/broadcast_log.jsonl")
    if student_recorder:
        student_recorder.set_file_path(f"{current_log_dir}/student_log.jsonl")


# Run one student feedback task with error handling.
async def student_feedback(student, feedback_type, feedback_func, file, postfix):
    print(f"{student.name}: starting {feedback_type}.")
    try:
        await feedback_func(student, file, postfix)
        print(f"{student.name}: completed {feedback_type}.")
    except Exception as e:
        print(f"Error: {student.name}'s {feedback_type} failed: {e}")


# ========== Observer function ==========

async def observer_command_listener(pause_flag, command_file="observer_cmd.json"):
    """
    Listen for observer commands in the command file.
    
    Args:
        pause_flag: Mutable observer state.
        command_file: Path to the observer command file.
    """
    last_modified = 0  # Retained for compatibility; command detection uses last_command.
    
    # Create initial command file and provide instructions
    command_template = {
        "command": "",
        "info": "Set the command field and save this file to send a command.",
        "available_commands": {
            "pause": "Pause after the current round",
            "resume": "Resume the simulation",
            "status": "Print the current simulation state",
            "intervene": "Request a teaching-plan adjustment (stub)",
            "rollback": "Restore teacher state from a saved round",
            "exit": "Stop the simulation"
        },
        "example": {
            "command": "pause",
            "note": "The command takes effect after you save this file."
        }
    }
    
    if not os.path.exists(command_file):
        with open(command_file, 'w', encoding='utf-8') as f:
            json.dump(command_template, f, indent=2, ensure_ascii=False)
    
    command_file_abs = os.path.abspath(command_file)
    print(f"\n{'='*70}")
    print(f"📝 [Observer Mode] Started")
    print(f"{'='*70}")
    print(f"Command File: {command_file_abs}")
    print(f"\nAvailable commands:")
    print(f"  • pause     - Pause after the current round")
    print(f"  • resume    - Resume the simulation")
    print(f"  • status    - Print the current simulation state")
    print(f"  • intervene - Request a teaching-plan adjustment (stub)")
    print(f"  • rollback  - Restore teacher state from a saved round")
    print(f"  • exit      - Stop the simulation")
    print(f"\nTo send a command, edit {command_file}, set the 'command' field, and save.")
    print(f"{'='*70}\n")
    
    while True:
        try:
            if os.path.exists(command_file):
                # Read the file and deduplicate commands using last_command.
                with open(command_file, 'r', encoding='utf-8') as f:
                    command_data = json.load(f)
                command = command_data.get("command", "").strip().lower()
                
                if command and command != pause_flag.get("last_command"):
                    print(f"\n{'='*70}")
                    print(f"📝 [Observer] Received command: {command}")
                    print(f"{'='*70}")
                    
                    pause_flag["command"] = command
                    pause_flag["last_command"] = command
                    
                    if command == "pause":
                        pause_flag["paused"] = True
                        print(f"⏸️  The simulation will pause after the current round...\n")
                    elif command == "resume":
                        pause_flag["paused"] = False
                        print(f"▶️  Resuming the simulation...\n")
                    elif command == "status":
                        pause_flag["show_status"] = True
                        pause_flag["paused"] = True
                        pause_flag["intervention"] = command_data.get("intervention", {})
                        print(f"🔧 [Stub] Intervention received and awaiting processing...\n")
                        pause_flag["paused"] = True
                        pause_flag["rollback"] = command_data.get("rollback", {})
                        print(f"🔙 Rollback command received and awaiting processing...\n")
                    elif command == "exit":
                        pause_flag["exit"] = True
                        print(f"🛑 Shutting down the simulation cleanly...\n")
                        break
                    
                    # Empty command file to prevent repetition of triggers
                    with open(command_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            "command": "",
                            "info": "Command processed",
                            "last_executed": command,
                            "timestamp": datetime.now().isoformat(),
                            "available_commands": command_template["available_commands"]
                        }, f, indent=2, ensure_ascii=False)
            
            await asyncio.sleep(0.5)  # Poll every 0.5 seconds.
            
        except json.JSONDecodeError:
            # Ignore malformed JSON while the file is being written.
            await asyncio.sleep(1)
        except Exception as e:
            print(f"[Error] Observer command listener failed: {e}")
            await asyncio.sleep(1)


def show_simulation_status(teacher, students, time_manager, runtime_snapshot=None):
    """Print the current simulation state."""
    print(f"\n{'='*70}")
    print(f"📊 Current Simulation Status")
    print(f"{'='*70}")
    
    # Time information
    current_time = time_manager.current_time
    print(f"\n⏱️  Time Information:")
    print(f"  • Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S %A')}")
    current_event = time_manager.get_current_active_event()
    print(f"  • Current Event: {current_event.type} (ID: {current_event.id})")
    
    # Teacher information
    print(f"\n👨‍🏫 Teacher status:")
    print(f"  • Name: {teacher.name}")
    print(f"  • Lesson: {teacher.class_number}")
    print(f"  • Teaching phase: {teacher.period}")
    print(f"  • Round: {teacher.current_turn}/{teacher.class_turns}")
    
    # Truncate long teaching content for display.
    content = teacher.content if hasattr(teacher, 'content') else "No teaching content available."
    if len(content) > 100:
        content = content[:100] + "..."
    print(f"  • Current content: {content}")
    # Show the teacher's last action, if available.
    if runtime_snapshot and isinstance(runtime_snapshot, dict):
        teacher_snap = runtime_snapshot.get("teacher", {})
        last_action = teacher_snap.get("action")
        if last_action:
            print(f"  • Previous Actions: {last_action}")
    
    # Student information
    print(f"\n👥 Student status:")
    for student_name, student in students.items():
        # Prefer attention_level, falling back to attention.
        attention = getattr(student.scratch, 'attention_level', None)
        if attention is None:
            attention = getattr(student.scratch, 'attention', 0.0)
        action = getattr(student.scratch, 'action', '')
        if (attention is None or attention == 0.0 or attention == 0) and runtime_snapshot and isinstance(runtime_snapshot, dict):
            snap = runtime_snapshot.get("students", {}).get(student_name, {})
            attention = snap.get("attention", attention)
        if (not action) and runtime_snapshot and isinstance(runtime_snapshot, dict):
            snap = runtime_snapshot.get("students", {}).get(student_name, {})
            action = snap.get("action", action) or ""
        print(f"  • {student_name}:")
        try:
            print(f"      - Attention: {float(attention):.2f}")
        except Exception:
            print(f"      - Attention: {attention}")
        print(f"      - Current action: {action}")
        print(f"      - Memory nodes: {len(student.mem.seq_thought) + len(student.mem.seq_knowledge)}")
    
    print(f"\n{'='*70}\n")


async def handle_observer_intervention(pause_flag, teacher, students, time_manager, runtime_snapshot=None):
    """
    Process observer status, intervention, and rollback commands.
    
    Args:
        pause_flag: Mutable observer state.
        teacher: Teacher instance.
        students: Student dictionary
        time_manager: Simulation time manager.
    """
    command = pause_flag.get("command")
    
    if command == "status":
        show_simulation_status(teacher, students, time_manager, runtime_snapshot)
        pause_flag["show_status"] = False
        pause_flag["command"] = None
    elif command == "intervene":
        # Call the teacher's observer intervention hook.
        intervention_data = pause_flag.get("intervention", {})
        
        print(f"\n{'='*70}")
        print(f"🔧 [Observer intervention] Processing...")
        print(f"{'='*70}")
        print(f"Intervention payload: {json.dumps(intervention_data, indent=2, ensure_ascii=False)}")
        
        # Call the teacher intervention hook.
        response = await teacher.handle_observer_intervention(intervention_data)
        
        print(f"\n🤖 Teacher response: {response}")
        print(f"{'='*70}\n")
        
        pause_flag["intervention"] = None
        pause_flag["command"] = None

    elif command == "rollback":
        rollback_data = pause_flag.get("rollback", {}) or {}
        turn = rollback_data.get("turn") or rollback_data.get("k")
        cls = rollback_data.get("class") or teacher.class_number
        print(f"\n{'='*70}")
        print(f"🔙 [Rollback] Restoring lesson {cls}, round {turn}")
        print(f"{'='*70}")
        try:
            if turn is None:
                raise ValueError("Missing rollback.turn")
            turn = int(turn)
            cls = int(cls)
            status_file = os.path.join(teacher.status_file_dirname, f"status_{cls}_{turn}.json")
            if not os.path.exists(status_file):
                raise FileNotFoundError(f"Status file does not exist: {status_file}")
            ok = teacher.jump(status_file)
            if ok:
                runtime_snapshot["teacher"] = {
                    "action": f"rollback to turn {turn}",
                    "turn": teacher.current_turn,
                    "content": getattr(teacher, "content", "")
                }
                print(f"✅ Restored teacher state from checkpoint: {status_file}")
                print(f"⚠️ Rollback restores teacher state only; student state is unchanged.")
                # Autoregeneration of residual plan after retroactive (no change in implemented part))
                try:
                    msg = teacher.regenerate_remaining_plan()
                    print(f"🧠 {msg}")
                except Exception as e2:
                    print(f"⚠️ Could not recreate the remaining teaching plan: {e2}")
        except Exception as e:
            print(f"❌ Rollback failed: {e}")
        finally:
            pause_flag["rollback"] = None
            pause_flag["command"] = None
            # Continue automatically after retroactive completion (cancelled pause))
            if pause_flag.get("paused", False):
                pause_flag["paused"] = False
                print(f"\n{'='*70}")
                print(f"▶️  Rollback complete. Resuming the simulation.")
                print(f"{'='*70}\n")


async def main():
    global base_log_dir, action_recorder, broadcast_recorder, student_recorder
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_log_dir = f'logs/{timestamp}'
    sim_wall_start = time.time()

    # Initialise System Component
    action_recorder = Recorder("")
    broadcast_recorder = Recorder("")
    student_recorder = Recorder("")
    broadcast_system = BroadcastSys(broadcast_recorder)

    # Time Manager
    time_manager = TimeManager(
        daily_schedule_path="config/schedule.json",
        broadcast_system=broadcast_system,
        day_start_time="08:00"
    )

    # Initial Log Settings
    course_id = 1
    switch_log_file(course_id)
    print(f"Logging started. Initial directory: {base_log_dir}/{course_id}")

    # Initialization students and teachers
    students = initialize_students_from_config("config/student", broadcast_system, student_recorder)
    teacher = await Teacher.initialize_teacher_async(broadcast_system, "config/teacher.json", list(students.values()))

    # Subscription to broadcast systems
    broadcast_system.subscribe(teacher, "teacher")
    for student_name in students:
        student = students[student_name]
        broadcast_system.subscribe(student, "student")
        broadcast_system.subscribe(student, student_name)

    # ========== Activate observer function ==========
    pause_flag = {
        "paused": False,
        "command": None,
        "last_command": None,
        "show_status": False,
        "intervention": None,
        "rollback": None,
        "exit": False
    }
    runtime_snapshot = {"teacher": {}, "students": {}}
    
    # Start an observer command listening mission (recycling with main))
    observer_task = asyncio.create_task(
        observer_command_listener(pause_flag, command_file="observer_cmd.json")
    )

    # Main cycle
    print("===== Pedagogical scene simulation begins =====")
    finished_courses = 0
    # Add: modified main cycle logic
    while finished_courses < time_manager.total_courses:
        # ========== Check observer orders ==========
        # Check exit signs
        if pause_flag.get("exit", False):
            print(f"\n{'='*70}")
            print(f"🛑 [Observer] Exit command received. Stopping the simulation.")
            print(f"{'='*70}\n")
            observer_task.cancel()
            break
        
        # Check the pause sign
        if pause_flag.get("paused", False):
            print(f"\n{'='*70}")
            print(f"⏸️  [Observer] Simulation Paused")
            print(f"{'='*70}")
            
            # Show current status (fill information that may be missing with a snapshot))
            show_simulation_status(teacher, students, time_manager, runtime_snapshot)
            
            print(f"💡 Edit observer_cmd.json and set 'command': 'resume' to continue.")
            print(f"   Or set 'command': 'status' to view the current state.")
            print(f"{'='*70}\n")
            
            # Waiting for resumption order
            while pause_flag.get("paused", False) and not pause_flag.get("exit", False):
                # Treatment of other orders (e.g status,intervene,rollback)
                if pause_flag.get("show_status", False) or pause_flag.get("command") in ["status", "intervene", "rollback"]:
                    await handle_observer_intervention(pause_flag, teacher, students, time_manager, runtime_snapshot)
                
                await asyncio.sleep(0.5)
            
            # Check for withdrawal orders received during suspension
            if pause_flag.get("exit", False):
                continue
            
            print(f"\n{'='*70}")
            print(f"▶️  [Observer] Simulation resumed")
            print(f"{'='*70}\n")
        
        # Deal with non-suspension status/rollback/Intervention orders
        if pause_flag.get("show_status", False) or pause_flag.get("command") in ["status", "intervene", "rollback"]:
            await handle_observer_intervention(pause_flag, teacher, students, time_manager, runtime_snapshot)
        
        current_date = time_manager.current_time.date()
        print(f"\n=== Date: {current_date} {current_date.strftime('%A')} ===")

        while True:
            current_time = time_manager.current_time
            print(f"\n Time: {current_time.strftime('%H:%M:%S')}")

            # Instant exit check (intracycle))
            if pause_flag.get("exit", False):
                break

            current_event = time_manager.get_current_active_event()

            # Panel discussion
            if current_event.type == "class":
                # Teacher behaviour
                teacher_action = teacher.move()
                print(teacher_action)
                await action_recorder.log(current_time, "teacher_action",
                                  {"teacher": teacher.name, "action": teacher_action})
                # Update teacher snapshots
                runtime_snapshot["teacher"] = {
                    "action": teacher_action,
                    "turn": teacher.current_turn,
                    "content": getattr(teacher, "content", "")
                }
                decide_leader = False
                infos = students["StudentA"].infos
                for info in infos:
                    if info.get("active_event") == "group_discussion_start" and info.get("receiver") == "student":
                        decide_leader = True
                        discussion_content = info.get("content", "")
                        break

                if decide_leader:
                    for student in students.values():
                        student.scratch.action = "group_discussion"
                        student.infos = [info for info in student.infos if not (
                                info.get("active_event") == "group_discussion_start" and
                                info.get("receiver") == "student"
                        )]

                    leader_student = random.choice(list(students.values()))
                    leader_student.scratch.isLeader = True
                    msg = BroadcastMessage(
                        message_type=MessageType.COMMAND,
                        active_event="group_discussion_start",
                        speaker=teacher.name,
                        content=discussion_content
                    )
                    teacher.broadcast_sys.publish_sync(leader_student.name, msg)
                    print(msg)

                # Student behaviour (sliding together))
                for student in students.values():
                    student.update_students_list(list(students.values()))

                tasks = [student.move() for student in students.values()]
                student_actions = await asyncio.gather(*tasks)

                # Recording student behaviour
                for student, action in zip(students.values(), student_actions):
                    if action:
                        print(action)
                        await action_recorder.log(current_time, "student_action",
                                                  {"student": student.name, "action": action})
                    # Update student snapshots
                    runtime_snapshot["students"][student.name] = {
                        "action": action or "",
                        "attention": (
                            getattr(student.scratch, "attention_level", None)
                            if getattr(student.scratch, "attention_level", None) is not None
                            else getattr(student.scratch, "attention", 0.0)
                        )
                    }

            # Course completion
            if current_event.end == current_time:
                overtime_minutes = teacher.delay_turns()
                # New: It's not really new. It's the longest set-up we've got 9 Minutes, trying to change here, but not longer than the class
                if overtime_minutes >= 10:
                    overtime_minutes = 9

                action = time_manager.handle_class_end(
                    current_event=current_event,
                    overtime_minutes=overtime_minutes
                )

                if action == ClassEndAction.CLASS_OVER:
                    current_log_dir = f"{base_log_dir}/{current_event.parent_event_id or current_event.id}"
                    os.makedirs(current_log_dir, exist_ok=True)
                    target_path = f'{current_log_dir}/target.txt'
                    with open(target_path, 'w', encoding='utf-8') as target_file:
                        target_file.write(teacher.target)

                    # print("=" * 60)
                    # print("At the end of the current course, the student feedback is used for the evaluation")
                    # postfix = f"{timestamp}_{current_event.id}"

                    # Step-by-step on all student feedback
                    # feedback_tasks = []
                    # for student in students.values():
                    #     # Add Questions
                    #     exercise_task = asyncio.create_task(
                    #         student_feedback(
                    #             student,
                    #             "It's a question",
                    #             exercise,
                    #             "student/data.jsonl",
                    #             postfix
                    #         )
                    #     )
                    #     feedback_tasks.append(exercise_task)
                    #
                    #     # Add a questionnaire task
                    #     evaluate_task = asyncio.create_task(
                    #         student_feedback(
                    #             student,
                    #             "Questionnaire",
                    #             evaluate,
                    #             "student/questionnaire.json",
                    #             postfix
                    #         )
                    #     )
                    #     feedback_tasks.append(evaluate_task)
                    #
                    # # And sent all the feedback missions
                    # await asyncio.gather(*feedback_tasks)

                    simulation_end = False
                    # Add: Check for completion of course
                    finished_courses += 1

                    # Update the curriculum number of all students
                    for student in students.values():
                        student.set_for_new_class()
                    
                    print(f"=" * 60)
                    print(f"Lesson {finished_courses} ended (index: {finished_courses - 1})")
                    print(f"Student state saved to: student/saving/{{StudentName}}/{current_time.strftime('%Y%m%d')}_{finished_courses - 1}/")
                    print(f"=" * 60)
                    

                    if finished_courses >= time_manager.total_courses:
                        simulation_end = True
                        break  # Jump out of inner circle

                    course_id += 1
                    switch_log_file(course_id)
                    print(f"Log directory changed to: {base_log_dir}/{course_id}")

                    # Check if there's any follow-up today
                    remaining_today_classes = [
                        e for e in time_manager.events
                        if e.type == "class" and not e.parent_event_id
                            and e.start.date() == current_date
                            and e.start > current_time
                    ]
                    if not remaining_today_classes:
                        print(f"[INFO] No more classes are scheduled for {current_date}.")
                        break  # Jump out of inner circle

            # === Deal with soft pauses before advance time: finish the current rotation before suspending ===
            if pause_flag.get("paused", False):
                print(f"\n{'='*70}")
                print(f"⏸️  [Observer] Simulation paused after the current round.")
                print(f"{'='*70}")

                # Shows the latest status of the moment (includes current round) teacher/student Outcome of behaviour)
                show_simulation_status(teacher, students, time_manager, runtime_snapshot)
                print(f"💡 Edit observer_cmd.json and set 'command': 'resume' to continue.")
                print(f"   Or set 'command': 'status' to view the current state.")
                print(f"{'='*70}\n")

                while pause_flag.get("paused", False) and not pause_flag.get("exit", False):
                    if pause_flag.get("show_status", False) or pause_flag.get("command") in ["status", "intervene", "rollback"]:
                        await handle_observer_intervention(pause_flag, teacher, students, time_manager, runtime_snapshot)
                    await asyncio.sleep(0.2)

                if pause_flag.get("exit", False):
                    break

                print(f"\n{'='*70}")
                print(f"▶️  [Observer] Simulation resumed")
                print(f"{'='*70}\n")

            # Time advance
            time_manager.current_time += timedelta(seconds=time_manager.round_time)
            await asyncio.sleep(0.1)  # Waiting for a walk

        # Add: Check for completion of course
        if simulation_end:
            break   # End simulation

        # Go to the next day
        time_manager.proceed_to_next_day()

    # ========== Simulate Cleanup ==========
    print("\n===== Simulation complete =====")
    
    # Cancel Observer Task
    if not observer_task.cancelled():
        observer_task.cancel()
        try:
            await observer_task
        except asyncio.CancelledError:
            pass
    
    sim_wall_cost = time.time() - sim_wall_start
    print(f"[TIME] Simulation duration: {sim_wall_cost:.2f}s")
    print(f"\n{'='*70}")
    print(f"✅ Simulation completed.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
