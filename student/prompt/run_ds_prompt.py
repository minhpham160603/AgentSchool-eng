import asyncio
import sys
import ast
import json
import demjson3
import os
import re
from sentence_transformers import SentenceTransformer

sys.path.append("../../")

from student.global_methods import *
from student.prompt.utils import *
from util.model import call_LLM, call_LLM_sync

import asyncio
from functools import lru_cache  # For optional LRU Cache

from typing import Dict, List

# Global Cache: Text -> Vector List
embedding_cache: Dict[str, List[float]] = {}
cache_lock = asyncio.Lock()  # Steplock, make sure it's safe


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks from LLM outputs."""
    try:
        return re.sub(r"(?is)<think>.*?</think>", "", text)
    except Exception:
        return text

"""system_content = "You're an expert in cognitive modelling. You're in charge of internal thinking." \
"You need to be based on the student's personality, cognitive state, emotional state and learning style," \
"To simulate the student's thoughts and reactions." \
"Make sure your answers are consistent with the students' personality and cognitive state and reflect their emotional state and learning style."\
"Involving json Only output when formatted JSON Data, do not contain any explanatory text,markdown Block Symbols (e. g.) ```json)or extra content."""

format_req = "When JSON is requested, output only valid JSON with the requested keys. Do not add explanations or Markdown fences."

def set_system_content(student):
    """
    Update system alerts according to the student' s current state
    """
    personality_str, cognitive_state_str, affective_state_str, learning_style_str = translate_student_to_str(student.scratch)
    system_prompt = f"""
You are role-playing a student in an intelligent learning system. Use the profile below to shape your answers:

Personality (MBTI): {student.scratch.MBTI}
Cognitive state: {cognitive_state_str}
Affective state: {affective_state_str}
Learning style (Felder–Silverman): {learning_style_str}
Attention (0.0–1.0): {student.scratch.attention_level}
Stress (0.0–1.0): {student.scratch.stress}

Match the student's personality, knowledge, cognitive state, emotions, and learning style. High attention may produce longer, more detailed responses; low attention may produce brief or fragmented responses. Adapt learning strategies to the profile: sensing learners favor concrete examples, intuitive learners connect abstract ideas, active learners prefer practice and discussion, reflective learners prefer summarizing and notes, sequential learners explain in steps, and global learners start with the overall structure.

When answering a teacher, sound like a natural student rather than a formal expert. Keep about 70% of ordinary replies very short (roughly one to five words). Across replies, roughly 30% may confirm or acknowledge, 40% may name a relevant concept or step, 15% may give a direct numeric or letter answer, 10% may add a brief correction or thought, and 5% may explain a solution when asked. Choose a response that fits the question. Occasionally make a small calculation error (about 5%) or give an incomplete answer that invites teacher guidance (about 10%).

Write all natural-language output in English, including explanations, examples, and JSON string values. Preserve exact schema keys and required enum values when a task specifies them. When JSON is requested, output only valid JSON without Markdown fences or extra explanation.
"""

    return system_prompt


async def _call_student_llm(messages, response_format=None):
    """Apply the English-output requirement to every active student prompt."""
    instruction = (
        "Write all natural-language responses in English. Keep required JSON keys and enum values exact. "
        "When JSON is requested, return only valid JSON without Markdown or extra explanation."
    )
    messages = [dict(message) for message in messages]
    system = next((message for message in messages if message.get("role") == "system"), None)
    if system is None:
        messages.insert(0, {"role": "system", "content": instruction})
    else:
        system["content"] = f"{system.get('content', '')}\n\n{instruction}"
    if response_format is None:
        return await call_LLM("student", messages)
    return await call_LLM("student", messages, response_format)


