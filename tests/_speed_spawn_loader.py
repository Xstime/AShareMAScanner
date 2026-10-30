"""Import the actual .pyw under a stable importable module name for spawn tests."""
from importlib.machinery import SourceFileLoader
from pathlib import Path

_source = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.2.9.pyw"
# Execute in this module namespace so spawned workers can pickle
# _day_pool_fetch as tests._speed_spawn_loader._day_pool_fetch.
with _source.open("rb") as _stream:
    _bytes = _stream.read()
__file__ = str(_source)
exec(compile(_bytes, str(_source), "exec"), globals())
