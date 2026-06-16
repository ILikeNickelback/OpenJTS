"Event bus implementation for decoupled communication between components."


class EventBus:
    def __init__(self):
        "Initialize the event bus with an empty subscriber registry."
        self._subscribers = {}

    def subscribe(self, event: str, callback):
        "Subscribe a callback function to a specific event."
        self._subscribers.setdefault(event, []).append(callback)

    def publish(self, event: str, **kwargs):
        "Publish an event with the given keyword arguments."
        for cb in self._subscribers.get(event, []):
            cb(**kwargs)
