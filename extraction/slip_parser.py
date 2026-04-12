import fitz  # PyMuPDF
import easyocr
import re
import math
import traceback
import difflib
from typing import List, Dict, Tuple, Optional

# ============================================================================
# CONFIG
# ============================================================================

OCR_DPI = 200
T4_SECONDARY_OCR_DPIS = (260, 360)
T4_SECONDARY_OCR_FIELDS = (
    "box16_cpp",
    "box18_ei",
    "box20_rpp",
    "box22_tax_withheld",
    "box24_ei_insurable_earnings",
    "box26_cpp_pensionable_earnings",
)
T4_DECIMAL_NEIGHBOR_FIELDS = ("box16_cpp", "box18_ei", "box22_tax_withheld")
T4_BOX16_CROP_DPI = 600
NORMALIZED_PAGE_SIZE = 1000.0
TEXT_MIN_WORDS = 25
TEXT_MIN_CHARS = 100
OCR_ENABLED = True

# Initialize EasyOCR lazily/fail-soft: text layer parsing should still work.
reader = None
reader_init_attempted = False


def get_ocr_reader():
    global reader, reader_init_attempted
    if not OCR_ENABLED:
        return None
    if reader is not None:
        return reader
    if reader_init_attempted:
        return None
    reader_init_attempted = True
    try:
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    except Exception as e:
        reader = None
        print(f"Failed to initialize EasyOCR lazily: {e}")
    return reader


# ============================================================================
# BBOX MODEL
# ============================================================================

class BBox:
    """
    Unified bounding box model for both PDF text-layer words and OCR output.
    Coordinates are normalized to a 1000 x 1000 page space so extraction rules
    can work consistently across different DPI/page sizes.
    """
    def __init__(
        self,
        raw_bbox,
        text,
        conf=0.0,
        source="text",
        page_width: float = NORMALIZED_PAGE_SIZE,
        page_height: float = NORMALIZED_PAGE_SIZE,
        normalized: bool = True,
    ):
        self.raw = raw_bbox
        self.text = str(text).strip()
        self.clean_text = self.text.lower()
        self.conf = float(conf or 0.0)
        self.source = source
        self.page_width = page_width
        self.page_height = page_height

        xs = [p[0] for p in raw_bbox]
        ys = [p[1] for p in raw_bbox]
        self.x_min, self.x_max = min(xs), max(xs)
        self.y_min, self.y_max = min(ys), max(ys)
        self.cx = sum(xs) / 4.0
        self.cy = sum(ys) / 4.0
        self.width = self.x_max - self.x_min
        self.height = self.y_max - self.y_min
        self.normalized = normalized

        self.is_numeric = False
        self.value = 0.0
        self.numeric_conf = 0.0
        self._parse_numeric()

    @classmethod
    def from_pdf_word(cls, word_tuple, page_w: float, page_h: float):
        x0, y0, x1, y1, text, *_ = word_tuple
        return cls(
            raw_bbox=_normalize_rect_to_quad(x0, y0, x1, y1, page_w, page_h),
            text=text,
            conf=0.995,
            source="text",
            normalized=True,
        )

    @classmethod
    def from_ocr(cls, raw_bbox, text, conf, img_w: float, img_h: float):
        return cls(
            raw_bbox=_normalize_quad(raw_bbox, img_w, img_h),
            text=text,
            conf=conf,
            source="ocr",
            normalized=True,
        )

    def _parse_numeric(self):
        t = self.text.strip()

        # Common OCR fixes for CRA slips
        t = t.replace('|', '.').replace('/', '.')
        t = t.replace('O', '0').replace('o', '0')
        t = t.replace('I', '1').replace('l', '1') if _looks_numericish(t) else t

        # Space-separated cents: "43366 23" -> "43366.23"
        parts = t.split()
        if len(parts) == 2:
            left = parts[0].replace(',', '')
            right = parts[1]
            if right.isdigit() and len(right) == 2 and left.replace('.', '').replace('-', '').isdigit():
                t = f"{left}.{right}"
            elif right.isdigit() and len(right) == 1 and left.replace('.', '').replace('-', '').isdigit():
                t = f"{left}{right}"

        cleaned = re.sub(r'[^\d.\-]', '', t)
        if not cleaned or cleaned in ('.', '-', '-.'):
            return

        alpha = sum(1 for c in self.text if c.isalpha())
        if alpha > 1 and len(self.text) > 3 and not _looks_numericish(self.text):
            return

        try:
            if cleaned.count('.') > 1:
                p = cleaned.rsplit('.', 1)
                cleaned = p[0].replace('.', '') + '.' + p[1]
            self.value = float(cleaned)
            self.is_numeric = True
            self.numeric_conf = min(1.0, self.conf + 0.05 if self.source == "text" else self.conf)
        except ValueError:
            pass

    def as_dict(self):
        return {
            "text": self.text,
            "value": self.value if self.is_numeric else None,
            "conf": self.conf,
            "source": self.source,
            "bbox": [self.x_min, self.y_min, self.x_max, self.y_max],
        }


# ============================================================================
# NORMALIZATION HELPERS
# ============================================================================

def _normalize_quad(raw_bbox, page_w: float, page_h: float):
    return [
        [p[0] / page_w * NORMALIZED_PAGE_SIZE, p[1] / page_h * NORMALIZED_PAGE_SIZE]
        for p in raw_bbox
    ]


def _normalize_rect_to_quad(x0: float, y0: float, x1: float, y1: float, page_w: float, page_h: float):
    return [
        [x0 / page_w * NORMALIZED_PAGE_SIZE, y0 / page_h * NORMALIZED_PAGE_SIZE],
        [x1 / page_w * NORMALIZED_PAGE_SIZE, y0 / page_h * NORMALIZED_PAGE_SIZE],
        [x1 / page_w * NORMALIZED_PAGE_SIZE, y1 / page_h * NORMALIZED_PAGE_SIZE],
        [x0 / page_w * NORMALIZED_PAGE_SIZE, y1 / page_h * NORMALIZED_PAGE_SIZE],
    ]


def _looks_numericish(text: str) -> bool:
    return bool(re.fullmatch(r"[\dOolI|/.,\-\s$]+", text.strip()))


# ============================================================================
# TEXT / SCAN DETECTION
# ============================================================================

def analyze_text_layer(page) -> Dict:
    words = page.get_text("words") or []
    word_texts = [str(w[4]).strip() for w in words if len(w) >= 5 and str(w[4]).strip()]
    joined = " ".join(word_texts)
    alpha_words = sum(1 for w in word_texts if re.search(r"[A-Za-z]", w))
    digit_words = sum(1 for w in word_texts if re.search(r"\d", w))
    char_count = len(joined)
    looks_digital = len(word_texts) >= TEXT_MIN_WORDS and char_count >= TEXT_MIN_CHARS and (alpha_words + digit_words) >= 15
    return {
        "words": words,
        "text": joined,
        "word_count": len(word_texts),
        "char_count": char_count,
        "alpha_words": alpha_words,
        "digit_words": digit_words,
        "looks_digital": looks_digital,
    }


# ============================================================================
# CRA FIELD DEFINITIONS
# ============================================================================

YEAR_VALUES = {float(y) for y in range(2020, 2031)}

T4_FIELDS = [
    {"key": "box14_employment_income",        "box": 14, "anchors": ["employment income", "revenu d'emploi"]},
    {"key": "box22_tax_withheld",             "box": 22, "anchors": ["income tax deducted", "tax deducted", "impot sur le revenu retenu"]},
    {"key": "box16_cpp",                      "box": 16, "anchors": ["cpp contributions", "cpp con", "cotisations au rpc"]},
    {"key": "box17_qpp",                      "box": 17, "anchors": ["qpp contributions", "cotisations au rrq"]},
    {"key": "box18_ei",                       "box": 18, "anchors": ["ei premiums", "assurance-emploi"]},
    {"key": "box20_rpp",                      "box": 20, "anchors": ["rpp contributions", "cotisations a un rpa"]},
    {"key": "box24_ei_insurable_earnings",    "box": 24, "anchors": ["insurable earnings", "gains assurables"]},
    {"key": "box26_cpp_pensionable_earnings", "box": 26, "anchors": ["pensionable earnings", "gains ouvrant droit a pension"]},
    {"key": "box44_union_dues",               "box": 44, "anchors": ["union dues", "cotisations syndicales"]},
    {"key": "box46_charitable_donations",     "box": 46, "anchors": ["charitable donations", "dons de bienfaisance"]},
    {"key": "box52_pension_adjustment",       "box": 52, "anchors": ["pension adjustment", "facteur d'equivalence"]},
]

