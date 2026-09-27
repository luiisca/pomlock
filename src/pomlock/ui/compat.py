import io


def patch_stream_capture() -> None:
    """Fix Textual fileno returning -1 causing multiprocessing spawn errors."""
    try:
        from textual.app import _PrintCapture

        def _fileno(self: _PrintCapture) -> int:
            raise io.UnsupportedOperation("fileno")

        _PrintCapture.fileno = _fileno
    except Exception:
        pass
