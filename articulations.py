import json
import request
import sys

from classes import (
    Conjunction,
    Institution,
    BasicCourse,
    SendingCourse,
    SetArticulation,
    GroupArticulation,
    ReceivingType,
    ReceivingSeries,
    ReceivingRequirement,
    ReceivingItem
)
from pathlib import Path

from agreements import get_agreements
from institutions import get_institutions


def json_if_str(x):
    return json.loads(x) if isinstance(x, str) else x


def make_series_key(members: list[BasicCourse]) -> str:
    tokens = []
    prev_prefix = None

    for member in members or []:
        if not tokens or member.prefix != prev_prefix:
            tokens.append(member.key)
        else:
            tokens.append(member.number)

        prev_prefix = member.prefix

    return " + ".join(tokens)


def parse_course_group(group: dict) -> SetArticulation:
    conjunction = group.get("courseConjunction", "").strip().lower()
    items = sorted(group.get("items", []), key=lambda x: x.get("position", 0))
    courses = [SendingCourse.from_assist(item) for item in items if item.get("type") == "Course"]
    group_level_notes: list[str] = [a.get("content") for a in group.get("attributes", []) if a.get("content")]

    if conjunction == "or":
        conj = Conjunction.OR if len(courses) > 1 else None
        return SetArticulation(conjunction=conj, items=courses, notes=group_level_notes)

    if conjunction == "and":
        conj = Conjunction.AND if len(courses) > 1 else None
        return SetArticulation(conjunction=conj, items=courses, notes=group_level_notes)

    return SetArticulation(conjunction=None, items=courses, notes=group_level_notes)


def combine_groups(groups: list[SetArticulation | GroupArticulation], group_conjunctions: list[dict], group_positions: list[int]) -> SetArticulation | GroupArticulation:
    sets: list[SetArticulation] = []

    for group in groups:
        if isinstance(group, GroupArticulation):
            for child in group.items:
                sets.append(child)
        else:
            sets.append(group)

    n = len(sets)

    if n == 0:
        return GroupArticulation(conjunctions=[], items=[], notes=[])

    if n == 1 and not group_conjunctions:
        return groups[0]

    conjunctions: list[Conjunction | None] = [None] * max(0, n - 1)
    for group in group_conjunctions or []:
        conjunction = group.get("groupConjunction", "And").strip().title()
        begin = int(group.get("sendingCourseGroupBeginPosition", 0))
        end = int(group.get("sendingCourseGroupEndPosition", max(0, n - 1)))

        i = next((idx for idx, pos in enumerate(group_positions) if pos >= begin), None)
        j = next((idx for idx in range(len(group_positions) - 1, -1, -1) if group_positions[idx] <= end), None)
        if i is None or j is None or i >= j:
            continue

        for k in range(i, j):
            conjunctions[k] = Conjunction.OR if conjunction.lower() == "or" else Conjunction.AND

    for i, c in enumerate(conjunctions):
        if c is None:
            conjunctions[i] = Conjunction.OR

    return GroupArticulation(conjunctions=conjunctions, items=sets, notes=[])


def normalize_node(node: SetArticulation | GroupArticulation) -> SetArticulation | GroupArticulation:
    if isinstance(node, GroupArticulation):
        for i, child in enumerate(node.items):
            node.items[i] = normalize_node(child)

            if isinstance(child, SetArticulation) and (len(node.items[i].items) == 1) and node.items[i].conjunction is not None:
                node.items[i].conjunction = None

        # Flatten groups if they only contain singleton sets with the same conjunction
        if len(node.items) > 1 and len(set(node.conjunctions)) == 1:
            all_singletons = all(isinstance(c, SetArticulation) and len(c.items) == 1 for c in node.items)

            if all_singletons:
                flattened_items = [c.items[0] for c in node.items]
                merged_notes: list[str] = []
                merged_notes.extend(node.notes)

                for c in node.items:
                    if isinstance(c, SetArticulation):
                        merged_notes.extend(c.notes)

                return SetArticulation(
                    conjunction=node.conjunctions[0] if len(flattened_items) > 1 else None,
                    items=flattened_items,
                    notes=merged_notes
                )

        if len(node.items) == 1:
            return node.items[0]

    if isinstance(node, SetArticulation):
        if len(node.items) == 1 and node.conjunction is not None:
            node.conjunction = None

    return node


