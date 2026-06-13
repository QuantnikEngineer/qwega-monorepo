from importlib import import_module

__all__ = [
	"adk_helpers",
	"docx_generator",
	"prompts",
	"validators",
	"file_extractor",
	"json_parser",
	"mcp_confluence",
	"confluence_exporter",
	"confluence_config",
]


def __getattr__(name: str):
	if name not in __all__:
		raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
	module = import_module(f"{__name__}.{name}")
	globals()[name] = module
	return module


def __dir__() -> list[str]:
	return sorted(list(globals().keys()) + __all__)
