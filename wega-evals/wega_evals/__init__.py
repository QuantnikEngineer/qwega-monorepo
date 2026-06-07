# wega-evals: Reusable LLM Agent Evaluation Framework

# Auto-register all built-in profiles on import
from wega_evals.profiles import cara as _cara  # noqa: F401
from wega_evals.profiles import brd_summary as _brd_summary  # noqa: F401
from wega_evals.profiles import brd as _brd  # noqa: F401
from wega_evals.profiles import user_story as _user_story  # noqa: F401
from wega_evals.profiles import userstory_validator as _userstory_validator  # noqa: F401
from wega_evals.profiles import userstory_to_testcases as _userstory_to_testcases  # noqa: F401
from wega_evals.profiles import testcases_to_testdata as _testcases_to_testdata  # noqa: F401
from wega_evals.profiles import testcase_to_scripts as _testcase_to_scripts  # noqa: F401
from wega_evals.profiles import sdlc_orchestrator as _sdlc_orchestrator  # noqa: F401
from wega_evals.profiles import code_assistant as _code_assistant  # noqa: F401
from wega_evals.profiles import user_manual as _user_manual  # noqa: F401
