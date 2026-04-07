from lightclaw.domain.errors import ToolArgumentValidationError


def validate_tool_arguments(schema: dict[str, object], arguments: dict[str, object]) -> None:
    if not schema:
        return
    expected_type = schema.get("type")
    if expected_type and expected_type != "object":
        raise ToolArgumentValidationError("Only object-shaped tool schemas are currently supported.")
    if not isinstance(arguments, dict):
        raise ToolArgumentValidationError("Tool arguments must be an object.")

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    additional_properties = schema.get("additionalProperties", True)

    if isinstance(required, list):
        missing = [name for name in required if name not in arguments]
        if missing:
            raise ToolArgumentValidationError(
                f"Missing required tool arguments: {', '.join(sorted(missing))}."
            )

    if additional_properties is False and isinstance(properties, dict):
        extras = [name for name in arguments if name not in properties]
        if extras:
            raise ToolArgumentValidationError(
                f"Unexpected tool arguments: {', '.join(sorted(extras))}."
            )

    if not isinstance(properties, dict):
        return

    for name, value in arguments.items():
        if name not in properties:
            continue
        property_schema = properties[name]
        if not isinstance(property_schema, dict):
            continue
        _validate_property(name, property_schema, value)


def _validate_property(name: str, schema: dict[str, object], value: object) -> None:
    expected_type = schema.get("type")
    if expected_type == "string":
        if not isinstance(value, str):
            raise ToolArgumentValidationError(f"Tool argument '{name}' must be a string.")
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            raise ToolArgumentValidationError(
                f"Tool argument '{name}' must be at least {min_length} characters."
            )
        return

    if expected_type == "array":
        if not isinstance(value, list):
            raise ToolArgumentValidationError(f"Tool argument '{name}' must be an array.")
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            raise ToolArgumentValidationError(
                f"Tool argument '{name}' must contain at least {min_items} item(s)."
            )
        item_schema = schema.get("items")
        if isinstance(item_schema, dict) and item_schema.get("type") == "string":
            if not all(isinstance(item, str) for item in value):
                raise ToolArgumentValidationError(
                    f"Tool argument '{name}' must only contain strings."
                )
        return

    if expected_type == "object":
        if not isinstance(value, dict):
            raise ToolArgumentValidationError(f"Tool argument '{name}' must be an object.")
