import json
from enum import Enum
from datetime import datetime, timedelta, time as dt_time
from typing import List
from util.BroadcastMessage import BroadcastMessage
from util.BroadcastMessage import MessageType
from util.BroadcastSys import BroadcastSys
from util.Events import Event
from util.Events import FREE_TIME_EVENT


class ClassEndAction(Enum):
    OVERTIME = 0
    CLASS_OVER = 1


class TimeManager:
    def __init__(self, daily_schedule_path, broadcast_system: BroadcastSys, day_start_time):
        self.current_time = None
        self.events: List[Event] = []
        self.last_active_event = None
        self.broadcast_system = broadcast_system
        self.day_start_time = day_start_time
        self.path = daily_schedule_path
        self.round_time = 60  # Default value
        self.total_courses = None  # How many sessions do you have to simulate?
        self._load_schedule()  # Load schedule on initialization

    def _load_schedule(self):
        """From JSON Loading the calendar and according to which start_date Set Current Time"""
        self.events.clear()
        try:
            with open(self.path, "r") as f:
                schedule_data = json.load(f)

            # Get the round time, use the default if not set
            self.round_time = schedule_data.get("round_time", self.round_time)

            # New: Total number of courses to be simulated
            self.total_courses = schedule_data.get("total_courses", None)

            # Access JSON specified in start_date
            if "start_date" not in schedule_data:
                raise ValueError("JSON File must contain 'start_date' Fields")

            start_date_str = schedule_data["start_date"]
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

            # Settings current_time(Default time is the day day_start_time)
            day_start_time_obj = datetime.strptime(self.day_start_time, "%H:%M").time()
            self.current_time = datetime.combine(start_date, day_start_time_obj)

            # Get the week
            weekday = self.current_time.strftime("%A")
            print(f"[DEBUG] Date used:{start_date},Week:{weekday}")

            daily_events = schedule_data.get(weekday, [])

            print(f"[DEBUG] Load {weekday} Schedule: {len(daily_events)} Event")

            for event_data in daily_events:
                # Parse Time String as Time Object
                start_time_obj = datetime.strptime(event_data["start"], "%H:%M").time()
                end_time_obj = datetime.strptime(event_data["end"], "%H:%M").time()

                # Create Full Time Date Object
                event_start = datetime.combine(start_date, start_time_obj)
                event_end = datetime.combine(start_date, end_time_obj)

                new_event = Event(
                    event_type=event_data["type"],
                    event_name=event_data["name"],
                    start_time=event_start,
                    end_time=event_end
                )

                print(
                    f"[DEBUG] Create Event: {new_event.name} ({event_start.strftime('%H:%M')} - {event_end.strftime('%H:%M')})")
                self.events.append(new_event)

            self.events.sort(key=lambda x: x.start)

            # Print all events for debugging
            print("[DEBUG] List of events of the day:")
            for event in self.events:
                print(f"  - {event.name}: {event.start.strftime('%H:%M')} Present {event.end.strftime('%H:%M')}")

        except Exception as e:
            print(f"[ERROR] Failed to load schedule: {str(e)}")
            # Make sure there's a reasonable time frame even if there's an error
            self.current_time = datetime.combine(datetime.now().date(),
                                                 datetime.strptime(self.day_start_time, "%H:%M").time())

    def get_current_active_event(self) -> Event:
        """Get the current active event"""
        # Use semi-open space [start, end) To determine whether the event is in progress
        for event in self.events:
            if event.start <= self.current_time <= event.end:
                # If there's a parent incident, ID,It's a child event)
                if event.parent_event_id:
                    return event

        # Check main event
        for event in self.events:
            if event.start <= self.current_time <= event.end:
                return event

        # Return to idle status when no incidents
        return FREE_TIME_EVENT

    def publish_event(self):
        """Monitor and broadcast event changes, if returned True"""
        current_event = self.get_current_active_event()
        changed = False

        # Only when events change
        if current_event != self.last_active_event:
            if self.last_active_event is not None:
                print(f"[EVENT] Changes in activity events: {self.last_active_event.name} -> {current_event.name}")
            else:
                print(f"[EVENT] Initial Activity: {current_event.name}")

            msg = BroadcastMessage(
                current_time=self.current_time,
                message_type=MessageType.EVENT_CHANGE,
                active_event=current_event.name,
                event_id=current_event.id,
                speaker="time_manager",
                content=f"Current activity changed to: {current_event.name}",
            )

            # Use synchronous broadcasts to ensure that incidents are handled immediately
            self.broadcast_system.publish_sync("all", msg)
            # await self.broadcast_system.publish("all", msg)

            # Update Last Recorded Events
            self.last_active_event = current_event
            changed = True

        return changed

    def add_event(self, new_event: Event):
        """Dynamic Add Event"""
        try:
            # Check conflicts
            for existing_event in self.events:
                if new_event.is_conflict(existing_event):
                    if existing_event.parent_event_id:
                        continue  # Allow to overwrite child events
                    else:
                        raise ValueError(f"Conflict of events: {new_event.name} and {existing_event.name}")

            # Add New Event
            self.events.append(new_event)
            self.events.sort(key=lambda x: x.start)
            print(
                f"[EVENT] Add New Event: {new_event.name} ({new_event.start.strftime('%H:%M')}-{new_event.end.strftime('%H:%M')})")

            # Check event change immediately
            self.publish_event()

        except ValueError as e:
            print(f"[ERROR] {str(e)}")

    def handle_class_end(
            self,
            current_event: Event,
            overtime_minutes: int  # It's already time for a stall
    ) -> ClassEndAction:
        """
        Based on overtime_minutes I don't know if I'm gonna drag you in
        """
        # Only the end of the course
        if current_event.type != "class":
            return ClassEndAction.OVERTIME  # No processing

        # The main course needs to end
        if overtime_minutes > 0 and current_event.parent_event_id is None:
            overtime_end = current_event.end + timedelta(minutes=overtime_minutes)
            print(f"[OVERTIME] We've detected the trailer! {overtime_minutes} min, to {overtime_end.strftime('%H:%M')}")

            overtime_event = Event(
                event_type="class",
                event_name=f"{current_event.name}[Towhouse]",
                start_time=current_event.end,
                end_time=overtime_end,
                parent_event_id=current_event.id
            )
            self.add_event(overtime_event)
            return ClassEndAction.OVERTIME

        # You don't have to drag the door to the end or the normal end of the course
        else:
            return ClassEndAction.CLASS_OVER

    def proceed_to_next_day(self):
        """Go to the next day"""
        print("\n===== Go to the next day =====")

        # Calculate the date of the next day
        next_day = self.current_time.date() + timedelta(days=1)

        # Update current_time For the next day day_start_time
        hour, minute = map(int, self.day_start_time.split(":"))
        self.current_time = datetime.combine(next_day, dt_time(hour, minute))

        # Reset Last Active Event
        self.last_active_event = None

        # Start of a new day of broadcasting (includes precise time))
        msg = BroadcastMessage(
            message_type=MessageType.NEW_DAY,
            active_event="new_day",
            speaker="time_manager",
            content=f"A new day begins: {self.current_time.strftime('%Y-%m-%d %H:%M')}",
        )
        self.broadcast_system.publish_sync("all", msg)