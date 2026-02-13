from app.core.registry import PluginRegistry
from app.core.routing import Router


class AppState:
    def __init__(self) -> None:
        self.registry = PluginRegistry()
        self.router = Router()


state = AppState()