T3_FIELDS = [
    {"key": "box21_capital_gains",                "box": 21, "anchors": ["capital gains", "gains en capital"]},
    {"key": "box25_foreign_income",               "box": 25, "anchors": ["foreign non-business income", "revenu etranger"]},
    {"key": "box26_other_income",                 "box": 26, "anchors": ["other income", "autres revenus"]},
    {"key": "box34_foreign_tax_paid",             "box": 34, "anchors": ["foreign non-business income tax", "impot etranger"]},
    {"key": "box50_eligible_dividends_taxable",   "box": 50, "anchors": ["taxable amount of eligible", "montant imposable des dividendes determines"]},
]

T4PS_FIELDS = [
    {"key": "box30_eligible_dividends_actual",   "box": 30, "anchors": ["actual amount of eligible"]},
    {"key": "box31_eligible_dividends_taxable",  "box": 31, "anchors": ["taxable amount of eligible"]},
    {"key": "box32_eligible_dividend_credit",    "box": 32, "anchors": ["dividend tax credit for eligible"]},
    {"key": "box34_capital_gains_or_losses",     "box": 34, "anchors": ["capital gains or losses"]},
    {"key": "box35_other_employment_income",     "box": 35, "anchors": ["other employment income"]},
    {"key": "box41_epsp_contributions",          "box": 41, "anchors": ["sharing plan contributions", "cotisations au regime"]},
]

T2202_FIELDS = [
    {"key": "box21_months_part_time",         "box": 21, "anchors": ["eligible months part-time", "part-time months", "mois a temps partiel"]},
    {"key": "box22_months_full_time",         "box": 22, "anchors": ["eligible months full-time", "full-time months", "mois a temps plein"]},
    {"key": "box23_session_tuition",          "box": 23, "anchors": ["tuition fees for this session", "frais de scolarite pour cette session"]},
    {"key": "box24_total_months_part_time",      "box": 24, "anchors": ["part-time months", "mois a temps partiel"]},
    {"key": "box25_total_months_full_time",      "box": 25, "anchors": ["full-time months", "mois a temps plein"]},
    {"key": "box26_total_eligible_tuition",      "box": 26, "anchors": ["eligible tuition fees", "frais de scolarite admissibles"]},
]

T5_FIELDS = [
    {"key": "box11_non_eligible_dividends_taxable", "box": 11, "anchors": ["other than eligible dividends", "autres que des dividendes determines"]},
    {"key": "box12_non_eligible_dividend_credit",   "box": 12, "anchors": ["dividend tax credit for other than eligible dividends", "credit d'impot pour dividendes autres que determines"]},
    {"key": "box13_interest",                      "box": 13, "anchors": ["interest from canadian sources", "interets de sources canadiennes"]},
    {"key": "box15_foreign_income",              "box": 15, "anchors": ["foreign income", "revenu etranger"]},
    {"key": "box16_foreign_tax_paid",            "box": 16, "anchors": ["foreign tax paid", "impot etranger paye"]},
    {"key": "box24_actual_amount_eligible_div",  "box": 24, "anchors": ["actual amount of eligible dividends"]},
    {"key": "box25_eligible_dividends_taxable",  "box": 25, "anchors": ["taxable amount of eligible dividends"]},
    {"key": "box26_eligible_dividend_credit",    "box": 26, "anchors": ["dividend tax credit for eligible dividends"]},
]

SLIP_FIELDS = {
    "T4": T4_FIELDS,
    "T3": T3_FIELDS,
    "T4PS": T4PS_FIELDS,
    "T2202": T2202_FIELDS,
    "T5": T5_FIELDS,
}

PARSER_KEY_ALIASES = {
    "T4": {
        "box20_rpp_contributions": "box20_rpp",
    },
    "T5": {
        "box13_interest_income": "box13_interest",
        "box25_taxable_amount_eligible_div": "box25_eligible_dividends_taxable",
        "box26_dividend_tax_credit": "box26_eligible_dividend_credit",
    },
}


# ============================================================================
# TEXT NORMALIZATION / ANCHOR MATCHING
# ============================================================================

def normalize(text):
    return re.sub(r"['\"\$\-_\s]+", '', text.lower()).strip()


def has_anchor(text, aliases):
    norm_text = normalize(text)
    for alias in aliases:
        norm_alias = normalize(alias)
        if not norm_alias:
            continue
        if norm_alias in norm_text:
            return True
        alen = len(norm_alias)
        if len(norm_text) >= alen:
            for i in range(len(norm_text) - alen + 1):
                sub = norm_text[i:i + alen]
                if difflib.SequenceMatcher(None, norm_alias, sub).ratio() > 0.78:
                    return True
    return False


# ============================================================================
# NUMERIC / LABEL LOGIC
# ============================================================================

def merge_cents_globally(numeric_boxes: List[BBox]):
    """
    Merge adjacent dollars + cents fragments like:
      44196   50  -> 44196.50
    Operates in normalized coordinate space.
    """
    numeric_boxes = sorted(numeric_boxes, key=lambda b: (round(b.cy / 12), b.cx))
    consumed = set()
    merged = []

    for i, curr in enumerate(numeric_boxes):
        if id(curr) in consumed:
            continue

        if curr.value >= 1 and curr.value == int(curr.value):
            max_gap = 55 if curr.value >= 100 else 28
            for j in range(i + 1, min(i + 5, len(numeric_boxes))):
                adj = numeric_boxes[j]
                if id(adj) in consumed:
                    continue
                if abs(adj.cy - curr.cy) > 10:
                    break
                x_gap = adj.x_min - curr.x_max
                if x_gap < 0 or x_gap > max_gap:
                    continue
                adj_digits = re.sub(r'[^\d]', '', adj.text)
                if adj_digits.isdigit() and len(adj_digits) == 2 and int(adj_digits) < 100:
                    if '.' not in str(curr.text) or curr.value == int(curr.value):
                        curr.value = float(f"{int(curr.value)}.{adj_digits.zfill(2)}")
                        curr.text = f"{int(curr.value)}.{adj_digits.zfill(2)}"
                        curr.clean_text = curr.text.lower()
                        curr.is_numeric = True
                        curr.numeric_conf = min(1.0, max(curr.numeric_conf, adj.numeric_conf) - 0.01)
                        consumed.add(id(adj))
                        break

        merged.append(curr)

    return merged, consumed


def is_box_label(bbox: BBox, consumed_ids):
    if not bbox.is_numeric:
        return False
    if id(bbox) in consumed_ids:
        return False
    if '.' in bbox.text or ',' in bbox.text:
        return False
    v = bbox.value
    if v != int(v):
        return False
    iv = int(v)
    return 0 <= iv <= 60 and bbox.width < 45 and bbox.height < 30


def is_year(bbox: BBox):
    return bbox.is_numeric and bbox.value in YEAR_VALUES


def score_candidate(label_box: Optional[BBox], anchor_box: Optional[BBox], value_box: BBox, strategy: str):
    score = value_box.numeric_conf
    if strategy == "label" and label_box:
        y_penalty = min(0.25, abs(value_box.cy - label_box.cy) / 120.0)
        x_bonus = max(0.0, 0.15 - abs((value_box.x_min - label_box.x_max) - 18) / 250.0)
        score += 0.18 + x_bonus - y_penalty
    elif strategy == "anchor" and anchor_box:
        y_diff = max(0.0, value_box.cy - anchor_box.cy)
        x_diff = abs(value_box.cx - anchor_box.cx)
        score += 0.10 - min(0.10, x_diff / 500.0) - min(0.10, abs(y_diff - 35) / 350.0)

    if value_box.source == "text":
        score += 0.12
    return max(0.0, min(0.99, score))


def field_search_cutoff(slip_type: str) -> float:
    return {
        "T4": 0.72,
        "T5": 0.72,
        "T2202": 0.85,
    }.get(slip_type, 0.60)


def field_value_bounds(slip_type: str, box_num: int) -> Tuple[float, float]:
    if slip_type == "T2202" and box_num in {21, 22, 24, 25}:
        return 0.0, 12.0
    if slip_type == "T2202" and box_num in {23, 26}:
        return 0.0, 100000.0
    if slip_type == "T5" and box_num in {11, 12, 13, 15, 16, 24, 25, 26}:
        return 0.0, 10000000.0
    if slip_type == "T4" and box_num in {14, 16, 18, 20, 22, 24, 26, 44, 46, 52}:
        return 0.0, 10000000.0
    return 0.0, 10000000.0


