import json
import sys
import asyncio

from student.retrieve import retrieve

sys.path.append("../../")

from student.cognitive_module.memory import *
from student.cognitive_module.scratch import *
from student.cognitive_module.memory import *
from student.cognitive_module.scratch import *
from student.cognitive_module.student import *
from student.prompt.run_ds_prompt import *
from student.perceive import perceive
from student.retrieve import *
from student.reflect import *
from student.plan import *
from student.execute import execute
from student.exercise import *
from student.global_methods import load_grade_knowledge_points
from datetime import datetime, timedelta
import os
from util.BroadcastSys import BroadcastSys
from util.Recorder import *
from util.BroadcastMessage import *
from util.TimeManager import TimeManager


PERSONALITY_CONFIG = {
    'Extraversion': {
        'high': {
            'label': 'Outgoing',
            'anchor': "You often think aloud and enjoy sharing ideas in conversation, even while they are still developing."
        },
        'low': {
            'label': 'Reserved',
            'anchor': "You tend to think things through privately, listen carefully, and speak when you feel ready."
        }
    },
    'Agreeableness': {
        'high': {
            'label': 'Cooperative',
            'anchor': "You value group harmony, support others, and try to resolve disagreements tactfully."
        },
        'low': {
            'label': 'Direct and critical',
            'anchor': "You value evidence and logic, and are willing to challenge ideas directly, even when others may disagree."
        }
    },
    'Conscientiousness': {
        'high': {
            'label': 'Organized and persistent',
            'anchor': "You try to understand a problem before answering, persist when unsure, and keep your reasoning organized."
        },
        'low': {
            'label': 'Flexible and spontaneous',
            'anchor': "You prefer a flexible approach and may lose focus when a task feels difficult or uninteresting."
        }
    },
    'Emotional Stability': {
        'high': {
            'label': 'Emotionally stable',
            'anchor': "You usually stay calm under pressure and can recover steadily after a mistake."
        },
        'low': {
            'label': 'Emotionally reactive',
            'anchor': "You may feel nervous or less confident when questioned or faced with uncertainty."
        }
    },
    'Openness to Experience': {
        'high': {
            'label': 'Open and curious',
            'anchor': "You enjoy novel and abstract ideas and like exploring why an answer works, not only what the answer is."
        },
        'low': {
            'label': 'Practical and conventional',
            'anchor': "You prefer clear, concrete questions and familiar approaches over abstract theoretical discussion."
        }
    }
}

SIX_THINKING_HATS = {
	"white_hat": "Focus on facts, evidence, and information that is still missing.",
	"green_hat": "Explore creative ideas, possibilities, and alternatives.",
	"yellow_hat": "Consider benefits, value, and promising opportunities.",
	"black_hat": "Look critically for risks, problems, and weaknesses.",
	"red_hat": "Consider feelings, attitudes, intuition, and personal preferences.",
	"blue_hat": "Organize the discussion, summarize progress, and plan next steps."
}

