import os
import json
from datetime import datetime
from datetime import timedelta
import sys
import re

sys.path.append(os.path.dirname(os.path.abspath(__file__)))#For import teacher The package
from vector_db import VectorDB
from Textbook.textbook_pretreat import textbook_pretreat
from personality.personalize import personalize

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))#For import root The package
from util.BroadcastSys import BroadcastSys
from util.BroadcastMessage import BroadcastMessage, MessageType
from util.Recorder import Recorder
from util.model import call_LLM_sync
from student.cognitive_module.student import Student
from student.cognitive_module.scratch import Scratch


script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Teacher:
    def __init__(self, broadcast_sys:BroadcastSys = None, init_file:str = os.path.join(root_dir, "config", "teacher.json"), student_list:list = None):
        """
        Initialization of teachers
        """
        # Read teacher information
        data = {}
        with open(init_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Basic parameters for teachers
        self.name = data["name"]
        self.age = data["age"]
        self.subject = data["subject"]
        self.ep_level = data["experience_level"]  # Level of teaching experience, by basic, intermediate, advanced, expert(Record the hours and range of teaching materials for each level of experience training)
        self.pck_level = data["pck_level"]#Level of knowledge of the content of education, by basic, intermediate, advanced, expert(Like what? basic Training can be carried out using the most basic primary-to-secondary materials，expert Training using university teaching materials and competition materials)
        self.overall_target = data["overall_target"]
        self.teaching_strategy_template = data["teaching_strategy_template"]  # Teaching strategy templates, divided into“high_level”（High) and“low_level”（Low) Default is high
        self.teaching_strategy = data["teaching_strategy"]
        self.teacher_identity = data["teacher_identity"]  # Teacher status

        #File Address Parameters
        self.ep_init_file= os.path.join(script_dir, "Experience/experience_init.txt")
        self.ep_buffer_file= os.path.join(script_dir, "Experience/experience_buffer.txt")
        self.ep_vector_db_file= os.path.join(script_dir, "Experience/ep_vector_db")
        self.pck_vector_db_file= os.path.join(script_dir, "PCK/pck_vector_db")
        self.textbook_file_dirname = os.path.join(script_dir, "Textbook/")
        self.sections_file = os.path.join(script_dir, "Textbook/sections.json")
        self.subsections_file = os.path.join(script_dir, "subsections.json")
        self.status_file_dirname = os.path.join(script_dir, "Status/")

        # Advanced teacher parameters
        #personality
        traits = {}
        personalize_or_not = data["personalize_or_not"]
        personality_theory = data.get("personality_theory", "")
        if personalize_or_not == "no":
            traits_file = os.path.join(script_dir, "personality/default_traits.json")
            with open(traits_file, "r", encoding='utf-8') as f:
                traits = json.load(f)
        else:
            traits_file = os.path.join(script_dir, "personality/traits.json")
            if personalize_or_not == "yes":
                personalize(personality_theory)
            with open(traits_file, "r", encoding='utf-8') as f:
                traits = json.load(f)
            print(f"Personality profile: {traits}")  # Show the profile to the user
            print("""Please confirm the weight of the characteristics in the form：\nP_N_weight Scope is-1 Present 1，P_N_weight To influence an individual's motivation and negativeness, and if the characteristic is positive, P_N_weight Positive, negative, positive or negative, absolute value higher (absolute) 0~0.3 Means less impact，0.3~0.7 Means medium impact，0.7~1 It means that the impact is greater）。\nV_S_weight Scope is-1 Present 1，V_S_weight It affects an individual's vitality and rigidity, and if it makes an individual's way of speaking a living thing, then V_S_weight The more positive, the less negative, the higher the tendency to be vivid or rigid, the higher the absolute value (absolute value) 0~0.3 Means less impact，0.3~0.7 Means medium impact，0.7~1 It means that the impact is greater）。：""")
            for trait, data in traits.items():
                print(f"Enter an index for {trait} (0-10):")
                index = int(input())
                data["index"] = index
        PN_index = 0
        VS_index = 0
        for trait,data in traits.items():
            PN_index += data["index"] * data["P_N_weight"]
            VS_index += data["index"] * data["V_S_weight"]
        self.PN_index = PN_index
        if VS_index > 8:
            speaking_style = "As vivid as possible"
        elif VS_index > 6:
            speaking_style = "Vivid"
        elif VS_index > 4:
            speaking_style = "Not very vivid"
        elif VS_index > 2:
            speaking_style = "Dead end"
        else:
            speaking_style = "As rigid as possible"
        self.speaking_style = speaking_style
        #experience
        leveled_ep_vector_db_file = os.path.join(self.ep_vector_db_file, f"{self.ep_level}")
        if os.path.exists(leveled_ep_vector_db_file):
            self.ep_vector_db = VectorDB()
            self.ep_vector_db.load(path=leveled_ep_vector_db_file)
            self.ep_vector_db.delete_documents()  # The initialization document is a user-enabled teaching strategy, which ensures that the last input does not affect the teaching process, while preserving the experience developed in the course of teaching
        else:
            self.ep_vector_db = VectorDB()
        with open(self.ep_init_file, 'r', encoding='utf-8') as f:
            init_text = f.read()
        self.ep_vector_db.create_from_text(text = init_text, init = True)
        #pck
        pck_subject_file = os.path.join(self.pck_vector_db_file, f"{self.subject}")
        leveled_pck_vector_db_file = os.path.join(pck_subject_file, f"{self.pck_level}")
        if os.path.exists(leveled_pck_vector_db_file):
            self.pck_vector_db = VectorDB()
            self.pck_vector_db.load(path=leveled_pck_vector_db_file)
        else:
            self.pck_vector_db = VectorDB()

        #Update class properties to update simultaneously finish_class Methodology update_status Methodology
        #Course parameters
        self.class_number = 1 # What are you talking about?
        self.target = ""  #Current course objectives
        self.student = student_list if student_list is not None else []  #Student List
        #Teaching materials（start_class）
        self.current_section_turn = 2  #Which section of the curriculum is currently used as an index-1（It was 1，But the first section is empty 2）
        self.sections_this_class = 0  #Number of sections to be covered in this class
        self.text_this_class = ""
        self.subsections = []  #Separated course content
        self.current_subsection_turn = 1 #Which section of the curriculum is currently being discussed?,Use as Index-1
        self.importance = []  #All subsection is recorded as 0 Present 10，0 Does not matter，10 It's very important
        self.focus = []  #All subsection , “thinking” or “pracing””
        #Lectures（next_subsection and teach and activate）
        self.detail_level = 0  # The degree of detail, the range 0 Present 10，0 That means no，10 Organisation 10 Round
        self.plan = []  #Teaching programme
        self.plan_methods = []  #The manner in which each section is taught
        self.current_plan_turn = 1  #Which paragraph of the current teaching is used as an index-1
        self.subsection_selected = 0  #Sections currently selected when deciding on activities
        self.activity_type = ""
        self.duration = 5  #Duration of one event
        self.duration_turn = 1  #What time is the current activity going on?,Use as Index-1
        self.times = 0  #Number of activities to prevent continuity of activities
        self.activity_content = ""  # Can not open message
        #Status
        self.saw = ""
        self.answered = ""
        self.discussed = ""
        self.practiced = ""
        self.to_solve = ""
        self.feedback = ""
        self.taught = "" #Previous lectures
        self.experience = ""
        self.type = ""  #Current type of teaching activity
        self.period = "not_started" # Current stage of instruction, divided into“not_started”（Not started）、“decide_ended”(End of one decision-making)、“subsection_activity”、“subsection_lecture”、“already_ended”（End of course）
        self.class_turns = 40  #Every class 40 Wheel
        self.current_turn = 0
        self.content = "I haven't started school yet" #Current teaching content

        # Broadcasting mechanisms
        if broadcast_sys is None:
            raise ValueError("Broadcast system is not provided")
        self.broadcast_sys = broadcast_sys;
        self.broadcast_sys.subscribe(self, "teacher")  # Subscriptions to broadcasts
        self.received = []
        self.time = datetime.strptime("2025-09-01 08:00:00", "%Y-%m-%d %H:%M:%S")


    #System Call
    @classmethod
    async def initialize_teacher_async(cls, broadcast_sys: BroadcastSys = None, init_file: str = os.path.join(root_dir, "config", "teacher.json"), student_list: list = None):
        """
        Step factory method for creating a walk environment Teacher Example
        """
        # Read teacher information
        with open(init_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # (if required)）
        textbook_file = data["textbook_file"]
        if textbook_file != "use last":
            await textbook_pretreat(textbook_file)

        # Create examples and initialize them (jumping teaching materials)）
        instance = cls.__new__(cls)
        instance.__init__(broadcast_sys, init_file, student_list)

        return instance
    def _strip_think_blocks(self, text: str) -> str:
        """
        Remove reasoning Model returning <think>...</think> Content to avoid interference with subsequent analysis or presentation。
        """
        try:
            return re.sub(r"(?is)<think>.*?</think>", "", text)
        except Exception:
            return text



    def _generate_plan_with_constraints(self, segments: int, prefer_method: str = "", extra_instruction: str = ""):
        """
        Generate a concise, structured teaching plan for the remaining lesson.
        """
        high_level_teaching_strategy_template = """
        * Explain the material in clear, student-friendly language, drawing together its main ideas.
        * Ask higher-order questions that invite analysis, reasoning, and synthesis. Ask why and how, not only what.
        * Take students' ideas seriously and invite them to explain their reasoning.
        * Welcome different perspectives and ask students to compare them.
        * Use students' answers to open up related questions and connect ideas.
        * Give specific, constructive feedback that explains what is valuable in an answer.
        * Help students notice and build on their classmates' observations.
        * Encourage students when they ask their own questions.
        """
        low_level_teaching_strategy_template = """
        * Follow the textbook closely and explain its content directly.
        * Ask short factual questions about the material.
        * Keep responses brief and focused on whether an answer is correct.
        * Give priority to explaining the material over extended discussion.
        * Use individual work, with limited group discussion or student presentations.
        """
        strategy = ""
        if self.teaching_strategy_template == "high_level":
            strategy = high_level_teaching_strategy_template
        elif self.teaching_strategy_template == "low_level":
            strategy = low_level_teaching_strategy_template
        strategy += self.teaching_strategy

        docs = self.pck_vector_db.search(self.subsections[self.current_subsection_turn-1]) if self.subsections else []
        pck_knowledge = ""
        for doc in docs:
            pck_knowledge += f"{doc.page_content.strip()}\n"

        constraint_text = ""
        if prefer_method:
            constraint_text += f"\nPrioritize this teaching method: {prefer_method}."
        if extra_instruction:
            constraint_text += f"\nAdditional constraint: {extra_instruction}"

        prompt = f"""
        You are an education expert. Create a teaching plan for the upcoming material using the teacher's experience, teaching strategy, and relevant subject knowledge.
        Teaching experience: {self.experience}
        Relevant subject knowledge: {pck_knowledge}
        Teaching strategy: {strategy}
        Upcoming material: {self.subsections[self.current_subsection_turn-1] if self.subsections else self.text_this_class}

        Requirements:
        * Generate exactly {segments} remaining plan steps.
        * For each step, choose exactly one method from: "Presentation of knowledge points", "Ask your classmates", or "Evaluation of responses received".
        * Ensure that each question is followed by a response step, which may appear later in the plan.
        * Do not combine methods within a step.
        * Return strict JSON with a "plan" array. Each item must contain "content" and "method" fields.
        * Write all generated content in clear, natural English. Keep the required field names and method values exactly as specified.
        {constraint_text}
        """
        response = call_LLM_sync(
            "teacher",
            messages=[
                {"role": "system", "content": self.teacher_identity},
                {"role": "user", "content": prompt},
            ],
            response_format={'type': 'json_object'}
        )
        result = json.loads(response)
        return result.get("plan", [])

    def regenerate_remaining_plan(self, segments: int = None, prefer_method: str = "", instruction: str = "") -> str:
        """
        Reproduction of “unimplemented” teaching plans only, without modification of the prefix of implemented plans。
        Here current_plan_turn Division: reserved [0, current_plan_turn-2]，From current_plan_turn Start recosting。
        """
        # Situation A：At the sub-boundary (the next subsection is about to begin), there is no plan to implement
        if self.period == "decide_ended" and (not self.plan or self.current_plan_turn > len(self.plan)):
            # Enter the normal decision-making process and automatically generate a complete plan for the next subsection
            self.decide()
            return "New teaching plans have been generated for the current section"

        # Situation B：At the lecture stage, there are executed prefixes and unexecuted suffixes
        if segments is None:
            segments = max(1, max(1, self.detail_level) - (self.current_plan_turn - 1))

        new_plan_items = self._generate_plan_with_constraints(segments, prefer_method=prefer_method, extra_instruction=instruction)

        prefix_contents = self.plan[:max(0, self.current_plan_turn-1)]
        prefix_methods = self.plan_methods[:max(0, self.current_plan_turn-1)]

        self.plan = prefix_contents + [item.get("content", "").strip() for item in new_plan_items]
        self.plan_methods = prefix_methods + [item.get("method", "").strip() for item in new_plan_items]

        # Back to the lecture stage. Continue current_plan_turn Implementation
        self.period = "subsection_lecture"
        self.activity_type = ""
        self.times = 0
        return "Regenerated remaining teaching plans"

    def get_info(self):
        """
        Basic information on returning teachers
        """
        return f"Teacher Name: {self.name}, Age: {self.age}, Subject: {self.subject}"

    def jump(self, status_file):
        """
        Go to the specified state
        """
        #Check if the file exists
        if not os.path.exists(status_file):
            raise FileNotFoundError(f"Status file not found: {status_file}")

        #Read JSON Documentation
        with open(status_file, 'r', encoding='utf-8') as f:
            status_data = json.load(f)

        #Authentication JSON Data Format
        if not isinstance(status_data, dict):
            raise ValueError(f"Invalid status file format: {status_file}")

        #Through JSON . All key values in, given to the corresponding attribute
        for key, value in status_data.items():
            if hasattr(self, key):
                # Special Field Conversion
                if key == "time" and isinstance(value, str):
                    try:
                        setattr(self, "time", datetime.strptime(value, "%Y-%m-%d %H:%M:%S"))
                    except Exception:
                        pass
                    continue
                setattr(self, key, value)

        print(f"Restored state from {status_file}")
        return True

    # …………

    #Function Functions
    async def receive_broadcast(self, content: dict):
        self.received.append(content)

    def receive_broadcast_sync(self, content: dict):
        self.received.append(content)

    async def handle_observer_intervention(self, intervention_data: dict):
        """
        Treatment of observer interventions and adjustment of teaching plans (preserved interfaces)）

        Args:
            intervention_data: Observer intervention data, including adjusted instructions and parameters

        Returns:
            str: Process Result Description

        Example: intervention_data Format:
        {
            "type": "adjust_plan",  // Adjustment Type：adjust_plan, change_strategy, skip_section Wait
            "instruction": "The student's attention is down, suggesting more interaction",
            "parameters": {
                "add_discussion": true,
                "topic": "Actual application of the opposite number"
            }
        }

        TODO:
        - Parsing intervention_data Command in
        - Call different treatments according to command type
        - Adjustment self.plan、self.teaching_strategy Equal Properties
        - Use LLM Understanding Natural Language Command
        - Return adjusted plan description
        """
        print("\n[Teacher.handle_observer_intervention] Observer intervention received")
        print(f"  Type: {intervention_data.get('type', 'Not specified')}")
        print(f"  Instruction: {intervention_data.get('instruction', 'none')}")

        intervention_type = (intervention_data.get("type") or "").strip()
        params = intervention_data.get("parameters", {}) or {}
        instruction = (intervention_data.get("instruction") or "").strip()

        # Use class level method

        # 1) Adjustment of teaching plans
        if intervention_type == "adjust_plan":
            prefer_method = params.get("prefer_method", "")
            segments = params.get("segments")
            if segments is None:
                remaining = max(1, max(1, self.detail_level) - (self.current_plan_turn - 1))
                segments = remaining
            new_plan_items = self._generate_plan_with_constraints(segments, prefer_method=prefer_method, extra_instruction=instruction)
            # Collapse: Retain completed paragraphs and replace the remainder
            prefix_contents = self.plan[:max(0, self.current_plan_turn-1)]
            prefix_methods = self.plan_methods[:max(0, self.current_plan_turn-1)]
            self.plan = prefix_contents + [item.get("content", "").strip() for item in new_plan_items]
            self.plan_methods = prefix_methods + [item.get("method", "").strip() for item in new_plan_items]
            self.period = "subsection_lecture"
            self.activity_type = ""
            self.times = 0
            return "The current curriculum has been reshaped by intervention"

        # 2) Change teaching strategy
        if intervention_type == "change_strategy":
            new_template = (params.get("template") or "").strip()  # high_level / low_level
            new_strategy = params.get("append_strategy", "")
            if new_template in ("high_level", "low_level"):
                self.teaching_strategy_template = new_template
            if new_strategy:
                self.teaching_strategy = new_strategy
            remaining = max(1, max(1, self.detail_level) - (self.current_plan_turn - 1))
            new_plan_items = self._generate_plan_with_constraints(remaining, extra_instruction=instruction)
            prefix_contents = self.plan[:max(0, self.current_plan_turn-1)]
            prefix_methods = self.plan_methods[:max(0, self.current_plan_turn-1)]
            self.plan = prefix_contents + [item.get("content", "").strip() for item in new_plan_items]
            self.plan_methods = prefix_methods + [item.get("method", "").strip() for item in new_plan_items]
            self.period = "subsection_lecture"
            return "Follow-up education plan updated in line with the new strategy"

        # 3) Skip the section/Go to the specified section
        if intervention_type == "skip_section":
            to_index = params.get("to_subsection_index")  # 1-based
            if to_index is None:
                # Defaultly skips the current subsection into the next subsection
                self.current_subsection_turn += 1
            else:
                try:
                    to_index = int(to_index)
                    if to_index >= 1:
                        self.current_subsection_turn = to_index
                except Exception:
                    pass
            self.plan = []
            self.plan_methods = []
            self.current_plan_turn = 1
            self.period = "decide_ended"
            self.activity_type = ""
            return "Jumped to specified section and emptied the current plan pending re-decision"

        # 4) Injection activities (e.g., panel discussions)）
        if intervention_type == "inject_activity":
            self.activity_type = "group_discussion"
            duration = params.get("duration")
            try:
                if duration is not None:
                    self.duration = max(1, int(duration))
            except Exception:
                pass
            # Default selection of the current subsection for active activity
            self.subsection_selected = max(0, self.current_subsection_turn - 1)
            self.duration_turn = 1
            self.period = "subsection_activity"
            return "Switched to panel discussion"

        # 5) Adjust the level of detail and reshape the remaining plan
        if intervention_type == "set_detail_level":
            try:
                new_level = int(params.get("detail_level"))
                self.detail_level = max(1, new_level)
            except Exception:
                pass
            remaining = max(1, self.detail_level - (self.current_plan_turn - 1))
            new_plan_items = self._generate_plan_with_constraints(remaining, extra_instruction=instruction)
            prefix_contents = self.plan[:max(0, self.current_plan_turn-1)]
            prefix_methods = self.plan_methods[:max(0, self.current_plan_turn-1)]
            self.plan = prefix_contents + [item.get("content", "").strip() for item in new_plan_items]
            self.plan_methods = prefix_methods + [item.get("method", "").strip() for item in new_plan_items]
            self.period = "subsection_lecture"
            return "Level of detail adjusted and follow-up plan updated"

        # 6) Set active time
        if intervention_type == "set_duration":
            try:
                new_duration = int(params.get("duration"))
                self.duration = max(1, new_duration)
            except Exception:
                pass
            return "Set active time"

        return "Type of intervention not identified or not subject to adjustment"

    def perceive(self):
        '''
        '''
        self.saw = ""
        self.answered = ""
        self.discussed = ""
        self.feedback = ""
        self.to_solve = ""
        for content in self.received:
            if content["active_event"] == "active":
                self.to_solve += f"{content['speaker']} made a request: {content['content']};"
            elif content["active_event"] == "answer":
                self.answered += f"{content['speaker']} answered the question: {content['content']};"
            elif content["active_event"] == "group_discussion":
                self.discussed += f"{content['speaker']} summarized the group discussion: {content['content']};"
            elif content["active_event"] == "practice":
                self.practiced += f"{content['speaker']} is working on an exercise: {content['content']};"
            elif content["active_event"] == "feedback":
                self.feedback += f"{content['speaker']} gave feedback: {content['content']};"
            else:
                self.saw += f"{content['speaker']} is taking part in {content['active_event']}: {content['content']};"

            if content["active_event"] == "new_day":
                self.time = (self.time + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)

        self.received = []  # clear received after processing

    def retrive(self, content: str):
        """Retrieving relevant experiences from teaching experience"""
        self.experience = ""  # Experience before clearance
        docs = self.ep_vector_db.search(content)
        for doc in docs:
            self.experience += f"{doc.page_content.strip()}\n"

    def update_target(self):
        """Access to teaching objectives for this class"""
        prompt = f"""
        Write one concise learning objective for this class based on the overall goal and the lesson material.
        Include objectives for students' knowledge, skills, and values. If the overall goal is empty, use the lesson material alone.
        Return only the objective as one coherent paragraph, in clear English. Do not include explanations or other text.
        Overall teaching goal: {self.overall_target}
        Lesson material: {self.text_this_class}
        """
        response = call_LLM_sync(
            "teacher",
            messages=[
                {"role": "system", "content": self.teacher_identity},
                {"role": "user", "content": prompt},
            ]
        )
        self.target = self._strip_think_blocks(response).strip()

    def update_experience(self):
        '''
        Rethinking and updating teaching experience
        '''
        self.perceive() #Access feedback，Observations independent of the update state, as the process of updating the experience does not allow access and reset the initial status
        #Reflection
        prompt = f"""
        You are an expert in reflective teaching. Review the teaching record, lesson material, and student feedback to identify useful teaching experience.
        Teaching record: {self.taught}
        Lesson material: {self.text_this_class}
        Student feedback: {self.feedback}
        Work through these steps:
        1. Review the material and teaching record and summarize the actions taken.
        2. Use student feedback to identify important issues.
        3. Consider alternative actions that could address those issues.
        4. Summarize the resulting teaching experience.
        Return only the teaching experience in clear English.
        """
        response = call_LLM_sync(
            "teacher",
            messages=[
                {"role": "system", "content": self.teacher_identity},
                {"role": "user", "content": prompt},
            ]
        )
        experience = response.strip()
        #Update experience
        self.ep_vector_db.create_from_text(text=experience)
        self.period = "not_started"  # Update experience and return to non-start status
        #Reset taught and text_this_class and current_turn
        self.taught = ""
        self.text_this_class = ""
        self.current_turn = 0
        self.type = ""  #Reset type
        self.content = "I haven't started school yet"  #Reset content
        #Save vector database
        self.ep_vector_db.save(path=os.path.join(self.ep_vector_db_file, f"{self.ep_level}"))
        self.pck_vector_db.save(path=os.path.join(self.pck_vector_db_file, f"{self.subject}", f"{self.pck_level}"))
        print("Teaching experience updated and preserved。")  #Hint

    def update_status(self):
        """
        Update teacher status, save current status to file
        """
        #Update Status
        self.perceive() #Update Perception Information
        teacher_actions = ""
        for plan in self.plan:
            teacher_actions += plan
        t = self.saw + self.answered + self.discussed + self.practiced + self.to_solve + self.feedback + teacher_actions + '\n' + teacher_actions
        self.retrive(t) #Update experience
        status = {
            "class_number": self.class_number,
            "target": self.target,
            "current_section_turn": self.current_section_turn,
            "sections_this_class": self.sections_this_class,
            "text_this_class": self.text_this_class,
            "subsections": self.subsections,
            "current_subsection_turn": self.current_subsection_turn,
            "importance": self.importance,
            "focus": self.focus,
            "detail_level": self.detail_level,
            "plan": self.plan,
            "plan_methods": self.plan_methods,
            "current_plan_turn": self.current_plan_turn,
            "subsection_selected": self.subsection_selected,
            "activity_type": self.activity_type,
            "duration": self.duration,
            "duration_turn": self.duration_turn,
            "times": self.times,
            "activity_content": self.activity_content,
            "saw": self.saw,
            "answered": self.answered,
            "discussed": self.discussed,
            "to_solve": self.to_solve,
            "feedback": self.feedback,
            "taught": self.taught,
            "experience": self.experience,
            "type": self.type,
            "period": self.period,
            "class_turns": self.class_turns,
            "current_turn": self.current_turn,
            "content": self.content,
            "time": datetime.strftime(self.time, "%Y-%m-%d %H:%M:%S"),
            "PN_index": self.PN_index,
            "speaking_style": self.speaking_style
        }
        with open(self.status_file_dirname + f"status_{self.class_number}_{self.current_turn}.json", 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=4)


    #Teaching activities
    def start_class(self):
        '''At the beginning of the class, determine the content of the teaching materials, their objectives and divide them'''
        sections = []
        with open(self.sections_file, 'r', encoding='utf-8') as f:
            sections = json.load(f)["sections"]
        # To determine the content of the teaching of the current class (if the number of sections to be given depending on the content is to be determined, one by the token Match sections Merge Operations）
        self.text_this_class = sections[self.current_section_turn - 1]
        # Teaching objectives
        self.update_target()
        # Partition of teaching materials
        text = f"""
        Lesson material: {self.text_this_class}
        """
        prompt = """
        Divide the lesson material into subsections and assess each subsection's importance and learning focus.

        Subsection requirements:
        * Divide the material into 5 to 8 coherent subsections. Each subsection should center on one theme.
        * Preserve all lesson content; do not omit or skip material.
        * Rate each subsection's importance with an integer score from 0 to 10.
        * Choose a focus of either "reflection" (understanding and reasoning) or "practice" (application and consolidation).

        Consider these factors when assigning importance:
        1. Core concepts and theories, and how essential they are to understanding the subject.
        2. Practical applications and the problem-solving skills developed.
        3. Cognitive difficulty and prerequisite concepts.
        4. Relevance to common assessment and examinations.

        Return strict JSON in this form:
        {
          "subsections": [
            {"content": "...", "score": 7, "focus": "reflection"},
            {"content": "...", "score": 5, "focus": "practice"}
          ]
        }
        Write all subsection content in clear English. Preserve formulas, numbers, and the lesson's original sequence.
        """
        response = call_LLM_sync(
            "teacher",
            messages=[
                {"role": "system", "content": self.teacher_identity},
                {"role": "system", "content": text},
                {"role": "user", "content": prompt},
            ],
            response_format={
                'type': 'json_object'
            }
        )
        t = []
        with open(self.subsections_file, 'w', encoding='utf-8') as subsections_file:
            subsections_file.write(response)
        with open(self.subsections_file, 'r', encoding='utf-8') as subsections_file:
            t = json.load(subsections_file)["subsections"]
        for item in t:
            self.subsections.append(item['content'])
            self.importance.append(item['score'])
            self.focus.append(item['focus'])
        self.type = "start_class"
        # Radio
        msg = BroadcastMessage(
            current_time=self.time,
            message_type=MessageType.COMMAND,
            active_event=self.type,
            speaker=self.name,
            content=f"Class begins. Learning objective: {self.target}"
        )
        self.broadcast_sys.publish_sync("student", msg)
        #Update Status
        self.content = "Let's start class。"
        self.period = "decide_ended"  # Start the first decision


    def decide(self):
        '''
        Adjudication of activities or lectures, and some pre-emptive work
        '''
        #Let's see if we're done
        teaching_progress = (self.current_subsection_turn-1)/len(self.subsections)
        class_progress = self.current_turn/self.class_turns
        if teaching_progress >= 1:# Teaching completed
            if class_progress < 1:
                self.period = "waiting_for_end"
                print("decide: waiting for end")
                return
            if class_progress >= 1:
                self.period = "already_ended"
                print("decide: already ended")
                return
        #Teaching incomplete
        if class_progress < 1:# Course not completed,Consider activities
            #Assessing student attention
            print(f"Student feedback: {self.saw}")
            prompt = f"""
            Assess the overall attention level of the students from their feedback.
            Student feedback: {self.saw}
            Return one integer from 0 to 10 only: 0 means no students are paying attention, and 10 means all students are fully attentive.
            """
            response = call_LLM_sync(
                "teacher",
                messages=[
                    {"role": "system", "content": self.teacher_identity},
                    {"role": "user", "content": prompt},
                ]
            )
            attention = int(self._strip_think_blocks(response).strip())
            print(f"Student attention level: {attention}")
            #Depending on the importance of the content of the course and the level of attention given to the student, it is decided to proceed,Then decide which activity is to be undertaken according to its focus
            #More parameters could be introduced to decide whether or not to proceed, and weights indicated that the teacher' s focus could be on some variable experiments and what activities needed to be carried out
            self.subsection_selected = self.current_subsection_turn - 2 if (self.current_subsection_turn > len(self.subsections) or self.importance[self.current_subsection_turn - 2] > self.importance[self.current_subsection_turn - 1]) else self.current_subsection_turn - 1
            #Watch out on the expression
            importance = int(self.importance[self.subsection_selected])
            importance_weight = 1  #Weight of importance
            attention_weight = 1  #Attention weights
            times_weight = 4  #Do not conduct activities on a continuous basis, unless they are of particular importance and low priority
            d = self.PN_index + importance * importance_weight - attention * attention_weight - times_weight * self.times
            print(f"Decision factors: positivity index={self.PN_index}, subsection importance={importance}, attention={attention}, activity count={self.times}")
            if d > 8:#Greater than threshold have to test
                #For the time being, there's only panel discussions. We can use what's already been designed focus Properties Expand More Activity Types
                self.activity_type = "group_discussion"
                self.period = "subsection_activity"
                self.times += 1  # Number of activities updated
                self.duration_turn = 1  # Reset Activity Wheels
                return
            else:
                self.times = 0  # Number of activities reset
        #Failure to carry out activities（class_progress >= 1 or decided not to proceed return）
        #Level of detail in the decision
        #Importance of integration
        sub_num = len(self.subsections)
        average = 40/sub_num
        total_score = 0
        for ip in self.importance:
            total_score += int(ip)
        now_average = total_score/sub_num
        p = average/now_average
        self.detail_level = int(self.importance[self.current_subsection_turn-1]*p)
        #Integration of teaching progress
        if class_progress >= 1:
            self.detail_level = 1  # If the course is more advanced 1，Indicates the course timeout, the degree of detail is as 1
        if teaching_progress > class_progress:
            self.detail_level += 1
        elif teaching_progress < class_progress:
            self.detail_level -= 1
            if self.detail_level <= 0:
                self.detail_level = 1
        print(f"Plan detail level: {self.detail_level}")
        #Production of lectures according to teacher style (strategy)
        high_level_teaching_strategy_template = """
        * Explain the material in clear, student-friendly language, drawing together its main ideas.
        * Ask higher-order questions that invite analysis, reasoning, and synthesis. Ask why and how, not only what.
        * Take students' ideas seriously and invite them to explain their reasoning.
        * Welcome different perspectives and ask students to compare them.
        * Use students' answers to open up related questions and connect ideas.
        * Give specific, constructive feedback that explains what is valuable in an answer.
        * Help students notice and build on their classmates' observations.
        * Encourage students when they ask their own questions.
        """
        low_level_teaching_strategy_template = """
        * Follow the textbook closely and explain its content directly.
        * Ask short factual questions about the material.
        * Keep responses brief and focused on whether an answer is correct.
        * Give priority to explaining the material over extended discussion.
        * Use individual work, with limited group discussion or student presentations.
        """
        strategy = ""
        if self.teaching_strategy_template == "high_level":
            strategy = high_level_teaching_strategy_template
        elif self.teaching_strategy_template == "low_level":
            strategy = low_level_teaching_strategy_template
        strategy += self.teaching_strategy
        #pck Knowledge
        docs = self.pck_vector_db.search(self.subsections[self.current_subsection_turn-1])
        pck_knowledge = ""
        for doc in docs:
            pck_knowledge += f"{doc.page_content.strip()}\n"
        #Generate a teaching plan
        json_example = """
        {
            "plan": [
                {
                "content": "Introduce positive and negative numbers using the Shenyang temperature example, then ask students for other examples from daily life.",
                "method": "Ask your classmates"
                },
                {
                    "content": "Then we evaluate the responses and encourage them to think",
                    "method": "Evaluation of responses received"
                },
                {
                    "content": "Next explain the definition and symbol of positive and negative numbers",
                    "method": "Presentation of knowledge points"
                },
                {
                    "content": "Emphasizing 0 Ask the students what they think about it",
                    "method": "Ask your classmates"
                },
                {
                    "content": "Evaluate student perceptions and encourage students to think positively",
                    "method": "Evaluation of responses received"
                },
                {
                    "content": "The process of generation and development of the final summary figures",
                    "method": "Presentation of knowledge points"
                }
            ]
        }
        """
        prompt = f"""
        You are an education expert. Create a teaching plan for the upcoming material using the teacher's experience, strategy, and relevant subject knowledge.
        Teaching experience: {self.experience}
        Relevant subject knowledge: {pck_knowledge}
        Teaching strategy: {strategy}
        Upcoming material: {self.subsections[self.current_subsection_turn-1]}

        Requirements:
        * Create exactly {self.detail_level} plan steps.
        * Choose exactly one method for each step: "Presentation of knowledge points", "Ask your classmates", or "Evaluation of responses received".
        * Follow every question with a response step.
        * Do not combine methods within one step. If a response should lead to another question, use separate steps.
        * Return strict JSON with a "plan" array. Each item must contain "content" and "method" fields.
        * Write generated content in clear English and use only the exact method values listed above.

        Example structure:
        {json_example}
        """
        if self.detail_level == 1:#A single-step lesson plan is clearer without an interaction
            json_type ="""
            {
                "plan": [
                    {
                        "content": "Explain positive and negative numbers, including their symbols, the role of zero, and why negative numbers were introduced.",
                        "method":"Presentation of knowledge points"
                    }
                ]
            }
            """
            prompt = f"""
            Create a concise teaching plan for explaining the lesson material, using the teacher's experience, strategy, and relevant subject knowledge.
            Teaching experience: {self.experience}
            Relevant subject knowledge: {pck_knowledge}
            Teaching strategy: {strategy}
            Lesson material: {self.subsections[self.current_subsection_turn-1]}

            Requirements:
            * Return one concise step that covers all key points.
            * Use only the method "Presentation of knowledge points"; do not include questions or other interactive methods.
            * Return strict JSON with a "plan" array whose item contains "content" and "method" fields.
            * Write the plan content in clear English.

            Example structure:
            {json_type}
            """
        response = call_LLM_sync(
            "teacher",
            messages=[
                {"role": "system", "content": self.teacher_identity},
                {"role": "user", "content": prompt},
            ],
            response_format={
                'type': 'json_object'
            }
        )
        dict = json.loads(response)
        t = dict.get("plan", [])
        self.plan = []  # Reset Last Schedule
        self.plan_methods = []  # Reset last planned method
        self.current_plan_turn = 1  # Reset Current Planned Wheels
        print(f"Generated {len(t)} teaching steps")
        for item in t:
            self.plan.append(item["content"].strip())
            self.plan_methods.append(item["method"].strip())
        for i in range(len(self.plan)):
            print(f"Teaching step {i+1}: {self.plan[i]}")
        self.period = "subsection_lecture"  # Let's go

    def teach(self):
        '''
        Generate actual teaching content
        '''
        type = self.plan_methods[self.current_plan_turn-1]
        if type == "Presentation of knowledge points":
            self.type = "lecture"
        elif type == "Ask your classmates":
            self.type = "ask_question"
        elif type == "Evaluation of responses received":
            self.type = "feedback"
        # Generate teaching content
        pre_text = ""
        prompt = f"""
        Write the next piece of lesson content in the teacher's established speaking style, following the current plan and considering prior teaching and student feedback.
        Lesson material: {self.subsections[self.current_subsection_turn-1]}
        Current plan step: {self.plan[self.current_plan_turn-1]}
        Required teaching mode: {self.type}
        Previous lesson content: {pre_text}
        Student answers: {self.answered}
        Teacher's speaking style: {self.speaking_style}

        Requirements:
        * Use only the information above; do not make assumptions.
        * Return one complete, coherent paragraph in clear English and follow the current plan step.
        * Use only one teaching mode. When presenting knowledge, do not ask questions or evaluate answers. When asking a question, ask only a question. When responding to answers, do not present new knowledge or ask a question.
        * Base responses on actual student feedback. If there is none, do not invent it; you may briefly connect to the previous lesson content.
        * Do not start group discussions or assign exercises.
        * Keep the content within the current lesson.
        * Return only the teacher's spoken content.
        """
        response = call_LLM_sync(
            "teacher",
            messages=[
                {"role": "system", "content": self.teacher_identity},
                {"role": "user", "content": prompt},
            ]
        )
        content = self._strip_think_blocks(response).strip()
        print(f"Generated teaching content: {content}")
        # Radio
        msg = BroadcastMessage(
            current_time=self.time,
            message_type=MessageType.CLASS,
            active_event=self.type,
            speaker=self.name,
            content=content
        )
        self.broadcast_sys.publish_sync("student", msg)
        #Update Status
        self.content = content
        self.taught += f"{content}\n"
        self.current_plan_turn += 1
        if self.current_plan_turn > len(self.plan):
            self.current_subsection_turn += 1  # Update the current subsection,Only lecture Update subsection after completion
            self.period = "decide_ended"  # It's over

    def activate(self):
        """
        """
        # Activities carried out
        if self.activity_type == "group_discussion":
            self.group_discussion()
        #Expandable
        #elif self.activity_type == "other":

    def group_discussion(self):
        """
        Panel discussion
        """
        self.type = "group_discussion"  # Sets the current type of activity as a panel discussion
        stu_num = len(self.student)  # Number of students
        stu_group_num = stu_num // 3 if stu_num >= 3 else 1  # Group, at least 1 Group
        #Group
        for i in range(stu_group_num):
            group = self.student[i*3:(i+1)*3] if i < stu_group_num - 1 else self.student[i*3:]
            for student in group:
                student.scratch.group = i+1  # Set the group number of the student
        if self.duration_turn == 1:
            #Theme for generating panel discussions
            prompt_pre = f"""
            Invite students to have a short introductory group discussion about the upcoming lesson material.
            Upcoming material: {self.subsections[self.subsection_selected]}
            Students have not studied this material yet, so keep the discussion broad, thought-provoking, and connected to the topic.
            Say only what the teacher should say to the class, in clear English and in this speaking style: {self.speaking_style}
            """
            prompt_post = f"""
            Invite students to have a short review discussion about the lesson material they have already studied.
            Studied material: {self.subsections[self.subsection_selected]}
            Students have studied this material, so connect the discussion to specific concepts.
            Say only what the teacher should say to the class, in clear English and in this speaking style: {self.speaking_style}
            """
            dis_type = ""
            if self.subsection_selected + 1 == self.current_subsection_turn:
                dis_type = "Preparatory studies"
            else:
                dis_type = "Review"
            prompt = f"{prompt_pre if dis_type == 'Preparatory studies' else prompt_post}"
            response = call_LLM_sync(
                "teacher",
                messages=[
                    {"role": "system", "content": self.teacher_identity},
                    {"role": "user", "content": prompt},
                ]
            )
            #Radio
            self.content = self._strip_think_blocks(response).strip()
            msg = BroadcastMessage(
                current_time=self.time,
                message_type=MessageType.COMMAND,
                active_event="group_discussion_start",
                speaker=self.name,
                content=self.content
            )
            self.broadcast_sys.publish_sync("student", msg)
            #Update Status
            self.taught += f"{self.content}\n"
            self.duration_turn += 1  # Update the panel discussion rounds
        elif self.duration_turn == self.duration:
            #Conclusion of the panel discussion
            self.content = "Conclusion of the panel discussion。"
            msg = BroadcastMessage(
                current_time=self.time,
                message_type=MessageType.COMMAND,
                active_event="group_discussion_end",
                speaker=self.name,
                content=self.content
            )
            self.broadcast_sys.publish_sync("student", msg)
            self.taught += f"{self.content}\n"
            self.duration_turn += 1  # Update the panel discussion rounds
        elif self.duration_turn - 1 == self.duration:
            #Feedback
            self.activity_content = self.discussed
            print(f"Group discussion: {self.activity_content}")
            prompt = f"""
            Give feedback on the group discussion.
            Discussion: {self.activity_content}
            Summarize and evaluate the discussion, noting its strengths and areas for improvement.
            Return only the feedback in clear English, using this speaking style: {self.speaking_style}
            """
            response = call_LLM_sync(
                "teacher",
                messages=[
                    {"role": "system", "content": self.teacher_identity},
                    {"role": "user", "content": prompt},
                ]
            )
            feedback = self._strip_think_blocks(response).strip()
            #Radio feedback
            msg = BroadcastMessage(
                current_time=self.time,
                message_type=MessageType.CLASS,
                active_event="group_discussion_feedback",
                speaker=self.name,
                content=feedback
            )
            self.broadcast_sys.publish_sync("student", msg)
            #Update Status
            self.content = f"Group discussion feedback: {feedback}"
            self.taught += f"{self.content}\n"
            self.period = "decide_ended"  # It's over
        else:
            #Panel discussion under way
            self.content = "The group discussion is in progress; the teacher is waiting."
            #Update Status
            self.taught += f"{self.content}\n"
            self.duration_turn += 1  # Update the panel discussion rounds

    def waiting(self):
        """"""
        self.content = "Teaching is done early and teachers are waiting for class to go。"
        self.type = "waiting"

    def delay_turns(self):
        """
        If you're in a tug, return the wheel
        """
        delta = 0
        lecture_end = False
        delay_turns = 0
        if self.period == "subsection_lecture":
            # If it's a small session,
            delta = len(self.plan) - self.current_plan_turn + 1  # Calculate remaining planned paragraphs
            if delta == 0:
                lecture_end = True
        elif self.period == "subsection_activity":
            # In the case of the subsection activity phase
            delta = self.duration - self.duration_turn + 1 + 1#One more feedback
        if lecture_end:
            delay_turns = len(self.subsections) - self.current_subsection_turn + delta + 1
        else:
            delay_turns = len(self.subsections) - self.current_subsection_turn + delta

        delay_turns = delay_turns + 1 + 1#First+1 It's about doing it finish_class，Second+1 It's for update_experience

        print(f"Extra class turns: {delay_turns}")
        return delay_turns

    def finish_class(self):
        '''
        '''
        #Radio content and closing information
        msg_command = BroadcastMessage(
            current_time=self.time,
            message_type=MessageType.COMMAND,
            active_event="finish_class",
            speaker=self.name,
            content="This lesson has ended."
        )
        self.broadcast_sys.publish_sync("student", msg_command)
        msg_taught = BroadcastMessage(
            current_time=self.time,
            message_type=MessageType.CLASS,
            active_event="taught",
            speaker=self.name,
            content=f"Lesson content: {self.taught}"
        )
        log_file = os.path.join(script_dir, "teacher_log.txt")
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(self.taught)
        self.broadcast_sys.publish_sync("student", msg_taught)
        #Reset Parameters (State)）
        #Update Additional Comment Unlike Initialization
        self.class_number += 1 # Next class
        self.target = ""
        self.current_section_turn += self.sections_this_class  # Update the current section
        self.sections_this_class = 0
        #text_this_class Reset after updating experience
        self.subsections = []
        self.current_subsection_turn = 1
        self.importance = []
        self.focus = []
        self.detail_level = 0
        self.plan = []
        self.plan_methods = []
        self.current_plan_turn = 1
        self.subsection_selected = 0
        self.activity_type = ""
        self.duration = 5
        self.duration_turn = 1
        self.times = 0
        self.activity_content = ""
        self.saw = ""
        self.answered = ""
        self.discussed = ""
        self.to_solve = ""
        self.feedback = ""
        #taught Reset after updating experience
        self.experience = ""
        self.type = "finish_class"  #Yes update_experience Reset Post
        self.class_turns = 40
        #current_turn Yes update_experience Update
        self.content = "This class is over。"#Yes update_experience Center Reset
        #Time does not reset
        self.period = "update_experience" #Enter the updated experience phase


    def move(self):
        '''
        External calls for interfaces, round implementation
        '''
        if self.period == "update_experience":
            self.update_experience()
            return f"{self.name} finished reflecting on the lesson."
        if self.period == "not_started":
            self.update_status()  # Initial Status
            self.start_class()
            self.current_turn += 1
            self.time += timedelta(minutes=1)
            return f"{self.name} started class. Content: {self.content}"
        self.update_status()  # Update partial status and save current cycle status
        if self.period == "decide_ended":
            self.decide()
        if self.period == "subsection_lecture":
            self.teach()
        elif self.period == "subsection_activity":
            self.activate()
        elif self.period == "waiting_for_end":
            self.waiting()
        elif self.period == "already_ended":
            self.finish_class()

        self.current_turn += 1
        self.time += timedelta(minutes=1)
        return_msg = f"Turn {self.current_turn}: {self.name} is {self.type}. Content: {self.content}"

        return return_msg


if __name__ == "__main__":
    teacher_recorder = Recorder("teacher_log.json")
    broadcast = BroadcastSys(teacher_recorder)
    teacher = Teacher(broadcast_sys=broadcast, init_file= "C:/Users/Aover/Documents/SchoolAgent-gitee/agentschool/teacher.json")
    for i in range(10):  # Simulation 10 Cycle of teaching activities
        print(teacher.move())
        print("==========================")
