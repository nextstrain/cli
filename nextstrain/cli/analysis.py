"""
Analysis directories and configuration.
"""
import json
from pathlib import Path
from typing import Optional
import jsonschema
import yaml
from . import resources
from .debug import debug
from .errors import UserError


CONFIG_FILE = "config.yaml"
MANIFEST_KEY = "nextstrain"


def read_analysis_manifest(path: Path) -> Optional[dict]:
    """
    Reads a configuration file at *path* and returns the contents of its
    top-level ``nextstrain`` key (the manifest).

    Returns ``None`` if *path* does not exist or has no manifest.

    Raises :exc:`UserError` if there are issues with the manifest.
    """
    try:
        with path.open("r", encoding = "utf-8") as f:
            configuration = yaml.safe_load(f)

    except FileNotFoundError as err:
        debug(f"failed to read {str(path)!r}:", err)
        return None

    except yaml.YAMLError as err:
        raise UserError(f"Failed to parse {path}:\n\n{err}") from err

    # File exists and we read it.
    #
    # If it's an empty file (or contains only comments), then we'll get None.
    # Treat that as an empty dict instead.
    if configuration is None:
        configuration = {}

    if not isinstance(configuration, dict):
        raise UserError(f"{path} top-level not a dict (got a {type(configuration).__name__})")

    if MANIFEST_KEY not in configuration:
        return None

    # If the manifest is present but empty (or contains only comments), we'll
    # get None.  Treat that as an empty dict instead.
    if (manifest := configuration[MANIFEST_KEY]) is None:
        manifest = {}

    # Locate schema for the manifest, if any
    if not (schema_id := manifest.get("$schema")):
        debug(f"skipping validation of analysis manifest in {str(path)!r}: no $schema declared")
        return manifest

    # Known schemas we can validate against
    schemas = {
        "https://nextstrain.org/schemas/analysis/v0": "schema-analysis-v0.json" }

    # Skip validation if schema is unknown
    if not (schema_path := schemas.get(schema_id)):
        debug(f"skipping validation of analysis manifest in {str(path)!r}: unknown $schema: {schema_id!r}")
        return manifest

    # Validate
    debug(f"validating analysis manifest in {str(path)!r} against {schema_id!r} ({schema_path!r})")

    with resources.open_text(schema_path) as f:
        schema = json.load(f)

    assert schema.get("$id") == schema_id

    try:
        jsonschema.validate(manifest, schema)
    except jsonschema.ValidationError as err:
        raise UserError(f"Schema validation failed for {MANIFEST_KEY!r} in {str(path)!r}: {err.message}") from err

    return manifest


def write_analysis_manifest(path: Path, pathogen: str, workflow: str) -> None:
    """
    Appends a manifest block to the configuration file at *path* with the given
    *pathogen* and *workflow*, creating the file if it doesn't already exist.
    """
    data = {
        MANIFEST_KEY: {
            "pathogen": pathogen,
            "workflow": workflow,
        },
    }

    block = "### Added by Nextstrain ###\n" + yaml.dump(data, indent = 2, sort_keys = False)

    path.parent.mkdir(parents = True, exist_ok = True)

    needs_separator = path.exists() and path.stat().st_size > 0

    with path.open("a", encoding = "utf-8") as f:
        if needs_separator:
            f.write("\n")
        f.write(block)
