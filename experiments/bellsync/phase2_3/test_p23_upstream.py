from __future__ import annotations

import copy
from pathlib import Path
import unittest

import p23_upstream as u

HERE = Path(__file__).resolve().parent


class P23UpstreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = u.load_ledger(
            HERE / "upstream_phase2_2_ledger.json"
        )

    def test_semantic_r1a_evidence_verifies(self):
        result = u.verify_semantic_evidence(
            self.ledger
        )
        self.assertTrue(
            result["semantic_evidence_verified"]
        )
        self.assertTrue(
            result["r1a_reconciliation_verified"]
        )
        self.assertEqual(
            result["semantic_evidence_sha256"],
            u.EXPECTED_SEMANTIC_SHA256,
        )

    def test_r1_gate_matrix_is_consistent(self):
        result = u.verify_r1_gate_consistency(
            self.ledger
        )
        self.assertTrue(
            result["r1_gate_consistency_verified"]
        )
        self.assertFalse(
            result["r1_spectral_gain_supported"]
        )

    def test_semantic_mutation_is_rejected(self):
        broken = copy.deepcopy(self.ledger)
        broken["r1a_reconciliation"][
            "pair_a_reported"
        ] += 1e-6

        with self.assertRaisesRegex(
            u.UpstreamError,
            "P23_P0_SEMANTIC_MISMATCH",
        ):
            u.verify_semantic_evidence(broken)

    def test_false_r1_gain_pass_is_rejected(self):
        broken = copy.deepcopy(self.ledger)
        broken["r1_gate_matrix"][
            "G4_PAIR_A_3REGULAR"
        ] = "PASS"

        with self.assertRaisesRegex(
            u.UpstreamError,
            "P23_P0_R1_GATE_INCONSISTENT",
        ):
            u.verify_r1_gate_consistency(broken)

    def test_source_artifact_contract_verifies_registered_r1(self):
        result = u.verify_source_artifact_contract(
            self.ledger
        )
        self.assertTrue(
            result["source_artifact_contract_verified"]
        )
        self.assertEqual(result["blockers"], [])

    def test_source_artifact_hash_mutation_is_rejected(self):
        broken = copy.deepcopy(self.ledger)
        broken["source_artifacts"]["script"]["sha256"] = "0" * 64

        result = u.verify_source_artifact_contract(broken)
        self.assertFalse(
            result["source_artifact_contract_verified"]
        )
        self.assertIn(
            "SOURCE_ARTIFACT_HASH_MISMATCH:script",
            result["blockers"],
        )

    def test_r2_or_stop_and_final_ledger_are_required(self):
        result = u.verify_series_completion(
            self.ledger
        )
        self.assertFalse(
            result["series_completion_verified"]
        )
        self.assertIn(
            "PHASE2_2_R2_OR_STOP_RECORD_MISSING",
            result["blockers"],
        )
        self.assertIn(
            "PHASE2_2_FINAL_SERIES_LEDGER_MISSING",
            result["blockers"],
        )

    def test_p23_p0_is_partial_pass_blocked(self):
        result = u.evaluate_upstream(
            self.ledger
        )

        self.assertTrue(
            result["r1a_evidence_imported"]
        )
        self.assertEqual(
            result["upstream_gate_status"],
            "PARTIAL_PASS_BLOCKED",
        )
        self.assertFalse(
            result["upstream_phase2_2_verified"]
        )
        self.assertFalse(
            result[
                "phase2_3_stochastic_execution_authorized"
            ]
        )
        self.assertFalse(
            result[
                "phase2_3_confirmatory_execution_authorized"
            ]
        )


if __name__ == "__main__":
    unittest.main()
