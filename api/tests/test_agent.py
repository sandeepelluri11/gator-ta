from gator_ta.chat.agent import Agent, answer_text
from tests.conftest import FakeLLM, FakeRetriever, text_turn, tool_turn


async def test_memory_trims_and_expires(memory, redis):
    for i in range(5):
        await memory.append(
            "s1", {"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}
        )
    history = await memory.history("s1")
    assert len(history) == 6  # history_turns=3 -> 6 messages
    assert history[0]["content"] == "q2"
    assert await redis.ttl(memory.key("s1")) > 0

    await memory.clear("s1")
    assert await memory.history("s1") == []


async def test_agent_streams_cited_answer_and_records_history(memory, tools, settings):
    llm = FakeLLM([text_turn("RRF uses ", "k = 60 [1].")])
    retriever = FakeRetriever()
    agent = Agent(llm, retriever, tools, memory, top_k=settings.top_k)

    events = [e async for e in agent.answer("s1", "What is k in RRF?")]

    assert events[0]["type"] == "citations"
    assert [c["n"] for c in events[0]["citations"]] == [1, 2]
    assert events[0]["citations"][0]["label"] == "02 Retrieval (p. 6)"
    assert [e["text"] for e in events if e["type"] == "token"] == ["RRF uses ", "k = 60 [1]."]
    assert events[-1]["type"] == "done"
    assert events[-1]["answer"] == "RRF uses k = 60 [1]."
    assert events[-1]["tool_rounds"] == 0

    # the prompt carried the excerpts and the question
    user_msg = llm.requests[0]["messages"][-1]["content"]
    assert "[1] 02 Retrieval (p. 6) - Hybrid retrieval" in user_msg
    assert "What is k in RRF?" in user_msg
    assert llm.requests[0]["tools"] is not None

    history = await memory.history("s1")
    assert [m["role"] for m in history] == ["user", "assistant"]


async def test_agent_runs_tool_loop_then_answers(memory, tools, settings):
    llm = FakeLLM(
        [
            tool_turn("get_office_hours", {"day": "Wednesday"}),
            text_turn("Head TA, Wednesday 10:00-12:00 in CSE E309."),
        ]
    )
    agent = Agent(llm, FakeRetriever([]), tools, memory, max_tool_rounds=settings.max_tool_rounds)

    events = [e async for e in agent.answer("s2", "When are TA office hours on Wednesday?")]

    tool_events = [e for e in events if e["type"] == "tool_call"]
    assert tool_events == [
        {"type": "tool_call", "name": "get_office_hours", "arguments": {"day": "Wednesday"}}
    ]
    assert events[-1]["tool_rounds"] == 1
    assert "CSE E309" in events[-1]["answer"]

    # second model call saw the assistant tool_calls message and the tool result
    second = llm.requests[1]["messages"]
    assert second[-2]["role"] == "assistant"
    assert second[-2]["tool_calls"][0]["function"]["name"] == "get_office_hours"
    assert second[-1]["role"] == "tool"
    assert "Head TA" in second[-1]["content"]


async def test_agent_stops_calling_tools_at_budget(memory, tools, settings):
    # the fake keeps asking for a tool forever; the agent must withhold tools after the budget
    llm = FakeLLM(
        [tool_turn("get_grading_policy"), tool_turn("get_grading_policy"), text_turn("done")]
    )
    agent = Agent(llm, FakeRetriever([]), tools, memory, max_tool_rounds=2)

    answer, _ = await answer_text(agent, "s3", "late policy?")

    assert answer == "done"
    assert llm.requests[0]["tools"] and llm.requests[1]["tools"]
    assert llm.requests[2]["tools"] is None


async def test_agent_includes_prior_turns(memory, tools):
    await memory.append(
        "s4",
        {"role": "user", "content": "earlier q"},
        {"role": "assistant", "content": "earlier a"},
    )
    llm = FakeLLM([text_turn("follow-up")])
    agent = Agent(llm, FakeRetriever([]), tools, memory)

    await answer_text(agent, "s4", "and then?")

    roles = [m["role"] for m in llm.requests[0]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert llm.requests[0]["messages"][0]["content"].startswith("You are GatorTA")
