"""SimpleFIX message adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..errors import MissingOptionalDependency


@dataclass
class SimpleFixNewOrderSingleEncoder:
    """Encode a FinSpace FIX order record using SimpleFIX."""

    sender: str = "FINSPACE_SENDER"
    target: str = "FINSPACE_TARGET"
    sending_time: str = "20260802-13:30:00.000"
    static_tags: Mapping[int, Any] = field(default_factory=dict)

    def __call__(self, record: Mapping[str, Any]) -> bytes:
        try:
            import simplefix
        except ImportError as error:
            raise MissingOptionalDependency("install finspace[fix]") from error
        message = simplefix.FixMessage()
        message.append_pair(8, "FIX.4.4")
        message.append_pair(35, record.get("message_type", "D"))
        message.append_pair(49, self.sender, header=True)
        message.append_pair(52, self.sending_time, header=True)
        message.append_pair(56, self.target, header=True)
        pairs = [
            (11, record.get("client_order_id", "FINSPACE-ORDER")),
            (21, "1"),
            (55, record["symbol"]),
            (54, record["side"]),
            (60, self.sending_time),
            (38, record["quantity"]),
            (40, record["order_type"]),
            (59, record.get("time_in_force", "0")),
        ]
        if "price" in record:
            pairs.append((44, record["price"]))
        if "stop_price" in record:
            pairs.append((99, record["stop_price"]))
        pairs.extend(self.static_tags.items())
        for tag, value in pairs:
            message.append_pair(tag, value)
        return message.encode()