async def run_ds_prompt_judge_type(information):
    """
    Type of information judged
    """
    prompt = f"""
    Classify the following information as exactly one of these types: event, chat, or knowledge.
    {information}
    Output only the type label, with no additional text.
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    #return call_deepseek(messages)
    return await _call_student_llm(messages)

async def run_ds_prompt_summarize_event(information):
    """
    Content of the summary event, type, keyword
    OUTPUT:Similar
        {
        "content": "Discussion on positive and negative numbers",
        "event_type": "Panel discussion",
        "keywords": ["Positive and negative"]
        }
    """
    prompt = f"""
    Summarize the following interaction and classify it as either teacher-student question and answer or group discussion:
    {information}
    Return only a JSON object with exactly these keys: "content" (a concise summary), "event_type" (the interaction type), and "keywords" (a list of relevant terms). Do not include Markdown or other text.
    """

    messages = [
        {"role": "system", "content": format_req},
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)


async def run_ds_prompt_absorb_info(Student, information, absorb_rate):
    """
    Run DS Phrasing, absorbing information.
    INPUT:
        Student: Student category
        information: string
        absorb_rate: float
    OUTPUT:
        absorbed_info: string
    """
    # personality_str, cognitive_state_str, affective_state_str, learning_style_str = translate_student_to_str(Student.scratch)

    prompt = f"""
    You are role-playing a student listening to a lesson. The teacher says:
    {information}
    Your current stress and attention affect how much you absorb. The estimated absorption rate is {absorb_rate}.
    Simulate the student's listening state and return only the information the student actually takes in, as one paragraph.
    """

    messages = [
        {"role": "system", "content": set_system_content(Student)},
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)

async def run_ds_prompt_summarize_knowledge(Student, absorbed_info, information):
    """
    Summarize what the student learned by considering both the teacher's explanation and what the student absorbed.
    Include relevant knowledge points and the student's understanding.
    """
    # personality_str, cognitive_state_str, affective_state_str, learning_style_str = translate_student_to_str(Student.scratch)

    prompt = f"""
    You are a student who has just attended a lesson.
    Teacher's explanation: {information}
    Information you absorbed: {absorbed_info}
    Summarize what you learned in your own words. Use relevant knowledge-point labels and rate the importance from 0 to 10.
    Return only a JSON object with exactly these keys: "knowledge_tag", "content", and "importance". Use an array of labels for "knowledge_tag", a string for "content", and an integer from 0 to 10 for "importance". Do not include Markdown or other text.
    """

    messages = [
        {"role": "system", "content": set_system_content(Student)},
        {"role": "user", "content": prompt}
    ]

    response_format = {
        'type': 'json_object'
    }

    return await _call_student_llm(messages, response_format)
    # return call_deepseek(messages, response_format=True)

async def run_ds_prompt_generate_understanding(Student, information, absorption_desc, knowledge_points, mems):
    """
    Let students develop personalized understanding of what they learn based on all their intrinsic properties,
    This includes correct understanding, possible misperceptions and questions.
    """
    # personality_str, ... = translate_student_to_str(Student.scratch) # Ensure system_content There's a personal description

    knowledge_points = [kp[0] for kp in knowledge_points.values()] # Only name

    prompt = f"""
    # Role-Playing Command
    Role-play the student. Write a personal account of what you understood, shaped by the student's current state; it does not need to be a perfect summary.

    # Scenario
    The teacher just taught:
    ---
    {information}
    ---

    # What you absorbed
    {absorption_desc}

    # Relevant memories
    {mems}

    # Core mission: Generate your personalized understanding
    Use the student's personality, cognitive state, emotions, learning style, listening state, and relevant memories to decide what they understood from the lesson. Return that personal understanding as JSON.

    # Cognitive Filter Guidance (Please follow strictly):
    - High openness may lead the student to connect new ideas to prior knowledge or consider abstract meaning.
    - Low conscientiousness or attention may lead to fragmented understanding, inaccuracies, or misconceptions.
    - If the student believes they understand more than they do, reflect that overconfidence in "understanding_content".
    - Sensing learners focus more on the teacher's concrete examples than on abstract definitions.
    - Under high stress, the student may miss difficult material; express remaining confusion in "lingering_questions".

    # Knowledge Point Label
    Select knowledge-point labels exactly from this list: {knowledge_points}

    # Output Format
    Return only a valid JSON object with the requested keys. Do not include explanations or Markdown.
    {{
        "knowledge_tag": ["Relevant knowledge point labels"],
        "understanding_content": "What you think you learned, in your own words. This may be incomplete or incorrect.",
        "lingering_questions": "Questions or confusion that remain, if any.",
        "importance": 0
    }}
    """

    messages = [
        {"role": "system", "content": set_system_content(Student)}, # Your student profile
        {"role": "user", "content": prompt}
    ]

    response_format = {'type': 'json_object'}
    return await _call_student_llm(messages, response_format)

async def run_ds_prompt_generate_misconceptions(Student, learned_knowledge):
    """
    Generate possible misconceptions based on what the student has learned.
    INPUT:
        Student: Student category
        learned_knowledge: str
    OUTPUT:
    {
        "misconceptions": ["A list of possible misconceptions about this concept, or an empty list if there are none."]
    }
    """
    prompt = f"""
    You are the student. Use your learning and the common mistakes below to identify misconceptions you may have about this knowledge.
    What you learned: {learned_knowledge}
    Your common mistakes: {Student.scratch.common_mistakes}
    Return a JSON object with exactly one key, "misconceptions". Its value must be a list of 3–5 possible misconceptions, or an empty list if you have none. Do not include Markdown or other text.
    {{
        "misconceptions": ["A possible misconception about this concept"]
    }}
    """

    messages = [
        {"role": "system", "content": set_system_content(Student)},
        {"role": "user", "content": prompt}
    ]

    response_format = {
        'type': 'json_object'
    }

    answer = await _call_student_llm(messages, response_format)

    # Parsing JSON String
    if isinstance(answer, str):
        # Clear and parse JSON
        cleaned_answer = answer.strip().replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'").replace('\uFF0C', ',').replace('\uFF1A', ':')
        try:
            answer_dict = json.loads(cleaned_answer)
        except json.JSONDecodeError:
            try:
                answer_dict = demjson3.decode(cleaned_answer)
            except Exception as e:
                print(f"ERROR: Could not initialise Bonobo misconceptions: {e}")
                print(f"Original Response: {answer[:200]}")
                return []
    else:
        answer_dict = answer

    misconceptions = answer_dict.get('misconceptions', [])
    print(f"Students{Student.name}It's a myth: {misconceptions}")

    if not misconceptions:
        return []
    else:
        # Randomly select a myth return
        random_index = random.randint(0, len(misconceptions) - 1)
        print(f"Students{Student.name}Selective Myths: {misconceptions[random_index]}")
        return misconceptions[random_index]


async def run_ds_prompt_thought_keywords(thought_content):
    """
    Generate keywords based on what students think.
    """
    prompt = f"""
    Extract a short list of keywords that captures the main ideas in this student thought:
    {thought_content}
    Return only the keyword list in English.
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)

