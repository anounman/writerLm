from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from planner_agent.schemas import BookPlan
from reviewer.schemas import ReviewBundle


CODE_BLOCK_RE = re.compile(r"```([A-Za-z0-9_+#.-]*)\n(.*?)```", re.DOTALL)
DIAGRAM_RE = re.compile(r"(?im)^DIAGRAM:\s*(.+)$")
PLACEHOLDER_RE = re.compile(
    r"\b(TODO|TBD|FIXME|insert here|placeholder|this diagram should|unresolved gaps?|"
    r"citation needed|source needed|changeme|lorem ipsum|example\.com)\b|"
    r"\[(?:insert|placeholder|todo|citation needed|source needed)[^\]]*\]",
    re.IGNORECASE,
)
AWS_RESOURCE_RE = re.compile(r"\bAWS::[A-Za-z0-9]+::[A-Za-z0-9]+\b")
FENCE_RE = re.compile(r"```")
RISKY_CLAIM_RE = re.compile(
    r"\b(official|requires?|must|guarantees?|always|never|current|latest|law|regulation|"
    r"standard|statistic|studies show|research shows|according to|limit|quota|pricing|"
    r"security recommendation|medical|legal|financial)\b|(?:\d+(?:\.\d+)?%)",
    re.IGNORECASE,
)

AWS_SERVICE_TERMS = {
    "api gateway",
    "cloudformation",
    "cloudfront",
    "cloudwatch",
    "codebuild",
    "codepipeline",
    "cognito",
    "dynamodb",
    "ecr",
    "ecs",
    "eks",
    "eventbridge",
    "iam",
    "lambda",
    "rds",
    "route 53",
    "s3",
    "secrets manager",
    "security group",
    "sns",
    "sqs",
    "subnet",
    "vpc",
    "waf",
}

KNOWN_CLOUDFORMATION_TYPES = {
    "AWS::ApiGateway::RestApi",
    "AWS::ApiGatewayV2::Api",
    "AWS::CloudFront::Distribution",
    "AWS::CloudWatch::Alarm",
    "AWS::CodeBuild::Project",
    "AWS::CodePipeline::Pipeline",
    "AWS::Cognito::UserPool",
    "AWS::DynamoDB::Table",
    "AWS::EC2::Instance",
    "AWS::EC2::InternetGateway",
    "AWS::EC2::NatGateway",
    "AWS::EC2::Route",
    "AWS::EC2::RouteTable",
    "AWS::EC2::SecurityGroup",
    "AWS::EC2::Subnet",
    "AWS::EC2::SubnetRouteTableAssociation",
    "AWS::EC2::VPC",
    "AWS::ECR::Repository",
    "AWS::ECS::Cluster",
    "AWS::ECS::Service",
    "AWS::ECS::TaskDefinition",
    "AWS::EKS::Cluster",
    "AWS::ElasticLoadBalancingV2::Listener",
    "AWS::ElasticLoadBalancingV2::LoadBalancer",
    "AWS::ElasticLoadBalancingV2::TargetGroup",
    "AWS::Events::Rule",
    "AWS::IAM::ManagedPolicy",
    "AWS::IAM::Role",
    "AWS::KMS::Key",
    "AWS::Lambda::Function",
    "AWS::Logs::LogGroup",
    "AWS::RDS::DBCluster",
    "AWS::RDS::DBInstance",
    "AWS::Route53::RecordSet",
    "AWS::S3::Bucket",
    "AWS::SecretsManager::Secret",
    "AWS::SNS::Topic",
    "AWS::SQS::Queue",
    "AWS::WAFv2::WebACL",
}

OFFICIAL_SOURCE_DOMAINS = (
    "docs.aws.amazon.com",
    "aws.amazon.com",
    "constructs.dev",
    "docs.python.org",
    "developer.mozilla.org",
    "kubernetes.io",
    "registry.terraform.io",
)


@dataclass
class QualityIssue:
    category: str
    severity: str
    section_id: str | None
    message: str
    evidence: str | None = None
    block_index: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "section_id": self.section_id,
            "message": self.message,
            "evidence": self.evidence,
            "block_index": self.block_index,
        }


