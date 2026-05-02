from __future__ import annotations

from .schemas import (
    CodeSnippet,
    CoverageSignal,
    DiagramSuggestion,
    ExampleNote,
    FlowStep,
    ImplementationStep,
    SectionNoteArtifact,
    SectionSynthesisInput,
    SourceTraceItem,
    SupportingFact,
    SynthesisStatus,
)


def build_deterministic_section_note(
    section_input: SectionSynthesisInput,
) -> SectionNoteArtifact:
    supporting_facts = [
        SupportingFact(
            fact=item,
            source_ids=section_input.available_source_ids[:1],
        )
        for item in section_input.evidence_items[:6]
    ]

    examples = [
        ExampleNote(
            example=item,
            source_ids=section_input.available_source_ids[:1],
        )
        for item in _pick_example_items(section_input)
    ]

    core_points = (
        section_input.key_concepts[:5]
        or section_input.evidence_items[:5]
        or [section_input.section_objective]
    )

    code_snippets = []
    if section_input.must_include_code or _looks_implementation_heavy(section_input):
        code_snippets.append(_fallback_code_snippet(section_input))

    diagram_suggestions = []
    if section_input.must_include_diagram or _looks_visual(section_input):
        diagram_suggestions.append(_fallback_diagram_suggestion(section_input, core_points))

    implementation_steps = _implementation_steps(section_input)

    status = (
        SynthesisStatus.READY
        if section_input.coverage_signal == CoverageSignal.SUFFICIENT
        else SynthesisStatus.PARTIAL
    )

    unresolved_gaps = list(section_input.open_questions[:3])
    if section_input.coverage_signal != CoverageSignal.SUFFICIENT and not unresolved_gaps:
        unresolved_gaps.append(
            "Some implementation details may need verification against the final library versions."
        )

    return SectionNoteArtifact(
        section_id=section_input.section_id,
        section_title=section_input.section_title,
        section_objective=section_input.section_objective,
        synthesis_status=status,
        coverage_signal=section_input.coverage_signal,
        central_thesis=(
            f"{section_input.section_title} should help the reader move from "
            "the concept to a small working implementation."
        ),
        core_points=core_points,
        supporting_facts=supporting_facts,
        examples=examples,
        code_snippets=code_snippets,
        diagram_suggestions=diagram_suggestions,
        implementation_steps=implementation_steps,
        must_include_code=section_input.must_include_code,
        must_include_diagram=section_input.must_include_diagram,
        important_caveats=[
            "Start with the smallest working version before adding abstractions.",
            "Verify package names, API signatures, and model names against current documentation.",
        ],
        unresolved_gaps=unresolved_gaps,
        recommended_flow=[
            FlowStep(step_number=1, instruction="Introduce the idea through the running project."),
            FlowStep(step_number=2, instruction="Show the smallest practical implementation."),
            FlowStep(step_number=3, instruction="Explain the expected output and common mistakes."),
            FlowStep(step_number=4, instruction="Give the reader one short exercise."),
        ],
        writer_guidance=[
            "Keep theory short and connect it to the project milestone.",
            "Use the code snippet as a runnable teaching scaffold.",
            "Place diagrams before code when they explain flow or architecture.",
        ],
        allowed_citation_source_ids=list(section_input.available_source_ids),
        source_trace=[
            SourceTraceItem(
                note_element="deterministic_summary",
                source_ids=section_input.available_source_ids[:3],
            )
        ],
        reference_links=[
            item
            for item in section_input.source_references
            if item.url
        ][:5],
    )


def _pick_example_items(section_input: SectionSynthesisInput) -> list[str]:
    example_items = [
        item
        for item in section_input.evidence_items
        if "example" in item.lower() or "use" in item.lower()
    ]
    return (example_items or section_input.evidence_items[:2])[:3]


def _looks_implementation_heavy(section_input: SectionSynthesisInput) -> bool:
    text = " ".join(
        [
            section_input.section_title,
            section_input.section_objective,
            *section_input.key_concepts,
        ]
    ).lower()
    return any(
        token in text
        for token in ("build", "implement", "install", "configure", "code", "test", "setup")
    )


def _looks_visual(section_input: SectionSynthesisInput) -> bool:
    text = " ".join(
        [
            section_input.section_title,
            section_input.section_objective,
            *section_input.key_concepts,
        ]
    ).lower()
    return any(
        token in text
        for token in ("architecture", "pipeline", "flow", "process", "system", "strategy")
    )


