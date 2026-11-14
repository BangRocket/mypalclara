"""mypal-protocol: the WebSocket wire contract shared by the engine and its clients.

Pure Pydantic message models, zero engine/db dependencies.
"""

from mypal_protocol.messages import *  # noqa: F401,F403
from mypal_protocol.messages import PROTOCOL_VERSION  # noqa: F401
