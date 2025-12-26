import os
import re

import requests
from dotenv import load_dotenv

TAG_RULES = {
    "CKD": ["chronic kidney", "ckd", "eGFR", "albuminuria"],
    "AKI": ["acute kidney", "aki", "acute renal", "kidney injury"],
    "HD": ["hemodialysis", "haemodialysis", "dialysis center"],
    "PD": ["peritoneal dialysis", "pd catheter"],
    "Transplant": ["kidney transplant", "renal transplant", "allograft"],
    "Electrolyte disorders": ["hyperkalemia", "hypokalemia", "hyponatremia", "hypernatremia"],
    "GN / IgA / Lupus": ["glomerul", "iga", "lupus", "nephritis"],
    "Drug / RCT / Guideline": ["randomized", "randomised", "trial", "rct", "guideline"],
}

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_URL = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_TIMEOUT = int(os.environ.get("OPENAI_TIMEOUT", "20"))
_TRANSLATION_CACHE = {}
_SUMMARY_CACHE = {}

TAG_POPULATION_MAP = {
    "CKD": "CKD（慢性腎臟病）患者",
    "AKI": "AKI（急性腎損傷）患者",
    "HD": "血液透析患者",
    "PD": "腹膜透析患者",
    "Transplant": "腎臟移植受者",
    "Electrolyte disorders": "電解質異常患者",
    "GN / IgA / Lupus": "腎炎/IgA/狼瘡腎炎相關患者",
    "Drug / RCT / Guideline": "臨床研究受試者",
}

STUDY_TYPE_ZH = {
    "Guideline": "臨床指引",
    "Meta-analysis": "系統性回顧/統合分析",
    "Randomized trial": "隨機對照試驗（RCT）",
    "Cohort study": "世代研究",
    "Case-control study": "病例對照研究",
    "Cross-sectional study": "橫斷面研究",
    "Observational study": "觀察性研究",
}

DESIGN_MAP = {
    "Randomized trial": "RCT",
    "Cohort study": "隊列",
    "Case-control study": "病例對照",
    "Meta-analysis": "系統回顧/統合分析",
    "Guideline": "其他",
    "Cross-sectional study": "其他",
    "Observational study": "其他",
}

ANIMAL_MAP = {
    "mice": "小鼠",
    "mouse": "小鼠",
    "rats": "大鼠",
    "rat": "大鼠",
    "rabbit": "兔",
    "rabbits": "兔",
    "porcine": "豬",
    "pig": "豬",
    "pigs": "豬",
    "canine": "犬",
    "dog": "犬",
    "dogs": "犬",
    "sheep": "羊",
    "ovine": "羊",
}

KNOWN_GENES = {
    "sglt2": "SGLT2",
    "sglt1": "SGLT1",
    "urat1": "URAT1",
    "glut9": "GLUT9",
}

KNOWN_DRUGS = {
    "canagliflozin": "canagliflozin（SGLT2 抑制劑）",
    "dapagliflozin": "dapagliflozin（SGLT2 抑制劑）",
    "empagliflozin": "empagliflozin（SGLT2 抑制劑）",
    "ertugliflozin": "ertugliflozin（SGLT2 抑制劑）",
    "ipragliflozin": "ipragliflozin（SGLT2 抑制劑）",
    "luseogliflozin": "luseogliflozin（SGLT2 抑制劑）",
    "tofogliflozin": "tofogliflozin（SGLT2 抑制劑）",
}

MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def _normalize(text):
    return (text or "").lower()


