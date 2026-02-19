from __future__ import annotations

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


class CategoryCode(str, Enum):
    MAJOR = "major"
    DEPT = "dept"
    PREFIX = "prefix"
    GE = "breadth"


class AgreementType(str, Enum):
    ALL_MAJORS = "AllMajors"
    ALL_DEPTS = "AllDepartments"
    ALL_PREFIXES = "AllPrefixes"
    ALL_GE = "AllGeneralEducation"


@dataclass
class Institution:
    id: int
    name: str
    category: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Course:
    prefix_desc: str
    prefix: str
    number: str
    title: str
    min_units: float
    max_units: float
    course_id: int
    prefix_id: int

    def get_unique_key(self):
        return f"COURSE:{self.course_id}"

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(class_dict: dict):
        if class_dict.get("courseTitle") is None:
            return Course(
                course_id=-1,
                title="Broken Course",
                number="Course",
                prefix="Unknown",
                prefix_id=-1,
                prefix_desc="Broken Course",
                min_units=-1,
                max_units=-1
            )

        course_id = class_dict["courseIdentifierParentId"]
        title = class_dict["courseTitle"].strip()
        number = class_dict["courseNumber"].strip()
        prefix = class_dict["prefix"].strip()
        prefix_id = class_dict["prefixParentId"]
        prefix_desc = class_dict["prefixDescription"].strip()
        min_units = class_dict["minUnits"]
        max_units = class_dict["maxUnits"]

        return Course(
            course_id=course_id,
            title=title,
            number=number,
            prefix=prefix,
            prefix_id=prefix_id,
            prefix_desc=prefix_desc,
            min_units=min_units,
            max_units=max_units
        )


@dataclass
class SeriesCourse(Course):
    position: int
    notes: list[str]

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(class_data: dict):
        course = Course.from_dict(class_data)
        position = class_data["position"]

        raw_attributes = class_data.get("attributes", [])
        raw_attributes.sort(key=lambda x: x["position"])
        notes = [attribute["content"] for attribute in raw_attributes]

        return SeriesCourse(
            **vars(course),
            position=position,
            notes=notes
        )


@dataclass
class Series:
    name: str
    notes: list[str]
    conjunction: str
    courses: list[SeriesCourse]

    def get_unique_key(self) -> str:
        course_ids = [str(course.course_id) for course in self.courses]
        return f"SERIES:{self.conjunction}:{"|".join(course_ids)}"

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(series_data: dict):
        conjunction = series_data["conjunction"].strip().upper()
        name = series_data["name"].strip()
        courses = [SeriesCourse.from_dict(course) for course in series_data["courses"]]
        courses.sort(key=lambda course: course.position)

        return Series(
            conjunction=conjunction,
            name=name,
            courses=courses,
            notes=[]
        )


@dataclass
class Requirement:
    name: str

    def get_unique_key(self) -> str:
        return f"REQ:{self.name.upper()}"

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(req_data: dict):
        return Requirement(
            name=req_data["name"].strip()
        )


@dataclass
class GeneralEducation:
    code: str
    name: str

    def get_unique_key(self) -> str:
        return f"GE:{self.code.upper()}"

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(ge_data: dict):
        return GeneralEducation(
            code=ge_data["code"].strip(),
            name=ge_data["name"].strip()
        )


@dataclass
class ArticulationItem:
    sending_id: int
    sending_name: str
    articulation: SendingArticulation

    def to_dict(self):
        return asdict(self)


@dataclass
class ReceivingCourse(Course):
    articulations: dict[str, ArticulationItem | list[ArticulationItem]]

    def get_unique_key(self):
        return super().get_unique_key()

    @staticmethod
    def from_dict(course_data: dict):
        return ReceivingCourse(
            **vars(Course.from_dict(course_data)),
            articulations={}
        )


@dataclass
class ReceivingSeries(Series):
    articulations: dict[str, ArticulationItem | list[ArticulationItem]]

    def get_unique_key(self) -> str:
        return super().get_unique_key()

    @staticmethod
    def from_dict(series_data: dict):
        return ReceivingSeries(
            **vars(Series.from_dict(series_data)),
            articulations={}
        )


@dataclass
class ReceivingRequirement(Requirement):
    articulations: dict[str, ArticulationItem | list[ArticulationItem]]

    def get_unique_key(self) -> str:
        return super().get_unique_key()

    @staticmethod
    def from_dict(req_data: dict):
        return ReceivingRequirement(
            **vars(Requirement.from_dict(req_data)),
            articulations={}
        )


@dataclass
class ReceivingGE(GeneralEducation):
    articulations: dict[str, ArticulationItem | list[ArticulationItem]]

    def get_unique_key(self) -> str:
        return super().get_unique_key()

    @staticmethod
    def from_dict(ge_data: dict):
        return ReceivingGE(
            **vars(GeneralEducation.from_dict(ge_data)),
            articulations={}
        )


@dataclass
class SendingArticulation:
    notes: list[str]
    conjunctions: list[str]
    items: list[Series]

    def get_unique_key(self) -> str:
        item_keys = [item.get_unique_key() for item in self.items]

        full_string = ""
        for i, key in enumerate(item_keys):
            full_string += key
            if i < len(self.conjunctions):
                full_string += f"_{self.conjunctions[i]}_"

        return f"SENDING_ART:{full_string}"

    def to_dict(self):
        data = asdict(self)

        if not self.conjunctions:
            data["conjunctions"] = None

        return data


@dataclass
class Major:
    name: str
    courses: list[Course | Series | Requirement | GeneralEducation]

    def to_dict(self):
        return asdict(self)


@dataclass
class Department:
    name: str
    courses: list[Course | Series | Requirement | GeneralEducation]

    def to_dict(self):
        return asdict(self)