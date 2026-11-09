import logging
import threading
from collections.abc import Callable
from functools import partial
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal

logger = logging.getLogger(__name__)


class _MainThreadBridge(QObject):
    deliver = Signal(object)

    def __init__(self):
        super().__init__()
        self.deliver.connect(self._run, Qt.ConnectionType.QueuedConnection)

    def _run(self, callback: Callable[[], None]) -> None:
        callback()


_bridge: _MainThreadBridge | None = None


def run_async(
    fn: Callable[..., Any],
    *args: Any,
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """Run fn(*args) on a background thread and pass the outcome to a callback
    on the Qt main thread. Must be called from the main thread.

    Daemon threads are used instead of QThread: there is no Qt object whose
    destruction can race the running thread, and a request stuck in a socket
    read cannot hold up quitting the app.
    """
    global _bridge
    if _bridge is None:
        _bridge = _MainThreadBridge()
    bridge = _bridge

    def work():
        try:
            result = fn(*args)
        except Exception as e:
            logger.debug("Background task %s failed: %s", getattr(fn, "__name__", fn), e)
            if on_error is not None:
                bridge.deliver.emit(partial(on_error, e))
            return
        if on_done is not None:
            bridge.deliver.emit(partial(on_done, result))

    threading.Thread(target=work, daemon=True).start()
