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

    def test_script_strings_untouched(self):  # JS 문자열 속 style="…" 에 따옴표를 넣으면 스크립트가 깨진다
        html = """<p style="font-family:'Inter',sans-serif">a</p><script>a+='<text style="font-family:\\'Geist Mono\\',monospace">'</script>"""
        out, n = slide.rewrite_fonts(html, "Inter", "Inter", "Pretendard", "Pretendard")
        self.assertEqual(n, 1)
        self.assertIn("'Inter', 'Pretendard', sans-serif", out)
        self.assertIn(html.split("<script>")[1], out)

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

    def test_ig_families_min_aspect(self):
        cat = {"a-tall": {"family": "a", "desc": "x · 모양: t", "qa": "ok", "aspect": 0.8},
               "a-wide": {"family": "a", "desc": "x · 모양: w", "qa": "ok", "aspect": 2.5},
               "b-tall": {"family": "b", "desc": "y · 모양: t", "qa": "ok", "aspect": 0.5}}
        f = slide.ig_families(cat, min_aspect=1.3)
        self.assertEqual(f["a"]["names"], ["a-wide"])
        self.assertNotIn("b", f)  # 가로 모양이 없는 계열은 후보에서 빠진다
        self.assertEqual(len(slide.ig_families(cat)), 2)

    def test_layout_missing_is_none(self):
        # 대체할 장도 없으면 use=None — outline 은 「템플릿에 없음 — 새로 그림」으로 찍는다
        tpl = {"layouts": [{"i": 0, "layout": "cover", "label": "c"}, {"i": 1, "layout": "compare", "label": "v"}]}
        _, _, slides = slide.parse_outline("## a {quote}\n")
        self.assertIsNone(slide.map_layouts(slides, tpl)[0]["use"])


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


    def test_diagram_catalog(self):  # 직접 그린 도식 — AntV 에 없는 계열만 · 문서·예시·검증 파일이 다 있다
        cat = slide.load_diagrams()
        self.assertGreaterEqual(len(cat), 10)
        antv = set(slide.ig_families(slide.load_ig(), usable_only=False))
        for k, d in cat.items():
            self.assertNotIn(k, antv)
            self.assertTrue(os.path.exists(os.path.join(slide.DIAGRAM_DIR, "types", d["doc"])), k)
            self.assertTrue(os.path.exists(os.path.join(slide.DIAGRAM_DIR, "examples", d["example"])), k)
            if d.get("verify"):
                self.assertTrue(os.path.exists(os.path.join(slide.DIAGRAM_DIR, "verify", d["verify"])), k)
            self.assertGreaterEqual(d["aspect"], slide.IG_MIN_ASPECT, k)
        self.assertTrue(os.path.exists(os.path.join(slide.DIAGRAM_DIR, "LICENSE")))
        slope = slide.diagram_doc("slopegraph", cat)
        self.assertTrue(slope.startswith("### Slopegraph"))
        self.assertNotIn("### Ridgeline", slope)
        self.assertNotIn("## Examples", slide.diagram_doc("venn", cat))
        self.assertIn("data-role", slide.diagram_contract("waterfall", cat))

    def test_ig_on(self):  # 강조 면 위 글자색 — 바탕과 섞인 색으로 고른다(어두운 덱 주황 반투명 칸에 검은 글자가 묻혔다)
        self.assertEqual(slide.ig_on(["#E85D26"], "#111111"), ("#111111", 0.9))
        self.assertEqual(slide.ig_on(["#1E2BFA"], "#FDFAE7"), ("#FFFFFF", 0.75))
        self.assertEqual(slide.ig_on(["var(--x)"], "#111111"), (None, None))
        self.assertIn("--ms-ig-on-from: 0.9;", slide.ig_on_var(["#E85D26"], "#111111"))

    def test_verify_diagram_waterfall(self):  # 덱 변수 색·한글 이름·20px 라벨에서 합계 보존을 잡는다
        def svg(end):
            return ('<svg viewBox="0 0 600 340">'
                    '<rect x="60" y="200" width="100" height="100" fill="currentColor" stroke="currentColor" data-role="total" data-value="10" data-name="시작"/>'
                    '<text x="110" y="192" font-size="24" text-anchor="middle">10</text>'
                    '<line x1="160" y1="200" x2="200" y2="200" stroke="currentColor" data-carry="10"/>'
                    '<rect x="200" y="150" width="100" height="50" fill="var(--ms-ig-1)" stroke="var(--ms-ig-1)" data-role="delta" data-value="+5" data-name="신규"/>'
                    '<text x="250" y="142" font-size="24" text-anchor="middle">+5</text>'
                    '<line x1="300" y1="150" x2="340" y2="150" stroke="currentColor" data-carry="15"/>'
                    f'<rect x="340" y="150" width="100" height="150" fill="currentColor" stroke="currentColor" data-role="total" data-value="{end}" data-name="끝"/>'
                    f'<text x="390" y="142" font-size="24" text-anchor="middle">{end}</text></svg>')
        self.assertEqual(slide.verify_diagram("waterfall", svg(15)), [])
        bad = slide.verify_diagram("waterfall", svg(16))
        self.assertTrue(bad and any("conserve" in m for m in bad), bad)
        self.assertEqual(slide.verify_diagram("venn", "<svg></svg>"), [])  # 검증 없는 계열


