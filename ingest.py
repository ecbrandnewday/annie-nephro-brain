import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import requests

from ai import infer_tags, impact_assessment, pico_from_text, summarize
from db import get_db, init_db, set_meta

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_JOURNALS = [
    "New England Journal of Medicine",
    "Nature Reviews Nephrology",
    "Kidney International",
    "Journal of the American Society of Nephrology",
    "American Journal of Kidney Diseases",
    "Clinical Journal of the American Society of Nephrology",
    "Nephrology Dialysis Transplantation",
    "Kidney International Reports",
    "American Journal of Nephrology",
    "Clinical Kidney Journal",
    "Journal of Nephrology",
]

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

MISSING_ABSTRACT_MARKERS = [
    "no abstract available",
    "abstract not available",
]


def _is_missing_abstract(text):
    if not text:
        return True
    normalized = text.strip().lower()
    return any(marker in normalized for marker in MISSING_ABSTRACT_MARKERS)


def _node_text(node):
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def fetch_article_ids(journal, start_date, end_date, max_per_journal):
    query = f'"{journal}"[Journal]'
    base_params = {
        "db": "pubmed",
        "term": query,
        "datetype": "pdat",
        "mindate": start_date.strftime("%Y/%m/%d"),
        "maxdate": end_date.strftime("%Y/%m/%d"),
    }
    if max_per_journal and max_per_journal > 0:
        params = {**base_params, "retmax": max_per_journal}
        response = requests.get(f"{BASE_URL}/esearch.fcgi", params=params, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        return [el.text for el in root.findall(".//Id") if el.text]

    count_params = {**base_params, "retmax": 0}
    count_response = requests.get(
        f"{BASE_URL}/esearch.fcgi", params=count_params, timeout=30
    )
    count_response.raise_for_status()
    count_root = ET.fromstring(count_response.text)
    count_text = count_root.findtext(".//Count", "0")
    total = int(count_text) if count_text.isdigit() else 0
    if total == 0:
        return []

    batch_size = 200
    ids = []
    for retstart in range(0, total, batch_size):
        params = {**base_params, "retmax": batch_size, "retstart": retstart}
        response = requests.get(f"{BASE_URL}/esearch.fcgi", params=params, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        ids.extend([el.text for el in root.findall(".//Id") if el.text])
    return ids


def fetch_article_details(pmids):
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    response = requests.get(f"{BASE_URL}/efetch.fcgi", params=params, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    return root.findall(".//PubmedArticle")


def parse_pub_date(article_node):
    pub_date_node = article_node.find(".//Journal/JournalIssue/PubDate")
    if pub_date_node is None:
        return date.today().isoformat()
    year = pub_date_node.findtext("Year")
    month = pub_date_node.findtext("Month")
    day = pub_date_node.findtext("Day")
    if not year:
        medline_date = pub_date_node.findtext("MedlineDate", "")
        match = next((token for token in medline_date.split() if token.isdigit()), None)
        year = match or str(date.today().year)
    if month:
        month_key = month.strip().lower()[:3]
        month = MONTH_MAP.get(month_key, "01")
    else:
        month = "01"
    day = day.zfill(2) if day and day.isdigit() else "01"
    return f"{year}-{month}-{day}"


def parse_article(article_node):
    pmid = article_node.findtext(".//PMID")
    title_node = article_node.find(".//ArticleTitle")
    title = _node_text(title_node) or "Untitled"
    abstract_parts = []
    for node in article_node.findall(".//AbstractText"):
        text = _node_text(node)
        if _is_missing_abstract(text):
            continue
        label = node.attrib.get("Label") or node.attrib.get("NlmCategory")
        if label and label.upper() == "UNASSIGNED":
            label = None
        if label:
            label_text = label.strip().title()
            abstract_parts.append(f"{label_text}: {text}")
        else:
            abstract_parts.append(text)
    abstract = "\n\n".join(abstract_parts)
    if not abstract:
        return None
    journal = article_node.findtext(".//Journal/Title") or "Unknown journal"
    publish_date = parse_pub_date(article_node)
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    return {
        "id": pmid,
        "title": title,
        "abstract": abstract,
        "journal": journal,
        "publish_date": publish_date,
        "url": url,
    }


def upsert_article(conn, article):
    now = datetime.utcnow().isoformat()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO articles (
            id, title, abstract, journal, publish_date, url, tags,
            key_takeaway, study_type, primary_outcome, outcome_direction,
            pico_p, pico_i, pico_c, pico_o, impact_level, impact_reason,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            abstract = excluded.abstract,
            journal = excluded.journal,
            publish_date = excluded.publish_date,
            url = excluded.url,
            tags = excluded.tags,
            key_takeaway = excluded.key_takeaway,
            study_type = excluded.study_type,
            primary_outcome = excluded.primary_outcome,
            outcome_direction = excluded.outcome_direction,
            pico_p = excluded.pico_p,
            pico_i = excluded.pico_i,
            pico_c = excluded.pico_c,
            pico_o = excluded.pico_o,
            impact_level = excluded.impact_level,
            impact_reason = excluded.impact_reason,
            updated_at = excluded.updated_at
        """,
        (
            article["id"],
            article["title"],
            article["abstract"],
            article["journal"],
            article["publish_date"],
            article["url"],
            json.dumps(article["tags"]),
            article["key_takeaway"],
            article["study_type"],
            article["primary_outcome"],
            article["outcome_direction"],
            article["pico"]["P"],
            article["pico"]["I"],
            article["pico"]["C"],
            article["pico"]["O"],
            article["impact"]["level"],
            article["impact"]["reason"],
            now,
            now,
        ),
    )
    conn.commit()


def run_ingest_range(journals, start_date, end_date, max_per_journal):
    init_db()
    conn = get_db()
    stored = 0
    for journal in journals:
        pmids = fetch_article_ids(journal, start_date, end_date, max_per_journal)
        if not pmids:
            continue
        for article_node in fetch_article_details(pmids):
            parsed = parse_article(article_node)
            if not parsed:
                continue
            tags = infer_tags(parsed["title"], parsed["abstract"])
            summary = summarize(parsed["title"], parsed["abstract"], tags)
            pico = pico_from_text(
                parsed["title"],
                parsed["abstract"],
                tags,
                summary["primary_outcome"],
            )
            impact = impact_assessment(summary["study_type"], summary["outcome_direction"])
            parsed.update(
                {
                    "tags": tags,
                    "key_takeaway": summary["key_takeaway"],
                    "study_type": summary["study_type"],
                    "primary_outcome": summary["primary_outcome"],
                    "outcome_direction": summary["outcome_direction"],
                    "pico": pico,
                    "impact": impact,
                }
            )
            upsert_article(conn, parsed)
            stored += 1
    set_meta(conn, "last_sync", datetime.now(timezone.utc).isoformat())
    conn.close()
    return stored


def run_ingest(journals, days, max_per_journal):
    start_date = date.today() - timedelta(days=days)
    end_date = date.today()
    return run_ingest_range(journals, start_date, end_date, max_per_journal)


def main():
    parser = argparse.ArgumentParser(description="Ingest PubMed articles.")
    parser.add_argument("--days", type=int, default=3, help="Lookback window in days.")
    parser.add_argument(
        "--max-per-journal",
        type=int,
        default=5,
        help="Max articles per journal.",
    )
    parser.add_argument(
        "--journals",
        type=str,
        default="",
        help="Comma-separated list of journals to query.",
    )
    args = parser.parse_args()
    journals = DEFAULT_JOURNALS
    if args.journals.strip():
        journals = [j.strip() for j in args.journals.split(",") if j.strip()]
    stored = run_ingest(journals, args.days, args.max_per_journal)
    print(f"Stored {stored} articles.")


if __name__ == "__main__":
    main()
