import json

from pathlib import Path


def upper_conj(c: str | None) -> str:
    return (c or "").upper()


def format_node(node: dict) -> str:
    def fmt(n: dict, depth: int = 0) -> list[str]:
        indent = "  " * depth
        lines: list[str] = []
        node_type = str(n.get("type", "")).upper()
        items = n.get("items") or []
        notes = n.get("notes") or []

        if node_type == "SET":
            join = upper_conj(n.get("conjunction"))
            for i, c in enumerate(items):
                key = c.get("key", "")
                title = c.get("title", "")
                lines.append(f"{indent}{key} - {title}")
                for note in c.get("notes", []) or []:
                    lines.append(f"{indent}  - {note}")
                if i != len(items) - 1 and join:
                    lines.append(f"{indent}{indent}{join}")
            for note in notes:
                lines.append(f"{indent}(Note) {note}")
            return lines

        joins_arr = n["conjunctions"]
        conj_list: list[str]
        conj_list = [upper_conj(j) for j in joins_arr]
        if len(conj_list) < len(items) - 1:
            conj_list += ["OR"] * (len(items) - 1 - len(conj_list))

        for i, ch in enumerate(items):
            lines.extend(fmt(ch, depth + 1))
            if i < len(items) - 1 and conj_list[i]:
                lines.append(f"{indent}{conj_list[i]}")

        for note in notes:
            lines.append(f"{indent}(Note) {note}")
        return lines

    return "\n".join(fmt(node))


def print_articulation(articulation: dict) -> None:
    print(f"\nFrom: {articulation["sending_name"]}")
    node = articulation["sending_articulation"]
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
        course_type = course["type"]
        if course_type == "COURSE":
            print(f"{i}: {course["key"]} - {course.get("title", "")}")
        elif course_type == "SERIES":
            codes = " + ".join(c.get("key", "") for c in course.get("courses", []))
            titles = " + ".join(c.get("title", "") for c in course.get("courses", []))
            print(f"{i}: {codes} - {titles}")
        elif course_type == "MISCELLANEOUS":
            print(f"{i}: {course["key"]}")
        elif course_type == "GE":
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
