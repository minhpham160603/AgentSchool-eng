import sys
# sys.path.append("../")

from student.cognitive_module.memory import *
from student.cognitive_module.scratch import *
from student.cognitive_module.student import *
from student.prompt.run_ds_prompt import *
from student.perceive import *
from student.retrieve import *
from student.reflect import *
from student.plan import *
from student.execute import *
from student.exercise import *
from student.evaluate import *
from util.BroadcastSys import BroadcastSys
from datetime import datetime, timedelta
import os
from util.Events import *
from util.Recorder import *


def main():
    # From json Load data in file - This section needs to specify how to load student data and initial information
    # Suppose we created an example of a student
    student_name = "StudentA"
    student_folder = f"student/students/{student_name}" # Suppose each student has a folder containing memories and temporary files



    # # Create corresponding folder (if no such folder exists))
    # import os
    # if not os.path.exists(student_folder):
    #     os.makedirs(f"{student_folder}/memory") # Yes memory Create a subfolder

    # broadcast_system = BroadcastSys()

    student = Student(name=student_name, folder_mem_saved=student_folder)

    # Number of Print Nodes
    print(f"{student.name} has {len(student.mem.seq_thought) + len(student.mem.seq_knowledge)} memory nodes.")

    # # Initialize scratch some of the attributes, for example, retention, current_time Wait, these can be loaded from the profile or default
    # student.scratch.retention = 100 # Example value
    # student.scratch.current_time = "2025-05-28T10:00:00" # Example Time
    # student.scratch.importance_trigger_max = 50 # Example value

    # Ensure test Directory Exists
    test_output_dir = "test"
    if not os.path.exists(test_output_dir):
        os.makedirs(test_output_dir)

    # # Simulate an input of information, such as the content of a teacher' s lecture
    information_from_environment = ["Today we are studying Chapter 1: Rational Numbers. Positive numbers are greater than 0, such as +3 and 500. Negative numbers are less than 0, such as -12 and -0.7. Zero is neither positive nor negative. Is -5 positive or negative? It is negative. If income of $100 is represented by +100, how should spending $80 be represented? It is -80.",
        "Next, let's classify rational numbers. Integers include positive integers, zero, and negative integers, such as 1, 0, and -3. Fractions include positive and negative fractions, such as 1/3 and -2/7. Rational numbers include both integers and fractions. Is 5 an integer or a fraction? It is an integer. Is -0.5 rational? Yes, it is a negative fraction.",
        "In Section 1.2, we study the number line. A number line has an origin, a positive direction, and a unit length. Mark 0 on a line, draw an arrow to the right for the positive direction, and use evenly spaced ticks for the units. Where does -4 lie relative to the origin? On the left. Which is farther to the right, -2 or 3? The number 3.",
        "In Section 1.3, we study opposites. Two numbers with different signs and the same absolute value are opposites, such as 5 and -5. The opposite of 0 is 0. What is the opposite of -7? It is 7. If a and b are opposites, what is a + b? It is 0.",
        "In Section 1.4, absolute value means distance from zero on the number line. For example, |-4.5| = 4.5 and |0| = 0. Which is smaller, -5 or -3? It is -5, because among negative numbers the one with the greater absolute value is smaller.",
        "In Section 1.5, remember that every positive number is greater than 0, and every negative number is less than 0. When comparing two negative numbers, the one with the smaller absolute value is greater. For example, -1/3 is greater than -1/2. Which is greater, -10 or -5? It is -5.",
        "In Sections 1.6–1.8, we study addition and subtraction of rational numbers. When adding numbers with the same sign, keep that sign and add their absolute values: (-3) + (-5) = -8. When adding numbers with different signs, keep the sign of the number with the greater absolute value and subtract the absolute values: 5 + (-3) = 2. Rewrite subtraction as addition of the opposite: 7 - 10 = 7 + (-10) = -3. What is (-4) + (-6)? It is -10. What is 9 - 12? It is -3."]


    content = [{"message_type": "class",
            "active_event": "ask_question",
           "speaker": "teacher",
            "content": "Now answer the question. Among the numbers $-4, 0, 0.7, -\\frac{13}{3}, 2.5\\%, -1.2$, how many are negative?\n(A) 1  \n(B) 2  \n(C) 3  \n(D) 4"}]
    information_from_environment = ["Now answer the question. Among the numbers $-4, 0, 0.7, -\\frac{13}{3}, 2.5\\%, -1.2$, how many are negative?\n(A) 1  \n(B) 2  \n(C) 3  \n(D) 4"]
    """   print(f"--- {student.name} Start class ---")
    for i, information in enumerate(content):
        info = information.get("content", "")
        info_type = information.get("active_event", "")
        print(f"--- Now {student.scratch.current_time} ---")
        node = perceive(student, info, sender="teacher", info_type=info_type)
        retrieved = retrieve(student, node)
        if retrieved and retrieved[node.content]:
            print(f"Retrieve Relevant Memory: {retrieved[node.content]}")
        else:
            print("No relevant memory retrieved.")

        reflect(student, retrieved)

        objects = plan(student, [student], node)

        print(f"--- {student.name}'s current objects: {objects} ---")

        execute(student, objects)

        student.scratch.current_time = student.scratch.current_time + timedelta(seconds=30) # Assumptions of time after each perception 30 sec


        #student.scratch.save(f"test/{student.name}_scratch_{i}.json")  # Save Current scratch Status to File

        #memory_file = f"test/{student.name}_memory_{i}"
        #if not os.path.exists(memory_file):
            #os.makedirs(memory_file, exist_ok=True) #Ensure memory_file Exists as Directory
        #student.mem.save(memory_file)"""

    # After class, make questions
    print("\n--- Class finished ---")
    print(f"{student.name} is starting the exercises.")
    exercise_questions = ["1. Among the numbers $-4, 0, 0.7, -\\frac{13}{3}, 2.5\\%, -1.2$, how many are negative?\n(A) 1  \n(B) 2  \n(C) 3  \n(D) 4",
                          "2. If a profit of 2 ten-thousand yuan is represented by $+2$ ten-thousand yuan, how should a loss of 5 ten-thousand yuan be represented?\n(A) 5 ten-thousand yuan  \n(B) 7 ten-thousand yuan  \n(C) $-5$ ten-thousand yuan  \n(D) $-3$ ten-thousand yuan",
                          "3. Which statements about 0 are correct? (Select all that apply.)\n① 0 separates positive numbers from negative numbers.  \n② 0 is positive.  \n③ 0 is a natural number.  \n④ 0 is not an integer.",
                          "4. Sort the following numbers into the appropriate groups:\n$$\n-10, 1, -0.5, 0, 36, -\\frac{2}{5}, 15\\%, -60, -\\frac{1}{53}, 22.8.\n$$\nPositive numbers: ________________________  \nNegative numbers: ________________________",
                          "5. A teacher uses 1.60 meters as a reference height. Five students' heights, relative to this reference, are recorded as $+0.12, -0.05, 0, +0.07, -0.02$ meters. What do the positive and negative values mean? What is each student's actual height?"]

    # answers_file = "questions/1.json"
    answers_file = "student/data.jsonl"
    # answers = exercise(student, answers_file)
    # Save answer to json Documentation
    # save_exercise_results(student, answers, 150)


    # Provide feedback on the process and then update itself on the basis of feedback.
    feedback = """
Overall feedback: excellence!

You've shown solid basic knowledge, rigorous logic and detailed validation habits in solving these mathematical problems, and you deserve full recognition! Here is a summary of your overall performance:

Strengths:
1. Clear conceptual understanding
   - You can make an accurate distinction between positives, negatives and zeros and understand what they mean in a particular case (e.g. profit, loss, high benchmark)).
   - The conversion of percentages, fractions and decimals has been properly processed (e.g 2.5%=0.025,-13/3≈-4.333).

2. It's logical
   - You use a step-by-step analysis to check options or values on a case-by-case basis to ensure that no details are omitted.
   - Yes"0 Nature"In question, you go through exclusion(①③Correct,②④It's the right answer.

3. Validation awareness
   - You've used several axes to help understand (e.g. profit)/Losses, distribution of positive and negative figures) which help to visualize answers.
   - When calculating the actual height, check the calculation over and over again to avoid careless error.

4. Clarity
   - Your process of thinking is structured and explains clearly the reasoning underlying each step (e.g"-1.2 less than 0,It's the third negative").

Something that could be elevated:
1. Simplicity of language
   - Part of the explanation could be more streamlined (e.g. problem) 1 Medium"0 Not positive or negative"Just once).
   - The answers section can directly identify key points (e.g"Negative:-4, -13/3, -1.2").

2. Symbolic writing norms
   - Take care of mathematical symbols"-13/3"Should write-13/3,Keep Score).

3. Outreach thinking
   - It's like that"Benchmark height"One of the questions that you can think about is,:"If someone is tall enough to-0.10 What's the actual amount??"To consolidate the concept.

Summary:
You have excellent solvency, especially in conceptual application and logical reasoning. You continue to be careful and authentic, while trying to simplify expression, and your mathematical thinking will be more efficient and accurate. If you encounter more complex problems (such as mixed computing or practical applications), you can practice more quickly how to extract key information.

You're doing great! 🚀
"""

    #adjust(student, feedback)

    # Assessing student performance
    evaluate(student, "student/questionnaire.json", 2)



if __name__ == "__main__":
    main()
