from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Any, Mapping

import yaml

from reference_agent.config import (
    configured_config_path,
    configured_profiles_dir,
    configured_tools_path,
    load_config,
    load_tools_md_text,
    load_yaml,
    validate_config_data,
)
from reference_agent.models import Profile


@dataclass(frozen=True)
class RuntimeField:
    name: str
    label: str
    input_type: str


@dataclass(frozen=True)
class ConfigEditTarget:
    key: str
    label: str
    path: Path
    kind: str


@dataclass(frozen=True)
class ConfigPreview:
    title: str
    target_key: str
    target_label: str
    content: str
    diff: str
    restart_required: bool
    changed_fields: tuple[str, ...]
    validation_error: str | None = None
    success_message: str | None = None


@dataclass(frozen=True)
class ConfigurationPageModel:
    targets: tuple[ConfigEditTarget, ...]
    structured_fields: tuple[RuntimeField, ...]
    structured_values: dict[str, str]
    raw_target_key: str
    raw_content: str
    preview: ConfigPreview | None = None
    flash_message: str | None = None


RUNTIME_FIELDS = (
    RuntimeField(name="port", label="Port", input_type="number"),
    RuntimeField(name="timeout_seconds", label="Timeout Seconds", input_type="number"),
    RuntimeField(name="concurrency", label="Concurrency", input_type="number"),
    RuntimeField(
        name="rate_limit_per_base_url",
        label="Rate Limit Per Base URL",
        input_type="number",
    ),
    RuntimeField(name="streaming_default", label="Streaming Default", input_type="boolean"),
    RuntimeField(
        name="stream_status_updates",
        label="Stream Status Updates",
        input_type="boolean",
    ),
)


def build_configuration_page_model(
    *,
    raw_target_key: str | None = None,
    raw_content: str | None = None,
    structured_values: dict[str, str] | None = None,
    preview: ConfigPreview | None = None,
    flash_message: str | None = None,
) -> ConfigurationPageModel:
    targets = list_config_targets()
    selected_target = resolve_target(raw_target_key or "config", targets)
    config_model = load_config(configured_config_path())
    selected_structured_values = structured_values or _structured_values_from_runtime_config(
        config_model.runtime
    )
    selected_raw_content = raw_content if raw_content is not None else selected_target.path.read_text()
    return ConfigurationPageModel(
        targets=targets,
        structured_fields=RUNTIME_FIELDS,
        structured_values=selected_structured_values,
        raw_target_key=selected_target.key,
        raw_content=selected_raw_content,
        preview=preview,
        flash_message=flash_message,
    )


def handle_configuration_submission(form_data: Mapping[str, str]) -> ConfigurationPageModel:
    mode = form_data.get("mode", "structured")
    action = form_data.get("action", "preview")
    if mode == "structured":
        preview = preview_structured_runtime(form_data)
        structured_values = structured_values_from_submission(form_data)
        if action == "apply" and preview.success_message is not None:
            structured_values = None
        flash_message = preview.success_message if action == "apply" else None
        return build_configuration_page_model(
            raw_target_key="config",
            raw_content=preview.content if action == "apply" else None,
            structured_values=structured_values,
            preview=preview,
            flash_message=flash_message,
        )

    preview = preview_raw_edit(
        form_data.get("raw_target", "config"),
        form_data.get("raw_content", ""),
        action=action,
    )
    flash_message = preview.success_message if action == "apply" else None
    return build_configuration_page_model(
        raw_target_key=preview.target_key,
        raw_content=preview.content,
        preview=preview,
        flash_message=flash_message,
    )


def preview_structured_runtime(form_data: Mapping[str, str]) -> ConfigPreview:
    config_path = configured_config_path()
    current_text = config_path.read_text()
    data = load_yaml(config_path)
    updated_runtime = dict(data.get("runtime") or {})
    changed_fields: list[str] = []

    try:
        for field in RUNTIME_FIELDS:
            next_value = _parse_runtime_field_value(field, form_data)
            if updated_runtime.get(field.name) != next_value:
                changed_fields.append(field.name)
            updated_runtime[field.name] = next_value
    except ValueError as exc:
        return ConfigPreview(
            title="Structured Runtime Preview",
            target_key="config",
            target_label="config.yaml",
            content=current_text,
            diff="No changes.",
            restart_required=False,
            changed_fields=(),
            validation_error=str(exc),
        )

    data["runtime"] = updated_runtime
    return _build_preview(
        target=resolve_target("config"),
        title="Structured Runtime Preview",
        content=_dump_yaml(data),
        changed_fields=tuple(changed_fields),
        validator=lambda text: validate_config_data(_load_yaml_text(text)),
        action=form_data.get("action", "preview"),
    )


