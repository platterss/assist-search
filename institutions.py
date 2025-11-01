import json
import request

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


def reformat_institutions(raw_institutions) -> list[dict]:
    institutions: list[dict] = []

    for institution in raw_institutions:
        # Mainly for Compton Community College (ID 34)
        if "endId" in institution.keys():
            continue

        data: dict = {"id": institution["id"],
                      "name": get_latest_institution_name(institution["names"]),
                      "category": get_institution_type(institution["category"])}

        institutions.append(data)

    return institutions


def create_institutions_file() -> None:
    raw_institutions = get_institutions_json()
    formatted_institutions = reformat_institutions(raw_institutions)

    output_file = Path("data/institutions.json")
    output_file.parent.mkdir(exist_ok=True, parents=True)
    with open(output_file, "w") as out:
        json.dump(formatted_institutions, out, indent=4)


if __name__ == "__main__":
    create_institutions_file()