def allows_sub_dollar_value(slip_type: str, box_num: int) -> bool:
    return (slip_type, box_num) in {
        ("T4PS", 32),
        ("T5", 12),
        ("T5", 26),
    }


def looks_like_field_value(value_box: BBox, slip_type: str, box_num: int) -> bool:
    if not value_box.is_numeric or is_year(value_box):
        return False

    digits = re.sub(r"[^0-9]", "", value_box.text or "")
    if not digits:
        return False
    if re.search(r"[A-Za-z]", value_box.text or ""):
        return False

    lower, upper = field_value_bounds(slip_type, box_num)
    if not (lower <= value_box.value <= upper):
        return False

    # OCR often produces tiny decimal fragments such as ".98" detached from the
    # actual amount; keep these out unless the field is explicitly a month count.
    if value_box.value < 1 and box_num not in {21, 22, 24, 25} and not allows_sub_dollar_value(slip_type, box_num):
        text = (value_box.text or "").strip()
        if text.startswith(".") or len(digits) <= 2:
            return False

    return True


def build_extraction_pools(all_bboxes: List[BBox], slip_type: str):
    page_height = NORMALIZED_PAGE_SIZE
    top = [b for b in all_bboxes if b.cy < page_height * field_search_cutoff(slip_type)]
    all_numeric = [b for b in top if b.is_numeric]
    merged_numeric, consumed_ids = merge_cents_globally(all_numeric)
    label_pool = [b for b in merged_numeric if is_box_label(b, consumed_ids)]
    value_pool = [b for b in merged_numeric if not is_box_label(b, consumed_ids) and not is_year(b)]

    for b in top:
        if b.is_numeric and b.text.startswith('.') and b not in value_pool:
            value_pool.append(b)

    return top, label_pool, value_pool


def find_best_anchor_candidate(
    top: List[BBox],
    value_pool: List[BBox],
    anchors,
    slip_type: str,
    box_num: int,
    *,
    min_y: float = -12,
    max_y: float = 110,
    min_x: float = -20,
    max_x: float = 280,
    exclude_instruction_like: bool = False,
):
    candidates = []
    anchor_boxes = [b for b in top if not b.is_numeric and has_anchor(b.clean_text, anchors)]
    if exclude_instruction_like:
        anchor_boxes = [b for b in anchor_boxes if not is_instruction_like_anchor(b.clean_text)]
    for ab in anchor_boxes:
        for vb in value_pool:
            if not looks_like_field_value(vb, slip_type, box_num):
                continue
            y_diff = vb.cy - ab.cy
            x_diff = vb.cx - ab.cx
            if min_y <= y_diff <= max_y and min_x <= x_diff <= max_x:
                score = score_candidate(None, ab, vb, "anchor")
                if abs(y_diff) <= 16 and x_diff >= 0:
                    score += 0.06
                elif y_diff > 0 and x_diff >= -10:
                    score += 0.03
                candidates.append((score, vb, ab))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_value, best_anchor = candidates[0]
    return {
        "score": round(best_score, 4),
        "value_box": best_value,
        "anchor_box": best_anchor,
    }


def is_instruction_like_anchor(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        phrase in lowered
        for phrase in [
            "for details",
            "see line",
            "subtract any amount",
            "report the",
            "schedule 3",
            "line 13000",
            "details, see",
        ]
    )


def find_strict_row_anchor_candidate(top: List[BBox], value_pool: List[BBox], anchors, slip_type: str, box_num: int):
    candidates = []
    anchor_boxes = [
        b for b in top
        if not b.is_numeric
        and has_anchor(b.clean_text, anchors)
        and not is_instruction_like_anchor(b.clean_text)
        and len((b.text or "").strip()) <= 60
    ]
    for ab in anchor_boxes:
        for vb in value_pool:
            if not looks_like_field_value(vb, slip_type, box_num):
                continue
            y_diff = abs(vb.cy - ab.cy)
            x_gap = vb.x_min - ab.x_max
            if y_diff <= 14 and 12 <= x_gap <= 220:
                score = score_candidate(None, ab, vb, "anchor") + 0.06
                candidates.append((score, vb, ab))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_value, best_anchor = candidates[0]
    return {
        "score": round(best_score, 4),
        "value_box": best_value,
        "anchor_box": best_anchor,
    }


def find_best_label_candidate(label_pool: List[BBox], value_pool: List[BBox], slip_type: str, box_num: int):
    candidates = []
    matching_labels = [lb for lb in label_pool if int(lb.value) == box_num]
    for lb in matching_labels:
        for vb in value_pool:
            if not looks_like_field_value(vb, slip_type, box_num):
                continue
            y_diff = abs(vb.cy - lb.cy)
            x_gap = vb.x_min - lb.x_max
            if y_diff <= 16 and 4 <= x_gap <= 420:
                score = score_candidate(lb, None, vb, "label") + 0.04
                candidates.append((score, vb, lb, x_gap, y_diff))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], -item[3], -item[4]), reverse=True)
    best_score, best_value, best_label, _, _ = candidates[0]
    return {
        "score": round(best_score, 4),
        "value_box": best_value,
        "anchor_box": None,
        "label_box": best_label,
    }


def maybe_override_field(result, confidences, evidence, key: str, candidate: Optional[dict], *, min_gain: float = 0.05, strategy: str = "anchor_refined"):
    if not candidate:
        return

    current_conf = confidences.get(key, -1.0)
    if key not in result or candidate["score"] >= current_conf + min_gain:
        value_box = candidate["value_box"]
        anchor_box = candidate["anchor_box"]
        label_box = candidate.get("label_box")
        result[key] = value_box.value
        confidences[key] = candidate["score"]
        evidence[key] = {
            "strategy": strategy,
            "value": value_box.as_dict(),
            "label": label_box.as_dict() if label_box else None,
            "anchor": anchor_box.as_dict() if anchor_box else None,
        }


def round_month_value(value: float) -> Optional[float]:
    if value is None:
        return None
    nearest = round(value)
    if 0 <= nearest <= 12 and abs(value - nearest) <= 0.15:
        return float(nearest)
    return None


# ============================================================================
# WORD MERGING FOR PDF TEXT LAYER
# ============================================================================

def merge_text_words_to_lines(words: List[BBox]) -> List[BBox]:
    """
    Merge adjacent text-layer words on the same line into larger text spans.
    This helps anchor matching like "employment income" instead of two boxes.
    """
    if not words:
        return []

    words = sorted(words, key=lambda b: (round(b.cy / 8), b.x_min))
    merged = []
    current = None

    for w in words:
        if current is None:
            current = _copy_bbox(w)
            continue

        same_line = abs(w.cy - current.cy) <= 7
        gap = w.x_min - current.x_max
        should_merge = same_line and -2 <= gap <= 18 and not (current.is_numeric and w.is_numeric)

        if should_merge:
            current.text = f"{current.text} {w.text}".strip()
            current.clean_text = current.text.lower()
            current.x_max = max(current.x_max, w.x_max)
            current.y_min = min(current.y_min, w.y_min)
            current.y_max = max(current.y_max, w.y_max)
            current.cx = (current.x_min + current.x_max) / 2.0
            current.cy = (current.y_min + current.y_max) / 2.0
            current.width = current.x_max - current.x_min
            current.height = current.y_max - current.y_min
            current.conf = min(current.conf, w.conf)
            current._parse_numeric()
        else:
            merged.append(current)
            current = _copy_bbox(w)

    if current is not None:
        merged.append(current)
    return merged


def _copy_bbox(b: BBox) -> BBox:
    return BBox(
        raw_bbox=[[b.x_min, b.y_min], [b.x_max, b.y_min], [b.x_max, b.y_max], [b.x_min, b.y_max]],
        text=b.text,
        conf=b.conf,
        source=b.source,
        normalized=True,
    )


# ============================================================================
# EXTRACTOR CORE
# ============================================================================

