import asyncio
from util.SQLRecorder import Recorder

async def demo():
    recorder = Recorder(
        dsn="postgresql://postgres:qwe123@localhost:5432/simulation_db",
        session_id="sess_001",
        course_id="course_math_101",
        frame_id=0
    )
    await recorder.init()

    # 1. Student log
    await recorder.student_log({
        "name": "StudentC",
        "stress": 0.0914601073985886,
        "attention": 0.25320364773599846,
        "absorbed": "",
        "learned": "",
        "reflection": {}
    })

    # 2. Action log
    await recorder.action_log({
        "student": "StudentA",
        "action": "listen"
    })

    # 3. Broadcast log
    await recorder.broadcast_log({
        "current_time": "2025-09-01T08:01:00",
        "message_type": "class",
        "active_event": "group_discussion",
        "event_id": None,
        "speaker": "StudentC",
        "content": "Let's start with the first count, for example-3,It should be negative.",
        "receiver": "StudentA"
    })

    await asyncio.sleep(0.1)
    await recorder.close()
    print("✅ All logs completed")

if __name__ == "__main__":
    asyncio.run(demo())