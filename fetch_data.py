#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_data.py
─────────────────────────────────────────────────────────────────────────────
从 Brandwatch 或 Meltwater 拉取三品牌（DJI / Insta360 / GoPro）的
欧洲五国（DE / FR / IT / ES / UK）社交媒体舆情数据。

使用方式:
    python fetch_data.py --source brandwatch
    python fetch_data.py --source meltwater

输出: data/latest.json
─────────────────────────────────────────────────────────────────────────────
"""

import os
import json
import ssl
import argparse
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone

# ── SSL 上下文（兼容企业代理证书环境）────────────────────────────────────
CTX = ssl._create_unverified_context()

# ── 从环境变量读取 API 凭证 ──────────────────────────────────────────────
#    在 GitHub Actions 里通过 Secrets 注入，本地测试时 export 到环境变量
BRANDWATCH_API_KEY   = os.environ.get("BRANDWATCH_API_KEY", "")
BRANDWATCH_PROJECT_ID = os.environ.get("BRANDWATCH_PROJECT_ID", "")  # 项目 ID

MELTWATER_API_KEY    = os.environ.get("MELTWATER_API_KEY", "")

# ── 监控配置 ────────────────────────────────────────────────────────────
BRANDS = {
    "dji": {
        "name": "DJI",
        "queries": [
            "DJI Action Camera", "DJI Osmo Action", "DJI Action 5",
            "DJI Action 4", "DJI Osmo 360", "DJI 360 Camera", "DJI Osmo Nano"
        ]
    },
    "i360": {
        "name": "Insta360",
        "queries": [
            "Insta360", "Insta360 GO Ultra", "Insta360 X5",
            "Insta360 X4", "Insta360 GO 3"
        ]
    },
    "gp": {
        "name": "GoPro",
        "queries": [
            "GoPro Hero", "GoPro Hero 13", "GoPro Max 2",
            "GoPro Max", "GoPro action camera"
        ]
    }
}

COUNTRIES = {
    "de": {"name": "德国",  "flag": "🇩🇪", "lang": "de", "bw_location": "Germany"},
    "fr": {"name": "法国",  "flag": "🇫🇷", "lang": "fr", "bw_location": "France"},
    "it": {"name": "意大利","flag": "🇮🇹", "lang": "it", "bw_location": "Italy"},
    "es": {"name": "西班牙","flag": "🇪🇸", "lang": "es", "bw_location": "Spain"},
    "uk": {"name": "英国",  "flag": "🇬🇧", "lang": "en", "bw_location": "United Kingdom"},
}

PLATFORMS = ["YouTube", "TikTok", "Instagram", "Facebook", "Twitter", "Reddit"]


def today_range():
    """返回昨天的 UTC 开始和结束时间（ISO 8601）"""
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
    end   = datetime.combine(today,     datetime.min.time()).replace(tzinfo=timezone.utc)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")


# ═══════════════════════════════════════════════════════════════════════════
# Brandwatch API
# ═══════════════════════════════════════════════════════════════════════════
class BrandwatchFetcher:
    BASE = "https://api.brandwatch.com"

    def __init__(self, api_key, project_id):
        self.token = api_key
        self.project_id = project_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path, params=None):
        url = self.BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self.headers)
        try:
            r = urllib.request.urlopen(req, timeout=30, context=CTX)
            return json.loads(r.read())
        except urllib.error.HTTPError as e:
            print(f"  [BW] HTTP {e.code}: {path}")
            return None

    def fetch_brand_country(self, brand_key, country_key, date_str):
        """
        拉取某品牌在某国的昨日数据。
        返回: { mentions, sentiment_pos, sentiment_neg, by_platform }
        """
        brand = BRANDS[brand_key]
        country = COUNTRIES[country_key]
        query_str = " OR ".join(f'"{q}"' for q in brand["queries"])

        params = {
            "queryId": self.project_id,
            "startDate": date_str,
            "endDate": date_str,
            "country": country["bw_location"],
            "query": query_str,
            "pageSize": 1000,
        }

        # 声量
        vol_data = self._get(f"/projects/{self.project_id}/data/volume/daily", params)
        mentions = 0
        if vol_data and "results" in vol_data:
            for item in vol_data["results"]:
                mentions += item.get("volume", 0)

        # 情感
        sent_data = self._get(f"/projects/{self.project_id}/data/sentiment/daily", params)
        pos = neg = neu = 0
        if sent_data and "results" in sent_data:
            for item in sent_data["results"]:
                pos += item.get("positive", 0)
                neg += item.get("negative", 0)
                neu += item.get("neutral", 0)
        total_sent = pos + neg + neu or 1
        sent_pct = round(pos / total_sent * 100)

        # 平台分布
        plat_data = self._get(f"/projects/{self.project_id}/data/sources/volume", params)
        by_platform = {p: 0 for p in PLATFORMS}
        if plat_data and "results" in plat_data:
            plat_map = {
                "youtube": "YouTube", "tiktok": "TikTok",
                "instagram": "Instagram", "facebook": "Facebook",
                "twitter": "Twitter", "reddit": "Reddit",
            }
            for item in plat_data.get("results", []):
                name = item.get("name", "").lower()
                mapped = plat_map.get(name)
                if mapped:
                    by_platform[mapped] += item.get("volume", 0)

        return {
            "mentions": mentions,
            "sentiment_pos": sent_pct,
            "by_platform": by_platform,
        }

    def fetch_all(self):
        start, _ = today_range()
        date_str = start[:10]  # YYYY-MM-DD
        print(f"[Brandwatch] Fetching data for {date_str} ...")
        data = {"date": date_str, "brands": {}}

        for brand_key in BRANDS:
            data["brands"][brand_key] = {}
            for country_key in COUNTRIES:
                print(f"  {BRANDS[brand_key]['name']} × {COUNTRIES[country_key]['name']} ...")
                result = self.fetch_brand_country(brand_key, country_key, date_str)
                data["brands"][brand_key][country_key] = result

        return data


# ═══════════════════════════════════════════════════════════════════════════
# Meltwater API
# ═══════════════════════════════════════════════════════════════════════════
class MeltwaterFetcher:
    BASE = "https://api.meltwater.com/v3"

    def __init__(self, api_key):
        self.headers = {
            "Authorization": f"apikey {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _post(self, path, payload):
        url = self.BASE + path
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=self.headers, method="POST")
        try:
            r = urllib.request.urlopen(req, timeout=30, context=CTX)
            return json.loads(r.read())
        except urllib.error.HTTPError as e:
            print(f"  [MW] HTTP {e.code}: {path}")
            return None

    def fetch_brand_country(self, brand_key, country_key, start, end):
        brand   = BRANDS[brand_key]
        country = COUNTRIES[country_key]

        payload = {
            "filter": {
                "keyword": " OR ".join(f'"{q}"' for q in brand["queries"]),
                "country": [country["bw_location"]],
                "date_range": {"start": start, "end": end},
            },
            "aggregations": [
                {"type": "total_count"},
                {"type": "sentiment"},
                {"type": "source", "limit": 20},
            ]
        }
        result = self._post("/analytics/search", payload)
        if not result:
            return {"mentions": 0, "sentiment_pos": 60, "by_platform": {p: 0 for p in PLATFORMS}}

        mentions  = result.get("total_count", 0)
        sentiment = result.get("sentiment", {})
        pos = sentiment.get("positive", 0)
        total_s = sum(sentiment.values()) or 1
        sent_pct = round(pos / total_s * 100)

        by_platform = {p: 0 for p in PLATFORMS}
        plat_map = {
            "youtube.com": "YouTube", "tiktok.com": "TikTok",
            "instagram.com": "Instagram", "facebook.com": "Facebook",
            "twitter.com": "Twitter", "x.com": "Twitter",
            "reddit.com": "Reddit",
        }
        for source in result.get("source_breakdown", []):
            domain = source.get("source", "").lower()
            for key, plat in plat_map.items():
                if key in domain:
                    by_platform[plat] += source.get("count", 0)
                    break

        return {"mentions": mentions, "sentiment_pos": sent_pct, "by_platform": by_platform}

    def fetch_all(self):
        start, end = today_range()
        date_str = start[:10]
        print(f"[Meltwater] Fetching data for {date_str} ...")
        data = {"date": date_str, "brands": {}}

        for brand_key in BRANDS:
            data["brands"][brand_key] = {}
            for country_key in COUNTRIES:
                print(f"  {BRANDS[brand_key]['name']} × {COUNTRIES[country_key]['name']} ...")
                result = self.fetch_brand_country(brand_key, country_key, start, end)
                data["brands"][brand_key][country_key] = result

        return data


# ═══════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["brandwatch", "meltwater"], default="brandwatch")
    args = parser.parse_args()

    if args.source == "brandwatch":
        if not BRANDWATCH_API_KEY:
            raise SystemExit("ERROR: BRANDWATCH_API_KEY 环境变量未设置")
        fetcher = BrandwatchFetcher(BRANDWATCH_API_KEY, BRANDWATCH_PROJECT_ID)
    else:
        if not MELTWATER_API_KEY:
            raise SystemExit("ERROR: MELTWATER_API_KEY 环境变量未设置")
        fetcher = MeltwaterFetcher(MELTWATER_API_KEY)

    data = fetcher.fetch_all()

    os.makedirs("data", exist_ok=True)
    out_path = "data/latest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Data saved to {out_path}")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:500])


if __name__ == "__main__":
    main()