def build_articulation_tree(sending_articulation: dict | None) -> dict | None:
    if not sending_articulation:
        return None

    reason = sending_articulation.get("noArticulationReason")
    if isinstance(reason, str) and reason.strip():
        return None

    groups_raw = sending_articulation.get("items", [])
    groups_raw = [group for group in groups_raw if group["type"] == "CourseGroup"]
    groups_raw.sort(key=lambda x: x.get("position", 0))

    normalized = [parse_course_group(g) for g in groups_raw]
    group_positions = [int(g.get("position", 0)) for g in groups_raw]

    node = combine_groups(normalized, sending_articulation.get("courseGroupConjunctions", []), group_positions)

    notes: list[str] = [a.get("content") for a in (sending_articulation.get("attributes") or []) if a.get("content")]
    if notes:
        node.notes.extend(notes)

    return normalize_node(node).to_dict()


def request_all_courses(year: int, sending: int, receiving: int, method: str) -> dict:
    url = f"https://www.assist.org/api/articulation/Agreements?Key={year}/{sending}/to/{receiving}/{method}"

    all_courses_json: dict = request.get(url=url).json()
    if not all_courses_json["isSuccessful"]:
        raise FileNotFoundError("Agreement was not found for this combination.")

    return all_courses_json


def get_all_courses_json(agreement_year: int, sending_id: int, receiving_id: int) -> dict | None:
    try:
        return request_all_courses(agreement_year, sending_id, receiving_id, "AllMajors")
    except FileNotFoundError:
        print("All majors agreement was not found. Attempting all departments.")

    try:
        return request_all_courses(agreement_year, sending_id, receiving_id, "AllDepartments")
    except FileNotFoundError:
        print("All departments agreement was not found. Attempting all general education requirements.")

    # Usually, if the departmental agreements are available, the prefix agreements ("AllPrefixes") will be too.
    # So if there is no departmental agreement, we can save a request and skip to the GE requirements.
    try:
        return request_all_courses(agreement_year, sending_id, receiving_id, "AllGeneralEducation")
    except FileNotFoundError:
        print("All general education requirements agreement was not found.")

    return None


def articulation_to_json_dict(articulation: dict) -> dict | None:
    sending = articulation.get("sendingArticulation")

    if sending is None:
        return None

    return build_articulation_tree(sending)


def extract_articulation_rows(result: dict) -> list[dict]:
    articulations = json_if_str(result.get("articulations", [])) or []

    if len(articulations) == 0:
        return articulations

    # All Majors / All General Education
    if isinstance(articulations[0], dict) and "articulations" not in articulations[0]:
        return articulations

    # All Departments or All Prefixes
    flat = []
    for subject in articulations:
        for row in (subject.get("articulations") or []):
            flat.append({"articulation": row})

    return flat


def walk_template_assets(assets) -> list[tuple[str | None, ReceivingItem]]:
    assets = json_if_str(assets)
    out: list[tuple[str | None, ReceivingItem]] = []

    def is_course_dict(d: dict) -> bool:
        return isinstance(d, dict) and all(k in d for k in ("prefix", "courseNumber", "courseTitle"))

    def dfs(node, cell_id=None):
        if isinstance(node, dict):
            cid = node.get("id", cell_id)

            if is_course_dict(node):
                basic_course = BasicCourse.from_assist(node)
                out.append((cid, ReceivingItem.from_receiving(basic_course)))

            series = node.get("series")
            if series is not None:
                courses = [BasicCourse.from_assist(c) for c in series["courses"] if is_course_dict(c)]

                if courses:
                    conjunction = Conjunction(series.get("conjunction").upper())
                    rs = ReceivingSeries(key=make_series_key(courses), conjunction=conjunction, courses=courses)
                    out.append((cid, ReceivingItem.from_receiving(rs)))

            req_tuple = ReceivingRequirement.get_kind_and_key(node)
            if req_tuple is not None:
                kind, key = req_tuple
                req = ReceivingRequirement(kind=kind, key=node[key]["name"].strip())
                out.append((cid, ReceivingItem.from_receiving(req)))

            for k, v in node.items():
                if k != "series":
                    dfs(v, cid)
        elif isinstance(node, list):
            for v in node:
                dfs(v, cell_id)

    dfs(assets, None)

    return out


