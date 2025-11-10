import json
import request

from classes import Institution
from pathlib import Path


def get_institution_type(category_num: int) -> str:
    match category_num:
        case 0:
            return "CSU"
        case 1:
            return "UC"
        case 2:
            return "CCC"
        case 5:
            return "AICCU"
        case _:
            return "Unknown"


def get_institutions_json() -> list[dict]:
    url: str = "https://www.assist.org/api/institutions"

    return request.get(url=url).json()


def get_latest_institution_name(names: list[dict]) -> str:
    return max(names, key=lambda n: n.get("fromYear", float("-inf")))["name"]


def reformat_institutions(raw_institutions) -> list[Institution]:
    institutions: list[Institution] = []

    for institution in raw_institutions:
        # Mainly for Compton Community College (ID 34)
        if "endId" in institution.keys():
            continue

        institutions.append(Institution(
            id=institution["id"],
            name=get_latest_institution_name(institution["names"]),
            category=get_institution_type(institution["category"])
        ))

    return institutions


def create_institutions_file() -> list[Institution]:
    print("Getting list of institutions.")

    raw_institutions = get_institutions_json()
    formatted_institutions = reformat_institutions(raw_institutions)

    output_file = Path("data/institutions.json")
    output_file.parent.mkdir(exist_ok=True, parents=True)
    with open(output_file, "w") as out:
        json.dump([i.to_dict() for i in formatted_institutions], out, indent=4)

    return formatted_institutions


def load_institutions_from_file(institutions_dict: list[dict]) -> list[Institution]:
    institutions: list[Institution] = []

    for institution in institutions_dict:
        institutions.append(Institution(
            id=institution["id"],
            name=institution["name"],
            category=institution["category"]
        ))

    return institutions


def get_institutions(create_new_if_existing: bool = False) -> list[Institution]:
    institutions_path = Path("data/institutions.json")

    if create_new_if_existing or not institutions_path.exists():
        return create_institutions_file()

    with open(institutions_path, "r") as file:
        return load_institutions_from_file(json.load(file))


if __name__ == "__main__":
    get_institutions(create_new_if_existing=True)
