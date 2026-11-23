#!/usr/bin/env python3
"""Safety tests of time budget and fallback contract; no benchmark claims."""
from __future__ import annotations
import contextlib
import io
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import selective_mix3 as m

def stage(status: str, output: str = "") -> dict:
    return {"status":status,"seconds":0.001,"stdout":output,"stderr":"","return_code":
            10 if status=="SAT" else 20 if status=="UNSAT" else None}

class SelectiveMix3Tests(unittest.TestCase):
    def solve_with(self, outcomes):
        stream=io.StringIO()
        with patch.object(m, "run_stage", side_effect=outcomes) as mocked:
            with contextlib.redirect_stdout(stream):
                code=m.solve(pathlib.Path("dummy.cnf"),pathlib.Path("/kissat"),
                             pathlib.Path("/mix2"),12.0,0.25,6.5)
        return code,stream.getvalue(),mocked

    def test_fast_sat_stops_before_mix2(self):
        code,output,runner=self.solve_with([stage("SAT","s SATISFIABLE\nv 1 -2 0\n")])
        self.assertEqual(code,10)
        self.assertEqual(runner.call_count,1)
        self.assertIn("via=kissat_probe",output)
        self.assertIn("v 1 -2 0",output)

    def test_fast_unsat_stops_before_mix2(self):
        code,output,runner=self.solve_with([stage("UNSAT","s UNSATISFIABLE\n")])
        self.assertEqual(code,20)
        self.assertEqual(runner.call_count,1)
        self.assertIn("via=kissat_probe",output)

    def test_mix2_unsat_requires_external_project_check(self):
        code,output,runner=self.solve_with([stage("TIMEOUT"),
                                            stage("UNSAT","s UNSATISFIABLE\n")])
        self.assertEqual(code,20)
        self.assertEqual(runner.call_count,2)
        self.assertIn("via=mix2_project_check_required",output)
        self.assertIn("standard_proof=none",output)

    def test_mix2_unknown_falls_back(self):
        code,output,runner=self.solve_with([stage("TIMEOUT"),stage("UNKNOWN"),
                                            stage("SAT","s SATISFIABLE\nv 1 -2 0\n")])
        self.assertEqual(code,10)
        self.assertEqual(runner.call_count,3)
        self.assertIn("via=kissat_fallback",output)

    def test_no_false_unsat_if_all_timeout(self):
        code,output,runner=self.solve_with([stage("TIMEOUT"),stage("TIMEOUT"),
                                            stage("TIMEOUT")])
        self.assertEqual(code,0)
        self.assertEqual(runner.call_count,3)
        self.assertIn("s UNKNOWN",output)

    def test_mix2_sat_without_witness_not_accepted(self):
        code,output,runner=self.solve_with([stage("TIMEOUT"),
                                            stage("SAT","s SATISFIABLE\n"),
                                            stage("TIMEOUT")])
        self.assertEqual(code,0)
        self.assertEqual(runner.call_count,3)
        self.assertIn("reason=mix2_sat_without_source_witness",output)
        self.assertIn("s UNKNOWN",output)

    def test_stage_exit_code_guard(self):
        class FakeProcess:
            stdout="s UNSATISFIABLE\n"
            stderr=""
            returncode=0
        with patch.object(m.subprocess,"run",return_value=FakeProcess()):
            r=m.run_stage(["bogus"],1)
        self.assertEqual(r["status"],"ERROR")

if __name__=="__main__":
    unittest.main()
