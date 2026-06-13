# quantnik-evals

Reusable LLM agent evaluation framework with Langfuse integration and LLM-as-judge scoring.

## Architecture

```
quantnik_evals/
├── models.py            # Generic data models (EvalResult, DimensionScore)
├── config.py            # Framework configuration
├── agent_profile.py     # AgentProfile base class — each agent implements this
├── llm_judge.py         # Generic LLM-as-judge evaluator
├── dataset_manager.py   # Langfuse dataset seeding/loading
├── runner.py            # Evaluation orchestrator + Langfuse score push
├── cli.py               # CLI entry point (quantnik-eval)
└── profiles/            # Built-in agent profiles
    ├── cara.py          # CARA code review agent
    ├── brd_summary.py   # BRD summary agent
    └── user_story.py    # User story generator agent
```

## Quick Start

```bash
pip install -e .

# List available agent profiles
quantnik-eval list-agents

# Seed a dataset from Langfuse traces
quantnik-eval --agent cara seed --limit 20

# Run evaluation
quantnik-eval --agent cara run --dataset cara-eval

# Evaluate a single trace
quantnik-eval --agent cara trace <trace-id>

# Use a different agent
quantnik-eval --agent brd_summary run --dataset brd-eval
```

## Agent Profiles

Each agent provides a profile class that defines:

| Attribute | Purpose |
|---|---|
| `name` | Agent identifier |
| `dimensions` | Evaluation dimensions to score |
| `judge_prompts` | LLM-as-judge prompt templates per dimension |
| `output_schema` | Expected output structure (for structural validation) |
| `trace_name` | Langfuse trace name filter |
| `extract_input()` | How to extract agent input from traces |
| `extract_output()` | How to extract agent output from traces |
| `programmatic_evals()` | Non-LLM scoring functions |

### Creating a Custom Agent Profile

```python
from quantnik_evals.agent_profile import AgentProfile

class MyAgentProfile(AgentProfile):
    name = "my_agent"
    description = "My custom agent"
    trace_name = "my_agent_trace"
    dimensions = ["output_quality", "completeness", "accuracy"]

    judge_prompts = {
        "output_quality": "Evaluate the quality of this output...\n{input}\n{output}",
        "completeness": "Is this output complete?...\n{input}\n{output}",
    }

    output_schema = {
        "required_fields": ["summary", "recommendations"],
        "status_field": "status",
        "status_values": ["pass", "fail"],
    }
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | Yes | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Yes | Langfuse secret key |
| `LANGFUSE_HOST` | Yes | Langfuse server URL |
| `JUDGE_API_KEY` | Yes | API key for the judge model |
| `JUDGE_MODEL` | No | Judge model (default: gemini-2.5-pro) |
| `JUDGE_TEMPERATURE` | No | Judge temperature (default: 0.0) |
| `EVAL_PASS_THRESHOLD` | No | Pass threshold (default: 0.7) |
