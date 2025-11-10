import requests
import time


def get(url: str, params=None, **kwargs) -> requests.Response:
    while True:
        response: requests.Response = requests.get(url=url, params=params, **kwargs)

        if response.text != "API calls quota exceeded! maximum admitted 50 per 5m.":
            break

        print("Exceeded rate limit. Retrying request in 30 seconds.")
        time.sleep(30)

    # It seems like they allow around 100 requests rather than just 50.
    # 3 seconds will occasionally exceed the rate limit but 4 is safer.
    time.sleep(3)

    return response