def extract_fields(all_bboxes: List[BBox], field_defs, slip_type: str):
    top, label_pool, value_pool = build_extraction_pools(all_bboxes, slip_type)

    used_values = set()
    extracted = {}
    confidences = {}
    evidence = {}

    def is_better_choice(score, tie_break, best_score, best_tie_break):
        if score > best_score + 1e-6:
            return True
        if abs(score - best_score) <= 1e-6 and (best_tie_break is None or tie_break > best_tie_break):
            return True
        return False

    for field in field_defs:
        key = field["key"]
        box_num = field["box"]
        anchors = field.get("anchors", [])

        best_choice = None
        best_score = -1.0
        best_src = None
        best_anchor_box = None
        best_label_box = None
        best_tie_break = None

        # Strategy A: label -> nearest value to the right on same row
        matching_labels = [lb for lb in label_pool if int(lb.value) == box_num]
        for lb in matching_labels:
            for vb in value_pool:
                if id(vb) in used_values:
                    continue
                if not looks_like_field_value(vb, slip_type, box_num):
                    continue
                y_diff = abs(vb.cy - lb.cy)
                x_gap = vb.x_min - lb.x_max
                if y_diff <= 16 and 4 <= x_gap <= 420:
                    score = score_candidate(lb, None, vb, "label")
                    tie_break = (-x_gap, -y_diff, vb.source == "text")
                    if is_better_choice(score, tie_break, best_score, best_tie_break):
                        best_score = score
                        best_tie_break = tie_break
                        best_choice = vb
                        best_src = "label"
                        best_label_box = lb
                        best_anchor_box = None

        # Strategy A2: value can sit directly below the numeric box label on some slips.
        for lb in matching_labels:
            for vb in value_pool:
                if id(vb) in used_values:
                    continue
                if not looks_like_field_value(vb, slip_type, box_num):
                    continue
                y_gap = vb.y_min - lb.y_max
                x_diff = abs(vb.cx - lb.cx)
                if 2 <= y_gap <= 80 and x_diff <= 95:
                    score = score_candidate(lb, None, vb, "label") - 0.03
                    tie_break = (-y_gap, -x_diff, vb.source == "text")
                    if is_better_choice(score, tie_break, best_score, best_tie_break):
                        best_score = score
                        best_tie_break = tie_break
                        best_choice = vb
                        best_src = "label_below"
                        best_label_box = lb
                        best_anchor_box = None

        # Strategy B: anchor -> value below / slightly right
        if anchors:
            anchor_boxes = [b for b in top if not b.is_numeric and has_anchor(b.clean_text, anchors)]
            for ab in anchor_boxes:
                for vb in value_pool:
                    if id(vb) in used_values:
                        continue
                    if not looks_like_field_value(vb, slip_type, box_num):
                        continue
                    y_diff = vb.cy - ab.cy
                    x_diff = abs(vb.cx - ab.cx)
                    if 2 <= y_diff <= 110 and x_diff <= 230:
                        score = score_candidate(None, ab, vb, "anchor")
                        tie_break = (-abs(y_diff - 18), -x_diff, vb.source == "text")
                        if is_better_choice(score, tie_break, best_score, best_tie_break):
                            best_score = score
                            best_tie_break = tie_break
                            best_choice = vb
                            best_src = "anchor"
                            best_anchor_box = ab
                            best_label_box = None

        if best_choice is not None:
            extracted[key] = best_choice.value
            confidences[key] = round(best_score, 4)
            evidence[key] = {
                "strategy": best_src,
                "value": best_choice.as_dict(),
                "label": best_label_box.as_dict() if best_label_box else None,
                "anchor": best_anchor_box.as_dict() if best_anchor_box else None,
            }
            used_values.add(id(best_choice))
            print(f"  [{slip_type}] Box {box_num:2d} -> {best_choice.value:>12.2f} [{best_src.upper()} score={best_score:.2f}] '{best_choice.text}'")
        else:
            print(f"  [{slip_type}] Box {box_num:2d} -> (empty)")

    return extracted, confidences, evidence


# ============================================================================
# SPECIALIZED EXTRACTORS
# ============================================================================

def extract_t4(all_bboxes):
    result, confidences, evidence = extract_fields(all_bboxes, T4_FIELDS, "T4")
    top, label_pool, value_pool = build_extraction_pools(all_bboxes, "T4")

    for key, box_num in [
        ("box16_cpp", 16),
        ("box18_ei", 18),
        ("box20_rpp", 20),
        ("box22_tax_withheld", 22),
        ("box24_ei_insurable_earnings", 24),
        ("box26_cpp_pensionable_earnings", 26),
    ]:
        label_candidate = find_best_label_candidate(label_pool, value_pool, "T4", box_num)
        if label_candidate:
            maybe_override_field(result, confidences, evidence, key, label_candidate, min_gain=-1.0, strategy="t4_label_refined")

    targeted_specs = {
        "box14_employment_income": {"anchors": ["employment income", "revenu d'emploi"], "max_x": 420, "max_y": 70},
    }

    for key, spec in targeted_specs.items():
        candidate = find_best_anchor_candidate(
            top,
            value_pool,
            spec["anchors"],
            "T4",
            next(field["box"] for field in T4_FIELDS if field["key"] == key),
            max_x=spec["max_x"],
            max_y=spec["max_y"],
        )
        maybe_override_field(result, confidences, evidence, key, candidate, min_gain=0.02, strategy="t4_anchor_refined")

    employment_income = result.get("box14_employment_income")
    if employment_income is not None:
        for key in ("box22_tax_withheld", "box16_cpp", "box18_ei"):
            if result.get(key, 0.0) > employment_income:
                candidate = find_best_anchor_candidate(
                    top,
                    value_pool,
                    next(field["anchors"] for field in T4_FIELDS if field["key"] == key),
                    "T4",
                    next(field["box"] for field in T4_FIELDS if field["key"] == key),
                    max_x=280,
                    max_y=60,
                )
                if candidate and candidate["value_box"].value <= employment_income:
                    maybe_override_field(result, confidences, evidence, key, candidate, min_gain=-1.0, strategy="t4_plausibility_fix")

    if evidence.get("box20_rpp", {}).get("strategy") == "anchor":
        result.pop("box20_rpp", None)
        confidences.pop("box20_rpp", None)
        evidence.pop("box20_rpp", None)
    elif result.get("box20_rpp") and result.get("box20_rpp") in {
        result.get("box14_employment_income"),
        result.get("box24_ei_insurable_earnings"),
        result.get("box26_cpp_pensionable_earnings"),
    }:
        result.pop("box20_rpp", None)
        confidences.pop("box20_rpp", None)
        evidence.pop("box20_rpp", None)

    pensionable_candidate = find_best_anchor_candidate(
        top,
        value_pool,
        ["pensionable earnings", "gains ouvrant droit a pension"],
        "T4",
        26,
        max_x=220,
        max_y=55,
    )
    if pensionable_candidate:
        maybe_override_field(result, confidences, evidence, "box26_cpp_pensionable_earnings", pensionable_candidate, min_gain=-1.0, strategy="t4_box26_refined")

    return result, confidences, evidence


def extract_t5(all_bboxes):
    result, confidences, evidence = extract_fields(all_bboxes, T5_FIELDS, "T5")
    top, _, value_pool = build_extraction_pools(all_bboxes, "T5")

    targeted_specs = {
        "box11_non_eligible_dividends_taxable": {"box": 11, "anchors": ["other than eligible dividends", "autres que des dividendes determines"], "max_x": 380, "max_y": 80},
        "box12_non_eligible_dividend_credit": {"box": 12, "anchors": ["dividend tax credit for other than eligible dividends", "credit d'impot pour dividendes autres que determines"], "max_x": 420, "max_y": 90},
        "box13_interest": {"box": 13, "anchors": ["interest from canadian sources", "interets de sources canadiennes"], "max_x": 320, "max_y": 70},
        "box24_actual_amount_eligible_div": {"box": 24, "anchors": ["actual amount of eligible dividends"], "max_x": 380, "max_y": 80},
        "box25_eligible_dividends_taxable": {"box": 25, "anchors": ["taxable amount of eligible dividends"], "max_x": 380, "max_y": 80},
        "box26_eligible_dividend_credit": {"box": 26, "anchors": ["dividend tax credit for eligible dividends"], "max_x": 420, "max_y": 90},
    }

    for key, spec in targeted_specs.items():
        candidate = find_best_anchor_candidate(
            top,
            value_pool,
            spec["anchors"],
            "T5",
            spec["box"],
            max_x=spec["max_x"],
            max_y=spec["max_y"],
        )
        maybe_override_field(result, confidences, evidence, key, candidate, min_gain=0.02, strategy="t5_anchor_refined")

    actual_div = result.get("box24_actual_amount_eligible_div")
    taxable_div = result.get("box25_eligible_dividends_taxable")
    dividend_credit = result.get("box26_eligible_dividend_credit")

    if actual_div is not None and taxable_div is not None and taxable_div < actual_div:
        result["box24_actual_amount_eligible_div"], result["box25_eligible_dividends_taxable"] = taxable_div, actual_div
        confidences["box24_actual_amount_eligible_div"], confidences["box25_eligible_dividends_taxable"] = confidences.get("box25_eligible_dividends_taxable", 0.0), confidences.get("box24_actual_amount_eligible_div", 0.0)
        evidence["box24_actual_amount_eligible_div"], evidence["box25_eligible_dividends_taxable"] = evidence.get("box25_eligible_dividends_taxable"), evidence.get("box24_actual_amount_eligible_div")

    if taxable_div is not None and dividend_credit is not None and dividend_credit > taxable_div:
        candidate = find_best_anchor_candidate(
            top,
            value_pool,
            targeted_specs["box26_eligible_dividend_credit"]["anchors"],
            "T5",
            26,
            max_x=420,
            max_y=90,
        )
        if candidate and candidate["value_box"].value <= taxable_div:
            maybe_override_field(result, confidences, evidence, "box26_eligible_dividend_credit", candidate, min_gain=-1.0, strategy="t5_dividend_credit_fix")

    return result, confidences, evidence


