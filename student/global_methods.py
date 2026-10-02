import random
import string
import csv
import time
import datetime as dt
import pathlib
import os
import sys
import numpy
import math
import shutil, errno
import json

from os import listdir

def check_if_file_exists(curr_file):
  """
  Checks if a file exists
  ARGS:
    curr_file: path to the current csv file.
  RETURNS:
    True if the file exists
    False if the file does not exist
  """
  try:
    with open(curr_file) as f_analysis_file: pass
    return True
  except:
    return False

def translate_dict_to_str(dict_obj):
    """
    Translate a single layer dictionary to a string representation.
    """
    return "\n".join([f"{k}: {v}" for k, v in dict_obj.items()])


def translate_set_to_str(set_obj):
    """
    Translate a set to a string representation.
    """
    return "\n".join(f"- {item}" for item in sorted(set_obj))

def translate_student_to_str(scratch):
   """
   Convert the student's personality, cognitive state, affective state, and learning style to text.
   """
   personality = scratch.personality
   personality_str = translate_dict_to_str(personality)
   cognitive_state = scratch.cognitive_state
   cognitive_state_str = translate_set_to_str(cognitive_state)
   affective_state = scratch.affective_state
   affective_state_str = translate_set_to_str(affective_state)
   learning_style = scratch.learning_style
   learning_style_str = translate_dict_to_str(learning_style)

   return personality_str, cognitive_state_str, affective_state_str, learning_style_str

# Chinese numeral compatibility for legacy grade values.
def chinese_num_to_int(cn_num):
    mapping = {'\u4e00': 1, '\u4e8c': 2, '\u4e09': 3, '\u56db': 4,
               '\u4e94': 5, '\u516d': 6, '\u4e03': 7, '\u516b': 8,
               '\u4e5d': 9, '\u5341': 10, '\u5341\u4e00': 11, '\u5341\u4e8c': 12}
    return mapping.get(cn_num, -1)

