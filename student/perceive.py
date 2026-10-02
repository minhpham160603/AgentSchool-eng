import json
import demjson3
import sys
sys.path.append("../../")
import re

from student.cognitive_module.memory import *
from student.knowledge_graph import kg
from student.cognitive_module.scratch import *
from student.cognitive_module.student import *
from student.prompt.run_ds_prompt import *
from student.retrieve import *
from util.BroadcastMessage import *
from util.BroadcastSys import *


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks from LLM outputs."""
    try:
        return re.sub(r"(?is)<think>.*?</think>", "", text)
    except Exception:
        return text

def _parse_int_0_10(text: str, default: int = 1) -> int:
    """Parse first integer 0..10 from messy text (after stripping <think> blocks)."""
    try:
        cleaned = _strip_think(str(text)).strip()
        m = re.search(r"(?:^|\D)(10|[0-9])(?:\D|$)", cleaned)
        return int(m.group(1)) if m else default
    except Exception:
        return default

def safe_json_decode(json_str, fallback=None):
    """
    Clear JSON Parsing functions, using demjson3 Providing better tolerance for errors
    """
    if not json_str or json_str.strip() == "":
        print(f"WARNING: Try to parse empty strings")
        return fallback

    # Clear String, Remove markdown Block tags and redundant blanks
    cleaned_str = json_str.strip()

    # Remove markdown Block Tags
    if cleaned_str.startswith('```json'):
        cleaned_str = cleaned_str[7:]  # Remove ```json
    elif cleaned_str.startswith('```'):
        cleaned_str = cleaned_str[3:]   # Remove ```

    if cleaned_str.endswith('```'):
        cleaned_str = cleaned_str[:-3]  # Remove the end ```

    cleaned_str = cleaned_str.strip()

    # Replace the Chinese Punctuation with the English Punctuation
    cleaned_str = cleaned_str.replace('"', '"').replace('"', '"')  # Chinese Double Quote
    cleaned_str = cleaned_str.replace(''', "'").replace(''', "'")  # Chinese single quotation marks
    cleaned_str = cleaned_str.replace('，', ',')  # Chinese commas
    cleaned_str = cleaned_str.replace('：', ':')  # Chinese colon

    # If empty string after cleanup, return fallback
    if not cleaned_str:
        print(f"WARNING: Empty string after cleanup")
        return fallback

    try:
        # First try using standards json
        return json.loads(cleaned_str)
    except json.JSONDecodeError:
        try:
            # If the standard json Failed, use demjson3
            print(f"WARNING: Standard JSON Parsing failed, trying to use demjson3")
            return demjson3.decode(cleaned_str)
        except Exception as e:
            print(f"ERROR: demjson3 Parsing failed: {e}")
            print(f"Original String: '{json_str}'")
            print(f"Cleanup String: '{cleaned_str}'")
            return fallback


async def perceive(student, information, sender=None, receiver=None, current_time = None, info_type = None):
    """
    Process incoming information according to the student's attention and stress,
    then store the resulting concept node in memory. A call normally handles one
    sender, though a group discussion may involve several participants.
    INPUT:
        student: student object
        information: str, content to process
        sender: str, sender's name
        receiver: str, recipient's name (optional)
        current_time: datetime, current time
        info_type: str, optional event type
    OUTPUT:
        node: the resulting concept node
        absorbed: str, information retained by the student
        learned: str, knowledge learned by the student
    """
        # If knowledge，info Like
        # {"message_type": "class",
        #  "active_event": "lecture",
        #  "speaker": self.name,
        #  "content": self.sections[self.current_section_turn]}
        # If event，info Like
        # Questions and answers：
        #   "message_type": "class",
        #    "active_event": "ask_question",
        #    "speaker": self.name,
        #    "content": self.q_a[0]
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

    if information is None or information == "":
        return None, None, None

    # Let's see what kind of information we have：event/chat/knowledge
    # info_type = run_ds_prompt_judge_type(information)
    print(f"{student.name}In Perception Information：{information}（Event type is{info_type}）")
    # print(f"Information Type: {info_type}")
    # Not now LLM The type of event is judged by the information that comes in
    # print(f"Information content: {information}")
    node = None
    absorbed_info = None
    learned = None
    # 1. If event Type, which requires judgement event and summarise this event Themes as keywords
    # Because the teacher is right there event The definition doesn't seem very clear, because he could send a question directly。
    # So I need to judge the type of event with the parameters it gives me
    if info_type == "event":
        event_summary = await run_ds_prompt_summarize_event(information)
        json_event = safe_json_decode(_strip_think(event_summary), {})
        if not json_event:
            print(f"ERROR: Unable to parse event summary, skip processing")
            return None, None, None
        content = json_event.get("content", "")
        event_type = json_event.get("event_type", "unknown")
        theme = json_event.get("keywords", [])
        if isinstance(theme, str):
            theme = [theme]
        keywords = [event_type] + theme
        importance_text = await run_ds_prompt_importance_event(student, content)
        importance = _parse_int_0_10(importance_text)
        student.scratch.accumulate_importance(importance)
        embedding_pair = (content, await get_local_embedding(content))
        node = student.mem.add_event(student.scratch.current_time, content, keywords, importance,
                              embedding_pair, event_type, theme)
        # --- Knowledge mapping: passive learning ---
        """if theme:
            kg.batch_passive_learn(
                student.name,
                [t for t in theme if isinstance(t, str) and t.strip()],
                base_strength=0.03,
                config_kg=student.knowledge_points_of_the_grade,
                importance=importance
            )"""
    elif info_type == "chat":
        # TODO:
        # 2. If chat type, directly use information content as keyword
        # And to store it
        # student.scratch.chat_buffer.append(0, (current_time, sender, information))
        absorb_rate = student.scratch.attention_level * (1 - student.scratch.stress)
        absorbed_info = await run_ds_prompt_absorb_info(student, information, absorb_rate)
        content = absorbed_info
        s = sender if sender else "unknown"
        p = "chat with"
        # Ping will be determined according to the current type of event，
        o = student.name
        current_time = current_time if current_time else student.scratch.current_time
        importance_text = await run_ds_prompt_importance_chat(student, absorbed_info)
        importance = _parse_int_0_10(importance_text)
        student.scratch.accumulate_importance(importance)
        keywords = [s, p, o]  # Keywords are senders, verbs and student names
        embedding_pair = (absorbed_info, await get_local_embedding(absorbed_info))
        node = student.mem.add_chat(current_time, content, keywords, importance, embedding_pair, s = s, p = p, o = o)
        # --- Knowledge mapping: treat chat participants and keywords as light conceptual labels (optional filter length)）---
        # candidate_concepts = [k for k in keywords if len(k) <= 20]
        # if candidate_concepts:
            # kg.batch_passive_learn(student.name, candidate_concepts, base_strength=0.01, importance=importance)
        student.scratch.chat_buffer.append(node)
        student.scratch.chat_with.append(s)
    # elif info_type == "knowledge":
    elif info_type == "lecture":
        # 3. If knowledge Type, in which the student combines the information that he/she absorbs with the current information，
        # Summarize their current learning points and put them in their memory
        # Take some information based on student pressure and attention
        attention_level = student.scratch.attention_level
        stress_level = student.scratch.stress
        if attention_level > 0.7 and stress_level < 0.3:
            absorption_desc = "You listened carefully and retained nearly all of the teacher's key details."
        elif attention_level < 0.3 or stress_level > 0.7:
            absorption_desc = "You were somewhat distracted or nervous, so you missed many details and retained only a few concepts and keywords."
        else:
            absorption_desc = "You mostly kept up with the teacher, but may not have understood the more complex ideas."

        # Retrieve the knowledge of memory。
        # Attention：further_retrieve You need a string list, so you want to information Pack in List
        retrieved_mem = await further_retrieve(
            student, [information], n_count=3
        )


        knowledge_understanding_str = await run_ds_prompt_generate_understanding(
            student, information, absorption_desc, student.knowledge_points_of_the_grade, retrieved_mem
        )

        json_understanding = safe_json_decode(_strip_think(knowledge_understanding_str), {})
        if not json_understanding:
            print("ERROR: Could not parse the student's understanding; skipping this item.")
            return

        content = json_understanding.get("understanding_content", "") # This is what students think they learned
        learned = content
        # misconceptions = json_understanding.get("misconceptions", []) # 【Where the students are wrong
        # lingering_questions = json_understanding.get("lingering_questions", []) # 【New students still have questions
        knowledge_tag = json_understanding.get("knowledge_tag", [])
        importance = json_understanding.get("importance", 1)

        # Generates a false understanding/Myths
        misconceptions = await run_ds_prompt_generate_misconceptions(
            student, learned
        )


        # Storage of core knowledge (students' understanding version)）
        if content:
            student.scratch.accumulate_importance(importance)
            keywords = knowledge_tag
            embedding_pair = (content, await get_local_embedding(content))
            node = student.mem.add_knowledge(student.scratch.current_time, content, keywords, importance, embedding_pair, knowledge_tag, misconceptions=misconceptions)
            # --- Knowledge mapping: teaching knowledge directly enhances matching labels ---
            if knowledge_tag:
                kp_ids = kg.get_batch_id_by_names(knowledge_tag, student.knowledge_points_of_the_grade)
                kg.batch_passive_learn(
                    student.name,
                    kp_ids,
                    base_strength=0.05,
                    config_kg=student.knowledge_points_of_the_grade,
                    misconceptions=misconceptions,
                    importance=importance
                )
            print(f"{student.name}Understanding: {content}")

        # To store false perceptions and questions as a special memory
        # if misconceptions:
            # print(f"{student.name} Misperception: {misconceptions}")
            # student.mem.add_thought(..., f"I was right'{knowledge_tag}'I think it's wrong'{misconceptions}'", ...)
        # if lingering_questions:
            # print(f"{student.name} Question: {lingering_questions}")
        """absorb_rate = student.scratch.attention_level * (1 - student.scratch.stress)
        absorbed_info = await run_ds_prompt_absorb_info(student, information, absorb_rate)
        # Store this memory
        importance_text = await run_ds_prompt_importance_thought(student, absorbed_info)
        importance = _parse_int_0_10(importance_text)
        student.scratch.accumulate_importance(importance)
        keywords = await run_ds_prompt_thought_keywords(absorbed_info)
        embedding_pair = (absorbed_info, await get_local_embedding(absorbed_info))
        student.mem.add_thought(student.scratch.current_time, absorbed_info, keywords, importance,
                                embedding_pair)
        # Output information absorbed by this student
        print(f"{student.name} Absorbed information: {absorbed_info}")

        # Simulation of the knowledge
        # I think he's only going to draw up one knowledge point at a time）
        knowledge_summary_str = await run_ds_prompt_summarize_knowledge(student, absorbed_info, information)
        # print(f"DEBUG: Raw output from run_ds_prompt_summarize_knowledge: '{knowledge_summary_str}'") # Print original output

        json_knowledge = safe_json_decode(knowledge_summary_str, {})
        if not json_knowledge:
            print(f"ERROR: Could not parse summary of knowledge, skip processing")
            return None, None, None

        content = json_knowledge.get("content", "")
        learned = content
        knowledge_tag = json_knowledge.get("knowledge_tag", [])
        importance = json_knowledge.get("importance", 1)
        if isinstance(importance, str):
            try:
                importance = int(importance)
            except ValueError:
                importance = 1
        student.scratch.accumulate_importance(importance)
        keywords = knowledge_tag
        embedding_pair = (content, await get_local_embedding(content))
        node = student.mem.add_knowledge(student.scratch.current_time, content, keywords, importance, embedding_pair, knowledge_tag)
        # Export the knowledge the student has learned
        print(f"{student.name} Knowledge gained: {content}")"""
    elif info_type == "ask_question":
        # 4. If ask_question Type of problem that needs to be placed on the student scratch Medium
        # This belongs first event，It's also a part of it chat
        event_summary = await run_ds_prompt_summarize_event(information)
        json_event = safe_json_decode(_strip_think(event_summary), {})
        if not json_event:
            print(f"ERROR: Unable to parse summary of events, skip processing")
            return None, None, None

        event_content = json_event.get("content", "")
        # print(f"Event content: {event_content}")
        # event_type = json_event["event_type"]
        event_theme = json_event.get("keywords", [])
        if isinstance(event_theme, str):
            event_theme = [event_theme]
        event_content = f"{sender}Ask{student.name}About{event_theme}Issues"
        print(f"Event content: {event_content}")

        importance_text = await run_ds_prompt_importance_event(student, event_content)
        importance = _parse_int_0_10(importance_text)
        student.scratch.accumulate_importance(importance)
        embedding_pair = (event_content, await get_local_embedding(event_content))
        s = sender if sender else "unknown"
        p = "asks"
        o = student.name
        keywords = ["ask_question"] + event_theme + [s, p, o]  # Keywords are type of event, theme, sender, verb and student name
        node = student.mem.add_event(student.scratch.current_time, event_content, keywords, importance,
                              embedding_pair, info_type, event_theme, s=s, p=p, o=o)
        # --- Knowledge mapping: minor reinforcement of subject-matter concepts ---
        """if event_theme:
            kg.batch_passive_learn(
                student.name,
                [t for t in event_theme if isinstance(t, str) and t.strip()],
                base_strength=0.02,
                config_kg=student.knowledge_points_of_the_grade,
                importance=importance
            )"""

        # And then you put it in chat
        absorb_rate = student.scratch.attention_level * (1 - student.scratch.stress)
        absorbed_info = await run_ds_prompt_absorb_info(student, information, absorb_rate)
        # chat_content = absorbed_info
        chat_content = information
        print(f"Contents of the query：{chat_content}")
        current_time = current_time if current_time else student.scratch.current_time
        importance_text = await run_ds_prompt_importance_chat(student, absorbed_info)
        importance = _parse_int_0_10(importance_text)
        student.scratch.accumulate_importance(importance)
        # To extract the knowledge point of the subject
        knowledge_tags = await run_ds_prompt_extract_knowledge_tag(absorbed_info, student.knowledge_points_of_the_grade)
        # Ensure knowledge_tags is the list
        if not isinstance(knowledge_tags, list):
            knowledge_tags = []
        keywords = knowledge_tags + [s, p, o]  # Key words are knowledge points, senders, verbs and student names
        embedding_pair = (absorbed_info, await get_local_embedding(absorbed_info))
        node = student.mem.add_chat(current_time, chat_content, keywords, importance, embedding_pair, s = s, p = p, o = o, knowledge_tag=knowledge_tags)
        if knowledge_tags:
            kp_ids = kg.get_batch_id_by_names(knowledge_tags, student.knowledge_points_of_the_grade)
            kg.batch_passive_learn(
                student.name,
                kp_ids,
                base_strength=0.025,
                config_kg=student.knowledge_points_of_the_grade,
                importance=importance
            )
        # Current chat It's for students scratch Medium
        student.scratch.chat_buffer.append(node)
        student.scratch.chat_with.append(s)  # Add Sender to Chat List
    elif info_type == "group_discussion_start" or info_type == "group_discussion" and receiver == student.name:
        # Panel discussions, accepted only when the subject is for himself
        # For the time being, I will speak in the same order

        # If so, update team
        if info_type == "group_discussion_start":
            student.update_group(student.scratch.group)

        # Ignore a discussion message if a group-discussion-end event is already queued.
        if any(student.infos[i].get("active_event") == "group_discussion_end" for i in range(len(student.infos))):
            print(f"{student.name}Ignore information on panel discussions as there is already an end-of-group discussion。")
            return None, None, None

        # To add the contents of the current statement scratch In the buffer zone
        s = sender if sender else "unknown"
        p = "talks with"
        # o = f"students in group {student.scratch.group}"
        o = receiver if receiver else "unknown"

        keys = await run_ds_prompt_chat_keywords(information)
        # Split string into keyword list
        if isinstance(keys, str):
            keys_list = [key.strip() for key in keys.split(',') if key.strip()]
        else:
            keys_list = keys if isinstance(keys, list) else [keys]
        keywords = ["group_discussion", s, p, o] + keys_list # Keywords are type of event, sender, verbs, students involved and keywords for summation
        embedding_pair = (information, await get_local_embedding(information))
        importance_text = await run_ds_prompt_importance_chat(student, information)
        importance = _parse_int_0_10(importance_text)
        student.scratch.accumulate_importance(importance)
        node = student.mem.add_chat(student.scratch.current_time, information, keywords, importance, embedding_pair, s = s, p = p, o = o)
        # --- Knowledge mapping: light reinforcement of discussion keywords ---
        # discussion_concepts = [k for k in keys_list if isinstance(k, str)]
        # if discussion_concepts:
            # kg.batch_passive_learn(student.name, discussion_concepts, base_strength=0.015, importance=importance)
        student.scratch.chat_buffer.append(node)
        student.scratch.chat_with.append(s)  # Add Sender to Chat List

        # Output of the panel discussion
        print(f"History of the current panel discussion：{format_chat_buffer(student.scratch.chat_buffer)}")
    elif info_type == "group_discussion_end":
        # Conclusion of the panel discussion
        if student.scratch.isLeader:
            chats = format_chat_buffer(student.scratch.chat_buffer)
            results = await prompt_summarize_group_discussion(student, chats)
            group = "group" + str(student.get_group())
            msg = BroadcastMessage(
                current_time=student.scratch.current_time,
                message_type = MessageType.CLASS,
                active_event = "group_discussion",
                speaker = group,
                content = results
            )
            student.broadcast_sys.publish_sync("teacher", msg)
            print(f"Outcome of the panel discussion: {chats}")
            print(f"{student.name}End of panel discussion, Chair' s summary: {results}")
            student.scratch.isLeader = False  # I'm not the leader anymore

        student.scratch.chat_buffer.clear()  # Empty chat buffers for panel discussions
        student.scratch.chat_with.clear()  # Chat list to empty panel discussion


        """elif info_type == "feedback":
            # Feedback from teachers
            # 1. Generate thought
            absorb_rate = student.scratch.attention_level * (1 - student.scratch.stress)
            absorbed_info = run_ds_prompt_absorb_info(student, information, absorb_rate)
            # Store this memory
            importance = int(run_ds_prompt_importance_thought(student, absorbed_info))
            student.scratch.accumulate_importance(importance)
            keywords = run_ds_prompt_thought_keywords(absorbed_info)
            embedding_pair = (absorbed_info, get_local_embedding(absorbed_info))
            student.mem.add_thought(student.scratch.current_time, absorbed_info, keywords, importance,
                                    embedding_pair)"""
        # 2. Changed students scratch Status
    elif info_type == "group_discussion_content":
        # If sender As with current student, skip processing this information
        if sender == student.name:
            return None, None, None

        # Skip if the same information exists in the current student information list
        if any(student.scratch.chat_buffer[i].content == information for i in range(len(student.scratch.chat_buffer))):
            return None, None, None

        # This message is used to synchronize and update information on panel discussions
        s = sender if sender else "unknown"
        p = "talks with"
        # o = f"students in group {student.scratch.group}"
        o = receiver if receiver else "unknown"

        keys = await run_ds_prompt_chat_keywords(information)
        # Split string into keyword list
        if isinstance(keys, str):
            keys_list = [key.strip() for key in keys.split(',') if key.strip()]
        else:
            keys_list = keys if isinstance(keys, list) else [keys]
        keywords = ["group_discussion", s, p, o] + keys_list # Keywords are type of event, sender, verbs, students involved and keywords for summation
        embedding_pair = (information, await get_local_embedding(information))
        importance_text = await run_ds_prompt_importance_chat(student, information)
        importance = _parse_int_0_10(importance_text)
        student.scratch.accumulate_importance(importance)
        node = student.mem.add_chat(student.scratch.current_time, information, keywords, importance, embedding_pair, s = s, p = p, o = o)
        # sync_concepts = [k for k in keys_list if isinstance(k, str)]
        # if sync_concepts:
            # kg.batch_passive_learn(student.name, sync_concepts, base_strength=0.01, importance=importance)
        student.scratch.chat_buffer.append(node)
        student.scratch.chat_with.append(s)  # Add Sender to Chat List
    elif info_type == "taught":
        feedback = await run_ds_prompt_feedback_teaching(student, information)
        msg = BroadcastMessage(
                current_time=student.scratch.current_time,
                message_type = MessageType.CLASS,
                active_event = "feedback",
                speaker = student.name,
                content = feedback
            )
        student.broadcast_sys.publish_sync("teacher", msg)
        print(f"{student.name}Feedback on teaching: {feedback}")
    elif info_type == "new_day":
        # New day, update student time
        student.scratch.current_time = current_time if current_time else student.scratch.current_time

    return node, absorbed_info, learned

