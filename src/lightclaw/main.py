from fastapi import FastAPI

from lightclaw.interfaces.common import create_interface_context
from lightclaw.interfaces.api.app import create_api


def app() -> FastAPI:
    settings, container = create_interface_context()
    return create_api(settings, container=container)
