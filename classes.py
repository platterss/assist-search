from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, Union


class Conjunction(str, Enum):
    AND = "AND"
    OR = "OR"


class NodeType(str, Enum):
    MULTI = "MULTI"
    SINGLE = "SINGLE"


@dataclass(frozen=True)
class SendingCourse:
    prefix: str
    number: str
    key: str
    title: str
    notes: list[str]
    min_units: float
    max_units: float

    @property
    def code(self) -> str:
        return self.key


@dataclass
class SendingArticulationNode:
    type: NodeType
    conjunction: Optional[Conjunction]
    course_groups: list[Union[SendingCourse, SendingArticulationNode]]
    notes: list[str]

    def to_dict(self) -> dict:
        out: dict = {
            "type": self.type.value
        }

        # I find it looks better when the conjunction is after the type instead of at the bottom
        if self.conjunction is not None:
            out["conjunction"] = self.conjunction.value

        groups = []
        for group in self.course_groups:
            if isinstance(group, SendingCourse):
                groups.append(asdict(group))
            elif isinstance(group, SendingArticulationNode):
                groups.append(group.to_dict())

        out.update({
            "course_groups": groups,
            "notes": list(self.notes)
        })

        return out
