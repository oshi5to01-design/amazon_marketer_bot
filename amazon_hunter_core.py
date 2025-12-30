import json
import os
import random
import re
import sys
import time

import google.generativeai as genai
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pyvirtualdisplay import Display

# ==========================================
# ⚙️ 共通設定 & .env読み込み
# ==========================================
load_dotenv()

AMAZON_TAG = os.getenv("AMAZON_TAG")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHECK_LIMIT = 5

# 設定チェック
if not AMAZON_TAG:
    print("⚠️ 警告: .envファイルに AMAZON_TAG が設定されていません！")
if not GEMINI_API_KEY:
    print("❌ エラー: .envファイルに GEMINI_API_KEY が設定されていません！")
    sys.exit(1)  # キーがないと動かないので終了

# Geminiの設定
genai.configure(api_key=GEMINI_API_KEY)


# ==========================================
# 🛠️ 便利なツール関数
# ==========================================
def _setup_driver():
    """Chromeドライバーの設定"""
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,1024")
    options.add_argument("--lang=ja-JP")
    driver = uc.Chrome(options=options)
    return driver


def _analyze_html_with_gemini(html_content):
    """
    HTMLをGeminiに渡して、商品情報を抽出する関数
    """
    try:
        # 1. HTMLを軽量化する（トークン節約のため）
        soup = BeautifulSoup(html_content, "html.parser")

        # scriptやstyleタグはノイズになるので削除
        for script in soup(["script", "style", "noscript", "iframe"]):
            script.decompose()

        # テキストのみを抽出（HTMLタグそのままだと重すぎる場合があるため）
        # ただし、構造が必要な場合は str(soup) でも良いが、今回はテキストベースで試す
        # Amazonは情報量が多いので、body内のメインコンテンツに絞ると精度が上がる
        main_content = soup.find("div", {"id": "dp"})  # 商品ページの大枠
        if not main_content:
            main_content = soup.body

        # テキスト化して空白を整理
        clean_text = main_content.get_text(separator="\n", strip=True)

        # 文字数が多すぎるとエラーになるので、先頭からある程度で切る（価格情報は上の方にあるはず）
        # Gemini 1.5 Flashならかなり長くてもいけるが、念のため
        input_text = clean_text[:30000]

        # 2. モデルの準備
        model = genai.GenerativeModel("models/gemini-flash-latest")

        # 3. プロンプト（命令文）
        prompt = (
            """
        あなたはAmazonの商品ページの解析AIです。
        以下のテキストデータから、この商品の情報を抽出してください。

        【抽出項目】
        1. name: 商品名（具体的かつ簡潔に）
        2. price: 現在の販売価格（数値のみ。円マークやカンマは削除）
        3. original: 参考価格または元値（数値のみ。見つからない場合は 0）
        4. discount: 割引率（数値のみ。%は削除。見つからない場合は 0）

        【出力形式】
        必ず以下のJSON形式のみを出力してください。Markdown記法（```json）は不要です。
        {
            "name": "商品名",
            "price": 1000,
            "original": 1200,
            "discount": 20
        }
        
        【対象テキスト】
        """
            + input_text
        )

        # 4. AIに聞く
        response = model.generate_content(prompt)
        text = response.text

        # JSON形式の文字列を探して取り出す
        clean_json_text = text.replace("```json", "").replace("```", "").strip()

        # 辞書データに変換
        result = json.loads(clean_json_text)

        # 型の安全対策（念のためint変換）
        if result.get("price"):
            result["price"] = int(result["price"])
        if result.get("original"):
            result["original"] = int(result["original"])
        if result.get("discount"):
            result["discount"] = int(result["discount"])

        return result

    except Exception as e:
        print(f"   ❌ AI解析エラー: {e}")
        return None


# ==========================================
# 🚀 メインミッション実行関数
# ==========================================
def run_mission(ranking_url, category_tag):
    print(f"\n🚀 ミッション開始: {category_tag}")
    print(f"Target: {ranking_url}")

    display = Display(visible=0, size=(1920, 1080))
    display.start()
    print("🖥️ 仮想ディスプレイを起動しました")

    driver = None

    try:
        driver = _setup_driver()

        # 1. ランキング取得
        driver.get(ranking_url)
        time.sleep(random.uniform(10, 15))

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
            print(f"[{i + 1}/{len(target_asins)}] 🔎 ASIN: {asin} を調査中...")

            try:
                driver.get(url)
                time.sleep(random.uniform(6, 10))

                # ページソースをAIに渡す
                html_content = driver.page_source

                # ★ここでGeminiを呼び出す！
                info = _analyze_html_with_gemini(html_content)

                if info and info.get("price", 0) > 0:
                    print(
                        f"   💰 {info['price']:,}円 (割引: {info['discount']}%) - {info['name'][:20]}..."
                    )

                    if best_deal is None or info["discount"] > best_deal["discount"]:
                        best_deal = {
                            "name": info["name"],
                            "url": url,
                            "price": info["price"],
                            "original": info["original"],
                            "discount": info["discount"],
                        }
                        print("   >>> 👑 暫定1位！")
                else:
                    print("   ❌ 価格取得失敗 (AI解析不能)")

            except Exception as e:
                print(f"   ❌ 個別エラー: {e}")
                continue

        # 3. 結果の返却
        print("-" * 40)
        if best_deal and best_deal["discount"] > 0:
            print("🏆 【今回の割引率No.1】 🏆")
            print(f"商品名: {best_deal['name']}")
            print(f"割引率: {best_deal['discount']}% OFF")

            tag_str = f"tag={AMAZON_TAG}" if AMAZON_TAG else ""
            affiliate_url = f"{best_deal['url']}?{tag_str}"

            short_name = " ".join(best_deal["name"].split()[:5])

            item_data = {
                "name": short_name,
                "price": best_deal["price"],
                "original": best_deal["original"],
                "discount": best_deal["discount"],
                "url": affiliate_url,
                "hashtag": f"{category_tag} #Amazonセール",
            }

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


if __name__ == "__main__":
    print("これは親玉モジュールです。daily_mission.py から呼び出してください。")
