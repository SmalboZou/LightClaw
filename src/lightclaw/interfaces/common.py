from lightclaw.bootstrap import ApplicationContainer, build_container
from lightclaw.config.logging import configure_logging
from lightclaw.config.settings import AppSettings


def create_interface_context(settings: AppSettings | None = None) -> tuple[AppSettings, ApplicationContainer]:
    resolved_settings = settings or AppSettings()
    configure_logging(resolved_settings)
    return resolved_settings, build_container(resolved_settings)
