# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Downstream regressions for OpenAI-compatible embeddings."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openai import BadRequestError

from datus.storage.embedding_openai import OpenAIEmbeddings
from datus.utils.exceptions import DatusException


@pytest.mark.ci
def test_single_input_only_configuration() -> None:
    assert OpenAIEmbeddings().single_input_only is False
    assert OpenAIEmbeddings(single_input_only=True).single_input_only is True


@pytest.mark.ci
def test_custom_openai_compatible_model_uses_configured_dims() -> None:
    emb = OpenAIEmbeddings(name="jina-embeddings-v3", dim=1024)
    assert emb.ndims() == 1024


@pytest.mark.ci
def test_unknown_model_without_dims_requests_explicit_dims() -> None:
    emb = OpenAIEmbeddings(name="nonexistent-model")
    with pytest.raises(DatusException, match="Set dim_size"):
        emb.ndims()


class TestGenerateEmbeddings:
    @staticmethod
    def _response(embedding):
        return SimpleNamespace(data=[SimpleNamespace(embedding=embedding)])

    @pytest.mark.ci
    def test_single_input_only_sends_strings_and_preserves_positions(self):
        emb = OpenAIEmbeddings(name="jina-embeddings-v3", dim=2, single_input_only=True)
        client = MagicMock()
        client.embeddings.create.side_effect = [self._response([1.0, 2.0]), self._response([3.0, 4.0])]
        emb.__dict__["_openai_client"] = client

        result = emb.generate_embeddings(["first", "", "second"])

        assert result == [[1.0, 2.0], None, [3.0, 4.0]]
        assert client.embeddings.create.call_args_list[0].kwargs == {
            "input": "first",
            "model": "jina-embeddings-v3",
            "dimensions": 2,
        }
        assert client.embeddings.create.call_args_list[1].kwargs["input"] == "second"

    @pytest.mark.ci
    def test_single_input_only_keeps_other_results_when_one_request_is_rejected(self):
        emb = OpenAIEmbeddings(name="jina-embeddings-v3", dim=2, single_input_only=True)
        client = MagicMock()
        response = httpx.Response(400, request=httpx.Request("POST", "https://example.test/v1/embeddings"))
        client.embeddings.create.side_effect = [
            self._response([1.0, 2.0]),
            BadRequestError("bad input", response=response, body={}),
            self._response([5.0, 6.0]),
        ]
        emb.__dict__["_openai_client"] = client

        assert emb.generate_embeddings(["first", "bad", "third"]) == [[1.0, 2.0], None, [5.0, 6.0]]

    @pytest.mark.ci
    def test_batch_bad_request_retries_individually_and_keeps_valid_results(self):
        emb = OpenAIEmbeddings(name="jina-embeddings-v3", dim=2)
        client = MagicMock()
        response = httpx.Response(400, request=httpx.Request("POST", "https://example.test/v1/embeddings"))
        client.embeddings.create.side_effect = [
            BadRequestError("bad batch", response=response, body={}),
            self._response([1.0, 2.0]),
            BadRequestError("bad input", response=response, body={}),
            self._response([5.0, 6.0]),
        ]
        emb.__dict__["_openai_client"] = client

        assert emb.generate_embeddings(["first", "bad", "third"]) == [[1.0, 2.0], None, [5.0, 6.0]]
        assert client.embeddings.create.call_args_list[0].kwargs["input"] == ["first", "bad", "third"]
        assert [call.kwargs["input"] for call in client.embeddings.create.call_args_list[1:]] == [
            "first",
            "bad",
            "third",
        ]

    @pytest.mark.ci
    def test_empty_inputs_do_not_call_api(self):
        emb = OpenAIEmbeddings(single_input_only=True)
        client = MagicMock()
        emb.__dict__["_openai_client"] = client

        assert emb.generate_embeddings(["", None]) == [None, None]
        client.embeddings.create.assert_not_called()
