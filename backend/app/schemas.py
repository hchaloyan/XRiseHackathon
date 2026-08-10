"""ALL Pydantic request/response models. This file is the API contract.

Two rules govern every model here (spec 4.1):
  - COMPUTED fields come from pandas. Always present, never Optional.
  - GENERATED fields come from the LLM. Always Optional, default None.

Mirror every change into frontend/src/api/types.ts by hand.
Serialization uses camelCase aliases; Python stays snake_case.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import List, Optional


class ApiModel(BaseModel):
    """Base: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


# Models are defined during the 0:00-0:45 contract slice.
# Nothing else in the codebase may define a response shape.

# ===== KNOWLEDGE BASE =====

# Spec 7.1: the fixed redirect for queries the SOP corpus cannot answer.
OFF_TOPIC_MESSAGE = (
    "I answer from SOPs and manuals. For line data, click any row below."
)


class SearchRequest(ApiModel):
    query: str


class SOPResult(ApiModel):
    """All COMPUTED - retrieval only, no model involved."""

    id: str  # chunk id, e.g. "SOP-002#3"
    doc_id: str
    title: str
    section: str
    content: str
    distance: float


class SearchResponse(ApiModel):
    query: str
    results: List[SOPResult]
    # Non-null only when nothing cleared the similarity floor.
    fallback_message: Optional[str] = None


class ExplainRequest(ApiModel):
    query: str
    sop_ids: List[str]  # chunk ids returned by /api/search


class ExplainStep(ApiModel):
    action: str
    why: str


class ExplainResponse(ApiModel):
    query: str
    sources: List[str]  # doc_ids actually shown to the model - COMPUTED
    # GENERATED below: all Optional, all None when the model fails or times out.
    explanation: Optional[str] = None
    steps: Optional[List[ExplainStep]] = None
    common_mistake: Optional[str] = None
    estimated_minutes: Optional[int] = None


# JSON schema handed to Ollama's `format` param. Every array carries explicit
# minItems/maxItems (spec 8).
EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "steps": {
            "type": "array",
            "minItems": 2,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["action", "why"],
            },
        },
        "common_mistake": {"type": "string"},
        "estimated_minutes": {"type": "integer"},
    },
    "required": ["explanation", "steps", "common_mistake", "estimated_minutes"],
}


# ===== ROOT CAUSE =====

class RootCauseItem(ApiModel):
    cause: str
    probability: str  # "high" | "medium" | "low"
    evidence: str