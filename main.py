import json

from agreements import get_agreements
from classes import Conjunction, SendingArticulationNode, SendingCourse, NodeType
from pathlib import Path


def make_node(data: dict) -> SendingArticulationNode:
    node_type = NodeType(data["type"])
    conjunction = Conjunction(data["conjunction"]) if data["conjunction"] else None

    courses = [SendingCourse(**course_data) for course_data in data["courses"]]
    children = [make_node(child) for child in data["children"]]
    notes = list(data.get("notes", []))

    return SendingArticulationNode(
        type=node_type,
        conjunction=conjunction,
        courses=courses,
        children=children,
        notes=notes,
    )


def format_node(node: SendingArticulationNode) -> str:
    def fmt(n: SendingArticulationNode, depth: int = 0) -> list[str]:
        indent = "  " * depth
        lines: list[str] = []

        if n.type == NodeType.COURSE:
            for i, c in enumerate(n.courses):
                lines.append(f"{indent}{c.code} - {c.title}")
                for note in c.notes:
                    lines.append(f"{indent}  - {note}")
                if i != len(n.courses) - 1:
                    lines.append(f"{indent}{indent}AND")
            for note in n.notes:
                lines.append(f"{indent}(Note) {note}")
            return lines

        conj = (n.conjunction or Conjunction.AND).value
        for i, ch in enumerate(n.children):
            lines.extend(fmt(ch, depth + 1))
            if i != len(n.children) - 1:
                lines.append(f"{indent}{conj}")
        for note in n.notes:
            lines.append(f"{indent}(Note) {note}")
        return lines

    return "\n".join(fmt(node))


def print_articulation(articulation: dict) -> None:
    print(f"\nFrom: {articulation['sending_name']}")
    node = make_node(articulation["sending_articulation"])
    print(format_node(node))


def get_universities() -> list[dict]:
    institutions_path = Path("data/institutions.json")
    with open(institutions_path, "r") as institutions_file:
        institutions: list[dict] = json.load(institutions_file)

    universities = [institution for institution in institutions if institution["category"] in ["UC", "CSU"]]
    universities.sort(key=lambda x: x["name"])

    return universities


def get_subjects(university_name: str) -> list[dict]:
    subjects_path = Path(f"data/universities/{university_name}/subjects.json")
    with open(subjects_path, "r") as subjects_file:
        return json.load(subjects_file)


def get_course_numbers(university_name: str, subject_prefix: str):
    courses_path = Path(f"data/universities/{university_name}/{subject_prefix}/courses.json")
    with open(courses_path, "r") as courses_file:
        return json.load(courses_file)


def university_input() -> str:
    universities = get_universities()

    uni_types = sorted(set([uni["category"] for uni in universities]))

    for i, uni_type in enumerate(uni_types, 1):
        print(f"{i}: {uni_type}")
    selected_category = uni_types[int(input("Select the type of universities you want to search through: ")) - 1]

    desired_universities = [university for university in universities if university["category"] == selected_category]
    for i, university in enumerate(desired_universities, 1):
        print(f"{i}: {university["name"]}")

    return desired_universities[int(input("Select the number of the university: ")) - 1]["name"]


def subject_input(university: str) -> dict:
    subjects: list[dict] = get_subjects(university)
    for i, subject in enumerate(subjects, 1):
        print(f"{i}: {subject["prefix"]} - {subject["name"]}")

    return subjects[int(input("Select the number of the subject: ")) - 1]


def handle_courses(university: str, subject: dict) -> dict:
    courses: list[dict] = get_course_numbers(university, subject["prefix"])

    for i, course in enumerate(courses, 1):
        if course["type"] == "COURSE":
            print(f"{i}: {course["prefix"]} {course["number"]} - {course["title"]}")
        elif course["type"] == "SERIES":
            nums = " + ".join(c["number"] for c in course["courses"])
            titles = ", ".join(c["title"] for c in course["courses"])
            print(f"{i}: {course["prefix"]} {nums} - {titles}")
        elif course["type"] == "REQUIREMENT":
            print(f"{i}: {course["name"]}")
        elif course["type"] == "GE":
            print(f"{i}: {course["name"]}")

    return courses[int(input("Select the number of the course: ")) - 1]


def print_articulations(course: dict) -> None:
    print(f"\n=== Articulations for {course["key"]} ===")

    articulation_result = course["articulations"]

    if len(articulation_result) == 0:
        print("This requirement has no articulations at any CCCs.")
        print("It will need to be completed at the university.")
    else:
        for articulation in articulation_result:
            print_articulation(articulation)


def main():
    if not Path("data/colleges").exists():
        get_agreements()

    while True:
        university: str = university_input()
        subject: dict = subject_input(university)
        course: dict = handle_courses(university, subject)
        print_articulations(course)

        proceed = input("\nContinue? (y/n) ")

        if proceed.lower() != "y":
            break


if __name__ == "__main__":
    main()
