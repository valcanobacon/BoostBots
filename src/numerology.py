import math
import re

PI = str(math.pi).replace(".", "")
PI_REGEX_PATTERN = "|".join(PI[:x] for x in range(len(PI) + 1, 3 - 1, -1))

COUNTDOWN = "987654321"
COUNTDOWN_REGEX_PATTEN = "|".join(
    COUNTDOWN[-n:] for n in range(len(COUNTDOWN), 3 - 1, -1)
)

REGEX_PATTEN = "|".join(
    (
        COUNTDOWN_REGEX_PATTEN,
        r"(?:10)+|11|21|33|69|73|88|420|666|1776|1867|9653|[68]00[68]|^2+$",
        PI_REGEX_PATTERN,
    )
)

REGEX = re.compile(REGEX_PATTEN)


def number_to_numerology(number: int) -> str:
    results = []

    number_str = str(number)

    matches = REGEX.findall(number_str)

    for match in matches:

        if re.search(r"(?:10)+", match):
            for _ in range(len(match) // 2):
                results.append("π³")
            for _ in range(len(match) // 2 - 3 + 1):
                results.append("π¦")

        if match == "11":
            results.append("π²")

        if match == "21":
            results.append("πͺ")

        if match == "33":
            results.append("β¨")

        if match == "69":
            results.append("π")

        if match == "73":
            results.append("π")

        if match == "88":
            results.append("π₯°")

        if match == "420":
            results.append("βπ½π¨")

        if match == "666":
            results.append("π")

        if match == "1776":
            results.append("πΊπΈ")

        if match == "1867":
            results.append("π¨π¦")

        if match == "9653":
            results.append("πΊ")

        if re.search(r"[68]00[68]", match):
            results.append("π±")
            results.append("π±")

        if re.search(r"^2+$", match):
            for _ in range(len(match)):
                results.append("π¦")

        if re.search(PI_REGEX_PATTERN, match):
            for _ in range(len(match) - 2):
                results.append("π₯§")

        if re.search(COUNTDOWN_REGEX_PATTEN, match):
            for _ in range(len(match) - 2):
                results.append("π₯")

    if number >= 100000:
        results.append("π₯")

    if number >= 50000:
        results.append("π₯")

    if number >= 10000:
        results.append("π₯")

    if number < 10:
        results.append("π©")

    if not results:
        return ""

    return "".join(results)
