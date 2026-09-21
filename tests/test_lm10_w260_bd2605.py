#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"mission-control/qps-triage-ultra/missions/validate_lm10_w260_bd2605.py"
OUT=ROOT/"mission-control/qps-triage-ultra/missions/LM-10_W260_BD260_5_TRIAGE_RECEIPT_v1.json"

def test_validator():
    cp=subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,text=True,capture_output=True,check=True)
    assert "PASS_LM10_W260_BD260_5_TRIAGE" in cp.stdout
    d=json.loads(OUT.read_text())
    assert d["status"]=="PASS_TRIAGE_VERIFICATION"
    assert d["disposition"]=="ACCEPT_BOUNDED_PROJECT_MATH_WITH_EXPLICIT_DEFER"
    assert d["authority_transfer"] is False
    assert d["formal_credit_delta"]==0
    assert d["threshold_class_counts"]=={"GOVERNANCE_IDENTITY":1,"NONE":2,"PROJECT_GOVERNED":0,"STATISTICAL":2}
    assert set(d["retained_first_reds"])=={"MANOVA_RUNTIME_NOT_PROMOTED_IN_THIS_SLICE","DEFER_NO_FINITE_MLE"}

if __name__=="__main__":
    test_validator()
    print("PASS_LM10_W260_BD260_5_TEST")
