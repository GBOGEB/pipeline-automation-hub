"""The suite must give the same answer on Windows as on the Linux runners.

Native CI is Linux-only, so a platform-default codec (cp1252 on Windows) or an
OS-separator path key cannot fail there. These static checks fail on Linux too.
"""
import ast
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=sorted(p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def calls(path):
    tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
    return [n for n in ast.walk(tree) if isinstance(n,ast.Call)]


def where(path,node):
    return f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"


def has_encoding(node,positional):
    return len(node.args)>positional or any(k.arg=="encoding" for k in node.keywords)


def text_mode(node,mode_index):
    mode=node.args[mode_index] if len(node.args)>mode_index else next((k.value for k in node.keywords if k.arg=="mode"),None)
    return not (isinstance(mode,ast.Constant) and "b" in str(mode.value))


class Portability(unittest.TestCase):
    def test_sources_found(self):
        self.assertIn(ROOT/"portal_bridge.py",SOURCES)
        self.assertIn(Path(__file__).resolve(),SOURCES)

    def test_text_io_declares_encoding(self):
        bad=[]
        for path in SOURCES:
            for n in calls(path):
                f=n.func
                if isinstance(f,ast.Attribute) and f.attr=="read_text" and not has_encoding(n,0):
                    bad.append(where(path,n))
                elif isinstance(f,ast.Attribute) and f.attr=="write_text" and not has_encoding(n,1):
                    bad.append(where(path,n))
                elif isinstance(f,ast.Name) and f.id=="open" and text_mode(n,1) and not has_encoding(n,3):
                    bad.append(where(path,n))
                elif (isinstance(f,ast.Attribute) and f.attr=="open" and not (isinstance(f.value,ast.Name) and f.value.id=="os")
                      and text_mode(n,0) and not has_encoding(n,2)):
                    bad.append(where(path,n))
        self.assertEqual(bad,[],"text I/O without encoding= uses the platform codec (cp1252 on Windows)")

    def test_relative_paths_are_not_stringified_with_os_separator(self):
        bad=[where(path,n) for path in SOURCES for n in calls(path)
             if isinstance(n.func,ast.Name) and n.func.id=="str" and len(n.args)==1
             and isinstance(n.args[0],ast.Call) and isinstance(n.args[0].func,ast.Attribute)
             and n.args[0].func.attr=="relative_to"]
        self.assertEqual(bad,[],"str(p.relative_to(root)) gives backslash keys on Windows; use .as_posix()")


if __name__=="__main__":
    unittest.main()
