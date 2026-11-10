import os
import unittest
from unittest.mock import patch
from qjai_producthunt import notion_sync

class ReadyGuardTests(unittest.TestCase):
    def setUp(self):
        patcher=patch.dict(os.environ,{
            "NOTION_API_KEY":"valid-unit-test-notion-token",
            "NOTION_PARENT_PAGE_ID":"4109e605-ccf8-81c4-accd-c19386b4a38d",
        })
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_is_safe_and_read_only(self):
        with patch.object(notion_sync,"_request",return_value={"results":[],"has_more":False}) as req:
            self.assertFalse(notion_sync.check_period_ready(
                source_key="producthunt:2026-11-09",unique_prefix="2026-11-09｜"))
            req.assert_called_once()
            self.assertEqual(req.call_args.args[0],"GET")

    def test_existing_ready_is_digest_verified_read_only(self):
        body="正文数据\n"
        digest=notion_sync.hashlib.sha256(body.encode()).hexdigest()
        marker="QJAI_PUBLISH_READY v=1 source_key=producthunt:2026-11-09 content_sha256="+digest
        calls=[]
        def fake(method,path,token,payload=None):
            calls.append(method)
            if "/children" in path:
                return {"results":[{"type":"child_page","id":"11111111-1111-4111-8111-111111111111",
                    "child_page":{"title":"2026-11-09｜标题"}}],"has_more":False}
            if "/markdown?" in path:
                return {"object":"page_markdown","markdown":body+marker,
                    "truncated":False,"unknown_block_ids":[],"warnings":[]}
            self.fail("Only GET permitted in READY checker")
        with patch.object(notion_sync,"_request",side_effect=fake):
            self.assertTrue(notion_sync.check_period_ready(
                source_key="producthunt:2026-11-09",unique_prefix="2026-11-09｜"))
        self.assertEqual(calls,["GET","GET"])

    def test_unsigned_existing_does_not_trigger_duplicate(self):
        def fake(method,path,token,payload=None):
            if "/children" in path:
                return {"results":[{"type":"child_page","id":"11111111-1111-4111-8111-111111111111",
                    "child_page":{"title":"2026-11-09｜未完成"}}],"has_more":False}
            return {"object":"page_markdown","markdown":"不完整文章",
                    "truncated":False,"unknown_block_ids":[],"warnings":[]}
        with patch.object(notion_sync,"_request",side_effect=fake):
            with self.assertRaisesRegex(RuntimeError,"not READY"):
                notion_sync.check_period_ready(
                    source_key="producthunt:2026-11-09",unique_prefix="2026-11-09｜")

    def test_invalid_digest_blocks_regeneration(self):
        body="正文数据\n"
        marker="QJAI_PUBLISH_READY v=1 source_key=producthunt:2026-11-09 content_sha256="+("a"*64)
        def fake(method,path,token,payload=None):
            if "/children" in path:
                return {"results":[{"type":"child_page","id":"11111111-1111-4111-8111-111111111111",
                    "child_page":{"title":"2026-11-09｜标题"}}],"has_more":False}
            return {"object":"page_markdown","markdown":body+marker,
                    "truncated":False,"unknown_block_ids":[],"warnings":[]}
        with patch.object(notion_sync,"_request",side_effect=fake):
            with self.assertRaisesRegex(RuntimeError,"digest is invalid"):
                notion_sync.check_period_ready(
                    source_key="producthunt:2026-11-09",unique_prefix="2026-11-09｜")
