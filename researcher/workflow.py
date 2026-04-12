from __future__ import annotations

from researcher.nodes.assemble_research_packet import AssembleResearchPacketNode
from researcher.nodes.build_research_task import BuildResearchTaskNode
from researcher.nodes.discover_sources import DiscoverSourcesNode
from researcher.nodes.extract_evidance import ExtractEvidenceNode
from researcher.nodes.fetch_sources import FetchSourcesNode
from researcher.nodes.followup_research import FollowupResearchNode
from researcher.nodes.plan_queries import PlanQueriesNode
from researcher.nodes.reflect_on_research import ReflectOnResearchNode
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

    Flow:
    1. build research task
    2. plan queries
    3. discover sources
    4. fetch sources
    5. extract evidence
    6. reflect on research
    7. optional bounded follow-up research
    8. reflect again if needed
    9. assemble research packet
    10. validate final packet
    """

    def __init__(
        self,
        *,
        llm: GroqStructuredLLM,
        tavily_client: TavilySearchClient,
        web_extractor: WebExtractor,
        pdf_extractor: PDFExtractor,
        firecrawl_client: FirecrawlClient | None = None,
        validator: ResearchPacketValidator | None = None,
    ) -> None:
        self.build_research_task_node = BuildResearchTaskNode(llm=llm)
        self.plan_queries_node = PlanQueriesNode(llm=llm)
        self.discover_sources_node = DiscoverSourcesNode(
            tavily_client=tavily_client,
        )
        self.fetch_sources_node = FetchSourcesNode(
            web_extractor=web_extractor,
            pdf_extractor=pdf_extractor,
            firecrawl_client=firecrawl_client,
        )
        self.extract_evidence_node = ExtractEvidenceNode(llm=llm)
        self.reflect_on_research_node = ReflectOnResearchNode(llm=llm)
        self.followup_research_node = FollowupResearchNode(
            llm=llm,
            tavily_client=tavily_client,
            web_extractor=web_extractor,
            pdf_extractor=pdf_extractor,
            firecrawl_client=firecrawl_client,
        )
        self.assemble_research_packet_node = AssembleResearchPacketNode()
        self.validator = validator or ResearchPacketValidator()

    def run(self, state: ResearcherState) -> ResearcherState:
        """
        Execute the full Researcher workflow for one planner section.
        """
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
        """
        Run final validation when a packet exists.
        """
        self.validator.validate_state(state)
        return state
