import re

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
    sentences = [s.strip() for s in abstract.split(".") if s.strip()]
    if len(sentences) >= 2:
        return f"Primary outcome inferred: {sentences[1]}."
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
    population_hint = "nephrology patients"
    if "AKI" in tags:
        population_hint = "patients with AKI"
    elif "CKD" in tags:
        population_hint = "patients with CKD"
    elif "HD" in tags:
        population_hint = "patients on hemodialysis"
    elif "PD" in tags:
        population_hint = "patients on peritoneal dialysis"
    elif "Transplant" in tags:
        population_hint = "kidney transplant recipients"

    direction_phrase = {
        "up": "a higher",
        "down": "a lower",
        "no difference": "no clear difference in",
    }.get(outcome_direction, "no clear difference in")

    outcome_summary = primary_outcome.replace("Primary outcome", "Outcome").strip()
    return f"{study_type} in {population_hint} shows {direction_phrase} {outcome_summary.lower()}"


def summarize(title, abstract, tags):
    study_type = detect_study_type(title, abstract)
    primary_outcome = extract_primary_outcome(abstract)
    outcome_direction = detect_outcome_direction(abstract)
    key_takeaway = build_key_takeaway(
        study_type, primary_outcome, outcome_direction, tags
    )
    return {
        "key_takeaway": key_takeaway,
        "study_type": study_type,
        "primary_outcome": primary_outcome,
        "outcome_direction": outcome_direction,
    }


def pico_from_text(title, abstract, tags, primary_outcome):
    population = "Adult nephrology patients"
    if "AKI" in tags:
        population = "Adults with acute kidney injury"
    elif "CKD" in tags:
        population = "Adults with chronic kidney disease"
    elif "HD" in tags:
        population = "Adults receiving hemodialysis"
    elif "PD" in tags:
        population = "Adults on peritoneal dialysis"
    elif "Transplant" in tags:
        population = "Kidney transplant recipients"
    elif "Electrolyte disorders" in tags:
        population = "Patients with electrolyte disorders"
    elif "GN / IgA / Lupus" in tags:
        population = "Patients with immune-mediated kidney disease"

    intervention = "Intervention in study"
    comparison = "Comparator in study"
    title_lower = _normalize(title)
    if " vs " in title_lower:
        parts = re.split(r"\s+vs\s+", title, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            intervention, comparison = parts[0].strip(), parts[1].strip()
    elif " versus " in title_lower:
        parts = re.split(r"\s+versus\s+", title, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            intervention, comparison = parts[0].strip(), parts[1].strip()
    elif " compared with " in title_lower:
        parts = re.split(r"\s+compared with\s+", title, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            intervention, comparison = parts[0].strip(), parts[1].strip()

    outcome = primary_outcome or "Primary outcome not stated."
    return {"P": population, "I": intervention, "C": comparison, "O": outcome}


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
