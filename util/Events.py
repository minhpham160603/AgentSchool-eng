from datetime import datetime, timedelta

class Event:
    _id_counter = -1  # For recording current ID Counter

    def __init__(self, event_type: str, event_name: str, start_time: datetime, end_time: datetime, parent_event_id: str = None):
        """
        Initialize Event Object
        ARGS:
            event_type: Event type
            event_name: Event Name
            start_time: Event Start Time(datetime Object)
            end_time: End of Event(datetime Object)
            parent_event_id: Parent Events ID
        type and name The difference, for example:group_discussion and math_class Yes type For class
        """
        Event._id_counter += 1  # id Automatic

        self.id = Event._id_counter
        self.type = event_type
        self.name = event_name
        self.start = start_time
        self.end = end_time
        self.parent_event_id = parent_event_id

    def is_conflict(self, other_event) -> bool:
        """Check the time conflict with another event"""
        if self.parent_event_id ==  other_event.id:
            return False
        return (self.start < other_event.end) and (other_event.start < self.end)

FREE_TIME_EVENT = Event(
    event_type="free_time",
    event_name="Free time",
    start_time=None,
    end_time=None
)