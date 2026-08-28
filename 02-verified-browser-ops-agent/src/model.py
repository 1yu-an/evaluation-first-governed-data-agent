from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

class Status(str, Enum):
    READY="READY"; ACTED="ACTED"; VERIFIED="VERIFIED"; FAILED="FAILED"; WAITING_APPROVAL="WAITING_APPROVAL"

@dataclass
class Task:
    action: str
    target: str
    value: str | None = None

@dataclass
class StepResult:
    status: Status
    observation: Dict[str, Any]
    message: str