def extract_t2202(all_bboxes):
    result, confidences, evidence = extract_fields(all_bboxes, T2202_FIELDS, "T2202")
    top, _, value_pool = build_extraction_pools(all_bboxes, "T2202")

    month_specs = {
        "box21_months_part_time": {"box": 21, "anchors": ["eligible months part-time", "part-time months", "mois a temps partiel"]},
        "box22_months_full_time": {"box": 22, "anchors": ["eligible months full-time", "full-time months", "mois a temps plein"]},
        "box24_total_months_part_time": {"box": 24, "anchors": ["part-time months", "mois a temps partiel"]},
        "box25_total_months_full_time": {"box": 25, "anchors": ["full-time months", "mois a temps plein"]},
    }
    tuition_specs = {
        "box23_session_tuition": {"box": 23, "anchors": ["tuition fees for this session", "frais de scolarite pour cette session"]},
        "box26_total_eligible_tuition": {"box": 26, "anchors": ["eligible tuition fees", "frais de scolarite admissibles"]},
    }

    for key, spec in month_specs.items():
        current_value = result.get(key)
        rounded = round_month_value(current_value) if current_value is not None else None
        if rounded is not None:
            result[key] = rounded
            continue

        candidate = find_best_anchor_candidate(
            top,
            value_pool,
            spec["anchors"],
            "T2202",
            spec["box"],
            min_y=-10,
            max_y=55,
            min_x=-10,
            max_x=180,
        )
        if candidate:
            month_value = round_month_value(candidate["value_box"].value)
            if month_value is not None:
                candidate["value_box"].value = month_value
                maybe_override_field(result, confidences, evidence, key, candidate, min_gain=-1.0, strategy="t2202_month_fix")

    for key, spec in tuition_specs.items():
        if result.get(key) is not None and result[key] > 12:
            continue
        candidate = find_best_anchor_candidate(
            top,
            value_pool,
            spec["anchors"],
            "T2202",
            spec["box"],
            min_y=-8,
            max_y=70,
            min_x=-10,
            max_x=260,
        )
        if candidate and candidate["value_box"].value > 12:
            maybe_override_field(result, confidences, evidence, key, candidate, min_gain=-1.0, strategy="t2202_tuition_fix")

    apply_t2202_totals_row(all_bboxes, result, confidences, evidence)

    return result, confidences, evidence


def apply_t2202_totals_row(all_bboxes, result, confidences, evidence):
    top = [b for b in all_bboxes if b.cy < NORMALIZED_PAGE_SIZE * field_search_cutoff("T2202")]
    numeric = [b for b in top if b.is_numeric]
    merged, consumed = merge_cents_globally(numeric)

    totals_anchors = [
        b for b in top
        if not b.is_numeric
        and ('totals' in b.clean_text or 'totaux' in b.clean_text)
    ]
    if not totals_anchors:
        return

    for anchor in totals_anchors:
        same_line_values = [
            vb for vb in merged
            if abs(vb.cy - anchor.cy) < 14
            and vb.cx > anchor.cx
            and not is_year(vb)
        ]
        if not same_line_values:
            continue

        same_line_values.sort(key=lambda vb: vb.cx)
        month_values = [
            vb for vb in same_line_values
            if 0 <= vb.value <= 12
            and int(round(vb.value)) not in {24, 25, 26}
        ]
        tuition_values = [
            vb for vb in same_line_values
            if vb.value > 12
            and int(round(vb.value)) not in {24, 25, 26}
        ]

        if "box24_total_months_part_time" not in result and month_values:
            chosen = month_values[0]
            month_value = round_month_value(chosen.value)
            if month_value is not None:
                result["box24_total_months_part_time"] = month_value
                confidences["box24_total_months_part_time"] = round(score_candidate(None, anchor, chosen, "anchor") + 0.03, 4)
                evidence["box24_total_months_part_time"] = {
                    "strategy": "totals_row",
                    "value": chosen.as_dict(),
                    "label": None,
                    "anchor": anchor.as_dict(),
                }

        if "box25_total_months_full_time" not in result and len(month_values) >= 2:
            chosen = month_values[1]
            month_value = round_month_value(chosen.value)
            if month_value is not None:
                result["box25_total_months_full_time"] = month_value
                confidences["box25_total_months_full_time"] = round(score_candidate(None, anchor, chosen, "anchor") + 0.03, 4)
                evidence["box25_total_months_full_time"] = {
                    "strategy": "totals_row",
                    "value": chosen.as_dict(),
                    "label": None,
                    "anchor": anchor.as_dict(),
                }

        if "box26_total_eligible_tuition" not in result and tuition_values:
            chosen = tuition_values[-1]
            result["box26_total_eligible_tuition"] = chosen.value
            confidences["box26_total_eligible_tuition"] = round(score_candidate(None, anchor, chosen, "anchor") + 0.03, 4)
            evidence["box26_total_eligible_tuition"] = {
                "strategy": "totals_row",
                "value": chosen.as_dict(),
                "label": None,
                "anchor": anchor.as_dict(),
            }
            print(f"  [T2202] Tuition from Totals row: {chosen.value}")

        if (
            "box24_total_months_part_time" in result
            or "box25_total_months_full_time" in result
            or "box26_total_eligible_tuition" in result
        ):
            break


def extract_t3(all_bboxes):
    result, confidences, evidence = extract_fields(all_bboxes, T3_FIELDS, "T3")
    top, _, value_pool = build_extraction_pools(all_bboxes, "T3")

    for key, box_num, anchors in [
        ("box26_other_income", 26, ["other income", "autres revenus"]),
        ("box50_eligible_dividends_taxable", 50, ["taxable amount of eligible", "montant imposable des dividendes determines"]),
    ]:
        candidate = find_strict_row_anchor_candidate(
            top,
            value_pool,
            anchors,
            "T3",
            box_num,
        )
        if candidate:
            maybe_override_field(result, confidences, evidence, key, candidate, min_gain=-1.0, strategy="t3_anchor_refined")
        elif key in result:
            result.pop(key, None)
            confidences.pop(key, None)
            evidence.pop(key, None)

    top = [b for b in all_bboxes if b.cy < NORMALIZED_PAGE_SIZE * 0.60]
    numeric = [b for b in top if b.is_numeric]
    merged, consumed = merge_cents_globally(numeric)
    value_pool = [b for b in merged if not is_box_label(b, consumed) and not is_year(b)]
    label_pool = [b for b in merged if is_box_label(b, consumed)]
    t3_box_map = {f["box"]: f["key"] for f in T3_FIELDS}

    for lb in label_pool:
        iv = int(lb.value)
        if iv not in t3_box_map:
            continue
        fk = t3_box_map[iv]
        if fk in {"box26_other_income", "box50_eligible_dividends_taxable"}:
            continue
        if fk in result:
            continue
        candidates = []
        for vb in value_pool:
            y_diff = abs(vb.cy - lb.cy)
            x_gap = vb.x_min - lb.x_max
            if y_diff < 10 and 6 < x_gap < 180 and vb.value <= 50000:
                candidates.append((score_candidate(lb, None, vb, "label"), vb))
        if candidates:
            candidates.sort(key=lambda c: c[0], reverse=True)
            score, best = candidates[0]
            result[fk] = best.value
            confidences[fk] = round(score, 4)
            evidence[fk] = {"strategy": "t3_other_info", "value": best.as_dict(), "label": lb.as_dict(), "anchor": None}
            print(f"  [T3-extra] Box {iv} -> {best.value} '{best.text}'")

    return result, confidences, evidence


