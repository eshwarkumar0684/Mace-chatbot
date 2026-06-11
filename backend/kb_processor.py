"""Parse and chunk the MACE AI Academy knowledge base document for RAG."""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import settings
from backend.utils import logger

# Canonical course sections in the knowledge base (order matters for splitting).
COURSE_SECTIONS: Tuple[Tuple[str, str, str], ...] = (
    (
        "WHAT IS ARTIFICIAL INTELLIGENCE & MACHINE LEARNING",
        "ai_ml",
        "AI & ML with Generative AI",
    ),
    ("WHAT IS DATA SCIENCE", "data_science", "Data Science with Generative AI"),
    ("WHAT IS DATA ANALYTICS", "data_analytics", "Data Analytics with Generative AI"),
    ("WHAT IS GENERATIVE AI", "generative_ai", "Generative AI"),
    ("WHAT IS AI PRODUCT MANAGEMENT", "ai_product_management", "AI Product Management"),
    ("WHAT IS DATA ENGINEERING", "data_engineering", "Data Engineering"),
    ("WHAT IS VIBE CODING", "vibe_coding", "Vibe Coding"),
)

STATIC_SECTIONS: Tuple[Tuple[str, str, str], ...] = (
    ("# About MACE AI Academy", "about", "About MACE AI Academy"),
    ("# Leadership Team", "leadership", "Leadership Team"),
    ("# Why Choose MACE AI Academy", "highlights", "Why Choose MACE AI Academy"),
    ("# Trainers & Faculty", "trainers", "Trainers & Faculty"),
    ("# Courses Offered", "courses_overview", "Courses Offered"),
)

SUPPLEMENTAL_FILE_META: Dict[str, Dict[str, str]] = {
    "faq.txt": {
        "section_type": "faq",
        "course_id": "faq",
        "course_name": "General FAQs",
        "section_title": "General FAQs",
    },
    "ai_course.txt": {
        "section_type": "course",
        "course_id": "ai_ml",
        "course_name": "AI & ML with Generative AI",
        "section_title": "AI & ML with Generative AI",
    },
    "data_science.txt": {
        "section_type": "course",
        "course_id": "data_science",
        "course_name": "Data Science with Generative AI",
        "section_title": "Data Science with Generative AI",
    },
    "analytics.txt": {
        "section_type": "course",
        "course_id": "data_analytics",
        "course_name": "Data Analytics with Generative AI",
        "section_title": "Data Analytics with Generative AI",
    },
}

