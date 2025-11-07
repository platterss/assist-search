from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, Union


class Conjunction(str, Enum):
    AND = "AND"
    OR = "OR"


class NodeType(str, Enum):
    SET = "SET"
    GROUP = "GROUP"


@dataclass(frozen=True)
class SendingCourse:
    prefix: str
    number: str
    key: str
    title: str
    notes: list[str]
    min_units: float
    max_units: float


@dataclass
class SendingArticulationNode:
    type: NodeType
    conjunction: Optional[Conjunction]
    items: list[Union[SendingCourse, SendingArticulationNode]]
    notes: list[str]

    def to_dict(self) -> dict:
        out: dict = {
            "type": self.type.value,
            "conjunction": None if self.conjunction is None else self.conjunction.value
        }

        groups = []
        for group in self.items:
            if isinstance(group, SendingCourse):
                groups.append(asdict(group))
            elif isinstance(group, SendingArticulationNode):
                groups.append(group.to_dict())

        out.update({
            "items": groups,
            "notes": list(self.notes)
        })

        return out
