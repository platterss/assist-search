from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional


class Conjunction(str, Enum):
    AND = "AND"
    OR = "OR"


class NodeType(str, Enum):
    GROUP = "GROUP"
    COURSE = "COURSE"


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
    courses: list[SendingCourse]
    children: list[SendingArticulationNode]
    notes: list[str]

    def to_dict(self) -> dict:
        out: dict = {
            "type": self.type.value
        }

        # I find it looks better when the conjunction is after the type instead of at the bottom
        if self.conjunction is not None:
            out["conjunction"] = self.conjunction.value

        out.update({
            "courses": [asdict(course) for course in self.courses],
            "children": [child.to_dict() for child in self.children],
            "notes": list(self.notes)
        })

        return out
