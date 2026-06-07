import asyncio
import json

import app.agents.streaming_graph as streaming_graph


class _StubMemory:
    async def get_conversation_history(self, session_id, limit=10):
        return []

    async def get_last_agent(self, session_id):
        return None

    async def get_suggested_actions(self, session_id):
        return []

    async def add_user_message(self, session_id, message):
        return None

    async def add_assistant_message(self, session_id, message):
        return None

    async def set_suggested_actions(self, session_id, actions):
        return None

    async def set_last_agent(self, session_id, agent):
        return None


class _UnexpectedCiClient:
    async def call_ci_agent(self, message, context):
        raise AssertionError('CI agent should not be called before the builder collects structured inputs.')

    async def call_cd_agent(self, message, context):
        raise AssertionError('CD agent should not be called in a CI handoff test.')


def _parse_sse_event(raw_event: str) -> dict:
    assert raw_event.startswith('data: ')
    return json.loads(raw_event[len('data: '):].strip())


def test_execute_with_streaming_short_circuits_ci_builder_handoff(monkeypatch):
    monkeypatch.setattr(streaming_graph, 'get_memory', lambda: _StubMemory())
    monkeypatch.setattr(streaming_graph, 'get_agent_client', lambda: _UnexpectedCiClient())

    async def collect_events():
        events = []
        async for raw_event in streaming_graph.execute_with_streaming(
            session_id='deploy-handoff-test',
            message='Generate CI pipeline',
            context={},
            explicit_intent='generate_ci_pipeline',
        ):
            events.append(_parse_sse_event(raw_event))
        return events

    events = asyncio.run(collect_events())

    milestone_stages = [event['stage'] for event in events if event['type'] == 'milestone']
    assert 'calling_agent' not in milestone_stages

    final_response = next(event for event in reversed(events) if event['type'] == 'response')
    assert final_response['status'] == 'success'
    assert final_response['routed_to'] == 'ci'
    assert final_response['nextagentflow'] == streaming_graph.CI_BUILDER_HANDOFF_FLOW
    assert final_response['message'] == streaming_graph.CI_BUILDER_HANDOFF_MESSAGE
    assert final_response['data']['intent'] == 'generate_ci_pipeline'