COURSE_QUERY_ALIASES: Dict[str, str] = {
    "ai/ml": "Artificial Intelligence Machine Learning",
    "ai & ml": "Artificial Intelligence Machine Learning",
    "ai and ml": "Artificial Intelligence Machine Learning",
    "machine learning": "Artificial Intelligence Machine Learning",
    "artificial intelligence": "Artificial Intelligence Machine Learning",
    "data science": "Data Science",
    "data analytics": "Data Analytics",
    "generative ai": "Generative AI",
    "ai product management": "AI Product Management",
    "product management": "AI Product Management",
    "data engineering": "Data Engineering",
    "vibe coding": "Vibe Coding",
    "ceo": "Mirza Ahmed Baig Leadership",
    "founder": "Mirza Ahmed Baig Leadership",
    "mirza ahmed baig": "Mirza Ahmed Baig Leadership",
    "trainer": "Trainers Faculty",
    "trainers": "Trainers Faculty",
    "syed abdul baseer": "Syed Abdul Baseer",
    "mohammed abdul imtiyaz": "Mohammed Abdul Imtiyaz",
    "girumapuram eeshwar kumar": "Girumapuram Eeshwar Kumar",
    "career": "Career Opportunities",
    "prerequisite": "Prerequisites",
    "qualification": "Qualification Required",
    "module": "Modules",
    "fee": "Fee Structure EMI Payment",
    "fees": "Fee Structure EMI Payment",
    "cost": "Fee Structure Course Fee INR",
    "price": "Fee Structure Course Fee INR",
    "duration": "Course Duration Months Weeks",
    "how long": "Course Duration Months Weeks",
    "placement": "Placement Assistance Support",
    "emi": "Easy Monthly Installments EMI",
    "payment": "Fee Payment Structure",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _section_fingerprint(title: str, body: str) -> str:
    payload = f"{title}|{_normalize(body)[:2000]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _split_on_markers(text: str, markers: List[str]) -> List[Tuple[str, str]]:
    if not text.strip():
        return []

    pattern = "|".join(re.escape(marker) for marker in markers)
    parts = re.split(rf"(?=({pattern}))", text, flags=re.IGNORECASE)
    sections: List[Tuple[str, str]] = []
    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        if not chunk:
            i += 1
            continue
        if chunk.upper() in {m.upper() for m in markers}:
            title = chunk
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            sections.append((title, body))
            i += 2
        else:
            sections.append(("General", chunk))
            i += 1
    return sections


def _strip_repeated_identity_blocks(text: str) -> str:
    """Remove repeated chatbot-identity boilerplate embedded between course sections."""
    marker = "# MACE AI Academy Chatbot Identity"
    parts = re.split(re.escape(marker), text, flags=re.IGNORECASE)
    if len(parts) <= 1:
        return text
    cleaned = parts[0]
    for part in parts[1:]:
        # Keep content after the identity block up to the next real section heading.
        match = re.search(
            r"(?:#\s|WHAT IS )",
            part,
            flags=re.IGNORECASE,
        )
        if match:
            cleaned += part[match.start() :]
    return cleaned


def extract_unique_sections(raw_text: str) -> List[Tuple[str, str, Dict[str, str]]]:
    """Extract deduplicated logical sections from the raw knowledge base text."""
    text = raw_text.replace("\r\n", "\n")
    text = _strip_repeated_identity_blocks(text)
    # Drop the leading chatbot-identity block; keep the overview that precedes it.
    intro_split = re.split(r"# MACE AI Academy Chatbot Identity", text, maxsplit=1, flags=re.IGNORECASE)
    preamble = intro_split[0].strip()
    remainder = intro_split[1] if len(intro_split) > 1 else text
    remainder = _strip_repeated_identity_blocks(remainder)

    seen: set[str] = set()
    course_best: Dict[str, Tuple[str, str, Dict[str, str]]] = {}
    unique: List[Tuple[str, str, Dict[str, str]]] = []

    for title, body, metadata in _iter_raw_sections(preamble, remainder):
        if not body.strip():
            continue

        course_id = metadata.get("course_id", "")
        if metadata.get("section_type") == "course" and course_id:
            existing = course_best.get(course_id)
            if existing is None or len(body) > len(existing[1]):
                course_best[course_id] = (title, body, metadata)
            continue

        fingerprint = _section_fingerprint(title, body)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append((title, body, metadata))

    unique.extend(course_best.values())
    unique.sort(
        key=lambda item: (
            item[2].get("section_type", ""),
            item[2].get("course_id", ""),
            item[0],
        )
    )
    logger.info("Extracted %d unique knowledge-base sections", len(unique))
    return unique


def _iter_raw_sections(preamble: str, remainder: str):
    if preamble:
        yield (
            "Overview",
            preamble,
            {
                "section_title": "Overview",
                "section_type": "general",
                "course_id": "",
                "course_name": "",
                "source": settings.KNOWLEDGE_BASE_FILE,
            },
        )

    markers = [title for title, _, _ in STATIC_SECTIONS] + [title for title, _, _ in COURSE_SECTIONS]
    for title, body in _split_on_markers(remainder, markers):
        metadata = {
            "section_title": title.strip(),
            "section_type": "general",
            "course_id": "",
            "course_name": "",
            "source": settings.KNOWLEDGE_BASE_FILE,
        }

        upper_title = title.upper()
        for marker, course_id, course_name in COURSE_SECTIONS:
            if marker in upper_title:
                metadata.update(
                    {
                        "section_type": "course",
                        "course_id": course_id,
                        "course_name": course_name,
                    }
                )
                break
        else:
            for marker, section_id, section_name in STATIC_SECTIONS:
                if marker.lower() in title.lower():
                    metadata.update(
                        {
                            "section_type": section_id,
                            "course_id": section_id,
                            "course_name": section_name,
                        }
                    )
                    break

        yield (title.strip(), body.strip(), metadata)


def _build_section_header(title: str, metadata: Dict[str, str]) -> str:
    lines = [f"Section: {title}"]
    if metadata.get("course_name"):
        lines.append(f"Course: {metadata['course_name']}")
    if metadata.get("section_type"):
        lines.append(f"Category: {metadata['section_type']}")
    return "\n".join(lines)


def chunk_knowledge_base(raw_text: str) -> List[Document]:
    """Turn raw KB text into metadata-rich chunks optimized for retrieval."""
    sections = extract_unique_sections(raw_text)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.RAG_CHUNK_SIZE,
        chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        length_function=len,
        add_start_index=True,
        separators=["\n\n", "\n", ". ", ", ", " "],
    )

    documents: List[Document] = []
    for title, body, metadata in sections:
        header = _build_section_header(title, metadata)
        enriched_body = f"{header}\n\n{body}"
        base_meta = dict(metadata)
        base_meta["section_title"] = title

        if len(enriched_body) <= settings.RAG_CHUNK_SIZE:
            documents.append(Document(page_content=enriched_body, metadata=base_meta))
            continue

        for idx, chunk in enumerate(splitter.split_text(enriched_body)):
            chunk_meta = dict(base_meta)
            chunk_meta["chunk_index"] = str(idx)
            documents.append(Document(page_content=chunk, metadata=chunk_meta))

    logger.info("Knowledge base chunked into %d documents", len(documents))
    return documents