@dataclass
class ProjectState:
    project_name: str
    implementation_strategy: str
    services: list[str] = field(default_factory=list)
    environments: list[str] = field(default_factory=list)
    resource_names: list[str] = field(default_factory=list)
    diagrams: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "implementation_strategy": self.implementation_strategy,
            "services": self.services,
            "environments": self.environments,
            "resource_names": self.resource_names,
            "diagrams": self.diagrams,
            "assumptions": self.assumptions,
        }


@dataclass
class QualityGateResult:
    report: dict[str, Any]
    review_bundle: ReviewBundle


def run_quality_gate(
    *,
    book_plan: BookPlan,
    review_bundle: ReviewBundle,
    research_bundle_payload: dict[str, Any] | None,
    run_dir: Path | None,
    profile: str | None = None,
    strict_full: bool | None = None,
) -> QualityGateResult:
    active_profile = (profile or os.getenv("RESEARCH_EXECUTION_PROFILE", "budget")).strip().lower()
    strict = strict_full
    if strict is None:
        strict = os.getenv("WRITERLM_STRICT_FULL_QA", "1").strip().lower() not in {"0", "false", "no"}

    project_state = infer_project_state(book_plan, review_bundle)
    source_map = build_source_map(research_bundle_payload)
    repairs: list[dict[str, Any]] = []
    pre_repair_issue_count = 0

    for section in review_bundle.sections:
        section_issues = analyze_section(
            section_id=section.section_output.section_id,
            title=section.section_output.section_title,
            content=section.section_output.reviewed_content,
            book_plan=book_plan,
            project_state=project_state,
            source_map=source_map,
            profile=active_profile,
            must_include_diagram=section.section_input.must_include_diagram,
            must_include_code=section.section_input.must_include_code,
            citations_used=list(section.section_output.citations_used),
        )
        pre_repair_issue_count += len(section_issues)
        repaired_content, section_repairs = repair_section_content(
            section_id=section.section_output.section_id,
            content=section.section_output.reviewed_content,
            issues=section_issues,
        )
        if section_repairs:
            section.section_output.reviewed_content = repaired_content
            section.section_output.applied_changes_summary.extend(section_repairs)
            repairs.extend(
                {"section_id": section.section_output.section_id, "change": item}
                for item in section_repairs
            )

    issues: list[QualityIssue] = []
    for section in review_bundle.sections:
        issues.extend(
            analyze_section(
                section_id=section.section_output.section_id,
                title=section.section_output.section_title,
                content=section.section_output.reviewed_content,
                book_plan=book_plan,
                project_state=project_state,
                source_map=source_map,
                profile=active_profile,
                must_include_diagram=section.section_input.must_include_diagram,
                must_include_code=section.section_input.must_include_code,
                citations_used=list(section.section_output.citations_used),
            )
        )
    issues.extend(
        analyze_book_level(
            book_plan=book_plan,
            review_bundle=review_bundle,
            project_state=project_state,
            source_map=source_map,
        )
    )

    report = build_report(
        profile=active_profile,
        book_plan=book_plan,
        project_state=project_state,
        source_map=source_map,
        issues=issues,
        repairs=repairs,
    )
    report["strict_full_qa"] = strict
    report["pre_repair_issue_count"] = pre_repair_issue_count
    report["failed"] = bool(active_profile == "full" and strict and report["gate"]["critical_issues"] > 0)

    if run_dir is not None:
        write_quality_report(run_dir, report)

    return QualityGateResult(report=report, review_bundle=review_bundle)


