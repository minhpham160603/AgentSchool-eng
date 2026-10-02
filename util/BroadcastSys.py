from typing import Dict, Set, Any
from util.BroadcastMessage import BroadcastMessage
import asyncio
import re


class BroadcastSys:
    def __init__(self, recorder):
        self.subscriptions: Dict[str, Set[Any]] = {"all": set()}
        self.recorder = recorder
        self.debug = True  # Enable debug output

    @staticmethod
    def _strip_think_blocks(text: str) -> str:
        """Remove <think>...</think> blocks and retain the remaining text."""
        try:
            return re.sub(r"(?is)<think>.*?</think>", "", text)
        except Exception:
            return text

    def subscribe(self, subscriber: Any, subscriber_type: str):
        """Subscribe an agent to a broadcast channel."""
        if subscriber_type not in self.subscriptions:
            self.subscriptions[subscriber_type] = set()
        self.subscriptions[subscriber_type].add(subscriber)
        self.subscriptions['all'].add(subscriber)

        if self.debug:
            print(f"[BroadcastSys] Subscriptions: {getattr(subscriber, 'name', 'unknown')} Type: {subscriber_type}")

    def unsubscribe(self, subscriber: Any, subscriber_type: str):
        """Unsubscribe an agent from a broadcast channel."""
        if subscriber_type in self.subscriptions:
            self.subscriptions[subscriber_type].discard(subscriber)

        if self.debug:
            print(f"[BroadcastSys] Unsubscribe: {getattr(subscriber, 'name', 'unknown')} Type: {subscriber_type}")

    async def publish(self, subscriber_type: str, message: BroadcastMessage):
        """
        Publish a structured message asynchronously to subscribers of the given type.
        ARGS:
            subscriber_type: Subscriber type, such as "student".
            message: BroadcastMessage instance.
        """
        if self.debug:
            print(f"[BroadcastSys.publish] Passing messages to {subscriber_type}")

        # Add recipient information to log
        log_data = message.to_dict()
        # Remove <think>...</think> blocks from the logged message content.
        if isinstance(log_data.get("content"), str):
            log_data["content"] = self._strip_think_blocks(log_data["content"]).strip()
        log_data["receiver"] = subscriber_type

        # Collect all the different tasks
        tasks = []
        agents = self.subscriptions.get(subscriber_type, set())

        if self.debug:
            print(f"[DEBUG] Found {len(agents)} subscribers of type {subscriber_type}")

        for agent in agents:
            if hasattr(agent, "receive_broadcast"):
                # Add each agent's receive_broadcast task to the list.
                tasks.append(agent.receive_broadcast(log_data))

                if self.debug:
                    name = getattr(agent, 'name', 'unknown')
                    print(f"[DEBUG] Sending asynchronous message to: {name}")

        # Run the asynchronous delivery tasks concurrently.
        if tasks:
            await asyncio.gather(*tasks)

        # Log messages except student facial expressions.
        if message.message_type != "expression":
            await self.recorder.log(
                event_type="broadcast",
                details=log_data
            )

    def publish_sync(self, subscriber_type: str, message: BroadcastMessage):
        """
        Publish a structured message synchronously to subscribers of the given type.
        ARGS:
            subscriber_type: Subscriber type, such as "student".
            message: BroadcastMessage instance.
        """
        if self.debug:
            print(f"[BroadcastSys.publish_sync] Synchronising message to {subscriber_type}")

        # Add recipient information to log
        log_data = message.to_dict()
        # Remove <think>...</think> blocks from the logged message content.
        if isinstance(log_data.get("content"), str):
            log_data["content"] = self._strip_think_blocks(log_data["content"]).strip()
        log_data["receiver"] = subscriber_type

        # Call receive_broadcast_sync on each subscriber.
        agents = self.subscriptions.get(subscriber_type, set())

        if self.debug:
            print(f"[DEBUG] Found {len(agents)} subscribers of type {subscriber_type}")

        for agent in agents:
            if self.debug:
                name = getattr(agent, 'name', 'unknown')
                print(f"[DEBUG] Delivering synchronous message to: {name} - Type: {type(agent).__name__}")

            if hasattr(agent, "receive_broadcast_sync"):
                agent.receive_broadcast_sync(log_data)

                if self.debug:
                    print(f"[DEBUG] Synchronising message sent: {name}")
            elif self.debug:
                print(f"[DEBUG] Subscriber has no receive_broadcast_sync method: {name}")

        # Log messages except student facial expressions.
        if message.active_event != "expression":
            self.recorder.log_sync(
                event_type="broadcast",
                details=log_data
            )

    def enable_debug(self, debug=True):
        """Enable or disable debug output"""
        self.debug = debug
