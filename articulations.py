import json
from collections import defaultdict

import request
import os
import re
import sys

from classes import (
    CategoryCode,
    AgreementType,
    Course,
    Series,
    SeriesCourse,
    Requirement,
    GeneralEducation,
    ArticulationItem,
    ReceivingCourse,
    ReceivingSeries,
    ReceivingRequirement,
    ReceivingGE,
    SendingArticulation,
    Major,
    Department,
    Institution
)

from agreements import get_agreements
from institutions import get_institutions


def clean_and_convert_json(obj):
    if hasattr(obj, "to_dict"):
        obj = obj.to_dict()

    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            obj[k] = clean_and_convert_json(v)

        if "courses" in obj and isinstance(obj.get("courses"), list) and "conjunction" in obj:
            if len(obj["courses"]) == 1:
                obj["conjunction"] = None

                if isinstance(obj["courses"][0], dict):
                    obj["courses"][0].pop("position", None)
    elif isinstance(obj, list):
        return [clean_and_convert_json(item) for item in obj]

    return obj


def write_json(json_dict, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cleaned_data = clean_and_convert_json(json_dict)

    with open(path, "w") as file:
        json.dump(cleaned_data, file, indent=4)


def get_categories(receiving_id, sending_id, year_id) -> list[dict]:
    url = (f"https://www.assist.org/api/agreements/categories"
           f"?receivingInstitutionId={receiving_id}&sendingInstitutionId={sending_id}&academicYearId={year_id}")

    # [{
    #     "label": "Major",
    #     "code": "major",
    #     "reportType": 3,
    #     "reportCategoryType": 0,
    #     "courseTransferItemType": 0,
    #     "hasReports": true
    # }, {
    #     "label": "Department",
    #     "code": "dept",
    #     "reportType": 2,
    #     "reportCategoryType": 0,
    #     "courseTransferItemType": 0,
    #     "hasReports": true
    # }, {
    #     "label": "Prefix",
    #     "code": "prefix",
    #     "reportType": 10,
    #     "reportCategoryType": 0,
    #     "courseTransferItemType": 0,
    #     "hasReports": true
    # }, {
    #     "label": "General Education / Breadth",
    #     "code": "breadth",
    #     "reportType": 1,
    #     "reportCategoryType": 0,
    #     "courseTransferItemType": 0,
    #     "hasReports": true
    # }]

    return request.get(url=url).json()


def get_available_categories(receiving_id, sending_id, year_id) -> tuple[bool, bool, bool, bool]:
    categories = get_categories(receiving_id, sending_id, year_id)
    has_major = has_dept = has_prefix = has_ge = False

    for category in categories:
        if category["code"] == CategoryCode.MAJOR.value:
            has_major = category["hasReports"]
        elif category["code"] == CategoryCode.DEPT.value:
            has_dept = category["hasReports"]
        elif category["code"] == CategoryCode.PREFIX.value:
            has_prefix = category["hasReports"]
        elif category["code"] == CategoryCode.GE.value:
            has_ge = category["hasReports"]

    return has_major, has_dept, has_prefix, has_ge


def get_all_agreement(receiving_id, sending_id, year_id, agreement_type: AgreementType) -> dict:
    url = (f"https://www.assist.org/api/articulation/Agreements"
           f"?Key={year_id}/{sending_id}/to/{receiving_id}/{agreement_type.value}")

    # {
    #     "result": {
    #         "name": "All Majors",
    #         "type": "AllMajors",
    #         "publishDate": "2026-02-17T21:58:23.7438318",
    #         "receivingInstitution":
    #         "sendingInstitution":
    #         "academicYear":
    #         "templateAssets":
    #         "articulations":
    #         "catalogYear":
    #     },
    #     "validationFailure": null,
    #     "isSuccessful": true
    # }

    return request.get(url=url).json()


def load_template_assets(agreement: dict) -> list[dict] | None:
    if agreement["result"]["templateAssets"] is None:
        return None

    # dict_keys(['name', 'templateAssets'])
    return json.loads(agreement["result"]["templateAssets"])


# Processes all the courses in a major's template assets
# Returns a dictionary where the key is the unique course ID and the value is the Course object
def process_major_ge_template_assets(
        template_assets: list[dict],
        courses: dict[str, ReceivingCourse],
        series: dict[str, ReceivingSeries],
        requirements: dict[str, ReceivingRequirement],
        ges: dict[str, ReceivingGE],
):
    majors: list[Major] = []

    for major in template_assets:
        name = major["name"]
        all_requirements: list[Course | Series | Requirement | GeneralEducation] = []

        assets = major["templateAssets"]
        for template in assets:
            if template["type"] != "RequirementGroup":
                continue

            sections: list[dict] = template["sections"]
            for section in sections:
                rows = section.get("rows")

                # Section header or something. Has no requirements
                if rows is None:
                    continue

                for row in rows:
                    cells = row["cells"]
                    for cell in cells:
                        if cell["type"] == "Course":
                            obj = ReceivingCourse.from_dict(cell["course"])
                            target_dict = courses
                        elif cell["type"] == "Series":
                            obj = ReceivingSeries.from_dict(cell["series"])
                            target_dict = series
                        elif cell["type"] == "Requirement":
                            obj = ReceivingRequirement.from_dict(cell["requirement"])
                            target_dict = requirements
                        elif cell["type"] == "GeneralEducation":
                            obj = ReceivingGE.from_dict(cell["generalEducationArea"])
                            target_dict = ges
                        else:
                            continue

                        key = obj.get_unique_key()
                        if key not in target_dict:
                            target_dict[key] = obj

                        all_requirements.append(target_dict[key])

        majors.append(Major(name=name, courses=all_requirements))

    return majors


def process_sending_articulation(sending_articulation: dict):
    raw_groups = sending_articulation["items"]

    if len(raw_groups) == 0:
        return None

    groups_by_position: dict[int, Series] = {}
    max_position = -1

    for group in raw_groups:
        pos = group["position"]
        max_position = max(max_position, pos)

        group_items = group["items"]
        group_items.sort(key=lambda x: x["position"])

        courses: list[SeriesCourse] = []
        for item in group_items:
            if item["type"] == "Course":
                courses.append(SeriesCourse.from_dict(item))

        raw_attributes = group.get("attributes", [])
        raw_attributes.sort(key=lambda x: x["position"])
        group_notes = [attribute["content"] for attribute in raw_attributes if "content" in attribute]

        internal_conjunction = group.get("courseConjunction", "And").upper()
        series_option = Series(
            conjunction=internal_conjunction,
            name=", ".join(f"{course.prefix} {course.number}" for course in courses),
            courses=courses,
            notes=group_notes
        )
        groups_by_position[pos] = series_option

    ordered_items = [groups_by_position[pos] for pos in sorted(groups_by_position.keys())]
    raw_conjunctions = sending_articulation.get("courseGroupConjunctions", [])
    ordered_conjunctions = ["OR"] * (len(ordered_items) - 1)

    for conjunction in raw_conjunctions:
        start_pos = conjunction["sendingCourseGroupBeginPosition"]
        end_pos = conjunction["sendingCourseGroupEndPosition"]
        val = conjunction["groupConjunction"]

        if end_pos == start_pos + 1 and start_pos < len(ordered_conjunctions):
            ordered_conjunctions[start_pos] = val.upper()

    global_attributes = sending_articulation.get("attributes", [])
    global_attributes.sort(key=lambda x: x["position"])
    global_notes = [attribute["content"] for attribute in global_attributes if "content" in attribute]

    return SendingArticulation(
        items=ordered_items,
        conjunctions=ordered_conjunctions,
        notes=global_notes
    )


def process_articulation(
        articulation,
        courses: dict[str, ReceivingCourse],
        series: dict[str, ReceivingSeries],
        requirements: dict[str, ReceivingRequirement],
        ges: dict[str, ReceivingGE],
        college_info: Institution
):
    target_dict = None
    key = None
    art_type = articulation["type"]

    if art_type == "Course":
        course = Course.from_dict(articulation["course"])
        key = course.get_unique_key()
        target_dict = courses
    elif art_type == "Series":
        s = Series.from_dict(articulation["series"])
        key = s.get_unique_key()
        target_dict = series
    elif art_type == "Requirement":
        req = Requirement.from_dict(articulation["requirement"])
        key = req.get_unique_key()
        target_dict = requirements
    elif art_type == "GeneralEducation":
        ge = GeneralEducation.from_dict(articulation["generalEducationArea"])
        key = ge.get_unique_key()
        target_dict = ges

    sending_payload = articulation["sendingArticulation"]

    if target_dict is not None and key in target_dict and sending_payload:
        processed_sending = process_sending_articulation(sending_payload)

        if processed_sending:
            articulation_key = processed_sending.get_unique_key()
            receiving_item = target_dict[key]

            if articulation_key not in receiving_item.articulations:
                receiving_item.articulations[articulation_key] = ArticulationItem(
                    articulation=processed_sending,
                    sending_id=college_info.id,
                    sending_name=college_info.name
                )

    return art_type, key


def process_major_ge_articulations(
        articulations: list[dict],
        courses: dict[str, ReceivingCourse],
        series: dict[str, ReceivingSeries],
        requirements: dict[str, ReceivingRequirement],
        ges: dict[str, ReceivingGE],
        college_info: Institution
):
    for cell in articulations:
        process_articulation(cell["articulation"], courses, series, requirements, ges, college_info)


def process_dept_prefix_articulations(
        depts_prefixes: list[dict],
        courses: dict[str, ReceivingCourse],
        series: dict[str, ReceivingSeries],
        requirements: dict[str, ReceivingRequirement],
        ges: dict[str, ReceivingGE],
        college_info: Institution
):
    all_departments: list[Department] = []

    for cell in depts_prefixes:
        name = cell["name"]
        all_requirements: list[Course | Series | Requirement | GeneralEducation] = []
        articulation = cell["articulations"]
        for art in articulation:
            art_type, key = process_articulation(art, courses, series, requirements, ges, college_info)

            if art_type == "Course" and key in courses:
                all_requirements.append(courses[key])
            elif art_type == "Series" and key in series:
                all_requirements.append(series[key])
            elif art_type == "Requirement" and key in requirements:
                all_requirements.append(requirements[key])
            elif art_type == "GeneralEducation" and key in ges:
                all_requirements.append(ges[key])

        all_departments.append(Department(name=name, courses=all_requirements))

    return all_departments


# Majors and GEs have the same general layout
# I could probably rename this better later
def process_all_majors_ges(
        agreement: dict,
        courses: dict[str, ReceivingCourse],
        series: dict[str, ReceivingSeries],
        requirements: dict[str, ReceivingRequirement],
        ges: dict[str, ReceivingGE],
        college_info: Institution
):
    if agreement["result"]["type"] not in [AgreementType.ALL_MAJORS, AgreementType.ALL_GE]:
        print("Incorrect processing type for agreement")
        return []

    template_assets: list[dict] = load_template_assets(agreement)
    categories = process_major_ge_template_assets(template_assets, courses, series, requirements, ges)

    articulations: list[dict] = json.loads(agreement["result"]["articulations"])
    process_major_ge_articulations(articulations, courses, series, requirements, ges, college_info)

    return categories


# Departments and Prefixes have the same general layout
# I could also probably rename this better later
def process_all_depts_prefixes(
        agreement: dict,
        courses: dict[str, ReceivingCourse],
        series: dict[str, ReceivingSeries],
        requirements: dict[str, ReceivingRequirement],
        ges: dict[str, ReceivingGE],
        college_info: Institution
):
    if agreement["result"]["type"] not in [AgreementType.ALL_DEPTS, AgreementType.ALL_PREFIXES]:
        print("Incorrect processing type for agreement")
        return []

    articulations: list[dict] = json.loads(agreement["result"]["articulations"])
    sections = process_dept_prefix_articulations(articulations, courses, series, requirements, ges, college_info)

    return sections


def process_agreements(
        receiving_id,
        sending_id,
        year_id,
        courses: dict[str, ReceivingCourse],
        series: dict[str, ReceivingSeries],
        requirements: dict[str, ReceivingRequirement],
        ges: dict[str, ReceivingGE],
        uni_majors: dict[str, Major],
        uni_depts: dict[str, Department],
        # uni_prefixes: dict[str, Department],
        uni_ge_categories: dict[str, Major],
        college_info
):
    def merge_requirements(existing_container, new_container):
        existing_keys = {item.get_unique_key() for item in existing_container.courses}
        for item in new_container.courses:
            key = item.get_unique_key()
            if key not in existing_keys:
                existing_container.courses.append(item)
                existing_keys.add(key)

    def process(agreement_type, processing_function, uni_dict):
        all_agreement = get_all_agreement(receiving_id, sending_id, year_id, agreement_type)
        current = processing_function(all_agreement, courses, series, requirements, ges, college_info)

        for item in current:
            if item.name not in uni_dict:
                uni_dict[item.name] = item
            else:
                merge_requirements(uni_dict[item.name], item)

    has_major, has_dept, has_prefix, has_ge = get_available_categories(receiving_id, sending_id, year_id)

    if has_major:
        process(AgreementType.ALL_MAJORS, process_all_majors_ges, uni_majors)

    if has_dept:
        process(AgreementType.ALL_DEPTS, process_all_depts_prefixes, uni_depts)

    # if has_prefix:
    #     process(AgreementType.ALL_PREFIXES, process_all_depts_prefixes, uni_prefixes)

    if has_ge:
        process(AgreementType.ALL_GE, process_all_majors_ges, uni_ge_categories)


def save_university_data(
        university_name,
        courses,
        series,
        requirements,
        ges,
        majors,
        # depts: dict[str, Department],
        # prefixes: dict[str, Department],
        ge_categories
):
    base_path = f"data/{university_name}"
    print(f"Transforming data structures...")

    all_objects = list(courses.values()) + list(series.values()) + list(requirements.values()) + list(ges.values())

    for obj in all_objects:
        if hasattr(obj, "articulations") and isinstance(obj.articulations, dict):
            obj.articulations = list(obj.articulations.values())

    def get_natural_sort_key(text):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

    def get_sort_key(thing):
        if isinstance(thing, ReceivingCourse):
            return 0, thing.prefix, get_natural_sort_key(thing.number)
        elif isinstance(thing, ReceivingSeries):
            return 0, thing.name, []
        elif isinstance(thing, ReceivingRequirement):
            return 1, thing.name, []
        elif isinstance(thing, ReceivingGE):
            return 2, thing.name, []
        return 3, "", []

    print("Writing Subject files...")
    subjects_metadata = {}
    items_by_prefix = defaultdict(list)

    for course in courses.values():
        items_by_prefix[course.prefix].append(course)

        if course.prefix not in subjects_metadata:
            subjects_metadata[course.prefix] = {
                "name": course.prefix_desc,
                "prefix": course.prefix
            }

    for s in series.values():
        involved_prefixes = {c.prefix for c in s.courses}

        for course in s.courses:
            if course.prefix not in subjects_metadata:
                subjects_metadata[course.prefix] = {
                    "name": course.prefix_desc,
                    "prefix": course.prefix
                }

        for prefix in involved_prefixes:
            items_by_prefix[prefix].append(s)

    sorted_metadata = sorted(list(subjects_metadata.values()), key=lambda x: x["prefix"])
    write_json(sorted_metadata, f"{base_path}/Subjects/subjects.json")

    for prefix, item_list in items_by_prefix.items():
        item_list.sort(key=get_sort_key)
        write_json(item_list, f"{base_path}/Subjects/{prefix}.json")

    print(f"Writing Major files...")
    major_names = sorted(list(majors.keys()))
    write_json(major_names, f"{base_path}/Majors/majors.json")

    for major_name, major_obj in majors.items():
        major_obj.courses.sort(key=get_sort_key)
        safe_major = major_name.replace("/", "-").replace(":", "").strip()
        write_json(major_obj, f"{base_path}/Majors/{safe_major}.json")

    print(f"Writing GE files...")
    existing_ge_keys = set()
    for category in ge_categories.values():
        for item in category.courses:
            existing_ge_keys.add(item.get_unique_key())

    missing_ges = [ge for ge in ges.values() if ge.get_unique_key() not in existing_ge_keys]

    if missing_ges:
        missing_ges.sort(key=get_sort_key)
        category_name = "General Education" if len(ge_categories) == 0 else "General Education (From Majors)"

        if category_name not in ge_categories:
            ge_categories[category_name] = Major(category_name, courses=[])

        ge_categories[category_name].courses.extend(missing_ges)

    write_json(list(ge_categories.values()), f"{base_path}/GEs/ge_categories.json")


def run(desired_universities: list):
    if desired_universities is None or len(desired_universities) == 0:
        desired_universities = ["CSU", "UC", "AICCU"]

    institutions = get_institutions(create_new_if_existing=False)
    colleges = sorted([i for i in institutions if i.category == "CCC"], key=lambda i: i.name)
    universities = [i for i in institutions if i.category in desired_universities]

    for university in universities:
        print(f"Getting articulations for {university.name} (ID {university.id}).")
        all_agreements = get_agreements(university.id)

        uni_courses: dict[str, ReceivingCourse] = {}
        uni_series: dict[str, ReceivingSeries] = {}
        uni_requirements: dict[str, ReceivingRequirement] = {}
        uni_ges: dict[str, ReceivingGE] = {}

        uni_majors: dict[str, Major] = {}
        uni_depts: dict[str, Department] = {}
        # uni_prefixes: dict[str, Department] = {}
        uni_ge_categories: dict[str, Major] = {}

        for college in colleges:
            agreement_year = all_agreements.get(college.id, -1)

            if agreement_year == -1:
                print(f"    {college.name} and {university.name} have no agreements.")
                continue

            if agreement_year < 74:
                print(f"    {college.name} and {university.name} have no modernized agreements.")
                continue

            print(f"    Fetching articulations for {college.name} -> {university.name}...")

            process_agreements(
                university.id,
                college.id,
                agreement_year,
                uni_courses,
                uni_series,
                uni_requirements,
                uni_ges,
                uni_majors,
                uni_depts,
                # uni_prefixes,
                uni_ge_categories,
                college
            )

        save_university_data(
            university.name,
            uni_courses,
            uni_series,
            uni_requirements,
            uni_ges,
            uni_majors,
            # uni_depts,
            # uni_prefixes,
            uni_ge_categories
        )

        print()


def main():
    desired_universities = [u.upper() for u in sys.argv[1:]]

    if len(desired_universities) > 3:
        print("Invalid number of universities provided.")
        print("Choose from CSU, UC, and AICCU.")
    else:
        run(desired_universities)


if __name__ == "__main__":
    main()