def extract_template_inventory(template_assets: dict, existing_articulation_cell_ids: set[str]) -> list[ReceivingItem]:
    items = walk_template_assets(template_assets)
    out: list[ReceivingItem] = []
    seen_keys: set[str] = set()

    for cell_id, item in items:
        if cell_id and cell_id in existing_articulation_cell_ids:
            continue  # already has an articulation row

        if item.key in seen_keys:
            continue

        seen_keys.add(item.key)
        out.append(item)

    return out


def get_course_articulation(articulation: dict, node_dict: dict, seen: set[str], out: list[ReceivingItem]) -> None:
    receiving = articulation["course"]
    basic_course = BasicCourse.from_assist(receiving)

    if basic_course.key in seen:
        return

    seen.add(basic_course.key)
    out.append(ReceivingItem.from_receiving(basic_course, node_dict))


def get_series_articulation(articulation: dict, node_dict: dict, seen: set[str], out: list[ReceivingItem]) -> None:
    series = articulation["series"]
    series_courses = [BasicCourse.from_assist(member) for member in series["courses"]]

    if not series_courses:
        return

    series_key = make_series_key(series_courses)
    if series_key in seen:
        return

    seen.add(series_key)
    conjunction = Conjunction(series.get("conjunction", "AND").upper())
    rs = ReceivingSeries(key=series_key, conjunction=conjunction, courses=series_courses)
    out.append(ReceivingItem.from_receiving(rs, node_dict))


def get_req_articulation(articulation: dict, node_dict: dict, seen: set[str], out: list[ReceivingItem]) -> None:
    req_tuple = ReceivingRequirement.get_kind_and_key(articulation)

    if req_tuple is None:
        return

    kind, key = ReceivingRequirement.get_kind_and_key(articulation)
    name = articulation[key]["name"].strip()

    if name in seen:
        return

    seen.add(name)
    req = ReceivingRequirement(kind=kind, key=name)
    out.append(ReceivingItem.from_receiving(req, node_dict))


def get_articulations(all_courses_json: dict) -> list[ReceivingItem]:
    result = all_courses_json["result"]
    rows = extract_articulation_rows(result)

    out: list[ReceivingItem] = []
    seen: set[str] = set()

    for row in rows:
        articulation = row["articulation"]
        node_dict = articulation_to_json_dict(articulation)

        receiving_type = articulation["type"]
        if receiving_type == "Course":
            get_course_articulation(articulation, node_dict, seen, out)
        elif receiving_type == "Series":
            get_series_articulation(articulation, node_dict, seen, out)
        else:
            get_req_articulation(articulation, node_dict, seen, out)

    existing_articulation_cell_ids = {row["templateCellId"] for row in rows if row.get("templateCellId")}
    for inv in extract_template_inventory(result["templateAssets"], existing_articulation_cell_ids):
        if inv.key in seen:
            continue

        seen.add(inv.key)
        out.append(inv)

    return out


def parse_num(num: str) -> tuple[int, str]:
    suffix = num.strip().upper()
    i = 0
    while i < len(suffix) and suffix[i].isdigit():
        i += 1

    int_part = int(suffix[:i]) if i > 0 else 10 ** 9
    suffix = suffix[i:]

    return int_part, suffix