class Synopsis(unittest.TestCase):
    """시놉시스 전략 — 원고 → (Jev) 전략 → 개요. Jev 호출 없이 데이터·점검·기본값만."""

    def setUp(self):
        self.syns = slide.load_synopses()

    def test_archive_fields(self):  # 전략 파일마다 필수 칸 · 레이아웃은 닫힌 목록 · 비트 id 겹침 없음
        self.assertGreaterEqual(len(self.syns), 40)
        for k, s in self.syns.items():
            for f in slide.SYN_FIELDS:
                self.assertIn(f, s, f"{k}.{f}")
            self.assertEqual(k, s["slug"])
            ids = [b["id"] for b in s["beats"]]
            self.assertEqual(len(ids), len(set(ids)), k)
            self.assertTrue(any(b["required"] for b in s["beats"]), k)
            for b in s["beats"]:
                self.assertIn(b["layout"], slide.LAYOUTS, f"{k}.{b['id']}")
            for x in s["layout_prefer"]:
                self.assertIn(x, slide.LAYOUTS, k)
            self.assertIn(slide.syn_knobs(s)["summary"], ("front", "end", "none"), k)
            self.assertNotIn("p8", slide.synopsis_desc(s))  # Jev 로 가는 설명에 원칙 PDF 쪽 번호가 섞이지 않게

    def test_examples_pass_own_checks(self):  # 전략의 예시 개요는 그 전략 기준 점검을 경고 없이 통과한다
        for k, s in self.syns.items():
            meta, sec, sl = slide.parse_outline(s["example"])
            self.assertEqual(meta.get("synopsis"), k)
            warns = [i["code"] for i in slide.check_outline(meta, sec, sl, s) if i["level"] != "info"]
            self.assertEqual(warns, [], k)

    def test_knobs_change_checks(self):  # 같은 개요라도 전략 기준이 바뀌면 경고가 바뀐다
        meta, sec, sl = slide.parse_outline(OUTLINE)
        base = [i["code"] for i in slide.check_outline(meta, sec, sl)]
        apple = [i["code"] for i in slide.check_outline(meta, sec, sl, self.syns["apple-keynote"])]
        bluf = [i["code"] for i in slide.check_outline(meta, sec, sl, self.syns["bluf-report"])]
        self.assertEqual(base.count("too-many-points"), 1)
        self.assertEqual(apple.count("too-many-points"), 2)  # 키노트는 근거 1개 — 근거 둘인 첫 장도 걸린다
        self.assertIn("few-images", apple)
        self.assertNotIn("no-front-summary", bluf)  # 3장짜리라 끝 요약도 첫 세 장 안
        five = "# 가\n## 하나 {points}\n## 둘 {chart}\n## 셋 {chart}\n## 넷 {points}\n## 끝으로 정리 {summary}\n"
        m5, s5, l5 = slide.parse_outline(five)
        self.assertIn("no-front-summary", [i["code"] for i in slide.check_outline(m5, s5, l5, self.syns["bluf-report"])])  # BLUF 는 결론이 앞에
        self.assertNotIn("no-summary", [i["code"] for i in slide.check_outline(m5, s5, l5)])

    def test_pick_order_without_jev(self):
        r = slide.pick_synopsis("아무 원고", use_jev=False)
        self.assertEqual((r["synopsis"], r["how"]), (slide.DEFAULT_SYNOPSIS, "default"))
        r = slide.pick_synopsis("---\nsynopsis: ted-big-idea\n---\n# a\n## b", use_jev=False)
        self.assertEqual((r["synopsis"], r["how"]), ("ted-big-idea", "outline"))
        r = slide.pick_synopsis("---\nsynopsis: ted-big-idea\n---\n", synopsis="vc-pitch", use_jev=False)
        self.assertEqual(r["how"], "user")
        with self.assertRaises(SystemExit):
            slide.pick_synopsis("x", synopsis="없는-전략", use_jev=False)

    def test_skeleton_roundtrip(self):  # 빈 개요는 다시 읽으면 전략의 비트 수·레이아웃 그대로
        s = self.syns["consulting-pyramid"]
        meta, sec, sl = slide.parse_outline(slide.synopsis_skeleton(s, {"title": "제목"}))
        self.assertEqual(meta["synopsis"], "consulting-pyramid")
        self.assertEqual([x["tag"] for x in sl], [b["layout"] for b in s["beats"]])
        self.assertEqual(sec, list(dict.fromkeys(b["section"] for b in s["beats"])))

    def test_beat_issues(self):
        s = self.syns["apple-keynote"]
        judged = [{"n": 1, "beat": "hook", "beat_confidence": 0.9}, {"n": 2, "beat": "three", "beat_confidence": 0.9},
                  {"n": 3, "beat": "villain", "beat_confidence": 0.9}, {"n": 4, "beat": "reveal", "beat_confidence": 0.2}]
        codes = {i["code"]: i["msg"] for i in slide.beat_issues(s, judged)}
        self.assertIn("공개", codes["beat-missing"])  # 확신 낮은 판정은 빼고 본다
        self.assertIn("beat-order", codes)

    def test_script_excerpt_keeps_tail(self):
        t = "가" * 9000 + "요청"
        self.assertTrue(slide.script_excerpt(t).endswith("요청"))
        self.assertLessEqual(len(slide.script_excerpt(t)), 6020)


