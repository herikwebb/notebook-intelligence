# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""Bounded wait + listener cleanup for run-ui-command round trips.

The frontend is the executor for UI commands. If the browser tab that
must answer disappears (reload, closed websocket), no response ever
arrives — the wait must time out instead of polling forever, and the
signal listener must be disconnected on every exit path so abandoned
waits can't leak callbacks.
"""

import asyncio

import pytest

from notebook_intelligence.api import ChatResponse


def _listeners(response: ChatResponse) -> list:
    return response.run_ui_command_response_signal._listeners


class TestWaitForRunUICommandResponse:
    def test_returns_result_and_disconnects_listener(self):
        response = ChatResponse()

        async def scenario():
            task = asyncio.ensure_future(
                ChatResponse.wait_for_run_ui_command_response(response, 'cb-1')
            )
            await asyncio.sleep(0)  # let the wait connect its listener
            assert len(_listeners(response)) == 1
            response.on_run_ui_command_response(
                {'callback_id': 'cb-1', 'result': {'path': 'nb.ipynb'}}
            )
            return await task

        result = asyncio.run(scenario())
        assert result == {'path': 'nb.ipynb'}
        assert _listeners(response) == []

    def test_ignores_responses_for_other_callbacks(self):
        response = ChatResponse()

        async def scenario():
            task = asyncio.ensure_future(
                ChatResponse.wait_for_run_ui_command_response(response, 'cb-1')
            )
            await asyncio.sleep(0)
            response.on_run_ui_command_response(
                {'callback_id': 'other', 'result': 'wrong'}
            )
            response.on_run_ui_command_response(
                {'callback_id': 'cb-1', 'result': 'right'}
            )
            return await task

        assert asyncio.run(scenario()) == 'right'

    def test_times_out_and_disconnects_listener(self):
        response = ChatResponse()

        async def scenario():
            await ChatResponse.wait_for_run_ui_command_response(
                response, 'cb-1', timeout=0.05
            )

        with pytest.raises(TimeoutError):
            asyncio.run(scenario())
        assert _listeners(response) == []

    def test_cancellation_disconnects_listener(self):
        response = ChatResponse()

        async def scenario():
            task = asyncio.ensure_future(
                ChatResponse.wait_for_run_ui_command_response(response, 'cb-1')
            )
            await asyncio.sleep(0)
            assert len(_listeners(response)) == 1
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(scenario())
        assert _listeners(response) == []

    def test_default_timeout_comes_from_module_constant(self, monkeypatch):
        import notebook_intelligence.api as api_mod
        monkeypatch.setattr(api_mod, 'RUN_UI_COMMAND_RESPONSE_TIMEOUT', 0.05)
        response = ChatResponse()

        async def scenario():
            await ChatResponse.wait_for_run_ui_command_response(response, 'cb-1')

        with pytest.raises(TimeoutError):
            asyncio.run(scenario())

    def test_non_positive_timeout_disables_the_bound(self):
        response = ChatResponse()

        async def scenario():
            task = asyncio.ensure_future(
                ChatResponse.wait_for_run_ui_command_response(
                    response, 'cb-1', timeout=0
                )
            )
            # Longer than a couple of poll intervals: with timeout=0 treated
            # as "expired immediately" this would raise instead of waiting.
            await asyncio.sleep(0.25)
            response.on_run_ui_command_response(
                {'callback_id': 'cb-1', 'result': 'ok'}
            )
            return await task

        assert asyncio.run(scenario()) == 'ok'


class TestFloatEnvParsing:
    """The timeout env var is parsed at import time — malformed values must
    degrade to the default with a warning, never raise and block startup."""

    def test_unset_returns_default(self, monkeypatch):
        from notebook_intelligence.api import _float_env
        monkeypatch.delenv('NBI_TEST_FLOAT', raising=False)
        assert _float_env('NBI_TEST_FLOAT', 1800.0) == 1800.0

    def test_valid_value_parsed(self, monkeypatch):
        from notebook_intelligence.api import _float_env
        monkeypatch.setenv('NBI_TEST_FLOAT', '42.5')
        assert _float_env('NBI_TEST_FLOAT', 1800.0) == 42.5

    def test_empty_string_returns_default(self, monkeypatch):
        from notebook_intelligence.api import _float_env
        monkeypatch.setenv('NBI_TEST_FLOAT', '   ')
        assert _float_env('NBI_TEST_FLOAT', 1800.0) == 1800.0

    def test_malformed_value_returns_default(self, monkeypatch):
        from notebook_intelligence.api import _float_env
        monkeypatch.setenv('NBI_TEST_FLOAT', '30s')
        assert _float_env('NBI_TEST_FLOAT', 1800.0) == 1800.0

    def test_negative_value_passes_through(self, monkeypatch):
        # <= 0 is the documented "disable the bound" escape hatch.
        from notebook_intelligence.api import _float_env
        monkeypatch.setenv('NBI_TEST_FLOAT', '-1')
        assert _float_env('NBI_TEST_FLOAT', 1800.0) == -1.0


class TestNoneResultIsAValidResponse:
    def test_none_result_resolves_the_wait(self):
        # Void UI commands legitimately respond with result=None (JSON
        # null). That must resolve the wait, not spin into the timeout.
        response = ChatResponse()

        async def scenario():
            task = asyncio.ensure_future(
                ChatResponse.wait_for_run_ui_command_response(
                    response, 'cb-1', timeout=5
                )
            )
            await asyncio.sleep(0)
            response.on_run_ui_command_response(
                {'callback_id': 'cb-1', 'result': None}
            )
            return await task

        assert asyncio.run(scenario()) is None
        assert _listeners(response) == []

    def test_non_finite_values_return_default(self, monkeypatch):
        # nan fails every `timeout > 0` comparison and inf never elapses;
        # either silently disables the bound. The documented disable
        # switch is a finite <= 0.
        from notebook_intelligence.api import _float_env
        for raw in ('nan', 'inf', '-inf', 'Infinity'):
            monkeypatch.setenv('NBI_TEST_FLOAT', raw)
            assert _float_env('NBI_TEST_FLOAT', 1800.0) == 1800.0
