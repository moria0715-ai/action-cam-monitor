#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_dashboard.py
─────────────────────────────────────────────────────────────────────────────
读取 data/latest.json，将真实 API 数据注入到 HTML 看板模板，
输出 index.html（直接部署到 GitHub Pages）。

使用方式:
    python generate_dashboard.py
─────────────────────────────────────────────────────────────────────────────
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta

# ── 配置 ───────────────────────────────────────────────────────────────────
DATA_PATH     = "data/latest.json"
TEMPLATE_PATH = "template.html"   # 原始看板 HTML（不含真实数据的版本）
OUTPUT_PATH   = "index.html"

BRANDS = {
    "dji":  {"name": "DJI",      "color": "#e8002d", "accent2": "#b00020"},
    "i360": {"name": "Insta360", "color": "#4f6ef7", "accent2": "#7c3aed"},
    "gp":   {"name": "GoPro",    "color": "#00aaff", "accent2": "#0077cc"},
}

COUNTRIES = {
    "de": {"name": "德国",   "flag": "🇩🇪"},
    "fr": {"name": "法国",   "flag": "🇫🇷"},
    "it": {"name": "意大利", "flag": "🇮🇹"},
    "es": {"name": "西班牙", "flag": "🇪🇸"},
    "uk": {"name": "英国",   "flag": "🇬🇧"},
}

PLATFORM_KEYS = {
    "YouTube": "yt", "TikTok": "tt", "Instagram": "ig",
    "Facebook": "fb", "Twitter": "tw", "Reddit": "rd",
}


def load_data():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"数据文件不存在: {DATA_PATH}\n请先运行 fetch_data.py")
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_daily_db_js(data):
    """
    把当天数据构建成 JS DB 格式（与模板里的 DB 对象格式完全一致）。
    返回一段可注入到 <script> 里的 JS 字符串。
    """
    date_str = data["date"]      # YYYY-MM-DD
    brands   = data["brands"]

    lines = []
    for brand_key, brand_data in brands.items():
        # 每个品牌的 DB 格式: { "YYYY-MM-DD": { de: {yt,tt,ig,fb,tw,rd,sent}, ... } }
        db_obj = {}
        entry = {}
        for country_key, country_data in brand_data.items():
            mentions   = country_data.get("mentions", 0)
            sent_pos   = country_data.get("sentiment_pos", 60)
            by_plat    = country_data.get("by_platform", {})

            # 按平台分配声量（如果 API 没有平台细分就按历史比例估算）
            plat_vals = {}
            total_plat = sum(by_plat.values())
            if total_plat > 0:
                for plat_name, js_key in PLATFORM_KEYS.items():
                    plat_vals[js_key] = by_plat.get(plat_name, 0)
            else:
                # 按各品牌历史平台比例估算
                ratios = {
                    "dji":  {"yt":.351,"tt":.250,"ig":.179,"fb":.077,"tw":.038,"rd":.020},
                    "i360": {"yt":.324,"tt":.287,"ig":.222,"fb":.080,"tw":.050,"rd":.037},
                    "gp":   {"yt":.338,"tt":.260,"ig":.169,"fb":.080,"tw":.040,"rd":.031},
                }
                r = ratios.get(brand_key, ratios["dji"])
                for js_key, ratio in r.items():
                    plat_vals[js_key] = round(mentions * ratio)

            entry[country_key] = dict(plat_vals, sent=sent_pos)

        db_obj[date_str] = entry

        # 生成 JS 变量名（与模板一致：DB for dji，DB_I360 for i360，DB_GP for gp）
        varmap = {"dji": "DB", "i360": "DB_I360", "gp": "DB_GP"}
        varname = varmap[brand_key]
        lines.append(f"// ── {BRANDS[brand_key]['name']} 新增当日数据 ──────────────")
        lines.append(f"Object.assign({varname}, {json.dumps({date_str: entry}, ensure_ascii=False)});")
        lines.append("")

    return "\n".join(lines)


def format_date_cn(date_str):
    """2026-03-18 → 3月18日"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.month}月{d.day}日"


def inject_into_html(template_html, data):
    """
    将实时数据注入 HTML 模板：
    1. 在 </body> 前插入数据注入 JS 代码块
    2. 更新顶部日期范围显示
    3. 更新页脚生成时间
    """
    date_str   = data["date"]
    date_cn    = format_date_cn(date_str)
    now_str    = datetime.now(timezone(timedelta(hours=8))).strftime("%Y年%m月%d日 %H:%M")

    # ── 1. 生成数据注入脚本 ───────────────────────────────────────────────
    db_js = build_daily_db_js(data)

    inject_script = f"""
<script>
// ═══════════════════════════════════════════════════════════════════
// 自动注入数据 — 由 generate_dashboard.py 在 {now_str} (UTC+8) 生成
// 数据来源：Brandwatch / Meltwater API · 日期：{date_str}
// ═══════════════════════════════════════════════════════════════════
(function() {{
  // 等待各品牌 DB 对象初始化完成后注入
  function injectData() {{
    {db_js}

    // 更新日期范围选择器默认值
    var dpEnd = document.getElementById('dp-end');
    if (dpEnd) dpEnd.value = '{date_str}';

    // 重新触发 KPI 计算
    if (typeof applyDateRange_dji  === 'function') applyDateRange_dji(document.getElementById('dp-start').value, '{date_str}');
    if (typeof applyDateRange_i360 === 'function') applyDateRange_i360(document.getElementById('dp-start').value, '{date_str}');
    if (typeof applyDateRange_gp   === 'function') applyDateRange_gp(document.getElementById('dp-start').value, '{date_str}');
    if (typeof renderCompareCharts === 'function') setTimeout(renderCompareCharts, 200);
    if (typeof renderCmpWeekly     === 'function') setTimeout(renderCmpWeekly, 300);
  }}

  // DOM 加载后执行
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', injectData);
  }} else {{
    injectData();
  }}
}})();
</script>
"""

    # ── 2. 更新顶部日期范围显示文字 ──────────────────────────────────────
    html = template_html
    html = re.sub(
        r'(id="date-range-display">[^<]*)',
        f'id="date-range-display">{date_cn} 数据已更新 · 自动采集',
        html
    )

    # ── 3. 更新 dp-end 默认值 ────────────────────────────────────────────
    html = re.sub(
        r'(id="dp-end"[^>]*value=")[0-9\-]+"',
        f'\\g<1>{date_str}"',
        html
    )

    # ── 4. 插入数据注入脚本（在 </body> 之前）────────────────────────────
    html = html.replace("</body>", inject_script + "\n</body>")

    return html


def main():
    print("[generate_dashboard] Loading data...")
    data = load_data()
    print(f"  Date: {data['date']}")

    print("[generate_dashboard] Loading HTML template...")
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    print("[generate_dashboard] Injecting real data...")
    output_html = inject_into_html(template, data)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(output_html)

    size_kb = os.path.getsize(OUTPUT_PATH) // 1024
    print(f"[generate_dashboard] ✓ Written: {OUTPUT_PATH} ({size_kb} KB)")


if __name__ == "__main__":
    main()