def _translate_to_zh(text):
    if not text:
        return "UNKNOWN"
    if text in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[text]
    if not OPENAI_API_KEY:
        return "UNKNOWN"
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a medical translator. Translate the given sentence into Traditional Chinese. "
                    "Keep it concise, single sentence, preserve meaning, and do not add new information."
                ),
            },
            {"role": "user", "content": text},
        ],
        "temperature": 0,
    }
    try:
        response = requests.post(
            OPENAI_API_URL,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json=payload,
            timeout=OPENAI_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        translation = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not translation:
            translation = "UNKNOWN"
    except Exception:
        translation = "UNKNOWN"
    _TRANSLATION_CACHE[text] = translation
    return translation


def translate_title(title):
    return _translate_to_zh(title)


def summarize_abstract_with_llm(abstract):
    if not abstract:
        return "UNKNOWN"
    if abstract in _SUMMARY_CACHE:
        return _SUMMARY_CACHE[abstract]
    if not OPENAI_API_KEY:
        return "UNKNOWN"
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是腎臟科臨床研究助理。請只依據 abstract 做摘要，"
                    "用繁體中文輸出 3-5 條列（每條一句話、精準短句），"
                    "禁止加入 abstract 未提到的資訊。"
                ),
            },
            {"role": "user", "content": abstract},
        ],
        "temperature": 0,
    }
    try:
        response = requests.post(
            OPENAI_API_URL,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json=payload,
            timeout=OPENAI_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        summary = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not summary:
            summary = "UNKNOWN"
    except Exception:
        summary = "UNKNOWN"
    _SUMMARY_CACHE[abstract] = summary
    return summary

def _dedupe_lines(lines):
    seen = set()
    result = []
    for line in lines:
        key = line.strip().lower()
        if key and key not in seen:
            result.append(line.strip())
            seen.add(key)
    return result


def _extract_animals(text):
    found = []
    text_norm = _normalize(text)
    for key, label in ANIMAL_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", text_norm):
            found.append(label)
    return sorted(set(found))


def _extract_gene_knockouts(text):
    hits = set()
    text_norm = _normalize(text)
    for gene_key, gene_label in KNOWN_GENES.items():
        if gene_key not in text_norm:
            continue
        if re.search(rf"{gene_key}[^.]*\b(ko|knockout|deficient|lacking|deleted)\b", text_norm):
            hits.add(gene_label)
        elif re.search(rf"\b(ko|knockout|deficient|lacking|deleted)[^.]*{gene_key}\b", text_norm):
            hits.add(gene_label)
    return sorted(hits)


def _extract_drugs(text):
    text_norm = _normalize(text)
    drugs = set()
    for drug in KNOWN_DRUGS.keys():
        if drug in text_norm:
            drugs.add(drug)
    for match in re.findall(r"\b[a-z0-9-]*gliflozin\b", text_norm):
        drugs.add(match)
    return sorted(drugs)


def _extract_population_phrase(text):
    match = re.search(
        r"\b(patients|participants|subjects|adults|children|infants|newborns|neonates)\s+with\s+([^.;,]+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    label_map = {
        "patients": "患者",
        "participants": "受試者",
        "subjects": "受試者",
        "adults": "成人",
        "children": "兒童",
        "infants": "嬰幼兒",
        "newborns": "新生兒",
        "neonates": "新生兒",
    }
    label = label_map.get(match.group(1).lower(), "受試者")
    condition = match.group(2).strip()
    return f"臨床對象：{condition} {label}"


def _extract_sample_size(text):
    text_norm = _normalize(text)
    match = re.search(r"\bn\s*=\s*(\d+)\b", text_norm)
    if match:
        return f"樣本數：n={match.group(1)}"
    match = re.search(
        r"\b(\d+)\s+(patients|participants|subjects|adults|children|infants|newborns)\b",
        text_norm,
    )
    if match:
        return f"樣本數：{match.group(1)} 人"
    match = re.search(r"\b(\d+)\s+(mice|rats|animals)\b", text_norm)
    if match:
        return f"樣本數：{match.group(1)} 隻動物"
    return None


def _extract_centers(text):
    text_norm = _normalize(text)
    match = re.search(
        r"\b(\d+)\s+(centers|centres|hospitals|sites|icus|icu)\b",
        text_norm,
    )
    if match:
        return f"研究中心：{match.group(1)} 家"
    return None


def _extract_location(text):
    locations = [
        "France",
        "French",
        "United States",
        "USA",
        "United Kingdom",
        "UK",
        "China",
        "Japan",
        "Taiwan",
        "Korea",
        "Germany",
        "Italy",
        "Spain",
        "Canada",
        "Australia",
    ]
    for location in locations:
        if re.search(rf"\b{re.escape(location)}\b", text):
            return f"地點：{location}"
    return None


def _extract_time_window(text):
    text_norm = _normalize(text)
    match = re.search(
        r"\bwithin\s+(\d+)\s*(hours|hour|hrs|hr|days|day|weeks|week|months|month)\b",
        text_norm,
    )
    if match:
        unit = match.group(2)
        value = match.group(1)
        unit_map = {
            "hours": "小時",
            "hour": "小時",
            "hrs": "小時",
            "hr": "小時",
            "days": "天",
            "day": "天",
            "weeks": "週",
            "week": "週",
            "months": "月",
            "month": "月",
        }
        return f"納入時間窗：{value}{unit_map.get(unit, unit)}內"
    return None


def _extract_dose_strings(text):
    text_norm = _normalize(text)
    matches = re.findall(
        r"\b\d+(?:\.\d+)?\s*(?:μg|ug|mcg|mg|g)\/kg(?:\/(?:min|h|hr|hour|day))?\b",
        text_norm,
    )
    return sorted(set(matches))


def _extract_drug_from_dose(text):
    match = re.search(
        r"\b([A-Za-z0-9-]+)\s+\d+(?:\.\d+)?\s*(?:μg|ug|mcg|mg|g)\/kg",
        text,
    )
    if match:
        return match.group(1)
    return None


def _extract_primary_outcome_phrase(text):
    if not text:
        return None
    match = re.search(
        r"\bprimary (outcome|endpoint)[^.;]*",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(0).strip()
    return None


def _extract_secondary_outcome_phrase(text):
    if not text:
        return None
    match = re.search(
        r"\bsecondary (outcome|outcomes|endpoint|endpoints)[^.;]*",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(0).strip()
    return None


def _extract_safety_phrase(text):
    if not text:
        return None
    match = re.search(
        r"\b(serious adverse events|adverse events|safety|arrhythmia|bleeding)[^.;]*",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(0).strip()
    return None


def _split_sentences(text):
    if not text:
        return []
    chunks = re.split(r"\n+", text.strip())
    sentences = []
    for chunk in chunks:
        parts = re.split(r"(?<=[\.\?!])\s+", chunk.strip())
        sentences.extend([p.strip() for p in parts if p.strip()])
    return sentences


def _find_sentence(sentences, keywords):
    for sentence in sentences:
        sentence_norm = _normalize(sentence)
        if any(keyword in sentence_norm for keyword in keywords):
            return sentence
    return "UNKNOWN"


def _keyword_in_text(text, keyword):
    if not text or not keyword:
        return False
    parts = [part for part in keyword.split() if part]
    if not parts:
        return False
    pattern = r"\b" + r"\s+".join(re.escape(part) for part in parts) + r"\b"
    return re.search(pattern, text) is not None


def _find_hits(text, keywords):
    text_norm = _normalize(text)
    hits = []
    for keyword in keywords:
        if _keyword_in_text(text_norm, keyword.lower()):
            hits.append(keyword)
    return hits


def _find_sentence_by_keyword(sentences, keyword):
    if not keyword:
        return "UNKNOWN"
    keyword_norm = keyword.lower()
    for sentence in sentences:
        if _keyword_in_text(_normalize(sentence), keyword_norm):
            return sentence
    return "UNKNOWN"


def _find_sentence_by_keywords(sentences, keywords):
    for keyword in keywords:
        sentence = _find_sentence_by_keyword(sentences, keyword)
        if sentence != "UNKNOWN":
            return sentence
    return "UNKNOWN"


def _first_keyword(text, keywords):
    text_norm = _normalize(text)
    for keyword in keywords:
        if _keyword_in_text(text_norm, keyword):
            return keyword
    return None


def _build_item(text, evidence):
    return {
        "text": text if text else "UNKNOWN",
        "evidence": evidence if evidence else "UNKNOWN",
    }


def _build_items_with_evidence(items, sentences, keywords):
    results = []
    evidence = _find_sentence(sentences, keywords) if keywords else "UNKNOWN"
    for item in items:
        results.append(_build_item(item, evidence))
    return results


def _extract_duration(text):
    text_norm = _normalize(text)
    match = re.search(
        r"\bfor\s+(\d+)\s*(days|day|weeks|week|months|month|years|year)\b",
        text_norm,
    )
    if match:
        unit_map = {
            "days": "天",
            "day": "天",
            "weeks": "週",
            "week": "週",
            "months": "月",
            "month": "月",
            "years": "年",
            "year": "年",
        }
        return f"期間：{match.group(1)}{unit_map.get(match.group(2), match.group(2))}"
    return None


def _extract_predictor_phrase(text):
    match = re.search(
        r"\b(biomarker|predictor|risk score|risk model|prediction model|model|index test|diagnostic test)[^.;]*",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(0).strip()
    return None


def _extract_intervention_phrase(text):
    match = re.search(
        r"\b(receive|received|treated with|administered|assigned to|randomized to receive)\s+([^.;]+)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        phrase = match.group(2)
        phrase = re.split(r"\bor placebo\b|\bor control\b", phrase, maxsplit=1, flags=re.IGNORECASE)[0]
        return phrase.strip()
    return None


def _extract_reference_phrase(text):
    match = re.search(
        r"\b(reference standard|gold standard|reference test|compared with)[^.;]*",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(0).strip()
    return None


def _extract_performance_metrics(text):
    text_norm = _normalize(text)
    metrics = []
    if "auc" in text_norm:
        metrics.append("AUC")
    if "roc" in text_norm:
        metrics.append("ROC")
    if "sensitivity" in text_norm:
        metrics.append("敏感度")
    if "specificity" in text_norm:
        metrics.append("特異度")
    if "ppv" in text_norm or "positive predictive value" in text_norm:
        metrics.append("陽性預測值（PPV）")
    if "npv" in text_norm or "negative predictive value" in text_norm:
        metrics.append("陰性預測值（NPV）")
    if "c-statistic" in text_norm or "c statistic" in text_norm:
        metrics.append("C-statistic")
    if "accuracy" in text_norm:
        metrics.append("Accuracy")
    return metrics


def _extract_key_mechanism_sentence(sentences):
    return _find_sentence(sentences, ["mechanism", "mediated", "via", "pathway"])


def _extract_so_what_sentence(sentences):
    return _find_sentence(
        sentences, ["implication", "suggest", "potential", "clinical", "relevance"]
    )


def _extract_key_points(sentences):
    items = []
    for sentence in sentences:
        if len(sentence) < 20:
            continue
        items.append(_build_item(sentence, sentence))
        if len(items) >= 5:
            break
    while len(items) < 3:
        items.append(_build_item("UNKNOWN", "UNKNOWN"))
    return items


def classify_abstract(abstract):
    rules = [
        (
            "REVIEW_GUIDELINE",
            [
                "systematic review",
                "meta-analysis",
                "guideline",
                "consensus",
                "recommendation",
                "review",
            ],
        ),
        (
            "MECHANISTIC_PRECLINICAL",
            [
                "mice",
                "mouse",
                "rat",
                "rats",
                "murine",
                "cell line",
                "in vitro",
                "in vivo",
                "knockout",
                "ko",
            ],
        ),
        (
            "DIAG_PROGNOSTIC",
            [
                "diagnostic",
                "diagnosis",
                "sensitivity",
                "specificity",
                "auc",
                "roc",
                "predict",
                "prediction",
                "prognostic",
                "risk model",
                "biomarker",
                "c-statistic",
            ],
        ),
        (
            "PICO_CLINICAL",
            [
                "randomized",
                "randomised",
                "trial",
                "placebo",
                "double-blind",
                "intervention",
                "treated",
                "assigned",
                "receive",
                "compared",
            ],
        ),
    ]
    sentences = _split_sentences(abstract)
    for label, keywords in rules:
        keyword = _first_keyword(abstract, keywords)
        if keyword:
            evidence = _find_sentence(sentences, [keyword])
            reason = f"摘要出現關鍵詞「{keyword}」"
            return {"label": label, "reason": reason, "evidence": evidence}
    return {"label": "PICO_CLINICAL", "reason": "UNKNOWN", "evidence": "UNKNOWN"}


def classify_framework(abstract):
    rules = {
        "REVIEW_GUIDELINE": [
            "systematic review",
            "meta-analysis",
            "guideline",
            "consensus",
            "recommendation",
            "review",
        ],
        "MECHANISTIC_PRECLINICAL": [
            "mice",
            "mouse",
            "rat",
            "rats",
            "rodent",
            "rodents",
            "murine",
            "animal model",
            "animal models",
            "cell line",
            "in vitro",
            "in vivo",
            "knockout",
            "ko",
        ],
        "DIAG_OR_ETIOLOGY_FRAME": [
            "diagnostic",
            "diagnosis",
            "sensitivity",
            "specificity",
            "auc",
            "roc",
            "prediction",
            "prognostic",
            "risk model",
            "biomarker",
            "c-statistic",
            "etiology",
            "etiologic",
            "aetiology",
        ],
        "OBSERVATIONAL_ASSOCIATION": [
            "observational",
            "cohort",
            "cross-sectional",
            "association",
            "regression",
            "multivariable",
            "unadjusted",
            "adjusted",
            "independent predictor",
        ],
        "TREATMENT_PICO": [
            "randomized",
            "randomised",
            "placebo",
            "double-blind",
            "intervention",
            "assigned",
        ],
    }
    anchors = {
        "REVIEW_GUIDELINE": ["systematic review", "meta-analysis", "guideline"],
        "MECHANISTIC_PRECLINICAL": [
            "mice",
            "mouse",
            "rat",
            "rats",
            "murine",
            "rodent",
            "rodents",
            "in vitro",
            "in vivo",
            "cell line",
            "knockout",
            "animal model",
            "animal models",
        ],
        "DIAG_OR_ETIOLOGY_FRAME": [
            "sensitivity",
            "specificity",
            "auc",
            "roc",
            "biomarker",
        ],
        "OBSERVATIONAL_ASSOCIATION": [
            "observational",
            "cohort",
            "cross-sectional",
            "association",
            "regression",
            "multivariable",
            "unadjusted",
            "adjusted",
            "independent predictor",
        ],
        "TREATMENT_PICO": ["randomized", "randomised", "placebo", "double-blind"],
    }

    scores = {}
    reasons = {}
    sentences = _split_sentences(abstract)
    for label, keywords in rules.items():
        hits = _find_hits(abstract, keywords)
        anchor_hits = _find_hits(abstract, anchors.get(label, []))
        if not anchor_hits:
            scores[label] = 0
            continue
        scores[label] = len(hits) + len(anchor_hits)
        reasons[label] = {"hits": hits, "anchors": anchor_hits}

    best_label = max(scores, key=scores.get)
    if scores.get(best_label, 0) == 0:
        return {"framework": "OTHER", "reason": "UNKNOWN", "evidence": "UNKNOWN"}

    reason_hits = reasons.get(best_label, {})
    reason_keyword = (
        reason_hits.get("anchors", []) or reason_hits.get("hits", [])
    )
    reason_keyword = reason_keyword[0] if reason_keyword else "UNKNOWN"
    evidence = _find_sentence_by_keyword(sentences, reason_keyword)
    reason = f"關鍵詞：{reason_keyword}"
    return {"framework": best_label, "reason": reason, "evidence": evidence}


def build_framework_summary(abstract):
    sentences = _split_sentences(abstract)
    classifier = classify_framework(abstract)
    framework = classifier["framework"]
    reason = classifier["reason"]
    reason_evidence = classifier["evidence"]

    one_liner = _pick_takeaway_sentence(abstract)
    if one_liner:
        one_liner = _strip_structured_label(one_liner)
    else:
        one_liner = "UNKNOWN"

    sections = {"framework_reason": [reason or "UNKNOWN"]}
    evidence = {"framework_reason": [reason_evidence or "UNKNOWN"]}
    quality_flags = []

    def make_section(items, evidence_sentence):
        clean_items = [item for item in items if item] if items else []
        if not clean_items:
            clean_items = ["UNKNOWN"]
            evidence_list = ["UNKNOWN"]
        else:
            evidence_list = [(evidence_sentence or "UNKNOWN")] * len(clean_items)
        return clean_items, evidence_list

    if framework == "TREATMENT_PICO":
        population_items = []
        population_phrase = _extract_population_phrase(abstract)
        if population_phrase:
            population_items.append(
                f"族群/疾病：{population_phrase.replace('臨床對象：', '')}"
            )
        sample_size = _extract_sample_size(abstract)
        if sample_size:
            population_items.append(sample_size)
        centers = _extract_centers(abstract)
        if centers:
            population_items.append(centers)
        location = _extract_location(abstract)
        if location:
            population_items.append(location)
        time_window = _extract_time_window(abstract)
        if time_window:
            population_items.append(time_window)
        population_items = _dedupe_lines(population_items)
        p_items, p_evidence = make_section(
            population_items,
            _find_sentence(sentences, ["patients", "participants", "subjects", "adult", "icu", "within"]),
        )

        intervention_items = []
        drugs = _extract_drugs(abstract)
        for drug in drugs:
            intervention_items.append(
                f"治療/暴露：{KNOWN_DRUGS.get(drug, drug)}"
            )
        dose_strings = _extract_dose_strings(abstract)
        for dose in dose_strings:
            intervention_items.append(f"劑量：{dose}")
        intervention_phrase = _extract_intervention_phrase(abstract)
        if intervention_phrase:
            intervention_items.append(f"治療/暴露：{intervention_phrase}")
        duration = _extract_duration(abstract)
        if duration:
            intervention_items.append(duration)
        intervention_items = _dedupe_lines(intervention_items)
        i_items, i_evidence = make_section(
            intervention_items,
            _find_sentence(
                sentences,
                ["treated with", "receive", "received", "administered", "assigned", "infusion", "dose"],
            ),
        )

        comparison_items = []
        abstract_norm = _normalize(abstract)
        if "placebo" in abstract_norm:
            comparison_items.append("對照：placebo")
        if "vehicle" in abstract_norm:
            comparison_items.append("對照：vehicle")
        if "standard care" in abstract_norm or "usual care" in abstract_norm:
            comparison_items.append("對照：standard/usual care")
        if "control" in abstract_norm:
            comparison_items.append("對照：control")
        comparison_items = _dedupe_lines(comparison_items)
        c_items, c_evidence = make_section(
            comparison_items,
            _find_sentence(sentences, ["placebo", "vehicle", "standard care", "usual care", "control"]),
        )

        primary_phrase = _extract_primary_outcome_phrase(abstract)
        secondary_phrase = _extract_secondary_outcome_phrase(abstract)
        safety_phrase = _extract_safety_phrase(abstract)
        o_primary_items, o_primary_evidence = make_section(
            [f"Primary：{primary_phrase or 'UNKNOWN'}"],
            _find_sentence(sentences, ["primary outcome", "primary endpoint"]),
        )
        o_secondary_items, o_secondary_evidence = make_section(
            [f"Secondary：{secondary_phrase or 'UNKNOWN'}"],
            _find_sentence(sentences, ["secondary outcome", "secondary outcomes", "secondary endpoint"]),
        )
        o_safety_items, o_safety_evidence = make_section(
            [f"Safety：{safety_phrase or 'UNKNOWN'}"],
            _find_sentence(sentences, ["adverse", "safety", "arrhythmia", "bleeding"]),
        )

        has_i = any(item != "UNKNOWN" for item in i_items)
        has_c = any(item != "UNKNOWN" for item in c_items)
        has_primary = primary_phrase is not None
        if not (has_i and has_c and has_primary):
            quality_flags.append("missing_pico_fields")
            quality_flags.append("fallback_key_points")
            key_points = _extract_key_points(sentences)
            sections.update({"key_points": [item["text"] for item in key_points]})
            evidence["key_points"] = [item["evidence"] for item in key_points]
        else:
            sections.update(
                {
                    "P": p_items,
                    "I": i_items,
                    "C": c_items,
                    "O_primary": o_primary_items,
                    "O_secondary": o_secondary_items,
                    "O_safety": o_safety_items,
                }
            )
            evidence.update(
                {
                    "P": p_evidence,
                    "I": i_evidence,
                    "C": c_evidence,
                    "O_primary": o_primary_evidence,
                    "O_secondary": o_secondary_evidence,
                    "O_safety": o_safety_evidence,
                }
            )

    elif framework == "OBSERVATIONAL_ASSOCIATION":
        population_items = []
        population_phrase = _extract_population_phrase(abstract)
        if population_phrase:
            population_items.append(
                f"族群/疾病：{population_phrase.replace('臨床對象：', '')}"
            )
        sample_size = _extract_sample_size(abstract)
        if sample_size:
            population_items.append(sample_size)
        comparator_sentence = _find_sentence(
            sentences, ["versus", "vs", "compared", "comparison", "control"]
        )
        if comparator_sentence != "UNKNOWN":
            population_items.append(f"對照/比較：{comparator_sentence}")
        else:
            population_items.append("對照/比較：UNKNOWN")
        population_items = _dedupe_lines(population_items)
        p_items, p_evidence = make_section(
            population_items,
            _find_sentence(sentences, ["patients", "participants", "subjects", "cohort"]),
        )

        exposure_items = []
        predictor_phrase = _extract_predictor_phrase(abstract)
        if predictor_phrase:
            exposure_items.append(predictor_phrase)
        exposure_sentence = _find_sentence(
            sentences,
            ["exposure", "marker", "biomarker", "associated with", "association between"],
        )
        if exposure_sentence != "UNKNOWN":
            exposure_items.append(exposure_sentence)
        exposure_items = _dedupe_lines(exposure_items)
        exposure_items, exposure_evidence = make_section(
            exposure_items,
            _find_sentence(sentences, ["exposure", "marker", "biomarker", "predictor"]),
        )

        outcome_sentence = _find_sentence(
            sentences, ["outcome", "mortality", "progression", "incidence", "risk"]
        )
        outcome_items, outcome_evidence = make_section(
            [outcome_sentence if outcome_sentence != "UNKNOWN" else "UNKNOWN"],
            outcome_sentence,
        )

        result_keywords = [
            "associated",
            "association",
            "correlated",
            "regression",
            "multivariable",
            "adjusted",
            "unadjusted",
            "independent predictor",
            "hazard ratio",
            "odds ratio",
            "risk ratio",
        ]
        result_sentences = []
        for sentence in sentences:
            if any(_keyword_in_text(_normalize(sentence), kw) for kw in result_keywords):
                if sentence not in result_sentences:
                    result_sentences.append(sentence)
            if len(result_sentences) >= 4:
                break

        def format_assoc_result(sentence):
            if not sentence or sentence == "UNKNOWN":
                return "UNKNOWN"
            return sentence

        key_results = []
        key_results_evidence = []
        for sentence in result_sentences:
            key_results.append(format_assoc_result(sentence))
            key_results_evidence.append(sentence)
        while len(key_results) < 2:
            key_results.append("UNKNOWN")
            key_results_evidence.append("UNKNOWN")

        if all(item == "UNKNOWN" for item in key_results):
            quality_flags.append("missing_key_results")

        confounding_items, confounding_evidence = make_section(
            ["觀察性研究，無法推論因果"],
            _find_sentence(sentences, ["observational", "cohort", "cross-sectional"]),
        )

        so_what_sentence = _extract_so_what_sentence(sentences)
        so_what_items, so_what_evidence = make_section(
            [so_what_sentence or "UNKNOWN"],
            so_what_sentence if so_what_sentence else "UNKNOWN",
        )

        sections.update(
            {
                "P": p_items,
                "Exposure/Marker": exposure_items,
                "Outcomes": outcome_items,
                "Key results": key_results,
                "Confounding/limits": confounding_items,
                "So what": so_what_items,
            }
        )
        evidence.update(
            {
                "P": p_evidence,
                "Exposure/Marker": exposure_evidence,
                "Outcomes": outcome_evidence,
                "Key results": key_results_evidence,
                "Confounding/limits": confounding_evidence,
                "So what": so_what_evidence,
            }
        )

    elif framework == "DIAG_OR_ETIOLOGY_FRAME":
        population_items = []
        population_phrase = _extract_population_phrase(abstract)
        if population_phrase:
            population_items.append(
                f"族群/疾病：{population_phrase.replace('臨床對象：', '')}"
            )
        sample_size = _extract_sample_size(abstract)
        if sample_size:
            population_items.append(sample_size)
        population_items = _dedupe_lines(population_items)
        p_items, p_evidence = make_section(
            population_items,
            _find_sentence(sentences, ["patients", "participants", "subjects", "cohort"]),
        )

        predictor_items = []
        predictor_phrase = _extract_predictor_phrase(abstract)
        if predictor_phrase:
            predictor_items.append(predictor_phrase)
        metrics = _extract_performance_metrics(abstract)
        if metrics:
            predictor_items.extend([f"檢測/預測指標：{metric}" for metric in metrics])
        predictor_items = _dedupe_lines(predictor_items)
        i_items, i_evidence = make_section(
            predictor_items,
            _find_sentence(sentences, ["biomarker", "predictor", "risk", "model", "diagnostic", "index test"]),
        )

        c_items = []
        c_concept = _find_sentence(sentences, ["compared with", "versus"])
        c_items.append(f"概念對照：{c_concept if c_concept != 'UNKNOWN' else 'UNKNOWN'}")
        c_analysis = _find_sentence(sentences, ["adjusted", "multivariable", "regression"])
        c_items.append(f"分析對照：{c_analysis if c_analysis != 'UNKNOWN' else 'UNKNOWN'}")
        c_external = _find_sentence(sentences, ["external validation", "validation cohort", "independent cohort"])
        c_items.append(f"外部對照：{c_external if c_external != 'UNKNOWN' else 'UNKNOWN'}")
        c_items = _dedupe_lines(c_items)
        c_items, c_evidence = make_section(
            c_items,
            _find_sentence(sentences, ["compared", "adjusted", "validation"]),
        )

        outcome_phrase = _extract_primary_outcome_phrase(abstract)
        if not outcome_phrase:
            outcome_phrase = _find_sentence(
                sentences, ["outcome", "mortality", "progression", "diagnosis"]
            )
        o_items, o_evidence = make_section(
            [outcome_phrase if outcome_phrase else "UNKNOWN"],
            _find_sentence(sentences, ["outcome", "mortality", "progression", "diagnosis"]),
        )

        implication_sentence = _extract_so_what_sentence(sentences)
        implication_items, implication_evidence = make_section(
            [implication_sentence or "UNKNOWN"],
            implication_sentence if implication_sentence else "UNKNOWN",
        )

        sections.update(
            {
                "P": p_items,
                "I": i_items,
                "C": c_items,
                "O": o_items,
                "Implication": implication_items,
            }
        )
        evidence.update(
            {
                "P": p_evidence,
                "I": i_evidence,
                "C": c_evidence,
                "O": o_evidence,
                "Implication": implication_evidence,
            }
        )

    elif framework == "MECHANISTIC_PRECLINICAL":
        population_items = []
        animals = _extract_animals(abstract)
        if animals:
            population_items.append(f"動物模型：{'、'.join(animals)}")
        if re.search(r"\b(wild[- ]type)\b", abstract, flags=re.IGNORECASE):
            population_items.append("野生型（wild-type）")
        gene_kos = _extract_gene_knockouts(abstract)
        if gene_kos:
            population_items.append(f"基因剔除：{'、'.join(gene_kos)}")
        if re.search(
            r"\b(tubule|tubular)[^.;]*glut9[^.;]*\b(ko|knockout|deficient|lacking|deleted)\b",
            abstract,
            flags=re.IGNORECASE,
        ):
            population_items.append("腎小管 GLUT9 缺失")
        if re.search(r"\b(non[- ]diabetic|nondiabetic)\b", abstract, flags=re.IGNORECASE):
            population_items.append("非糖尿病條件")
        if re.search(r"\bhek\s*293\b", abstract, flags=re.IGNORECASE):
            population_items.append("細胞模型：HEK293")
        population_items = _dedupe_lines(population_items)
        p_items, p_evidence = make_section(
            population_items,
            _find_sentence_by_keywords(
                sentences,
                [
                    "mice",
                    "mouse",
                    "rat",
                    "rats",
                    "wild-type",
                    "nondiabetic",
                    "non-diabetic",
                    "knockout",
                    "cell line",
                    "hek293",
                ],
            ),
        )

        intervention_items = []
        drugs = _extract_drugs(abstract)
        for drug in drugs:
            intervention_items.append(f"藥物介入：{KNOWN_DRUGS.get(drug, drug)}")
        if gene_kos:
            intervention_items.append(f"基因操作：{'、'.join(gene_kos)} KO")
        intervention_phrase = _extract_intervention_phrase(abstract)
        if intervention_phrase:
            intervention_items.append(f"處置：{intervention_phrase}")
        text_norm = _normalize(abstract)
        if any(
            phrase in text_norm
            for phrase in ["luminal glucose", "tubular fluid", "glucose delivery"]
        ):
            intervention_items.append("生理操作：管腔葡萄糖相關處置")
        intervention_items = _dedupe_lines(intervention_items)
        i_items, i_evidence = make_section(
            intervention_items,
            _find_sentence_by_keywords(
                sentences,
                ["treated with", "administered", "inhibitor", "knockout", "luminal glucose"],
            ),
        )

        comparison_items = []
        if re.search(r"\bwild[- ]type\b", abstract, flags=re.IGNORECASE):
            comparison_items.append("對照：wild-type")
        if re.search(r"\bvehicle\b", abstract, flags=re.IGNORECASE):
            comparison_items.append("對照：vehicle")
        if re.search(r"\b(control|baseline|untreated)\b", abstract, flags=re.IGNORECASE):
            comparison_items.append("對照：未處理/基線")
        comparison_sentence = _find_sentence_by_keywords(
            sentences, ["versus", "vs", "compared", "comparison", "absence of", "without"]
        )
        if comparison_sentence != "UNKNOWN":
            comparison_items.append(f"對照/比較：{comparison_sentence}")
        comparison_items = _dedupe_lines(comparison_items)
        c_items, c_evidence = make_section(
            comparison_items,
            _find_sentence_by_keywords(
                sentences,
                ["wild-type", "vehicle", "control", "compared", "absence of", "without"],
            ),
        )

        readouts = _extract_methods(abstract)
        if "mRNA expression" in text_norm:
            readouts.append("mRNA expression")
        if any(term in text_norm for term in ["glycosuric", "glycosuria"]):
            readouts.append("尿糖/糖尿（glycosuria）")
        if any(term in text_norm for term in ["uricosuric", "urate excretion"]):
            readouts.append("排尿酸效應（uricosuria/urate excretion）")
        readouts = _dedupe_lines(readouts)
        o_items, o_evidence = make_section(
            readouts,
            _find_sentence_by_keywords(
                sentences,
                ["urate", "clearance", "gfr", "fitc-sinistrin", "mRNA", "glycosuric", "uricosuric"],
            ),
        )

        sections.update({"P": p_items, "I": i_items, "C": c_items, "O": o_items})
        evidence.update({"P": p_evidence, "I": i_evidence, "C": c_evidence, "O": o_evidence})

    elif framework == "REVIEW_GUIDELINE":
        scope_sentence = _find_sentence(sentences, ["review", "guideline", "consensus", "recommendation"])
        data_sentence = _find_sentence(sentences, ["pubmed", "medline", "embase", "cochrane", "database", "search"])
        conclusion_sentence = _find_sentence(sentences, ["conclude", "recommend", "suggest"])
        evidence_sentence = _find_sentence(sentences, ["grade", "quality of evidence", "strength"])
        scope_items, scope_evidence = make_section(
            [scope_sentence if scope_sentence != "UNKNOWN" else "UNKNOWN"],
            scope_sentence,
        )
        data_items, data_evidence = make_section(
            [data_sentence if data_sentence != "UNKNOWN" else "UNKNOWN"],
            data_sentence,
        )
        conclusion_items, conclusion_evidence = make_section(
            [conclusion_sentence if conclusion_sentence != "UNKNOWN" else "UNKNOWN"],
            conclusion_sentence,
        )
        strength_items, strength_evidence = make_section(
            [evidence_sentence if evidence_sentence != "UNKNOWN" else "UNKNOWN"],
            evidence_sentence,
        )
        sections.update(
            {
                "Scope": scope_items,
                "Data sources": data_items,
                "Key conclusions": conclusion_items,
                "Evidence strength": strength_items,
            }
        )
        evidence.update(
            {
                "Scope": scope_evidence,
                "Data sources": data_evidence,
                "Key conclusions": conclusion_evidence,
                "Evidence strength": strength_evidence,
            }
        )

    else:
        quality_flags.append("framework_other")
        key_points = _extract_key_points(sentences)
        sections.update({"key_points": [item["text"] for item in key_points]})
        evidence["key_points"] = [item["evidence"] for item in key_points]

    return {
        "framework": framework,
        "one_liner": one_liner,
        "sections": sections,
        "evidence": evidence,
        "quality_flags": quality_flags,
    }

def build_two_step_analysis(abstract):
    sentences = _split_sentences(abstract)
    classifier = classify_abstract(abstract)
    label = classifier["label"]
    sections = []
    template = label

    if label == "PICO_CLINICAL":
        population_items = []
        population_phrase = _extract_population_phrase(abstract)
        if population_phrase:
            evidence = _find_sentence(
                sentences, ["patients", "participants", "subjects", "adult", "children", "infants", "newborns"]
            )
            population_items.append(
                _build_item(
                    f"族群/疾病：{population_phrase.replace('臨床對象：', '')}",
                    evidence,
                )
            )
        sample_size = _extract_sample_size(abstract)
        if sample_size:
            evidence = _find_sentence(sentences, ["n=", "patients", "participants", "subjects"])
            population_items.append(_build_item(sample_size, evidence))
        centers = _extract_centers(abstract)
        if centers:
            evidence = _find_sentence(sentences, ["centers", "centres", "hospitals", "icu", "icus"])
            population_items.append(_build_item(centers, evidence))
        location = _extract_location(abstract)
        if location:
            evidence = _find_sentence(sentences, [location.split("：")[-1].lower()])
            population_items.append(_build_item(location, evidence))
        time_window = _extract_time_window(abstract)
        if time_window:
            evidence = _find_sentence(sentences, ["within"])
            population_items.append(_build_item(time_window, evidence))
        population_items = _dedupe_lines([item["text"] for item in population_items])
        population_items = [
            _build_item(text, _find_sentence(sentences, ["patients", "participants", "subjects", "icu", "within"]))
            for text in population_items
        ]
        if len(population_items) < 2:
            population_items.append(_build_item("族群/疾病：UNKNOWN", "UNKNOWN"))
        if len(population_items) < 2:
            population_items.append(_build_item("樣本數/地點/時間窗：UNKNOWN", "UNKNOWN"))
        population_items = population_items[:4]

        intervention_items = []
        drugs = _extract_drugs(abstract)
        for drug in drugs:
            label_text = KNOWN_DRUGS.get(drug, drug)
            evidence = _find_sentence(sentences, [drug])
            intervention_items.append(_build_item(f"治療/暴露：{label_text}", evidence))
        dose_strings = _extract_dose_strings(abstract)
        for dose in dose_strings:
            evidence = _find_sentence(sentences, [dose])
            intervention_items.append(_build_item(f"劑量：{dose}", evidence))
        intervention_phrase = _extract_intervention_phrase(abstract)
        if intervention_phrase:
            evidence = _find_sentence(sentences, ["receive", "received", "treated", "administered", "assigned"])
            intervention_items.append(_build_item(f"治療/暴露：{intervention_phrase}", evidence))
        duration = _extract_duration(abstract)
        if duration:
            evidence = _find_sentence(sentences, ["for"])
            intervention_items.append(_build_item(duration, evidence))
        if not intervention_items:
            intervention_items = [_build_item("UNKNOWN", "UNKNOWN")]

        comparison_items = []
        if "placebo" in _normalize(abstract):
            comparison_items.append(
                _build_item("對照：placebo", _find_sentence(sentences, ["placebo"]))
            )
        if "vehicle" in _normalize(abstract):
            comparison_items.append(
                _build_item("對照：vehicle", _find_sentence(sentences, ["vehicle"]))
            )
        if "control" in _normalize(abstract):
            comparison_items.append(
                _build_item("對照：control", _find_sentence(sentences, ["control"]))
            )
        if not comparison_items:
            comparison_items = [_build_item("UNKNOWN", "UNKNOWN")]

        primary_phrase = _extract_primary_outcome_phrase(abstract)
        secondary_phrase = _extract_secondary_outcome_phrase(abstract)
        safety_phrase = _extract_safety_phrase(abstract)
        outcome_items = [
            _build_item(
                f"Primary：{primary_phrase or 'UNKNOWN'}",
                _find_sentence(sentences, ["primary outcome", "primary endpoint"]),
            ),
            _build_item(
                f"Secondary：{secondary_phrase or 'UNKNOWN'}",
                _find_sentence(sentences, ["secondary outcome", "secondary outcomes", "secondary endpoint"]),
            ),
            _build_item(
                f"Safety：{safety_phrase or 'UNKNOWN'}",
                _find_sentence(sentences, ["adverse", "safety", "arrhythmia", "bleeding"]),
            ),
        ]

        has_intervention = any(item["text"] != "UNKNOWN" for item in intervention_items)
        has_comparison = any(item["text"] != "UNKNOWN" for item in comparison_items)
        has_primary = primary_phrase is not None
        if not (has_intervention and has_comparison and has_primary):
            template = "KEY_POINTS"
            sections = [
                {"title": "Key points", "items": _extract_key_points(sentences)}
            ]
        else:
            sections = [
                {"title": "P（Population）", "items": population_items},
                {"title": "I（Intervention / Exposure）", "items": intervention_items},
                {"title": "C（Comparison）", "items": comparison_items},
                {"title": "O（Outcome）", "items": outcome_items},
            ]

    elif label == "DIAG_PROGNOSTIC":
        population_items = []
        population_phrase = _extract_population_phrase(abstract)
        if population_phrase:
            population_items.append(
                _build_item(
                    f"族群/疾病：{population_phrase.replace('臨床對象：', '')}",
                    _find_sentence(sentences, ["patients", "participants", "subjects"]),
                )
            )
        sample_size = _extract_sample_size(abstract)
        if sample_size:
            population_items.append(_build_item(sample_size, _find_sentence(sentences, ["n="])))
        if not population_items:
            population_items = [_build_item("UNKNOWN", "UNKNOWN")]

        predictor_phrase = _extract_predictor_phrase(abstract)
        predictor_items = [
            _build_item(
                predictor_phrase or "UNKNOWN",
                _find_sentence(sentences, ["biomarker", "predictor", "risk", "model", "diagnostic", "index test"]),
            )
        ]

        reference_phrase = _extract_reference_phrase(abstract)
        reference_items = [
            _build_item(
                reference_phrase or "UNKNOWN",
                _find_sentence(sentences, ["reference", "gold standard", "compared"]),
            )
        ]

        outcome_phrase = _extract_primary_outcome_phrase(abstract)
        outcome_items = [
            _build_item(
                outcome_phrase or "UNKNOWN",
                _find_sentence(sentences, ["outcome", "mortality", "progression"]),
            )
        ]

        metrics = _extract_performance_metrics(abstract)
        metrics_items = []
        if metrics:
            for metric in metrics:
                keyword_map = {
                    "AUC": ["auc"],
                    "ROC": ["roc"],
                    "敏感度": ["sensitivity"],
                    "特異度": ["specificity"],
                    "陽性預測值（PPV）": ["ppv", "positive predictive value"],
                    "陰性預測值（NPV）": ["npv", "negative predictive value"],
                    "C-statistic": ["c-statistic", "c statistic"],
                    "Accuracy": ["accuracy"],
                }
                evidence = _find_sentence(sentences, keyword_map.get(metric, []))
                metrics_items.append(_build_item(metric, evidence))
        else:
            metrics_items = [_build_item("UNKNOWN", "UNKNOWN")]

        sections = [
            {"title": "Population", "items": population_items},
            {"title": "Index test / Predictor", "items": predictor_items},
            {"title": "Comparator / Reference", "items": reference_items},
            {"title": "Outcomes", "items": outcome_items},
            {"title": "Performance metrics", "items": metrics_items},
        ]

    elif label == "MECHANISTIC_PRECLINICAL":
        model_items = []
        animals = _extract_animals(abstract)
        if animals:
            model_items.append(
                _build_item(
                    f"動物模型：{'、'.join(animals)}",
                    _find_sentence(
                        sentences, ["mice", "mouse", "rat", "rats", "murine", "animal"]
                    ),
                )
            )
        if re.search(r"\bhek\s*293\b", _normalize(abstract)):
            model_items.append(_build_item("細胞模型：HEK293", _find_sentence(sentences, ["hek"])))
        if not model_items:
            model_items = [_build_item("UNKNOWN", "UNKNOWN")]

        manipulation_items = []
        gene_kos = _extract_gene_knockouts(abstract)
        if gene_kos:
            manipulation_items.append(
                _build_item(
                    f"基因操作：{'、'.join(gene_kos)} KO",
                    _find_sentence(sentences, ["knockout", "ko", gene_kos[0].lower()]),
                )
            )
        drugs = _extract_drugs(abstract)
        if drugs:
            manipulation_items.append(
                _build_item(
                    f"藥物處置：{KNOWN_DRUGS.get(drugs[0], drugs[0])}",
                    _find_sentence(sentences, [drugs[0]]),
                )
            )
        if not manipulation_items:
            manipulation_items = [_build_item("UNKNOWN", "UNKNOWN")]

        readouts = _extract_methods(abstract)
        readout_items = []
        if readouts:
            for readout in readouts:
                readout_items.append(
                    _build_item(readout, _find_sentence(sentences, ["urate", "clearance", "gfr", "fitc"]))
                )
        else:
            readout_items = [_build_item("UNKNOWN", "UNKNOWN")]

        mechanism_sentence = _extract_key_mechanism_sentence(sentences)
        mechanism_items = [_build_item(mechanism_sentence or "UNKNOWN", mechanism_sentence)]

        so_what_sentence = _extract_so_what_sentence(sentences)
        so_what_items = [_build_item(so_what_sentence or "UNKNOWN", so_what_sentence)]

        sections = [
            {"title": "Model", "items": model_items},
            {"title": "Manipulation", "items": manipulation_items},
            {"title": "Readouts", "items": readout_items},
            {"title": "Key mechanism", "items": mechanism_items},
            {"title": "So what", "items": so_what_items},
        ]

    else:
        scope_sentence = _find_sentence(sentences, ["review", "guideline", "consensus", "recommendation"])
        data_sentence = _find_sentence(sentences, ["pubmed", "medline", "embase", "cochrane", "database", "search"])
        recommendation_sentence = _find_sentence(sentences, ["recommend", "conclude", "suggest"])
        evidence_sentence = _find_sentence(sentences, ["grade", "quality of evidence", "strength"])
        sections = [
            {"title": "Scope", "items": [_build_item(scope_sentence or "UNKNOWN", scope_sentence)]},
            {"title": "Data sources", "items": [_build_item(data_sentence or "UNKNOWN", data_sentence)]},
            {
                "title": "Key recommendations or conclusions",
                "items": [_build_item(recommendation_sentence or "UNKNOWN", recommendation_sentence)],
            },
            {
                "title": "Evidence strength",
                "items": [_build_item(evidence_sentence or "UNKNOWN", evidence_sentence)],
            },
        ]

    return {
        "classifier": classifier,
        "template": template,
        "sections": sections,
    }


def _extract_follow_up(text):
    text_norm = _normalize(text)
    match = re.search(
        r"\b(\d+)\s*(days|day|weeks|week|months|month|years|year)\b",
        text_norm,
    )
    if match:
        unit_map = {
            "days": "天",
            "day": "天",
            "weeks": "週",
            "week": "週",
            "months": "月",
            "month": "月",
            "years": "年",
            "year": "年",
        }
        return f"追蹤時間：{match.group(1)}{unit_map.get(match.group(2), match.group(2))}"
    return "追蹤時間：UNKNOWN"


def _extract_analysis(text):
    text_norm = _normalize(text)
    metrics = []
    if "hazard ratio" in text_norm:
        metrics.append("HR")
    if "risk ratio" in text_norm or "relative risk" in text_norm:
        metrics.append("RR")
    if "odds ratio" in text_norm:
        metrics.append("OR")
    if "mean difference" in text_norm or "md" in text_norm:
        metrics.append("MD")
    if "confidence interval" in text_norm or "ci" in text_norm:
        metrics.append("CI")
    if metrics:
        return f"主要分析：{', '.join(sorted(set(metrics)))}"
    return "主要分析：UNKNOWN"


def _strip_structured_label(sentence):
    return re.sub(
        r"^(results?|conclusions?|objective|background|methods?|main outcomes? and measures?|findings?):\s*",
        "",
        sentence,
        flags=re.IGNORECASE,
    ).strip()


def _pick_takeaway_sentence(abstract):
    if not abstract:
        return None
    sentences = _split_sentences(abstract)
    prefixes = [
        "results:",
        "conclusions:",
        "conclusion:",
        "findings:",
        "main outcomes and measures:",
    ]
    for sentence in sentences:
        sentence_norm = _normalize(sentence)
        if any(sentence_norm.startswith(prefix) for prefix in prefixes):
            return sentence
    keywords = [
        "significant",
        "did not",
        "increased",
        "decreased",
        "reduced",
        "improved",
        "higher",
        "lower",
        "mortality",
        "risk",
        "hazard",
        "odds",
        "difference",
        "no significant",
        "associated with",
    ]
    for sentence in sentences:
        sentence_norm = _normalize(sentence)
        if any(keyword in sentence_norm for keyword in keywords):
            return sentence
    return None


def _extract_methods(text):
    text_norm = _normalize(text)
    lines = []
    if "fe-urate" in text_norm or ("fractional" in text_norm and "urate" in text_norm):
        lines.append("尿酸分率排泄（FE-urate）")
    if "plasma" in text_norm and "urate" in text_norm:
        lines.append("血漿尿酸")
    if "serum" in text_norm and "urate" in text_norm:
        lines.append("血清尿酸")
    if "creatinine" in text_norm and "urate" in text_norm:
        lines.append("尿/血尿酸與肌酐比（creatinine）")
    elif "creatinine" in text_norm:
        lines.append("肌酐校正/肌酐比（creatinine）")
    if "renal clearance" in text_norm:
        lines.append("腎清除率（renal clearance）")
    if "fitc-sinistrin" in text_norm:
        lines.append("GFR 以 FITC-sinistrin 評估")
    elif "gfr" in text_norm:
        lines.append("腎絲球過濾率（GFR）")
    return _dedupe_lines(lines)


def _normalize_primary_outcome(primary_outcome):
    if not primary_outcome:
        return ""
    text = primary_outcome.strip()
    if "not stated" in text.lower():
        return ""
    text = re.sub(r"^primary outcome inferred:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^primary outcome:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^primary outcome\s*", "", text, flags=re.IGNORECASE)
    return text.rstrip(".").strip()


def infer_tags(title, abstract):
    text = f"{title} {abstract}".lower()
    tags = []
    for tag, keywords in TAG_RULES.items():
        if any(keyword.lower() in text for keyword in keywords):
            tags.append(tag)
    if not tags:
        tags = ["CKD"]
    return tags


def detect_study_type(title, abstract):
    text = _normalize(f"{title} {abstract}")
    if "guideline" in text:
        return "Guideline"
    if "meta-analysis" in text or "systematic review" in text:
        return "Meta-analysis"
    if "randomized" in text or "randomised" in text or "rct" in text or "trial" in text:
        return "Randomized trial"
    if "cohort" in text:
        return "Cohort study"
    if "case-control" in text:
        return "Case-control study"
    if "cross-sectional" in text:
        return "Cross-sectional study"
    return "Observational study"


def extract_primary_outcome(abstract):
    if not abstract:
        return "Primary outcome not stated."
    match = re.search(
        r"(primary (outcome|endpoint)[^\.]*\.)", abstract, flags=re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
    return "Primary outcome not stated."


def detect_outcome_direction(abstract):
    text = _normalize(abstract)
    if any(phrase in text for phrase in ["no significant difference", "no difference", "not different"]):
        return "no difference"
    if any(word in text for word in ["increased", "higher", "improved", "greater"]):
        return "up"
    if any(word in text for word in ["decreased", "reduced", "lower", "declined"]):
        return "down"
    return "no difference"


def build_key_takeaway(study_type, primary_outcome, outcome_direction, tags):
    outcome_summary = _normalize_primary_outcome(primary_outcome)
    direction_phrase = {
        "up": "上升",
        "down": "下降",
        "no difference": "無差異",
    }.get(outcome_direction, "UNKNOWN")
    if not outcome_summary or direction_phrase == "UNKNOWN":
        return "UNKNOWN"
    summary = f"{outcome_summary}{direction_phrase}"
    if len(summary) > 25:
        summary = f"{summary[:24]}…"
    return summary


def summarize(title, abstract, tags):
    study_type = detect_study_type(title, abstract)
    primary_outcome = extract_primary_outcome(abstract)
    outcome_direction = detect_outcome_direction(abstract)
    takeaway_sentence = _pick_takeaway_sentence(abstract)
    if takeaway_sentence:
        takeaway_sentence = _strip_structured_label(takeaway_sentence)
        translation = _translate_to_zh(takeaway_sentence)
        key_takeaway = f"{takeaway_sentence}（{translation}）"
    else:
        key_takeaway = "UNKNOWN"
    return {
        "key_takeaway": key_takeaway,
        "study_type": study_type,
        "primary_outcome": primary_outcome,
        "outcome_direction": outcome_direction,
    }


def pico_from_text(title, abstract, tags, primary_outcome):
    text = f"{title} {abstract}"
    text_norm = _normalize(text)
    sentences = _split_sentences(abstract)

    population_lines = []
    population_phrase = _extract_population_phrase(text)
    if population_phrase:
        population_lines.append(f"族群/疾病：{population_phrase.replace('臨床對象：', '')}")

    animals = _extract_animals(text)
    if animals:
        modifier = "非糖尿病" if "nondiabetic" in text_norm or "non-diabetic" in text_norm else ""
        animal_text = "、".join(animals)
        if modifier:
            population_lines.append(f"動物模型：{modifier}{animal_text}")
        else:
            population_lines.append(f"動物模型：{animal_text}")

    sample_size = _extract_sample_size(text)
    if sample_size:
        population_lines.append(sample_size)

    centers = _extract_centers(text)
    if centers:
        population_lines.append(centers)

    location = _extract_location(text)
    if location:
        population_lines.append(location)

    time_window = _extract_time_window(text)
    if time_window:
        population_lines.append(time_window)

    population_lines = _dedupe_lines(population_lines)
    if len(population_lines) < 2:
        population_lines.extend(
            [
                "族群/疾病：UNKNOWN",
                "樣本數/地點/時間窗：UNKNOWN",
            ]
        )
    population_lines = population_lines[:4]

    intervention_lines = []
    drugs = _extract_drugs(text)
    for drug in drugs:
        label = KNOWN_DRUGS.get(drug, drug)
        intervention_lines.append(f"治療/暴露：{label}")

    dose_drug = _extract_drug_from_dose(text)
    if dose_drug:
        intervention_lines.append(f"治療/暴露：{dose_drug}")

    dose_strings = _extract_dose_strings(text)
    for dose in dose_strings:
        intervention_lines.append(f"劑量：{dose}")

    gene_kos = _extract_gene_knockouts(text)
    if gene_kos:
        intervention_lines.append(f"遺傳介入：{'、'.join(gene_kos)} KO")

    receive_match = re.search(r"\breceive[d]?\s+([^.;]+)", text, flags=re.IGNORECASE)
    if receive_match:
        intervention_lines.append(f"治療/暴露：{receive_match.group(1).strip()}")

    intervention_lines = _dedupe_lines(intervention_lines)
    if not intervention_lines:
        intervention_lines = ["UNKNOWN"]

    comparison_lines = []
    if "placebo" in text_norm:
        comparison_lines.append("對照：placebo")
    if "vehicle" in text_norm:
        comparison_lines.append("對照：vehicle")
    if "wild-type" in text_norm or "wild type" in text_norm:
        comparison_lines.append("對照：野生型")

    comparison = None
    title_lower = _normalize(title)
    if " vs " in title_lower:
        parts = re.split(r"\s+vs\s+", title, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            comparison = parts[1].strip()
    elif " versus " in title_lower:
        parts = re.split(r"\s+versus\s+", title, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            comparison = parts[1].strip()
    elif " compared with " in title_lower:
        parts = re.split(r"\s+compared with\s+", title, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            comparison = parts[1].strip()
    if comparison:
        comparison_lines.append(f"對照：{comparison}")

    comparison_lines = _dedupe_lines(comparison_lines)
    if not comparison_lines:
        comparison_lines = ["UNKNOWN"]

    outcome_lines = []
    primary_phrase = _extract_primary_outcome_phrase(abstract)
    secondary_phrase = _extract_secondary_outcome_phrase(abstract)
    safety_phrase = _extract_safety_phrase(abstract)
    outcome_lines.append(f"Primary：{primary_phrase or 'UNKNOWN'}")
    outcome_lines.append(f"Secondary：{secondary_phrase or 'UNKNOWN'}")
    outcome_lines.append(f"Safety：{safety_phrase or 'UNKNOWN'}")

    design_lines = []
    study_type = detect_study_type(title, abstract)
    if animals:
        design_lines.append("設計：動物/機轉")
    else:
        design_label = DESIGN_MAP.get(study_type, "UNKNOWN")
        design_lines.append(f"設計：{design_label}")
    design_lines.append(_extract_follow_up(text))
    design_lines.append(_extract_analysis(text))

    result_sentences = []
    for sentence in sentences:
        sentence_norm = _normalize(sentence)
        if any(
            keyword in sentence_norm
            for keyword in [
                "significant",
                "no significant",
                "increased",
                "decreased",
                "higher",
                "lower",
                "mortality",
                "death",
                "arrhythmia",
            ]
        ):
            result_sentences.append(sentence)
        if len(result_sentences) >= 2:
            break
    if not result_sentences:
        result_sentences = ["UNKNOWN"]
    result_lines = [f"結果 {index + 1}：{sentence}" for index, sentence in enumerate(result_sentences)]

    evidence = {
        "P evidence": _find_sentence(
            sentences, ["patients", "participants", "subjects", "adult", "mice", "rats", "icu"]
        ),
        "I evidence": _find_sentence(
            sentences, ["treated with", "receive", "administer", "infusion", "dose"]
        ),
        "C evidence": _find_sentence(
            sentences, ["placebo", "vehicle", "control", "compared", "randomized"]
        ),
        "O evidence": _find_sentence(
            sentences, ["primary outcome", "secondary", "outcome", "mortality"]
        ),
    }

    return {
        "P": "\n".join(population_lines),
        "I": "\n".join(intervention_lines),
        "C": "\n".join(comparison_lines),
        "O": "\n".join(outcome_lines),
        "design": "\n".join(design_lines),
        "results": "\n".join(result_lines),
        "evidence": "\n".join([f"{key}: \"{value}\"" for key, value in evidence.items()]),
    }


def impact_assessment(study_type, outcome_direction):
    if study_type in ["Guideline", "Meta-analysis"]:
        return {
            "level": "possibly",
            "reason": "Synthesized evidence; verify quality and applicability.",
        }
    if study_type == "Randomized trial":
        if outcome_direction in ["up", "down"]:
            return {
                "level": "yes",
                "reason": "Randomized design with directional outcome.",
            }
        return {
            "level": "possibly",
            "reason": "Randomized design but effect is unclear.",
        }
    if study_type in ["Cohort study", "Case-control study"]:
        return {
            "level": "possibly",
            "reason": "Observational design; interpret with caution.",
        }
    return {
        "level": "no",
        "reason": "Preliminary evidence or unclear impact.",
    }
