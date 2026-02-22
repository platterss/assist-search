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
class SendingSeriesCourse:
    course_id: int
    notes: list[str]


@dataclass
class SendingSeries:
    notes: list[str]
    conjunction: str
    courses: list[SendingSeriesCourse]

    def get_unique_key(self) -> str:
        course_ids = [str(course.course_id) for course in self.courses]
        return f"SERIES:{self.conjunction}:{'|'.join(course_ids)}"


@dataclass
class SeriesCourse(Course):
    notes: list[str]

    @staticmethod
    def from_dict(class_data: dict):
        course = Course.from_dict(class_data)

        raw_attributes = class_data.get("attributes") or []
        raw_attributes.sort(key=lambda x: x["position"])
        notes = [attribute["content"] for attribute in raw_attributes]

        return SeriesCourse(
            **vars(course),
            notes=notes
        )


@dataclass
class Series:
    name: str
    notes: list[str]
    conjunction: str | None
    courses: list[SeriesCourse | SendingSeriesCourse]

    def get_unique_key(self) -> str:
        course_ids = [str(course.course_id) for course in self.courses]
        conj = self.conjunction if self.conjunction else "NONE"
        return f"SERIES:{conj}:{"|".join(course_ids)}"

    @staticmethod
    def from_dict(series_data: dict):
        raw_courses = series_data["courses"]
        raw_courses.sort(key=lambda c: c["position"])
        courses = [SeriesCourse.from_dict(course) for course in raw_courses]
        conjunction = series_data["conjunction"].strip().upper()

        if len(courses) == 1:
            conjunction = None

        return Series(
            conjunction=conjunction,
            name=series_data["name"].strip(),
            courses=courses,
            notes=[]
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
    articulations: (dict[str, ArticulationItem | list[ArticulationItem]] |
                    list[ArticulationItem | list[ArticulationItem]])

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
