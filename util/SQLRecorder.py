import json
import datetime
import asyncio
import asyncpg
from typing import List, Dict, Optional, Any
from enum import Enum

# Sequenced Functions (original))
def default_serializer(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, type.MappingProxyType):
        return dict(obj)
    elif isinstance(obj, Enum):
        return obj.value
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    elif hasattr(obj, 'to_dict') and callable(obj.to_dict):
        return obj.to_dict()
    raise TypeError(f"Unable to sequence type: {type(obj)}")

def make_json_serializable(data):
    """Recursive processing of data to make it possible to JSON Sequenced"""
    if isinstance(data, dict):
        return {k: make_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [make_json_serializable(item) for item in data]
    # Fixed here: The original code is data.to_to_dict,For to_dict
    elif hasattr(data, 'to_dict') and callable(data.to_dict):
        return make_json_serializable(data.to_dict())
    else:
        return data


class Recorder:
    def __init__(
        self,
        dsn: str,
        session_id: str,
        course_id: str,
        frame_id: int = 0,
        table_name: str = "simulation_logs",
        batch_size: int = 100,
        flush_interval: float = 5.0
    ):
        """
        Initialization log recorder
        :param dsn: Database Connection String
        :param session_id: Session ID(It must be entered when initializing)
        :param course_id: Courses ID(It must be entered when initializing)
        :param frame_id: Current Frame ID(Optional, Default 0)
        :param table_name: Data Table Name
        :param batch_size: Batch writing threshold
        :param flush_interval: Automatically refresh interval (seconds))
        """
        self.dsn = dsn
        self.table_name = table_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Context information entered at initialization
        self._session_id = session_id
        self._course_id = course_id
        self._frame_id = frame_id

        # Buffer zone and connectivity
        self.buffer: List[tuple] = []
        self.pool: Optional[asyncpg.Pool] = None
        self.flush_task: Optional[asyncio.Task] = None

    async def init(self):
        """Initialize database connect pool and backstage refresh jobs"""
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=10)
        self.flush_task = asyncio.create_task(self._auto_flush_loop())

    async def close(self):
        """Close resources: cancel time assignments, refresh remaining data, close connect pool"""
        if self.flush_task:
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_buffer()  # Ensure that final data are written
        if self.pool:
            await self.pool.close()

    # setter
    def set_session_id(self, session_id: str):
        self._session_id = session_id
        return self  # Support chain call

    def set_course_id(self, course_id: str):
        self._course_id = course_id
        return self

    def set_frame_id(self, frame_id: int):
        self._frame_id = frame_id
        return self

    async def student_log(self, details: Dict[str, Any], log_time: Optional[datetime.datetime] = None):
        """
        Record student status log
        """
        name = details.get("name")
        stress = details.get("stress")
        attention = details.get("attention")
        absorbed = details.get("absorbed")
        learned = details.get("learned")
        reflection = details.get("reflection", {})

        # Sequenced reflection Yes JSON String
        reflection_str = json.dumps(
            make_json_serializable(reflection),
            ensure_ascii=False,
            default=default_serializer
        )

        record = (
            log_time or datetime.datetime.now(),
            self._session_id,
            self._course_id,
            self._frame_id,
            "student",          # event_type
            name,               # character
            None,               # action
            None,               # speaker
            None,               # receiver
            None,               # message_type
            None,               # active_event
            None,               # content
            stress,
            attention,
            absorbed,
            learned,
            reflection_str
        )
        self.buffer.append(record)
        if len(self.buffer) >= self.batch_size:
            await self._flush_buffer()

    async def action_log(self, details: Dict[str, Any], log_time: Optional[datetime.datetime] = None):
        """
        Record action logs listen, raise_hand)
        """
        character = details.get("student")  # Note: The input is "student": "StudentA"
        action = details.get("action")

        record = (
            log_time or datetime.datetime.now(),
            self._session_id,
            self._course_id,
            self._frame_id,
            "action",           # event_type
            character,          # character
            action,             # action
            None,               # speaker
            None,               # receiver
            None,               # message_type
            None,               # active_event
            None,               # content
            None,               # stress
            None,               # attention
            None,               # absorbed
            None,               # learned
            None,               # reflection
        )
        self.buffer.append(record)
        if len(self.buffer) >= self.batch_size:
            await self._flush_buffer()

    async def broadcast_log(self, details: Dict[str, Any], log_time: Optional[datetime.datetime] = None):
        """
        Recording of broadcast news logs (e.g., statements, system announcements))
        """
        speaker = details.get("speaker")
        receiver = details.get("receiver")
        message_type = details.get("message_type")
        active_event = details.get("active_event")
        content = details.get("content")

        # Inference character:Priority speaker
        character = speaker

        record = (
            log_time or datetime.datetime.now(),
            self._session_id,
            self._course_id,
            self._frame_id,
            "broadcast",        # event_type
            character,          # character
            None,               # action
            speaker,            # speaker
            receiver,           # receiver
            message_type,       # message_type
            active_event,       # active_event
            content,            # content
            None,               # stress
            None,               # attention
            None,               # absorbed
            None,               # learned
            None,               # reflection
        )
        self.buffer.append(record)
        if len(self.buffer) >= self.batch_size:
            await self._flush_buffer()

    #  Batch Write and Time Refresh
    async def _flush_buffer(self):
        if not self.buffer:
            return

        columns = [
            'log_time', 'session_id', 'course_id', 'frame_id', 'event_type',
            'name', 'action', 'speaker', 'receiver', 'message_type',
            'active_event', 'content', 'stress', 'attention', 'absorbed',
            'learned', 'reflection'
        ]

        try:
            async with self.pool.acquire() as conn:
                await conn.copy_records_to_table(
                    self.table_name,
                    records=self.buffer,
                    columns=columns
                )
            self.buffer.clear()
        except Exception as e:
            print(f"Batch writing failed: {e}")

    async def _auto_flush_loop(self):
        while True:
            await asyncio.sleep(self.flush_interval)
            if self.buffer:
                await self._flush_buffer()