def parse_grade_term(value):
    """Parse supported grade formats into a comparable (grade, term) pair."""
    if not isinstance(value, str):
        return (-1, -1)
    value = value.strip()
    import re
    match = re.fullmatch(r"Grade\s*(\d{1,2})\s+Term\s*([12])", value, re.IGNORECASE)
    if match:
        grade = int(match.group(1))
        return (grade, int(match.group(2))) if 1 <= grade <= 12 else (-1, -1)
    match = re.fullmatch(r"grade_(\d{1,2})_term_([12])", value, re.IGNORECASE)
    if match:
        grade = int(match.group(1))
        return (grade, int(match.group(2))) if 1 <= grade <= 12 else (-1, -1)
    match = re.fullmatch(r"Grade\s*(\d{1,2})", value, re.IGNORECASE)
    if match:
        grade = int(match.group(1))
        return (grade, 1) if 1 <= grade <= 12 else (-1, -1)
    match = re.fullmatch(r"(\d{1,2})", value)
    if match and 1 <= int(match.group(1)) <= 12:
        return int(match.group(1)), 1
    match = re.fullmatch(r"(\d{1,2})\s*[- ]?\s*(?:term\s*)?([12])", value, re.IGNORECASE)
    if match:
        grade = int(match.group(1))
        return (grade, int(match.group(2))) if 1 <= grade <= 12 else (-1, -1)
    for numeral, grade in sorted(((k, v) for k, v in {
        '\u5341\u4e00': 11, '\u5341\u4e8c': 12, '\u4e00': 1, '\u4e8c': 2,
        '\u4e09': 3, '\u56db': 4, '\u4e94': 5, '\u516d': 6,
        '\u4e03': 7, '\u516b': 8, '\u4e5d': 9, '\u5341': 10,
    }.items()), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(numeral):
            tail = value[len(numeral):]
            if tail in ('\u4e0a', '\u4e0a\u518c', '\u5e74\u7ea7\u4e0a', '\u5e74\u7ea7(\u4e0a)', '\u5e74\u7ea7\uff08\u4e0a\uff09', '\u4e0a\u77e5\u8bc6\u56fe\u8c31'):
                return grade, 1
            if tail in ('\u4e0b', '\u4e0b\u518c', '\u5e74\u7ea7\u4e0b', '\u5e74\u7ea7(\u4e0b)', '\u5e74\u7ea7\uff08\u4e0b\uff09', '\u4e0b\u77e5\u8bc6\u56fe\u8c31'):
                return grade, 2
    return (-1, -1)

def compare_grade_terms(a, b):
    parsed_a, parsed_b = parse_grade_term(a), parse_grade_term(b)
    return parsed_a != (-1, -1) and parsed_b != (-1, -1) and parsed_a < parsed_b

# Format retrieved concepts for inclusion in a prompt.
def format_retrieved_info(retrieved_info):
   """
   Format a mapping of focus points to retrieved concept nodes.
   """
   formatted_info = []
   for focus_point, nodes in retrieved_info.items():
        nodes_str = "\n".join(f"- {node.content}" for node in nodes)
        formatted_info.append(f"Focus point: {focus_point}\n{nodes_str}")
   return "\n\n".join(formatted_info)

# Format the student's chat history for inclusion in a prompt.
def format_chat_buffer(chat_buffer):
    """
    INPUT:
        chat_buffer: list of nodes
    OUTPUT:
        One line per chat message, containing its timestamp, sender, and content.
    """
    formatted_buffer = []
    for node in chat_buffer:
        timestamp = node.created
        sender = node.s
        content = node.content
        formatted_buffer.append(f"- {timestamp}, {sender}: {content}")
    return "\n".join(formatted_buffer)

def get_knowledge_points_from_json(student, file):
    """
    Load the knowledge points for the student's grade from a JSON file.
    Return a dictionary mapping each knowledge-point ID to its name and parent ID.

    OUTPUT:
        dedup: dictionary mapping IDs to (name, parent_id) tuples
    """
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Accept canonical labels, graph keys, numeric grades, and legacy Chinese labels.
    grade_raw = getattr(getattr(student, 'scratch', student), 'grade', None)
    if not grade_raw:
        return []
    parsed_grade, parsed_term = parse_grade_term(str(grade_raw))
    key_candidates = [grade_raw] if grade_raw in data else []
    if parsed_grade > 0 and parsed_term > 0:
        key_candidates.extend([
            f"grade_{parsed_grade}_term_{parsed_term}",
            f"Grade {parsed_grade} Term {parsed_term}",
        ])
    # Preserve candidate order while removing duplicates.
    seen = set()
    ordered_keys = []
    for k in key_candidates:
        if k not in seen:
            ordered_keys.append(k)
            seen.add(k)

    # Use the first matching graph section.
    nodes_section = None
    selected_key = None
    for k in ordered_keys:
        if k in data and isinstance(data[k], dict):
            nodes_section = data[k].get('nodes', [])
            selected_key = k
            break
    if nodes_section is None:
        return []

    dedup = {}
    for node in nodes_section:
        if isinstance(node, dict):
            kid = node.get('id')
            kname = node.get('name')
            parent_id = node.get('parent_id')
            if kid and kname:
                if kid not in dedup:
                    dedup[kid] = (kname, parent_id)
    return dedup

def load_grade_knowledge_points(student):
    """Load knowledge points for the student's grade from the first available file.
    Search order:
      1. student/math_knowledge_points.json
      2. student/teaching_knowledge_points.json
      3. math_knowledge_points.json (repository root or current working directory)
      4. teaching_knowledge_points.json
    If no file is available, return an empty list and print the attempted paths.
    """
    from pathlib import Path
    candidates = [
        Path('student/math_knowledge_points.json'),
        Path('student/teaching_knowledge_points.json'),
        Path('math_knowledge_points.json'),
        Path('teaching_knowledge_points.json'),
    ]
    tried = []
    for p in candidates:
        if p.exists():
            try:
                # print(get_knowledge_points_from_json(student, str(p)))
                return get_knowledge_points_from_json(student, str(p))
            except Exception as e:
                print(f"Failed to load knowledge point files {p}: {e}")
        tried.append(str(p))
    print("Warning: No knowledge point file found. Attempted: ", tried)
    return []
