import json
import request
import sys

from classes import Conjunction, SendingArticulationNode, SendingCourse, NodeType
from pathlib import Path
from typing import Optional

from agreements import get_agreements
from institutions import get_institutions


def as_obj(x):
    return json.loads(x) if isinstance(x, str) else x


def make_course_key(prefix: str, number: str) -> str:
    return f"{prefix.strip()} {number.strip()}"


def make_series_key(members: list[dict]) -> str:
    tokens = []
    prev_prefix = None

    for member in members or []:
        prefix = str(member["prefix"]).strip()
        number = str(member["number"]).strip()

        if not tokens or prefix != prev_prefix:
            tokens.append(f"{prefix} {number}")
        else:
            tokens.append(number)

        prev_prefix = prefix

    return " + ".join(tokens)


def receiving_key(payload: dict) -> str:
    receiving_type = payload["receiving_type"]

    if receiving_type == "COURSE":
        receiving = payload["receiving"]
        return make_course_key(receiving["prefix"], receiving["number"])

    if receiving_type == "SERIES":
        series = payload["receiving_series"]
        return make_series_key(series["courses"])

    if receiving_type == "REQUIREMENT":
        return f"{payload["receiving_requirement"]["name"]}"

    if receiving_type == "GE":
        return f"{payload["receiving_ge"]["name"]}"

    # shouldn't ever happen
    return payload.get("receiving_key", "")


def make_sending_course(obj: dict, extra_notes: Optional[list[str]] = None) -> SendingCourse:
    notes = []

    for attribute in obj.get("attributes") or []:
        content = attribute.get("content")

        if content:
            notes.append(content)

    if extra_notes:
        notes.extend(extra_notes)

    if obj["prefix"] is None and obj["courseNumber"] is None:
        print("Found broken course.")

        return SendingCourse(
            prefix="Unknown",
            number="Course",
            key=make_course_key("Unknown", "Course"),
            title="Missing",
            min_units=-1.0,
            max_units=-1.0,
            notes=["This particular course is broken on ASSIST and displays an empty course."]
        )

    return SendingCourse(
        prefix=obj["prefix"].strip(),
        number=obj["courseNumber"].strip(),
        key=make_course_key(obj["prefix"], obj["courseNumber"]),
        title=obj["courseTitle"].strip(),
        min_units=float(obj["minUnits"]),
        max_units=float(obj["maxUnits"]),
        notes=notes
    )


def parse_course_group(group: dict) -> SendingArticulationNode:
    conjunction = group.get("courseConjunction", "").strip().lower()
    items = sorted(group.get("items", []), key=lambda x: x.get("position", 0))
    courses = [make_sending_course(item) for item in items if item.get("type") == "Course"]
    group_level_notes: list[str] = [
        a.get("content") for a in group.get("attributes", []) if a.get("content")
    ]

    if conjunction == "or":
        children: list[SendingArticulationNode] = [
            SendingArticulationNode(
                type=NodeType.SET,
                conjunction=None,
                items=[course],
                notes=[]
            )
            for course in courses
        ]

        return SendingArticulationNode(
            type=NodeType.GROUP,
            conjunction=Conjunction.OR,
            items=children,
            notes=group_level_notes
        )

    if conjunction == "and":
        return SendingArticulationNode(
            type=NodeType.SET,
            conjunction=None if len(courses) == 1 else Conjunction.AND,
            items=courses,
            notes=group_level_notes
        )

    return SendingArticulationNode(
        type=NodeType.SET,
        conjunction=None,
        items=courses,
        notes=group_level_notes
    )


