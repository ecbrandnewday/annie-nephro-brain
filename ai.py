import os
import re
import traceback

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
_ONE_CLICK_SUMMARY_CACHE = {}

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

def _normalize(text):
    return (text or "").lower()


def openai_chat(messages, temperature=0, model=None, log_errors=True):
    if not OPENAI_API_KEY:
        return {"ok": False, "error": "OPENAI_API_KEY not set"}
    payload = {
        "model": model or OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
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
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            raise ValueError("empty OpenAI response")
        return {"ok": True, "content": content}
    except Exception as exc:
        if log_errors:
            print(f"[OpenAI] model={OPENAI_MODEL} base_url={OPENAI_API_URL}")
            print(f"[OpenAI] exception={exc!r}")
            traceback.print_exc()
        error = str(exc).strip() or repr(exc)
        return {"ok": False, "error": error[:500]}


def _translate_to_zh(text):
    if not text:
        return "UNKNOWN"
    if text in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[text]
    result = openai_chat(
        [
            {
                "role": "system",
                "content": (
                    "You are a medical translator. Translate the given sentence into Traditional Chinese. "
                    "Keep it concise, single sentence, preserve meaning, and do not add new information."
                ),
            },
            {"role": "user", "content": text},
        ],
        temperature=0,
        log_errors=False,
    )
    translation = result.get("content") if result.get("ok") else "UNKNOWN"
    if not translation:
        translation = "UNKNOWN"
    _TRANSLATION_CACHE[text] = translation
    return translation


def summarize_article_with_openai(title, abstract):
    if not title and not abstract:
        return {"ok": False, "summary": "UNKNOWN", "error": "missing title/abstract"}
    cache_key = f"{title}||{abstract}"
    if cache_key in _ONE_CLICK_SUMMARY_CACHE:
        return _ONE_CLICK_SUMMARY_CACHE[cache_key]
    prompt = (
        "你是腎臟科臨床研究助理。任務是「從 Title + Abstract 抽取資訊並重組」以協助臨床快速判讀，"
        "不做科普。"
        "重要規則："
        "只能使用我提供的 Title 與 Abstract；沒寫到一律輸出 UNKNOWN，不得推測或編造。"
        "禁止模板空話（例如：Adult patients / Intervention in study / Comparator in study）。"
        "先判斷研究類型（只從 Title/Abstract 判斷），擇一："
        "A) Clinical trial / interventional study（有介入與對照）"
        "B) Observational study（cohort/case-control/cross-sectional）"
        "C) Diagnostic / prognostic / biomarker study"
        "D) Systematic review / meta-analysis / narrative review"
        "E) Guideline / consensus / position statement"
        "F) Editorial / commentary / letter / viewpoint"
        "G) Basic / animal / in vitro / mechanistic"
        "H) Other / unclear"
        "若 Title/Abstract 出現 guideline/guidelines/consensus/position statement/recommendation，優先判定 E。"
        "輸出規則："
        "第一行必須是「【研究類型】<代碼> <名稱>」。"
        "不論類型，必須包含一行「重點結論：...」。"
        "若類型為 A/B/C，必須輸出 PICO 四行，格式固定："
        "P：..."
        "I：..."
        "C：..."
        "O：..."
        "A/B/C 不可用條列摘要。"
        "PICO 內容僅能取自 Title/Abstract 中可直接對應的名詞片語；若該欄位完全無資訊才寫 UNKNOWN。"
        "若類型非 A/B/C，禁止輸出任何 P/I/C/O 行，改用條列式摘要（以「• 」開頭）。"
        "總結字數控制在 500 字以內，輸出繁體中文。"
    )
    user_content = f"Title: {title}\n\nAbstract:\n{abstract}"
    result = openai_chat(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )
    if not result.get("ok"):
        error = result.get("error") or "OpenAI request failed"
        return {"ok": False, "summary": "UNKNOWN", "error": error}
    summary = result.get("content", "").strip()
    if len(summary) > 500:
        summary = summary[:500].rstrip()
    payload = {"ok": True, "summary": summary}
    _ONE_CLICK_SUMMARY_CACHE[cache_key] = payload
    return payload


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


def summarize(title, abstract, tags, translate=False):
    study_type = detect_study_type(title, abstract)
    primary_outcome = extract_primary_outcome(abstract)
    outcome_direction = detect_outcome_direction(abstract)
    takeaway_sentence = _pick_takeaway_sentence(abstract)
    if takeaway_sentence:
        takeaway_sentence = _strip_structured_label(takeaway_sentence)
        if translate:
            translation = _translate_to_zh(takeaway_sentence)
            key_takeaway = f"{takeaway_sentence}（{translation}）"
        else:
            key_takeaway = takeaway_sentence
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
