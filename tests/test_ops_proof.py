import unittest
from unittest.mock import patch
from qjai_producthunt import ops_proof

class Response:
    status=202
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n): return b'{"accepted":true,"duplicate":false}'

class OpsProofTests(unittest.TestCase):
    @patch.object(ops_proof,"_oidc_token",return_value="a.b.c")
    @patch.object(ops_proof,"check_period_ready",return_value=True)
    @patch.object(ops_proof,"urlopen",return_value=Response())
    def test_only_verified_canonical_ready_emits(self,send,ready,token):
        result=ops_proof.report("2026-11-09")
        self.assertEqual(result["status"],"OPS_NOTION_READY_CONFIRMED")
        self.assertEqual(result["period"],"2026-11-09")
        ready.assert_called_once_with(source_key="producthunt:2026-11-09",
                                      unique_prefix="2026-11-09｜")
        request=send.call_args.args[0]
        self.assertEqual(request.full_url,ops_proof.INGEST_URL)
        self.assertEqual(request.method,"POST")
        self.assertIn("Bearer a.b.c",request.headers["Authorization"])
        self.assertIn(b'"job_id":"ph_not_ready"',request.data)
    @patch.object(ops_proof,"check_period_ready",return_value=False)
    @patch.object(ops_proof,"_oidc_token")
    def test_absent_ready_stops_before_identity_or_post(self,identity,ready):
        with self.assertRaisesRegex(RuntimeError,"READY missing"):
            ops_proof.report("2026-11-09")
        identity.assert_not_called()
    def test_invalid_calendar_day_rejected(self):
        with self.assertRaises(ValueError):
            ops_proof.report("2026-02-31")
    @patch.dict(ops_proof.os.environ,{"GITHUB_REPOSITORY":"not/authorized","GITHUB_REF":"refs/heads/main",
                                      "GITHUB_EVENT_NAME":"schedule"})
    def test_untrusted_runner_cannot_request_proof(self):
        with self.assertRaisesRegex(RuntimeError,"authorized production"):
            ops_proof._oidc_token()
