import sys
sys.path.append("../../")


from student.cognitive_module.student import *
from student.cognitive_module.scratch import *
from student.cognitive_module.memory import *
from student.prompt.run_ds_prompt import *
from util.BroadcastSys import *
from util.Recorder import *
from student.retrieve import *
from util.BroadcastMessage import *

# TODO: Now the question is, is it all the same that the teacher gives the order and the conversation?。
# 1.
# If it's separate, then give the order. I'll put it in the sensory phase event It's an event, and it's gonna be there chat_with Add"teacher"。
# But this stage should not be able to answer. Because the teacher didn't ask questions execute Should've done nothing, even now`chat_with`Yes"teacher"。
# But here chat_buffer It should be empty chat_with Object）
# Then in the next round, the teacher asks questions, and I'll put them in the sensory phase chat_buffer Medium。
# At this point, chat_with It's already there"teacher"And then chat_buffer When there's something, I can answer。
# 2.
# If it's at the same time, the teacher gives instructions and questions, and I put them in the sensory phase event Events and chat_buffer Medium。
# At this point, chat_with It's already there"teacher"And then chat_buffer When there's something, I can answer

# So it's okay because of mine move Function is a running through all current information。
# Just chat_buffer There's something I can answer。
async def execute(student, object, retrieved=None, info=None):
    """
    Execute the action for the current list of recipients.
    The list can have three forms:
    1. None
    2. ["teacher"]
    3. ["group_member1", "group_member2", ...]
    INPUT:
        student: student object
        object: list of str, current recipient list
    OUTPUT:
        None
    """
    if object is None:
        # If the object list is empty, nothing needs to be done
        return None

    if student.scratch.chat_buffer is None:
        # If chat_buffer There's nothing to do
        return None

    print(f"{student.name} is executing an action.")

    if object == ["teacher"]:
        # And now we need to chat_buffer Get the teacher's questions and answer them
        # chat_buffer There may be a teacher's question, his own answer。
        # We search the last one. If it's a teacher's question, answer, or don't answer
        # But if it's your answer, then it's your decision）
        # If the answer of the other person is yes, it will be settled directly）
        last_chat = student.scratch.chat_buffer[-1]
        # First of all, we'll get the entire history of the conversation

        if last_chat.s == student.teacher_name:
            # If the last question is a teacher's question, answer it
            # First, to retrieve the relevant memories
            print(f"{student.name} Got a question from the teacher: {last_chat.content}")
            relevant_mem = await further_retrieve(student, [last_chat.content])
            mems = [i.embedding_key for i in relevant_mem[last_chat.content]]
            mems_str = "\n".join(mems)
            response = await run_ds_prompt_answer_question(student, object, last_chat.content, mems_str)

            msg = BroadcastMessage(
                current_time=student.scratch.current_time,
                message_type = MessageType.CLASS,
                active_event = "answer",
                speaker = student.name,
                content = response
            )
            """content = {"message_type": "class",
                       "active_event": "response_question",
                       "speaker": student.name,
                       "content": response,
                       "current_time": student.scratch.current_time}"""

            student.broadcast_sys.publish_sync("teacher", msg)
            print(f"{student.name} Answer!: {response}")
            # Let's assume it's only a round, so it's empty
            student.scratch.chat_buffer.clear()
            student.scratch.chat_with.clear()
    elif info.get("active_event") == "group_discussion_start" or info.get("active_event") == "group_discussion" and info.get("receiver") == student.name:
        # Panel discussion if there are others in the object list
        # Panel discussions based on the contents of the current dialogue box

        print(f"{student.name} Panel discussion")
        last_chat = student.scratch.chat_buffer[-1]
        try:
                relevant_mem = await further_retrieve(student, [last_chat.content])

                if relevant_mem and last_chat.content in relevant_mem:
                    mems = [i.embedding_key for i in relevant_mem[last_chat.content]]
                    mems_str = "\n".join(mems) if mems else ""
                else:
                    mems_str = ""

        except Exception as e:
            print(f"{student.name}Error Retrieving Memory: {e}")
            mems_str = ""
        discussion_content = format_chat_buffer(student.scratch.chat_buffer)

        try:
            response = await run_ds_prompt_group_discussion(student, discussion_content, mems_str, object, isLeader=student.scratch.isLeader)
        except json.JSONDecodeError as e:
            response = ""
        except Exception as e:
            print(f"{student.name}Error running panel discussion hint: {e}")
            response = ""

        s = student.name if student.name else "unknown"
        p = "talks with"
        # o = f"students in group {student.scratch.group}"
        o = object[0] if object[0] else "unknown"

        keys = await run_ds_prompt_chat_keywords(response)
        # Split string into keyword list
        if isinstance(keys, str):
            keys_list = [key.strip() for key in keys.split(',') if key.strip()]
        else:
            keys_list = keys if isinstance(keys, list) else [keys]
        keywords = ["group_discussion", s, p, o] + keys_list # Keywords are type of event, sender, verbs, students involved and keywords for summation
        embedding_pair = (response, await get_local_embedding(response))
        importance = int(await run_ds_prompt_importance_chat(student, response))
        student.scratch.accumulate_importance(importance)
        node = student.mem.add_chat(student.scratch.current_time, response, keywords, importance, embedding_pair, s = s, p = p, o = o)
        student.scratch.chat_buffer.append(node)
        student.scratch.chat_with.append(s)  # Add Sender to Chat List

        msg = BroadcastMessage(
            current_time=student.scratch.current_time,
            message_type = MessageType.CLASS,
            active_event = "group_discussion",
            speaker = student.name,
            content = response
        )
        student.broadcast_sys.publish_sync(object[0], msg)
        # student.broadcast_sys.publish("teacher", msg)

        msg2 = BroadcastMessage(
            current_time=student.scratch.current_time,
            message_type = MessageType.CLASS,
            active_event = "group_discussion_content",
            speaker = student.name,
            content = response
        )
        group = "group" + str(student.scratch.group)
        student.broadcast_sys.publish_sync(group, msg2)
        print(f"{student.name} Panel discussions were held: {response}")