def preview_raw_edit(target_key: str, raw_content: str, *, action: str = "preview") -> ConfigPreview:
    try:
        target = resolve_target(target_key)
    except ValueError as exc:
        return ConfigPreview(
            title="Raw Preview",
            target_key="config",
            target_label="config.yaml",
            content=raw_content,
            diff="No changes.",
            restart_required=False,
            changed_fields=(),
            validation_error=str(exc),
        )
    return _build_preview(
        target=target,
        title="Raw Preview",
        content=raw_content,
        changed_fields=(),
        validator=lambda text: _validate_raw_target(target, text),
        action=action,
    )


def list_config_targets() -> tuple[ConfigEditTarget, ...]:
    profiles_dir = configured_profiles_dir()
    targets = [
        ConfigEditTarget(
            key="config",
            label="config.yaml",
            path=configured_config_path(),
            kind="config",
        ),
        ConfigEditTarget(
            key="tools",
            label="TOOLS.md",
            path=configured_tools_path(),
            kind="tools",
        ),
    ]
    for profile_path in sorted(profiles_dir.glob("*.yaml")):
        targets.append(
            ConfigEditTarget(
                key=f"profile:{profile_path.stem}",
                label=profile_path.name,
                path=profile_path,
                kind="profile",
            )
        )
    return tuple(targets)


def resolve_target(
    target_key: str, targets: tuple[ConfigEditTarget, ...] | None = None
) -> ConfigEditTarget:
    available_targets = targets or list_config_targets()
    for target in available_targets:
        if target.key == target_key:
            return target
    raise ValueError(f"Unknown config target: {target_key}")


def structured_values_from_submission(form_data: Mapping[str, str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in RUNTIME_FIELDS:
        submitted_value = form_data.get(f"structured_runtime_{field.name}")
        if submitted_value is None:
            config_model = load_config(configured_config_path())
            return _structured_values_from_runtime_config(config_model.runtime)
        values[field.name] = submitted_value
    return values


def _build_preview(
    *,
    target: ConfigEditTarget,
    title: str,
    content: str,
    changed_fields: tuple[str, ...],
    validator,
    action: str,
) -> ConfigPreview:
    current_text = target.path.read_text()
    validation_error: str | None = None
    success_message: str | None = None
    has_valid_changes = False

    try:
        validator(content)
    except (ValueError, yaml.YAMLError) as exc:
        validation_error = str(exc)
    else:
        has_valid_changes = current_text != content
        if action == "apply":
            target.path.write_text(content)
            success_message = "Configuration updated."

    return ConfigPreview(
        title=title,
        target_key=target.key,
        target_label=target.label,
        content=content,
        diff=_build_diff(current_text, content, str(target.path)),
        restart_required=has_valid_changes,
        changed_fields=changed_fields,
        validation_error=validation_error,
        success_message=success_message,
    )


def _validate_raw_target(target: ConfigEditTarget, text: str) -> None:
    if target.kind == "config":
        validate_config_data(_load_yaml_text(text))
        return
    if target.kind == "tools":
        load_tools_md_text(text)
        return
    if target.kind == "profile":
        Profile(**_load_yaml_text(text))
        return
    raise ValueError(f"Unsupported config target: {target.kind}")


def _load_yaml_text(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("YAML content must decode to a mapping.")
    return data


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False)


def _build_diff(before: str, after: str, path_label: str) -> str:
    diff_lines = unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=path_label,
        tofile=path_label,
        lineterm="",
    )
    return "\n".join(diff_lines) or "No changes."


def _parse_runtime_field_value(field: RuntimeField, form_data: Mapping[str, str]) -> Any:
    raw_value = form_data.get(f"structured_runtime_{field.name}", "")
    if field.input_type == "boolean":
        return _parse_bool(raw_value, field.label)
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{field.label} must be an integer.") from exc


def _parse_bool(raw_value: str, field_label: str) -> bool:
    normalized = raw_value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{field_label} must be a boolean.")


def _structured_values_from_runtime_config(runtime_config: Any) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in RUNTIME_FIELDS:
        value = getattr(runtime_config, field.name)
        if field.input_type == "boolean":
            values[field.name] = "true" if value else "false"
        else:
            values[field.name] = str(value)
    return values
