"""The suite must give the same answer on Windows as on the Linux runners.

Native CI is Linux-only, so a platform-default codec (cp1252 on Windows), a
platform-default newline (CRLF on Windows) or an OS-separator path key cannot
fail there. These static checks fail on Linux too.

They cover every tree whose generators write committed or DAG-pinned outputs
(F5 portability, Refs #870 P1b): a writer must name encoding= and newline=.
"""
import ast
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MC=ROOT.parent
TREES=(ROOT,MC/"gogreen",MC/"v2",MC/"qps-triage-ultra"/"p-process")
SOURCES=sorted(p for t in TREES for p in t.rglob("*.py") if "__pycache__" not in p.parts)
# Writers not yet converted, by mission-control path. Each is pinned by the
# CICD DAG (a change re-pins outputs owned by #931, which supersedes #858/#860)
# or is a p-process file it owns. P1b phase B converts them once it lands; an
# entry that has no finding left fails test_pending_is_not_stale.
PENDING={
    "jade_temple/portal_bridge.py",
    "jade_temple/tools/build_redtrace_data.py",
    "qps-triage-ultra/p-process/build_p_process.py",
    "qps-triage-ultra/p-process/everred/build_page.py",
    "qps-triage-ultra/p-process/p_decide.py",
    "qps-triage-ultra/p-process/package.py",
    "qps-triage-ultra/p-process/rulesets/survey.py",
    "qps-triage-ultra/p-process/rulesets/verify_rulesets.py",
    "qps-triage-ultra/p-process/tests/test_p_process.py",
}


def calls(path):
    tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
    return [n for n in ast.walk(tree) if isinstance(n,ast.Call)]


def rel(path):
    return path.relative_to(MC).as_posix()


def where(path,node):
    return f"{rel(path)}:{node.lineno}"


def has_kw(node,name,positional):
    """Named, positional, or passed in a **mapping (lf={"encoding":..,"newline":..})."""
    return len(node.args)>positional or any(k.arg in (name,None) for k in node.keywords)


def mode_arg(node,mode_index):
    return node.args[mode_index] if len(node.args)>mode_index else next((k.value for k in node.keywords if k.arg=="mode"),None)


def text_mode(node,mode_index):
    mode=mode_arg(node,mode_index)
    return not (isinstance(mode,ast.Constant) and "b" in str(mode.value))


def writes(node,mode_index):
    """True unless the mode is a constant read-only mode ('r', 'rt', default)."""
    mode=mode_arg(node,mode_index)
    return not (mode is None or isinstance(mode,ast.Constant) and not set(str(mode.value))&set("wax+"))


def file_open(node):
    """(mode index, open call) for builtin open() and Path.open(); else None.

    A method .open() whose first argument is not a mode string (urllib's
    opener.open(request)) is not file I/O.
    """
    f=node.func
    if isinstance(f,ast.Name) and f.id=="open":
        return 1
    if isinstance(f,ast.Attribute) and f.attr=="open" and not (isinstance(f.value,ast.Name) and f.value.id=="os"):
        first=node.args[0] if node.args else None
        if first is None or isinstance(first,ast.Constant) and isinstance(first.value,str):
            return 0
    return None


def encoding_findings(path):
    bad=[]
    for n in calls(path):
        f=n.func
        if isinstance(f,ast.Attribute) and f.attr=="read_text" and not has_kw(n,"encoding",0):
            bad.append(where(path,n))
        elif isinstance(f,ast.Attribute) and f.attr=="write_text" and not has_kw(n,"encoding",1):
            bad.append(where(path,n))
        else:
            i=file_open(n)
            if i is not None and text_mode(n,i) and not has_kw(n,"encoding",i+2):
                bad.append(where(path,n))
    return bad


def newline_findings(path):
    bad=[]
    for n in calls(path):
        f=n.func
        if isinstance(f,ast.Attribute) and f.attr=="write_text" and not has_kw(n,"newline",3):
            bad.append(where(path,n))
        else:
            i=file_open(n)
            if i is not None and text_mode(n,i) and writes(n,i) and not has_kw(n,"newline",i+4):
                bad.append(where(path,n))
    return bad


def separator_findings(path):
    return [where(path,n) for n in calls(path)
            if isinstance(n.func,ast.Name) and n.func.id=="str" and len(n.args)==1
            and isinstance(n.args[0],ast.Call) and isinstance(n.args[0].func,ast.Attribute)
            and n.args[0].func.attr=="relative_to"]


CHECKS=(encoding_findings,newline_findings,separator_findings)


def findings(check):
    return [b for path in SOURCES if rel(path) not in PENDING for b in check(path)]


class Portability(unittest.TestCase):
    def test_sources_found(self):
        self.assertIn(ROOT/"portal_bridge.py",SOURCES)
        self.assertIn(Path(__file__).resolve(),SOURCES)
        for tree in TREES:
            self.assertTrue(any(tree in p.parents for p in SOURCES),tree)

    def test_text_io_declares_encoding(self):
        self.assertEqual(findings(encoding_findings),[],"text I/O without encoding= uses the platform codec (cp1252 on Windows)")

    def test_text_writers_declare_newline(self):
        self.assertEqual(findings(newline_findings),[],
                         "a text writer without newline= writes CRLF on Windows; pinned bytes then differ from Linux CI")

    def test_relative_paths_are_not_stringified_with_os_separator(self):
        self.assertEqual(findings(separator_findings),[],"str(p.relative_to(root)) gives backslash keys on Windows; use .as_posix()")

    def test_pending_is_not_stale(self):
        by_rel={rel(p):p for p in SOURCES}
        self.assertEqual(sorted(PENDING-set(by_rel)),[],"PENDING names a file that no longer exists")
        clean=sorted(r for r in PENDING if not any(c(by_rel[r]) for c in CHECKS))
        self.assertEqual(clean,[],"PENDING file is portable now; drop it from PENDING")

    def test_checks_catch_platform_defaults(self):
        tree=ast.parse('Path("a").write_text(s)\nopen(p,"w",encoding="utf-8")\nPath(p).open("a")\n'
                       'open(p,encoding="utf-8")\nopener.open(request,timeout=3)\nstr(p.relative_to(root))\n')
        nodes=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        flagged=lambda pred:sorted({n.lineno for n in nodes if pred(n)})
        write_text=lambda n:isinstance(n.func,ast.Attribute) and n.func.attr=="write_text"
        self.assertEqual(flagged(lambda n:write_text(n) and not has_kw(n,"newline",3)),[1])
        self.assertEqual(flagged(lambda n:file_open(n) is not None and writes(n,file_open(n))),[2,3])
        self.assertEqual(flagged(lambda n:file_open(n) is not None and not writes(n,file_open(n))),[4])


if __name__=="__main__":
    unittest.main()
