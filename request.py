import requests
import time


def get(url: str, params=None, **kwargs) -> requests.Response:
    while True:
        response = requests.get(url=url, params=params, **kwargs)

        if response.status_code != 429:
            break

        print("Exceeded rate limit. Retrying request in 30 seconds.")
        time.sleep(30)

    time.sleep(3)

    return response