def combine_groups(groups: list[SendingArticulationNode], group_conjunctions: list[dict]) -> SendingArticulationNode:
    n = len(groups)

    if n == 0:
        return SendingArticulationNode(
            type=NodeType.GROUP,
            conjunction=Conjunction.AND,
            items=[],
            notes=[]
        )

    if n == 1 and not group_conjunctions:
        return groups[0]

    edges: list[Optional[str]] = [None] * max(0, n - 1)
    for group in group_conjunctions or []:
        conjunction = group.get("groupConjunction", "And")
        begin = int(group.get("sendingCourseGroupBeginPosition", 0))
        end = int(group.get("sendingCourseGroupEndPosition", max(0, n - 1)))

        low = max(0, begin)
        high = min(n - 1, end)

        for i in range(low, high):
            edges[i] = conjunction

    edges = [(edge or "Or") for edge in edges]

    if edges and all(edge.lower() == edges[0].lower() for edge in edges):
        conjunction = Conjunction.OR if edges[0].lower() == "or" else Conjunction.AND
        return SendingArticulationNode(
            type=NodeType.GROUP,
            conjunction=conjunction,
            items=groups,
            notes=[]
        )

    segments: list[SendingArticulationNode] = []
    start = 0
    for i, edge in enumerate(edges):
        if edge.lower() != "or":
            continue

        seg_children = groups[start:i+1]
        if len(seg_children) == 1 and seg_children[0].type == NodeType.GROUP:
            segments.append(seg_children[0])
        else:
            segments.append(
                SendingArticulationNode(
                    type=NodeType.GROUP,
                    conjunction=Conjunction.AND,
                    items=seg_children,
                    notes=[],
                )
            )
        start = i + 1

    if start < n:
        seg_children = groups[start:n]
        if len(seg_children) == 1 and seg_children[0].type == NodeType.GROUP:
            segments.append(seg_children[0])
        else:
            segments.append(
                SendingArticulationNode(
                    type=NodeType.GROUP,
                    conjunction=Conjunction.AND,
                    items=seg_children,
                    notes=[],
                )
            )

    if len(segments) == 1:
        return segments[0]

    return SendingArticulationNode(
        type=NodeType.GROUP,
        conjunction=Conjunction.OR,
        items=segments,
        notes=[]
    )


def is_singleton_set(node: SendingArticulationNode) -> bool:
    return (
        node and
        node.type == NodeType.SET and
        node.items is not None and
        isinstance(node.items, list) and
        all(isinstance(item, SendingCourse) for item in node.items) and
        len(node.items) == 1
    )


def flatten_group_of_singleton_sets(node: SendingArticulationNode) -> SendingArticulationNode:
    if node.type != NodeType.GROUP:
        return node

    children = node.items
    if not children:
        return node

    if not all(isinstance(child, SendingArticulationNode) and is_singleton_set(child) for child in children):
        return node

    flat_courses: list[SendingCourse] = []
    for child in children:
        course = child.items[0]

        if child.notes:
            course = SendingCourse(
                prefix=course.prefix,
                number=course.number,
                key=course.key,
                title=course.title,
                notes=list(course.notes) + list(child.notes),
                min_units=course.min_units,
                max_units=course.max_units
            )

        flat_courses.append(course)

    return SendingArticulationNode(
        type=NodeType.SET,
        conjunction=node.conjunction,
        items=flat_courses,
        notes=list(node.notes or [])
    )


def normalize_node(node: SendingArticulationNode) -> SendingArticulationNode:
    if node.type == NodeType.GROUP:
        normalized_children = [normalize_node(child) for child in node.items]
        node = SendingArticulationNode(
            type=NodeType.GROUP,
            conjunction=node.conjunction,
            items=normalized_children,
            notes=list(node.notes or []),
        )

        if len(normalized_children) == 1:
            return normalized_children[0]

        node = flatten_group_of_singleton_sets(node)
        return node

    if node.type == NodeType.SET:
        conj = node.conjunction if len(node.items) > 1 else None

        return SendingArticulationNode(
            type=NodeType.SET,
            conjunction=conj,
            items=node.items,
            notes=list(node.notes or []),
        )

    return node


def build_articulation_tree(sending_articulation: Optional[dict]) -> Optional[SendingArticulationNode]:
    if not sending_articulation:
        return None

    reason = sending_articulation.get("noArticulationReason")
    if isinstance(reason, str) and reason.strip():
        return None

    groups_raw = sending_articulation.get("items", [])
    groups_raw = [group for group in groups_raw if group["type"] == "CourseGroup"]
    groups_raw.sort(key=lambda x: x.get("position", 0))
    normalized = [parse_course_group(g) for g in groups_raw if g["type"] == "CourseGroup"]

    node = combine_groups(normalized, sending_articulation.get("courseGroupConjunctions", []))

    return normalize_node(node)


def request_all_courses(year: int, sending: int, receiving: int, method: str) -> dict:
    url = f"https://www.assist.org/api/articulation/Agreements?Key={year}/{sending}/to/{receiving}/{method}"

    all_courses_json: dict = request.get(url=url).json()
    if not all_courses_json["isSuccessful"]:
        raise FileNotFoundError("Agreement was not found for this combination.")

    return all_courses_json