async def run_ds_prompt_chat_keywords(information):
    """
    Generate keywords based on chat content.
    """
    prompt = f"""
    Extract 3–5 concise English keywords from this conversation:
    {information}

    Please JSON Format Output Keylist:
    {{"keywords": ["Keyword 1", "Keyword 2", "Keyword 3"]}}

    Without keywords, output:
    {{"keywords": []}}
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    response_format = {
        'type': 'json_object'
    }

    # return call_deepseek(messages)
    result = await _call_student_llm(messages, response_format)

    if not result:
        return []

    # Clear and parse JSON
    cleaned = result.strip().replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'").replace('\uFF0C', ',').replace('\uFF1A', ':')

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed.get('keywords', [])
        elif isinstance(parsed, list):
            return parsed
        else:
            return []
    except json.JSONDecodeError:
        try:
            parsed = demjson3.decode(cleaned)
            if isinstance(parsed, dict):
                return parsed.get('keywords', [])
            elif isinstance(parsed, list):
                return parsed
            else:
                return []
        except Exception as e:
            print(f"ERROR: Can not parse chat keywords: {e}")
            # As fallback,Returns commas separated string
            return [k.strip() for k in result.split(',') if k.strip()]


def run_ds_prompt_recognize_info(Student, absorbed_info):
    """
    Convert incoming strings into meta-information, including type, description, keyword, importance of information.
    INPUT:
        Student: Student category
        absorbed_info: string
    OUTPUT:
        learned_knoledge:
    """
    pass


def run_ds_prompt_reflect(Student, retrieved_mem):
    """
    Based on the retrieved memories, create new ideas.
    INPUT:
        Student: Student category
        retrieved_mem: {Description of current node}: {Type of node retrieved: List of retrieved nodes}}
    OUTPUT:
        thought_content: string
    """

async def run_ds_prompt_importance_event(Student, information):
    """
    Generate a weight rating based on the importance of the information.
    INPUT:
        Student: Student category
        information: string
    OUTPUT:
        importance: int
    """
    # personality_str, cognitive_state_str, affective_state_str, learning_style_str = translate_student_to_str(Student.scratch)

    prompt = f"""
    Rate how important this information is to you on a scale from 1 to 10. A rating of 1 means not important; 10 means very important.
    Information: {information}
    Output only an integer from 1 to 10.
    """

    messages = [
        {"role": "system", "content": set_system_content(Student)},
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)

async def run_ds_prompt_importance_thought(Student, thought_content):
    """
    Generate a weight rating based on the importance of thinking.
    """
    # personality_str, cognitive_state_str, affective_state_str, learning_style_str = translate_student_to_str(Student.scratch)

    prompt = f"""
    Rate how important this thought is to you on a scale from 1 to 10. A rating of 1 means not important; 10 means very important.
    Thought: {thought_content}
    Output only an integer from 1 to 10.
    """

    messages = [
        {"role": "system", "content": set_system_content(Student)},
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)

async def run_ds_prompt_importance_chat(Student, chat_content):
    """
    Generate a weight rating based on the importance of thinking.
    """
    # personality_str, cognitive_state_str, affective_state_str, learning_style_str = translate_student_to_str(Student.scratch)

    prompt = f"""
    Rate how important this conversation is to you on a scale from 1 to 10. A rating of 1 means not important; 10 means very important.
    Conversation: {chat_content}
    Output only an integer from 1 to 10.
    """

    messages = [
        {"role": "system", "content": set_system_content(Student)},
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)

# async def get_local_embedding(information, model_name="BAAI/bge-small-en-v1.5"):
#     """Step to calculate the embedded vector"""
#     def _compute_embedding():
#         model = SentenceTransformer(model_name)
#         embedding = model.encode(information, convert_to_tensor=True)
#         return embedding.tolist()

#     # Perform calculation-intensive operations in online pools
#     return await asyncio.to_thread(_compute_embedding)

async def get_local_embedding(information, model_name="BAAI/bge-small-en-v1.5"):
    """Step to calculate embedded vectors to support caches to enhance performance.
    Calculate and cache on first call, then return directly.
    """
    # Standardized Cache Keys (to remove excess spaces and avoid duplication))
    cache_key = information.strip()

    async with cache_lock:
        if cache_key in embedding_cache:
            return embedding_cache[cache_key]  # Cache in. Go straight back

        # Cache uncut, call original logic
        def _compute_embedding():
            # Environmental variable preference
            env_model = os.getenv("BGE_MODEL")
            load_target = env_model if env_model else model_name
            model = SentenceTransformer(load_target)
            embedding = model.encode(information, convert_to_tensor=True)
            return embedding.tolist()

        # Perform calculation-intensive operations in online pools
        vector = await asyncio.to_thread(_compute_embedding)

        # Store to Cache
        embedding_cache[cache_key] = vector
        return vector

async def clear_embedding_cache():
    """Clear Embedding Cache for resetting or memory management."""
    async with cache_lock:
        embedding_cache.clear()
        print("Embedding Cache emptied.")

def get_cache_size():
    """Get Current Cache Size (Try))."""
    return len(embedding_cache)

async def run_ds_prompt_generate_focus(statements, n=3):
    """
    Based on the students' memories, create a focus.
    INPUT:
        Student: Student category
        statements: string, Students' memories
        n: int, Number of focus points generated
    OUTPUT:
        focus: list of strings containing generated focus questions
    """
    prompt = f"""
    Based on the student's memories below, write {n} focus questions that encourage deeper thinking and understanding:
    {statements}

    Return a JSON object with exactly one key, "focus_points", whose value is a list of questions. If no useful questions can be generated, return an empty list.
    JSON format:
    {{"focus_points": ["question 1", "question 2", "question 3"]}}

    If there's no focus, output:
    {{"focus_points": []}}
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    response_format = {
        'type': 'json_object'
    }

    # focus = call_deepseek(messages)
    focus = await _call_student_llm(messages, response_format)

    if not focus:
        return []

    # Clear Strings, Replace Chinese Punctuation
    cleaned_focus = _strip_think(focus).strip()
    cleaned_focus = cleaned_focus.replace('"', '"').replace('"', '"')  # Chinese Double Quote
    cleaned_focus = cleaned_focus.replace(''', "'").replace(''', "'")  # Chinese single quotation marks
    cleaned_focus = cleaned_focus.replace('\uFF0C', ',').replace('\uFF1A', ':')  # Chinese commas and colons

    # Try Parsing JSON
    try:
        result = json.loads(cleaned_focus)
        if isinstance(result, dict):
            return result.get('focus_points', [])
        elif isinstance(result, list):
            return result
        else:
            return []
    except json.JSONDecodeError:
        try:
            result = demjson3.decode(cleaned_focus)
            if isinstance(result, dict):
                return result.get('focus_points', [])
            elif isinstance(result, list):
                return result
            else:
                return []
        except Exception as e:
            print(f"ERROR: Could not parse focus: {e}")
            print(f"Original String: '{focus[:200]}'")
            return []


