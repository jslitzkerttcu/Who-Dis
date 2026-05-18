"""Temporary password generator for AD account operations.

Generates readable passwords meeting AD complexity requirements:
uppercase, lowercase, digit, and symbol. Designed for verbal
communication to end users (D-06 pattern).
"""

import secrets
from typing import List

WORDS: List[str] = [
    "Sunset", "Silver", "Garden", "Breeze", "Castle",
    "Dragon", "Forest", "Harbor", "Island", "Marble",
    "Orange", "Planet", "Rocket", "Sierra", "Timber",
    "Violet", "Winter", "Zenith", "Crystal", "Phoenix",
    "Thunder", "Diamond", "Falcon", "Copper", "Alpine",
    "Beacon", "Blazer", "Bridge", "Candle", "Canvas",
    "Carbon", "Cedar", "Chroma", "Cobalt", "Comet",
    "Coral", "Cosmos", "Dagger", "Delphi", "Ember",
    "Falcon", "Flint", "Garnet", "Ginger", "Glacier",
    "Gravel", "Hallow", "Hammer", "Helium", "Indigo",
    "Ivory", "Jasper", "Jumper", "Kayak", "Kernel",
    "Lantern", "Laurel", "Lemon", "Lotus", "Magnet",
    "Meadow", "Meteor", "Mosaic", "Nebula", "Nickel",
    "Obsidian", "Orchid", "Osprey", "Oyster", "Pebble",
    "Pepper", "Prism", "Quartz", "Raven", "Riddle",
    "Ripple", "Rubric", "Rustic", "Saffron", "Scroll",
    "Shadow", "Sketch", "Solder", "Sphinx", "Spruce",
    "Summit", "Tangle", "Thorns", "Topaz", "Tropic",
    "Tunnel", "Umber", "Vortex", "Walnut", "Willow",
    "Anchor", "Bamboo", "Birch", "Clover", "Dune",
    "Fjord", "Granite", "Helix", "Ivory", "Juniper",
]

SYMBOLS: str = "!@#$%&*"


def generate_temp_password() -> str:
    """Generate a temporary password meeting AD complexity requirements.

    Format: {Word}{2-digit-number}{symbol}
    Example: Castle42!

    Returns:
        A readable temporary password with uppercase, lowercase, digit, and symbol.
    """
    word = secrets.choice(WORDS)
    digits = secrets.randbelow(90) + 10
    symbol = secrets.choice(SYMBOLS)
    return f"{word}{digits}{symbol}"