def get_all_courses_json(agreement_year: int, sending_id: int, receiving_id: int) -> dict | None:
    if agreement_year < 74:  # The modernized agreements view only started in year ID 74
        return None

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


def articulation_to_json_dict(articulation: dict) -> Optional[dict]:
    sending = articulation.get("sendingArticulation")

    if sending is None:
        return None

    node = build_articulation_tree(sending)

    if node is None:
        return None

    return node.to_dict()


def extract_cells(payload: dict | list) -> list[dict]:
    result = payload["result"]

    if result["name"] in {"All Majors", "All General Education"}:
        return as_obj(result["articulations"])

    # All Departments or All Prefixes
    cells = []
    for subject in as_obj(result["articulations"]):
        for articulation in subject.get("articulations", []):
            cells.append({"articulation": articulation})

    return cells


def collect_cell_ids(result: dict) -> set[str]:
    ids = set()

    for c in as_obj(result.get("articulations", "[]")):
        art = c.get("articulation") or {}
        template_cell_id = c.get("templateCellId") or art.get("templateCellId")
        if template_cell_id:
            ids.add(template_cell_id)

    return ids


def make_receiving_course(data: dict) -> dict:
    return {
        "prefix": data["prefix"].strip(),
        "prefix_description": data["prefixDescription"].strip(),
        "key": make_course_key(data["prefix"], data["courseNumber"]),
        "number": data["courseNumber"].strip(),
        "title": data["courseTitle"].strip(),
        "min_units": data["minUnits"],
        "max_units": data["maxUnits"],
    }


def walk_template_assets(assets) -> list[tuple[str | None, str, dict]]:
    assets = as_obj(assets)
    out: list[tuple[str | None, str, dict]] = []

    def is_course_dict(d: dict) -> bool:
        return isinstance(d, dict) and all(k in d for k in ("prefix", "courseNumber", "courseTitle"))

    def dfs(node, cell_id=None):
        if isinstance(node, dict):
            cid = node.get("id", cell_id)

            if is_course_dict(node):
                out.append((cid, "COURSE", make_receiving_course(node)))

            series = node.get("series")
            if series is not None:
                courses = [make_receiving_course(c) for c in series["courses"] if is_course_dict(c)]

                if courses:
                    conjunction = series.get("conjunction")
                    out.append((cid, "SERIES", {
                        "conjunction": conjunction,
                        "courses": courses
                    }))

            req = node.get("requirement")
            if req is not None:
                out.append((cid, "REQUIREMENT", {
                    "name": req.get("name").strip(),
                }))

            ge = node.get("generalEducationArea")
            if ge is not None:
                out.append((cid, "GE", {
                    "name": ge.get("name").strip()
                }))

            for k, v in node.items():
                if k != "series":
                    dfs(v, cid)
        elif isinstance(node, list):
            for v in node:
                dfs(v, cell_id)

    dfs(assets, None)

    return out


def extract_template_inventory(result: dict) -> list[dict]:
    used = collect_cell_ids(result)
    items = walk_template_assets(result["templateAssets"])

    out: list[dict] = []
    seen_keys: set[str] = set()

    for cell_id, articulation_type, payload in items:
        if cell_id and cell_id in used:
            continue  # already has an articulation row

        if articulation_type == "COURSE":
            key = f'{payload["prefix"]} {str(payload["number"])}'
            if key in seen_keys:
                continue

            seen_keys.add(key)
            out.append({
                "receiving_key": key,
                "receiving_type": "COURSE",
                "receiving": payload,
                "sending_articulation": None,
            })
        elif articulation_type == "SERIES":
            courses = payload.get("courses") or []
            if not courses:
                continue

            key = make_series_key(courses)
            if key in seen_keys:
                continue

            seen_keys.add(key)
            out.append({
                "receiving_key": key,
                "receiving_type": "SERIES",
                "receiving_series": {
                    "conjunction": payload["conjunction"].upper(),
                    "courses": courses,
                },
                "sending_articulation": None,
            })
        elif articulation_type == "REQUIREMENT":
            key = f"{payload["name"]}"
            if key in seen_keys:
                continue

            seen_keys.add(key)
            out.append({
                "receiving_key": key,
                "receiving_type": "REQUIREMENT",
                "receiving_requirement": payload,
                "sending_articulation": None,
            })
        elif articulation_type == "GE":
            key = f"{payload["name"]}"
            if key in seen_keys:
                continue

            seen_keys.add(key)
            out.append({
                "receiving_key": key,
                "receiving_type": "GE",
                "receiving_ge": payload,
                "sending_articulation": None,
            })

    return out


