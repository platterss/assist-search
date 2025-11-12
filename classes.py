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
            min_units=data["minUnits"],
            max_units=data["maxUnits"]
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
            title=(obj.get("courseTitle") or "").strip(),
            min_units=float(obj.get("minUnits")),
            max_units=float(obj.get("maxUnits")),
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


# BasicCourse is enough for our needs so far. Not much point to this.
# @dataclass
# class ReceivingCourse(BasicCourse):
#     articulations: list
#
#     def to_row(self) -> dict:
#         return {**{"type": "COURSE"},
#                 **self.to_dict(),
#                 "articulations": []}
#
#     @staticmethod
#     def from_basic(basic: BasicCourse) -> "ReceivingCourse":
#         course = ReceivingCourse.__new__(ReceivingCourse)
#         course.__dict__.update(basic.__dict__)
#         course.articulations = []
#
#         return course


@dataclass
class ReceivingSeries:
    key: str
    conjunction: Conjunction
    courses: list[BasicCourse]

    def to_row(self) -> dict:
        return {
            "type": "SERIES",
            "key": self.key,
            "conjunction": self.conjunction.value,
            "courses": [course.to_dict() for course in self.courses],
            "articulations": []
        }


@dataclass
class ReceivingMisc:
    key: str

    def to_row(self) -> dict:
        return {
            "type": "MISCELLANEOUS",
            "key": self.key,
            "articulations": []
        }


@dataclass
class ReceivingGE:
    key: str

    def to_row(self) -> dict:
        return {
            "type": "GE",
            "key": self.key,
            "articulations": []
        }


@dataclass
class ReceivingItem:
    key: str
    receiving_type: ReceivingType
    receiving: BasicCourse | ReceivingSeries | ReceivingMisc | ReceivingGE
    sending_articulation: dict | None

    @staticmethod
    def from_receiving(
            receiving: BasicCourse | ReceivingSeries | ReceivingMisc | ReceivingGE,
            sending_articulation: dict | None = None
    ) -> "ReceivingItem":
        if isinstance(receiving, BasicCourse):
            receiving_type = ReceivingType.COURSE
        elif isinstance(receiving, ReceivingSeries):
            receiving_type = ReceivingType.SERIES
        elif isinstance(receiving, ReceivingMisc):
            receiving_type = ReceivingType.MISC
        else:
            receiving_type = ReceivingType.GE

        return ReceivingItem(
            key=receiving.key,
            receiving_type=receiving_type,
            receiving=receiving,
            sending_articulation=sending_articulation
        )
