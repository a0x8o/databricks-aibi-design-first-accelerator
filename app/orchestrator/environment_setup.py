"""EnvironmentSetup — Step 0: Prepare workspace for pipeline execution.

Handles clean start (delete + recreate output folder), creates target
schema if needed, and verifies service connectivity.

Design notes:
    - This is deterministic (no LLM calls)
    - Respects pipeline.clean_start setting
    - Never drops source catalog/schema (only target for clean_start)
    - Creates output directory structure
    - Phase-aware: execution driven by pipeline_step_phases_config table
    - Supports resume from failed phase without re-running completed phases

See docs/design_phase2.md Section 4.3, master_prompt.md Step 0.
"""

import logging
import time
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class EnvironmentSetup:
    """Pipeline Step 0: Environment preparation.

    Phase-aware step. Phases are driven by pipeline_step_phases_config:
        setup_env (0) -> verify connectivity, clean start, create schemas

    Supports:
        - Phase-level progress events via phase_callback
        - Resume from failed phase (skips completed phases)
    """

    # Phase name -> handler method name (ordered)
    # Split into distinct phases so the UI accordion shows granular progress.
    PHASE_HANDLERS = {
        "verify_connectivity": "_phase_verify_connectivity",
        "prepare_workspace":   "_phase_prepare_workspace",
        "setup_schemas":       "_phase_setup_schemas",
    }

    def __init__(self, config, services: dict):
        """Initialize step with config and services.

        Args:
            config: AcceleratorConfig instance.
            services: Dict of service instances (workspace, sql, etc.).
        """
        self._config = config
        self._ws = services["workspace"]
        self._sql = services["sql"]
        # Inter-phase context
        self._ctx = {"artifacts": []}

    def execute(self, phases=None, resume_from_phase=None,
                phase_callback: Optional[Callable] = None) -> list:
        """Execute the environment setup step.

        Args:
            phases: Ordered list of phase dicts from pipeline_step_phases_config.
                    Falls back to PHASE_HANDLERS keys if None (backward compat).
            resume_from_phase: Phase name to resume from (skips prior phases).
            phase_callback: Callable(phase_name, event, **kwargs) for progress.

        Returns:
            List of created artifact paths.

        Raises:
            Exception: If setup fails (connectivity, permissions).
        """
        # Reset context
        self._ctx = {"artifacts": []}

        # Determine phase list
        if phases:
            phase_names = [p["phase_name"] if isinstance(p, dict) else p for p in phases]
        else:
            phase_names = list(self.PHASE_HANDLERS.keys())

        # Find resume index
        resume_index = 0
        if resume_from_phase:
            try:
                resume_index = phase_names.index(resume_from_phase)
            except ValueError:
                logger.warning(f"Resume phase '{resume_from_phase}' not found, running all")
                resume_index = 0

        # Execute phases
        for i, phase_name in enumerate(phase_names):
            if i < resume_index:
                if phase_callback:
                    phase_callback(phase_name, "skipped")
                continue

            # Clear phase detail before each phase
            self._ctx.pop('_phase_detail', None)

            if phase_callback:
                phase_callback(phase_name, "started",
                               current_task=f'Running {phase_name.replace("_", " ")}')

            start_ms = time.time() * 1000
            try:
                self._run_phase(phase_name)
                duration_ms = int(time.time() * 1000 - start_ms)

                # Extract rich detail set by the phase handler
                detail = self._ctx.pop('_phase_detail', {})

                if phase_callback:
                    phase_callback(phase_name, "completed",
                                   duration_ms=duration_ms,
                                   artifacts=self._ctx["artifacts"],
                                   happenings=detail.get('happenings'),
                                   findings=detail.get('findings'),
                                   stats=detail.get('stats'),
                                   current_task=detail.get('current_task'))
            except Exception as exc:
                duration_ms = int(time.time() * 1000 - start_ms)
                if phase_callback:
                    phase_callback(phase_name, "failed",
                                   duration_ms=duration_ms,
                                   error=str(exc),
                                   error_detail=self._format_error_detail(exc))
                raise

        return self._ctx["artifacts"]

    # ------------------------------------------------------------------
    # Phase dispatcher
    # ------------------------------------------------------------------

    def _run_phase(self, phase_name: str) -> None:
        """Dispatch to the handler for a given phase."""
        handler_name = self.PHASE_HANDLERS.get(phase_name)
        if not handler_name:
            raise ValueError(f"Unknown phase: {phase_name}")
        handler = getattr(self, handler_name)
        handler()

    @staticmethod
    def _format_error_detail(exc: Exception) -> str:
        """Format full traceback for error persistence."""
        import traceback
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    # ------------------------------------------------------------------
    # Phase handler methods
    # ------------------------------------------------------------------

    def _phase_verify_connectivity(self) -> None:
        """Phase 1: Verify SQL warehouse is reachable."""
        self._verify_connectivity()
        warehouse_id = getattr(self._config, 'sql_warehouse_id', '?') or '?'
        self._ctx['_phase_detail'] = {
            'current_task': 'SQL warehouse health check',
            'happenings': [
                f'Connecting to SQL warehouse {warehouse_id[:12]}...',
                'Executed SELECT 1 AS health_check',
                'Warehouse responded successfully',
            ],
            'findings': [
                f'Warehouse ID: {warehouse_id}',
                'Connectivity: OK',
            ],
            'stats': {},
        }
        logger.info("Phase verify_connectivity: complete")

    def _phase_prepare_workspace(self) -> None:
        """Phase 2: Clean start (if enabled) and create output directories."""
        output = self._config.output_folder
        clean_start = self._config.pipeline.clean_start
        happenings = []
        findings = []

        if clean_start:
            self._clean_output_folder()
            happenings.append(f'Cleaned output folder: .../{output.split("/")[-1]}')
            self._clean_target_schema()
            target = getattr(self._config.catalog, 'target', '') or ''
            if target:
                happenings.append(f'Dropped and recreated schema: {target}')
                findings.append(f'Schema recreated: {target}')
        else:
            happenings.append('Clean start disabled — preserving existing outputs')
            findings.append('Clean start: off (incremental)')

        self._create_output_structure()
        self._ctx["artifacts"].append(output)
        happenings.append(f'Created output directories: .../{output.split("/")[-1]}/')

        # List subdirs created
        subdirs = ['notebooks/', 'manifests/', 'metric_views/']
        findings.append(f'Output subdirs: {" ".join(subdirs)}')

        self._ctx['_phase_detail'] = {
            'current_task': 'Preparing workspace directories',
            'happenings': happenings,
            'findings': findings,
            'stats': {'clean_start': 1 if clean_start else 0},
        }
        logger.info("Phase prepare_workspace: complete")

    def _phase_setup_schemas(self) -> None:
        """Phase 3: Ensure target and source schemas exist."""
        happenings = []
        findings = []

        target = getattr(self._config.catalog, 'target', '') or ''
        source = getattr(self._config.catalog, 'source', '') or ''
        greenfield = getattr(self._config.data_source, 'greenfield_enabled', False)

        if target:
            self._ensure_target_schema()
            happenings.append(f'Ensured target schema: {target}')
            findings.append(f'Target schema: {target}')
        else:
            happenings.append('No target schema configured')

        if greenfield and source:
            self._ensure_source_schema()
            happenings.append(f'Ensured source schema: {source}')
            findings.append(f'Source schema: {source}')
        else:
            if greenfield:
                happenings.append('Greenfield mode, no source schema override')
            else:
                happenings.append(f'Using existing source: {source or "(default)"}')
                if source:
                    findings.append(f'Source schema: {source}')

        self._ctx['_phase_detail'] = {
            'current_task': 'Setting up catalog schemas',
            'happenings': happenings,
            'findings': findings,
            'stats': {},
        }
        logger.info("Phase setup_schemas: Environment setup complete")

    # ------------------------------------------------------------------
    # Internal Methods
    # ------------------------------------------------------------------

    def _verify_connectivity(self) -> None:
        """Verify SQL warehouse is reachable."""
        logger.info("Verifying SQL warehouse connectivity...")
        result = self._sql.execute_and_wait("SELECT 1 AS health_check", timeout_s=30.0)
        if result.status != "SUCCEEDED":
            raise RuntimeError(
                f"SQL warehouse not reachable (status={result.status}). "
                f"Check warehouse ID: {self._config.sql_warehouse_id}"
            )
        logger.info("SQL warehouse connectivity verified")

    def _clean_output_folder(self) -> None:
        """Delete and recreate the output folder."""
        output = self._config.output_folder
        logger.info(f"Clean start: removing output folder {output}")
        self._ws.ensure_clean_directory(output)

    def _clean_target_schema(self) -> None:
        """Drop and recreate the target schema (for metric views)."""
        target = self._config.catalog.target
        if not target:
            return

        logger.info(f"Clean start: dropping target schema {target}")
        catalog, schema = target.split(".", 1)
        self._sql.execute_and_wait(
            f"DROP SCHEMA IF EXISTS {target} CASCADE",
            timeout_s=60.0
        )
        self._sql.execute_and_wait(
            f"CREATE SCHEMA IF NOT EXISTS {target}",
            timeout_s=30.0
        )
        logger.info(f"Target schema recreated: {target}")

    def _create_output_structure(self) -> None:
        """Create the output directory tree."""
        output = self._config.output_folder
        # Explicitly create the output root first (write_file needs parent to exist)
        self._ws.mkdirs(output)
        subdirs = [
            f"{output}/notebooks",
            f"{output}/manifests",
            f"{output}/metric_views",
        ]
        for subdir in subdirs:
            self._ws.mkdirs(subdir)
        logger.info(f"Output structure created: {output}/")

    def _ensure_target_schema(self) -> None:
        """Create target schema if it does not exist.

        For versioned runs, source and target point to the same schema
        (aibi_{domain}_v{N}), so this is a no-op if source already created it.
        """
        target = self._config.catalog.target
        if not target:
            return
        self._sql.execute_and_wait(
            f"CREATE SCHEMA IF NOT EXISTS {target}",
            timeout_s=30.0
        )
        logger.info(f"Target schema ensured: {target}")

    def _ensure_source_schema(self) -> None:
        """Create source schema (SP becomes owner automatically).

        For versioned runs the schema is aibi_{domain}_v{N} — freshly
        created by the SP, so the SP owns it with full privileges.
        No explicit GRANTs are needed.
        """
        source = self._config.catalog.source
        if not source:
            return
        self._sql.execute_and_wait(
            f"CREATE SCHEMA IF NOT EXISTS {source}",
            timeout_s=30.0
        )
        logger.info(f"Source schema ensured: {source}")
