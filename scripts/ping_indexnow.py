"""Submits updated beacon URLs to IndexNow for immediate Bing/search engine crawling."""
import json
import urllib.request

HOST = "autonomous-agent-beacon.onrender.com"
KEY = "9f8e4b7c2a1d6e5f8a0b3c4d7e9f1a2b"
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"

URL_LIST = [
    f"https://{HOST}/",
    f"https://{HOST}/resources/model-matrix",
    f"https://{HOST}/data/model-matrix.json",
    f"https://{HOST}/resources/sandbox",
    f"https://{HOST}/resources/mcp-catalog",
    f"https://{HOST}/data/mcp-catalog.json",
    f"https://{HOST}/resources/llm-errors",
    f"https://{HOST}/data/llm-errors.json",
    f"https://{HOST}/hall-of-fame",
    f"https://{HOST}/llms.txt",
    f"https://{HOST}/llms-full.txt",
    f"https://{HOST}/.well-known/agent-beacon.json",
    f"https://{HOST}/api/v1/echo",
]


def ping():
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": URL_LIST,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            print(f"IndexNow Ping Status: {res.status} (OK/Submitted)")
    except urllib.error.HTTPError as e:
        print(f"IndexNow Response: {e.code} - {e.read().decode('utf-8')}")


if __name__ == "__main__":
    ping()
