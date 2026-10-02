# -*- coding: utf-8 -*-
import sys
import argparse
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
from student.global_methods import load_grade_knowledge_points
from util.BroadcastSys import BroadcastSys
from datetime import datetime, timedelta
import os
from util.Events import *
from util.Recorder import *

def parse_arguments():
    parser = argparse.ArgumentParser(description='Run an individual AgentSchool student agent')
    
    parser.add_argument(
        '--student', '-s',
        type=str,
        default='StudentC',
        help='Student name (default: StudentC)'
    )
    
    parser.add_argument(
        '--list-students', '-l',
        action='store_true',
        help='List all available students'
    )
    
    return parser.parse_args()

def list_available_students():
    """List all available students"""
    students_dir = "student/students"
    if os.path.exists(students_dir):
        students = [d for d in os.listdir(students_dir) 
                   if os.path.isdir(os.path.join(students_dir, d))]
        if students:
            print("Available students:")
            for student in students:
                print(f"  - {student}")
        else:
            print("No available students found")
    else:
        print(f"Student directory not found: {students_dir}")


async def main():

    args = parse_arguments()
    # List available students and exit when requested.
    if args.list_students:
        list_available_students()
        return
    # Load student data and initial state from the configured files.
    student_name = "StudentA"
    student_folder = f"student/saving/{student_name}/20250901_0/{student_name}_45_1"  # Each student has a directory for memory and temporary files

    # Check for student folders
    if not os.path.exists(student_folder):
        print(f"Error: student '{student_name}' does not exist.")
        print("Available students:")
        list_available_students()
        return
    
    print(f"Using student: {student_name}")

    

    # # Synchronising folder(If not present)
    # import os
    # if not os.path.exists(student_folder):
    #     os.makedirs(f"{student_folder}/memory") # Yes memory Create a subfolder

    # broadcast_system = BroadcastSys()

    student = Student(name=student_name, folder_mem_saved=student_folder)
    # Load grade-level knowledge points (supports multiple source filenames).
    # grade_kps = load_grade_knowledge_points(student)
    # print(f"Number of information points loaded for grade: {len(grade_kps)}")

    # Number of Print Nodes
    print(f"Memory nodes for {student.name}: {len(student.mem.seq_thought) + len(student.mem.seq_knowledge)}")
    
    # # Initialize scratch some properties in,For example: retention, current_time Wait,These can be loaded from the profile or default
    # student.scratch.retention = 100 # Example value
    # student.scratch.current_time = "2025-05-28T10:00:00" # Example Time
    # student.scratch.importance_trigger_max = 50 # Example value

    # Ensure test Directory Exists
    """test_output_dir = "test"
    if not os.path.exists(test_output_dir):
        os.makedirs(test_output_dir)"""

    # # Simulate an information input,Like what the teacher taught


    content = [{"message_type": "class",
            "active_event": "ask_question",
           "speaker": "teacher",
           "content": "Now answer the question,Counting $-4, 0, 0.7, -\\frac{13}{3}, 2.5\\%, -1.2$ Medium,Negative( ).\n(A) 1 individual  \n(B) 2 individual  \n(C) 3 individual  \n(D) 4 individual"}]
    information_from_environment = ["Now answer the question,Counting $-4, 0, 0.7, -\\frac{13}{3}, 2.5\\%, -1.2$ Medium,Negative( ).\n(A) 1 individual  \n(B) 2 individual  \n(C) 3 individual  \n(D) 4 individual"]
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

        print(f"--- {student.name} Current Object List: {objects} ---")

        execute(student, objects)

        student.scratch.current_time = student.scratch.current_time + timedelta(seconds=30) # Assumptions of time after each perception 30 sec

        
        #student.scratch.save(f"test/{student.name}_scratch_{i}.json")  # Save Current scratch Status to File

        #memory_file = f"test/{student.name}_memory_{i}"
        #if not os.path.exists(memory_file):
            #os.makedirs(memory_file, exist_ok=True) #Ensure memory_file Exists as Directory
        #student.mem.save(memory_file)"""
    
    # Exercise phase
    print(f"\n--- class over ---")
    print(f"{student.name} is starting the exercises.")
   
    # Step-by-step task
    answers_file = "student/data.jsonl"
    # await exercise(student, answers_file)

    # Analysis of the results
    a1, a2 = await analyze_exercise(student)
    # print(f"\n=== Make a problem analysis ===")
    # print(f"Analysis of correct topics:\n{a1}\n")
    # print(f"Error Title Analysis:\n{a2}\n")

    print(f"=== Generating an analysis of errors and improvement areas ===")
    # result = await run_ds_prompt_improve_from_exercise(student, a1, a2)
    # # Read json Format Answers
    # data = json.loads(result)
    # # Read Parts
    # elimination = data.get("Elimination", [])
    # evolution = data.get("Evolution", {})
    # emergence = data.get("Emergence", [])

    # # Example Output
    # print("Exhausted misperceptions:", elimination)
    # print("Evolutional misconceptions:", evolution)
    # print("Added Error Awareness:", emergence)

    # Improvements
    await(improve_after_exercise(student, a1, a2))

    # Testing feedback on teacher teaching
    teaching_content = """
    Guys, let's take a look at the axes-6 and 6 What do these two points have in common with their position on the axes??\n The students were very accurate. The two points were indeed symmetrical-6 and 6,1.5 and-1.5 It's a very important feature that these two arrays are located at the same distance from the point of origin on the array axis.\n Yeah-6 and 6 So only two numbers with different symbols are in reverse,-6 and 6 It's on both sides of the original, and the distance from the original is 6 Unit length. Same,1.5 and-1.5 It's the opposite number of symbols, and they're located on both sides of the axis and at a distance from the point of origin 1.5 Each unit length. So, two numbers that are in reverse have two key characteristics: one is their symbol, and the other is their distance from the axis to the point of origin.\n Why do two opposing points have to be on either side of the original??\n The students have just precisely marked the axes-6 and 6,1.5 and-1.5 The teacher noticed that many students have discovered the characteristics of the original symmetry\"The two numbers are the same distance to the original, but in the opposite direction\",This observation is very well in place. It captures the nature of the opposite number from geometry\"They're like images in the mirror\",This metaphor is an image of the symmetry of the axes. Now, let's think, if the two points are equal in distance from the axis to the original point, but in the opposite direction, what is the relationship between the two numbers??\n If the axis is in the right direction to the left, then-1.5 and 1.5 Will the location relationship change??\n Ladies and gentlemen, please look at the list of axes 6 and-6 These two numbers, can you see what their position on the axes is??\n When they were observing the symmetry points on the axle, they were able to point them out exactly 6 and-6 It's very good that the numbers are on both sides of the original and equal in distance. The symmetry you find is the geometry of the opposite numbers -- the two numbers that are the opposite are symmetry of the original points on the axes, and the intuitive method of determining whether the two numbers are the opposite.\n In math, like 6 and-6,1.5 and-1.5 So only two numbers with different positive and negative numbers are called opposites. That is, one number is the opposite of the other, for example,6 Yes-6 The opposite,-6 Yeah 6 The opposite number,0 The opposite is still true 0,It's a special rule.\n We've learned the concept of the opposite number 6 and-6 So there's only two numbers with different numbers. So, why? 0 The opposite is 0 What does this have to do with absolute symmetry??\n The concept of the opposite is well understoodπand-πAn example of this is the opposite of the two numbers and the same absolute values. Then we look at the angle of the axes: What are the common features of the points on the axes that correspond to the opposite numbers? What is their relationship to the place of origin??\n We've studied like 6 and-6 So only two numbers with different positive and negative numbers are in reverse, and it's stipulated that 0 The opposite is 0.Let's see now 1.5 and-1.5 Who can explain their relationship in their own words??\n Today we learned the opposite of the concept, like 6 and-6,1.5 and-1.5 So only two numbers with different positive and negative numbers are in reverse. The core feature of the opposite number is that they are symmetrical on the axes of origin, i.e., at the same distance to the origin, but in the opposite direction,0 The opposite is it itself. The opposite has important application value when it comes to indicating the opposite, for example, when the temperature is zero or zero, and income or expenditure, the opposite can be accurately described.\n Ladies and gentlemen, please look at the list of axes+5 and-5 The location, can you find anything in common with them? Why are these numbers the opposite??\n Good. You've noticed that they're symmetrical on the axes of origin and are absolutely equal.\n Guys, we just saw-7 The opposite is 7,Can you explain why?-7 The opposite is 7 Is that true?.\n Very good. You're working on the case 1 The definition of the opposite number is accurately applied, i.e. only two numbers with different symbols is the opposite. For example, you correctly point out that+5 The opposite is-5,-7 The opposite is 7,-3 1/2 The opposite is 3 1/2,11.2 The opposite is-11.2.It's a clear indication that you've got the exact opposite definition.\n Let's see-3 1/2 and 3 1/2 The conversion, in the form of fractions, of opposite numbers?\n Very well, you've noticed that, in seeking the opposite number of commingling numbers, changes in symbols do not change the value of the fraction itself, which is very accurate. Understanding this is essential for the correct processing of the opposite number of fractions.\n We've just learned how to get different numbers, for example+5 The opposite is-5,-7 The opposite is 7,-3 1/2 The opposite is 3 1/2,11.2 The opposite is-11.2.So, is the pattern of conversion of decimals and integers consistent? Why??\n Very well, you can see from a comparative analysis that the reverse numbers of both integers and decimals follow the same pattern of symbol change, which fully reflects the generality of mathematical patterns. Then, who can give an example of how the opposite number is applied in real life??\n We saw-(-4)=4 And-(+5.5)=-5.5,Why do negative numbers have different results in different contexts? Can you explain the pattern??\n You've noticed the pattern of symbol change. That's good. Let's take a closer look at the mathematical principles behind the pattern: when we add a number,“-”No. It's actually asking for the opposite number and adding“+”The number is the same as the original number, determined by the definition of the opposite number, i.e. the sum of one number is equal to zero.\n We just saw it+(-4)=-4 and+(+12)=12 For example, there are students who don't think the positive number will change the value. Is that a general rule??\n Students B Take note of the sign that the negative mark changes the number, which is very well understood. Let's take another example:-(-8)How much??\n Students, let's see these four simple examples of the teaching materials:(1) -(+10) = -10；(2) +(-0.15) = -0.15；(3) +(+3) = 3；(4) -(-20) = 20.Please take a closer look at these condensed results and reflect on the pattern of symbol changes within and outside brackets?\n Zhang's making it simple(4)I got it right 20 As a result, this step is well regulated because, according to mathematical rules, two negatives meet to offset each other into positives, which is the expression of "negatively positive".\n Class, let's see the first example-(+10)=-10,Now, let's think about why+10 The negatives out there will turn the results into-10?Can you explain why you think that??\n Little Wang's explanation is good. He understands that the proper number can be omitted, so-(+10)Equals-10,This reflects the simplicity of the mathematical symbol. Likewise, it's being simplified+(-0.15)It's time for the positive and the negative-0.15,And+(+3)The center sign can be omitted and simplified to 3,-(-20)And it's right through negative 20,These are the basic rules of symbolic simplicity.\n Targeted+(-0.15)Some people think it's possible to just remove the real number?\n Now let's take a look at this 2 Simplified process:(1) -(+10) = -10,There's a negative sign for the real one；(2) +(-0.15) = -0.15,The positive hit the negative, the different hit the negative；(3) +(+3) = 3,It's the same number as the two；(4) -(-20) = 20,The two negative numbers are right. These simplicitys reflect the core of the symbol operation -- the same numbers are right and the others negative -- and that's the opposite of what we're going to learn in our next class.\n Ladies and gentlemen, we've just learned from the examples on the axes,+5 The absolute value is 5,Recorded|+5|=5,-6 The absolute value is 6,Recorded|-6|=6.Now, let me ask you a question: Why?+5 and-6 The absolute values are positive. What does that have to do with their position on the axes??\n The answer was very good, especially since absolute values mean distance and distance is not negative C The absolute values are non-negative, either on the left or on the right, at the origin of the axes. This observation is very accurate and helps us to better understand the nature of the absolute values.\n Students, we have just learned the concept of absolute values, and we know that the distance from point to point of origin of a number of axes is the absolute value of that number. Now, let's think: a A positive number,|a|That's what? a It's negative?0 And what is the absolute value? Try to explain these patterns in your own words.\n Students D The summary is very well-established, and it accurately outlines the nature of the absolute value, in particular by adding that “the positive absolute value is itself and the negative absolute value is the opposite”“0 The distance to the original point is 0”This is an exceptional example of the rigour of mathematical thinking. It's a simple and clear expression that you should learn.\n Classes, we have learned the concept of absolute values, knowing that they represent the distance from point to point of origin on a number of axes. So why is absolute values important in real life??\n Students E The reference to altitude comparisons is good, because it shows how absolute values help us to ignore directional differences and focus on the size of comparisons. That's the central role of absolute values in scientific measurements.\n Class, we already know-5 and 5 It's different on the axes, but they're both absolute values 5.So why do two numbers have the same absolute value??\n“The absolute value means the distance above the axis to the point of origin, so the distance is always non-negative. Li notes that the absolute value means the distance, and this observation is accurate because the distance is not directional?”\n Absolute values have many applications in real life, such as readings on thermometers, either zero or zero 5 It's still zero 5 D, they're with 0 All the distance 5,This distance is their absolute value. So is the altitude, whether you're above sea level 100 The rice is still below 100 Mi, you're at a vertical distance from sea level 100 meters, this distance is absolute. Absolute values are like measuring your distance from your home, whether you go east or west, you're positive because it's only about the size of the distance, not the direction.\n Why is the absolute value of negative numbers expressed in its opposite? What does that have to do with the distance on the axes??\n“Li says that absolute values can be understood from above the axis to the point of origin, which is very accurate, and helps us grasp the geometry of absolute values in an intuitive way. Who can then give an example of how a negative absolute value is reflected on the axis??”\n According to the definition of absolute value, we know that any reasonable absolute value is always non-negative, i.e|a|≥0.Who can give an example of an absolute number that can't be negative??\n Class, watch the case-15/2 and+15/2 The absolute value results, why are they the same? This reflects the nature of the absolute value?\n Li is quite accurate in referring to the notion that distance has no direction, because absolute values mean distance from point of origin and not direction, which is its geometry. The result of absolute values is always non-negative, because it cares only about the size of distance, regardless of the position of the left and right on the axis.\n Who else can explain the meaning of absolute values other than the distance on the axes? Examples of thermometers or debt?\n Zhang!\"It doesn't matter who is owed\"The concept of analogies of absolute values is very relevant, and it does help us understand intuitively that absolute values are denumerable symbols, and only retain their size-15/2 and 15/2 Although the symbols are the opposite, they're all absolute values 15/2,Indicates that the absolute value is not related to the positive or negative of the number, but only reflects the distance between the number on the axis and the point of origin.\n
    """
    # print(await run_ds_prompt_feedback_teaching(student, "I understand the concept and application of negative numbers. Thank you!"))
    
    # Select how to do the issue:
    # Modalities 1:Original Issue-by-Purpose(Slow but stable)
    # Modalities 2:Batch Interstep(Faster but more memory)
    
    """use_enhanced_version = True  # Set As True Use enhanced stept processing
    
    if use_enhanced_version:
        # Use enhanced stept processing
        from student.async_exercise import enhanced_exercise_with_progress
        try:
            answers = await enhanced_exercise_with_progress(student, answers_file, batch_size=5)
        except Exception as e:
            print(f"Enhancement processing failed,Back to original method: {e}")
            use_enhanced_version = False
    
    if not use_enhanced_version:
        # Use original step processing
        import time
        start_time = time.time()
        print(f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
        
        try:
            # Isophistication
            answers = await exercise(student, answers_file)
            
            # Time-consuming calculation
            end_time = time.time()
            duration = end_time - start_time
            print(f"Completion time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}")
            print(f"Total time taken: {duration:.2f} sec ({duration/60:.2f} min)")
            
            # Show final results
            total_questions = len(answers)
            correct_answers = sum(1 for answer in answers.values() if answer.get('correct', False))
            accuracy_rate = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
            
            print(f"\n=== Summary of findings ===")
            print(f"Students: {student.name}")
            print(f"Total number of topics: {total_questions}")
            print(f"Number of answers: {correct_answers}")
            print(f"Correct Rate: {accuracy_rate:.2f}%")
            print(f"Average time spent on subjects: {duration/total_questions:.2f} sec")
            
            # Save answer to json Documentation
            save_exercise_results(student, answers, 150.1)
            
        except Exception as e:
            print(f"There was an error in the question: {e}")
            import traceback
            traceback.print_exc()"""


    # Feedback on the process,Then update yourself with feedback.
    feedback = """
Overall feedback:Excellent performance!

You have demonstrated solid basic knowledge, rigorous logic and detailed validation habits in solving these mathematical problems,It deserves full recognition!Here's a summary of your overall performance:

Strengths:
1. Clear conceptual understanding
   - You can make a precise distinction between positive, negative and zero,And understand what they mean on specific issues(Like a profit, a loss, a higher base).
   - Correctly processed percentages, fractions and decimals(Like 2.5%=0.025,-13/3≈-4.333).

2. It's logical
   - You're using a step-by-step approach,Check options or values individually,Make sure nothing is missing.
   - Yes"0 Nature"Problem,You passed the rule(①③Correct,②④Error)I got the right answer,It's an expression of critical thinking.

3. Validation awareness
   - You've used several axes to help understand(Like profit/Distribution of losses, positive or negative),It helps to visualize answers.
   - When calculating actual height,You double-check the calculations,Avoid careless error.

4. Clarity
   - Your thinking is organized,It clearly explains the reasoning of every step(Like"-1.2 less than 0,It's the third negative").

Something that could be elevated:
1. Simplicity of language
   - Part of the explanation could be simpler(Like a problem 1 Medium"0 Not positive or negative"Just once).
   - The answer section can list the key points directly(Like"Negative:-4, -13/3, -1.2").

2. Symbolic writing norms
   - Pay attention to mathematical symbols(Like"-13/3"Should write-13/3,Keep Score).

3. Outreach thinking
   - It's like that"Benchmark height"Question,I can think further:"If someone is tall enough to-0.10 meters,What is it??"To consolidate the concept.

Summary:
You've done a great job,Especially in terms of conceptual application and logical reasoning,And try to simplify the expression,Your mathematical thinking will be more efficient and accurate!If you have more complex problems,(If mixed or applied),We can further practice how to extract critical information quickly.

Keep going,You did good! 🚀
"""

    #adjust(student, feedback)
    
    # Assessing student performance
    # await evaluate(student, "student/cognitive_style_inventory.json", 5)
    # await evaluate_bfi(student, "student/big_five_inventory.json", "bfi_2")
    
    

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
    # main()