class Student:
    # TODO：Add recorder Category
    def __init__(self, name, broadcast_sys=False, recorder=False, folder_mem_saved=False):
        self.name = name

        self.broadcast_sys = broadcast_sys

        self.recorder = recorder  # Recorder Examples of categories used to document student behaviour

        f_mem_saved = f"{folder_mem_saved}"
        self.mem = Memory(f_mem_saved)

        scratch_saved = f"{folder_mem_saved}/scratch.json"
        self.scratch = Scratch(scratch_saved)

        # TODO: Need to create all agent After each example agent Subscribe separately
        if self.broadcast_sys and isinstance(self.broadcast_sys, BroadcastSys):
            # self.broadcast_sys.subscribe(self, "Teacher")
            self.broadcast_sys.subscribe(self, "student")
            self.broadcast_sys.subscribe(self, self.name)  # Subscription to your name
            group = "group" + str(self.scratch.group)
            self.broadcast_sys.subscribe(self, group) # Subscribe to your own group, Group name"group0", "group1", ...
                                                #TODO: Remember to update this subscription later if you want to set the group function during the process


        self.infos = [] # list of strings, To store all information in the current environment

        self.current_turn = 0  # Current rotation

        self.current_course_number = 0  # Current course number(From 0 Start)

        self.config_path = "config"

        self.config_schedule = f"{self.config_path}/schedule.json"

        self.config_teacher = f"{self.config_path}/teacher.json"

        with open(self.config_schedule, "r", encoding="utf-8") as f:
            schedule_data = json.load(f)

        with open(self.config_teacher, "r", encoding="utf-8") as f:
            teacher_data = json.load(f)

        self.round_time = schedule_data.get("round_time", 30)  # Every turn of time, default to 30 sec

        self.teacher_name = teacher_data.get("name", "Teacher")  # The teacher's name"Teacher"

        self.time_manager = TimeManager(
            daily_schedule_path="config/schedule.json",
            broadcast_system=self.broadcast_sys,
            day_start_time="08:00"
        )

        self.scratch.current_time = self.time_manager.current_time  # Initialize current time

        self.students_list = []

        # Curriculum knowledge points for the student's grade; this is not a
        # list of concepts the student has already mastered.
        self.knowledge_points_of_the_grade = load_grade_knowledge_points(self)  # Load the grade-level curriculum.

    def receive_broadcast(self, info):
        """
        It's for students infos list。
        INPUT:
            info: dict
            info = {"message_type": "class",
                "active_event": "lecture",
                "speaker": self.name,
                "content": self.sections[self.current_section_turn],
                "time": self.current_time} # Should add time
            TODO: This category requires variables: sender sender（Examples of students or teachers），
        OUTPUT:
            None
        """
        self.infos.append(info)
        print(f"[{self.name}] Message received: {info.get('active_event', 'unknown')}")  # Debug Information

    def receive_broadcast_sync(self, info):
        """
        Synchronize receiving broadcast messages with the same feature as the walk-in version
        INPUT:
            info: dict
        OUTPUT:
            None
        """
        self.infos.append(info)
        print(f"[{self.name}] Synchronous message received: {info.get('active_event', 'unknown')}")

    """
    def move(self):

        INPUT:
            student
            file: File deposited
            i: Round
            info: String, current information

        OUTPUT:
            String to show the current student

        print(f"--- Now {self.scratch.current_time} ---")
        infos = self.infos
        print(f"Could not handle message: {infos}")
        folder_name = f"student/test_{self.name}"

        # If knowledge，info Like
        # {"message_type": "class",
        #  "active_event": "lecture",
        #  "speaker": self.name,
        #  "content": self.sections[self.current_section_turn]}
        # If event，info Like
        # Questions and answers：
        #   "message_type": "class",
        #    "active_event": "response",
        #    "speaker": self.name,
        #    "content": response.choices[0].message.content.strip()
        # Panel discussion：
        #（Start）
        #    "message_type": "class",
        #    "active_event": "group_discussion_start",
        #    "speaker": self.name,
        #    "content": f"Please have a panel discussion：{point}"
        #（End）
        #    "message_type": "class",
        #    "active_event": "group_discussion_end",
        #    "speaker": self.name,
        #    "content": "Conclusion of the panel discussion。"


        # Every time you process a message, then add 30s；The current status is saved for every processing
        # Generally, there's only one message that can be handled in class (because the teacher only says one word at a time) infos This list has only one element
        # During the panel discussion,，infos This list may have more than one element？）

        overall_thougts = {}  # To store all thoughts

        for i, info in enumerate(infos):
            node = perceive(self, info.get("content", None), info.get("speaker", None), info.get("time", self.scratch.current_time), info.get("active_event", None))
            retrieved = retrieve(self, node)
            if retrieved and retrieved[node.content]:
                print(f"Retrieved relevant memories: {retrieved[node.content]}")
            else:
                print("No relevant memories retrieved.")

            reflected = reflect(self, retrieved)

            if(reflected):
                overall_thougts.update(reflected)  # Add the current cycle of reflection to the overall picture

            objects = plan(self, self.broadcast_sys.subscriptions.get("Students", []), node, self.broadcast_sys.subscriptions.get("Teacher", None))

            execute(self, objects)

            # Time+30s
            self.scratch.current_time = self.scratch.current_time + timedelta(seconds=30) # Assumptions of time after each perception 30 sec

            # Save Current Status
            self.scratch.save(f"{folder_name}/{self.name}_scratch_{self.current_turn}_{i}.json")  # Save Current scratch Status to File

            memory_file = f"{folder_name}/{self.name}_memory_{self.current_turn}_{i}"
            if not os.path.exists(memory_file):
                os.makedirs(memory_file, exist_ok=True) #Ensure memory_file Exists as Directory
            self.mem.save(memory_file)


            details = {
                "thoughts": reflected if reflected else {},
            }
            self.recorder.log(self.scratch.current_time, info.get("active_event", "unknown_event"), details)




        # Clear processed messages.
        self.infos = []

        if overall_thougts is None:
            return None

        return run_ds_prompt_generalize(overall_thougts)"""

    async def move(self):
        """
        INPUT:
            student
            file: File deposited
            i: Round
            info: String, current information

        OUTPUT:
            String to show the current student
        """
        try:
            print(f"--- Now {self.scratch.current_time} ---")
            infos = self.infos
            print(f"{self.name} could not handle message: {infos}")
            saving_folder_name = "student/saving"
            folder_name = f"{saving_folder_name}/{self.name}"

            # Initializing Variables
            # Initializing variables outside the cycle
            reflected = {}
            absorbed_info = ""
            learned = ""

            if infos is None or len(infos) == 0:
                action = self.scratch.action
            else:
                action = infos[0].get("active_event")

            if "group_discussion" in action:
                self.action = "group_discussion"
            elif action == "ask_question" or action == "answer":
                self.action = "answer"
            else:
                self.action = "listen"

            overall_thougts = {}  # To store all thoughts

            for i, info in enumerate(infos):
                # If you're in class, skip first
                #if info.get("active_event") == "lecture":
                    #self.infos = []
                    #return None

                # Test panel discussion only
                # if info.get("active_event") != "group_discussion_start" and info.get("active_event") != "group_discussion" and info.get("active_event") != "group_discussion_end":
                    # continue  # Skip events not discussed by the panel

                try:
                    # Sensory stage - Step Call
                    print(f"{self.name} is handling message {i + 1}...")
                    node, absorbed_info, learned = await perceive(self, info.get("content", None), info.get("speaker", None), info.get("receiver", None),
                                info.get("time", info.get("current_time", None)), info.get("active_event", None))

                except Exception as e:
                    print(f"{self.name} encountered an error during perception: {e}")
                    continue  # Skip current information and continue processing next

                try:
                    # Retrieving phase - Step Call
                    retrieved = await retrieve(self, node)

                    if retrieved and retrieved.get(node.content):
                        print(f"{self.name} retrieved relevant memories: {retrieved[node.content]}")
                    else:
                        print(f"{self.name} retrieved no relevant memories.")

                except Exception as e:
                    print(f"{self.name} encountered an error during memory retrieval: {e}")
                    retrieved = {}  # Use empty dictionary as default value

                try:
                    # Reflection phase - Step Call
                    reflected = await reflect(self, retrieved)


                    if reflected:
                        overall_thougts.update(reflected)  # Add the current cycle of reflection to the overall picture

                except Exception as e:
                    print(f"{self.name} encountered an error during reflection: {e}")
                    reflected = {}  # Use empty dictionary as default value

                try:
                    # Planning phase - Step Call
                    #students_list = self.broadcast_sys.subscriptions.get("Students", []) if self.broadcast_sys else []
                    #teacher = self.broadcast_sys.subscriptions.get("Teacher", None) if self.broadcast_sys else None
                    # Through config/student Folders to retrieve the names of students from the same group
                    """students_list = []
                    student_config_path = "config/student"
                    for filename in os.listdir(student_config_path):
                        with open(os.path.join(student_config_path, filename), "r", encoding="utf-8") as f:
                            student_config = json.load(f)
                            print(f"Students {student_config.get('name', 'Unknown')} Group: {student_config.get('group', 'Unknown')}")
                        if student_config.get("group") == self.scratch.group:
                            students_list.append(student_config.get("name", "Unknown"))"""

                    students_list = [student.name for student in self.students_list if hasattr(student, 'name') and student.scratch.group == self.scratch.group]


                    objects = plan(self, students_list, node, info.get("active_event", None), info.get("receiver", None))



                except Exception as e:
                    print(f"{self.name}Error at planning stage: {e}")
                    objects = []  # Use empty list as default

                try:
                    # Implementation phase - Step Call
                    await execute(self, objects, retrieved=retrieved, info=info)

                except Exception as e:
                    print(f"{self.name}Error at implementation stage: {e}")
                    # The failure of implementation continues\

                try:
                    # Dynamic adjustment of attention and pressure
                    event_type = info.get("active_event", "")
                    self.adjust_attention_and_stress(event_type)

                    # Further adjustments based on reflection
                    if reflected:
                        # Keep your mind up when you think deep
                        reflection_bonus = min(0.1, len(reflected) * 0.02)
                        self.scratch.attention_level += reflection_bonus
                        self.scratch.attention_level = min(1.0, self.scratch.attention_level)

                except Exception as e:
                    print(f"{self.name}Status Adjustment Error: {e}")

                """try:
                    # Time Update


                    self.scratch.current_time = self.scratch.current_time + timedelta(seconds=self.round_time)

                except Exception as e:
                    print(f"Time Update Error: {e}")
                    # Use current time if time update failed
                    from datetime import datetime
                    self.scratch.current_time = datetime.now()"""

                try:
                    # Save Memory - Step File Operation
                    # New structure: student/saving/{StudentName}/{Date}_{CourseNumber}/{StudentName}_{turn}_{i}
                    course_date = self.scratch.current_time.strftime("%Y%m%d")
                    course_number = self.current_course_number

                    # Build Full Path
                    course_dir = f"{folder_name}/{course_date}_{course_number}"
                    memory_file = f"{course_dir}/{self.name}_{self.current_turn}_{i}"

                    if not os.path.exists(memory_file):
                        await asyncio.to_thread(os.makedirs, memory_file, exist_ok=True)

                    # Execute saving operations using a walk-through thread
                    await asyncio.to_thread(self.mem.save, memory_file)

                except Exception as e:
                    print(f"Error saving memory: {e}")
                    # Continue without interruption

                try:
                    # Save Status - Step File Operation
                    scratch_file = f"{memory_file}/scratch.json"
                    await asyncio.to_thread(self.scratch.save, scratch_file)

                except Exception as e:
                    print(f"Save scratch Status Error: {e}")
                    # Continue without interruption

                try:
                    # Log - Step Call
                    if self.recorder:
                        details = {
                            "name": self.name,
                            "stress": self.scratch.stress,
                            "attention": self.scratch.attention_level,
                            "absorbed": absorbed_info if absorbed_info else "",
                            "learned": learned if learned else "",
                            "reflection": reflected if reflected else {},
                        }

                        await self.recorder.log(self.scratch.current_time,
                                        info.get("active_event", "unknown_event"), details)


                except Exception as e:
                    print(f"Log Log Error: {e}")
                    # Log failure does not affect the main process

                # Generate a performance of current student to broadcast - Step Call
                try:

                    content = await run_ds_prompt_summarize_status(self)

                    msg = BroadcastMessage(
                        current_time=self.scratch.current_time,
                        message_type=MessageType.CLASS,
                        active_event="expression",
                        speaker=self.name,
                        content=content
                    )

                    self.broadcast_sys.publish_sync("teacher", msg)

                except Exception as e:
                    print(f"Could not publish the student's status: {e}")

            # Clear processed messages.
            self.infos = []

            # Update turn
            self.current_turn += 1

            # Update Time
            self.update_time()

            try:
                # Generate summary
                """if overall_thougts:
                    return run_ds_prompt_generalize(overall_thougts)
                else:
                    return None"""
                if self.action == "listen" and reflected is not None:
                    return "reflection"
                else:
                    return self.action

            except Exception as e:
                print(f"Error Generating Summary: {e}")
                return None

        except Exception as e:
            print(f"move Error executing function as a whole: {e}")
            # Make sure you empty the information list even if you have an error
            self.infos = []
            return None

    def update_time(self):
        """
        Update current time, add another round
        """
        self.scratch.current_time = self.scratch.current_time + timedelta(seconds=self.round_time)

    def update_students_list(self, students_list):
        """
        Import Student Examples list, update student list
        INPUT:
            students_list: List[Student]
        """
        self.students_list = students_list

    """def adjust_attention_and_stress(self, event_type, duration=0, success_rate=None):
        ""
        Align attention and stress with event type dynamics
        INPUT:
            event_type: str, Event type
            duration: int, Constant rounds of activity
            success_rate: float, Success rate(0-1)，Optional
        ""
        # Basic adjustment rules
        adjustments = {
            "lecture": {"attention": -0.05, "stress": 0.02},  # Hearings: reduced attention, increased stress
            "group_discussion_start": {"attention": 0.1, "stress": -0.05},  # Start the discussion: Increased attention, reduced stress
            "group_discussion": {"attention": 0.05, "stress": -0.02},  # Discussion: Staying positive
            "ask_question": {"attention": 0.15, "stress": 0.1},  # Questioned: Increased attention and pressure
            "answer": {"attention": 0.1, "stress": 0.05},  # Answer the question: Attention up, light pressure
            "practice": {"attention": -0.02, "stress": 0.03},  # Practice: Little attention, little pressure
        }

        if event_type in adjustments:
            adj = adjustments[event_type]

            # Base adjustment
            self.scratch.attention_level += adj["attention"]
            self.scratch.stress += adj["stress"]

            # Adjustments based on duration (extraordinary activities increase fatigue)）
            if duration > 3:
                fatigue_factor = (duration - 3) * 0.02
                self.scratch.attention_level -= fatigue_factor
                self.scratch.stress += fatigue_factor * 0.5

            # Adjusted for success rate (if provided)）
            if success_rate is not None:
                if success_rate > 0.8:  # High success rate
                    self.scratch.attention_level += 0.05
                    self.scratch.stress -= 0.03
                elif success_rate < 0.4:  # Low success rate
                    self.scratch.attention_level -= 0.03
                    self.scratch.stress += 0.05

        # Limit range
        self.scratch.attention_level = max(0.0, min(1.0, self.scratch.attention_level))
        self.scratch.stress = max(0.0, min(1.0, self.scratch.stress))

        print(f"{self.name} Status Adjustment: Attention={self.scratch.attention_level:.2f}, Pressure={self.scratch.stress:.2f}")"""

    def adjust_attention_and_stress(self, event_type, success_rate=None):
        """
        Aligning attention and pressure with a smooth dynamic equilibrium system。
        This version reduces pulse intensity and introduces state inertia。
        """
        # --- 1. Calculate a personalized base value” (Baseline) ---
        attention_baseline = 0.5 + (self.scratch.personality.get('Extraversion', 15) - 15) * 0.01 + (self.scratch.personality.get('Conscientiousness', 15) - 15) * 0.015
        stress_baseline = 0.3 + (self.scratch.personality.get('Emotional Stability', 15) - 15) * -0.02

        # --- 2. Adjusting Mean Return and Introducing State inertia” ---
        # 【We see the rate of return and the impact of the event as the force of the change of status”
        # 'inertia_factor' Trends in representational status unchanged，'change_factor' Representation of changing status trends
        inertia_factor = 0.85  # Yes 85%It's probably the last round (The higher the value, the smoother the change)
        change_factor = 1.0 - inertia_factor # Only 15%The space is reserved for "change."”

        # a. Calculates the pull of the mean return”
        regression_pull = change_factor * (attention_baseline - self.scratch.attention_level)

        # b. The "push" to calculate the pulse of the event”
        pulse_push = {"attention": 0.0, "stress": 0.0}

        # 【Adjustment points) significantly lower base pulse values, which now represent “change trends” rather than absolute increments
        pulse_definitions = {
            # Focus on "resources," listening consumes it, discussing/Question added to its “needs””
            "lecture":          {"attention": -0.1, "stress": 0.02}, # Ongoing consumption
            "group_discussion": {"attention": 0.15, "stress": 0.05}, # Active participation
            "ask_question":     {"attention": 0.4, "stress": 0.25}, # Exciting
            "answer_success":   {"attention": 0.1, "stress": -0.15}, # Success brings relief
            "answer_fail":      {"attention": -0.05, "stress": 0.2}, # Failure brings stress
            "idle":             {"attention": 0.0, "stress": -0.03},# It's natural for stress to drop during rest
        }

        # Select the appropriate pulse according to the type of event and success rate
        effective_event = event_type
        if event_type == "answer":
            effective_event = "answer_success" if success_rate is not None and success_rate > 0.6 else "answer_fail"

        if effective_event in pulse_definitions:
            pulse = pulse_definitions[effective_event]

            # Individualized reconciliation factor (part maintained but less effective)）
            attention_factor = 1.0
            stress_factor = 1.0
            if effective_event == "group_discussion" and self.scratch.personality.get('Extraversion', 15) > 18:
                attention_factor = 1.3
            if effective_event == "ask_question" and self.scratch.personality.get('Emotional Stability', 15) < 12:
                stress_factor = 1.8

            pulse_push["attention"] = change_factor * pulse["attention"] * attention_factor
            pulse_push["stress"] = change_factor * pulse["stress"] * stress_factor

        # --- 3. Calculate final state changes ---
        # New Status = Most of the old state + A small percentage of changes affected by the return of mean values and the pulse of events
        self.scratch.attention_level = (self.scratch.attention_level * inertia_factor) + regression_pull + pulse_push["attention"]
        regression_pull_stress = change_factor * (stress_baseline - self.scratch.stress)
        self.scratch.stress = (self.scratch.stress * inertia_factor) + regression_pull_stress + pulse_push["stress"] # Attention: Pressure return also needs to be calculated

        # --- 4. Inter-state interaction (Still unchanged, but more smooth value) ---
        max_attention_under_stress = 1.0 - (self.scratch.stress ** 2) * 0.5
        self.scratch.attention_level = min(self.scratch.attention_level, max_attention_under_stress)

        # --- 5. Limit final value range (No change) ---
        self.scratch.attention_level = max(0.0, min(1.0, self.scratch.attention_level))
        self.scratch.stress = max(0.0, min(1.0, self.scratch.stress))

        print(f"{self.name} State adjusted: Attention={self.scratch.attention_level:.2f} (Benchmark: {attention_baseline:.2f}), Pressure={self.scratch.stress:.2f} (Benchmark: {stress_baseline:.2f})")

    def update_group(self, group):
        "Update broadcast Group subscriptions"
        group = "group" + str(self.scratch.group)
        self.broadcast_sys.subscribe(self, group)

    def get_group(self):
        """
        Get the group number where the student is
        """
        return self.scratch.group

    def update_student_scratch(self, students_list, group):
        """
        Updates for students scratch Status, including student lists and group numbers
        """
        self.update_students_list(students_list)
        self.update_group(group)

    def get_full_personality_description(self, trait_name):
        """
        Generate a complete descriptive sentence with strength, base description and behavioral influence anchors based on the value of the personality。
        """
        value = self.scratch.personality.get(trait_name, 0)

        # 1. Determine strength words(level)and describe direction(desc_key: 'high' or 'low')
        if value >= 23:
            level, desc_key = 'extremely high', 'high'
        elif value >= 19:
            level, desc_key = 'high', 'high'
        elif value >= 15:
            level, desc_key = 'moderately high', 'high'
        elif value >= 12:
            level, desc_key = 'slightly high', 'high'
        elif value >= 9:
            level, desc_key = 'slightly low', 'low'
        else:  # 5-8
            level, desc_key = 'very low', 'low'

        # 2. Get basic tags and behavioural anchors from the configuration centre
        try:
            config = PERSONALITY_CONFIG[trait_name][desc_key]
            base_label = config['label']
            anchor_text = config['anchor']
        except KeyError:
            # If the configuration is not found, return a secure default value
            return f"No description is available for {trait_name}."

        # 3. Combining final sentences
        # Special wording for dealing with neutral zones
        full_description = f"Your {trait_name} is {level} ({base_label}). {anchor_text}"

        return full_description

    def generate_persona_prompt(self):
        traits = ['Extraversion', 'Agreeableness', 'Conscientiousness', 'Emotional Stability', 'Openness to Experience']
        descriptions = [self.get_full_personality_description(trait) for trait in traits]
        return "\n".join(descriptions)

    def get_personalized_retrieval_params(self):
        """
        According to the students, scratch Data calculates individualized search parameters
        INPUT:
            student: Student Category
        OUTPUT:
            retrieval_params: dict, Include individualised parameters
        """
        params = {
            "n_count": 10,  # Default Retrieving Number
            "recency_weight": 1.0,
            "importance_weight": 1.0,
            "relevance_weight": 1.0,
            "similarity_threshold": 0.1,  # Similarity threshold
            "diversity_factor": 0.0,  # Diversity factor
        }

        scratch = self.scratch

        # 1. Attention-based adjustments
        attention_level = getattr(scratch, 'attention_level', 0.8)
        if attention_level < 0.4:  # StudentA: 0.34 (Low profile)
            params["n_count"] = max(5, int(params["n_count"] * 0.6))  # Reduction to 6 individual
            params["recency_weight"] = 1.3  # More dependent on recent memories
            print(f"[Personalization] {self.name}: low attention ({attention_level:.2f}); retrieving {params['n_count']} memories.")
        elif attention_level > 0.7:
            params["n_count"] += 3
            params["diversity_factor"] = 0.2

        # 2. Pressure-based adjustments
        stress = getattr(scratch, 'stress', 0.0)
        if stress > 0.3:  # StudentA: 0.35 (Medium pressure)
            params["importance_weight"] = 1.4  # More important information
            params["recency_weight"] = 1.2     # Prioritize recent familiarization
            params["similarity_threshold"] += 0.05  # Increased similarity requirements
            print(f"[Personalization] {self.name}: high stress ({stress:.2f}); using a conservative retrieval strategy.")

        # 3. Based on five major personality profiles
        personality = getattr(scratch, 'personality', {})
        if personality:
            extraversion = personality.get('Extraversion', 15)
            if extraversion <= 12:
                params["n_count"] = max(4, params["n_count"] - 2)  # Inner search fewer
                params["importance_weight"] *= 1.2
            elif extraversion >= 20:  # High outward orientation
                params["n_count"] += 2
                params["diversity_factor"] = 0.1

            conscientiousness = personality.get('Conscientiousness', 15)
            if conscientiousness <= 10:
                params["recency_weight"] *= 1.3  # Low due diligence depends more on recent memory
                params["similarity_threshold"] -= 0.02  # Lower Standards
                print(f"[Personalization] {self.name}: lower conscientiousness ({conscientiousness:.2f}); favoring recent memories.")
            elif conscientiousness >= 20:  # Due diligence
                params["importance_weight"] *= 1.4
                params["n_count"] += 2

            openness = personality.get('Openness to Experience', 15)
            if openness <= 10:
                params["diversity_factor"] = 0.0  # Low openness doesn't require diversity
                params["relevance_weight"] *= 1.2  # More direct attention
                print(f"[Personalization] {self.name}: lower openness ({openness:.2f}); favoring directly relevant memories.")
            elif openness >= 20:
                params["diversity_factor"] = 0.3
                params["n_count"] += 3
                params["relevance_weight"] *= 0.9  # Appropriately lower relevance requirements to allow wider access

            # Emotional Stability (Emotional Stability): StudentA = 19 (Lower)
            emotional_stability = personality.get('Emotional Stability', 15)
            if emotional_stability <= 10:
                params["n_count"] = max(4, params["n_count"] - 2)  # Reduce information overload
                params["importance_weight"] *= 1.3
                print(f"[Personalization] {self.name}: lower emotional stability ({emotional_stability:.2f}); reducing cognitive load.")
            elif emotional_stability >= 20:  # High emotional stability
                params["n_count"] += 1
                params["diversity_factor"] += 0.1

            agreeableness = personality.get('Agreeableness', 15)
            if agreeableness <= 10:  # Low human
                params["relevance_weight"] *= 1.1  # More attention to directly relevant information
            elif agreeableness >= 20:  # Humanity
                # Humanization primarily affects social learning and has a relatively small impact on personal access
                pass

        """# 4. Based on cognitive adjustment
        cognitive_state = getattr(scratch, 'cognitive_state', [])
        if cognitive_state:
            cognitive_text = " ".join(cognitive_state) if isinstance(cognitive_state, list) else str(cognitive_state)

            # Test metre cognitive overestimation - StudentA Features
            if "It's an overestimation" in cognitive_text or "Self-assessment" in cognitive_text:
                params["importance_weight"] *= 1.5  # More dependent on objective and important information
                params["similarity_threshold"] += 0.03  # Raise standards and avoid overconfidence
                print(f"[Personalization] {student.name} Overestimation of meta-perceptions, strengthening of objective information dependency")

            # Testing capacity assessment gaps
            if "Less skilled" in cognitive_text or "Actual 65%" in cognitive_text:
                params["n_count"] = max(6, params["n_count"] - 2)  # Appropriate reduction
                params["recency_weight"] *= 1.2  # More dependent on recent learning
                print(f"[Personalization] {student.name} Capacity assessment gaps exist and conservative access is used")"""

        """# 5. Based on emotional state
        affective_state = getattr(scratch, 'affective_state', [])
        if affective_state:
            affective_text = " ".join(affective_state) if isinstance(affective_state, list) else str(affective_state)

            # Testing frustration and anxiety - StudentA Features
            if "Frustration" in affective_text or "Anxiety" in affective_text:
                params["importance_weight"] *= 1.4  # Dependence on critical basic knowledge
                params["n_count"] = max(5, params["n_count"] - 3)  # Reduce cognitive load
                params["recency_weight"] *= 1.3  # Prioritize recent success stories
                print(f"[Personalization] {student.name} There's frustration/Anxiety. Supportive search strategies")

            # Test motivation level
            if "Medium motivation" in affective_text:
                params["relevance_weight"] *= 1.1  # A little more relevance"""

        # 6. Learning style-based adjustments
        learning_style = getattr(scratch, 'learning_style', {})
        if learning_style:
            # Sensory Type：StudentA Yes"sensing"
            perception = learning_style.get('perception', [])
            if "sensing" in str(perception).casefold():
                params["importance_weight"] *= 1.3  # Sensory values specific and important information
                params["similarity_threshold"] += 0.02  # Need more direct information
                print(f"[Personalization] {self.name}: sensing preference detected; prioritizing concrete, important information.")

            # Process Type：StudentA Yes"reflective"
            processing = learning_style.get('processing', [])
            if "reflective" in str(processing).casefold():
                params["n_count"] += 2  # Rethinking requires more information to think about
                params["importance_weight"] *= 1.2
                print(f"[Personalization] {self.name}: reflective preference detected; increasing retrieval depth.")

            # Understanding Type：StudentA Yes"sequential"
            understanding = learning_style.get('understanding', [])
            if "sequential" in str(understanding).casefold():
                params["recency_weight"] *= 1.1  # Sequenced focus on structured learning
                # Consideration could be given to ranking the results in order of importance

        # 7. Application of final limits and adjustments
        params["n_count"] = max(3, min(20, params["n_count"]))  # Limit to 3-20 Between
        params["similarity_threshold"] = max(0.01, min(0.5, params["similarity_threshold"]))

        return params

    def get_hat_weights(self):
        """
        Calculate weights for the six thinking hats from the student's
        personality traits.
        OUTPUT:
            weights: dict, The weight of each hat
        """
        personality = self.scratch.personality

        # Use neutral scores when a personality value is unavailable.
        extraversion = personality.get('Extraversion', 15)
        agreeableness = personality.get('Agreeableness', 15)
        conscientiousness = personality.get('Conscientiousness', 15)
        emotional_stability = personality.get('Emotional Stability', 15)
        openness = personality.get('Openness to Experience', 15)

        # Base weight (all hats have a minimum weight) 1.0）
        weights = {
            "white_hat": 1.0,  # White hat: objective facts
            "green_hat": 1.0,  # Green hat: creativity
            "yellow_hat": 1.0, # Yellow hat: positive optimism
            "black_hat": 1.0,  # Black hat: Caution
            "red_hat": 1.0,    # Red hat: Emotional intuition
            "blue_hat": 1.0    # Blue hat: organizational control
        }

        # Adjust weight to character
        # Outwardity: High outward preference for green hats (creative interaction) and red hats (emotional expression)）
        if extraversion > 18:
            weights["green_hat"] += 1.5
            weights["red_hat"] += 1.2
        elif extraversion < 12:
            weights["blue_hat"] += 0.8  # Introverts prefer organizational thinking

        # Due diligence: high-level due diligence preference for white hat (fact) and blue hat (organization)）
        if conscientiousness > 18:
            weights["white_hat"] += 1.5
            weights["blue_hat"] += 1.3
            weights["black_hat"] += 0.8  # Caution
        elif conscientiousness < 12:
            weights["red_hat"] += 0.7  # Intuitives are preferred

        # Emotional stability: high stability prefers yellow hats (optimistic) and white hats (reasonable)）
        if emotional_stability > 18:
            weights["yellow_hat"] += 1.4
            weights["white_hat"] += 0.9
        elif emotional_stability < 12:
            weights["red_hat"] += 1.3  # The unstable prefer emotional expression
            weights["black_hat"] += 0.6  # Carefully avoid risk

        # Openness: High openness prefers green hats (new ideas) and yellow hats (exploration)）
        if openness > 18:
            weights["green_hat"] += 1.4
            weights["yellow_hat"] += 1.1
        elif openness < 12:
            weights["blue_hat"] += 1.0  # Traditional preference for structure

        # Humanization: High-profile preference for yellow hats (harmonization) and red hats (complementarity)）
        if agreeableness > 18:
            weights["yellow_hat"] += 1.3
            weights["red_hat"] += 1.0
        elif agreeableness < 12:
            weights["black_hat"] += 1.2  # It's cheap to judge

        return weights

    def choose_one_hat(self):
        """
        Weighted randomly from six thinking hats based on the weight of personality。
        OUTPUT:
            hat: str, Selected Hat Description
        """
        weights = self.get_hat_weights()

        # Get the hat list and the corresponding weight
        hats = list(SIX_THINKING_HATS.keys())
        hat_weights = [weights[hat] for hat in hats]

        # Use weight for random selection
        total_weight = sum(hat_weights)
        if total_weight == 0:
            # If the weight is all 0，Use even distribution
            chosen_hat = random.choice(hats)
        else:
            # Weight random selection
            r = random.uniform(0, total_weight)
            cumulative = 0
            chosen_hat = hats[0]  # Default selection first
            for i, weight in enumerate(hat_weights):
                cumulative += weight
                if r <= cumulative:
                    chosen_hat = hats[i]
                    break

        chosen_desc = SIX_THINKING_HATS[chosen_hat]
        print(f"{self.name} selected the {chosen_hat} thinking perspective: {chosen_desc}")
        return chosen_desc

    def get_all_misconceptions(self):
        """
        Collect all misconceptions recorded for the student.
        OUTPUT:
            dict: {knowledge_tag: [misconceptions]}
        """
        misconceptions_dict = {}

        for node in self.mem.seq_knowledge:
            if node.misconceptions:
                tag = node.knowledge_tag[0] if node.knowledge_tag else "uncategorized"
                if tag not in misconceptions_dict:
                    misconceptions_dict[tag] = []
                misconceptions_dict[tag].extend(node.misconceptions)

        return misconceptions_dict

    def get_certain_misconceptions(self, knowledge_tag):
        """
        Taking a student's misperception at a point of knowledge
        INPUT:
            knowledge_tag: str, Knowledge Point Label
        OUTPUT:
            list: [misconceptions]
        """
        misconceptions = []

        for node in self.mem.seq_knowledge:
            if node.misconceptions and knowledge_tag in node.knowledge_tag:
                misconceptions.extend(node.misconceptions)

        return misconceptions

    async def read_latest_saving_dir(self, course_date=None, course_number=None):
        """
        Step to read the latest save folder path (avoid blocking event cycle)）

        New File Structure: student/saving/{StudentName}/{Date}_{CourseNumber}/{StudentName}_{X}_{Y}
        For example:: student/saving/StudentA/20251101_1/StudentA_0_0

        INPUT:
            course_date: str, Course date, format is YYYYMMDD，If for None Find Recent
            course_number: int, course number, if None Find Recent
        """

        saving_base_dir = f"student/saving/{self.name}"
        # Check for directory in the online process
        exists = await asyncio.to_thread(os.path.exists, saving_base_dir)
        if not exists:
            print(f"Not found {self.name} Save directory: {saving_base_dir}")
            return None

        base = Path(saving_base_dir)

        # List and filter directories in back-office threads
        def _find_latest():
            # First find date_Course number catalogue
            course_dirs = [d for d in base.iterdir() if d.is_dir()]
            if not course_dirs:
                print(f"Contents {saving_base_dir} No subdirectories")
                return None

            # If a date and course number are specified, find the corresponding directory directly
            if course_date is not None and course_number is not None:
                target_course_dir = base / f"{course_date}_{course_number}"
                if not target_course_dir.exists():
                    print(f"The specified course catalogue does not exist: {target_course_dir}")
                    return None
                course_dir = target_course_dir
            else:
                # Otherwise, find the latest course catalogue
                def course_key(dir_path):
                    parts = dir_path.name.split('_')
                    if len(parts) >= 2:
                        try:
                            date = int(parts[0])
                            course_num = int(parts[1])
                            return (date, course_num)
                        except ValueError:
                            return (-1, -1)
                    return (-1, -1)

                course_dirs.sort(key=course_key, reverse=True)
                course_dir = course_dirs[0]

            # Find the latest version in the course catalogue
            version_dirs = [d for d in course_dir.iterdir() if d.is_dir()]
            if not version_dirs:
                print(f"Course catalogue {course_dir} No version subdirectories")
                return None

            def version_key(dir_path):
                parts = dir_path.name.split('_')
                if len(parts) >= 3:
                    try:
                        x = int(parts[1])
                        y = int(parts[2])
                        return (x, y)
                    except ValueError:
                        return (-1, -1)
                return (-1, -1)

            version_dirs.sort(key=version_key, reverse=True)
            return version_dirs[0] if version_dirs else None

        latest_dir = await asyncio.to_thread(_find_latest)

        if latest_dir is None:
            print(f"Not found {self.name} . Any save version directory")
            return None

        # Parsing and showing version numbers
        parts = latest_dir.name.split('_')
        if len(parts) >= 3:
            try:
                x, y = int(parts[1]), int(parts[2])
                print(f"Recent Save Directory: {latest_dir.name} (Version: X={x}, Y={y})")
            except ValueError:
                print(f"Recent Save Directory: {latest_dir.name}")
        else:
            print(f"Recent Save Directory: {latest_dir.name}")

        return latest_dir


    async def improve_from_exercise(self, analyze_correct, analyze_wrong):
        """
        Generate a learning-improvement plan from exercise analysis.
        INPUT:
            self: Student Category
            analyze_correct: analysis of correct answers
            analyze_wrong: analysis of incorrect answers
        OUTPUT:
            None
        """
        result = await run_ds_prompt_improve_from_exercise(self, analyze_correct, analyze_wrong)
        # Read json Format Answers
        data = json.loads(result)

        # Read Parts
        elimination = data.get("Elimination", [])
        evolution = data.get("Evolution", {})
        emergence = data.get("Emergence", [])

        # Example Output
        print("Exhausted misperceptions:", elimination)
        print("Evolutional misconceptions:", evolution)
        print("Added Error Awareness:", emergence)

        # Update students' common misconceptions
        for common_mistake in elimination:
            self.scratch.remove_common_mistake(common_mistake)

        for original_mistake, new_mistake in evolution.items():
            self.scratch.update_common_mistake(original_mistake, new_mistake)

        for common_mistake in emergence:
            self.scratch.add_common_mistake(common_mistake)

    async def save_student_state(self, course_date=None, course_number=None):
        """
        Save all current student status to new saving The corresponding document below

        New File Structure: student/saving/{StudentName}/{Date}_{CourseNumber}/{StudentName}_{X}_{Y}
        For example:: student/saving/StudentA/20251101_1/StudentA_0_0

        INPUT:
            course_date: str, Course date, format is YYYYMMDD，Default as Current Date
            course_number: int, Course number, default to self.current_course_number
        """
        # If no date is provided, use current time date
        if course_date is None:
            course_date = self.scratch.current_time.strftime("%Y%m%d")

        # If no course number is provided, use the example variable
        if course_number is None:
            course_number = self.current_course_number

        # Build course catalogue path
        course_dir_name = f"{course_date}_{course_number}"
        saving_base_dir = f"student/saving/{self.name}"
        course_dir_path = Path(saving_base_dir) / course_dir_name

        # Ensure that the curriculum catalogue exists
        await asyncio.to_thread(os.makedirs, course_dir_path, exist_ok=True)

        # Read the last save directory of the current course
        latest_dir = await self.read_latest_saving_dir(course_date, course_number)

        # Determine new version number
        if latest_dir is None:
            # If this is the first time the course has been saved, 0_0 Start
            new_x, new_y = 0, 0
            print(f"First Save Course {course_dir_name} Status")
        else:
            # Otherwise add a version number
            latest_name = latest_dir.name  # Format: {StudentName}_{X}_{Y}
            parts = latest_name.split("_")
            if len(parts) < 3:
                print(f"Error saving directory name format: {latest_name}，From 0_0 Start")
                new_x, new_y = 0, 0
            else:
                try:
                    x = int(parts[1])
                    new_x = x + 1
                    new_y = 0
                except ValueError:
                    print(f"Could not parse version number in save directory: {parts[1]}，From 0_0 Start")
                    new_x, new_y = 0, 0

        # Build new directory names and paths
        new_dir_name = f"{self.name}_{new_x}_{new_y}"
        new_dir_path = course_dir_path / new_dir_name

        # Create New Directory
        await asyncio.to_thread(os.makedirs, new_dir_path, exist_ok=True)
        print(f"Save new status to directory: {new_dir_path}")

        # Save memory and scratch Status
        await asyncio.to_thread(self.mem.save, str(new_dir_path))
        scratch_file = f"{new_dir_path}/scratch.json"
        await asyncio.to_thread(self.scratch.save, scratch_file)

    def set_for_new_class(self):
        """
        Get into a new course and reset the relevant status
        """
        self.current_course_number += 1
        self.current_turn = 0