def get_course_articulation(articulation: dict, node_dict: dict, seen: set[str], out: list[dict]) -> None:
    receiving = articulation["course"]

    key = make_course_key(receiving["prefix"], receiving["courseNumber"])
    if key in seen:
        return

    seen.add(key)
    out.append({
        "receiving_key": key,
        "receiving_type": "COURSE",
        "receiving": make_receiving_course(receiving),
        "sending_articulation": node_dict
    })


def get_series_articulation(articulation: dict, node_dict: dict, seen: set[str], out: list[dict]) -> None:
    series = articulation["series"]
    series_courses = [make_receiving_course(member) for member in series["courses"]]

    if not series_courses:
        return

    series_key = make_series_key(series_courses)
    if series_key in seen:
        return

    seen.add(series_key)
    out.append({
        "receiving_key": series_key,
        "receiving_type": "SERIES",
        "receiving_series": {
            "conjunction": series["conjunction"].upper(),
            "courses": series_courses
        },
        "sending_articulation": node_dict
    })


def get_requirement_articulation(articulation: dict, node_dict: dict, seen: set[str], out: list[dict]) -> None:
    req = articulation["requirement"]
    label = req["name"]
    key = label

    if key in seen:
        return

    seen.add(key)
    out.append({
        "receiving_key": key,
        "receiving_type": "REQUIREMENT",
        "receiving_requirement": {
            "name": req["name"]
        },
        "sending_articulation": node_dict
    })


def get_ge_articulation(articulation: dict, node_dict: dict, seen: set[str], out: list[dict]) -> None:
    ge = articulation["generalEducationArea"]
    label = ge["name"]
    key = label

    if key in seen:
        return

    seen.add(key)
    out.append({
        "receiving_key": key,
        "receiving_type": "GE",
        "receiving_ge": {
            "name": ge["name"]
        },
        "sending_articulation": node_dict
    })


def get_articulations(all_courses_json: dict) -> list[dict]:
    cells = extract_cells(all_courses_json)

    out: list[dict] = []
    seen: set[str] = set()

    for cell in cells:
        art = cell.get("articulation") or {}
        node_dict = articulation_to_json_dict(art)

        if art["type"] == "Course":
            get_course_articulation(art, node_dict, seen, out)
        elif art["type"] == "Series":
            get_series_articulation(art, node_dict, seen, out)
        elif art["type"] == "Requirement":
            get_requirement_articulation(art, node_dict, seen, out)
        elif art["type"] == "GeneralEducation":
            get_ge_articulation(art, node_dict, seen, out)

    for inv in extract_template_inventory(all_courses_json["result"]):
        if inv["receiving_key"] in seen:
            continue

        seen.add(inv["receiving_key"])
        out.append(inv)

    return out


def build_receiving_row(subject_prefix: str, key: str, payload: dict) -> dict:
    receiving_type: str = payload["receiving_type"]

    if receiving_type == "COURSE":
        course = payload["receiving"]

        return {
            "type": "COURSE",
            "prefix": subject_prefix,
            "prefix_description": course["prefix_description"],
            "number": course["number"],
            "key": key,
            "title": course["title"],
            "min_units": course["min_units"],
            "max_units": course["max_units"],
            "articulations": []
        }

    if receiving_type == "SERIES":
        series = payload["receiving_series"]

        return {
            "type": "SERIES",
            "key": key,
            "conjunction": series["conjunction"],
            "courses": series["courses"],
            "articulations": []
        }

    if receiving_type == "REQUIREMENT":
        return {
            "type": "REQUIREMENT",
            "key": key,
            "articulations": []
        }

    if receiving_type == "GE":
        return {
            "type": "GE",
            "key": key,
            "articulations": []
        }

    # shouldn't ever happen
    return {
        "type": "UNKNOWN",
        "key": key,
        "prefix": subject_prefix,
        "articulations": []
    }


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


