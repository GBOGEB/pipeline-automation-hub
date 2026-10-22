"""Injected by harness.py via PYTHONPATH into EVERY Python process of a traced run.

Records, per process: argv, parent pid, every function called whose source lies under
TRACE_ROOT (the repo; stdlib/site-packages ignored) with call counts and first-call order,
and any uncaught exception with its traceback. Read-only observation: it never changes
arguments, return values or files other than its own JSON in TRACE_OUT.
"""
import atexit
import json
import os
import sys
import time
import traceback

_root = os.environ.get("TRACE_ROOT")
_out = os.environ.get("TRACE_OUT")
if _root and _out:
    _root = os.path.realpath(_root) + os.sep
    _skip = ("site-packages", "dist-packages", os.sep + "tracer" + os.sep)
    _calls, _order, _t0 = {}, [], time.time()
    _exc = []

    def _prof(frame, event, arg):
        if event != "call":
            return
        f = frame.f_code.co_filename
        if not f.startswith(_root) or any(s in f for s in _skip):
            return
        key = (f[len(_root):], getattr(frame.f_code, "co_qualname", frame.f_code.co_name), frame.f_code.co_firstlineno)
        n = _calls.get(key)
        if n is None:
            _order.append(key)
            _calls[key] = 1
        else:
            _calls[key] = n + 1

    _prev_hook = sys.excepthook

    def _hook(t, v, tb):
        _exc.append({"type": t.__name__, "message": str(v)[:2000],
                     "traceback": "".join(traceback.format_exception(t, v, tb))[-6000:]})
        _prev_hook(t, v, tb)

    sys.excepthook = _hook
    sys.setprofile(_prof)
    import threading
    threading.setprofile(_prof)

    @atexit.register
    def _dump():
        sys.setprofile(None)
        rec = {"pid": os.getpid(), "ppid": os.getppid(), "argv": sys.argv, "executable": sys.executable,
               "started": _t0, "seconds": round(time.time() - _t0, 3), "uncaught": _exc,
               "functions": [{"file": k[0], "qualname": k[1], "line": k[2], "calls": _calls[k], "order": i}
                             for i, k in enumerate(_order)]}
        try:
            os.makedirs(_out, exist_ok=True)
            with open(os.path.join(_out, f"proc-{os.getpid()}.json"), "w") as fh:
                json.dump(rec, fh)
        except OSError:
            pass
