import requests

from config import (
    PALWORLD_API_URL,
    PALWORLD_API_USER,
    PALWORLD_API_PASSWORD
)


def get_players():

    response = requests.get(
        f"{PALWORLD_API_URL}/v1/api/players",
        auth=(
            PALWORLD_API_USER,
            PALWORLD_API_PASSWORD
        ),
        timeout=5
    )

    response.raise_for_status()

    return response.json()["players"]