def subject_bucket(articulation: dict) -> list[tuple[str, str, str]]:
    receiving_type: str = articulation["receiving_type"]

    if receiving_type == "COURSE":
        subject = articulation["receiving"]["prefix"]
        name = articulation["receiving"]["prefix_description"].strip()
        return [(subject, subject, name)]

    if receiving_type == "SERIES":
        seen = {}

        for member in articulation["receiving_series"]["courses"]:
            prefix = member["prefix"].strip()
            if prefix not in seen:
                seen[prefix] = (prefix, prefix, member["prefix_description"])

        return list(seen.values())

    if receiving_type == "REQUIREMENT":
        return [("# MISC-REQS #", "# MISC-REQS #", "Miscellaneous Requirements")]

    if receiving_type == "GE":
        return [("# GE-REQS #", "# GE-REQS #", "General Education Requirements")]

    # shouldn't ever happen
    return [("UNKNOWN", "UNKNOWN", "UNKNOWN")]


def save_articulations(
    university_name: str,
    college_name: str,
    all_articulations: list[dict],
    rows_by_subject_dir: dict[str, list[dict]],
    changed_subjects: dict[str, bool],
    subjects_map: dict[str, str],
) -> None:
    buckets: dict[str, dict] = {}
    for a in all_articulations:
        for directory, prefix, name in subject_bucket(a):
            if directory == "UNKNOWN":
                continue

            b = buckets.setdefault(directory, {"prefix": prefix, "name": name, "items": []})
            b["items"].append(a)

    for subject_dir, meta in buckets.items():
        subject_prefix = meta["prefix"]
        subject_name = meta["name"]
        items = meta["items"]

        if subject_name:
            subjects_map[subject_prefix] = subject_name
        else:
            subjects_map.setdefault(subject_prefix, subject_prefix)

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
            rtype = row.get("type", "COURSE")
            if "key" in row:
                key = row["key"]
            elif rtype == "COURSE":
                key = make_course_key(row["prefix"], row["number"])
                row["key"] = key
                row["type"] = "COURSE"
            elif rtype == "SERIES":
                key = make_series_key(row["courses"])
                row["key"] = key
                row["type"] = "SERIES"
            else:
                key = row["key"]
            row.setdefault("articulations", [])
            index[key] = row
            art_maps[key] = {art["sending_name"]: art for art in row["articulations"]}

        changed = False

        for a in items:
            key = receiving_key(a)
            if key not in index:
                index[key] = build_receiving_row(subject_prefix, key, a)
                art_maps[key] = {}
                changed = True

            if upsert_sending_articulation(art_maps[key], college_name, a["sending_articulation"]):
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

    institutions = get_institutions(create_new_if_existing=False)

    colleges = sorted([i for i in institutions if i["category"] == "CCC"], key=lambda i: i["name"])
    universities = [i for i in institutions if i["category"] in desired_universities]

    for university in universities:
        university_id = university["id"]
        university_name = university["name"]
        print(f"Getting articulations for {university_name} (ID {university_id}).")

        all_agreements = get_agreements(university_id)

        rows_by_subject_dir: dict[str, list[dict]] = {}
        changed_subjects: dict[str, bool] = {}
        subjects_map: dict[str, str] = {}

        for college in colleges:
            college_id = college["id"]
            college_name = college["name"]
            agreement_year = all_agreements.get(college_id, -1)

            print(f"Getting articulation: {college_name} (ID {college_id}) -> {university_name} (ID {university_id}) "
                  f"for year ID {agreement_year}")

            all_courses = get_all_courses_json(agreement_year, college_id, university_id)

            if all_courses is None:
                print(f"{university_name} and {college_name} have no viable agreements.")
                continue

            all_articulations = get_articulations(all_courses)

            save_articulations(
                university_name,
                college_name,
                all_articulations,
                rows_by_subject_dir,
                changed_subjects,
                subjects_map
            )

        flush_courses_for_university(university_name, rows_by_subject_dir, changed_subjects)
        flush_subjects_for_university(university_name, subjects_map)

        print("\n")

    print("Finished saving articulations.")


def main():
    desired_universities = [u.upper() for u in sys.argv[1:]]

    if len(desired_universities) > 3:
        print("Invalid number of universities provided.")
        print("Choose from CSU, UC, and AICCU.")
    else:
        run(desired_universities)


if __name__ == "__main__":
    main()
