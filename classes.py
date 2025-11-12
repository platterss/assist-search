from dataclasses import asdict, dataclass
from enum import Enum


class Conjunction(str, Enum):
    AND = "AND"
    OR = "OR"


class ReceivingType(str, Enum):
    COURSE = "COURSE"
    SERIES = "SERIES"
    MISC = "MISCELLANEOUS"
    GE = "GE"


@dataclass
class Institution:
    id: int
    name: str
    category: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BasicCourse:
    subject: str
    prefix: str
    number: str
    key: str
    title: str
    min_units: float
    max_units: float

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_assist(data: dict) -> "BasicCourse":
        prefix = data["prefix"].strip()
        number = data["courseNumber"].strip()

        return BasicCourse(
            subject=data["prefixDescription"].strip(),
            prefix=prefix,
            key=f"{prefix} {number}",
            number=number,
            title=data["courseTitle"].strip(),
            min_units=float(data["minUnits"]),
            max_units=float(data["maxUnits"])
        )


@dataclass
class SendingCourse(BasicCourse):
    notes: list[str]

    @staticmethod
    def from_assist(obj: dict) -> "SendingCourse":
        notes: list[str] = []
        for attribute in (obj.get("attributes") or []):
            content = attribute.get("content")

            if content:
                notes.append(content)

        if obj.get("prefix") is None and obj.get("courseNumber") is None:
            return SendingCourse(
                subject="Broken",
                prefix="Broken",
                number="404",
                key="Broken 404",
                title="Missing Course",
                min_units=-1.0,
                max_units=-1.0,
                notes=["This particular course is broken on ASSIST and displays an empty course."],
            )

        subject = obj["prefixDescription"].strip()
        prefix = obj["prefix"].strip()
        number = obj["courseNumber"].strip()

        return SendingCourse(
            subject=subject,
            prefix=prefix,
            number=number,
            key=f"{prefix} {number}".strip(),
            title=obj["courseTitle"].strip(),
            min_units=float(obj["minUnits"]),
            max_units=float(obj["maxUnits"]),
            notes=notes,
        )


@dataclass
class SetArticulation:
    conjunction: Conjunction | None
    items: list[SendingCourse]
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "type": "SET",
            "conjunction": None if self.conjunction is None else self.conjunction.value,
            "items": [course.to_dict() for course in self.items],
            "notes": self.notes
        }


@dataclass
class GroupArticulation:
    conjunctions: list[Conjunction]
    items: list[SetArticulation]
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "type": "GROUP",
            "conjunctions": [conjunction.value for conjunction in self.conjunctions],
            "items": [item.to_dict() for item in self.items],
            "notes": self.notes
        }


@dataclass
class ReceivingSeries:
    key: str
    conjunction: Conjunction
    courses: list[BasicCourse]

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "conjunction": self.conjunction.value,
            "courses": [course.to_dict() for course in self.courses],
        }


@dataclass
class ReceivingRequirement:
    kind: ReceivingType
    key: str

    def to_dict(self) -> dict:
        return {"key": self.key}

    @staticmethod
    def get_kind_and_key(node: dict) -> tuple[ReceivingType, str] | None:
        if "requirement" in node.keys():
            return ReceivingType.MISC, "requirement"
        elif "generalEducationArea" in node.keys():
            return ReceivingType.GE, "generalEducationArea"

        return None


@dataclass
class ReceivingItem:
    key: str
    receiving_type: ReceivingType
    receiving: BasicCourse | ReceivingSeries | ReceivingRequirement
    sending_articulation: dict | None

    @staticmethod
    def from_receiving(
            receiving: BasicCourse | ReceivingSeries | ReceivingRequirement,
            sending_articulation: dict | None = None
    ) -> "ReceivingItem":
        if isinstance(receiving, BasicCourse):
            receiving_type = ReceivingType.COURSE
        elif isinstance(receiving, ReceivingSeries):
            receiving_type = ReceivingType.SERIES
        else:
            receiving_type = receiving.kind

        return ReceivingItem(
            key=receiving.key,
            receiving_type=receiving_type,
            receiving=receiving,
            sending_articulation=sending_articulation
        )
