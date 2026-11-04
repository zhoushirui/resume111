import unittest
from pathlib import Path
from unittest.mock import patch

import backend
import launcher


class AppTests(unittest.TestCase):
    def test_parse_person(self):
        self.assertEqual(backend.parse_target_line("单位甲\t张某\t主任"),
                         ("单位甲", "张某", "主任"))
        self.assertEqual(backend.parse_target_line("单位甲 张某"),
                         ("单位甲", "张某", ""))

    def test_empty_input(self):
        self.assertFalse(backend.api_scrape(backend.ScrapeRequest(targets=" \n"))["success"])

    @patch("backend.time.sleep")
    @patch("backend.scrape_baike_data")
    def test_person_and_photo_mapping(self, scrape, sleep):
        scrape.side_effect = [("来源链接：https://example.org/one\n测试资料", "data:image/png;base64,AA==", None),
                              (None, None, "测试失败")]
        result = backend.api_scrape(backend.ScrapeRequest(targets="单位甲\t张某\t主任\n单位乙 李某 副主任"))
        self.assertTrue(result["success"])
        self.assertEqual(result["images"][0]["name"], "张某")
        self.assertIn("单位乙 李某 副主任 抓取失败", result["content"])
        self.assertEqual(scrape.call_count, 2)

    def test_only_local_app_routes(self):
        routes = {route.path for route in launcher.app.routes}
        self.assertIn("/api/scrape", routes)
        self.assertIn("/", routes)
        self.assertNotIn("/api/doubao", routes)
        self.assertNotIn("/api/task/{task_id}", routes)

    def test_packaged_page(self):
        html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("fetch('/api/scrape'", html)
        self.assertNotIn('<script src="https:', html)
        self.assertIn("采用浮动图片和四周型文字环绕", html)
        self.assertIn("不占用单独段落", html)
        self.assertIn("与右侧文字间距为0.3厘米", html)
        self.assertIn("黑体，三号（16磅），首行缩进两个字符", html)
        self.assertIn("即使整个职业生涯始终在北京，也必须写这唯一一行地点", html)
        self.assertIn("每个先后岗位对应独立履历行", html)
        self.assertIn("首次达到正处写【XX岁，正处】", html)
        self.assertIn("不能将前后北京任职合并", html)
        self.assertIn("packetPrompt_v4_", html)
        self.assertNotIn("首次地点块不另加地点行", html)
        self.assertNotIn("仅在地点变化时添加", html)
        for obsolete in ("照片独占段落", "嵌入型", "禁止浮动图片", "api/doubao"):
            self.assertNotIn(obsolete, html)


if __name__ == "__main__":
    unittest.main()