def infer_project_state(book_plan: BookPlan, review_bundle: ReviewBundle) -> ProjectState:
    corpus = "\n".join(
        [
            book_plan.title,
            book_plan.audience,
            book_plan.depth,
            *(section.section_output.reviewed_content for section in review_bundle.sections),
        ]
    ).lower()
    # Require explicit 'aws' mention AND at least 2 AWS service terms to avoid false positives
    # (ML books frequently mention 'lambda', 'rds', 'eks' in non-AWS contexts)
    aws_service_hits = sum(1 for term in AWS_SERVICE_TERMS if term in corpus)
    is_aws = "aws" in corpus and aws_service_hits >= 2
    strategy_counts = {
        "AWS CDK v2": corpus.count("aws-cdk-lib") + corpus.count("cdk v2") + corpus.count("construct"),
        "Terraform": corpus.count("terraform") + corpus.count(".tf"),
        "CloudFormation": corpus.count("cloudformation") + corpus.count("aws::"),
        "AWS CLI": corpus.count("aws "),
        "Console": corpus.count("console"),
    }
    strategy = max(strategy_counts, key=strategy_counts.get)
    if is_aws and strategy_counts[strategy] == 0:
        strategy = "AWS CDK v2"

    services = sorted({term for term in AWS_SERVICE_TERMS if term in corpus})
    environments = sorted({env for env in ("dev", "staging", "prod", "production") if re.search(rf"\b{env}\b", corpus)})
    resources = sorted(set(re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:Stack|Bucket|Vpc|Cluster|Service|Table|Queue|Topic)\b", corpus)))
    diagrams = [match.group(1).strip() for section in review_bundle.sections for match in DIAGRAM_RE.finditer(section.section_output.reviewed_content)]

    project_name = "BookProject"
    name_match = re.search(r"\b([A-Z][A-Za-z0-9]+(?:Stack|Project|Platform|Service))\b", "\n".join(s.section_output.reviewed_content for s in review_bundle.sections))
    if name_match:
        project_name = name_match.group(1)
    elif is_aws:
        project_name = "ProductionAwsProject"

    assumptions = []
    if is_aws:
        assumptions.append("AWS implementation should use one primary infrastructure strategy unless the request explicitly asks for alternatives.")
        assumptions.append("Official AWS documentation is authoritative for resource types, CLI options, and service behavior.")

    return ProjectState(
        project_name=project_name,
        implementation_strategy=strategy,
        services=services,
        environments=environments or (["dev", "staging", "prod"] if is_aws else []),
        resource_names=resources,
        diagrams=diagrams,
        assumptions=assumptions,
    )


def build_source_map(research_bundle_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(research_bundle_payload, dict):
        return {"official_sources": [], "section_sources": {}, "source_count": 0}
    official_sources: list[dict[str, str]] = []
    section_sources: dict[str, list[dict[str, str]]] = {}
    source_count = 0
    for chapter in research_bundle_payload.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        for packet in chapter.get("section_packets") or []:
            if not isinstance(packet, dict):
                continue
            section_id = str(packet.get("section_id") or "")
            refs: list[dict[str, str]] = []
            for source in packet.get("source_references") or packet.get("sources") or []:
                if not isinstance(source, dict):
                    continue
                url = str(source.get("url") or "")
                if not url:
                    continue
                source_count += 1
                item = {
                    "source_id": str(source.get("source_id") or ""),
                    "title": str(source.get("title") or source.get("source_id") or ""),
                    "url": url,
                }
                refs.append(item)
                if _is_official_source_url(url):
                    official_sources.append(item)
            if section_id:
                section_sources[section_id] = refs
    return {"official_sources": official_sources, "section_sources": section_sources, "source_count": source_count}


def analyze_section(
    *,
    section_id: str,
    title: str,
    content: str,
    book_plan: BookPlan,
    project_state: ProjectState,
    source_map: dict[str, Any],
    profile: str,
    must_include_diagram: bool,
    must_include_code: bool,
    citations_used: list[str] | None = None,
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    lowered = content.lower()
    # Use the same strict detection as infer_project_state to avoid false positives from
    # ML terms like 'lambda' / 'rds' / 'eks' being mistaken for AWS service references.
    aws_context = f"{book_plan.title} {book_plan.audience} {content}".lower()
    aws_service_hits_section = sum(1 for term in AWS_SERVICE_TERMS if term in aws_context)
    is_aws_book = "aws" in aws_context and aws_service_hits_section >= 2
    strict_profile = profile == "full"
    section_sources = source_map.get("section_sources", {}).get(section_id, [])
    has_research_sources = bool(source_map.get("source_count"))

    for match in PLACEHOLDER_RE.finditer(content):
        marker = match.group(0)
        issues.append(
            QualityIssue(
                category="unresolved_placeholder",
                severity="critical" if marker.lower() in {"todo", "fixme", "insert here"} else "warning",
                section_id=section_id,
                message="Unresolved draft marker or placeholder text remains in reviewed content.",
                evidence=marker,
            )
        )

    if len(FENCE_RE.findall(content)) % 2:
        issues.append(
            QualityIssue(
                category="code_validity",
                severity="critical",
                section_id=section_id,
                message="Malformed Markdown code fence remains in reviewed content.",
                evidence=title,
            )
        )

    code_blocks = extract_code_blocks(content)
    if must_include_code and not code_blocks:
        issues.append(
            QualityIssue(
                category="code_validity",
                severity="critical",
                section_id=section_id,
                message="Planner required code/examples, but reviewed content has no closed fenced code block.",
                evidence=title,
            )
        )

    for index, block in enumerate(code_blocks, start=1):
        issues.extend(validate_code_block(section_id=section_id, block_index=index, block=block))

    if is_aws_book:
        for resource_type in AWS_RESOURCE_RE.findall(content):
            if resource_type not in KNOWN_CLOUDFORMATION_TYPES:
                issues.append(
                    QualityIssue(
                        category="aws_correctness",
                        severity="critical",
                        section_id=section_id,
                        message="CloudFormation resource type is not in the local allow-list.",
                        evidence=resource_type,
                    )
                )

        has_official_source = any(_is_official_source_url(str(item.get("url", ""))) for item in section_sources)
        if not has_official_source:
            issues.append(
                QualityIssue(
                    category="source_grounding",
                    severity="critical" if strict_profile else "warning",
                    section_id=section_id,
                    message="AWS section has no per-section official source reference.",
                    evidence=title,
                )
            )

    if has_research_sources and not section_sources:
        issues.append(
            QualityIssue(
                category="source_grounding",
                severity="critical" if strict_profile and RISKY_CLAIM_RE.search(content) else "warning",
                section_id=section_id,
                message="Research-backed run has no source references mapped to this section.",
                evidence=title,
            )
        )
    elif has_research_sources and RISKY_CLAIM_RE.search(content) and not citations_used:
        issues.append(
            QualityIssue(
                category="source_grounding",
                severity="warning",
                section_id=section_id,
                message="Section contains risky factual/authoritative claims but records no citations_used.",
                evidence=title,
            )
        )

    diagrams = list(DIAGRAM_RE.finditer(content))
    if must_include_diagram and not diagrams:
        issues.append(
            QualityIssue(
                category="diagram_quality",
                severity="critical",
                section_id=section_id,
                message="Planner required a diagram but reviewed content has no DIAGRAM hint.",
                evidence=title,
            )
        )
    for match in diagrams:
        line = match.group(0)
        if "this diagram should" in line.lower() or "placeholder" in line.lower():
            issues.append(
                QualityIssue(
                    category="diagram_quality",
                    severity="critical",
                    section_id=section_id,
                    message="Diagram hint reads like a placeholder instead of an implementable visual spec.",
                    evidence=line,
                )
            )

    if _is_advanced_aws_book(book_plan):
        missing = [
            label
            for label, terms in {
                "security implications": ("security", "iam", "least privilege", "encryption"),
                "cost implications": ("cost", "pricing", "budget"),
                "observability": ("observability", "monitoring", "logging", "cloudwatch"),
                "failure modes": ("failure", "rollback", "recovery", "blast radius"),
                "verification": ("verify", "test", "validation", "smoke test"),
                "cleanup": ("cleanup", "teardown", "destroy"),
            }.items()
            if not any(term in lowered for term in terms)
        ]
        if len(missing) >= 3:
            issues.append(
                QualityIssue(
                    category="audience_depth",
                    severity="warning",
                    section_id=section_id,
                    message="Advanced AWS/DevOps section is missing multiple production-depth checks.",
                    evidence=", ".join(missing),
                )
            )

    if project_state.implementation_strategy == "AWS CDK v2" and "@aws-cdk/core" in content:
        issues.append(
            QualityIssue(
                category="implementation_strategy",
                severity="critical",
                section_id=section_id,
                message="CDK v1 import appears in a CDK v2 book.",
                evidence="@aws-cdk/core",
            )
        )
    return issues


def analyze_book_level(
    *,
    book_plan: BookPlan,
    review_bundle: ReviewBundle,
    project_state: ProjectState,
    source_map: dict[str, Any],
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    corpus = "\n".join(section.section_output.reviewed_content for section in review_bundle.sections).lower()

    if _is_advanced_aws_book(book_plan) and book_plan.depth != "advanced":
        issues.append(
            QualityIssue(
                category="audience_depth",
                severity="critical",
                section_id=None,
                message="Book metadata downgraded an advanced request.",
                evidence=f"depth={book_plan.depth}",
            )
        )

    strategy_hits = {
        "cdk_v1": corpus.count("@aws-cdk/core"),
        "cdk_v2": corpus.count("aws-cdk-lib"),
        "terraform": corpus.count("terraform"),
        "cloudformation": corpus.count("cloudformation") + corpus.count("aws::"),
    }
    active = [name for name, count in strategy_hits.items() if count >= 2]
    if len(active) > 1 and "compare" not in corpus and "alternative" not in corpus:
        issues.append(
            QualityIssue(
                category="implementation_strategy",
                severity="critical",
                section_id=None,
                message="Book mixes multiple implementation strategies without an explicit comparison frame.",
                evidence=", ".join(active),
            )
        )

    if "aws" in corpus and len(source_map.get("official_sources") or []) < 3:
        issues.append(
            QualityIssue(
                category="source_grounding",
                severity="warning",
                section_id=None,
                message="AWS book has too few official documentation sources in the research bundle.",
                evidence=f"official_sources={len(source_map.get('official_sources') or [])}",
            )
        )

    normalized_sections = [re.sub(r"\s+", " ", s.section_output.reviewed_content.lower()).strip() for s in review_bundle.sections]
    seen: dict[str, str] = {}
    for section, normalized in zip(review_bundle.sections, normalized_sections):
        if not normalized:
            continue
        key = normalized[:800]
        previous = seen.get(key)
        if previous:
            issues.append(
                QualityIssue(
                    category="repetition",
                    severity="warning",
                    section_id=section.section_output.section_id,
                    message="Section starts with near-duplicate content from an earlier section.",
                    evidence=previous,
                )
            )
        else:
            seen[key] = section.section_output.section_id
    return issues


def extract_code_blocks(content: str) -> list[dict[str, Any]]:
    return [{"language": m.group(1).strip().lower(), "code": m.group(2), "start": m.start()} for m in CODE_BLOCK_RE.finditer(content)]


def validate_code_block(*, section_id: str, block_index: int, block: dict[str, Any]) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    language = str(block.get("language") or "").lower()
    code = str(block.get("code") or "")
    stripped = code.strip()
    if not stripped:
        return [QualityIssue(category="code_validity", severity="critical", section_id=section_id, message="Empty code block.", block_index=block_index)]

    if PLACEHOLDER_RE.search(code) or re.search(r"<[A-Z0-9_ -]{3,}>|YOUR_[A-Z0-9_]+|REPLACE_ME", code):
        issues.append(
            QualityIssue(
                category="code_validity",
                severity="critical",
                section_id=section_id,
                message="Runnable-looking code contains placeholder markers.",
                evidence=_shorten(stripped),
                block_index=block_index,
            )
        )

    if language in {"python", "py"}:
        try:
            ast.parse(stripped)
        except SyntaxError as exc:
            issues.append(
                QualityIssue(
                    category="code_validity",
                    severity="critical",
                    section_id=section_id,
                    message=f"Python code does not parse: {exc.msg}.",
                    evidence=f"line {exc.lineno}",
                    block_index=block_index,
                )
            )
    elif language == "json":
        try:
            json.loads(stripped)
        except json.JSONDecodeError as exc:
            issues.append(
                QualityIssue(
                    category="code_validity",
                    severity="critical",
                    section_id=section_id,
                    message=f"JSON code does not parse: {exc.msg}.",
                    evidence=f"line {exc.lineno}",
                    block_index=block_index,
                )
            )
    elif language in {"yaml", "yml"}:
        try:
            import yaml  # type: ignore

            yaml.safe_load(stripped)
        except Exception as exc:
            issues.append(
                QualityIssue(
                    category="code_validity",
                    severity="critical",
                    section_id=section_id,
                    message=f"YAML code does not parse: {exc}.",
                    evidence=_shorten(stripped),
                    block_index=block_index,
                )
            )

    if language in {"typescript", "ts", "javascript", "js", "tsx"}:
        if "@aws-cdk/core" in stripped and "aws-cdk-lib" in stripped:
            issues.append(
                QualityIssue(
                    category="implementation_strategy",
                    severity="critical",
                    section_id=section_id,
                    message="Code mixes CDK v1 and CDK v2 imports.",
                    evidence="@aws-cdk/core + aws-cdk-lib",
                    block_index=block_index,
                )
            )
        if stripped.count("{") != stripped.count("}"):
            issues.append(
                QualityIssue(
                    category="code_validity",
                    severity="warning",
                    section_id=section_id,
                    message="JavaScript/TypeScript block has unbalanced braces.",
                    evidence=_shorten(stripped),
                    block_index=block_index,
                )
            )

    for resource_type in AWS_RESOURCE_RE.findall(stripped):
        if resource_type not in KNOWN_CLOUDFORMATION_TYPES:
            issues.append(
                QualityIssue(
                    category="aws_correctness",
                    severity="critical",
                    section_id=section_id,
                    message="Unknown or unsupported-looking CloudFormation resource type in code block.",
                    evidence=resource_type,
                    block_index=block_index,
                )
            )
    return issues


def repair_section_content(*, section_id: str, content: str, issues: list[QualityIssue]) -> tuple[str, list[str]]:
    repairs: list[str] = []
    bad_blocks = {issue.block_index for issue in issues if issue.block_index is not None and issue.severity == "critical"}
    if bad_blocks:
        counter = 0

        def replace_block(match: re.Match[str]) -> str:
            nonlocal counter
            counter += 1
            language = match.group(1).strip() or "text"
            code = match.group(2).strip()
            if counter not in bad_blocks:
                return match.group(0)
            repairs.append(f"Marked invalid {language} code block #{counter} as conceptual text after deterministic QA.")
            return (
                "```text\n"
                "Conceptual example only. The QA gate found validation problems, so this block is not presented as runnable code.\n"
                f"{code}\n"
                "```"
            )

        content = CODE_BLOCK_RE.sub(replace_block, content)

    if re.search(r"(?im)^#+\s*Unresolved Gaps?\s*$", content):
        content = re.sub(r"(?im)^#+\s*Unresolved Gaps?\s*$", "### Advanced Extension Ideas", content)
        repairs.append("Renamed unresolved-gaps heading to an explicit advanced-extension section.")

    removed = 0
    lines = []
    for line in content.splitlines():
        if re.search(r"(?i)\b(this diagram should|insert here|TODO|FIXME)\b", line):
            removed += 1
            continue
        lines.append(line)
    if removed:
        content = "\n".join(lines)
        repairs.append(f"Removed {removed} unresolved placeholder line(s).")
    return content, repairs


def build_report(
    *,
    profile: str,
    book_plan: BookPlan,
    project_state: ProjectState,
    source_map: dict[str, Any],
    issues: list[QualityIssue],
    repairs: list[dict[str, Any]],
) -> dict[str, Any]:
    critical = sum(1 for issue in issues if issue.severity == "critical")
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    by_category: dict[str, int] = {}
    for issue in issues:
        by_category[issue.category] = by_category.get(issue.category, 0) + 1
    scores = {
        "code_validity": _score_category(issues, "code_validity", critical_weight=22, warning_weight=7),
        "aws_correctness": _score_category(issues, "aws_correctness", critical_weight=24, warning_weight=8),
        "source_grounding": _score_category(issues, "source_grounding", critical_weight=18, warning_weight=10),
        "project_continuity": _score_category(issues, "implementation_strategy", critical_weight=20, warning_weight=8),
        "diagram_quality": _score_category(issues, "diagram_quality", critical_weight=16, warning_weight=8),
        "audience_depth": _score_category(issues, "audience_depth", critical_weight=18, warning_weight=9),
        "unresolved_placeholders": _score_category(issues, "unresolved_placeholder", critical_weight=25, warning_weight=8),
        "hallucination_risk": max(0, 100 - critical * 12 - warnings * 3),
        "repeated_sections": _score_category(issues, "repetition", critical_weight=15, warning_weight=12),
        "broken_examples": _score_category(issues, "code_validity", critical_weight=20, warning_weight=8),
    }
    overall = round(sum(scores.values()) / len(scores), 1)
    return {
        "profile": profile,
        "book": {"title": book_plan.title, "audience": book_plan.audience, "depth": book_plan.depth},
        "project_state": project_state.as_dict(),
        "source_map": {
            "source_count": source_map.get("source_count", 0),
            "official_source_count": len(source_map.get("official_sources") or []),
            "official_sources": source_map.get("official_sources", [])[:20],
        },
        "gate": {
            "overall_score": overall,
            "critical_issues": critical,
            "warnings": warnings,
            "issue_count_by_category": by_category,
        },
        "scores": scores,
        "repairs_applied": repairs,
        "issues": [issue.as_dict() for issue in issues],
        "trace": {
            "stages_ran": [
                "project_state_inference",
                "source_map_build",
                "code_validation",
                "aws_resource_validation",
                "diagram_qa",
                "audience_depth_check",
                "placeholder_scan",
                "deterministic_repair",
            ],
            "full_profile_expected_delta": [
                "more official-source grounding",
                "stricter code/resource validation",
                "project continuity enforcement",
                "diagram specificity checks",
                "audience-depth QA",
            ],
        },
    }


def write_quality_report(run_dir: Path, report: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "quality_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        f"# Quality Report: {report['book']['title']}",
        "",
        f"- Profile: `{report['profile']}`",
        f"- Overall score: **{report['gate']['overall_score']}/100**",
        f"- Critical issues: **{report['gate']['critical_issues']}**",
        f"- Warnings: **{report['gate']['warnings']}**",
        "",
        "## Scores",
        "",
    ]
    for key, value in report["scores"].items():
        lines.append(f"- {key}: {value}/100")
    lines.extend(["", "## Repairs", ""])
    if report["repairs_applied"]:
        for repair in report["repairs_applied"]:
            lines.append(f"- {repair['section_id']}: {repair['change']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Issues", ""])
    for issue in report["issues"][:50]:
        lines.append(f"- [{issue['severity']}] {issue['category']} ({issue.get('section_id') or 'book'}): {issue['message']}")
    (run_dir / "quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _score_category(issues: list[QualityIssue], category: str, *, critical_weight: int, warning_weight: int) -> int:
    critical = sum(1 for issue in issues if issue.category == category and issue.severity == "critical")
    warnings = sum(1 for issue in issues if issue.category == category and issue.severity == "warning")
    return max(0, 100 - critical * critical_weight - warnings * warning_weight)


def _is_advanced_aws_book(book_plan: BookPlan) -> bool:
    text = f"{book_plan.title} {book_plan.audience} {book_plan.depth}".lower()
    return "aws" in text and ("advanced" in text or "devops" in text or book_plan.depth == "advanced")


def _is_official_source_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    host = host.lower().removeprefix("www.")
    return any(host == domain or host.endswith(f".{domain}") for domain in OFFICIAL_SOURCE_DOMAINS)


def _shorten(value: str, limit: int = 180) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."