def row_sort_key(row: dict) -> tuple:
    if row.get("type") == "COURSE":
        k = parse_num(row.get("number", ""))
        series_flag = 0
        return k[0], k[1], series_flag, row.get("number", "")
    elif row.get("type") == "SERIES":
        nums = [member["number"] for member in row.get("courses", [])]
        k = min((parse_num(n) for n in nums), default=(10 ** 9, ""))
        series_flag = 1
        return k[0], k[1], series_flag, " ".join(nums)
    else:
        k = parse_num(row.get("key", ""))
        series_flag = 0
        return k[0], k[1], series_flag, row.get("key", "")


def upsert_sending_articulation(art_map: dict, college_name: str, sending: dict | None) -> bool:
    if sending is None:
        return False

    existing = art_map.get(college_name)

    if existing is None:
        art_map[college_name] = {
            "sending_name": college_name,
            "sending_articulation": sending
        }
        return True

    if existing.get("sending_articulation") != sending:
        existing["sending_articulation"] = sending
        return True

    return False


def subject_bucket(item: ReceivingItem) -> list[tuple[str, str, str]]:
    if item.receiving_type == ReceivingType.COURSE:
        subject = item.receiving.prefix
        name = item.receiving.subject or item.receiving.prefix
        return [(subject, subject, name)]

    if item.receiving_type == ReceivingType.SERIES:
        seen = {}

        for member in item.receiving.courses:
            if member.prefix not in seen:
                seen[member.prefix] = (member.prefix, member.prefix, member.subject)

        return list(seen.values())

    if item.receiving_type == ReceivingType.MISC:
        return [("# MISC-REQS #", "# MISC-REQS #", "Miscellaneous Requirements")]

    if item.receiving_type == ReceivingType.GE:
        return [("# GE-REQS #", "# GE-REQS #", "General Education Requirements")]

    # shouldn't ever happen
    return [("UNKNOWN", "UNKNOWN", "UNKNOWN")]


def save_articulations(
    university_name: str,
    college_name: str,
    all_articulations: list[ReceivingItem],
    rows_by_subject_dir: dict[str, list[dict]],
    changed_subjects: dict[str, bool],
    subjects_map: dict[str, str],
) -> None:
    buckets: dict[str, dict[str, str | list[ReceivingItem]]] = {}
    for item in all_articulations:
        for directory, prefix, name in subject_bucket(item):
            if directory == "UNKNOWN":
                continue

            b = buckets.setdefault(directory, {"prefix": prefix, "name": name, "items": []})
            b["items"].append(item)

    for subject_dir, meta in buckets.items():
        prefix: str = meta["prefix"]
        subject: str = meta["name"]
        items: list[ReceivingItem] = meta["items"]

        if subject:
            subjects_map[prefix] = subject
        else:
            subjects_map.setdefault(prefix, prefix)

        rows = rows_by_subject_dir.get(subject_dir)
        if rows is None:
            courses_path = Path(f"data/{university_name}/{subject_dir}/courses.json")

            if courses_path.exists():
                with open(courses_path, "r") as f:
                    rows = json.load(f)
            else:
                rows = []

            rows_by_subject_dir[subject_dir] = rows
            changed_subjects.setdefault(subject_dir, False)

        index: dict[str, dict] = {}
        art_maps: dict[str, dict] = {}
        for row in rows:
            row.setdefault("articulations", [])
            key = row["key"]
            index[key] = row
            art_maps[key] = {art["sending_name"]: art for art in row["articulations"]}

        changed = False

        for item in items:
            if item.key not in index:
                index[item.key] = {"type": item.receiving_type.value, **item.receiving.to_dict(), "articulations": []}
                art_maps[item.key] = {}
                changed = True

            if upsert_sending_articulation(art_maps[item.key], college_name, item.sending_articulation):
                changed = True

        if not changed:
            continue

        for k, amap in art_maps.items():
            index[k]["articulations"] = list(amap.values())
        new_rows = list(index.values())
        new_rows.sort(key=row_sort_key)

        rows_by_subject_dir[subject_dir] = new_rows
        changed_subjects[subject_dir] = True


