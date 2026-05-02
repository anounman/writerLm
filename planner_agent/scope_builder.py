import re
from collections import Counter
from typing import Any

from planner_agent.schemas import PlanningContext, UserBookRequest


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

    def _build_scope_includes(
        self,
        request: UserBookRequest,
        discovery_bundle: dict[str, Any],
        lines: list[str],
    ) -> list[str]:
        includes: list[str] = []

        if request.normalized_goals:
            includes.extend(request.normalized_goals)

        if request.project_based:
            includes.extend(
                [
                    "step-by-step implementation with working code at each stage",
                    "concrete code examples the reader can run and modify",
                    "diagrams and visuals explaining architecture and data flow",
                    "progressive project build where each chapter adds a new capability",
                    "common mistakes and debugging guidance for each implementation step",
                ]
            )

        if request.is_focused_beginner_guide:
            includes.extend(
                [
                    "only the minimum background needed to understand the topic",
                    "the core architecture and moving parts of a simple system",
                    "a practical path from mental model to first implementation",
                    "common beginner pitfalls, debugging tips, and pragmatic trade-offs",
                ]
            )
        else:
            bucket_to_label = {
                "topic_structure": "learning progression and structure patterns",
                "implementation_patterns": "practical implementation patterns",
                "audience_needs": "reader pain points and recurring learner questions",
                "common_pitfalls": "common mistakes and trade-offs",
            }

            for key, label in bucket_to_label.items():
                if key in discovery_bundle:
                    includes.append(label)

        deduped: list[str] = []
        seen = set()
        for item in includes:
            normalized = item.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        return deduped

    def _build_scope_excludes(self, request: UserBookRequest) -> list[str]:
        if request.is_focused_beginner_guide:
            return [
                "broad handbook-style coverage of every adjacent subtopic",
                "deep standalone surveys of large language models or generative AI",
                "advanced production scaling, governance, compliance, CI/CD, or enterprise operations",
                "ethics, legal, and societal chapters unless explicitly requested",
                "research frontiers, future directions, or state-of-the-art survey chapters",
                "broad collections of industry case studies unless explicitly requested",
                "advanced multimodal, agentic, or niche extensions unless explicitly requested",
            ]

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
        if request.project_based:
            logic = [
                "start with minimal setup and get the reader to a working (even trivial) version in chapter 1-2",
                "introduce concepts ONLY when the reader needs them for the next build step",
                "each chapter adds a new capability to the running project",
                "interleave theory and practice: explain a concept, then immediately implement it",
                "include code, examples, or diagrams in EVERY section",
                "end each chapter with a working milestone the reader can verify",
            ]
            if request.is_focused_beginner_guide:
                logic.append("reserve advanced extensions for optional later material only if requested")
            return logic

        if request.is_focused_beginner_guide:
            logic = [
                "start with why the topic matters and the reader's practical outcome",
                "include only the minimum background needed before using the core architecture",
                "introduce the system mental model early",
                "reach a practical implementation or walkthrough by the middle of the book",
                "keep theory in service of building and understanding the system",
                "reserve advanced extensions for optional later material only if requested",
            ]
            if key_themes:
                logic.append("group related beginner concepts into a short, implementation-first learning path")
            return logic

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
        if request.project_based:
            return [
                "project-driven: each chapter builds on the previous chapter's code",
                "setup → core build → enhance → test/debug → polish progression",
                "theory introduced just-in-time as the project demands it",
                "every section ends with runnable code or a verifiable result",
            ]

        if request.is_focused_beginner_guide:
            return [
                "focused guide from motivation to architecture to working prototype",
                "minimal background followed by hands-on implementation and debugging",
                "concepts in service of building a simple end-to-end system",
            ]

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
        if request.normalized_goals:
            goal_questions = [
                goal if goal.endswith("?") else f"How does the book help the reader {goal.rstrip('.')}?"
                for goal in request.normalized_goals[:6]
            ]
            main_questions = [*goal_questions, *main_questions][:8]
        key_themes = self._extract_key_themes(lines, request.topic)
        scope_includes = self._build_scope_includes(request, discovery_bundle, lines)
        scope_excludes = self._build_scope_excludes(request)
        sequence_logic = self._build_sequence_logic(request, key_themes)
        structure_options = self._build_structure_options(request)
        evidence_examples = self._build_evidence_examples(lines)
        notes = self._build_notes(lines)

        if request.project_based:
            book_purpose = "guide the reader through building a complete working project with code, examples, and diagrams at every step"
        elif request.is_focused_beginner_guide:
            book_purpose = "explain and help the reader build a simple working system"
        elif request.depth == "introductory":
            book_purpose = "explain"
        elif request.depth == "intermediate":
            book_purpose = "explain and guide practice"
        else:
            book_purpose = "explain, deepen, and extend practice"

        goal_summary = (
            " Goals: " + "; ".join(request.normalized_goals[:4]) + "."
            if request.normalized_goals
            else ""
        )

        project_desc = ""
        if request.project_based and request.running_project_description:
            project_desc = f" The reader builds: {request.running_project_description}."

        core_idea = (
            f"A {request.tone} book for {request.audience} that teaches "
            f"{request.topic} with an appropriate scope and sequence.{goal_summary}{project_desc}"
        )

        if request.is_focused_beginner_guide:
            notes = [
                "This request is a focused beginner practical guide, not a comprehensive handbook.",
                "Practical payoff should appear early and advanced topics should stay out unless explicitly requested.",
                *notes,
            ][:10]

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
