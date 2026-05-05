from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import statistics
import tracemalloc
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns


NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CELL_REF_RE = re.compile(r"([A-Z]+)(\d+)")
WORD_RE = re.compile(r"[a-z0-9]+")

SCENARIOS = (
    ("A", 100, 20),
    ("B", 500, 50),
    ("C", 1000, 100),
)

MERGED_DATASET_FILENAME = "merged_hoax_dataset.csv"
MERGED_DATASET_HEADERS = (
    "id",
    "source",
    "label",
    "title",
    "timestamp",
    "tags",
    "author",
    "url",
    "text",
    "text_column",
)

STOPWORDS = {
    "ada",
    "adalah",
    "agar",
    "akan",
    "aku",
    "anda",
    "antar",
    "apa",
    "apakah",
    "atas",
    "atau",
    "bahwa",
    "bagi",
    "bagian",
    "bahkan",
    "baik",
    "baru",
    "bawah",
    "beberapa",
    "begitu",
    "belum",
    "benar",
    "berada",
    "berbagai",
    "berikut",
    "bersama",
    "besar",
    "biasa",
    "bisa",
    "boleh",
    "buat",
    "bukan",
    "bukanlah",
    "cukup",
    "dalam",
    "dan",
    "dari",
    "daripada",
    "data",
    "dengan",
    "demi",
    "demikian",
    "depan",
    "desa",
    "dia",
    "diantara",
    "diberi",
    "dibuat",
    "didalam",
    "digunakan",
    "dijelaskan",
    "diketahui",
    "dilakukan",
    "dimana",
    "dini",
    "dipakai",
    "diri",
    "disampaikan",
    "ditambah",
    "diterima",
    "ditulis",
    "dua",
    "empat",
    "enam",
    "fakta",
    "guna",
    "hal",
    "hari",
    "harus",
    "hasil",
    "hingga",
    "ia",
    "ialah",
    "ibarat",
    "ikut",
    "ini",
    "itu",
    "jadi",
    "jangan",
    "jika",
    "juga",
    "justru",
    "kabar",
    "kalau",
    "kami",
    "kamu",
    "karena",
    "kata",
    "ke",
    "kecil",
    "kelas",
    "kelompok",
    "kemudian",
    "kemungkinan",
    "kenapa",
    "kepada",
    "keren",
    "ketika",
    "khusus",
    "kita",
    "kurang",
    "lagi",
    "lain",
    "lainnya",
    "lalu",
    "lebih",
    "lewat",
    "luar",
    "maka",
    "makin",
    "mana",
    "masih",
    "masing",
    "mau",
    "media",
    "memang",
    "membuat",
    "mencari",
    "menjadi",
    "menjelaskan",
    "menuju",
    "mereka",
    "merupakan",
    "meski",
    "meskipun",
    "mesti",
    "mohon",
    "muncul",
    "nah",
    "namun",
    "nantinya",
    "nya",
    "oleh",
    "orang",
    "pada",
    "padahal",
    "paling",
    "para",
    "per",
    "pernah",
    "perlu",
    "pihak",
    "pukul",
    "pun",
    "saat",
    "saja",
    "saling",
    "sama",
    "sambil",
    "sampai",
    "sana",
    "sangat",
    "satu",
    "saya",
    "sebagai",
    "sebagian",
    "sebelum",
    "sebuah",
    "secara",
    "sedang",
    "sedangkan",
    "segala",
    "sehingga",
    "sejak",
    "sejumlah",
    "sekadar",
    "sekali",
    "sekitar",
    "selain",
    "selama",
    "selanjutnya",
    "seluruh",
    "semakin",
    "sementara",
    "sempat",
    "semua",
    "sendiri",
    "seorang",
    "seperti",
    "sering",
    "serta",
    "sesuai",
    "setelah",
    "setiap",
    "siapa",
    "sini",
    "soal",
    "suatu",
    "sudah",
    "supaya",
    "tak",
    "tampak",
    "tanpa",
    "tapi",
    "telah",
    "tentang",
    "tentu",
    "tepat",
    "terhadap",
    "terjadi",
    "terkait",
    "tersebut",
    "terus",
    "tetap",
    "tetapi",
    "tiap",
    "tidak",
    "tiga",
    "toh",
    "tolong",
    "turut",
    "untuk",
    "usai",
    "video",
    "warga",
    "waktu",
    "yang",
    "akun",
    "beredar",
    "berita",
    "cek",
    "content",
    "disinformasi",
    "editor",
    "facebook",
    "false",
    "foto",
    "gambar",
    "hoax",
    "info",
    "informasi",
    "kategori",
    "klarifikasi",
    "konten",
    "manipulated",
    "misleading",
    "narasi",
    "penjelasan",
    "periksa",
    "referensi",
    "salah",
    "sumber",
    "terbaru",
    "twitter",
    "unggahan",
    "whatsapp",
}


