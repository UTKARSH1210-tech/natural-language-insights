from __future__ import annotations

import json
from pathlib import Path


def save_dataset_profile(
    dataset_id: str,
    profile: dict,
    profile_path: Path,
) -> None:

    profile_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with profile_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            profile,
            file,
            indent=2,
            default=str,
        )


def load_dataset_profile(
    profile_path: Path,
) -> dict:

    if not profile_path.exists():

        raise FileNotFoundError(
            "Dataset profile not found."
        )

    with profile_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)