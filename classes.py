from __future__ import annotations

from dataclasses import dataclass
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

    @staticmethod
    def from_dict(class_dict: dict):
        valid = bool(class_dict.get("courseTitle"))

        return Course(
            prefix_desc=class_dict.get("prefixDescription").strip() if valid else "Broken Course",
            prefix=class_dict.get("prefix").strip() if valid else "Unknown",
            number=class_dict.get("courseNumber").strip() if valid else "Course",
            title=class_dict.get("courseTitle").strip() if valid else "Broken Course",
            min_units=class_dict.get("minUnits") if valid else -1.0,
            max_units=class_dict.get("maxUnits") if valid else-1.0,
            course_id=class_dict.get("courseIdentifierParentId") if valid else -1,
            prefix_id=class_dict.get("prefixParentId") if valid else -1
        )


@dataclass
class SendingCourse:
    course_id: int
    notes: list[str]


@dataclass
class SendingSeries:
    notes: list[str]
    conjunction: str
    courses: list[SendingCourse]

    def get_unique_key(self) -> str:
        course_ids = [str(course.course_id) for course in self.courses]
        return f"SERIES:{self.conjunction}:{'|'.join(course_ids)}"


@dataclass
class Series:
    name: str
    conjunction: str | None
    courses: list[Course | SendingCourse]

    def get_unique_key(self) -> str:
        course_ids = [str(course.course_id) for course in self.courses]
        conj = self.conjunction if self.conjunction else "NONE"
        return f"SERIES:{conj}:{"|".join(course_ids)}"

    @staticmethod
    def from_dict(series_data: dict):
        raw_courses = series_data["courses"]
        raw_courses.sort(key=lambda c: c["position"])
        courses = [Course.from_dict(course) for course in raw_courses]
        conjunction = series_data["conjunction"].strip().upper()

        if len(courses) == 1:
            conjunction = None

        return Series(
            conjunction=conjunction,
            name=series_data["name"].strip(),
            courses=courses,
        )


@dataclass
class Requirement:
    name: str

    def get_unique_key(self) -> str:
        return f"REQ:{self.name.upper()}"

    @staticmethod
    def from_dict(req_data: dict):
        return Requirement(
            name=req_data["name"].strip()
        )


@dataclass
class GeneralEducation:
    area_type: str  # CSUGE, IGETC, CALGETC
    code: str
    name: str

    def get_unique_key(self) -> str:
        return f"GE:{self.code.upper()}"

    @staticmethod
    def from_dict(ge_data: dict):
        return GeneralEducation(
            area_type=ge_data.get("areaType", "University").strip(),
            code=ge_data["code"].strip(),
            name=ge_data["name"].strip()
        )


@dataclass
class ArticulationItem:
    sending_id: int
    articulation: SendingArticulation
    contexts: list[str]


@dataclass
class ReceivingCourse(Course):
    articulations: dict[str, ArticulationItem | list[ArticulationItem]]

    @staticmethod
    def from_dict(course_data: dict):
        return ReceivingCourse(
            **vars(Course.from_dict(course_data)),
            articulations={}
        )


@dataclass
class ReceivingSeries(Series):
    articulations: dict[str, ArticulationItem | list[ArticulationItem]]

    @staticmethod
    def from_dict(series_data: dict):
        return ReceivingSeries(
            **vars(Series.from_dict(series_data)),
            articulations={}
        )


@dataclass
class ReceivingRequirement(Requirement):
    articulations: dict[str, ArticulationItem | list[ArticulationItem]]

    @staticmethod
    def from_dict(req_data: dict):
        return ReceivingRequirement(
            **vars(Requirement.from_dict(req_data)),
            articulations={}
        )


@dataclass
class ReceivingGE(GeneralEducation):
    articulations: (dict[str, ArticulationItem | list[ArticulationItem]] |
                    list[ArticulationItem | list[ArticulationItem]])

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
    items: list[SendingSeries]

    def get_unique_key(self) -> str:
        item_keys = [item.get_unique_key() for item in self.items]

        full_string = ""
        for i, key in enumerate(item_keys):
            full_string += key
            if self.conjunctions and i < len(self.conjunctions):
                full_string += f"_{self.conjunctions[i]}_"

        return f"SENDING_ART:{full_string}"


@dataclass
class Major:
    name: str
    courses: list[Course | Series | Requirement | GeneralEducation]


@dataclass
class Department:
    name: str
    courses: list[Course | Series | Requirement | GeneralEducation]
