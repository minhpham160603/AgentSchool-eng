from typing import Dict, Set, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum


class MessageType(Enum):
    """Can not open message"""
    EVENT_CHANGE = "event_change"
    COMMAND = "command"
    CLASS = "class"
    ACTIVITY = "activity"
    NEW_DAY = "new_day"

@dataclass
class BroadcastMessage:
    """Radio Message Class"""
    current_time: Optional[datetime] = None
    message_type: MessageType = None
    active_event: str = ""
    event_id: Optional[int] = None
    speaker: str = ""
    content: str = ""


    def to_dict(self) -> Dict:
        """Convert to log compatible dictionary format"""
        return asdict(self)