def extract_t4ps(all_bboxes):
    result, confidences, evidence = extract_fields(all_bboxes, T4PS_FIELDS, "T4PS")
    top, _, value_pool = build_extraction_pools(all_bboxes, "T4PS")

    targeted_specs = {
        "box32_eligible_dividend_credit": {"box": 32, "anchors": ["dividend tax credit for eligible dividends", "dividend tax credit for eligible"]},
        "box34_capital_gains_or_losses": {"box": 34, "anchors": ["capital gains or losses"]},
        "box35_other_employment_income": {"box": 35, "anchors": ["other employment income"]},
        "box41_epsp_contributions": {"box": 41, "anchors": ["sharing plan contributions", "cotisations au regime"]},
    }

    for key, spec in targeted_specs.items():
        candidate = find_best_anchor_candidate(
            top,
            value_pool,
            spec["anchors"],
            "T4PS",
            spec["box"],
            min_y=-10,
            max_y=80,
            min_x=-10,
            max_x=320,
        )
        if candidate:
            maybe_override_field(result, confidences, evidence, key, candidate, min_gain=-1.0, strategy="t4ps_anchor_refined")

    if result.get("box35_other_employment_income") and result.get("box34_capital_gains_or_losses") == result.get("box35_other_employment_income"):
        result.pop("box34_capital_gains_or_losses", None)
        confidences.pop("box34_capital_gains_or_losses", None)
        evidence.pop("box34_capital_gains_or_losses", None)

    actual_div = result.get("box30_eligible_dividends_actual")
    taxable_div = result.get("box31_eligible_dividends_taxable")
    if actual_div is not None and taxable_div is not None and taxable_div < actual_div:
        result["box30_eligible_dividends_actual"], result["box31_eligible_dividends_taxable"] = taxable_div, actual_div
        confidences["box30_eligible_dividends_actual"], confidences["box31_eligible_dividends_taxable"] = confidences.get("box31_eligible_dividends_taxable", 0.0), confidences.get("box30_eligible_dividends_actual", 0.0)
        evidence["box30_eligible_dividends_actual"], evidence["box31_eligible_dividends_taxable"] = evidence.get("box31_eligible_dividends_taxable"), evidence.get("box30_eligible_dividends_actual")

    return result, confidences, evidence


# ============================================================================
# PDF / OCR INGESTION
# ============================================================================

def extract_text_bboxes(page) -> Tuple[List[BBox], Dict]:
    analysis = analyze_text_layer(page)
    page_w, page_h = float(page.rect.width), float(page.rect.height)
    boxes = [BBox.from_pdf_word(w, page_w, page_h) for w in analysis["words"] if len(w) >= 5 and str(w[4]).strip()]
    boxes = merge_text_words_to_lines(boxes)
    return boxes, analysis


def extract_ocr_bboxes(page, dpi: Optional[int] = None) -> Tuple[List[BBox], Dict]:
    ocr_reader = get_ocr_reader()
    if ocr_reader is None:
        return [], {"ocr_used": False, "reason": "easyocr_unavailable"}

    target_dpi = dpi or OCR_DPI
    pix = page.get_pixmap(dpi=target_dpi, alpha=False)
    img_data = pix.tobytes("png")
    results = ocr_reader.readtext(img_data)
    boxes = [BBox.from_ocr(bbox, text, conf, pix.width, pix.height) for bbox, text, conf in results if str(text).strip()]
    return boxes, {
        "ocr_used": True,
        "ocr_count": len(boxes),
        "dpi": target_dpi,
        "image_width": pix.width,
        "image_height": pix.height,
    }


def extract_ocr_text_from_clip(page, clip_rect, dpi: int) -> List[Tuple[str, float]]:
    ocr_reader = get_ocr_reader()
    if ocr_reader is None:
        return []
    pix = page.get_pixmap(dpi=dpi, alpha=False, clip=clip_rect)
    img_data = pix.tobytes("png")
    results = ocr_reader.readtext(img_data)
    return [(str(text).strip(), float(conf or 0.0)) for _, text, conf in results if str(text).strip()]


# ============================================================================
# SLIP TYPE DETECTION
# ============================================================================

def determine_slip_type(text_blob: str, filename: str):
    fname_lower = (filename or "").lower()
    if "t4ps" in fname_lower:
        return "T4PS"
    if "t2202" in fname_lower:
        return "T2202"
    if re.search(r'(^|[^a-z])t5([^a-z]|$)', fname_lower):
        return "T5"
    if re.search(r'(^|[^a-z])t4([^a-z]|$)', fname_lower):
        return "T4"
    if re.search(r'(^|[^a-z])t3([^a-z]|$)', fname_lower):
        return "T3"

    blob_lower = (text_blob or "").lower()
    if re.search(r'\bt4ps\b', blob_lower):
        return "T4PS"
    if re.search(r'\bt2202\b', blob_lower):
        return "T2202"
    if re.search(r'\bt-?5\b', blob_lower):
        return "T5"
    if re.search(r'\bt-?4\b', blob_lower):
        return "T4"
    if re.search(r'\bt-?3\b', blob_lower):
        return "T3"

    # CRA-form phrase hints
    if "statement of remuneration paid" in blob_lower:
        return "T4"
    if "statement of investment income" in blob_lower:
        return "T5"
    if "statement of trust income allocations" in blob_lower:
        return "T3"
    if "tuition and enrolment certificate" in blob_lower:
        return "T2202"

    return "UNKNOWN"


# ============================================================================
# HYBRID EXTRACTION ORCHESTRATION
# ============================================================================

def run_extractor(slip_type: str, bboxes: List[BBox]):
    if slip_type == "T4":
        return extract_t4(bboxes)
    if slip_type == "T3":
        return extract_t3(bboxes)
    if slip_type == "T4PS":
        return extract_t4ps(bboxes)
    if slip_type == "T2202":
        return extract_t2202(bboxes)
    if slip_type == "T5":
        return extract_t5(bboxes)
    return {}, {}, {}


def normalize_extraction_keys(slip_type: str, data: dict, confidence: dict, evidence: dict):
    aliases = PARSER_KEY_ALIASES.get(slip_type, {})
    if not aliases:
        return data, confidence, evidence

    normalized_data = {}
    normalized_confidence = {}
    normalized_evidence = {}

    for key, value in data.items():
        target_key = aliases.get(key, key)
        current_conf = normalized_confidence.get(target_key, -1.0)
        next_conf = confidence.get(key, 0.0)
        if target_key not in normalized_data or next_conf >= current_conf:
            normalized_data[target_key] = value
            normalized_confidence[target_key] = next_conf
            normalized_evidence[target_key] = evidence.get(key)

    return normalized_data, normalized_confidence, normalized_evidence


def choose_better_result(text_result: dict, ocr_result: dict):
    """
    Choose the best source per field instead of picking a single primary result.
    This helps when text-layer extraction is right for some boxes and OCR is
    right for others on the same slip.
    """
    text_data = dict(text_result.get("data", {}))
    text_conf = dict(text_result.get("confidence", {}))
    text_evidence = dict(text_result.get("evidence", {}))
    ocr_data = dict(ocr_result.get("data", {}))
    ocr_conf = dict(ocr_result.get("confidence", {}))
    ocr_evidence = dict(ocr_result.get("evidence", {}))

    text_avg = _avg_conf(text_conf)
    ocr_avg = _avg_conf(ocr_conf)
    preferred_engine = "text" if (len(text_data), text_avg) >= (len(ocr_data), ocr_avg) else "ocr"
    primary = text_result if preferred_engine == "text" else ocr_result

    merged = {
        **primary,
        "data": {},
        "confidence": {},
        "evidence": {},
        "meta": dict(primary.get("meta", {})),
    }
    merged["meta"]["comparison"] = {
        "text": {"field_count": len(text_data), "avg_conf": text_avg},
        "ocr": {"field_count": len(ocr_data), "avg_conf": ocr_avg},
    }
    merged["meta"]["field_sources"] = {}

    all_keys = sorted(set(text_data) | set(ocr_data))
    for key in all_keys:
        has_text = key in text_data
        has_ocr = key in ocr_data
        if has_text and not has_ocr:
            chosen_engine = "text"
        elif has_ocr and not has_text:
            chosen_engine = "ocr"
        else:
            text_score = text_conf.get(key, 0.0)
            ocr_score = ocr_conf.get(key, 0.0)
            if text_score > ocr_score:
                chosen_engine = "text"
            elif ocr_score > text_score:
                chosen_engine = "ocr"
            else:
                chosen_engine = preferred_engine

        if chosen_engine == "text":
            merged["data"][key] = text_data[key]
            merged["confidence"][key] = text_conf.get(key, 0.0)
            merged["evidence"][key] = text_evidence.get(key)
        else:
            merged["data"][key] = ocr_data[key]
            merged["confidence"][key] = ocr_conf.get(key, 0.0)
            merged["evidence"][key] = ocr_evidence.get(key)
        merged["meta"]["field_sources"][key] = chosen_engine

    return merged


