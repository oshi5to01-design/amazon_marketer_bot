# daily_mission.py
import os
import random
import tweepy
from dotenv import load_dotenv
import amazon_hunter_core  # さっき作った親玉を読み込む

# ==========================================
# ⚙️ 設定 & 準備
# ==========================================
load_dotenv()

# 巡回リスト（ここにURLとタグをまとめておく）
MISSIONS = [
    {
        "url": "https://www.amazon.co.jp/gp/bestsellers/computers/2151973051/",
        "tag": "#ゲーミングマウス",
    },
    {
        "url": "https://www.amazon.co.jp/gp/bestsellers/computers/2151982051/ref=zg_bs_nav_computers_1",
        "tag": "#ゲーミングモニター",
    },
    {
        "url": "https://www.amazon.co.jp/gp/bestsellers/computers/2151972051/ref=zg_bs_nav_computers_2_2151970051",
        "tag": "#ゲーミングキーボード",
    },
]


# X API設定
def get_twitter_client():
    return tweepy.Client(
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_SECRET"),
    )


# ==========================================
# 🚀 メイン処理
# ==========================================
def main():
    print("🤖 --- デイリー・ミッション開始 ---")

    candidates = []  # 候補を入れるリスト

    # 1. 各ミッションを順番に実行
    for mission in MISSIONS:
        # 親玉を呼び出して、結果を直接受け取る！
        result = amazon_hunter_core.run_mission(mission["url"], mission["tag"])

        if result:
            candidates.append(result)
            print(f"✅ 候補に追加: {result['name']}")
        else:
            print("Pass (対象なし)")

    # 2. 集まった候補から抽選してツイート
    if candidates:
        print(f"\n📊 {len(candidates)} 件の候補が集まりました。抽選します...")
        winner = random.choice(candidates)

        print(f"👑 当選: {winner['name']}")

        # ツイート処理
        try:
            client = get_twitter_client()

            # 1ツイート目
            text_main = (
                f"🚨【セール速報】{winner['name']}\n\n"
                f"💰 現在: {winner['price']:,}円\n"
                f"📉 割引: -{winner['discount']}% OFF"
            )
            if winner["original"] > 0:
                text_main += f" (元値: {winner['original']:,}円)"
            text_main += "\n\n在庫と詳細はリプライへ👇"

            response = client.create_tweet(text=text_main)
            tweet_id = response.data["id"]

            # 2ツイート目（リプライ）
            text_reply = f"在庫はこちら👉 {winner['url']}\n{winner['hashtag']}"
            client.create_tweet(text=text_reply, in_reply_to_tweet_id=tweet_id)

            print("✅ ツイート成功！ミッションコンプリート。")

        except Exception as e:
            print(f"❌ ツイート失敗: {e}")
    else:
        print("📭 今回は投稿できる商品が1つもありませんでした。")


if __name__ == "__main__":
    main()
