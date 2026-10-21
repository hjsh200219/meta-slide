#!/usr/bin/env python3
"""색 체계 data/colors.json 을 만든다 — ui-ux-pro-max colors.csv(MIT, nextlevelbuilder/ui-ux-pro-max-skill) 161종.

  python3 build_colors.py <colors.csv>
역할: primary(주색) · secondary · accent(강조) · bg(바탕) · fg(글자) · card · muted · muted_fg · border (+ on_*).
scheme 은 바탕 밝기로 light/dark. 원본이 WCAG 대비를 맞춰 둔 값이다(Notes 참고).
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROLE = {"Primary": "primary", "On Primary": "on_primary", "Secondary": "secondary", "On Secondary": "on_secondary",
        "Accent": "accent", "On Accent": "on_accent", "Background": "bg", "Foreground": "fg", "Card": "card",
        "Card Foreground": "card_fg", "Muted": "muted", "Muted Foreground": "muted_fg", "Border": "border"}


def lum(h):
    h = h.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def main(path):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        name = r["Product Type"].strip()
        cid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        roles = {v: r[k].strip().upper() for k, v in ROLE.items() if re.fullmatch(r"#[0-9A-Fa-f]{6}", r[k].strip())}
        if "border" not in roles and r["Border"].strip().startswith("rgba("):
            roles["border"] = r["Border"].strip()  # 어두운 체계는 반투명 선
        if len(roles) < len(ROLE):
            continue
        out[cid] = {"name": name, "scheme": "dark" if lum(roles["bg"]) < 0.2 else "light", **roles,
                    "notes": re.sub(r"\s*\[.*?\]\s*", " ", r.get("Notes", "")).strip()}
    dst = os.path.join(HERE, "data", "colors.json")
    json.dump({"_source": "ui-ux-pro-max-skill colors.csv (MIT) — data/LICENSE-ui-ux-pro-max-colors", "systems": out},
              open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"색 체계 {len(out)}종 (dark {sum(1 for v in out.values() if v['scheme'] == 'dark')}) → {dst}")


if __name__ == "__main__":
    main(sys.argv[1])
