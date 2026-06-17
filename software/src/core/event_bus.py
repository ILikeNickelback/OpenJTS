"""Event bus implementation for decoupled communication between components."""


class EventBus:
    """Publish/subscribe event bus for loosely coupled inter-component messaging.

    Components subscribe to named events with a callback. When another component
    publishes that event, all registered callbacks are invoked with the provided
    keyword arguments.
    """

    def __init__(self):
        """Initialize the event bus with an empty subscriber registry."""
        self._subscribers = {}

    def subscribe(self, event: str, callback) -> None:
        """Register a callback to be invoked when the given event is published.

        Multiple callbacks can be subscribed to the same event; they are called
        in registration order.

        Args:
            event: Name of the event to listen for.
            callback: Callable invoked with the keyword arguments passed to
                :meth:`publish` when the event fires.
        """
        self._subscribers.setdefault(event, []).append(callback)

    def publish(self, event: str, **kwargs) -> None:
        """Broadcast an event to all registered subscribers.

        Subscribers are called synchronously in registration order. If no
        callbacks are registered for the event, the call is a no-op.

        Args:
            event: Name of the event to broadcast.
            **kwargs: Arbitrary keyword arguments forwarded to each callback.
        """
        for cb in self._subscribers.get(event, []):
            cb(**kwargs)
