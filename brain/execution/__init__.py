from .intent import (
    ExecutionIntent,
    ExecutionIntentBuilder,
)


class LiveExecutionDisabled(RuntimeError):
    """Raised whenever live order execution is attempted.

    APEX currently operates in PAPER_ONLY mode.
    Live exchange execution is intentionally unavailable.
    """


class ExecutionEngine:
    """Backward-compatible execution facade.

    This preserves the original APEX Brain API while the newer
    ExecutionIntentBuilder handles paper execution intents.
    """

    def __init__(self, *args, **kwargs):
        self.live_enabled = False

    def execute_live(self, *args, **kwargs):
        raise LiveExecutionDisabled(
            "Live execution is disabled. "
            "APEX currently supports PAPER_ONLY execution."
        )


__all__ = [
    "ExecutionIntent",
    "ExecutionIntentBuilder",
    "ExecutionEngine",
    "LiveExecutionDisabled",
]