def _avg_conf(conf_map: Dict[str, float]) -> float:
    return round(sum(conf_map.values()) / len(conf_map), 4) if conf_map else 0.0


def aggregate_page_results(page_results: List[dict], filename: str, fallback_type: str):
    if not page_results:
        return {
            "type": fallback_type,
            "filename": filename,
            "engine": "hybrid",
            "data": {},
            "confidence": {},
            "evidence": {},
            "meta": {"pages_processed": 0, "avg_confidence": 0.0},
        }

    final_type = next((res.get("type") for res in page_results if res.get("type") and res.get("type") != "UNKNOWN"), fallback_type)
    merged = {
        "type": final_type,
        "filename": filename,
        "engine": "hybrid",
        "data": {},
        "confidence": {},
        "evidence": {},
        "meta": {
            "pages_processed": len(page_results),
            "page_summaries": [
                {
                    "page": res.get("meta", {}).get("page_number", 1),
                    "engine": res.get("engine"),
                    "field_count": len(res.get("data", {})),
                    "avg_confidence": _avg_conf(res.get("confidence", {})),
                }
                for res in page_results
            ],
        },
    }

    for page_result in page_results:
        for key, value in page_result.get("data", {}).items():
            next_conf = page_result.get("confidence", {}).get(key, 0.0)
            current_conf = merged["confidence"].get(key, -1.0)
            if key not in merged["data"] or next_conf > current_conf:
                merged["data"][key] = value
                merged["confidence"][key] = next_conf
                merged["evidence"][key] = page_result.get("evidence", {}).get(key)

    merged["meta"]["avg_confidence"] = _avg_conf(merged["confidence"])
    return merged


def refine_t4_with_secondary_high_dpi(page, page_result: dict):
    field_sources = dict(page_result.get("meta", {}).get("field_sources", {}))
    suspicious_fields = [
        key for key in T4_SECONDARY_OCR_FIELDS
        if key not in page_result.get("data", {}) or field_sources.get(key) == "ocr"
    ]
    if not suspicious_fields:
        return page_result

    candidates_by_field = {}
    for dpi in T4_SECONDARY_OCR_DPIS:
        ocr_bboxes, _ = extract_ocr_bboxes(page, dpi=dpi)
        if not ocr_bboxes:
            continue
        ocr_data, ocr_conf, ocr_evidence = run_extractor("T4", ocr_bboxes)
        ocr_data, ocr_conf, ocr_evidence = normalize_extraction_keys("T4", ocr_data, ocr_conf, ocr_evidence)
        for key in suspicious_fields:
            if key not in ocr_data:
                continue
            candidates_by_field.setdefault(key, []).append(
                {
                    "dpi": dpi,
                    "value": ocr_data[key],
                    "confidence": ocr_conf.get(key, 0.0),
                    "evidence": ocr_evidence.get(key),
                }
            )

    if not candidates_by_field:
        return page_result

    page_result.setdefault("meta", {}).setdefault("secondary_high_dpi_fields", {})
    for key, field_candidates in candidates_by_field.items():
        if not field_candidates:
            continue

        consensus_candidate = choose_t4_decimal_neighbor_consensus(
            key,
            page_result.get("data", {}).get(key),
            page_result.get("confidence", {}).get(key, 0.0),
            page_result.get("evidence", {}).get(key),
            field_candidates,
        )
        if consensus_candidate:
            page_result["data"][key] = consensus_candidate["value"]
            page_result.setdefault("confidence", {})[key] = consensus_candidate["confidence"]
            page_result.setdefault("evidence", {})[key] = consensus_candidate["evidence"]
            page_result["meta"]["field_sources"][key] = "ocr"
            page_result["meta"]["secondary_high_dpi_fields"][key] = consensus_candidate["dpi"]
            continue

        field_candidates.sort(key=lambda item: (item["confidence"], item["dpi"]), reverse=True)
        best_candidate = field_candidates[0]
        current_conf = page_result.get("confidence", {}).get(key, -1.0)
        current_value = page_result.get("data", {}).get(key)
        should_replace = (
            key not in page_result.get("data", {})
            or best_candidate["confidence"] > current_conf + 0.002
            or (
                field_sources.get(key) == "ocr"
                and best_candidate["confidence"] >= current_conf - 0.01
                and best_candidate["value"] != current_value
            )
        )
        if not should_replace:
            continue

        page_result["data"][key] = best_candidate["value"]
        page_result.setdefault("confidence", {})[key] = best_candidate["confidence"]
        page_result.setdefault("evidence", {})[key] = best_candidate["evidence"]
        page_result["meta"]["field_sources"][key] = "ocr"
        page_result["meta"]["secondary_high_dpi_fields"][key] = best_candidate["dpi"]

    return page_result


def choose_t4_decimal_neighbor_consensus(key: str, current_value, current_confidence: float, current_evidence: Optional[dict], field_candidates: List[dict]):
    if key not in T4_DECIMAL_NEIGHBOR_FIELDS:
        return None

    signatures = []

    def add_signature(text, dpi, evidence, confidence):
        parsed = parse_decimal_neighbor_signature(text)
        if parsed is None:
            return
        whole, dec1, dec2, normalized_value, ambiguous = parsed
        signatures.append(
            {
                "whole": whole,
                "dec1": dec1,
                "dec2": dec2,
                "value": normalized_value,
                "ambiguous": ambiguous,
                "dpi": dpi,
                "evidence": evidence,
                "confidence": confidence,
            }
        )

    current_text = (((current_evidence or {}).get("value") or {}).get("text"))
    if current_text:
        add_signature(current_text, 0, current_evidence, current_confidence)

    for candidate in field_candidates:
        text = (((candidate.get("evidence") or {}).get("value") or {}).get("text"))
        add_signature(text, candidate.get("dpi", 0), candidate.get("evidence"), candidate.get("confidence", 0.0))

    if len(signatures) < 2:
        return None

    whole_parts = {item["whole"] for item in signatures}
    second_decimal_digits = {item["dec2"] for item in signatures}
    if len(whole_parts) != 1 or len(second_decimal_digits) != 1:
        return None

    ambiguous_signatures = [item for item in signatures if item["ambiguous"]]
    if not ambiguous_signatures:
        return None

    ambiguous_signatures.sort(key=lambda item: (item["dpi"], item["confidence"]), reverse=True)
    winner = ambiguous_signatures[0]
    if current_value is not None and abs(winner["value"] - float(current_value)) > 0.40:
        return None

    winner_text = f'{winner["whole"]}.{winner["dec1"]}{winner["dec2"]}'
    return {
        "value": winner["value"],
        "confidence": max(current_confidence, winner["confidence"]) + 0.003,
        "dpi": winner["dpi"],
        "evidence": {
            "strategy": "t4_decimal_neighbor_consensus",
            "value": {
                "text": winner_text,
                "value": winner["value"],
                "conf": winner["confidence"],
                "source": "ocr",
                "bbox": (((winner["evidence"] or {}).get("value") or {}).get("bbox")),
            },
            "label": (winner["evidence"] or {}).get("label"),
            "anchor": (winner["evidence"] or {}).get("anchor"),
        },
    }


def parse_decimal_neighbor_signature(text: Optional[str]):
    raw = (text or "").strip()
    if not raw or "." not in raw:
        return None

    match = re.search(r"(\d+)\.([0-9A-Za-z])(\d)", raw)
    if not match:
        return None

    whole, dec1, dec2 = match.groups()
    ambiguous_map = {
        "h": "1",
        "H": "1",
        "I": "1",
        "l": "1",
        "|": "1",
        "O": "0",
        "o": "0",
        "S": "5",
        "s": "5",
        "B": "8",
    }
    ambiguous = dec1 in ambiguous_map
    normalized_dec1 = ambiguous_map.get(dec1, dec1)
    if not normalized_dec1.isdigit():
        return None

    normalized_value = float(f"{whole}.{normalized_dec1}{dec2}")
    return whole, normalized_dec1, dec2, normalized_value, ambiguous


def normalized_bbox_to_rect(page, bbox):
    if not bbox or len(bbox) != 4:
        return None
    page_w = float(page.rect.width)
    page_h = float(page.rect.height)
    x0, y0, x1, y1 = bbox
    return fitz.Rect(
        x0 / NORMALIZED_PAGE_SIZE * page_w,
        y0 / NORMALIZED_PAGE_SIZE * page_h,
        x1 / NORMALIZED_PAGE_SIZE * page_w,
        y1 / NORMALIZED_PAGE_SIZE * page_h,
    )


