import sys
sys.path.append("../../")

from student.cognitive_module.memory import *
from student.cognitive_module.scratch import *
from student.cognitive_module.student import *
from student.prompt.run_ds_prompt import *


def plan(student, students, perceived_node, event_type=None, receiver=None):
    """
    Generate plans based on students' memories and current perceptions。
    INPUT:
        student: Student Category
        students: list of string, List of student names
        perceived_node: ConceptNode Category
        event_type: str, Type of current event"ask_question", "group_discussion_start"Wait）
        receiver: str, Name of recipient (default is) None）
    OUTPUT:
        objects: list of str, List of planned objects generated
    """

    if perceived_node is None:
        print("No information was sensed, so no plan was generated.")
        return None

    print(f"{student.name} is generating a plan.")

    # Based on the type of sensory information, what's going on?
    """if perceived_node.type == "knowledge" or perceived_node.type == "chat":
        return student.scratch.chat_with  # Knowledge, dialogue-type sensory information does not need to be generated
    elif perceived_node.type == "event":
        # Retrieve the latest event from memory.
        # It's like we haven't started dealing with the current situation yet
        current_event = student.mem.seq_event[0]
        # event_type = run_ds_prompt_event_type(current_event)
        if event_type == "ask_question":
            # If it's a teacher and student question and answer,
            # TODO: I'm taking the teacher's message。
            # Waiting for the teacher to send me the question, which means the teacher's words are stored student.scratch.chat_req Medium。
            # Mine student.scratch.chat_req Each element is one(time, object, content)The triad。
            # I'm taking it out time >= student.scratch.current_time and object == "teacher"Elements。
            # Put it in student.scratch.chat_buffer Medium。
            # Keep the above thought
            # Here we are perceived_node Medium content That's for the teacher
            student.scratch.chat_with.append("teacher")
            return ["teacher"]
        elif event_type == "group_discussion_start":
            # If it was a panel discussion,
            # Walk through the student list and find the same group back
            objects = []
            for s in students:
                if s.scratch.group == student.scratch.group and s != student:
                    student.scratch.chat_with.append(s.scratch.name)
                    objects.append(s.scratch.name)
            return objects"""
    if event_type == "group_discussion_start" or event_type == "group_discussion" and receiver == student.name:
        # If it was a panel discussion,
        # Choose a random object for discussion

        available_students = students.copy()

        # To rule out yourself
        if student.name in available_students:
            available_students.remove(student.name)

        print(f"Original student list: {students}")
        print(f"Current student: {student.name}")
        print(f"Available students to talk with: {available_students}")

        # Randomly select an object to discuss
        if available_students:  # Make sure the list is not empty
            discussion_target = random.choice(available_students)
        else:
            discussion_target = None  # No other students


        objects = []
        """for s in students:
            if s.scratch.group == student.scratch.group and s != student:
                student.scratch.chat_with.append(s.scratch.name)
                objects.append(s.scratch.name)"""
        objects = [discussion_target]
        print(f"{student.name} is joining the group discussion with: {objects}")
        return objects
    elif event_type == "group_discussion_end":
        # If the panel discussion is over,
        # Empty student chat records
        student.scratch.chat_with.clear()
        student.scratch.chat_buffer.clear()
        return []
    elif event_type == "ask_question":
        # If it's a teacher and student question and answer,
        student.scratch.chat_with.append("teacher")
        return ["teacher"]
    return None