class Shots(unittest.TestCase):
    def test_fit_and_capture_scripts(self):
        self.assertIn("window.metaSlideFit", slide.META_JS)
        self.assertIn("pushedOut", slide.META_JS)
        self.assertIn("finish()", slide.FINISH_ANIM_JS)
        self.assertIn("const deco", slide.CHECK_JS)
        self.assertIn("msDiagram", slide.CHECK_JS)  # 직접 그린 도식 이름
        self.assertIn("title, desc", slide.CHECK_JS)  # 그려지지 않는 접근성 글은 글자 크기 검사에서 뺀다
        self.assertIn(".ms-ig[data-ms-diagram] svg", slide.META_CSS)  # 도식 SVG 에 덱 서체

    def test_layout_repeats(self):
        flow = {"sig": "div.fl>div.nd", "img": 0, "text": 200}
        sigs = [(n, flow) for n in (3, 5, 7, 9)] + [(4, {"sig": "div.fl>div.nd", "img": 1, "text": 200}),  # 큰 실제 화면 장은 뺀다
                                                    (6, {"sig": "div.fl>div.nd", "img": 0, "text": 40}),   # 간지·한 문장 장도 뺀다
                                                    (8, {"sig": "ig:chart-pie", "img": 0, "text": 200})]
        self.assertEqual(slide.layout_repeats(sigs), [("div.fl>div.nd", [3, 5, 7, 9])])
        self.assertEqual(slide.layout_repeats(sigs[:3]), [])  # 세 장까지는 괜찮다
        self.assertIn("ig:", slide.LAYOUT_SIG_JS)


