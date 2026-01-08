"""Base event listener for MindFlow event system."""

from abc import ABC, abstractmethod

from mindflow.events.event_bus import MindflowEventsBus, mindflow_event_bus


class BaseEventListener(ABC):
    """Abstract base class for event listeners."""

    verbose: bool = False

    def __init__(self) -> None:
        """Initialize the event listener and register handlers."""
        super().__init__()
        self.setup_listeners(mindflow_event_bus)
        mindflow_event_bus.validate_dependencies()

    @abstractmethod
    def setup_listeners(self, mindflow_event_bus: MindflowEventsBus) -> None:
        """Setup event listeners on the event bus.

        Args:
            mindflow_event_bus: The event bus to register listeners on.
        """
