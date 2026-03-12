from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import requests



def _check_token(token: str) -> str | None:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        r = requests.get(url, timeout=20)
    except requests.RequestException:
        return None

    if r.status_code == 200:
        data = r.json()
        if isinstance(data, dict) and "jobs" in data:
            return token
    elif r.status_code != 404:
        print(f"SKIP {token}: status {r.status_code}")

    return None


def validate_greenhouse_tokens(tokens: set[str], *, max_workers: int = 20) -> list[str]:
    valid: list[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_check_token, token): token for token in tokens}
        for future in as_completed(futures):
            result = future.result()
            if result:
                valid.append(result)

    return sorted(valid)