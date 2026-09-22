"""PromptLoader - Reads framework prompt files for the agent loop.

Instead of hardcoding prompt content in Python, this module reads the
actual framework/agent_skills/<version>/*.md files at runtime. This ensures
the app uses exactly the same prompts as Genie Code.

The prompt files are organized under versioned agent_skills directories
(v1, v2, etc.) allowing different prompt versions to coexist. The version
is selected per-domain in accelerator.yaml or via the UI.

Context variables are injected via simple {placeholder} replacement.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Version-specific prompt file layouts
# ---------------------------------------------------------------------------
# Each version can have a different directory structure. The loader picks
# the correct layout based on agent_skills_version.

# v1: flat layout — prompts and guardrails at the root of the version dir
_V1_STEP_PROMPT_FILES = {
    "master": "00_master_prompt.md",
    "create_data_layer": "01_create_data_layer.md",
    "create_metric_views": "02_create_metric_views.md",
    "create_dashboards": "03_create_dashboards.md",
    "create_genie_space": "04_create_genie_space.md",
    "generate_documentation": "05_generate_documentation.md",
}
_V1_SUPPLEMENT_FILES = {
    "create_data_layer": ["guardrails/sql_generation_rules.md"],
    "create_metric_views": ["guardrails/sql_generation_rules.md"],
    "create_dashboards": ["guardrails/sql_generation_rules.md"],
    "create_genie_space": ["guardrails/sql_generation_rules.md"],
}

# v2: modular layout — prompts/<stage>/instructions.md + shared guardrails
_V2_STEP_PROMPT_FILES = {
    "master": "prompts/00_master_prompt.md",
    "create_data_layer": "prompts/data_layer/instructions.md",
    "create_metric_views": "prompts/metric_views/instructions.md",
    "create_dashboards": "prompts/dashboards/instructions.md",
    "create_genie_space": "prompts/genie/instructions.md",
    "generate_documentation": "prompts/documentation/instructions.md",
}
_V2_SUPPLEMENT_FILES = {
    "master": [
        "prompts/shared/agent_transport.md",
        "prompts/shared/global_guardrails.md",
        "prompts/shared/state_contract.md",
    ],
    "create_data_layer": [
        "prompts/shared/global_guardrails.md",
        "prompts/data_layer/guardrails.md",
        "prompts/data_layer/validation.md",
        "prompts/shared/state_contract.md",
        "prompts/shared/sql_generation_rules.md",
    ],
    "create_metric_views": [
        "prompts/shared/global_guardrails.md",
        "prompts/metric_views/guardrails.md",
        "prompts/metric_views/validation.md",
        "prompts/shared/state_contract.md",
        "prompts/shared/sql_generation_rules.md",
    ],
    "create_dashboards": [
        "prompts/shared/global_guardrails.md",
        "prompts/dashboards/guardrails.md",
        "prompts/dashboards/validation.md",
        "prompts/shared/state_contract.md",
        "prompts/shared/sql_generation_rules.md",
    ],
    "create_genie_space": [
        "prompts/shared/global_guardrails.md",
        "prompts/genie/guardrails.md",
        "prompts/genie/validation.md",
        "prompts/shared/state_contract.md",
        "prompts/shared/sql_generation_rules.md",
    ],
    "generate_documentation": [
        "prompts/shared/global_guardrails.md",
        "prompts/documentation/guardrails.md",
        "prompts/documentation/validation.md",
        "prompts/shared/state_contract.md",
    ],
}

# Registry: version prefix → layout dicts (default falls back to v1)
_VERSION_LAYOUTS = {
    "v1": (_V1_STEP_PROMPT_FILES, _V1_SUPPLEMENT_FILES),
    "v2": (_V2_STEP_PROMPT_FILES, _V2_SUPPLEMENT_FILES),
}


def _get_layout(version: str):
    """Return (step_files, supplement_files) for a version, defaulting to v1."""
    return _VERSION_LAYOUTS.get(version, _VERSION_LAYOUTS["v1"])


# Non-versioned supplement files (loaded from framework root, not agent_skills)
GLOBAL_SUPPLEMENT_FILES = {
    "create_dashboards": ["inputs/lakeview_dashboard_api.md"],
    "create_genie_space": ["inputs/genie_space_configuration.md"],
}


class PromptLoader:
    """Loads framework prompts from workspace files.

    Usage:
        loader = PromptLoader(workspace_service, framework_root)
        prompt = loader.load_step_prompt("create_dashboards")
        supplements = loader.load_supplements("create_dashboards")
    """

    def __init__(self, workspace_service, framework_root: str, agent_skills_version: str = "v1"):
        """Initialize prompt loader.

        Args:
            workspace_service: WorkspaceService instance for reading files.
            framework_root: Absolute workspace path to framework/ directory.
                Example: /Workspace/Users/user/project/framework
            agent_skills_version: Version of agent_skills to load (e.g. 'v1', 'v2').
        """
        self._ws = workspace_service
        self._root = framework_root
        self._version = agent_skills_version

    def load_step_prompt(self, step_name: str) -> str:
        """Load the primary prompt file for a pipeline step.

        Args:
            step_name: Pipeline step (e.g. 'create_dashboards').

        Returns:
            Full prompt content as string.

        Raises:
            FileNotFoundError: If prompt file doesn't exist.
        """
        step_files, _ = _get_layout(self._version)
        filename = step_files.get(step_name)
        if not filename:
            raise ValueError(f"Unknown step: {step_name}. Known: {list(step_files.keys())}")

        path = f"{self._root}/agent_skills/{self._version}/{filename}"
        content = self._ws.read_file(path)
        if content is None:
            raise FileNotFoundError(f"Prompt file not found: {path}")

        logger.info(f"Loaded prompt for '{step_name}' [agent_skills={self._version}]: {len(content)} chars from {path}")
        return content

    def load_supplements(self, step_name: str) -> str:
        """Load supplementary reference files for a step.

        These are the input files (lakeview_dashboard_api.md, etc.) that
        the prompt references. They're concatenated and included as additional
        context for the LLM.

        Args:
            step_name: Pipeline step name.

        Returns:
            Concatenated supplement content (empty string if none).
        """
        # Versioned supplements (guardrails etc.) from agent_skills/<version>/
        _, supplement_map = _get_layout(self._version)
        versioned_files = supplement_map.get(step_name, [])
        # Global supplements (API docs etc.) from framework root
        global_files = GLOBAL_SUPPLEMENT_FILES.get(step_name, [])

        if not versioned_files and not global_files:
            return ""

        parts = []
        for filename in versioned_files:
            path = f"{self._root}/agent_skills/{self._version}/{filename}"
            content = self._ws.read_file(path)
            if content:
                parts.append(f"--- BEGIN {filename} ---\n{content}\n--- END {filename} ---")
                logger.info(f"Loaded versioned supplement: {filename} ({len(content)} chars)")
            else:
                logger.warning(f"Versioned supplement file not found: {path}")

        for filename in global_files:
            path = f"{self._root}/{filename}"
            content = self._ws.read_file(path)
            if content:
                parts.append(f"--- BEGIN {filename} ---\n{content}\n--- END {filename} ---")
                logger.info(f"Loaded global supplement: {filename} ({len(content)} chars)")
            else:
                logger.warning(f"Global supplement file not found: {path}")

        return "\n\n".join(parts)

    def load_domain_inputs(self, domain_root: str) -> dict:
        """Load domain-specific input files (KPI spec, ERD, accelerator.yaml).

        Args:
            domain_root: Path to the KPI domain directory.
                Example: /Workspace/Users/user/project/kpi_domains/member_claims

        Returns:
            Dict with keys: kpi_spec, accelerator_yaml, erd_image_path
        """
        inputs = {}

        # KPI spec
        kpi_path = f"{domain_root}/inputs/kpi_spec.md"
        inputs["kpi_spec"] = self._ws.read_file(kpi_path) or ""

        # Accelerator config
        accel_path = f"{domain_root}/accelerator.yaml"
        inputs["accelerator_yaml"] = self._ws.read_file(accel_path) or ""

        # ERD image path (for vision model)
        inputs["erd_image_path"] = f"{domain_root}/inputs/erd.png"

        return inputs

    def build_context_vars(self, config) -> dict:
        """Build the context variables dict from accelerator config.

        These are substituted into prompt {placeholder} references.

        Args:
            config: AcceleratorConfig instance.

        Returns:
            Dict of all context variables for prompt injection.
        """
        # Derive catalog and schema from config.catalog.target ("catalog.schema" string)
        catalog_target = config.catalog.target or ""
        parts = catalog_target.split(".", 1)
        catalog_name = parts[0] if parts else ""
        schema_name = parts[1] if len(parts) > 1 else ""

        # Resolve agent_skills version — use config field, fall back to loader's version
        version = getattr(config, 'agent_skills_version', None) or self._version

        return {
            # Core identifiers
            "CATALOG": catalog_name,
            "SCHEMA": schema_name,
            "VERSION_SUFFIX": config.version_suffix or "",
            "NEXT_VERSION": str(config.version) if config.version else "",
            "OUTPUT_FOLDER": config.output_folder,
            "EXAMPLE_DIR": config.example_dir,

            # Agent skills paths (version-resolved, so prompts never hardcode v1/v2)
            "AGENT_SKILLS_VERSION": version,
            "AGENT_SKILLS_DIR": f"{self._root}/agent_skills/{version}",

            # Workspace paths
            "workspace.output_folder": config.output_folder,
            "workspace.host": config.databricks_host,
            "paths.framework_root": config.framework_root,

            # Runtime
            "sql_warehouse_id": config.sql_warehouse_id,
            "deploy_root": config.deploy_root,
        }
