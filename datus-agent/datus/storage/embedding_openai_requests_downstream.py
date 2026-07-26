# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Any, Sequence

from openai import BadRequestError

from datus.utils.loggings import get_logger

logger = get_logger(__name__)


def request_openai_embeddings(
    client: Any,
    *,
    model: str,
    dim: int | None,
    texts: Sequence[str],
    indices: Sequence[int],
    single_input_only: bool,
) -> dict[int, Any]:
    """Request compatible embeddings, falling back from a rejected batch to single inputs."""
    kwargs: dict[str, Any] = {"model": model}
    if model != "text-embedding-ada-002" and dim is not None:
        kwargs["dimensions"] = dim

    embeddings: dict[int, Any] = {}

    def request_individually() -> None:
        for text, index in zip(texts, indices):
            try:
                response = client.embeddings.create(input=text, **kwargs)
                if response.data:
                    embeddings[index] = response.data[0].embedding
            except BadRequestError:
                logger.error(
                    "Bad request when generating embedding: model=%s, input_index=%d, input_chars=%d",
                    model,
                    index,
                    len(text),
                )

    if single_input_only:
        request_individually()
        return embeddings

    try:
        response = client.embeddings.create(input=texts, **kwargs)
        embeddings.update({index: item.embedding for item, index in zip(response.data, indices)})
    except BadRequestError:
        if len(texts) == 1:
            raise
        logger.warning(
            "Embedding batch was rejected; retrying inputs individually: model=%s, text_count=%d",
            model,
            len(texts),
        )
        request_individually()
    return embeddings
