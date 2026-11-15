"""Regression tests for DynamoDB-backed link deduplication in the processor.

Uses moto so the real ConditionExpressions run against a DynamoDB table.
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import boto3
import pytest
from botocore.exceptions import EndpointConnectionError
from moto import mock_dynamodb

from src.unfurl_processor.handler_async import (
    DEDUP_WINDOW_SECONDS,
    AsyncUnfurlHandler,
)
from src.unfurl_processor.url_utils import get_cache_key

TABLE_NAME = "unfurl-deduplication-test"
POST_A = "https://www.instagram.com/p/AAA111"
POST_B = "https://www.instagram.com/p/BBB222"


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("DEDUPLICATION_TABLE_NAME", TABLE_NAME)
    with mock_dynamodb():
        resource = boto3.resource("dynamodb")
        tbl = resource.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "url", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "url", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield tbl


@pytest.fixture
def handler(table):
    return AsyncUnfurlHandler()


def _event(*urls):
    return {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps(
                        {
                            "channel": "C1",
                            "message_ts": "1.0",
                            "unfurl_id": "u1",
                            "links": [{"url": u} for u in urls],
                        }
                    )
                }
            }
        ]
    }


def _entry(table, url):
    return table.get_item(Key={"url": get_cache_key(url)}).get("Item")


class TestClaim:
    def test_first_claim_wins_and_second_is_skipped(self, handler, table):
        assert handler._is_url_being_processed(POST_A) is False
        other = AsyncUnfurlHandler()
        assert other._is_url_being_processed(POST_A) is True

    def test_stale_claim_is_taken_over_despite_lazy_ttl(self, handler, table):
        # TTL sweeps can lag hours: a lingering entry past the window must not
        # block new processing.
        old = int(time.time()) - DEDUP_WINDOW_SECONDS - 5
        table.put_item(
            Item={
                "url": get_cache_key(POST_A),
                "processing_started": old,
                "ttl": old + DEDUP_WINDOW_SECONDS,
            }
        )
        assert handler._is_url_being_processed(POST_A) is False
        assert _entry(table, POST_A)["processing_started"] > old

    def test_fresh_claim_is_respected(self, handler, table):
        recent = int(time.time()) - DEDUP_WINDOW_SECONDS + 30
        table.put_item(
            Item={"url": get_cache_key(POST_A), "processing_started": recent}
        )
        assert handler._is_url_being_processed(POST_A) is True

    def test_connection_error_fails_open(self, handler):
        broken = MagicMock()
        broken.put_item.side_effect = EndpointConnectionError(endpoint_url="x")
        handler.deduplication_table = broken
        assert handler._is_url_being_processed(POST_A) is False


class TestRelease:
    def test_release_deletes_own_claim(self, handler, table):
        handler._is_url_being_processed(POST_A)
        handler._release_url(POST_A)
        assert _entry(table, POST_A) is None
        assert AsyncUnfurlHandler()._is_url_being_processed(POST_A) is False

    def test_release_keeps_claim_taken_over_by_another_invocation(self, handler, table):
        handler._is_url_being_processed(POST_A)
        # Our claim went stale and another invocation took it over.
        table.put_item(
            Item={
                "url": get_cache_key(POST_A),
                "processing_started": int(time.time()),
                "lock_token": "someone-else",
            }
        )
        handler._release_url(POST_A)
        assert _entry(table, POST_A)["lock_token"] == "someone-else"

    def test_release_without_claim_never_deletes(self, handler, table):
        # A skipped URL belongs to another invocation; releasing must not
        # delete their entry.
        AsyncUnfurlHandler()._is_url_being_processed(POST_A)
        assert handler._is_url_being_processed(POST_A) is True
        handler._release_url(POST_A)
        assert _entry(table, POST_A) is not None


class TestProcessEvent:
    @pytest.mark.asyncio
    async def test_skipped_link_does_not_shift_result_mapping(self, handler, table):
        # Another invocation holds POST_A, so only POST_B is processed. Its
        # result must be attributed to POST_B's original URL, not POST_A's.
        AsyncUnfurlHandler()._is_url_being_processed(POST_A)
        b_original = POST_B + "/?igsh=share"
        b_unfurl = {"title": "B"}

        with (
            patch.object(
                handler, "_get_secret", AsyncMock(return_value={"bot_token": "x"})
            ),
            patch.object(
                handler,
                "_process_single_link",
                AsyncMock(return_value=(POST_B, b_unfurl)),
            ) as process,
            patch.object(
                handler, "_send_unfurl_to_slack", AsyncMock(return_value=True)
            ) as send,
        ):
            result = await handler.process_event(
                _event(POST_A + "/", b_original), MagicMock()
            )

        assert result["statusCode"] == 200
        process.assert_awaited_once_with(POST_B)
        unfurls = send.await_args.args[4]
        assert unfurls == {b_original: b_unfurl}
        # The other invocation's claim on POST_A is untouched; ours is released.
        assert _entry(table, POST_A) is not None
        assert _entry(table, POST_B) is None

    @pytest.mark.asyncio
    async def test_claims_released_when_processing_raises(self, handler, table):
        with (
            patch.object(
                handler, "_get_secret", AsyncMock(return_value={"bot_token": "x"})
            ),
            patch.object(
                handler,
                "_process_single_link",
                AsyncMock(side_effect=RuntimeError("boom")),
            ),
            patch.object(handler, "_send_unfurl_to_slack", AsyncMock()) as send,
        ):
            result = await handler.process_event(_event(POST_A), MagicMock())

        assert result["statusCode"] == 200
        send.assert_not_awaited()
        assert _entry(table, POST_A) is None

    @pytest.mark.asyncio
    async def test_reshare_after_completion_is_processed(self, handler, table):
        with (
            patch.object(
                handler, "_get_secret", AsyncMock(return_value={"bot_token": "x"})
            ),
            patch.object(
                handler,
                "_process_single_link",
                AsyncMock(return_value=(POST_A, {"title": "A"})),
            ) as process,
            patch.object(
                handler, "_send_unfurl_to_slack", AsyncMock(return_value=True)
            ) as send,
        ):
            await handler.process_event(_event(POST_A), MagicMock())
            await handler.process_event(_event(POST_A), MagicMock())

        assert process.await_count == 2
        assert send.await_count == 2
