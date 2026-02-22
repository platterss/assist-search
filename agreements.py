import request

from pathlib import Path
from util import read_json, write_json


# Fetches a local agreement from the given path if present
# Otherwise, go get the agreement, save it, then return it
def get_local_agreement(path, url):
    file_path = Path(path)

    if file_path.is_file():
        return read_json(file_path)

    resp = request.get(url=url).json()
    write_json(resp, path)

    return resp


def get_agreements(university_id: int, use_local_agreement_data: bool = False) -> dict:
    print(f"Getting agreements for university ID {university_id}.")
    url = f"https://www.assist.org/api/institutions/{university_id}/agreements"

    if use_local_agreement_data:
        path = f"raw_agreements/{university_id}/Agreements.json"
        agreements_json: list[dict] = get_local_agreement(path, url)
    else:
        agreements_json: list[dict] = request.get(url=url).json()

    agreements: dict = {}
    existing_ids: set[int] = set()

    for agreement in agreements_json:
        if not agreement["isCommunityCollege"] or agreement["institutionParentId"] in existing_ids:
            continue

        existing_ids.add(agreement["institutionParentId"])
        agreements[agreement["institutionParentId"]] = max(agreement["sendingYearIds"])

    return agreements