@dataclass(frozen=True)
class DatasetSpec:
    source: str
    filename: str
    text_columns: tuple[str, ...]
    label: int


@dataclass(frozen=True)
class Document:
    source: str
    label: int
    text: str


@dataclass(frozen=True)
class Metrics:
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class BenchmarkResult:
    scenario: str
    algorithm: str
    documents: int
    keywords: int
    threshold: int
    execution_time_ms: float
    peak_memory_kb: float
    precision: float
    recall: float
    f1: float


DATASET_SPECS = (
    DatasetSpec("cnn", "dataset_cnn_10k_cleaned.xlsx", ("text_new", "FullText", "Title"), 0),
    DatasetSpec("kompas", "dataset_kompas_4k_cleaned.xlsx", ("text_new", "FullText", "Title"), 0),
    DatasetSpec("tempo", "dataset_tempo_6k_cleaned.xlsx", ("text_new", "FullText", "Title"), 0),
    DatasetSpec(
        "turnbackhoax",
        "dataset_turnbackhoax_10_cleaned.xlsx",
        ("Clean Narasi", "Narasi", "Title"),
        1,
    ),
)

RK_ALPHABET_SIZE = 256
RK_PRIME_MOD = 1_000_000_007


def column_letters_to_index(column_letters: str) -> int:
    value = 0
    for character in column_letters:
        value = value * 26 + (ord(character) - 64)
    return value - 1


def load_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    try:
        raw_xml = workbook.read("xl/sharedStrings.xml")
    except KeyError:
        return []

    root = ET.fromstring(raw_xml)
    return [
        "".join(text_node.text or "" for text_node in string_node.iter(f"{NS_MAIN}t"))
        for string_node in root.findall(f"{NS_MAIN}si")
    ]


def get_first_sheet_path(workbook: zipfile.ZipFile) -> str:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    relationships_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    relationship_map = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships_root.findall(f"{NS_REL}Relationship")
    }
    first_sheet = workbook_root.find(f"{NS_MAIN}sheets/{NS_MAIN}sheet")
    if first_sheet is None:
        raise ValueError("Workbook tidak memiliki sheet.")

    relation_id = first_sheet.attrib[
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    ]
    target = relationship_map[relation_id].replace("\\", "/").lstrip("/")
    if not target.startswith("xl/"):
        target = f"xl/{target}"
    return target


def parse_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value_node = cell.find(f"{NS_MAIN}v")
    if value_node is None:
        inline_string = cell.find(f"{NS_MAIN}is")
        if inline_string is None:
            return ""
        return "".join(text_node.text or "" for text_node in inline_string.iter(f"{NS_MAIN}t"))

    raw_value = value_node.text or ""
    cell_type = cell.attrib.get("t")
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except (ValueError, IndexError):
            return raw_value
    return raw_value


def iter_sheet_cell_maps(workbook_path: Path) -> list[dict[int, str]]:
    rows: list[dict[int, str]] = []
    with zipfile.ZipFile(workbook_path) as workbook:
        shared_strings = load_shared_strings(workbook)
        sheet_path = get_first_sheet_path(workbook)
        with workbook.open(sheet_path) as sheet_stream:
            context = ET.iterparse(sheet_stream, events=("end",))
            for _, element in context:
                if element.tag != f"{NS_MAIN}row":
                    continue
                row_cells: dict[int, str] = {}
                for cell in element.findall(f"{NS_MAIN}c"):
                    reference = cell.attrib.get("r", "")
                    match = CELL_REF_RE.match(reference)
                    if not match:
                        continue
                    column_index = column_letters_to_index(match.group(1))
                    row_cells[column_index] = parse_cell_value(cell, shared_strings)
                rows.append(row_cells)
                element.clear()
    return rows