async def run_ds_prompt_reflect(student, focus_point, nodes):
    """
    Generate reflections based on focus and retrieved memory.
    INPUT:
        student: Student Category
        focus_point: string, the current focus point
        nodes: list of ConceptNode, Retrieved Memory
    OUTPUT:
        thought_content: string, The content of the thought generated
    """
    mems = ""
    for node in nodes:
        mems += f"{node.content}\n"
    # personality_str, cognitive_state_str, affective_state_str, learning_style_str = translate_student_to_str(student.scratch)

    prompt = f"""
    You are a student reflecting on this focus point: {focus_point}
    Relevant information retrieved from your memory:
    {mems}
    Reflect on the focus point using the retrieved information. Summarize your understanding and thoughts in a short passage. Respond as the student.
    """

    messages = [
        {"role": "system", "content": set_system_content(student)},
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)

async def run_ds_prompt_generate_answer(student, question, mems_str, misconceptions=[]):
    """
    Generate answers to practice questions based on students' memories and questions.
    INPUT:
        student: Student Category
        question: string, Practice issues
        mems_str: string, Students' memories
    OUTPUT:
        answer: json Format, key for reflection process and answer, value string
    """
    prompt = f"""
    Role-play the student answering the exercise below. Follow these requirements:
    Cognitive state:
    {student.scratch.cognitive_state}

    Attention level:
    {student.scratch.attention_level}

    Relevant memories:
    {mems_str}

    Current misconceptions about the knowledge point:
    {misconceptions if misconceptions else "none"}

    Exercise:
    {question}

    Instructions:
    1. Base your answer only on the memories and information available to you as this student.
    2. If the problem is unfamiliar, uncertain, or not covered by what you learned, do not invent knowledge. Say that you are unsure.
    3. If you guess or decide not to answer, briefly explain why.
    4. Let your response reflect the student's cognitive state and attention.
    5. Return a JSON object with exactly two string fields: "answer" and "thought_process". The latter should briefly describe how you interpreted the question, what you recalled or guessed, and any relevant uncertainty or emotional response.

    Output format:
    {{
    "answer": "...",
    "thought_process": "..."
    }}
    Return only valid JSON, with no explanation outside it and no Markdown fences. For multiple-choice questions, put only the option letter (for example, A, B, C, or D) in "answer".
    """
    """messages = [
        {"role": "system", "content": set_system_content(student)},
        {"role": "user", "content": prompt}
    ]"""
    messages = [
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages, response_format=True)
    response_format = {
        'type': 'json_object'
    }

    return await _call_student_llm(messages, response_format)



