import request


def get_agreements(university_id: int) -> dict:
    print(f"Getting agreements for university ID {university_id}.")
    url = f"https://www.assist.org/api/institutions/{university_id}/agreements"
    agreements_json: list[dict] = request.get(url=url).json()

    agreements: dict = {}
    existing_ids: set[int] = set()

    for agreement in agreements_json:
        if not agreement["isCommunityCollege"] or agreement["institutionParentId"] in existing_ids:
            continue

        existing_ids.add(agreement["institutionParentId"])
        agreements[agreement["institutionParentId"]] = max(agreement["sendingYearIds"])

    return agreements
