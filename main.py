import json

from classes import Conjunction, SendingArticulationNode, SendingCourse, NodeType
from pathlib import Path


def make_node(data: dict) -> SendingArticulationNode:
    node_type = NodeType(data["type"])
    conjunction = Conjunction(data["conjunction"]) if data["conjunction"] else None

    if node_type == NodeType.SINGLE:
        course_groups = [SendingCourse(**course_data) for course_data in data["course_groups"]]
    else:
        course_groups = [make_node(child) for child in data["course_groups"]]

    notes = list(data.get("notes", []))

    return SendingArticulationNode(
        type=node_type,
        conjunction=conjunction,
        course_groups=course_groups,
        notes=notes,
    )


def format_node(node: SendingArticulationNode) -> str:
    def fmt(n: SendingArticulationNode, depth: int = 0) -> list[str]:
        indent = "  " * depth
        lines: list[str] = []

        if n.type == NodeType.SINGLE:
            join = n.conjunction.value if n.conjunction else None
            for i, c in enumerate(n.course_groups):
                lines.append(f"{indent}{c.code} - {c.title}")
                for note in c.notes:
                    lines.append(f"{indent}  - {note}")
                if i != len(n.course_groups) - 1:
                    lines.append(f"{indent}{join}")
            for note in n.notes:
                lines.append(f"{indent}(Note) {note}")
            return lines

        # NodeType.MULTI
        join = n.conjunction.value if n.conjunction else ""
        for i, ch in enumerate(n.course_groups):
            lines.extend(fmt(ch, depth + 1))
            if join and i != len(n.course_groups) - 1:
                lines.append(f"{indent}{join}")
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
    subjects_path = Path(f"data/{university_name}/subjects.json")
    with open(subjects_path, "r") as subjects_file:
        return json.load(subjects_file)


def get_course_numbers(university_name: str, subject_prefix: str):
    courses_path = Path(f"data/{university_name}/{subject_prefix}/courses.json")
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
            print(f"{i}: {course["key"]} - {course["title"]}")
        elif course["type"] == "SERIES":
            codes = " + ".join(c["key"] for c in course["courses"])
            titles = " + ".join(c["title"] for c in course["courses"])
            print(f"{i}: {codes} - {titles}")
        elif course["type"] == "REQUIREMENT":
            print(f"{i}: {course["key"]}")
        elif course["type"] == "GE":
            print(f"{i}: {course["key"]}")

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