def _fallback_code_snippet(section_input: SectionSynthesisInput) -> CodeSnippet:
    text = f"{section_input.section_title} {section_input.section_objective}".lower()
    title = section_input.section_title.replace('"', "'")

    if "virtual environment" in text or "project setup" in text:
        return CodeSnippet(
            language="bash",
            description="Create an isolated Python workspace for the RAG project.",
            code=(
                "mkdir rag-from-scratch\n"
                "cd rag-from-scratch\n"
                "python -m venv .venv\n"
                ".venv\\Scripts\\activate  # Windows PowerShell\n"
                "python -m pip install --upgrade pip\n"
                "python -c \"import sys; print(sys.executable)\"\n"
            ),
            source_ids=[],
        )

    if "install" in text or "libraries" in text:
        return CodeSnippet(
            language="bash",
            description="Install a small but practical dependency set for a local RAG prototype.",
            code=(
                "pip install langchain langchain-community faiss-cpu sentence-transformers python-dotenv\n"
                "pip freeze > requirements.txt\n"
                "python -c \"import faiss, dotenv; print('RAG dependencies ready')\"\n"
            ),
            source_ids=[],
        )

    if "api" in text or "llm" in text and "access" in text:
        return CodeSnippet(
            language="python",
            description="Load an API key from the environment without hard-coding secrets.",
            code=(
                "import os\n"
                "from dotenv import load_dotenv\n\n"
                "load_dotenv()\n"
                "api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('OPENAI_API_KEY')\n"
                "if not api_key:\n"
                "    raise RuntimeError('Set GOOGLE_API_KEY or OPENAI_API_KEY in .env')\n"
                "print('API key loaded safely:', bool(api_key))\n"
            ),
            source_ids=[],
        )

    if "load" in text and "document" in text:
        return CodeSnippet(
            language="python",
            description="Load plain-text documents from a local folder.",
            code=(
                "from pathlib import Path\n\n"
                "def load_documents(folder='docs'):\n"
                "    documents = []\n"
                "    for path in Path(folder).glob('*.txt'):\n"
                "        documents.append({'path': str(path), 'text': path.read_text(encoding='utf-8')})\n"
                "    return documents\n\n"
                "docs = load_documents()\n"
                "print(f'Loaded {len(docs)} documents')\n"
            ),
            source_ids=[],
        )

    if "recursive" in text and "split" in text:
        return CodeSnippet(
            language="python",
            description="Split text recursively using paragraph, sentence, and word boundaries.",
            code=(
                "def recursive_split(text, max_chars=500):\n"
                "    if len(text) <= max_chars:\n"
                "        return [text]\n"
                "    for separator in ['\\n\\n', '. ', ' ']:\n"
                "        parts = text.split(separator)\n"
                "        if len(parts) > 1:\n"
                "            chunks, current = [], ''\n"
                "            for part in parts:\n"
                "                candidate = (current + separator + part).strip()\n"
                "                if len(candidate) > max_chars and current:\n"
                "                    chunks.extend(recursive_split(current, max_chars))\n"
                "                    current = part\n"
                "                else:\n"
                "                    current = candidate\n"
                "            if current:\n"
                "                chunks.extend(recursive_split(current, max_chars))\n"
                "            return chunks\n"
                "    return [text[:max_chars], *recursive_split(text[max_chars:], max_chars)]\n"
            ),
            source_ids=[],
        )

    if "chunk" in text:
        return CodeSnippet(
            language="python",
            description="Create overlapping chunks so retrieval keeps nearby context.",
            code=(
                "def chunk_text(text, chunk_size=500, overlap=80):\n"
                "    chunks = []\n"
                "    start = 0\n"
                "    while start < len(text):\n"
                "        end = start + chunk_size\n"
                "        chunks.append(text[start:end])\n"
                "        start = max(end - overlap, start + 1)\n"
                "    return chunks\n\n"
                "sample = 'Retrieval augmented generation connects documents to model answers. ' * 20\n"
                "print(len(chunk_text(sample)))\n"
            ),
            source_ids=[],
        )

    if "embedding" in text:
        return CodeSnippet(
            language="python",
            description="Generate embeddings for chunks with a local sentence-transformer model.",
            code=(
                "from sentence_transformers import SentenceTransformer\n\n"
                "model = SentenceTransformer('all-MiniLM-L6-v2')\n"
                "chunks = ['RAG retrieves context.', 'Embeddings turn text into vectors.']\n"
                "vectors = model.encode(chunks, normalize_embeddings=True)\n"
                "print(vectors.shape)\n"
            ),
            source_ids=[],
        )

    if "faiss" in text or "vector store" in text:
        return CodeSnippet(
            language="python",
            description="Build a FAISS index from embedding vectors.",
            code=(
                "import faiss\n"
                "import numpy as np\n\n"
                "vectors = np.random.random((4, 384)).astype('float32')\n"
                "index = faiss.IndexFlatL2(vectors.shape[1])\n"
                "index.add(vectors)\n"
                "distances, ids = index.search(vectors[:1], k=2)\n"
                "print(ids[0].tolist())\n"
            ),
            source_ids=[],
        )

    if "save" in text and "index" in text:
        return CodeSnippet(
            language="python",
            description="Persist a FAISS index and the chunk metadata beside it.",
            code=(
                "import json\n"
                "import faiss\n\n"
                "faiss.write_index(index, 'rag.index')\n"
                "with open('chunks.json', 'w', encoding='utf-8') as file:\n"
                "    json.dump(chunks, file, indent=2)\n\n"
                "loaded_index = faiss.read_index('rag.index')\n"
                "print('Vectors in index:', loaded_index.ntotal)\n"
            ),
            source_ids=[],
        )

    if "retrieval" in text or "query" in text:
        return CodeSnippet(
            language="python",
            description="Retrieve the most relevant chunks for a user question.",
            code=(
                "def retrieve(question, embed_fn, index, chunks, k=3):\n"
                "    query_vector = embed_fn([question]).astype('float32')\n"
                "    distances, ids = index.search(query_vector, k)\n"
                "    return [chunks[i] for i in ids[0] if i != -1]\n\n"
                "context = retrieve('How does chunking affect RAG?', embed_fn, index, chunks)\n"
                "print('\\n---\\n'.join(context))\n"
            ),
            source_ids=[],
        )

    if "prompt" in text:
        return CodeSnippet(
            language="python",
            description="Build a grounded prompt that separates context from the user question.",
            code=(
                "def build_rag_prompt(question, context_chunks):\n"
                "    context = '\\n\\n'.join(context_chunks)\n"
                "    return f\"\"\"\n"
                "Use only the context below to answer.\n\n"
                "Context:\n{context}\n\n"
                "Question: {question}\n"
                "Answer with citations to the provided context when possible.\n"
                "\"\"\".strip()\n"
            ),
            source_ids=[],
        )

    if "evaluation" in text or "metric" in text or "faithfulness" in text:
        return CodeSnippet(
            language="python",
            description="Compute a simple retrieval hit-rate metric for a small evaluation set.",
            code=(
                "def hit_rate(results, expected_ids):\n"
                "    hits = 0\n"
                "    for retrieved_ids, expected in zip(results, expected_ids):\n"
                "        hits += int(any(item in retrieved_ids for item in expected))\n"
                "    return hits / max(len(expected_ids), 1)\n\n"
                "print(hit_rate([[1, 4, 5], [2, 3]], [{4}, {9}]))\n"
            ),
            source_ids=[],
        )

    if "streamlit" in text or "user interface" in text or "ui" in text:
        return CodeSnippet(
            language="python",
            description="Create a minimal Streamlit interface for asking questions.",
            code=(
                "import streamlit as st\n\n"
                "st.title('Local RAG Assistant')\n"
                "question = st.text_input('Ask a question about your documents')\n"
                "if question:\n"
                "    answer = rag_answer(question)\n"
                "    st.write(answer)\n"
            ),
            source_ids=[],
        )

    return CodeSnippet(
        language="python",
        description=f"Turn {section_input.section_title} into a small runnable checkpoint.",
        code=(
            "def checkpoint(name, result):\n"
            "    print(f'{name}: {result}')\n\n"
            f"checkpoint('{title}', 'small working version complete')\n"
        ),
        source_ids=[],
    )


def _fallback_diagram_suggestion(
    section_input: SectionSynthesisInput,
    core_points: list[str],
) -> DiagramSuggestion:
    return DiagramSuggestion(
        diagram_type=section_input.suggested_diagram_type or "flowchart",
        title=f"{section_input.section_title}: from idea to output",
        description=(
            "A simple learning map that connects the concept, the implementation step, "
            "the expected output, and the improvement loop."
        ),
        elements=(core_points[:4] or [
            "Concept",
            "Implementation",
            "Expected output",
            "Improve",
        ]),
    )


def _implementation_steps(section_input: SectionSynthesisInput) -> list[ImplementationStep]:
    if not (section_input.must_include_code or _looks_implementation_heavy(section_input)):
        return []

    return [
        ImplementationStep(
            step_number=1,
            action="Create the smallest working version",
            detail=f"Focus only on {section_input.section_title.lower()} before adding extra features.",
            has_code=True,
        ),
        ImplementationStep(
            step_number=2,
            action="Run and inspect the result",
            detail="Check the output manually before moving to the next abstraction.",
            has_code=False,
        ),
        ImplementationStep(
            step_number=3,
            action="Improve one behavior",
            detail="Change one parameter, input, or component and compare the result.",
            has_code=True,
        ),
    ]
