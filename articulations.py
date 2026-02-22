import argparse
import orjson as json
from collections import defaultdict

import re
import request
import timeit

from classes import (
    CategoryCode,
    AgreementType,
    Course,
    Series,
    SeriesCourse,
    SendingSeries,
    SendingSeriesCourse,
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

from agreements import get_agreements, get_local_agreement
from institutions import get_institutions
from util import write_json


# Saves and uses raw ASSIST.org JSON files on disk
# Just here so we don't have to keep making requests for every little change
use_local_agreement_data = False

CC_REGISTRY = {
    "colleges": {},
    "courses": {}
}


class UniversitySession:
    def __init__(self, university: Institution):
        self.university = university

        self.courses: dict[str, ReceivingCourse] = {}
        self.series: dict[str, ReceivingSeries] = {}
        self.requirements: dict[str, ReceivingRequirement] = {}
        self.ges: dict[str, ReceivingGE] = {}

        self.majors: dict[str, Major] = {}
        self.departments: dict[str, Department] = {}
        # self.prefixes: dict[str, Department] = {}
        self.ge_categories: dict[str, Major] = {}

    @staticmethod
    def _merge_requirement_container(existing_container, new_container):
        existing_keys = {item.get_unique_key() for item in existing_container.courses}

        for item in new_container.courses:
            if item.get_unique_key() not in existing_keys:
                existing_container.courses.append(item)

    def add_major(self, major: Major):
        if major.name not in self.majors:
            self.majors[major.name] = major
        else:
            self._merge_requirement_container(self.majors[major.name], major)

    def add_department(self, dept: Department):
        if dept.name not in self.departments:
            self.departments[dept.name] = dept
        else:
            self._merge_requirement_container(self.departments[dept.name], dept)

    # def add_prefix(self, dept: Department):
    #     if dept.name not in self.prefixes:
    #         self.prefixes[dept.name] = dept
    #     else:
    #         self.merge_requirement_container(self.prefixes[dept.name], dept)

    def add_ge(self, ge: Major):
        if ge.name not in self.ge_categories:
            self.ge_categories[ge.name] = ge
        else:
            self._merge_requirement_container(self.ge_categories[ge.name], ge)


class AgreementProcessor:
    def __init__(self, session: UniversitySession, college: Institution):
        self.session = session
        self.college = college
        self.template_id_map = {}  # Maps the templateCellId -> (target_dict, unique_key) for GE articulations

    def process_all_types(self, year_id):
        receiving_id = self.session.university.id
        sending_id = self.college.id

        has_major, has_dept, has_prefix, has_ge = get_available_categories(receiving_id, sending_id, year_id)

        if has_major:
            self._handle_agreement(year_id, AgreementType.ALL_MAJORS, self.session.add_major)

        if has_dept:
            self._handle_agreement(year_id, AgreementType.ALL_DEPTS, self.session.add_department)

        # if has_prefix:
        #     self._handle_agreement(year_id, AgreementType.ALL_PREFIXES, self.session.add_prefix)

        if has_ge:
            self._handle_agreement(year_id, AgreementType.ALL_GE, self.session.add_ge)

    def _handle_agreement(self, year_id, agreement_type, storage_callback):
        receiving_id = self.session.university.id
        sending_id = self.college.id

        raw_agreement = get_all_agreement(receiving_id, sending_id, year_id, agreement_type)

        if agreement_type in [AgreementType.ALL_MAJORS, AgreementType.ALL_GE]:
            results = self.process_majors_ges_layout(raw_agreement)
        else:
            results = self.process_dept_prefix_layout(raw_agreement)

        for item in results:
            storage_callback(item)

    def process_articulation(self, articulation_wrapper):
        # Supports wrapped (for majors/GEs) and unwrapped (departments/prefixes) formats
        # We originally did the wrapped agreements for everything but major/GE agreements
        # have some GEs that require the template cell IDs from the unwrapped agreements
        if "articulation" in articulation_wrapper:
            articulation = articulation_wrapper["articulation"]
            template_cell_id = articulation_wrapper.get("templateCellId")
        else:
            articulation = articulation_wrapper
            template_cell_id = None

        target_dict = None
        key = None
        art_type = articulation["type"]

        if art_type == "Course":
            course = ReceivingCourse.from_dict(articulation["course"])
            key = course.get_unique_key()
            target_dict = self.session.courses
            if key not in target_dict:
                target_dict[key] = course
        elif art_type == "Series":
            s = ReceivingSeries.from_dict(articulation["series"])
            key = s.get_unique_key()
            target_dict = self.session.series
            if key not in target_dict:
                target_dict[key] = s
        elif art_type == "Requirement":
            req = ReceivingRequirement.from_dict(articulation["requirement"])
            key = req.get_unique_key()
            target_dict = self.session.requirements
            if key not in target_dict:
                target_dict[key] = req
        elif art_type == "GeneralEducation":
            ge = ReceivingGE.from_dict(articulation["generalEducationArea"])
            key = ge.get_unique_key()
            target_dict = self.session.ges
            if key not in target_dict:
                target_dict[key] = ge
        elif art_type == "Transferability":
            if template_cell_id and template_cell_id in self.template_id_map:
                target_dict, key = self.template_id_map[template_cell_id]

        sending_payload = articulation["sendingArticulation"]

        if target_dict and sending_payload and key in target_dict:
            processed_sending = process_sending_articulation(sending_payload)

            if processed_sending:
                articulation_key = processed_sending.get_unique_key()
                receiving_item = target_dict[key]

                if articulation_key not in receiving_item.articulations:
                    receiving_item.articulations[articulation_key] = ArticulationItem(
                        articulation=processed_sending,
                        sending_id=self.college.id
                    )

        return art_type, key

    # Processes all the courses in a major's template assets
    # Returns a dictionary where the key is the unique course ID and the value is the Course object
    def process_major_ge_template_assets(self, template_assets: list[dict]):
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
                            cell_id = cell.get("id")

                            if cell["type"] == "Course":
                                obj = ReceivingCourse.from_dict(cell["course"])
                                target_dict = self.session.courses
                            elif cell["type"] == "Series":
                                obj = ReceivingSeries.from_dict(cell["series"])
                                target_dict = self.session.series
                            elif cell["type"] == "Requirement":
                                obj = ReceivingRequirement.from_dict(cell["requirement"])
                                target_dict = self.session.requirements
                            elif cell["type"] == "GeneralEducation":
                                obj = ReceivingGE.from_dict(cell["generalEducationArea"])
                                target_dict = self.session.ges
                            elif cell["type"] in ["CSUGE", "IGETC", "CALGETC"]:
                                ge_payload = cell[cell["type"].lower()]
                                ge_payload["id"] = cell_id
                                obj = ReceivingGE.from_dict(ge_payload)
                                target_dict = self.session.ges
                            else:
                                continue

                            key = obj.get_unique_key()
                            if key not in target_dict:
                                target_dict[key] = obj

                            if cell_id:
                                self.template_id_map[cell_id] = (target_dict, key)

                            all_requirements.append(target_dict[key])

            majors.append(Major(name=name, courses=all_requirements))

        return majors

    def process_major_ge_articulations(self, articulations: list[dict]):
        for cell in articulations:
            self.process_articulation(cell)

    def process_majors_ges_layout(self, agreement: dict):
        result = agreement["result"]

        if result is None:
            print("    Agreement does not have an 'All' section.")
            return []

        if agreement["result"]["type"] not in [AgreementType.ALL_MAJORS, AgreementType.ALL_GE]:
            print("    Incorrect processing type for agreement")
            return []

        template_assets: list[dict] = load_template_assets(agreement)
        categories = self.process_major_ge_template_assets(template_assets)

        articulations: list[dict] = json.loads(result["articulations"])
        self.process_major_ge_articulations(articulations)

        return categories

    def process_dept_prefix_articulations(self, depts_prefixes: list[dict]):
        all_departments: list[Department] = []

        for cell in depts_prefixes:
            name = cell["name"]
            all_requirements: list[Course | Series | Requirement | GeneralEducation] = []
            articulation = cell["articulations"]
            for art in articulation:
                art_type, key = self.process_articulation(art)

                if art_type == "Course" and key in self.session.courses:
                    all_requirements.append(self.session.courses[key])
                elif art_type == "Series" and key in self.session.series:
                    all_requirements.append(self.session.series[key])
                elif art_type == "Requirement" and key in self.session.requirements:
                    all_requirements.append(self.session.requirements[key])
                elif art_type == "GeneralEducation" and key in self.session.ges:
                    all_requirements.append(self.session.ges[key])

            all_departments.append(Department(name=name, courses=all_requirements))

        return all_departments

    def process_dept_prefix_layout(self, agreement: dict):
        result = agreement["result"]

        if result is None:
            print(f"Agreement does not have an 'All' section.")
            return []

        if result["type"] not in [AgreementType.ALL_DEPTS, AgreementType.ALL_PREFIXES]:
            print("Incorrect processing type for agreement")
            return []

        articulations: list[dict] = json.loads(result["articulations"])
        sections = self.process_dept_prefix_articulations(articulations)

        return sections


def get_categories(receiving_id, sending_id, year_id) -> list[dict]:
    url = (f"https://www.assist.org/api/agreements/categories"
           f"?receivingInstitutionId={receiving_id}"
           f"&sendingInstitutionId={sending_id}"
           f"&academicYearId={year_id}")

    if use_local_agreement_data:
        path = f"raw_agreements/{receiving_id}/{sending_id}_{year_id}_Categories.json"
        return get_local_agreement(path, url)

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

    if use_local_agreement_data:
        path = f"raw_agreements/{receiving_id}/{sending_id}_{year_id}_{agreement_type.value}.json"
        return get_local_agreement(path, url)

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


def process_sending_articulation(sending_articulation: dict):
    raw_groups = sending_articulation["items"]

    if len(raw_groups) == 0:
        return None

    groups_by_position: dict[int, SendingSeries] = {}
    max_position = -1

    for group in raw_groups:
        pos = group["position"]
        max_position = max(max_position, pos)

        group_items = group.get("items")

        # For "advisements" like "Select 1 course from the following" that appear in the box but is not a course.
        # The issue is that the advisements use the "position" key, so removing it throws off the rest of the positions,
        # which messes up the conjunctions (since we check end_pos == start_pos + 1).
        # So we just map the original positions to our array indices later.
        if group_items is None:
            continue

        group_items.sort(key=lambda x: x["position"])

        courses: list[SeriesCourse] = []
        sending_courses: list[SendingSeriesCourse] = []

        for item in group_items:
            if item["type"] == "Course":
                sc = SeriesCourse.from_dict(item)
                courses.append(sc)

                CC_REGISTRY["courses"][sc.course_id] = {
                    "prefix_desc": sc.prefix_desc,
                    "prefix": sc.prefix,
                    "number": sc.number,
                    "title": sc.title,
                    "min_units": sc.min_units,
                    "max_units": sc.max_units,
                    "course_id": sc.course_id,
                    "prefix_id": sc.prefix_id
                }

                sending_courses.append(SendingSeriesCourse(
                    course_id=sc.course_id,
                    position=sc.position,
                    notes=sc.notes
                ))

        raw_attributes = group.get("attributes", [])
        raw_attributes.sort(key=lambda x: x["position"])
        group_notes = [attribute["content"] for attribute in raw_attributes if "content" in attribute]

        internal_conjunction = group.get("courseConjunction", "And").upper()
        series_option = SendingSeries(
            conjunction=internal_conjunction,
            courses=sending_courses,
            notes=group_notes
        )
        groups_by_position[pos] = series_option

    # Map to the original ASSIST positions due to the advisements issue
    # It's better doing it this way in case there are multiple advisements in a cell
    sorted_positions = sorted(groups_by_position.keys())
    ordered_items = [groups_by_position[pos] for pos in sorted_positions]
    pos_to_index = {original_pos: new_index for new_index, original_pos in enumerate(sorted_positions)}

    raw_conjunctions = sending_articulation.get("courseGroupConjunctions") or []
    ordered_conjunctions = ["OR"] * (len(ordered_items) - 1)

    for conjunction in raw_conjunctions:
        start_pos = conjunction["sendingCourseGroupBeginPosition"]
        end_pos = conjunction["sendingCourseGroupEndPosition"]
        val = conjunction["groupConjunction"]

        # Find out where original positions ended up in the filtered list
        if start_pos in pos_to_index and end_pos in pos_to_index:
            mapped_start = pos_to_index[start_pos]
            mapped_end = pos_to_index[end_pos]

            if mapped_end == mapped_start + 1 and mapped_start < len(ordered_conjunctions):
                ordered_conjunctions[mapped_start] = val.upper()

    global_attributes = sending_articulation.get("attributes") or []
    global_attributes.sort(key=lambda x: x["position"])
    global_notes = [attribute["content"] for attribute in global_attributes if "content" in attribute]

    # Normalize multi-group articulations where each group only has one course
    # We can just compress it all into a single group if they all share the same conjunction
    new_items = []
    new_conjunctions = []

    i = 0
    while i < len(ordered_items):
        current_item = ordered_items[i]

        # Current group must have one course and have a conjunction after it
        if len(current_item.courses) == 1 and i < len(ordered_conjunctions):
            target_conjunction = ordered_conjunctions[i]

            merge_block = [current_item]
            j = i + 1

            # Keep looking ahead for more of those things connected by the same conjunction
            while (j < len(ordered_items) and len(ordered_items[j].courses) == 1
                   and ordered_conjunctions[j - 1] == target_conjunction):
                merge_block.append(ordered_items[j])
                j += 1

            if len(merge_block) > 1:
                flattened_courses = []

                for item in merge_block:
                    course = item.courses[0]
                    course_notes = course.notes if course.notes else []
                    group_notes = item.notes if item.notes else []

                    # Group-level notes for single-course groups are basically just course notes
                    course.notes = course_notes + group_notes
                    flattened_courses.append(course)

                merged_series = SendingSeries(
                    conjunction=target_conjunction,
                    courses=flattened_courses,
                    notes=[]
                )

                new_items.append(merged_series)

                i = j
                if i < len(ordered_items):
                    new_conjunctions.append(ordered_conjunctions[i - 1])
                continue

        # If no merge happened for this item then just keep it the same
        new_items.append(current_item)
        if i < len(ordered_conjunctions):
            new_conjunctions.append(ordered_conjunctions[i])
        i += 1

    ordered_items = new_items
    ordered_conjunctions = new_conjunctions

    return SendingArticulation(
        items=ordered_items,
        conjunctions=ordered_conjunctions,
        notes=global_notes
    )


def save_university_data(session: UniversitySession):
    base_path = f"data/universities/{session.university.name}"
    print(f"Transforming data structures...")

    all_objects = (list(session.courses.values()) + list(session.series.values()) +
                   list(session.requirements.values()) + list(session.ges.values()))

    for obj in all_objects:
        if hasattr(obj, "articulations") and isinstance(obj.articulations, dict):
            obj.articulations = list(obj.articulations.values())

    def get_natural_sort_key(text):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

    def get_sort_key(thing):
        if isinstance(thing, ReceivingCourse):
            return 0, thing.prefix, get_natural_sort_key(thing.number), ""
        elif isinstance(thing, ReceivingSeries):
            if thing.courses:
                first_course = thing.courses[0]
                return 0, first_course.prefix, get_natural_sort_key(first_course.number), thing.name
            return 0, thing.name, [], ""
        elif isinstance(thing, ReceivingRequirement):
            return 1, thing.name, [], ""
        elif isinstance(thing, ReceivingGE):
            code_str = thing.code if thing.code else thing.name
            return 2, get_natural_sort_key(code_str), [], thing.name
        return 3, "", [], ""

    print("Writing Subject files...")
    subjects_metadata = {}
    items_by_prefix = defaultdict(list)

    for course in session.courses.values():
        items_by_prefix[course.prefix].append(course)

        if course.prefix not in subjects_metadata:
            subjects_metadata[course.prefix] = {
                "name": course.prefix_desc,
                "prefix": course.prefix
            }

    for s in session.series.values():
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
        # We have to add "subj_" because Windows does not like some subject names
        write_json(item_list, f"{base_path}/Subjects/subj_{prefix}.json")

    print(f"Writing Major files...")
    major_names = sorted(list(session.majors.keys()))
    write_json(major_names, f"{base_path}/Majors/majors.json")

    for major_name, major_obj in session.majors.items():
        major_obj.courses.sort(key=get_sort_key)
        safe_major = major_name.replace("/", "-").replace(":", "").replace("*", "=").replace(">", "").strip()
        write_json(major_obj, f"{base_path}/Majors/{safe_major}.json")

    print(f"Writing GE files...")
    existing_ge_keys = set()
    for category in session.ge_categories.values():
        for item in category.courses:
            existing_ge_keys.add(item.get_unique_key())

    missing_ges = [ge for ge in session.ges.values() if ge.get_unique_key() not in existing_ge_keys]

    if missing_ges:
        category_name = "General Education" if len(session.ge_categories) == 0 else "General Education (From Majors)"

        if category_name not in session.ge_categories:
            session.ge_categories[category_name] = Major(category_name, courses=[])

        session.ge_categories[category_name].courses.extend(missing_ges)

    for category in session.ge_categories.values():
        category.courses.sort(key=get_sort_key)

    write_json(list(session.ge_categories.values()), f"{base_path}/GEs/ge_categories.json")


def has_no_agreements(agreement_year: int, university: Institution, college: Institution):
    if agreement_year == -1:
        print(f"    {college.name} and {university.name} have no agreements.")
        return True

    if agreement_year < 74:
        print(f"    {college.name} and {university.name} have no modernized agreements.")
        return True

    return False


def get_desired_institutions():
    parser = argparse.ArgumentParser(description="ASSIST.org Scraper")
    parser.add_argument("--types", nargs="+", default=["CSU", "UC", "AICCU"],
                        help="University segments to include (e.g. --types UC CSU AICCU)")
    parser.add_argument("--colleges", nargs="+", help="Specific college names or IDs")
    parser.add_argument("--universities", nargs="+", help="Specific university names or IDs")
    parser.add_argument("--after-college", type=str, help="College name or ID to start from")
    parser.add_argument("--after-university", type=str, help="University name or ID to start from")

    args = parser.parse_args()

    all_institutions = get_institutions(create_new_if_existing=not use_local_agreement_data)
    all_colleges = sorted([i for i in all_institutions if i.category == "CCC"], key=lambda i: i.name)
    all_universities = [i for i in all_institutions if i.category in [t.upper() for t in args.types]]

    def resolve_offset(input_val, search_list):
        if not input_val:
            return None

        if input_val.isdigit():
            return int(input_val)

        for institution in search_list:
            if institution.name.lower() == input_val.lower():
                return int(institution.id)

        print(f"Could not find institution named '{input_val}'. Offset ignored.")
        return None

    college_offset = resolve_offset(args.after_college, all_colleges)
    university_offset = resolve_offset(args.after_university, all_universities)

    def parse_criteria(input_list):
        if not input_list:
            return [], []
        ids = [int(x) for x in input_list if x.isdigit()]
        names = [x for x in input_list if not x.isdigit()]
        return ids, names

    college_ids, college_names = parse_criteria(args.colleges)
    university_ids, university_names = parse_criteria(args.universities)

    def apply_filters(target_list, ids, names, offset):
        if ids or names:
            target_list = [i for i in target_list if i.id in ids or i.name in names]
        if offset is not None:
            target_list = [i for i in target_list if int(i.id) >= offset]
        return target_list

    colleges = apply_filters(all_colleges, college_ids, college_names, college_offset)
    universities = apply_filters(all_universities, university_ids, university_names, university_offset)

    return colleges, universities


def main():
    start_time = timeit.default_timer()

    colleges, universities = get_desired_institutions()

    if not colleges or not universities:
        print("No institutions found matching those filters.")
        return

    for college in colleges:
        CC_REGISTRY["colleges"][college.id] = college.name

    for university in universities:
        print(f"Getting articulations for {university.name} (ID {university.id}).")

        all_agreements = get_agreements(university.id, use_local_agreement_data)
        session = UniversitySession(university)

        for college in colleges:
            agreement_year = all_agreements.get(college.id, -1)
            if has_no_agreements(agreement_year, university, college):
                continue

            print(f"    Fetching articulations for {college.name} -> {university.name}...")
            processor = AgreementProcessor(session, college)
            processor.process_all_types(agreement_year)

        save_university_data(session)
        print()

    print("Writing CC registry...")
    write_json(CC_REGISTRY, "data/colleges/cc_registry.json")

    end_time = timeit.default_timer()
    print(f"Execution time: {end_time - start_time:.2f}s")


if __name__ == "__main__":
    main()
