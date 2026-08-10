"""ALL Pydantic request/response models. This file is the API contract.

Two rules govern every model here (spec 4.1):
  - COMPUTED fields come from pandas. Always present, never Optional.
  - GENERATED fields come from the LLM. Always Optional, default None.

Mirror every change into frontend/src/api/types.ts by hand.
Serialization uses camelCase aliases; Python stays snake_case.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


# Models are defined during the 0:00-0:45 contract slice.
# Nothing else in the codebase may define a response shape.
