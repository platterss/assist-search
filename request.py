import requests
import time


def get(url: str, params=None, **kwargs) -> requests.Response:
    while True:
        response: requests.Response = requests.get(url=url, params=params, **kwargs)

        if response.text != "API calls quota exceeded! maximum admitted 50 per 5m.":
            break

        print("Exceeded rate limit. Retrying request in 30 seconds.")
        time.sleep(30)

    print("Sleeping for 6 seconds.")
    time.sleep(6)

    return response
