from __future__ import annotations

from researcher.nodes.assemble_research_packet import AssembleResearchPacketNode
from researcher.nodes.build_research_task import BuildResearchTaskNode
from researcher.nodes.discover_sources import DiscoverSourcesNode
from researcher.nodes.extract_evidance import ExtractEvidenceNode
from researcher.nodes.fetch_sources import FetchSourcesNode
from researcher.nodes.followup_research import FollowupResearchNode
from researcher.nodes.inject_user_documents import InjectUserDocumentsNode
from researcher.nodes.plan_queries import PlanQueriesNode
from researcher.nodes.reflect_on_research import ReflectOnResearchNode
from researcher.schemas import SourceDocument
from researcher.services.firecrawl_client import FirecrawlClient
from researcher.services.llm_structured import GroqStructuredLLM
from researcher.services.pdf_extractor import PDFExtractor
from researcher.services.tavily_client import TavilySearchClient
from researcher.services.web_extractor import WebExtractor
from researcher.state import ResearcherState
from researcher.validator import ResearchPacketValidator


class ResearcherWorkflow:
    """
    End-to-end orchestrator for the Researcher layer.

    Two execution modes controlled by ``web_research_enabled``:

    **PDF-only mode** (``web_research_enabled=False``, default when user PDFs
    are present):
        0. Inject user PDFs -> fetched_documents
        1. Build research task   (LLM - creates objective/scope)
        2. Extract evidence      (LLM - mines evidence from user PDFs)
        3. Assemble packet       (deterministic)
        4. Validate

    **Full web mode** (``web_research_enabled=True``, always used when no user
    PDFs are present, or when WRITERLM_FORCE_WEB_RESEARCH=1):
        0. [optional] Inject user PDFs -> fetched_documents
        1. Build research task
        2. Plan queries
        3. Discover sources  (Tavily)
        4. Fetch sources     (web / PDF / Firecrawl)
        5. Extract evidence
        6. Reflect -> optional bounded follow-up loop
        7. Assemble packet
        8. Validate
    """

    def __init__(
        self,
        *,
        llm: GroqStructuredLLM,
        tavily_client: TavilySearchClient | None,
        web_extractor: WebExtractor,
        pdf_extractor: PDFExtractor,
        firecrawl_client: FirecrawlClient | None = None,
        validator: ResearchPacketValidator | None = None,
        user_documents: list[SourceDocument] | None = None,
        web_research_enabled: bool = True,
    ) -> None:
        if web_research_enabled and tavily_client is None:
            raise ValueError("Tavily API key is required when web research is enabled.")

        self.web_research_enabled = web_research_enabled

        self.build_research_task_node = BuildResearchTaskNode(llm=llm)
        self.extract_evidence_node = ExtractEvidenceNode(llm=llm)
        self.assemble_research_packet_node = AssembleResearchPacketNode()
        self.validator = validator or ResearchPacketValidator()

        self.plan_queries_node: PlanQueriesNode | None = None
        self.discover_sources_node: DiscoverSourcesNode | None = None
        self.fetch_sources_node: FetchSourcesNode | None = None
        self.reflect_on_research_node: ReflectOnResearchNode | None = None
        self.followup_research_node: FollowupResearchNode | None = None

        if web_research_enabled:
            assert tavily_client is not None
            self.plan_queries_node = PlanQueriesNode(llm=llm)
            self.discover_sources_node = DiscoverSourcesNode(
                tavily_client=tavily_client,
            )
            self.fetch_sources_node = FetchSourcesNode(
                web_extractor=web_extractor,
                pdf_extractor=pdf_extractor,
                firecrawl_client=firecrawl_client,
            )
            self.reflect_on_research_node = ReflectOnResearchNode(llm=llm)
            self.followup_research_node = FollowupResearchNode(
                llm=llm,
                tavily_client=tavily_client,
                web_extractor=web_extractor,
                pdf_extractor=pdf_extractor,
                firecrawl_client=firecrawl_client,
            )

        # Optional: inject user-uploaded PDFs as pre-fetched sources.
        # None when no documents were provided (no-op path).
        self.inject_user_documents_node: InjectUserDocumentsNode | None = (
            InjectUserDocumentsNode(user_documents)
            if user_documents
            else None
        )

    def run(self, state: ResearcherState) -> ResearcherState:
        """
        Execute the Researcher workflow for one planner section.

        Routes to ``_run_pdf_only`` or ``_run_full_web`` based on
        ``self.web_research_enabled``.
        """
        # Step 0 (always): inject user-uploaded PDFs when available.
        if self.inject_user_documents_node is not None:
            state = self.inject_user_documents_node.run(state)

        if self.web_research_enabled:
            return self._run_full_web(state)
        return self._run_pdf_only(state)

    # ------------------------------------------------------------------
    # Private execution paths
    # ------------------------------------------------------------------

    def _run_pdf_only(self, state: ResearcherState) -> ResearcherState:
        """
        PDF-only path: build task -> extract evidence from injected docs ->
        assemble.  No Tavily calls, no web fetching, no reflection loop.
        """
        state = self.build_research_task_node.run(state)
        if state.has_blocking_errors:
            return self._finalize_with_validation(state)

        if not state.fetched_documents:
            state.add_error(
                "PDF-only mode is active but no documents were injected. "
                "Check that inputs/pdfs/ contains readable PDF files."
            )
            return self._finalize_with_validation(state)

        state = self.extract_evidence_node.run(state)
        if state.has_blocking_errors:
            return self._finalize_with_validation(state)

        state = self.assemble_research_packet_node.run(state)
        return self._finalize_with_validation(state)

    def _run_full_web(self, state: ResearcherState) -> ResearcherState:
        """
        Full web path: plan queries -> Tavily -> fetch -> extract -> reflect ->
        optional follow-up -> assemble.
        """
        assert self.plan_queries_node is not None
        assert self.discover_sources_node is not None
        assert self.fetch_sources_node is not None
        assert self.reflect_on_research_node is not None
        assert self.followup_research_node is not None

        state = self.build_research_task_node.run(state)
        if state.has_blocking_errors:
            return self._finalize_with_validation(state)

        state = self.plan_queries_node.run(state)
        if state.has_blocking_errors:
            return self._finalize_with_validation(state)

        state = self.discover_sources_node.run(state)
        if state.has_blocking_errors:
            return self._finalize_with_validation(state)

        state = self.fetch_sources_node.run(state)
        if state.has_blocking_errors:
            return self._finalize_with_validation(state)

        state = self.extract_evidence_node.run(state)
        if state.has_blocking_errors:
            return self._finalize_with_validation(state)

        state = self.reflect_on_research_node.run(state)
        if state.has_blocking_errors:
            return self._finalize_with_validation(state)

        while not state.has_blocking_errors and state.should_continue_research:
            state = self.followup_research_node.run(state)
            if state.has_blocking_errors:
                break
            state = self.reflect_on_research_node.run(state)

        if not state.has_blocking_errors:
            state = self.assemble_research_packet_node.run(state)

        return self._finalize_with_validation(state)

    def _finalize_with_validation(self, state: ResearcherState) -> ResearcherState:
        """Run final validation when a packet exists."""
        self.validator.validate_state(state)
        return state
