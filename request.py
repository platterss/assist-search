import time
import urllib.parse
import requests


session = requests.Session()

def refresh_session():
    print("Refreshing ASSIST.org session.")

    session.cookies.clear()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.assist.org/",
        "Connection": "keep-alive",
    })

    main_resp = session.get("https://www.assist.org/")
    print(f"Homepage load status: {main_resp.status_code}")

    raw_token = session.cookies.get("X-XSRF-TOKEN") or session.cookies.get("XSRF-TOKEN")

    if raw_token:
        decoded_token = urllib.parse.unquote(raw_token)
        session.headers.update({
            "X-XSRF-TOKEN": decoded_token,
            "Accept": "application/json, text/plain, */*",
        })
    else:
        print("Failed to get token.")


refresh_session()


def requires_refresh(response: requests.Response):
    if response.status_code == 400:
        resp_json = response.json()
        return "title" in resp_json.keys() and resp_json["title"] == "Bad Request"

    return False


def get(url: str, params=None, **kwargs) -> requests.Response:
    while True:
        response = session.get(url=url, params=params, **kwargs)

        if requires_refresh(response):
            print(f"Received {response.status_code} error on {url}. Token likely expired.")
            print(f"Server response payload: {response.text}")
            refresh_session()
            time.sleep(10)
            continue

        if response.status_code == 429:
            print("Exceeded rate limit. Retrying request in 60 seconds.")
            time.sleep(60)
            continue

        break

    time.sleep(3)
    return response
