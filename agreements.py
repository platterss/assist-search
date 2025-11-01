import json
import request

from pathlib import Path
from institutions import create_institutions_file


def save_ccc_agreements(institutions: list[dict]) -> None:
    for ccc in [i for i in institutions if i["category"] == "CCC"]:
        print(f"Getting agreements for {ccc["name"]}")

        url = f"https://www.assist.org/api/institutions/{ccc["id"]}/agreements"
        agreements_json: list[dict] = request.get(url=url).json()

        agreements: list[dict] = []
        existing_ids: set[int] = set()

        for university in agreements_json:
            if university["institutionParentId"] in existing_ids:
                continue

            existing_ids.add(university["institutionParentId"])
            agreements.append(
                {"id": university["institutionParentId"],
                 "name": university["institutionName"],
                 "years": university["receivingYearIds"]}
            )

        output_file = Path(f"data/colleges/{ccc["name"]}/agreements.json")
        output_file.parent.mkdir(exist_ok=True, parents=True)
        with open(output_file, 'w') as out:
            json.dump(agreements, out, indent=4)


def get_agreements() -> None:
    institutions_path = Path("data/institutions.json")

    if not institutions_path.exists():
        create_institutions_file()

    with open(institutions_path, "r") as file:
        institutions: list[dict] = json.load(file)
        save_ccc_agreements(institutions)


if __name__ == "__main__":
    get_agreements()
