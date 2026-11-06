"""Offline tests for the shared article-only Notion adapter."""

import os
import unittest
from unittest.mock import patch

from qjai_producthunt import notion_sync


class NotionSyncTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "NOTION_ENABLE_SYNC": "true", "NOTION_API_KEY": "test-token-is-long-enough",
            "NOTION_PARENT_PAGE_ID": "4109e605-ccf8-81c4-accd-c19386b4a38d",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_creates_one_page_using_v2_markdown_and_digest(self):
        calls = []
        page_id = "e1f1a7d4-8f66-4df7-8831-ae957a4025a4"
        parent_id = "4109e605-ccf8-81c4-accd-c19386b4a38d"
        created_document = None

        def fake(method, path, token, payload=None):
            nonlocal created_document
            calls.append((method, path, payload))
            if method == "GET" and "/blocks/" in path and "/children" in path:
                return {"results": [], "has_more": False}
            if method == "POST":
                self.assertEqual(payload["markdown_version"], "v2")
                self.assertIn("producthunt:2026-11-01", payload["markdown"])
                self.assertIn("sha-256", payload["markdown"].lower())
                self.assertNotIn("# 原题", payload["markdown"])
                created_document = payload["markdown"]
                return {"id": page_id, "url": "https://www.notion.so/e1f1a7d48f664df78831ae957a4025a4"}
            if method == "GET" and path == f"/v1/pages/{page_id}":
                return {
                    "parent": {"type": "page_id", "page_id": parent_id},
                    "properties": {"title": {"type": "title", "title": [{"plain_text": "2026-11-01｜原题"}]}},
                }
            if method == "GET" and "/markdown?" in path:
                marker = getattr(fake, "marker", None)
                return {"object": "page_markdown", "markdown": created_document + (("\n" + marker) if marker else ""),
                        "truncated": False, "unknown_block_ids": [], "warnings": []}
            if method == "PATCH":
                fake.marker = payload["children"][0]["paragraph"]["rich_text"][0]["text"]["content"]
                return {"results": []}
            self.fail((method, path))

        with patch.object(notion_sync, "_request", side_effect=fake):
            r = notion_sync.sync_article(
                source_key="producthunt:2026-11-01",
                title="2026-11-01｜原题", unique_prefix="2026-11-01｜",
                markdown="# 原题\n\n正文",
            )
        self.assertEqual(r["result"], "created_ready")
        self.assertEqual([c[0] for c in calls], ["GET", "POST", "GET", "GET", "PATCH", "GET"])
        self.assertIn("QJAI_PUBLISH_READY", fake.marker)

    def test_readback_mismatch_never_appends_ready(self):
        page_id = "e1f1a7d4-8f66-4df7-8831-ae957a4025a4"

        def fake(method, path, token, payload=None):
            if method == "GET" and "/blocks/" in path:
                return {"results": [], "has_more": False}
            if method == "POST":
                return {"id": page_id, "url": "https://www.notion.so/page"}
            if method == "GET" and "/markdown?" in path:
                return {"object": "page_markdown", "markdown": "tampered", "truncated": False,
                        "unknown_block_ids": [], "warnings": []}
            if method == "GET":
                return {"parent": {"type": "page_id", "page_id": "4109e605-ccf8-81c4-accd-c19386b4a38d"},
                        "properties": {"title": {"type": "title", "title": [{"plain_text": "2026-11-01｜原题"}]}}}
            if method == "PATCH":
                self.fail("READY must not be appended after a failed readback")

        with patch.object(notion_sync, "_request", side_effect=fake):
            with self.assertRaisesRegex(RuntimeError, "differs"):
                notion_sync.sync_article(source_key="producthunt:2026-11-01",
                    title="2026-11-01｜原题", unique_prefix="2026-11-01｜", markdown="# 原题\n\n正文")

    def test_duplicate_no_write_after_title_change(self):
        body = "正文\n"
        digest = notion_sync.hashlib.sha256(body.encode()).hexdigest()
        marker = "QJAI_PUBLISH_READY v=1 source_key=producthunt:2026-11-01 content_sha256=" + digest
        methods = []

        def fake(method, path, token, payload=None):
            methods.append(method)
            if "/children" in path:
                return {"results": [{"type": "child_page", "id": "11111111-1111-4111-8111-111111111111", "child_page": {
                    "title": "2026-11-01｜人工改题"}}], "has_more": False}
            if "/markdown?" in path:
                return {"object": "page_markdown", "markdown": body + marker + "\n",
                        "truncated": False, "unknown_block_ids": [], "warnings": []}
            self.fail("Existing article lookup must never POST or mutate the page")

        with patch.object(notion_sync, "_request", side_effect=fake):
            result = notion_sync.sync_article(
                source_key="producthunt:2026-11-01", title="2026-11-01｜原标题",
                unique_prefix="2026-11-01｜", markdown="# 原标题\n\n内容",
            )
        self.assertEqual(result["result"], "duplicate_ready")
        self.assertEqual(methods, ["GET", "GET"])

    def test_paginated_search(self):
        calls = []
        body = "正文\n"
        digest = notion_sync.hashlib.sha256(body.encode()).hexdigest()
        marker = "QJAI_PUBLISH_READY v=1 source_key=producthunt:2026-11-01 content_sha256=" + digest

        def fake(method, path, token, payload=None):
            calls.append((method, path))
            if "/markdown?" in path:
                return {"object": "page_markdown", "markdown": body + marker + "\n",
                        "truncated": False, "unknown_block_ids": [], "warnings": []}
            if "start_cursor" not in path:
                return {"results": [], "has_more": True, "next_cursor": "next-page"}
            return {"results": [{"type": "child_page", "id": "22222222-2222-4222-8222-222222222222", "child_page": {
                "title": "2026-11-01｜旧标题"}}], "has_more": False}

        with patch.object(notion_sync, "_request", side_effect=fake):
            result = notion_sync.sync_article(
                source_key="producthunt:2026-11-01", title="2026-11-01｜题",
                unique_prefix="2026-11-01｜", markdown="内容")
        self.assertEqual(result["result"], "duplicate_ready")
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(item[0] == "GET" for item in calls))

    def test_existing_without_ready_never_counts_as_archived(self):
        methods = []
        def fake(method, path, token, payload=None):
            methods.append(method)
            if "/children" in path:
                return {"results": [{"type": "child_page", "id": "11111111-1111-4111-8111-111111111111", "child_page": {
                    "title": "2026-11-01｜不完整"}}], "has_more": False}
            if "/markdown?" in path:
                return {"object": "page_markdown", "markdown": "正文未完成",
                        "truncated": False, "unknown_block_ids": [], "warnings": []}
            self.fail("Existing partial article must never be changed")
        with patch.object(notion_sync, "_request", side_effect=fake):
            with self.assertRaisesRegex(RuntimeError, "lacks a valid READY"):
                notion_sync.sync_article(source_key="producthunt:2026-11-01",
                    title="2026-11-01｜题", unique_prefix="2026-11-01｜", markdown="正文")
        self.assertEqual(methods, ["GET", "GET"])

    def test_ambiguous_pages_fail_closed(self):
        pages = [{"type": "child_page", "id": str(i), "child_page": {"title": "2026-11-01｜标题"}} for i in (1, 2)]
        with patch.object(notion_sync, "_request", return_value={"results": pages, "has_more": False}):
            with self.assertRaisesRegex(RuntimeError, "More than one"):
                notion_sync.sync_article(source_key="producthunt:2026-11-01", title="2026-11-01｜题",
                                          unique_prefix="2026-11-01｜", markdown="内容")

    def test_malformed_listing_fails_without_creating_page(self):
        with patch.object(notion_sync, "_request", return_value={"results": []}) as send:
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                notion_sync.sync_article(source_key="producthunt:2026-11-01", title="2026-11-01｜题",
                                          unique_prefix="2026-11-01｜", markdown="正文")
        self.assertEqual(send.call_count, 1)

    def test_disabled_never_calls_api(self):
        with patch.dict(os.environ, {"NOTION_ENABLE_SYNC": "false"}), patch.object(notion_sync, "_request") as send:
            with self.assertRaises(PermissionError):
                notion_sync.sync_article(source_key="producthunt:2026-11-01", title="2026-11-01｜题",
                                          unique_prefix="2026-11-01｜", markdown="内容")
            send.assert_not_called()

    def test_monthly_identity_valid(self):
        body = "月报正文\n"
        digest = notion_sync.hashlib.sha256(body.encode()).hexdigest()
        marker = "QJAI_PUBLISH_READY v=1 source_key=trustmrr-monthly:2026-11 content_sha256=" + digest
        def fake(method, path, token, payload=None):
            if "/children" in path:
                return {"results": [{"type": "child_page", "id": "33333333-3333-4333-8333-333333333333", "child_page": {
                    "title": "2026-11｜TrustMRR 月报｜标题"}}], "has_more": False}
            if "/markdown?" in path:
                return {"object": "page_markdown", "markdown": body + marker + "\n",
                        "truncated": False, "unknown_block_ids": [], "warnings": []}
            self.fail("Existing monthly lookup must remain read-only")
        with patch.object(notion_sync, "_request", side_effect=fake):
            result = notion_sync.sync_article(
                source_key="trustmrr-monthly:2026-11",
                title="2026-11｜TrustMRR 月报｜标题",
                unique_prefix="2026-11｜TrustMRR 月报｜", markdown="正文")
        self.assertEqual(result["result"], "duplicate_ready")


if __name__ == "__main__":
    unittest.main()
