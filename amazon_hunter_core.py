# amazon_hunter_core.py
import time
import random
import re
import os
import sys
from dotenv import load_dotenv
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from pyvirtualdisplay import Display

# ==========================================
# ⚙️ 共通設定 & .env読み込み
# ==========================================
load_dotenv()

AMAZON_TAG = os.getenv("AMAZON_TAG")
CHECK_LIMIT = 11

# タグ設定チェック
if not AMAZON_TAG:
    print("⚠️ 警告: .envファイルに AMAZON_TAG が設定されていません！")


# ==========================================
# 🛠️ 便利なツール関数（内部用）
# ==========================================
def _clean_number(text):
    """文字から数字だけを抜き出す（内部関数）"""
    if not text:
        return 0
    cleaned = (
        text.strip()
        .replace("¥", "")
        .replace(",", "")
        .replace("￥", "")
        .replace(".", "")
    )
    cleaned = cleaned.replace("-", "").replace("%", "")
    if cleaned.isdigit():
        return int(cleaned)
    return 0


def _setup_driver():
    """Chromeドライバーの設定"""
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,1024")
    options.add_argument("--lang=ja-JP")
    driver = uc.Chrome(options=options)
    return driver


def _extract_price_info(soup):
    """価格と割引率を抽出する"""
    info = {"price": 0, "original_price": 0, "discount": 0}

    # 1. 現在価格
    price_selectors = [
        "#corePriceDisplay_desktop_feature_div .a-price-whole",
        "#corePrice_feature_div .a-price-whole",
        ".a-price .a-price-whole",
    ]
    for sel in price_selectors:
        tag = soup.select_one(sel)
        if tag:
            price = _clean_number(tag.text)
            if price > 0:
                info["price"] = price
                break

    # 2. 割引率
    discount_tag = soup.select_one(".savingsPercentage")
    if discount_tag:
        info["discount"] = _clean_number(discount_tag.text)

    # 3. 参考価格
    original_selectors = [
        "span.a-price.a-text-price span.a-offscreen",
        ".basisPrice span.a-offscreen",
    ]
    for sel in original_selectors:
        tag = soup.select_one(sel)
        if tag:
            original = _clean_number(tag.text)
            if original > 0:
                info["original_price"] = original
                break

    return info


# ==========================================
# 🚀 メインミッション実行関数
# ==========================================
def run_mission(ranking_url, category_tag):
    """
    子分からURLとタグを受け取って、スクレイピングを実行する関数。
    一番良い商品のデータを辞書形式で返す（return）。
    見つからなかった場合は None を返す。
    """
    print(f"\n🚀 ミッション開始: {category_tag}")
    print(f"Target: {ranking_url}")

    # 仮想ディスプレイの起動
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    print("🖥️ 仮想ディスプレイを起動しました")

    driver = None

    try:
        driver = _setup_driver()

        # 1. ランキング取得
        driver.get(ranking_url)
        time.sleep(random.uniform(5, 8))

        soup_ranking = BeautifulSoup(driver.page_source, "html.parser")
        all_links = soup_ranking.find_all("a", href=True)

        target_asins = []
        seen_asins = set()

        print("🔍 リンクからASINを抽出しています...")
        for link in all_links:
            href = link["href"]
            match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", href)
            if match:
                asin = match.group(1)
                if asin not in seen_asins:
                    target_asins.append(asin)
                    seen_asins.add(asin)

                if len(target_asins) >= CHECK_LIMIT:
                    break

        if not target_asins:
            print("❌ ASINが見つかりませんでした。")
            return None

        print(f"📋 TOP{len(target_asins)} の商品をリストアップしました。")

        # 2. 個別ページ巡回
        best_deal = None

        for i, asin in enumerate(target_asins):
            url = f"https://www.amazon.co.jp/dp/{asin}"
            print(f"[{i+1}/{len(target_asins)}] 🔎 ASIN: {asin} を調査中...")

            try:
                driver.get(url)
                time.sleep(random.uniform(6, 10))

                soup_item = BeautifulSoup(driver.page_source, "html.parser")

                title_tag = soup_item.select_one("#productTitle")
                title = title_tag.text.strip() if title_tag else "商品名不明"

                info = _extract_price_info(soup_item)

                if info["price"] > 0:
                    print(f"   💰 {info['price']:,}円 (割引: {info['discount']}%)")

                    if best_deal is None or info["discount"] > best_deal["discount"]:
                        best_deal = {
                            "name": title,
                            "url": url,
                            "price": info["price"],
                            "original": info["original_price"],
                            "discount": info["discount"],
                        }
                        print("   >>> 👑 暫定1位！")
                else:
                    print("   ❌ 価格取得失敗")

            except Exception as e:
                print(f"   ❌ 個別エラー: {e}")
                continue

        # 3. 結果の返却
        print("-" * 40)
        if best_deal and best_deal["discount"] > 0:
            print("🏆 【今回の割引率No.1】 🏆")
            print(f"商品名: {best_deal['name']}")
            print(f"割引率: {best_deal['discount']}% OFF")

            # アフィリエイトリンク生成
            tag_str = f"tag={AMAZON_TAG}" if AMAZON_TAG else ""
            affiliate_url = f"{best_deal['url']}?{tag_str}"

            # 名前短縮
            short_name = " ".join(best_deal["name"].split()[:5])

            # データを辞書にまとめる
            item_data = {
                "name": short_name,
                "price": best_deal["price"],
                "original": best_deal["original"],
                "discount": best_deal["discount"],
                "url": affiliate_url,
                "hashtag": f"{category_tag} #Amazonセール",
            }

            # ファイル保存せず、呼び出し元にデータを「返す」
            return item_data

        else:
            print("📭 今回は条件を満たす商品がありませんでした。")
            return None

    except Exception as e:
        print(f"❌ 致命的なエラー: {e}")
        import traceback

        traceback.print_exc()
        return None

    finally:
        if driver:
            driver.quit()
            print("👋 ブラウザ終了")
        display.stop()
        print("🖥️ 仮想ディスプレイ停止")
        print("=" * 40)


# テスト用（このファイルを直接実行した場合のみ動く）
if __name__ == "__main__":
    print("これは親玉モジュールです。daily_mission.py から呼び出してください。")
