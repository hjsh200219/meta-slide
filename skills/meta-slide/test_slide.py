#!/usr/bin/env python3
"""slide.py 의 결정론 부분 시험(Jev·네트워크 없음). python3 test_slide.py"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slide  # noqa: E402
from slide import _read  # noqa: E402

OUTLINE = """---
title: 시험 덱
presenter: 발표자 · 의도
---
# 첫 장
## 첫 헤드라인은 결론 문장이다
- 근거 하나
- 근거 둘
## 두 번째 장 {diagram}
- a
- b
- c
- d
- e
- f
| 표 | 값 |
| a | 1 |
# 끝
## 오늘 드린 말씀 {summary}
- 요약
"""


class FontInsert(unittest.TestCase):
    def test_before_system_fonts(self):
        v = slide._kr_insert("'Inter',-apple-system,Helvetica,Arial,sans-serif", "Pretendard")
        self.assertEqual(v, "'Inter', 'Pretendard', -apple-system, Helvetica, Arial, sans-serif")

    def test_quoted_and_important(self):
        self.assertEqual(slide._kr_insert("'JetBrains Mono', monospace !important", "X"), "'JetBrains Mono', 'X', monospace !important")
        self.assertEqual(slide._kr_insert(' "Cormorant Garamond", serif', "X"), " \"Cormorant Garamond\", 'X', serif")

    def test_var_untouched(self):
        self.assertEqual(slide._kr_insert(" var(--font-body)", "X"), " var(--font-body)")

    def test_var_fallback_list(self):
        self.assertEqual(slide._kr_insert(' var(--font-mono, "IBM Plex Mono", monospace)', "X"), " var(--font-mono, \"IBM Plex Mono\", 'X', monospace)")

    def test_rewrite_style_and_attr(self):
        html = '<style>h1{font-family:"Playfair Display", serif} p{font-family:"Inter", sans-serif}</style><p style="font-family: Inter, sans-serif">x</p>'
        out, n = slide.rewrite_fonts(html, "Playfair Display", "Inter", "T", "B")
        self.assertIn("\"Playfair Display\", 'T', serif", out)
        self.assertIn("\"Inter\", 'B', sans-serif", out)
        self.assertIn("Inter, 'B', sans-serif\"", out)
        self.assertEqual(n, 3)

    def test_css_var_role(self):
        out, n = slide.rewrite_fonts(":root{--font-display:'A',serif;--font-sans:'B',sans-serif}", "A", "B", "T", "BB", whole_css=True)
        self.assertIn("--font-display:'A', 'T', serif", out)
        self.assertIn("--font-sans:'B', 'BB', sans-serif", out)

    def test_short_font_var(self):  # 이름에 font 가 없어도 값이 서체 목록이면
        out, n = slide.rewrite_fonts(":root{--fd:'Sora', sans-serif;--fb:'DM', sans-serif;--bg:#000;--x: a, b}", "Sora", "DM", "T", "B", whole_css=True)
        self.assertIn("--fd:'Sora', 'T', sans-serif", out)
        self.assertIn("--fb:'DM', 'B', sans-serif", out)
        self.assertIn("--bg:#000", out)
        self.assertIn("--x: a, b", out)
        self.assertEqual(n, 2)


class Outline(unittest.TestCase):
    def test_parse_and_checks(self):
        meta, sections, slides = slide.parse_outline(OUTLINE)
        self.assertEqual(meta["title"], "시험 덱")
        self.assertEqual(sections, ["첫 장", "끝"])
        self.assertEqual([s["tag"] for s in slides], [None, "diagram", "summary"])
        codes = {i["code"] for i in slide.check_outline(meta, sections, slides)}
        self.assertIn("too-many-points", codes)
        self.assertIn("table", codes)
        self.assertNotIn("no-summary", codes)

    def test_no_summary_warns(self):
        meta, sections, slides = slide.parse_outline("---\ntitle: t\n---\n## 하나\n- a\n")
        self.assertIn("no-summary", {i["code"] for i in slide.check_outline(meta, sections, slides)})

    def test_layout_fallback(self):
        tpl = {"layouts": [{"i": 0, "layout": "cover", "label": "c"}, {"i": 1, "layout": "points", "label": "p"}]}
        _, _, slides = slide.parse_outline("## a {table}\n## b {summary}\n")
        m = slide.map_layouts(slides, tpl)
        self.assertEqual([x["use"] for x in m], ["points", "points"])


class Colors(unittest.TestCase):
    def test_contrast(self):
        self.assertAlmostEqual(slide.contrast("#000000", "#FFFFFF"), 21.0, places=1)

    def test_colors_load_and_filter(self):
        cs = slide.load_colors()
        self.assertGreaterEqual(len(cs), 150)
        opts = slide.color_options({"scheme": "dark"})
        self.assertTrue(opts and all(c["scheme"] == "dark" for c in opts.values()))

    def test_recolor_keeps_structure(self):
        t = {"scheme": "light", "palette": {"bg": "#FFFFFF", "ink": "#111111", "accent": "#E11D48"}}
        text = ":root{--bg:#FFFFFF;--ink:#111111;--accent:#E11D48;--soft:#F3F3F3} a{color:rgba(225, 29, 72, 0.5)}"
        system = slide.load_colors()["healthcare-app"]
        m = slide.recolor_map(t, system, text)
        out = slide.apply_recolor(text, m)
        self.assertIn(system["bg"], out)          # 바탕 → 체계 바탕
        self.assertIn(system["fg"], out)          # 글자 → 체계 글자
        self.assertIn(system["primary"], out)     # 포인트 → 주색
        self.assertRegex(out, r"rgba\(\d+, \d+, \d+, 0\.5\)")  # 투명도 유지


class Assets(unittest.TestCase):
    def test_templates_have_license_and_meta(self):
        ts = slide.load_templates()
        self.assertGreaterEqual(len(ts), 35)
        for slug, t in ts.items():
            self.assertTrue(os.path.exists(os.path.join(t["dir"], "template.html")), slug)
            if not t["house"] and "-" in slug and slug.split("-")[0] in ("hp", "ns", "fe", "fs", "sw", "vc", "ve", "pa", "hd", "kd", "psg", "pm", "os"):
                self.assertTrue(os.path.exists(os.path.join(t["dir"], "LICENSE")), slug)

    def test_fonts_no_gulim_batang(self):
        names = " ".join(f["name"] for f in slide.load_fonts().values())
        self.assertNotIn("굴림", names)
        self.assertNotRegex(names, r"(?<!고운)바탕")

    def test_infographic_catalog(self):
        cat = slide.load_ig()
        self.assertGreaterEqual(len(cat), 250)
        fams = slide.ig_families(cat)
        self.assertTrue(all(len(v["names"]) <= 250 for v in fams.values()))
        self.assertTrue(all(cat[n].get("qa", "ok") == "ok" for v in fams.values() for n in v["names"]))
        self.assertIn("infographic compare-swot", slide.ig_example("compare-swot", cat))


class Shots(unittest.TestCase):
    def test_fit_and_capture_scripts(self):
        self.assertIn("window.metaSlideFit", slide.META_JS)
        self.assertIn("pushedOut", slide.META_JS)
        self.assertIn("finish()", slide.FINISH_ANIM_JS)
        self.assertIn("const deco", slide.CHECK_JS)


class KeyStore(unittest.TestCase):
    def test_file_backend_roundtrip(self):  # 키체인·자격 증명 관리자를 끄고 파일 저장소만(모든 OS 공통 경로)
        import jev
        d = tempfile.mkdtemp()
        saved = (jev._mac, jev._win_write, jev._win_read, jev._win_delete, jev.KEY_FILE)
        try:
            jev._mac, jev._win_write, jev._win_read, jev._win_delete = (lambda: False), (lambda k: False), (lambda: None), (lambda: False)
            jev.KEY_FILE = jev.Path(d) / "typesafe-jev" / "key"
            self.assertEqual(jev.save_key(" test-key-0123456789 "), str(jev.KEY_FILE))
            self.assertEqual(jev.stored_key()[0], "test-key-0123456789")
            if os.name != "nt":
                self.assertEqual(os.stat(jev.KEY_FILE).st_mode & 0o777, 0o600)
            self.assertEqual(jev.forget_key(), [str(jev.KEY_FILE)])
            self.assertEqual(jev.stored_key(), (None, ""))
            with self.assertRaises(jev.JevError):
                jev.save_key("bad\nkey")
        finally:
            jev._mac, jev._win_write, jev._win_read, jev._win_delete, jev.KEY_FILE = saved
            shutil.rmtree(d)


class Gallery(unittest.TestCase):
    def test_gate(self):
        import localnet
        status = {"Self": {"UserID": 1, "TailscaleIPs": ["100.1.1.1", "fd7a::1"], "DNSName": "edb-mac.tail.ts.net."},
                  "Peer": {"a": {"UserID": 1, "TailscaleIPs": ["100.2.2.2"]}, "b": {"UserID": 2, "TailscaleIPs": ["100.3.3.3"]}}}
        ip, dns, hosts, peers = localnet.allowlist(status)
        self.assertEqual((ip, dns), ("100.1.1.1", "edb-mac.tail.ts.net"))
        g = localnet.Gate(8766, hosts, peers)
        self.assertTrue(g.allowed("100.2.2.2", "edb-mac.tail.ts.net:8766"))   # 내 PC
        self.assertFalse(g.allowed("100.3.3.3", "edb-mac.tail.ts.net:8766"))  # 같은 tailnet 다른 사람
        self.assertFalse(g.allowed("127.0.0.1", "evil.com:8766"))            # DNS rebinding
        self.assertTrue(g.allowed("127.0.0.1", "127.0.0.1:8766"))
        self.assertFalse(localnet.Gate(8766).allowed("100.2.2.2", "127.0.0.1:8766"))  # --local 아니면 밖에서 못 들어옴

    def test_build_page(self):
        import serve
        d = tempfile.mkdtemp()
        try:
            html = _read(serve.build(d))
            data = serve.gallery_data()
            self.assertEqual(len(data["templates"]), len(slide.load_templates()))
            self.assertTrue(all(t["thumb"] for t in data["templates"]), [t["slug"] for t in data["templates"] if not t["thumb"]])
            self.assertEqual(len(data["igs"]), sum(1 for v in slide.load_ig().values() if v.get("qa", "ok") == "ok"))
            self.assertIn("data/infographics/meta-slide-ig.js", html)
            self.assertNotIn("</script><", html.split("const D = ")[1].split(";\nconst TABS")[0])  # 자료 안 </ 는 이스케이프
        finally:
            shutil.rmtree(d)

    def test_routes(self):
        import serve
        h = type("H", (serve.Handler,), {"root": "/r"})
        tp = lambda p: serve.Handler.translate_path(h.__new__(h), p)  # noqa: E731
        self.assertEqual(tp("/data/thumbs/x.jpg"), os.path.join(slide.DATA, "thumbs", "x.jpg"))
        self.assertEqual(tp("/data/../slide.py"), os.path.join(slide.DATA, "slide.py"))  # .. 는 버린다
        self.assertEqual(tp("/"), os.path.join("/r", "gallery"))
        self.assertEqual(tp("/preview/없는-id/deck.html"), os.path.join("/r", "_none"))


class NewDeck(unittest.TestCase):
    def test_new_injects_fonts_ig_and_color(self):
        d = tempfile.mkdtemp()
        try:
            dest = os.path.join(d, "deck")
            slide.cmd_new([dest, "--template", "cheil-dark-point", "--color", "financial-dashboard",
                           "--title-font", "pretendard", "--body-font", "noto-sans-kr"])
            html = _read(os.path.join(dest, "deck.html"))
            self.assertIn('lang="ko"', html)
            self.assertIn("infographics/meta-slide-ig.js", html)
            self.assertIn("'Pretendard'", html)
            css = _read(os.path.join(dest, "meta-slide.css"))
            self.assertIn("--ms-ig-1", css)
            self.assertIn("keep-all", css)
            meta = json.loads(_read(os.path.join(dest, "meta-slide.json")))
            self.assertEqual(meta["color"], "financial-dashboard")
            self.assertGreater(meta["recolored"], 0)
            for f in ("deck-stage.js", "meta-slide.js", "infographics/infographic.min.js", "infographics/icons.js"):
                self.assertTrue(os.path.exists(os.path.join(dest, f)), f)
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main(verbosity=1)