def chunk_supplemental_document(filename: str, raw_text: str) -> List[Document]:
    """Chunk a supplemental data file (FAQ, course prospectus, etc.)."""
    meta = SUPPLEMENTAL_FILE_META.get(filename)
    if not meta or not raw_text.strip():
        return []

    header = _build_section_header(meta["section_title"], meta)
    enriched_body = f"{header}\n\n{raw_text.strip()}"
    base_meta = {
        "source": filename,
        "section_title": meta["section_title"],
        "section_type": meta["section_type"],
        "course_id": meta["course_id"],
        "course_name": meta["course_name"],
    }

    if len(enriched_body) <= settings.RAG_CHUNK_SIZE:
        return [Document(page_content=enriched_body, metadata=dict(base_meta))]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.RAG_CHUNK_SIZE,
        chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        length_function=len,
        add_start_index=True,
        separators=["\n\n", "\n", ". ", ", ", " "],
    )
    documents: List[Document] = []
    for idx, chunk in enumerate(splitter.split_text(enriched_body)):
        chunk_meta = dict(base_meta)
        chunk_meta["chunk_index"] = str(idx)
        documents.append(Document(page_content=chunk, metadata=chunk_meta))
    return documents


def expand_query(query: str) -> str:
    """Add course/topic aliases to improve embedding retrieval."""
    lowered = query.lower()
    extras: List[str] = []
    for alias, expansion in COURSE_QUERY_ALIASES.items():
        if alias in lowered:
            extras.append(expansion)
    if not extras:
        return query
    return f"{query}\nRelated topics: {', '.join(dict.fromkeys(extras))}"


def detect_course_filter(query: str) -> str | None:
    """Return course_id metadata filter when the query names a specific course."""
    lowered = query.lower()
    mapping = {
        "vibe coding": "vibe_coding",
        "ai product management": "ai_product_management",
        "product management": "ai_product_management",
        "data engineering": "data_engineering",
        "data analytics": "data_analytics",
        "data science": "data_science",
        "generative ai": "generative_ai",
        "ai/ml": "ai_ml",
        "ai & ml": "ai_ml",
        "ai and ml": "ai_ml",
        "artificial intelligence": "ai_ml",
        "machine learning": "ai_ml",
    }
    for alias in sorted(mapping, key=len, reverse=True):
        if alias in lowered:
            return mapping[alias]
    return None


def detect_section_filter(query: str) -> Dict[str, str] | None:
    """Return metadata filter for non-course knowledge sections."""
    lowered = query.lower()
    if any(term in lowered for term in ("ceo", "founder", "mirza ahmed baig", "leadership")):
        return {"section_type": "leadership"}
    if any(
        term in lowered
        for term in (
            "trainer",
            "trainers",
            "faculty",
            "syed abdul baseer",
            "mohammed abdul imtiyaz",
            "girumapuram eeshwar kumar",
        )
    ):
        return {"section_type": "trainers"}
    if any(term in lowered for term in ("courses offered", "what courses", "programs offered")):
        return {"section_type": "courses_overview"}
    if any(
        term in lowered
        for term in (
            "fee",
            "fees",
            "emi",
            "payment",
            "how much",
            "cost",
            "price",
            "placement",
            "duration",
            "how long",
            "installment",
        )
    ):
        return {"section_type": "faq"}
    return None