def expand_clip_rect(page, rect, *, left=0, top=0, right=0, bottom=0):
    page_rect = fitz.Rect(page.rect)
    expanded = fitz.Rect(
        max(page_rect.x0, rect.x0 - left),
        max(page_rect.y0, rect.y0 - top),
        min(page_rect.x1, rect.x1 + right),
        min(page_rect.y1, rect.y1 + bottom),
    )
    return expanded


def normalize_moneylike_text(raw: Optional[str]):
    text = (raw or "").strip()
    if not text:
        return None
    text = text.replace(",", "").replace(" ", "")
    text = text.replace("$", "")
    if "." not in text:
        return None
    match = re.search(r"(\d+)\.([0-9A-Za-z|])([0-9A-Za-z|])", text)
    if not match:
        return None
    whole, dec1, dec2 = match.groups()
    replacements = {
        "h": "1",
        "H": "1",
        "I": "1",
        "l": "1",
        "|": "1",
        "O": "0",
        "o": "0",
        "S": "5",
        "s": "5",
        "B": "8",
    }
    dec1 = replacements.get(dec1, dec1)
    dec2 = replacements.get(dec2, dec2)
    if not (dec1.isdigit() and dec2.isdigit()):
        return None
    value = float(f"{whole}.{dec1}{dec2}")
    return f"{whole}.{dec1}{dec2}", value


def refine_t4_box16_with_crop_ocr(page, page_result: dict):
    evidence = (page_result.get("evidence", {}) or {}).get("box16_cpp") or {}
    label_bbox = (evidence.get("label") or {}).get("bbox")
    label_rect = normalized_bbox_to_rect(page, label_bbox)
    if label_rect is None:
        return page_result

    clip_rect = expand_clip_rect(page, label_rect, left=10, top=18, right=150, bottom=30)
    local_texts = extract_ocr_text_from_clip(page, clip_rect, dpi=T4_BOX16_CROP_DPI)
    if not local_texts:
        return page_result

    current_value = page_result.get("data", {}).get("box16_cpp")
    best_text = None
    best_value = None
    best_conf = -1.0

    for raw_text, conf in local_texts:
        normalized = normalize_moneylike_text(raw_text)
        if not normalized:
            continue
        normalized_text, value = normalized
        if current_value is not None and abs(value - float(current_value)) > 1.0:
            continue
        if conf > best_conf:
            best_text = normalized_text
            best_value = value
            best_conf = conf

    if best_value is None or current_value is None:
        return page_result
    if abs(best_value - float(current_value)) < 0.001:
        return page_result

    page_result["data"]["box16_cpp"] = best_value
    page_result.setdefault("confidence", {})["box16_cpp"] = max(page_result.get("confidence", {}).get("box16_cpp", 0.0), best_conf) + 0.004
    page_result.setdefault("evidence", {})["box16_cpp"] = {
        "strategy": "t4_box16_crop_ocr",
        "value": {
            "text": best_text,
            "value": best_value,
            "conf": best_conf,
            "source": "ocr",
            "bbox": label_bbox,
        },
        "label": evidence.get("label"),
        "anchor": None,
    }
    page_result.setdefault("meta", {}).setdefault("secondary_high_dpi_fields", {})["box16_cpp"] = T4_BOX16_CROP_DPI
    page_result["meta"].setdefault("field_sources", {})["box16_cpp"] = "ocr"
    return page_result


def parse_pdf_slip(pdf_path, filename):
    """
    Production-style hybrid parser:
      1) inspect text layer
      2) use text-layer extraction when available
      3) fallback to OCR when text layer is weak or incomplete
      4) normalize all bboxes to one coordinate system
      5) attach confidence + evidence for reviewability
    """
    print(f"Extracting from {pdf_path} ...")
    try:
        doc = fitz.open(pdf_path)
        page_inputs = []
        combined_text_blob_parts = []
        for page_index in range(len(doc)):
            page = doc[page_index]
            text_bboxes, text_analysis = extract_text_bboxes(page)
            text_blob = " ".join(b.text for b in text_bboxes)
            combined_text_blob_parts.append(text_blob)
            page_inputs.append(
                {
                    "page_number": page_index + 1,
                    "page": page,
                    "text_bboxes": text_bboxes,
                    "text_analysis": text_analysis,
                    "text_blob": text_blob,
                }
            )

        global_text_blob = " ".join(part for part in combined_text_blob_parts if part)
        global_slip_type = determine_slip_type(global_text_blob, filename)
        page_results = []

        for page_input in page_inputs:
            page = page_input["page"]
            page_number = page_input["page_number"]
            text_bboxes = page_input["text_bboxes"]
            text_analysis = page_input["text_analysis"]
            text_blob = page_input["text_blob"]

            text_slip_type = global_slip_type if global_slip_type != "UNKNOWN" else determine_slip_type(text_blob, filename)
            text_data, text_conf, text_evidence = run_extractor(text_slip_type, text_bboxes)
            text_data, text_conf, text_evidence = normalize_extraction_keys(text_slip_type, text_data, text_conf, text_evidence)

            text_result = {
                "type": text_slip_type,
                "filename": filename,
                "engine": "text",
                "data": text_data,
                "confidence": text_conf,
                "evidence": text_evidence,
                "meta": {
                    "page_number": page_number,
                    "text_layer": {
                        "looks_digital": text_analysis["looks_digital"],
                        "word_count": text_analysis["word_count"],
                        "char_count": text_analysis["char_count"],
                    },
                    "avg_confidence": _avg_conf(text_conf),
                },
            }

            need_ocr = (
                not text_analysis["looks_digital"]
                or text_slip_type == "UNKNOWN"
                or len(text_data) == 0
                or _avg_conf(text_conf) < 0.82
            )

            if text_slip_type in SLIP_FIELDS:
                expected_fields = len(SLIP_FIELDS[text_slip_type])
                if 0 < len(text_data) < max(2, math.ceil(expected_fields * 0.35)):
                    need_ocr = True

            if not need_ocr:
                text_result["meta"]["selected_engine"] = "text"
                page_results.append(text_result)
                continue

            ocr_bboxes, ocr_meta = extract_ocr_bboxes(page)
            ocr_blob = " ".join(b.text for b in ocr_bboxes)
            ocr_slip_type = global_slip_type if global_slip_type != "UNKNOWN" else determine_slip_type(ocr_blob or text_blob, filename)
            if ocr_slip_type == "UNKNOWN":
                ocr_slip_type = text_slip_type

            ocr_data, ocr_conf, ocr_evidence = run_extractor(ocr_slip_type, ocr_bboxes)
            ocr_data, ocr_conf, ocr_evidence = normalize_extraction_keys(ocr_slip_type, ocr_data, ocr_conf, ocr_evidence)
            ocr_result = {
                "type": ocr_slip_type,
                "filename": filename,
                "engine": "ocr",
                "data": ocr_data,
                "confidence": ocr_conf,
                "evidence": ocr_evidence,
                "meta": {
                    "page_number": page_number,
                    **ocr_meta,
                    "avg_confidence": _avg_conf(ocr_conf),
                },
            }

            if text_result["type"] == "UNKNOWN" and ocr_result["type"] != "UNKNOWN":
                text_result["type"] = ocr_result["type"]

            page_result = choose_better_result(text_result, ocr_result)
            page_result["type"] = page_result.get("type") if page_result.get("type") != "UNKNOWN" else ocr_result["type"]
            page_result["filename"] = filename
            page_result["meta"]["page_number"] = page_number
            page_result["meta"]["selected_engine"] = page_result.get("engine", "hybrid")
            page_result["meta"]["text_fallback_triggered"] = True
            page_result["engine"] = "hybrid"
            if page_result.get("type") == "T4":
                page_result = refine_t4_with_secondary_high_dpi(page, page_result)
                page_result = refine_t4_box16_with_crop_ocr(page, page_result)
            page_results.append(page_result)

        final_result = aggregate_page_results(page_results, filename, global_slip_type)
        final_result["meta"]["selected_engine"] = final_result.get("engine", "hybrid")
        final_result["meta"]["text_fallback_triggered"] = any(
            res.get("meta", {}).get("text_fallback_triggered", False) for res in page_results
        )

        print(f">>> FINAL {final_result['type']} [HYBRID]: {final_result['data']}")
        return final_result

    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return {
            "type": "UNKNOWN",
            "filename": filename,
            "engine": "error",
            "data": {},
            "confidence": {},
            "evidence": {},
            "meta": {"error": str(e)},
        }
