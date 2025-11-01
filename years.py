import json

from agreements import get_agreements
from pathlib import Path


def get_latest_agreement_year() -> int:
    colleges_path = Path("data/colleges")
    if not colleges_path.exists():
        get_agreements()

    latest_agreement: int = 0

    all_agreements = Path(colleges_path).glob("**/agreements.json")
    for college_agreement in all_agreements:
        with open(college_agreement, "r") as file:
            agreement = json.load(file)

        agreement_max: int = 0

        for university in agreement:
            agreement_max = max(university["years"])

        latest_agreement = max(latest_agreement, agreement_max)

    return latest_agreement


if __name__ == "__main__":
    print(f"Latest academic year with any agreements: {get_latest_agreement_year()}")
