from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aws_lambda_powertools.utilities.parser.envelopes.base import BaseEnvelope
from aws_lambda_powertools.utilities.parser.models import BedrockAgentEventModel

if TYPE_CHECKING:
    from aws_lambda_powertools.utilities.parser.types import Model

logger = logging.getLogger(__name__)


class BedrockAgentEnvelope(BaseEnvelope):
    """Bedrock Agent envelope to extract data within input_text key"""

    def parse(self, data: dict[str, Any] | Any | None, model: type[Model]) -> Model | None:
        """Parses data found with model provided

        Parameters
        ----------
        data : dict
            Lambda event to be parsed
        model : type[Model]
            Data model provided to parse after extracting data using envelope

        Returns
        -------
        Model | None
            Parsed detail payload with model provided
        """
        logger.debug(f"Parsing incoming data with Bedrock Agent model {BedrockAgentEventModel}")
        parsed_envelope: BedrockAgentEventModel = BedrockAgentEventModel.model_validate(data)
        logger.debug(f"Parsing event payload in `input_text` with {model}")
        return self._parse(data=parsed_envelope.input_text, model=model)