def iter_xlsx_records(workbook_path: Path) -> list[dict[str, str]]:
    rows = iter_sheet_cell_maps(workbook_path)
    if not rows:
        return []

    header_row = rows[0]
    header_map = {
        column_index: header_name.strip()
        for column_index, header_name in header_row.items()
        if header_name.strip()
    }
    ordered_headers = [name for _, name in sorted(header_map.items(), key=lambda item: item[0])]

    records: list[dict[str, str]] = []
    for row_cells in rows[1:]:
        record = {header_name: "" for header_name in ordered_headers}
        for column_index, value in row_cells.items():
            header_name = header_map.get(column_index)
            if header_name:
                record[header_name] = value
        records.append(record)
    return records


def pick_first_non_empty(record: dict[str, str], column_names: tuple[str, ...]) -> str:
    for column_name in column_names:
        value = record.get(column_name, "")
        if value and value.strip():
            return value.strip()
    return ""


def pick_first_non_empty_with_column(
    record: dict[str, str],
    column_names: tuple[str, ...],
) -> tuple[str, str]:
    for column_name in column_names:
        value = record.get(column_name, "")
        if value and value.strip():
            return value.strip(), column_name
    return "", ""


def normalize_for_matching(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text)).replace("\u00a0", " ").casefold()
    return normalized


