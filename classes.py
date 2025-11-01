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
class Course:
    prefix: str
    number: str
    title: str
    notes: list[str]
    min_units: float
    max_units: float

    @property
    def code(self) -> str:
        return f"{self.prefix} {self.number}"


@dataclass
class ArticulationNode:
    type: NodeType
    conjunction: Optional[Conjunction]
    courses: list[Course]
    children: list[ArticulationNode]
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "conjunction": None if self.conjunction is None else self.conjunction.value,
            "courses": [asdict(course) for course in self.courses],
            "children": [child.to_dict() for child in self.children],
            "notes": list(self.notes)
        }
