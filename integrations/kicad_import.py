from pathlib import Path


def import_kicad_labels(path):
    labels = []
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            labels.append({"label": parts[0], "pin": parts[1], "raw": line})
    return labels