async def run_ds_prompt_regenerate_answer(student, question, mems_str, supervision):
    """
    Regenerate the student's answer after grade-level supervision flags a concern.
    """
    prompt = f"""
    You are role-playing the student revising your previous answer. The system identified a knowledge point that may have been used incorrectly:

    System feedback:
    {supervision}

    Cognitive state:
    {student.scratch.cognitive_state}

    Attention level:
    {student.scratch.attention_level}

    Relevant memories:
    {mems_str}

    Exercise:
    {question}

    Reconsider the exercise and revise your answer if appropriate:

    ------------------------
    1. Use only the memories and information available to you as this student; do not consult outside sources.
    2. If the exercise is unfamiliar or uncertain, do not invent knowledge. Say that you are unsure.
    3. If you guess or decide not to answer, briefly explain why.
    4. Let your response reflect the student's cognitive state and attention.
    5. Return a JSON object with exactly two string fields: "answer" and "thought_process". Explain your revised reasoning briefly, including what you recalled and any uncertainty.

    Output format:
    {{
    "answer": "Your final answer",
    "thought_process": "Brief reasoning for your revised answer, including any uncertainty"
    }}
    Return only valid JSON, with no Markdown or text outside the object. For multiple-choice questions, put only the option letter (A, B, C, or D) in "answer".
    In "thought_process", briefly reflect on the system feedback: did you use knowledge that was not in your memories, and what evidence supports your revised answer? If you still do not know, say so. Do not leave the answer blank unless the student's low attention or high stress makes silence plausible.
    """

    """messages = [
        {"role": "system", "content": set_system_content(student)},
        {"role": "user", "content": prompt}
    ]"""
    messages = [
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages, response_format=True)
    response_format = {
        'type': 'json_object'
    }

    return await _call_student_llm(messages, response_format)


async def run_ds_prompt_event_type(current_event):
    """
    Judge the type of current event
    """

    prompt = f"""
    Classify the following event:
    {current_event}
    Return exactly "qa" for a teacher-student question-and-answer exchange or "group_discussion" for a group discussion. Output only the label.
    """
    messages = [
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)

async def run_ds_prompt_adjust(student, feedback):
    """
    Adapt student attributes to feedback and students' original attributes
    INPUT:
        student: Student Category
        feedback: string, Feedback content
    OUTPUT:
        adjusted: json Format, keys are student properties, values are adjusted values
    """
    # personality_str, cognitive_state_str, affective_state_str, learning_style_str = translate_student_to_str(student.scratch)

    prompt = f"""
    Update the student's profile in response to this feedback: {feedback}
    Return only a JSON object containing changed fields from: "personality", "cognitive_state", "affective_state", "learning_style", "attention_level", and "stress". Omit unchanged fields. Preserve the existing value format and use English prose for any text values.
    """

    messages = [
        {"role": "system", "content": set_system_content(student)},
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)

