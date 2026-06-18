import json
import os


def load_entrants(ref_dir: str = "data/reference") -> list:
    with open(os.path.join(ref_dir, "entrants.json")) as f:
        return json.load(f)["entrants"]
