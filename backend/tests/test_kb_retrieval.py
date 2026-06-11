"""Retrieval smoke tests for the MACE knowledge base."""

from backend.kb_processor import detect_course_filter, detect_section_filter
from backend.rag_pipeline import get_rag_pipeline

SAMPLE_QUERIES = [
    ("What courses does MACE AI Academy provide?", {"section_type": "courses_overview"}, "Artificial Intelligence"),
    ("Who is the CEO of MACE AI Academy?", {"section_type": "leadership"}, "Mirza Ahmed Baig"),
    ("Tell me about Syed Abdul Baseer", {"section_type": "trainers"}, "Syed Abdul Baseer"),
    ("What are the prerequisites for Data Science?", {"course_id": "data_science"}, "Prerequisites"),
    ("What qualifications are required for AI and ML?", {"course_id": "ai_ml"}, "Qualification"),
    ("What modules are covered in Data Analytics?", {"course_id": "data_analytics"}, "Modules"),
    ("What career opportunities exist in Generative AI?", {"course_id": "generative_ai"}, "Career Opportunities"),
    ("What is Vibe Coding?", {"course_id": "vibe_coding"}, "Vibe Coding"),
    ("What is AI Product Management?", {"course_id": "ai_product_management"}, "AI Product Management"),
    ("What is Data Engineering?", {"course_id": "data_engineering"}, "Data Engineering"),
]


def _metadata_matches(source: dict, expected: dict) -> bool:
    if "course_id" in expected:
        return (
            source.get("section_type") == "course"
            and source.get("course_id") == expected["course_id"]
        )
    if "section_type" in expected:
        return source.get("section_type") == expected["section_type"]
    return False


def run_retrieval_tests() -> None:
    pipeline = get_rag_pipeline()
    failures = 0

    for query, expected_meta, expected_snippet in SAMPLE_QUERIES:
        sources = pipeline.format_sources(pipeline.retrieve_context(query))
        if not sources:
            print(f"FAIL: no sources for {query!r}")
            failures += 1
            continue

        top = sources[0]
        meta_ok = any(_metadata_matches(src, expected_meta) for src in sources)
        snippet_ok = expected_snippet.lower() in " ".join(s["content"] for s in sources).lower()

        if meta_ok and snippet_ok:
            print(
                f"OK: {query!r} | score={top['score']:.3f} | "
                f"section={top.get('section_type')} | hits={len(sources)}"
            )
        else:
            print(
                f"FAIL: {query!r} | meta_ok={meta_ok} snippet_ok={snippet_ok} | "
                f"top_section={top.get('section_type')}"
            )
            failures += 1

    # Sanity: course and section filters resolve for representative queries
    assert detect_course_filter("What is Data Science?") == "data_science"
    assert detect_section_filter("Who is the CEO?") == {"section_type": "leadership"}

    if failures:
        raise SystemExit(f"{failures} retrieval test(s) failed")

    print("All retrieval tests passed.")


if __name__ == "__main__":
    run_retrieval_tests()