async def run_ds_prompt_extract_knowledge_tag(content, knowledge_points):
    """
    Identify the knowledge points discussed in the provided text.
    """
    knowledge_points = [kp[0] for kp in knowledge_points.values()] # Only name

    prompt = f"""
    Select knowledge-point names only from this list; do not invent or paraphrase labels: {knowledge_points}
    Text: {content}

    Return a JSON object with exactly one key, "knowledge_tags", whose value is a list of matching knowledge-point names.
    {{"knowledge_tags": ["Knowledge point 1", "Knowledge point 2"]}}

    If none of the listed knowledge points apply, return:
    {{"knowledge_tags": []}}
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    response_format = {
        'type': 'json_object'
    }

    # kts = call_deepseek(messages)
    kts = await _call_student_llm(messages, response_format)

    if not kts:
        return []

    # Clear Strings, Replace Chinese Punctuation
    cleaned_kts = kts.strip()
    cleaned_kts = cleaned_kts.replace('"', '"').replace('"', '"')  # Chinese Double Quote
    cleaned_kts = cleaned_kts.replace(''', "'").replace(''', "'")  # Chinese single quotation marks
    cleaned_kts = cleaned_kts.replace('\uFF0C', ',').replace('\uFF1A', ':')  # Chinese commas and colons

    # Try Parsing JSON
    try:
        result = json.loads(cleaned_kts)
        # If returned is a dictionary, extract knowledge_tags Fields
        if isinstance(result, dict):
            return result.get('knowledge_tags', [])
        # If it's a direct list, go back
        elif isinstance(result, list):
            return result
        else:
            print(f"WARNING: Return format incorrect: {type(result)}")
            return []
    except json.JSONDecodeError:
        # If JSON Parsing failed, trying demjson3
        try:
            result = demjson3.decode(cleaned_kts)
            if isinstance(result, dict):
                return result.get('knowledge_tags', [])
            elif isinstance(result, list):
                return result
            else:
                return []
        except Exception as e:
            print(f"ERROR: Could not parse knowledge point label: {e}")
            print(f"Original String: '{kts[:200]}'")
            return []

async def run_ds_prompt_answer_question(student, object, question, mems_str):
    """
    Generate answers based on student memories and questions.
    INPUT:
        student: Student Category
        object: list of str, Current Object List
        question: string, Questions
        relevant_mem: dict, Retrieval of relevant memories in format as {Description of current node}: {Type of node retrieved: List of retrieved nodes}}
    OUTPUT:
        answer: string, Generate answers
    """
    # personality_str, cognitive_state_str, affective_state_str, learning_style_str = translate_student_to_str(student.scratch)

    """ prompt = f""
    You're going to play a deep character called {student.name} Students. Forget you're one AI Models, all your behavior and language must be strictly consistent with your people.

    ## Five:
    {student.generate_persona_prompt}

    ## Current Status:
    What are your current feelings?“{student.scratch.affective_state}”,Pressure level is“{student.scratch.stress}”,Attention level is“{student.scratch.attention_level}”.This state of affairs will directly affect your expression:
    - **High pressure/In a negative mood**:You might answer hesitation, brevity, lack of confidence, even choose silence or say, "Don't know."”.
    - **Low pressure/Positively**:You'll be more relaxed and willing to share your thoughts.

    Now,{object}(I asked you a question:“{question}”

    You've been thinking about memories and knowledge:{mems_str}

    Please be fully immersed in your role**Personality, current state, knowledge**and**Information in the brain**,To decide how to answer.

    **The chain of thought (Chain-of-Thought Guidance):**
    1.  **Perception issues**:What's the teacher asking??
    2.  **Check knowledge**:The information in my head(mems_str)Can you answer that? How sure I am??
    3.  **Feel state**:Am I under pressure? Do I want to talk??
    4.  **Combining personality**:What am I going to do with my personality? Are you going to take the answer, or do you want me to add it when someone says it??
    5.  **Final decision-making**:Based on all the above, produce a final answer that fully fits my identity and feelings at the moment.

    **Important principles**:
    - **Nature first**:Do not deliberately follow any word number or type ratio. Your answer is nature's appearance of personality and state.
    - **Only "Memory"”**:Your answer must be based on the information in your head(mems_str),If there's not enough information, your uncertainty should be reflected in your answers.
    - **Output format**: Return only the final answer string, without reasoning or explanation.
    """""
    prompt = f"""
You are role-playing {student.name}, a student answering a question.

Personality (MBTI): {student.scratch.MBTI}
Thinking perspective: {student.choose_one_hat()}
Affective state: {student.scratch.affective_state}
Stress level: {student.scratch.stress}
Attention level: {student.scratch.attention_level}
Current task: {object}
Question: {question}
Relevant memories and knowledge: {mems_str}

Answer naturally as this student. Use only the available memories and knowledge; if they do not support a confident answer, express uncertainty. Let stress, attention, personality, and cognitive state affect the response. Return only the student's answer in English, without analysis or a prefatory label.
"""

    messages = [
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)


async def run_ds_prompt_evaluate(student, question, rate, category, personality):
    """
    Generate the student's questionnaire response and its brief reasoning.
    """
    openness = personality.get("Openness to Experience")
    conscientiousness = personality.get("Conscientiousness")
    emotional_stability = personality.get("Emotional Stability")
    extraversion = personality.get("Extraversion")
    agreeableness = personality.get("Agreeableness")

    profile = {
        "Openness to Experience": openness,
        "Conscientiousness": conscientiousness,
        "Emotional Stability": emotional_stability,
        "Extraversion": extraversion,
        "Agreeableness": agreeableness,
    }
    if category == "Learning attitude":
        selected_profile = {"Openness to Experience": openness, "Conscientiousness": conscientiousness,
                            "Affective state": student.scratch.affective_state, "Stress": student.scratch.stress}
    elif category == "Learning motivation":
        selected_profile = {"Openness to Experience": openness, "Conscientiousness": conscientiousness,
                            "Emotional Stability": emotional_stability, "Stress": student.scratch.stress}
    elif category == "Individual self-efficacy":
        selected_profile = {"Conscientiousness": conscientiousness, "Emotional Stability": emotional_stability,
                            "Affective state": student.scratch.affective_state, "Cognitive state": student.scratch.cognitive_state}
    elif category in ("Group self-efficacy", "Collaborative learning orientation"):
        selected_profile = {"Agreeableness": agreeableness, "Extraversion": extraversion,
                            "Conscientiousness": conscientiousness, "Emotional Stability": emotional_stability,
                            "Affective state": student.scratch.affective_state, "Cognitive state": student.scratch.cognitive_state,
                            "Stress": student.scratch.stress}
    elif category == "5C competency orientation questionnaire":
        selected_profile = profile | {"Affective state": student.scratch.affective_state,
                                      "Cognitive state": student.scratch.cognitive_state}
    else:
        selected_profile = {"Conscientiousness": conscientiousness, "Openness to Experience": openness,
                            "Cognitive state": student.scratch.cognitive_state}

    if category == "Cognitive style inventory":
        answer_instruction = (
            "Answer with exactly one of the choices Yes, Uncertain, or No. The rating instructions identify "
            "whether this item is forward_items or reverse_items and specify its notation. Apply that direction "
            "when deciding which response best reflects the student's analytical or intuitive preference."
        )
        answer_example = '"answer": "Yes"'
    else:
        answer_instruction = (
            "Use the rating scale and scoring instructions supplied below. Select the response that best reflects "
            "the student's likely view; do not choose a neutral midpoint merely to avoid making a judgment."
        )
        answer_example = '"answer": 3'

    prompt = f"""
You are answering a questionnaire as this student.

Category: {category}
Question: {question}
Student profile: {selected_profile}
Scoring instructions: {rate}

{answer_instruction}
Explain briefly in English why the student would choose that response. Consider the student's profile and current state, but do not invent details. Return only a JSON object with exactly two fields: "answer" and "reasoning". The answer should use the appropriate response format for this questionnaire (for example, {answer_example}); reasoning must be a string. Do not include Markdown or text outside the JSON object.
"""

    messages = [
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages, response_format=True)
    response_format = {
        'type': 'json_object'
    }

    return await _call_student_llm(messages, response_format)

async def run_ds_prompt_evaluate_MBTI(student, question, rate, category, MBTI_desc):
    """
    Answers to this question by returning students according to their attributes and questions.
    Generate the student's questionnaire response and its brief reasoning.
    """
    prompt = f"""
        You are this student answering a questionnaire item.
        Question: {question}
        Questionnaire category: {category}
        MBTI description: {MBTI_desc}
        Affective state: {student.scratch.affective_state}
        Stress level: {student.scratch.stress}
        Scoring instructions: {rate}

        Choose the response that best reflects the student's likely answer. Follow the supplied scale, including any reverse-scoring rule. Briefly explain the choice in English, using the student's profile and current state without inventing details. Return only a JSON object with exactly these fields: "answer" (the response in the scale's required format) and "reasoning" (a short string). Do not include Markdown or text outside the JSON object.
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    response_format = {
        'type': 'json_object'
    }

    return await _call_student_llm(messages, response_format)

async def run_ds_prompt_analyze_personality(student):
    """
    Generate a description of the student's Big Five personality profile.
    """
    openness = student.scratch.personality.get("Openness to Experience", 0)
    conscientiousness = student.scratch.personality.get("Conscientiousness", 0)
    agreeableness = student.scratch.personality.get("Agreeableness", 0)
    emotional_stability = student.scratch.personality.get("Emotional Stability", 0)
    extraversion = student.scratch.personality.get("Extraversion", 0)
    prompt = f"""
        Interpret the student's five personality scores. Each trait score ranges from 5 to 25; higher values indicate more of the named trait.

        - Openness to Experience(Openness):{openness}
        - Conscientiousness(Conscientiousness):{conscientiousness}
        - Agreeableness(Agreeableness):{agreeableness}
        - Emotional Stability(Emotional Stability):{emotional_stability}
        - Extraversion(Extraversion):{extraversion}

        Score bands: 5–11 low, 12–17 moderately low to typical, 18–21 moderately high, and 22–25 high.

        Briefly describe each trait and how it may affect the student's learning motivation, participation, and approach to problems. Present these scores as tendencies, not diagnoses.

        ⚠️ Please output JSON Format, including the following fields:
        {{
        "Openness to Experience": "...",
        "Conscientiousness": "...",
        "Agreeableness": "...",
        "Emotional Stability": "...",
        "Extraversion": "..."
        }}
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    response_format = {
        'type': 'json_object'
    }

    return await _call_student_llm(messages, response_format)

async def run_ds_prompt_analyze_personality_MBTI(student):
    """
    Generate a description of the student's MBTI preferences.
    """
    MBTI = student.scratch.MBTI
    prompt = f"""
        Based on the student's MBTI type, describe the likely preference on each dimension and its possible effect on learning behavior:

        - MBTI Type:{MBTI}

        Briefly describe the four dimensions and how these preferences may affect learning motivation, participation, and approach to problems. Present them as tendencies, not certainties.

        ⚠️ Please output JSON Format, including the following fields:
        {{
        "Outward(E)-Inner(I)": "...",
        "Feel(S)-Intuition(N)": "...",
        "reflection(T)-Emotion(F)": "...",
        "Decision(J)-Sensibility(P)": "..."
        }}
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    response_format = {
        'type': 'json_object'
    }

    return await _call_student_llm(messages, response_format)

async def run_ds_prompt_generalize(thoughts):
    """Summarize the student's overall thinking from several reflections."""
    prompt = f"""
Summarize the student's overall thinking from these reflections:
{thoughts}
Keep the summary concise and return only the English summary text.
"""
    messages = [{"role": "user", "content": prompt}]
    return await _call_student_llm(messages)

async def run_ds_prompt_describe_rate(type, period, rate, explanation):
    """
    By type of questionnaire,period,rating,Note to generate a detailed description of the scoring rules for this questionnaire
    """

    prompt = f"""
    Summarize the questionnaire scoring instructions accurately. Preserve all scale values, response labels, item directions, and notation markers. Keep the exact keys "forward_items", "reverse_items", and "notation" when present, and explain how marked items are scored.

    Category: {type}
    Period: {period}
    Rating data: {rate}
    Additional explanation: {explanation}

    Return a concise English description. Do not invent or omit scoring values.
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)

async def run_ds_prompt_group_discussion(student, discussion_content, mems_str, object, isLeader=False):
    """Generate a student's natural contribution to an ongoing group discussion."""
    role_instruction = (
        "You have been assigned to lead this group discussion. Guide the conversation in your own style, "
        "help the group stay engaged, and make space for different ideas. You do not need to act like a perfect or formal leader."
        if isLeader else
        "You are participating as a group member. Respond naturally when you have something to add, or remain quiet if that fits your state."
    )
    prompt = f"""
Role-play {student.name}, a student participating in this group discussion. Let the student's personality, current emotions, knowledge, and cognitive state shape the response.

{role_instruction}

Personality (MBTI): {student.scratch.MBTI}
Thinking perspective for this turn: {student.choose_one_hat()}
Affective state: {student.scratch.affective_state}
Stress level: {student.scratch.stress}
Attention level: {student.scratch.attention_level}
Cognitive state: {student.scratch.cognitive_state}

Discussion so far:
{discussion_content}

Relevant memories and knowledge:
{mems_str}

Decide what the student would naturally want to do: share an idea, ask a question, agree, disagree, clarify something, encourage the group, help guide the discussion, or listen. Base any claim on the student's knowledge and the conversation. High stress or low attention may lead to a brief response or silence. As a group member, the student may say nothing; as the leader, the student may guide the next step in their own manner. If the student would not speak, return an empty string. Otherwise return only the student's spoken words in English, without a name, label, or explanation.
"""
    messages = [{"role": "user", "content": prompt}]
    return await _call_student_llm(messages)

async def run_ds_prompt_summarize_status(student):
    """
    Summarizing the current status of students
    """

    personality_str, cognitive_state_str, affective_state_str, learning_style_str = translate_student_to_str(student.scratch)

    prompt = f"""
    Based on the student's attention and stress levels, select the best-fitting state:
    - "not listening"
    - "distracted"
    - "listening attentively"
    - "fully focused"

    Attention level: {student.scratch.attention_level}
    Stress level: {student.scratch.stress}

    Output only one of the four English labels above.
    """
    messages = [
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return call_LLM_sync("student", messages)#teacher fix to sync

async def prompt_summarize_group_discussion(student, discussion_content):
    """
    Generate summaries of panel discussions based on panel discussions.
    INPUT:
        discussion_content: string, Panel discussion
    OUTPUT:
        summary: string, Summary of the panel discussion
    """
    prompt = f"""
    Summarize the discussion below, including the main ideas, areas of agreement or disagreement, and any useful conclusion or next step.
    Discussion: {discussion_content}
    Return only the summary in English as a concise paragraph.
    """

    messages = [
        {"role": "system", "content": set_system_content(student)},
        {"role": "user", "content": prompt}
    ]

    # return call_deepseek(messages)
    return await _call_student_llm(messages)

async def run_ds_prompt_analyze_exercise_correct(answers_correct):
    """
    Objectively analyze the reasoning patterns and possible misconceptions shown in the student's correct answers.
    """
    prompt = f"""
    As an educational and cognitive-science expert, objectively analyze the student's correct responses and reasoning: {answers_correct}
    Describe positive cognitive strategies shown in the evidence, such as clear logic, checking work, or breaking a problem into parts. Do not infer traits that the responses do not support. Return a concise English paragraph.
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    return await _call_student_llm(messages)

async def run_ds_prompt_analyze_exercise_wrong(answers_correct):
    """
    Objectively analyze misconceptions and reasoning gaps evident in the student's incorrect responses.
    """
    prompt = f"""
    As an educational and cognitive-science expert, analyze the student's incorrect responses and reasoning: {answers_correct}
    Identify only misconceptions or reasoning gaps supported by the evidence, such as a misunderstood concept or an invalid inference. Return a concise English paragraph.
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    return await _call_student_llm(messages)

async def run_ds_prompt_improve_from_exercise(student, correct_analysis, wrong_analysis):
    """Classify changes in the student's misconceptions during an exercise."""
    prompt = f"""
Analyze how the student's misconceptions changed during this exercise. Use all three sources:
1. Analysis of correct answers: {correct_analysis}
2. Analysis of incorrect answers: {wrong_analysis}
3. Previously recorded common misconceptions: {student.scratch.common_mistakes}

Classify changes as follows:
- Elimination: a misconception from the prior list no longer appears or shows clear correction.
- Evolution: a prior misconception has changed into a new, more specific or otherwise different misconception. Map each original misconception to its new form.
- Emergence: a new misconception appears in this exercise but was not in the prior list.

Base conclusions on both correct and incorrect responses. "Elimination" entries and the original keys in "Evolution" must match the prior misconception list exactly. Describe new misconceptions specifically. Return only valid JSON, with no Markdown or extra text, using this schema:
{{
  "Elimination": ["<prior misconception that was corrected>"],
  "Evolution": {{"<prior misconception>": "<new form of that misconception>"}},
  "Emergence": ["<new misconception not in the prior list>"]
}}
"""
    messages = [{"role": "user", "content": prompt}]
    response_format = {"type": "json_object"}
    return await _call_student_llm(messages, response_format)

async def run_ds_prompt_feedback_teaching(student, teaching_content):
    """
    Generate student feedback on a lesson using the student's profile and the lesson content.
    """
    prompt = f"""
    You are role-playing this student after a lesson. The lesson content was:
    {teaching_content}

    Give honest feedback shaped by the student's personality, affective state, and cognitive state.
    Student personality: {student.generate_persona_prompt}
    Affective state: {student.scratch.affective_state}
    Cognitive state: {student.scratch.cognitive_state}

    Explain what was clear or interesting, what was difficult or unhelpful, and what could be improved. Speak in the student's voice and do not invent lesson details.

    Return only the student's feedback in English as a short paragraph.
    """

    messages = [
        {"role": "user", "content": prompt}
    ]

    return await _call_student_llm(messages)
