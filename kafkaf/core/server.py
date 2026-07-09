import uvicorn

from kafkaf.core.config import settings


def run() -> None:
    uvicorn.run("kafkaf.core.api:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
