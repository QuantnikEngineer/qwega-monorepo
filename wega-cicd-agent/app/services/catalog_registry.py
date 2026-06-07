from app.core.policies import load_policy
from app.models.responses import CatalogItem, CatalogResponse, CatalogStage, CatalogTool


def get_catalog_definition() -> dict:
    return load_policy('catalogs.json')


def get_platform_map() -> dict[str, dict]:
    catalog = get_catalog_definition()
    return {item['value']: item for item in catalog['platforms']}


def get_language_map() -> dict[str, dict]:
    catalog = get_catalog_definition()
    return {item['value']: item for item in catalog['languages']}


def get_stage_map() -> dict[str, dict]:
    catalog = get_catalog_definition()
    return {item['id']: item for item in catalog['stages']}


def get_tool_map() -> dict[str, dict]:
    catalog = get_catalog_definition()
    return {item['id']: item for item in catalog['tools']}


def build_catalog_response() -> CatalogResponse:
    catalog = get_catalog_definition()
    return CatalogResponse(
        platforms=[CatalogItem(value=item['value'], label=item['label']) for item in catalog['platforms']],
        languages=[CatalogItem(value=item['value'], label=item['label']) for item in catalog['languages']],
        artifactTypes=get_artifact_type_items(),
        deploymentTargets=[CatalogItem(value=item['value'], label=item['label']) for item in catalog['deploymentTargets']],
        tools=[
            CatalogTool(id=item['id'], name=item['name'], category=item['category'], description=item['description'])
            for item in catalog['tools']
        ],
        stages=[CatalogStage(id=item['id'], name=item['name'], description=item['description']) for item in catalog['stages']],
    )


def get_artifact_type_items() -> list[CatalogItem]:
    seen = set()
    items = []
    for language in get_catalog_definition()['languages']:
        for value in language['artifactTypes']:
            if value in seen:
                continue
            seen.add(value)
            items.append(CatalogItem(value=value, label=_artifact_label(value)))
    return items


def _artifact_label(value: str) -> str:
    labels = {
        'none': 'No artifact',
        'binary': 'Binary',
        'container': 'Container image',
        'package': 'Package',
    }
    return labels.get(value, value.replace('-', ' ').title())