class KeyStore(unittest.TestCase):
    def test_file_backend_roundtrip(self):  # 키체인·자격 증명 관리자를 끄고 파일 저장소만(모든 OS 공통 경로)
        import jev
        d = tempfile.mkdtemp()
        saved = (jev._mac, jev._win_write, jev._win_read, jev._win_delete, jev.KEY_DIR)
        try:
            jev._mac, jev._win_write, jev._win_read, jev._win_delete = (lambda: False), (lambda t, a, v: False), (lambda t: None), (lambda t: False)
            jev.KEY_DIR = jev.Path(d)
            f = jev.Path(d) / "typesafe-jev" / "key"
            self.assertEqual(jev.save_key(" test-key-0123456789 "), str(f))
            self.assertEqual(jev.stored_key()[0], "test-key-0123456789")
            if os.name != "nt":
                self.assertEqual(os.stat(f).st_mode & 0o777, 0o600)
            fish = jev.save_secret("fish-audio", "FISH_AUDIO_API_KEY", "fish-key-0123456789")  # 서비스마다 따로
            self.assertTrue(fish.endswith(os.path.join("fish-audio", "key")))
            self.assertEqual(jev.stored_secret("fish-audio", "FISH_AUDIO_API_KEY")[0], "fish-key-0123456789")
            self.assertEqual(jev.forget_key(), [str(f)])
            self.assertEqual(jev.stored_key(), (None, ""))
            self.assertEqual(jev.stored_secret("fish-audio", "FISH_AUDIO_API_KEY")[0], "fish-key-0123456789")  # 다른 키는 그대로
            with self.assertRaises(jev.JevError):
                jev.save_key("bad\nkey")
        finally:
            jev._mac, jev._win_write, jev._win_read, jev._win_delete, jev.KEY_DIR = saved
            shutil.rmtree(d)


class Setup(unittest.TestCase):
    def test_slide_asks_jev_only(self):  # meta-slide 에는 narrate/ 가 없다 — Fish 키를 묻지 않는다
        import setup
        self.assertEqual(setup.plugin_keys(), ["jev"])


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

    def test_tagged_nodes(self):  # 태그 기기는 tailnet 공용 UserID 를 함께 쓴다 — 같은 계정으로 보지 않는다
        import localnet
        peers = {"t": {"UserID": 1, "TailscaleIPs": ["100.4.4.4"], "Tags": ["tag:server"]},
                 "a": {"UserID": 1, "TailscaleIPs": ["100.2.2.2"]}}
        tagged_self = {"Self": {"UserID": 1, "TailscaleIPs": ["100.1.1.1"], "Tags": ["tag:server"]}, "Peer": peers}
        self.assertTrue(localnet.refuse_reason(tagged_self))
        self.assertIsNone(localnet.allowlist(tagged_self)[0])
        ok = {"Self": {"UserID": 1, "TailscaleIPs": ["100.1.1.1"]}, "Peer": peers}
        self.assertIsNone(localnet.refuse_reason(ok))
        self.assertNotIn("100.4.4.4", localnet.allowlist(ok)[3])
        self.assertIn("100.2.2.2", localnet.allowlist(ok)[3])
        self.assertTrue(localnet.refuse_reason({}))

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
            self.assertEqual(len(data["synopses"]), len(slide.load_synopses()))
            self.assertIn("viewSynopses", html)
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
            slide.cmd_new([dest, "--template", "broadside", "--color", "financial-dashboard",
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
            for f in ("meta-slide.js", "infographics/infographic.min.js", "infographics/icons.js"):  # deck-stage.js 는 그 런타임을 쓰는 템플릿만
                self.assertTrue(os.path.exists(os.path.join(dest, f)), f)
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main(verbosity=1)
