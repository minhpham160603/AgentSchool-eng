import json
import datetime
import types
import aiofiles
from typing import List, Dict
from enum import Enum

def default_serializer(obj):
    """Enhanced Sequencing Functions to Process More Types"""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, types.MappingProxyType):
        return dict(obj)  # Will mappingproxy Convert to a normal dictionary
    elif isinstance(obj, Enum):
        return obj.value  # Convert Element to Value
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    elif hasattr(obj, 'to_dict') and callable(obj.to_dict):
        return obj.to_dict()  # Support to_dict() Methodology
    raise TypeError(f"Unable to sequence type: {type(obj)}")

def make_json_serializable(data):
    """
    Recursive conversion of data structure to JSON Sequencable Format
    """
    if isinstance(data, dict):
        return {key: make_json_serializable(value) for key, value in data.items()}
    elif isinstance(data, (list, tuple)):
        return [make_json_serializable(item) for item in data]
    elif isinstance(data, datetime.datetime):
        return data.isoformat()
    elif isinstance(data, Enum):
        return data.value  # Handle count type
    elif hasattr(data, 'to_dict') and callable(data.to_dict):
        return make_json_serializable(data.to_dict())  # Recursively handle custom objects
    else:
        return data

class Recorder:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.logs: List[Dict] = []

    async def log(self, current_time: datetime = None, event_type: str = "", details: dict = None):
        entry = {}
        if current_time is not None:
            entry['time'] = current_time.isoformat()
        entry['event'] = event_type
        entry['details'] = details or {}

        cleaned_entry = make_json_serializable(entry)
        self.logs.append(cleaned_entry)

        # Step file
        async with aiofiles.open(self.log_file, "a", encoding='utf-8') as f:
            # Use enhanced serialization functions
            json_str = json.dumps(cleaned_entry, ensure_ascii=False, default=default_serializer)
            await f.write(json_str + "\n")
    
    def log_sync(self, current_time: datetime = None, event_type: str = "", details: dict = None):
        """
        Synchronize log
        """
        # time.sleep(0.01)
        entry = {}
        if current_time is not None:
            entry['time'] = current_time.isoformat()
        entry['event'] = event_type
        entry['details'] = details or {}

        cleaned_entry = make_json_serializable(entry)
        self.logs.append(cleaned_entry)

        with open(self.log_file, "a", encoding='utf-8') as f:
            json_str = json.dumps(cleaned_entry, ensure_ascii=False, default=default_serializer)
            f.write(json_str + "\n")

    def query_logs(self, event_type: str = None, start_time: str = None, end_time: str = None) -> List[Dict]:
        """Query Log by Condition"""
        results = []
        for entry in self.logs:
            if event_type and entry["event"] != event_type:
                continue
            if start_time and entry["time"] < start_time:
                continue
            if end_time and entry["time"] > end_time:
                continue
            results.append(entry)
        return results

    def set_file_path(self, file: str):
        self.log_file = file
        # # Empty Log File
        # with open(self.log_file, "w", encoding='utf-8') as f:
        #     pass  # Use only for emptying files without writing