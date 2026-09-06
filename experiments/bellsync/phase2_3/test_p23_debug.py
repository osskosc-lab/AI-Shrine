from __future__ import annotations

import json
from pathlib import Path
import unittest
import numpy as np
import p23_debug as d

HERE = Path(__file__).resolve().parent


class P23DebugTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = d.load_manifest(HERE / "debug_manifest.json")
        cls.s = d.spectrum(cls.m["graph"]["adjacency"])
        cls.p = cls.m["parameters"]
        cls.q = cls.m["qualification"]

    def test_d0_contract_and_mutation(self):
        clone = json.loads(json.dumps(self.m))
        d.assert_manifest_unchanged(self.m, clone)

        clone["parameters"]["beta"] += 0.001
        with self.assertRaisesRegex(
            d.DebugError, "DBG_CONFIG_MUTATION"
        ):
            d.assert_manifest_unchanged(self.m, clone)

        self.assertFalse(
            self.m["execution_authorization"][
                "stochastic_phase2_3"
            ]
        )
        self.assertFalse(
            self.m["execution_authorization"][
                "confirmatory_phase2_3"
            ]
        )

    def test_d1_graph_and_eigenpairs(self):
        d.audit_spectrum(
            self.s,
            float(self.q["spectrum_tolerance"]),
        )
        d.audit_golden_p3(
            self.s,
            float(self.q["spectrum_tolerance"]),
        )
        np.testing.assert_allclose(
            self.s.values,
            [0, 1, 3],
            atol=1e-10,
            rtol=0,
        )

    def test_d1_rejects_asymmetric_graph(self):
        with self.assertRaisesRegex(
            d.DebugError, "DBG_GRAPH_INVALID"
        ):
            d.spectrum([[0, 1], [0, 0]])

    def test_d2_injection_reconstruction_equal_norm(self):
        delta = float(
            self.p["perturbation_delta"]
        )
        norms = []

        for mode in self.q["mode_numbers"]:
            x = d.inject_mode(
                np.zeros(3),
                self.s.vectors,
                int(mode),
                delta,
            )
            norms.append(float(np.linalg.norm(x)))

            d.audit_injection(
                x,
                self.s.vectors,
                int(mode),
                delta,
                float(
                    self.q["injection_tolerance"]
                ),
            )
            self.assertLessEqual(
                d.reconstruction_error(
                    x, self.s.vectors
                ),
                float(
                    self.q[
                        "reconstruction_tolerance"
                    ]
                ),
            )

        np.testing.assert_allclose(
            norms,
            [delta, delta],
            atol=1e-12,
            rtol=0,
        )

    def test_d3_one_step_linearization_and_beta_zero_coupling(self):
        x = d.inject_mode(
            np.zeros(3),
            self.s.vectors,
            2,
            float(
                self.p["perturbation_delta"]
            ),
        )

        audit = d.one_step_audit(
            x, self.s, self.p
        )
        self.assertEqual(
            audit["saturation_fraction"], 0.0
        )

        np.testing.assert_array_equal(
            d.nonlinear_coupling(
                x, self.s.W, 0.0
            ),
            np.zeros(3),
        )

    def test_d4_replay_and_beta_zero_sanity(self):
        x = d.inject_mode(
            np.zeros(3),
            self.s.vectors,
            2,
            float(
                self.p["perturbation_delta"]
            ),
        )

        t1 = d.deterministic_trace(
            x,
            self.s.W,
            float(self.p["beta"]),
        )
        t2 = d.deterministic_trace(
            x,
            self.s.W,
            float(self.p["beta"]),
        )

        self.assertEqual(
            d.trace_digest(t1),
            d.trace_digest(t2),
        )

        self.assertEqual(
            d.beta_zero_sanity(
                float(
                    self.p["local_jacobian"]
                ),
                self.s.values,
            )["spread"],
            0.0,
        )

    def test_d5_debug_pass_does_not_authorize_production(self):
        r = d.qualify(
            {g: True for g in d.DEBUG_GATES},
            upstream_verified=False,
        )

        self.assertTrue(
            r["debug_qualified"]
        )
        self.assertEqual(
            r["debug_verdict"],
            "DEBUG_QUALIFIED",
        )
        self.assertFalse(
            r[
                "stochastic_execution_authorized"
            ]
        )
        self.assertFalse(
            r[
                "confirmatory_execution_authorized"
            ]
        )
        self.assertIn(
            "PHASE2_2_LEDGER_NOT_VERIFIED",
            r["production_blockers"],
        )

    def test_d5_failure_closes_debug_gate(self):
        gates = {
            g: True for g in d.DEBUG_GATES
        }
        gates["P23-D2"] = False

        r = d.qualify(
            gates,
            upstream_verified=True,
        )

        self.assertFalse(
            r["debug_qualified"]
        )
        self.assertIn(
            "P23-D2",
            r["production_blockers"],
        )


if __name__ == "__main__":
    unittest.main()
