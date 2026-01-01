import re
from typing import List

CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}")
MITRE_RE = re.compile(r"T\d{4}")


def extract_bindings(text: str) -> List[str]:
    found = set()
    for match in CVE_RE.findall(text or ""):
        found.add(match)
    for match in MITRE_RE.findall(text or ""):
        found.add(match)
    return sorted(found)
