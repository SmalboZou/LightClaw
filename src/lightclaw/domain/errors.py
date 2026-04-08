class LightClawError(Exception):
    """Base application error."""


class PolicyViolationError(LightClawError):
    """Raised when a tool call violates the active execution policy."""


class ToolNotFoundError(LightClawError):
    """Raised when a requested tool is not registered."""


class ToolArgumentValidationError(LightClawError):
    """Raised when tool arguments do not satisfy the declared schema."""


class AgentLoopExceededError(LightClawError):
    """Raised when the agent exceeds the configured loop limit."""


class ProviderRequestError(LightClawError):
    """Raised when an upstream model provider request fails."""


class JobNotFoundError(LightClawError):
    """Raised when a requested job does not exist."""


class JobDisabledError(LightClawError):
    """Raised when a requested job is disabled."""


class JobRunNotFoundError(LightClawError):
    """Raised when a requested job run does not exist."""


class SkillNotFoundError(LightClawError):
    """Raised when a requested skill package does not exist."""


class SkillDependencyError(LightClawError):
    """Raised when a skill package cannot be activated due to missing dependencies."""


class AuthenticationError(LightClawError):
    """Raised when console authentication fails."""


class AuthorizationError(LightClawError):
    """Raised when a console user attempts to access another user's resources."""
