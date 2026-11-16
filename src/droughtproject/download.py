# ////////////////////////////////////////////////////////////////////////////
# // 1. Reads cached NASA annual JSON responses and the NOAA NAO text index.
# // 2. Reuses the existing real downloads; fetches missing years when online.
# // 3. Saves raw responses without filling, deleting, or changing measurements.
# // 4. Includes 1981 onward rainfall for the independent SPI reference period.
# ////////////////////////////////////////////////////////////////////////////
import json

import httpx

from droughtproject.settings import (
    DATA,
    RAW,
    PARAMETERS,
    LOCATION,
    ENDPOINT,
    NAO_URL,
    ARCHIVE_START,
    ARCHIVE_END,
    MODEL_HISTORY_START,
)


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        timeout=120, follow_redirects=True, transport=httpx.HTTPTransport(retries=2)
    ) as client:
        for year in range(ARCHIVE_START, ARCHIVE_END + 1):
            destination = RAW / f"{year}.json"
            if destination.exists():
                continue
            codes = list(PARAMETERS) if year >= MODEL_HISTORY_START else ["PRECTOTCORR"]
            response = client.get(
                ENDPOINT,
                params={
                    "parameters": ",".join(codes),
                    "community": "AG",
                    "latitude": LOCATION["latitude"],
                    "longitude": LOCATION["longitude"],
                    "start": f"{year}0101",
                    "end": f"{year}1231",
                    "format": "JSON",
                    "time-standard": "UTC",
                },
            )
            response.raise_for_status()
            payload = response.json()
            destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"Downloaded NASA {year}", flush=True)
        nao_path = DATA / "raw" / "nao.txt"
        if not nao_path.exists():
            response = client.get(NAO_URL)
            response.raise_for_status()
            nao_path.write_text(response.text, encoding="utf-8")
    print("Raw archive ready. Run prepare to validate it.", flush=True)


if __name__ == "__main__":
    download()
