from app.core.config import Settings


def test_settings_accepts_legacy_gemini_model_alias_and_ignores_google_sdk_env(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    creds_path = tmp_path / 'service-account.json'
    creds_path.write_text('{}', encoding='utf-8')
    env_file.write_text(
        '\n'.join(
            [
                'GOOGLE_GENAI_USE_VERTEXAI=TRUE',
                f'GOOGLE_APPLICATION_CREDENTIALS={creds_path}',
                'GEMINI_MODEL=gemini-2.5-flash',
                'LLM_THINKING_BUDGET=0',
            ]
        ),
        encoding='utf-8',
    )
    monkeypatch.delenv('LLM_MODEL', raising=False)
    monkeypatch.delenv('GEMINI_MODEL', raising=False)

    configured = Settings(_env_file=env_file)

    assert configured.llm_model == 'gemini-2.5-flash'
    assert configured.llm_thinking_budget == 0