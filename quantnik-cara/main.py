import os

from cara.app import app as fastapi_app

app = fastapi_app


def main() -> None:
    import uvicorn

    # Default to 8001 locally so we don't collide with the Planning Orchestrator
    # (which runs on 8000). Cloud Run / Docker will inject $PORT and override.
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
