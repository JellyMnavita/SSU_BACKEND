"""Import métadonnées HUMVI (articles FR) — texte dérivé des URLs."""

from __future__ import annotations

import ast
import csv
import re
import urllib.parse
import urllib.request
from pathlib import Path

from nlp_shared.corpus_utils import CorpusRow, normalize_text

HUMVI_TRAIN_URL = (
    "https://raw.githubusercontent.com/dataminr-ai/humvi-dataset/main/data/"
    "humvi_expansion_train.csv"
)
HUMVI_TEST_URL = (
    "https://raw.githubusercontent.com/dataminr-ai/humvi-dataset/main/data/"
    "humvi_expansion_test.csv"
)

DRC_HINTS = re.compile(
    r"kinshasa|congo|rdc|goma|lubumbashi|bukavu|kananga|kisangani|"
    r"ituri|kivu|beni|butembo|matadi|kolwezi",
    re.IGNORECASE,
)


def download_humvi_csv(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "SSU-NLP-Corpus/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
    return dest


def _url_to_text(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path or "")
    segment = path.rstrip("/").split("/")[-1]
    segment = re.sub(r"\.(html?|php|aspx?)$", "", segment, flags=re.IGNORECASE)
    text = segment.replace("-", " ").replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_label_combined(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw or raw == "[]":
        return []
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [str(x).lower() for x in parsed]
    except (SyntaxError, ValueError):
        pass
    return [part.strip().lower() for part in raw.strip("[]").split(",") if part.strip()]


def map_humvi_to_ssu_label(
    label_combined: list[str],
    relevant: bool,
    text: str,
) -> str | None:
    if len(text) < 12:
        return None
    if not relevant:
        return "autre"
    if not label_combined:
        return "violence"

    joined = " ".join(label_combined)
    if "aid-sec" in joined or "protection" in joined:
        return "violence"
    if "food" in joined:
        return "violence"
    if "education" in joined:
        return "agression"
    if "health" in joined:
        return "violence"
    return "violence"


def load_humvi_rows(
    raw_dir: Path,
    *,
    language: str = "french",
    prefer_drc: bool = False,
    max_rows: int = 800,
) -> list[CorpusRow]:
    train_path = raw_dir / "humvi_expansion_train.csv"
    test_path = raw_dir / "humvi_expansion_test.csv"
    download_humvi_csv(HUMVI_TRAIN_URL, train_path)
    download_humvi_csv(HUMVI_TEST_URL, test_path)

    rows: list[CorpusRow] = []
    for csv_path in (train_path, test_path):
        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get("language") or "").strip().lower() != language:
                    continue
                url = row.get("url", "")
                text = normalize_text(_url_to_text(url))
                relevant = str(row.get("label_relevance", "")).strip().lower() == "true"
                labels = _parse_label_combined(row.get("label_combined", ""))
                ssu_label = map_humvi_to_ssu_label(labels, relevant, text)
                if ssu_label is None:
                    continue
                if prefer_drc and not DRC_HINTS.search(url + " " + text):
                    continue
                source = "humvi_fr_relevant" if relevant else "humvi_fr_irrelevant"
                rows.append(CorpusRow(text=text, label=ssu_label, source=source))
                if len(rows) >= max_rows:
                    return rows
    return rows
