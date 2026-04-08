import re
from collections import Counter
from typing import Any

from schemas import UserBookRequest, PlanningContext


class ScopeBuilder:
    def __init__(self) -> None:
        pass

    def _collect_text_blocks(self, discovery_bundle: dict[str, Any]) -> list[str]:
        text_blocks: list[str] = []

        for bucket in discovery_bundle.values():
            search_result = bucket.get("search_result", {})
            answer = search_result.get("answer", "")
            if answer:
                text_blocks.append(answer)

            successful_pages = bucket.get("successful_pages", [])
            for page in successful_pages:
                content = page.get("content", "")
                if content:
                    text_blocks.append(content[:4000])

        return text_blocks

    def _normalize_line(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _extract_candidate_lines(self, text_blocks: list[str]) -> list[str]:
        lines: list[str] = []

        for block in text_blocks:
            for raw_line in block.splitlines():
                line = self._normalize_line(raw_line)

                if len(line) < 20:
                    continue

                if line.lower().startswith(("title:", "url source:", "published time:", "markdown content:")):
                    continue

                lines.append(line)

        return lines

    def _pick_audience_needs(self, lines: list[str]) -> list[str]:
        keywords = [
            "struggle",
            "challenge",
            "problem",
            "learn",
            "understand",
            "beginner",
            "roadmap",
            "faq",
            "question",
            "how to",
        ]

        selected: list[str] = []
        for line in lines:
            lower = line.lower()
            if any(keyword in lower for keyword in keywords):
                selected.append(line)

        return selected[:8]

    def _pick_main_questions(self, lines: list[str]) -> list[str]:
        questions: list[str] = []

        for line in lines:
            if "?" in line:
                questions.append(line)

        return questions[:8]

    def _extract_key_themes(self, lines: list[str], topic: str) -> list[str]:
        topic_words = {word.lower() for word in re.findall(r"[a-zA-Z0-9]+", topic) if len(word) > 2}

        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "into", "about",
            "your", "their", "what", "when", "where", "which", "will", "have",
            "using", "used", "than", "then", "also", "more", "most", "into",
            "guide", "learn", "learning", "book", "chapter", "topic", "topics",
            "introduction", "overview",
        }

        words: list[str] = []
        for line in lines:
            for word in re.findall(r"[a-zA-Z0-9\-\+]+", line.lower()):
                if len(word) < 4:
                    continue
                if word in stopwords:
                    continue
                if word in topic_words:
                    continue
                words.append(word)

        counter = Counter(words)
        return [word for word, _ in counter.most_common(12)]

    def _build_scope_includes(self, discovery_bundle: dict[str, Any], lines: list[str]) -> list[str]:
        includes: list[str] = []

        bucket_to_label = {
            "topic_subareas": "major subareas of the topic",
            "competitor_books": "commonly covered chapter themes",
            "structure_frameworks": "learning progression and structure patterns",
            "audience_needs": "reader pain points and recurring beginner questions",
        }

        for key, label in bucket_to_label.items():
            if key in discovery_bundle:
                includes.append(label)

        return includes

    def _build_scope_excludes(self, request: UserBookRequest) -> list[str]:
        if request.depth == "introductory":
            return [
                "deep specialist treatment",
                "advanced edge cases",
                "heavy research-level detail",
            ]
        if request.depth == "intermediate":
            return [
                "extreme beginner-only repetition",
                "deep research-level detail",
                "very advanced niche edge cases",
            ]
        return [
            "basic-only explanations",
            "over-simplified coverage",
        ]

    def _build_sequence_logic(self, request: UserBookRequest, key_themes: list[str]) -> list[str]:
        logic = [
            "start with foundations and definitions",
            "introduce major concepts before methods and applications",
            "place practical usage after conceptual grounding",
            "move from simpler ideas to more advanced or integrated topics",
        ]

        if request.depth in {"intermediate", "advanced"}:
            logic.append("place implementation or applied workflow chapters after foundational chapters")

        if key_themes:
            logic.append("group related themes into coherent chapter clusters")

        return logic

    def _build_structure_options(self, request: UserBookRequest) -> list[str]:
        return [
            "linear chapter-by-chapter learning path",
            "progressive structure from foundations to application",
            "theory followed by practical examples within each major part",
        ]

    def _build_evidence_examples(self, lines: list[str]) -> list[str]:
        keywords = [
            "case study",
            "example",
            "examples",
            "exercise",
            "real-world",
            "application",
            "use case",
            "story",
        ]

        selected: list[str] = []
        for line in lines:
            lower = line.lower()
            if any(keyword in lower for keyword in keywords):
                selected.append(line)

        return selected[:8]

    def _build_notes(self, lines: list[str]) -> list[str]:
        return lines[:10]

    def build_context(
        self,
        request: UserBookRequest,
        discovery_bundle: dict[str, Any],
    ) -> PlanningContext:
        text_blocks = self._collect_text_blocks(discovery_bundle)
        lines = self._extract_candidate_lines(text_blocks)

        audience_needs = self._pick_audience_needs(lines)
        main_questions = self._pick_main_questions(lines)
        key_themes = self._extract_key_themes(lines, request.topic)
        scope_includes = self._build_scope_includes(discovery_bundle, lines)
        scope_excludes = self._build_scope_excludes(request)
        sequence_logic = self._build_sequence_logic(request, key_themes)
        structure_options = self._build_structure_options(request)
        evidence_examples = self._build_evidence_examples(lines)
        notes = self._build_notes(lines)

        if request.depth == "introductory":
            book_purpose = "explain"
        elif request.depth == "intermediate":
            book_purpose = "explain and guide practice"
        else:
            book_purpose = "explain, deepen, and extend practice"

        core_idea = (
            f"A {request.tone} book for {request.audience} that teaches "
            f"{request.topic} with an appropriate scope and sequence."
        )

        return PlanningContext(
            book_purpose=book_purpose,
            audience_needs=audience_needs,
            core_idea=core_idea,
            main_questions=main_questions,
            scope_includes=scope_includes,
            scope_excludes=scope_excludes,
            key_themes=key_themes,
            sequence_logic=sequence_logic,
            structure_options=structure_options,
            evidence_examples=evidence_examples,
            notes=notes,
        )