def normalize_for_tokens(text: str) -> str:
    normalized = normalize_for_matching(text)
    normalized = re.sub(r"https?://\S+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalized


def tokenize(text: str) -> list[str]:
    tokens = WORD_RE.findall(normalize_for_tokens(text))
    return [
        token
        for token in tokens
        if len(token) >= 4 and len(token) <= 24 and token not in STOPWORDS and not token.isdigit()
    ]


def normalize_record(
    spec: DatasetSpec,
    record: dict[str, str],
    record_index: int,
) -> dict[str, str]:
    text, text_column = pick_first_non_empty_with_column(record, spec.text_columns)
    return {
        "id": f"{spec.source}_{record_index}",
        "source": spec.source,
        "label": str(spec.label),
        "title": record.get("Title", "").strip(),
        "timestamp": record.get("Timestamp", "").strip(),
        "tags": record.get("Tags", "").strip(),
        "author": record.get("Author", "").strip(),
        "url": record.get("Url", "").strip(),
        "text": text,
        "text_column": text_column,
    }


def load_normalized_records_from_xlsx(data_dir: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for spec in DATASET_SPECS:
        workbook_path = data_dir / spec.filename
        if not workbook_path.exists():
            raise FileNotFoundError(f"File dataset tidak ditemukan: {workbook_path}")

        for record_index, record in enumerate(iter_xlsx_records(workbook_path), start=1):
            normalized_record = normalize_record(spec, record, record_index)
            if not normalized_record["text"]:
                continue
            records.append(normalized_record)
    return records


def load_normalized_records_from_csv(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        records = []
        for row in reader:
            normalized_row = {header: (row.get(header, "") or "").strip() for header in MERGED_DATASET_HEADERS}
            if not normalized_row["text"]:
                continue
            records.append(normalized_row)
        return records


def write_merged_dataset_csv(output_path: Path, records: list[dict[str, str]]) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MERGED_DATASET_HEADERS)
        writer.writeheader()
        writer.writerows(records)


def resolve_merged_dataset_path(data_dir: Path, merged_dataset_path: Path | None) -> Path | None:
    if merged_dataset_path is not None:
        if not merged_dataset_path.exists():
            raise FileNotFoundError(f"File dataset gabungan tidak ditemukan: {merged_dataset_path}")
        return merged_dataset_path

    auto_path = data_dir / MERGED_DATASET_FILENAME
    if auto_path.exists():
        return auto_path
    return None


def load_documents(data_dir: Path, merged_dataset_path: Path | None = None, force_excel: bool = False) -> list[Document]:
    if force_excel:
        normalized_records = load_normalized_records_from_xlsx(data_dir)
    else:
        resolved_merged_path = resolve_merged_dataset_path(data_dir, merged_dataset_path)
        if resolved_merged_path is not None:
            normalized_records = load_normalized_records_from_csv(resolved_merged_path)
        else:
            normalized_records = load_normalized_records_from_xlsx(data_dir)

    return [
        Document(
            source=record["source"],
            label=int(record["label"]),
            text=record["text"],
        )
        for record in normalized_records
    ]


def stratified_split(
    documents: list[Document],
    train_ratio: float,
    validation_ratio: float,
    seed: int,
) -> dict[str, list[Document]]:
    grouped: dict[int, list[Document]] = defaultdict(list)
    for document in documents:
        grouped[document.label].append(document)

    splits = {"train": [], "validation": [], "test": []}
    randomizer = random.Random(seed)
    for label, group in grouped.items():
        shuffled = list(group)
        randomizer.shuffle(shuffled)

        train_end = int(len(shuffled) * train_ratio)
        validation_end = train_end + int(len(shuffled) * validation_ratio)

        splits["train"].extend(shuffled[:train_end])
        splits["validation"].extend(shuffled[train_end:validation_end])
        splits["test"].extend(shuffled[validation_end:])

    return splits


def sample_balanced(documents: list[Document], total_size: int, seed: int) -> list[Document]:
    grouped: dict[int, list[Document]] = defaultdict(list)
    for document in documents:
        grouped[document.label].append(document)

    if 0 not in grouped or 1 not in grouped:
        raise ValueError("Sample seimbang memerlukan data label 0 dan 1.")

    half = total_size // 2
    if len(grouped[0]) < half or len(grouped[1]) < half:
        raise ValueError("Jumlah dokumen per kelas tidak cukup untuk sample seimbang.")

    randomizer = random.Random(seed)
    negatives = list(grouped[0])
    positives = list(grouped[1])
    randomizer.shuffle(negatives)
    randomizer.shuffle(positives)

    sample = negatives[:half] + positives[:half]
    randomizer.shuffle(sample)
    return sample


def select_keyword_training_documents(
    documents: list[Document],
    per_class_limit: int,
    seed: int,
) -> tuple[list[Document], list[Document]]:
    grouped: dict[int, list[Document]] = defaultdict(list)
    for document in documents:
        grouped[document.label].append(document)

    randomizer = random.Random(seed)
    positive_documents = list(grouped.get(1, []))
    negative_documents = list(grouped.get(0, []))
    randomizer.shuffle(positive_documents)
    randomizer.shuffle(negative_documents)

    return positive_documents[:per_class_limit], negative_documents[:per_class_limit]


def extract_keywords(
    positive_documents: list[Document],
    negative_documents: list[Document],
    keyword_limit: int,
) -> list[str]:
    positive_df: Counter[str] = Counter()
    negative_df: Counter[str] = Counter()

    for document in positive_documents:
        positive_df.update(set(tokenize(document.text)))
    for document in negative_documents:
        negative_df.update(set(tokenize(document.text)))

    if not positive_df:
        raise ValueError("Tidak ada keyword kandidat yang bisa dibentuk dari data hoaks.")

    positive_total = max(1, len(positive_documents))
    negative_total = max(1, len(negative_documents))

    scored_keywords: list[tuple[float, int, int, str]] = []
    for token, positive_count in positive_df.items():
        if positive_count < 3:
            continue
        positive_rate = positive_count / positive_total
        negative_rate = negative_df[token] / negative_total
        score = (positive_rate - negative_rate) * math.log1p(positive_count)
        if score <= 0:
            continue
        scored_keywords.append((score, positive_count, -negative_df[token], token))

    scored_keywords.sort(key=lambda item: (-item[0], -item[1], item[3]))
    return [token for _, _, _, token in scored_keywords[:keyword_limit]]


def build_failure_function(pattern: str) -> list[int]:
    failure = [0] * len(pattern)
    matched = 0
    for index in range(1, len(pattern)):
        while matched > 0 and pattern[matched] != pattern[index]:
            matched = failure[matched - 1]
        if pattern[matched] == pattern[index]:
            matched += 1
        failure[index] = matched
    return failure


def compute_hash(text: str, alphabet_size: int, prime_mod: int) -> int:
    value = 0
    for character in text:
        value = (value * alphabet_size + ord(character)) % prime_mod
    return value


def kmp_search_precompiled(
    text: str,
    pattern: str,
    failure: list[int],
    include_positions: bool,
) -> tuple[int, list[int]]:
    if not pattern or len(pattern) > len(text):
        return 0, []

    matches: list[int] = []
    count = 0
    matched = 0

    for index, character in enumerate(text):
        while matched > 0 and character != pattern[matched]:
            matched = failure[matched - 1]
        if character == pattern[matched]:
            matched += 1
        if matched == len(pattern):
            count += 1
            if include_positions:
                matches.append(index - len(pattern) + 1)
            matched = failure[matched - 1]

    return count, matches


def rabin_karp_search_precompiled(
    text: str,
    pattern: str,
    pattern_hash: int,
    high_order: int,
    include_positions: bool,
) -> tuple[int, list[int]]:
    pattern_length = len(pattern)
    text_length = len(text)
    if pattern_length == 0 or pattern_length > text_length:
        return 0, []

    window_hash = compute_hash(text[:pattern_length], RK_ALPHABET_SIZE, RK_PRIME_MOD)

    count = 0
    matches: list[int] = []
    for start_index in range(text_length - pattern_length + 1):
        if pattern_hash == window_hash and text[start_index : start_index + pattern_length] == pattern:
            count += 1
            if include_positions:
                matches.append(start_index)
        if start_index == text_length - pattern_length:
            continue

        leading_value = ord(text[start_index]) * high_order
        trailing_value = ord(text[start_index + pattern_length])
        window_hash = (window_hash - leading_value) % RK_PRIME_MOD
        window_hash = (window_hash * RK_ALPHABET_SIZE + trailing_value) % RK_PRIME_MOD

    return count, matches


SEARCH_FUNCTIONS = ("kmp", "rabin-karp")


class HoaxDetector:
    def __init__(self, keywords: list[str], algorithm_name: str, threshold: int) -> None:
        if algorithm_name not in SEARCH_FUNCTIONS:
            raise ValueError(f"Algoritma tidak dikenal: {algorithm_name}")
        self.algorithm_name = algorithm_name
        self.keywords = [normalize_for_matching(keyword) for keyword in keywords if keyword.strip()]
        self.threshold = max(1, threshold)
        if self.algorithm_name == "kmp":
            self.compiled_patterns = [
                (keyword, build_failure_function(keyword))
                for keyword in self.keywords
            ]
        else:
            self.compiled_patterns = [
                (
                    keyword,
                    compute_hash(keyword, RK_ALPHABET_SIZE, RK_PRIME_MOD),
                    pow(RK_ALPHABET_SIZE, len(keyword) - 1, RK_PRIME_MOD),
                )
                for keyword in self.keywords
            ]

    def count_matches_in_normalized_text(self, normalized_text: str) -> int:
        total_matches = 0
        if self.algorithm_name == "kmp":
            for keyword, failure in self.compiled_patterns:
                match_count, _ = kmp_search_precompiled(normalized_text, keyword, failure, False)
                total_matches += match_count
        else:
            for keyword, pattern_hash, high_order in self.compiled_patterns:
                match_count, _ = rabin_karp_search_precompiled(
                    normalized_text,
                    keyword,
                    pattern_hash,
                    high_order,
                    False,
                )
                total_matches += match_count
        return total_matches

    def count_matches(self, text: str) -> int:
        normalized_text = normalize_for_matching(text)
        return self.count_matches_in_normalized_text(normalized_text)

    def detect(self, text: str) -> dict[str, object]:
        normalized_text = normalize_for_matching(text)
        found_keywords: dict[str, list[int]] = {}
        total_matches = 0

        if self.algorithm_name == "kmp":
            for keyword, failure in self.compiled_patterns:
                match_count, positions = kmp_search_precompiled(normalized_text, keyword, failure, True)
                if match_count > 0:
                    found_keywords[keyword] = positions
                    total_matches += match_count
        else:
            for keyword, pattern_hash, high_order in self.compiled_patterns:
                match_count, positions = rabin_karp_search_precompiled(
                    normalized_text,
                    keyword,
                    pattern_hash,
                    high_order,
                    True,
                )
                if match_count > 0:
                    found_keywords[keyword] = positions
                    total_matches += match_count

        score = total_matches / self.threshold
        label = "HOAKS" if score >= 1 else "BUKAN_HOAKS"
        return {
            "algorithm": self.algorithm_name,
            "threshold": self.threshold,
            "label": label,
            "score": score,
            "total_matches": total_matches,
            "matches": found_keywords,
        }


def calculate_metrics(expected_labels: list[int], predicted_labels: list[int]) -> Metrics:
    true_positive = sum(1 for expected, predicted in zip(expected_labels, predicted_labels) if expected == 1 and predicted == 1)
    false_positive = sum(1 for expected, predicted in zip(expected_labels, predicted_labels) if expected == 0 and predicted == 1)
    false_negative = sum(1 for expected, predicted in zip(expected_labels, predicted_labels) if expected == 1 and predicted == 0)

    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return Metrics(precision=precision, recall=recall, f1=f1)


def tune_threshold(
    validation_documents: list[Document],
    keywords: list[str],
    algorithm_name: str,
) -> int:
    provisional_detector = HoaxDetector(keywords=keywords, algorithm_name=algorithm_name, threshold=1)
    normalized_texts = [normalize_for_matching(document.text) for document in validation_documents]
    counts = [
        provisional_detector.count_matches_in_normalized_text(normalized_text)
        for normalized_text in normalized_texts
    ]
    labels = [document.label for document in validation_documents]

    max_count = max(counts, default=0)
    if max_count <= 0:
        return 1

    best_threshold = 1
    best_tuple = (-1.0, -1.0, -1.0, 0)
    for threshold in range(1, max_count + 1):
        predicted = [1 if count >= threshold else 0 for count in counts]
        metrics = calculate_metrics(labels, predicted)
        ranking_tuple = (metrics.f1, metrics.precision, metrics.recall, -threshold)
        if ranking_tuple > best_tuple:
            best_tuple = ranking_tuple
            best_threshold = threshold
    return best_threshold


def benchmark_detector(
    documents: list[Document],
    keywords: list[str],
    algorithm_name: str,
    threshold: int,
    repeats: int,
) -> BenchmarkResult:
    detector = HoaxDetector(keywords=keywords, algorithm_name=algorithm_name, threshold=threshold)
    expected_labels = [document.label for document in documents]
    normalized_texts = [normalize_for_matching(document.text) for document in documents]
    elapsed_times_ms: list[float] = []
    peak_memories_kb: list[float] = []
    final_predictions: list[int] = []

    for repeat_index in range(repeats):
        predicted_labels: list[int] = []
        tracemalloc.start()
        started_at = perf_counter_ns()
        for normalized_text in normalized_texts:
            total_matches = detector.count_matches_in_normalized_text(normalized_text)
            predicted_labels.append(1 if total_matches >= threshold else 0)
        elapsed_ms = (perf_counter_ns() - started_at) / 1_000_000
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        elapsed_times_ms.append(elapsed_ms)
        peak_memories_kb.append(peak_memory / 1024)
        if repeat_index == repeats - 1:
            final_predictions = predicted_labels

    metrics = calculate_metrics(expected_labels, final_predictions)
    return BenchmarkResult(
        scenario="",
        algorithm=algorithm_name,
        documents=len(documents),
        keywords=len(keywords),
        threshold=threshold,
        execution_time_ms=statistics.mean(elapsed_times_ms),
        peak_memory_kb=statistics.mean(peak_memories_kb),
        precision=metrics.precision,
        recall=metrics.recall,
        f1=metrics.f1,
    )


def summarize_documents(documents: list[Document]) -> dict[str, object]:
    grouped = defaultdict(int)
    by_source = defaultdict(int)
    for document in documents:
        grouped[str(document.label)] += 1
        by_source[document.source] += 1
    return {
        "total_documents": len(documents),
        "label_distribution": dict(sorted(grouped.items())),
        "source_distribution": dict(sorted(by_source.items())),
    }


def limit_document_length(documents: list[Document], max_text_length: int) -> list[Document]:
    if max_text_length <= 0:
        return documents
    return [
        Document(
            source=document.source,
            label=document.label,
            text=document.text[:max_text_length],
        )
        for document in documents
    ]


def prepare_experiment_assets(
    data_dir: Path,
    merged_dataset_path: Path | None,
    seed: int,
    train_ratio: float,
    validation_ratio: float,
    keyword_source_docs_per_class: int,
    keyword_pool_size: int,
    validation_docs_per_class: int,
    max_text_length: int,
    force_excel: bool = False,
) -> dict[str, object]:
    documents = limit_document_length(
        load_documents(data_dir, merged_dataset_path=merged_dataset_path, force_excel=force_excel),
        max_text_length=max_text_length,
    )
    splits = stratified_split(
        documents=documents,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        seed=seed,
    )

    positive_training_documents, negative_training_documents = select_keyword_training_documents(
        splits["train"],
        per_class_limit=keyword_source_docs_per_class,
        seed=seed + 7,
    )
    keywords = extract_keywords(
        positive_documents=positive_training_documents,
        negative_documents=negative_training_documents,
        keyword_limit=keyword_pool_size,
    )

    validation_sample = sample_balanced(
        splits["validation"],
        total_size=validation_docs_per_class * 2,
        seed=seed + 11,
    )

    return {
        "documents": documents,
        "splits": splits,
        "keywords": keywords,
        "validation_sample": validation_sample,
    }


def run_merge(args: argparse.Namespace) -> None:
    normalized_records = load_normalized_records_from_xlsx(args.data_dir)
    write_merged_dataset_csv(args.output, normalized_records)

    documents = [
        Document(source=record["source"], label=int(record["label"]), text=record["text"])
        for record in normalized_records
    ]
    summary = summarize_documents(documents)
    print("Dataset berhasil digabungkan.")
    print(f"Output: {args.output}")
    print_dataset_summary(summary)


def run_benchmark(args: argparse.Namespace) -> None:
    assets = prepare_experiment_assets(
        data_dir=args.data_dir,
        merged_dataset_path=args.merged_dataset,
        seed=args.seed,
        train_ratio=args.train_ratio,
        validation_ratio=args.validation_ratio,
        keyword_source_docs_per_class=args.keyword_source_docs_per_class,
        keyword_pool_size=max(keyword_count for _, _, keyword_count in SCENARIOS),
        validation_docs_per_class=args.validation_docs_per_class,
        max_text_length=args.max_text_length,
    )

    test_documents: list[Document] = assets["splits"]["test"]  # type: ignore[index]
    validation_sample: list[Document] = assets["validation_sample"]  # type: ignore[assignment]
    keywords: list[str] = assets["keywords"]  # type: ignore[assignment]

    results: list[BenchmarkResult] = []
    for scenario_name, document_count, keyword_count in SCENARIOS:
        scenario_documents = sample_balanced(
            test_documents,
            total_size=document_count,
            seed=args.seed + document_count,
        )
        scenario_keywords = keywords[:keyword_count]

        for algorithm_name in SEARCH_FUNCTIONS:
            threshold = tune_threshold(
                validation_documents=validation_sample,
                keywords=scenario_keywords,
                algorithm_name=algorithm_name,
            )
            result = benchmark_detector(
                documents=scenario_documents,
                keywords=scenario_keywords,
                algorithm_name=algorithm_name,
                threshold=threshold,
                repeats=args.repeats,
            )
            results.append(
                BenchmarkResult(
                    scenario=scenario_name,
                    algorithm=result.algorithm,
                    documents=result.documents,
                    keywords=result.keywords,
                    threshold=result.threshold,
                    execution_time_ms=result.execution_time_ms,
                    peak_memory_kb=result.peak_memory_kb,
                    precision=result.precision,
                    recall=result.recall,
                    f1=result.f1,
                )
            )

    payload = {
        "dataset_summary": summarize_documents(assets["documents"]),  # type: ignore[arg-type]
        "top_keywords": keywords[:20],
        "results": [result.__dict__ for result in results],
    }

    if args.output:
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print_dataset_summary(payload["dataset_summary"])
    print("\nTop 20 keyword kandidat:")
    print(", ".join(payload["top_keywords"]))
    print("\nHasil benchmark:")
    print_result_table(results)

    if args.output:
        print(f"\nHasil JSON disimpan ke: {args.output}")


def print_dataset_summary(summary: dict[str, object]) -> None:
    print("Ringkasan dataset:")
    print(f"- total_documents: {summary['total_documents']}")
    print(f"- label_distribution: {summary['label_distribution']}")
    print(f"- source_distribution: {summary['source_distribution']}")


def print_result_table(results: list[BenchmarkResult]) -> None:
    headers = (
        ("Scenario", 8),
        ("Algorithm", 12),
        ("Docs", 8),
        ("Keywords", 10),
        ("Threshold", 10),
        ("Time(ms)", 12),
        ("Mem(KB)", 12),
        ("Precision", 12),
        ("Recall", 12),
        ("F1", 10),
    )
    header_line = " ".join(title.ljust(width) for title, width in headers)
    separator = "-" * len(header_line)
    print(header_line)
    print(separator)
    for result in results:
        row = (
            result.scenario.ljust(8),
            result.algorithm.ljust(12),
            str(result.documents).ljust(8),
            str(result.keywords).ljust(10),
            str(result.threshold).ljust(10),
            f"{result.execution_time_ms:.2f}".ljust(12),
            f"{result.peak_memory_kb:.2f}".ljust(12),
            f"{result.precision:.4f}".ljust(12),
            f"{result.recall:.4f}".ljust(12),
            f"{result.f1:.4f}".ljust(10),
        )
        print(" ".join(row))


def run_classification(args: argparse.Namespace) -> None:
    assets = prepare_experiment_assets(
        data_dir=args.data_dir,
        merged_dataset_path=args.merged_dataset,
        seed=args.seed,
        train_ratio=args.train_ratio,
        validation_ratio=args.validation_ratio,
        keyword_source_docs_per_class=args.keyword_source_docs_per_class,
        keyword_pool_size=max(args.keyword_count, 100),
        validation_docs_per_class=args.validation_docs_per_class,
        max_text_length=args.max_text_length,
    )

    keywords: list[str] = assets["keywords"][: args.keyword_count]  # type: ignore[index]
    validation_sample: list[Document] = assets["validation_sample"]  # type: ignore[assignment]
    threshold = tune_threshold(
        validation_documents=validation_sample,
        keywords=keywords,
        algorithm_name=args.algorithm,
    )
    detector = HoaxDetector(keywords=keywords, algorithm_name=args.algorithm, threshold=threshold)
    result = detector.detect(args.text)

    print(f"Algoritma : {result['algorithm']}")
    print(f"Threshold : {result['threshold']}")
    print(f"Label     : {result['label']}")
    print(f"Score     : {result['score']:.4f}")
    print(f"Matches   : {result['total_matches']}")
    print("Keyword terdeteksi:")

    matches: dict[str, list[int]] = result["matches"]  # type: ignore[assignment]
    if not matches:
        print("- tidak ada keyword yang cocok")
        return

    for keyword, positions in sorted(matches.items(), key=lambda item: (-len(item[1]), item[0])):
        preview = ", ".join(str(position) for position in positions[:10])
        if len(positions) > 10:
            preview += ", ..."
        print(f"- {keyword}: {preview}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Program deteksi hoaks berbasis keyword matching dengan KMP dan Rabin-Karp."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Folder yang berisi empat file dataset .xlsx",
    )
    parser.add_argument(
        "--merged-dataset",
        type=Path,
        default=None,
        help="Opsional: pakai file dataset gabungan .csv. Jika tidak diisi, script akan otomatis memakai merged_hoax_dataset.csv bila ada.",
    )
    parser.add_argument("--seed", type=int, default=45, help="Seed random agar hasil sampling stabil.")
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.7,
        help="Proporsi data train untuk ekstraksi keyword.",
    )
    parser.add_argument(
        "--validation-ratio",
        type=float,
        default=0.15,
        help="Proporsi data validasi untuk tuning threshold.",
    )
    parser.add_argument(
        "--max-text-length",
        type=int,
        default=120,
        help="Panjang maksimum teks per dokumen. Pakai 0 untuk full text.",
    )
    parser.add_argument(
        "--keyword-source-docs-per-class",
        type=int,
        default=1500,
        help="Jumlah maksimum dokumen per kelas untuk membentuk keyword kandidat.",
    )
    parser.add_argument(
        "--validation-docs-per-class",
        type=int,
        default=250,
        help="Jumlah dokumen per kelas untuk tuning threshold.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    merge_parser = subparsers.add_parser("merge", help="Gabungkan semua dataset ke satu file CSV terstandar.")
    merge_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data") / MERGED_DATASET_FILENAME,
        help="Lokasi file CSV hasil gabungan.",
    )
    merge_parser.set_defaults(handler=run_merge)

    benchmark_parser = subparsers.add_parser("benchmark", help="Jalankan benchmark sesuai skenario laporan.")
    benchmark_parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Jumlah pengulangan benchmark per skenario.",
    )
    benchmark_parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/benchmark_results.json"),
        help="Lokasi file JSON hasil benchmark.",
    )
    benchmark_parser.set_defaults(handler=run_benchmark)

    classify_parser = subparsers.add_parser("classify", help="Klasifikasikan satu teks.")
    classify_parser.add_argument(
        "--algorithm",
        choices=SEARCH_FUNCTIONS,
        default="kmp",
        help="Algoritma string matching yang digunakan.",
    )
    classify_parser.add_argument(
        "--keyword-count",
        type=int,
        default=50,
        help="Jumlah keyword teratas yang dipakai untuk deteksi.",
    )
    classify_parser.add_argument(
        "--text",
        required=True,
        help="Teks yang ingin diklasifikasikan.",
    )
    classify_parser.set_defaults(handler=run_classification)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
