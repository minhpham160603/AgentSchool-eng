from cognitive_module.memory import *
from cognitive_module.scratch import *
from cognitive_module.student import *
from prompt.run_ds_prompt import *
from perceive import *
from retrieve import *
from reflect import *
from plan import *
from exercise import *
from datetime import datetime, timedelta
import os

def move(student, file, i, info):
    """
    INPUT:
        student
        file: File deposited
        i: Round
        info: String, current information
    """
    print(f"--- Now {student.scratch.current_time} ---")
    node = perceive(student, info)
    retrieved = retrieve(student, node)
    if retrieved and retrieved[node.content]:
        print(f"Retrieve Relevant Memory: {retrieved[node.content]}")
    else:
        print("No relevant memories retrieved.")

    reflect(student, retrieved)

    student.scratch.current_time = student.scratch.current_time + timedelta(seconds=30) # Assumptions of time after each perception 30 sec


    student.scratch.save(f"test/{student.name}_scratch_{i}.json")  # Save Current scratch Status to File

    memory_file = f"test/{student.name}_memory_{i}"
    if not os.path.exists(memory_file):
        os.makedirs(memory_file, exist_ok=True) #Ensure memory_file Exists as Directory
    student.mem.save(memory_file)