def flush_courses_for_university(name: str, rows: dict[str, list[dict]], subjects: dict[str, bool], ) -> None:
    for subject_dir, rows in rows.items():
        if not subjects.get(subject_dir):
            continue
        courses_path = Path(f"data/{name}/{subject_dir}/courses.json")
        courses_path.parent.mkdir(parents=True, exist_ok=True)
        with open(courses_path, "w") as f:
            json.dump(rows, f, indent=4)


def flush_subjects_for_university(name: str, subjects_map: dict[str, str]) -> None:
    if not subjects_map:
        return

    subjects_path = Path(f"data/{name}/subjects.json")
    existing: list[dict] = []
    if subjects_path.exists():
        try:
            with open(subjects_path, "r") as f:
                existing = json.load(f)
        except json.decoder.JSONDecodeError:
            existing = []

    merged: dict[str, str] = {}
    for it in existing or []:
        pref = it.get("prefix")
        name = it.get("name", pref)
        if isinstance(pref, str) and isinstance(name, str):
            merged[pref] = name
    merged.update(subjects_map)

    new_payload = [{"prefix": p, "name": merged[p]} for p in sorted(merged.keys())]
    if new_payload != (existing or []):
        subjects_path.parent.mkdir(parents=True, exist_ok=True)
        with open(subjects_path, "w") as out:
            json.dump(new_payload, out, indent=4)


def run(desired_universities: list[str] = None) -> None:
    if desired_universities is None or len(desired_universities) == 0:
        desired_universities = ["CSU", "UC", "AICCU"]

    institutions: list[Institution] = get_institutions(create_new_if_existing=True)

    colleges = sorted([i for i in institutions if i.category == "CCC"], key=lambda i: i.name)
    universities = [i for i in institutions if i.category in desired_universities]

    successful = 0
    no_agreements = 0
    no_modern_agreements = 0
    no_viable_agreements = 0

    for university in universities:
        print(f"Getting articulations for {university.name} (ID {university.id}).")

        all_agreements = get_agreements(university.id)

        rows_by_subject_dir: dict[str, list[dict]] = {}
        changed_subjects: dict[str, bool] = {}
        subjects_map: dict[str, str] = {}

        for college in colleges:
            agreement_year = all_agreements.get(college.id, -1)

            if agreement_year == -1:
                print(f"{college.name} and {university.name} have no agreements.")
                no_agreements += 1
                continue

            # Modern agreements only started in year ID 74
            if agreement_year < 74:
                print(f"{college.name} and {university.name} have no modern agreements.")
                no_modern_agreements += 1
                continue

            print(f"Getting articulation: {college.name} (ID {college.id}) -> {university.name} (ID {university.id}) "
                  f"for year ID {agreement_year}")

            all_courses = get_all_courses_json(agreement_year, college.id, university.id)

            if all_courses is None:
                print(f"{college.name} and {university.name} have no viable agreements.")
                no_viable_agreements += 1
                continue

            all_articulations = get_articulations(all_courses)

            save_articulations(
                university.name,
                college.name,
                all_articulations,
                rows_by_subject_dir,
                changed_subjects,
                subjects_map
            )

            successful += 1

        flush_courses_for_university(university.name, rows_by_subject_dir, changed_subjects)
        flush_subjects_for_university(university.name, subjects_map)

        print("\n")

    print("== Results ==")
    print(f"Agreements saved: {successful}")
    print(f"Missing agreements: {no_agreements}")
    print(f"Lacking modern agreements: {no_modern_agreements}")
    print(f"No viable modern agreements: {no_viable_agreements}")


def main():
    desired_universities = [u.upper() for u in sys.argv[1:]]

    if len(desired_universities) > 3:
        print("Invalid number of universities provided.")
        print("Choose from CSU, UC, and AICCU.")
    else:
        run(desired_universities)


if __name__ == "__main__":
    main()
