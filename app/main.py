import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers.webhooks import webhooks_router
from app.routers.sessions_router import sessions_router
from app.routers.system import router as system_router
import rollbar
from rollbar.logger import RollbarHandler
from rollbar.contrib.fastapi import ReporterMiddleware as RollbarMiddleware
from fastapi_pagination import add_pagination

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from app.telemetry import setup_tracing
from app.exceptions.handlers import register_exception_handlers
from app.infra.logging_config import get_logger
from app.db import db_manager
from app.utils.metrics import PrometheusMiddleware, metrics
from app.infra.logging_config import get_logger

logger = get_logger()

SKIP_AUTH_PATHS = ["/health", "/openapi.json", "/docs", "/metrics"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init Telegram plugin when enabled. Shutdown: stop Telegram."""
    settings = get_settings()

    if settings.telegram_enabled and settings.telegram_bot_token:
        from app.channels.plugins.telegram.plugin import TelegramPlugin
        from app.channels.plugins.telegram.config import TelegramConfig
        from app.core.app_state import state

        telegram = TelegramPlugin(TelegramConfig(bot_token=settings.telegram_bot_token))
        state.registry.register_channel(telegram)
        await telegram.start()
        app.state.telegram = telegram
    else:
        app.state.telegram = None
    yield
    telegram = getattr(app.state, "telegram", None)
    if telegram:
        await telegram.stop()


class EndpointFilter(logging.Filter):
    # Uvicorn endpoint access log filter
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /metrics") == -1


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


def create_app(testing: bool = False, auth_middleware=None) -> FastAPI:
    logger = get_logger()
    settings = get_settings()

    app = FastAPI(lifespan=lifespan)
    if settings.is_production:
        # Initialize Rollbar SDK with your server-side access token
        rollbar.init(settings.rollbar_access_token, environment=settings.environment)

        # Report ERROR and above to Rollbar
        rollbar_handler = RollbarHandler()
        rollbar_handler.setLevel(logging.ERROR)

        # Attach Rollbar handler to the root logger
        logger.addHandler(rollbar_handler)
        app.add_middleware(RollbarMiddleware)

    if not testing and not settings.disable_auth:
        logger.info("Main: Adding authentication middleware")
        from tessera_sdk.middleware.authentication import AuthenticationMiddleware
        from tessera_sdk.middleware.user_onboarding import UserOnboardingMiddleware
        from tessera_sdk.utils.service_factory import create_service_factory
        from app.services.user_service import UserService

        # Create service factory for UserService
        user_service_factory = create_service_factory(UserService, db_manager)

        app.add_middleware(
            UserOnboardingMiddleware,
            user_service_factory=user_service_factory,
        )
        app.add_middleware(
            AuthenticationMiddleware,
            skip_paths=SKIP_AUTH_PATHS,
            user_service_factory=user_service_factory,
        )

        # Setting metrics middleware
        app.add_middleware(PrometheusMiddleware, app_name=settings.app_name)
        app.add_route("/metrics", metrics)

    else:
        logger.info("Main: No authentication middleware")
        if auth_middleware:
            app.add_middleware(auth_middleware)

    # TODO: Restrict this to the allowed origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Puedes restringir esto a dominios específicos
        allow_credentials=True,
        allow_methods=["*"],  # Permitir todos los métodos (GET, POST, etc.)
        allow_headers=["*"],  # Permitir todos los headers
    )

    register_exception_handlers(app)

    # Add pagination support
    add_pagination(app)

    # Chat gateway and webhooks
    app.include_router(webhooks_router)
    app.include_router(sessions_router)
    app.include_router(system_router)

    return app


# Production app instance
app = create_app()

settings = get_settings()
if settings.otel_enabled:
    tracer_provider = setup_tracing()  # Or use env/config
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)


@app.get("/")
def main_route():
    return {"message": "Hey, It is me Goku"}
