import json
import sys

sys.path.append("../../")

from student.global_methods import *
from datetime import datetime
from pathlib import Path

class Scratch:
    def __init__(self, file):
        self.attention_level = 0.8
        self.stress = 0
        # Group allocated to this student
        self.group = None
        self.isLeader = False  # Is it the team leader?
        self.current_time = None
        # Number of recent memories retained for processing.
        self.retention = 10

        self.name = None
        self.age = None
        self.gender = None
        self.grade = None  # Grade of student``
        # based on big five personality
        self.personality = None
        # Cognitive status: based on
        # 1. Item Response Theory (IRT) estimates proficiency using item difficulty,
        #    discrimination, and guessing parameters.
        # 2. Self-assessment captures the student's perceived performance and knowledge.
        # 3. An LLM estimates the student's state from interactions.
        # 4. Learning gains are estimated from knowledge gaps across assessments.
        # These signals help improve learning while separating strategy from ability.
        self.cognitive_state = None
        # Emotional state: based on
        # 1. Comparison IRT The degree of proficiency determined by the model and self-reported proficiency of students, identifying the gap between perceptions and actual skill levels
        # 2. An LLM summarizes dialogue and interaction to estimate engagement,
        #    motivation, and other affective indicators.
        self.affective_state = None
        # Learning style
        # 1. based on Felder and Silverman learning style model
        # Perception (sensory vs intuitive), Processing (active vs reflective), and Understanding (sequential vs global)
        # 2. An LLM analyzes interactions and responses during tutoring to infer
        #    learning styles and adapt learning strategies.
        # These styles can guide personalized hints.
        self.learning_style = None

        self.common_mistakes = []  # Students' common mistakes

        # Reflection module
        self.recency_w = 1
        self.relevance_w = 1
        self.importance_w = 1
        self.recency_decay = 0.99
        self.importance_trigger_max = 50
        self.importance_trigger_curr = 0

        # Plan module
        self.plan_req = []
        self.chat_req = []
        self.chat_with = []
        self.chat_buffer = [] #The list of nodes for the dialogue type memory, which is stored in order from morning to night
        self.action = ""

        if check_if_file_exists(file):
            #scratch_load = json.load(open(file))
            with open(file, "r", encoding='utf-8') as f:
                scratch_load = json.load(f)

            self.attention_level = scratch_load["attention_level"]
            self.stress = scratch_load["stress"]
            self.group = scratch_load["group"]
            self.isLeader = scratch_load["isLeader"]

            if scratch_load["current_time"]:
                # self.current_time = datetime.datetime.strptime(scratch_load["current_time"], "%Y-%m-%d %H:%M:%S")
                self.current_time = datetime.strptime(scratch_load["current_time"], "%Y-%m-%d %H:%M:%S")
            else:
                self.current_time = None

            self.retention = scratch_load["retention"]

            self.name = scratch_load["name"]
            self.age = scratch_load["age"]
            self.gender = scratch_load["gender"]
            self.grade = scratch_load["grade"]
            self.personality = scratch_load["personality"]
            self.MBTI = scratch_load["MBTI"]
            self.cognitive_state = scratch_load["cognitive_state"]
            self.affective_state = scratch_load["affective_state"]
            self.learning_style = scratch_load["learning_style"]
            self.common_mistakes = scratch_load.get("common_mistakes", [])
            self.recency_w = scratch_load["recency_w"]
            self.relevance_w = scratch_load["relevance_w"]
            self.importance_w = scratch_load["importance_w"]
            self.recency_decay = scratch_load["recency_decay"]
            self.importance_trigger_max = scratch_load["importance_trigger_max"]
            self.importance_trigger_curr = scratch_load["importance_trigger_curr"]
            self.plan_req = scratch_load["plan_req"]
            self.chat_req = scratch_load["chat_req"]
            self.chat_with = scratch_load["chat_with"]
            # chat_buffer Converted to string while saving and re-initiated to list when loading
            chat_buffer_loaded = scratch_load["chat_buffer"]
            if isinstance(chat_buffer_loaded, str):
                self.chat_buffer = []  # Restart to Empty List
            else:
                self.chat_buffer = chat_buffer_loaded
            self.action = scratch_load["action"]

    def save(self, out_json):
        scratch = dict()
        scratch["attention_level"] = self.attention_level
        scratch["stress"] = self.stress
        scratch["group"] = self.group
        scratch["isLeader"] = self.isLeader
        scratch["current_time"] = self.current_time.strftime("%Y-%m-%d %H:%M:%S") if self.current_time else None
        scratch["retention"] = self.retention
        scratch["name"] = self.name
        scratch["age"] = self.age
        scratch["gender"] = self.gender
        scratch["grade"] = self.grade
        scratch["personality"] = self.personality
        scratch["MBTI"] = self.MBTI
        scratch["cognitive_state"] = self.cognitive_state
        scratch["affective_state"] = self.affective_state
        scratch["learning_style"] = self.learning_style
        scratch["common_mistakes"] = self.common_mistakes
        scratch["recency_w"] = self.recency_w
        scratch["relevance_w"] = self.relevance_w
        scratch["importance_w"] = self.importance_w
        scratch["recency_decay"] = self.recency_decay
        scratch["importance_trigger_max"] = self.importance_trigger_max
        scratch["importance_trigger_curr"] = self.importance_trigger_curr
        scratch["plan_req"] = self.plan_req
        scratch["chat_req"] = self.chat_req
        scratch["chat_with"] = self.chat_with
        # scratch["chat_buffer"] = self.chat_buffer
        # Will chat_buffer Format into String List
        scratch["chat_buffer"] = format_chat_buffer(self.chat_buffer)
        scratch["action"] = self.action


        # Ensure that the output directory exists
        out_dir = os.path.dirname(out_json)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)

        # Write Data JSON Documentation
        with open(out_json, "w", encoding='utf-8') as f:
            json.dump(scratch, f, indent=4, ensure_ascii=False)


    def accumulate_importance(self, importance):
        self.importance_trigger_curr += importance

    def obstacle_student(self):
        """
        Output student properties
        """
        print(f"Student name: {self.name}")
        print(f"Character: {self.personality}")
        print(f"Cognitive Status: {self.cognitive_state}")
        print(f"Emotional state: {self.affective_state}")
        print(f"Learning style: {self.learning_style}")
        print(f"Attention level: {self.attention_level}")
        print(f"Pressure level: {self.stress}")

    def remove_common_mistake(self, mistake):
        """
        Remove an error perception from the common error list
        """
        if mistake in self.common_mistakes:
            self.common_mistakes.remove(mistake)
            print(f"Removed from common error: {mistake}")
        else:
            print(f"Misperception '{mistake}' Not in Common Errors List")

    def add_common_mistake(self, mistake):
        """
        Add an error perception to the common error list
        """
        if mistake not in self.common_mistakes:
            self.common_mistakes.append(mistake)
            print(f"Added to common error: {mistake}")
        else:
            print(f"Misperception '{mistake}' Already in Common Error List")

    def update_common_mistake(self, old_mistake, new_mistake):
        """
        Updates an error perception in a common error list
        """
        if old_mistake in self.common_mistakes:
            index = self.common_mistakes.index(old_mistake)
            self.common_mistakes[index] = new_mistake
            print(f"Updated common error '{old_mistake}' Yes '{new_mistake}'")
        else:
            print(f"Misperception '{old_mistake}' Not in Common Errors List")
