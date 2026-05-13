#!/usr/bin/env python3
"""
Twitter 监控脚本 (使用 twscrape)
监控指定用户的新推文，并推送到飞书
"""

import os
import json
import asyncio
from datetime import datetime
from pathlib import Path

try:
    from twscrape import API, gather
except ImportError:
    print("请先安装 twscrape:")
    print("pip install git+https://github.com/vladkens/twscrape.git")
    exit(1)

# ============ 配置 ============
TWITTER_USERS = os.getenv("TWITTER_USERS", "GeekCatX").split(",")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
TWITTER_COOKIE = os.getenv("TWITTER_COOKIE", "")
DATA_FILE = Path("data/last_tweet.json")


def load_last_tweets():
    """加载上次处理的推文记录"""
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}


def save_last_tweets(data):
    """保存推文记录"""
    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


async def send_to_feishu(message):
    """发送消息到飞书"""
    if not FEISHU_WEBHOOK:
        print("⚠️ 未配置飞书 Webhook")
        return False

    try:
        import httpx
        data = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "🐦 Twitter 监控通知"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": message
                        }
                    }
                ]
            }
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(FEISHU_WEBHOOK, json=data, timeout=10)
            if resp.status_code == 200:
                print("✅ 飞书推送成功")
                return True
            else:
                print(f"❌ 飞书推送失败: {resp.status_code}")
                print(f"响应: {resp.text}")
                return False
    except Exception as e:
        print(f"❌ 飞书推送异常: {e}")
        return False


def format_tweet_message(new_tweets):
    """格式化推文消息"""
    if not new_tweets:
        return None

    lines = ["## 📬 有新推文！\n"]

    for username, tweets in new_tweets.items():
        if not tweets:
            continue

        lines.append(f"### 👤 {username}\n")

        for tweet in tweets:
            # 时间
            time_str = str(tweet.date)[:16] if hasattr(tweet, 'date') else ""

            # 文本（最多200字）
            text = tweet.rawContent if hasattr(tweet, 'rawContent') else tweet.text
            if text and len(text) > 200:
                text = text[:200] + "..."

            if time_str:
                lines.append(f"**{time_str}**")
            if text:
                lines.append(f"{text}")

            # 媒体
            if hasattr(tweet, 'media') and tweet.media:
                lines.append(f"📎 媒体: {len(tweet.media)}个")

            lines.append(f"🔗 [查看原推](https://x.com/{username}/status/{tweet.id})")
            lines.append("")

    return "\n".join(lines)


async def main():
    """主函数"""
    print("=" * 50)
    print("🐦 Twitter 监控开始")
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 检查配置
    if not TWITTER_COOKIE:
        print("❌ 未配置 TWITTER_COOKIE")
        return

    if not FEISHU_WEBHOOK:
        print("❌ 未配置 FEISHU_WEBHOOK")
        return

    # 加载上次处理的记录
    last_tweets = load_last_tweets()
    print(f"📂 已加载历史记录")

    # 初始化 API
    api = API()
    await api.pool.add_account("cookie_user", "", "", "", cookies=TWITTER_COOKIE)

    # 存储新推文
    all_new_tweets = {}

    try:
        # 遍历每个用户
        for username in TWITTER_USERS:
            username = username.strip().lstrip('@')
            if not username:
                continue

            print(f"\n{'='*20} {username} {'='*20}")

            try:
                # 获取用户信息（使用 async for 迭代）
                print(f"🔍 正在获取用户 {username} 的信息...")
                user = None
                async for u in api.user_by_login(username):
                    user = u
                    break

                if not user:
                    print(f"❌ 用户 {username} 不存在或无法访问")
                    continue

                print(f"✅ 用户 ID: {user.id}")

                # 获取推文（使用 async for 迭代并收集）
                print(f"📥 正在获取推文...")
                tweets = []
                async for tweet in api.user_tweets(user.id, limit=50):
                    tweets.append(tweet)

                # 过滤新推文
                new_tweets = []
                last_id = last_tweets.get(username, "")

                for tweet in tweets:
                    tweet_id = str(tweet.id)
                    if tweet_id != last_id:
                        new_tweets.append(tweet)
                    else:
                        # 遇到已处理的推文，停止
                        break

                if new_tweets:
                    print(f"✨ 发现 {len(new_tweets)} 条新推文！")
                    all_new_tweets[username] = new_tweets

                    # 更新最新推文 ID
                    if tweets:
                        last_tweets[username] = str(tweets[0].id)
                else:
                    print(f"✅ 没有新推文")

            except Exception as e:
                print(f"❌ 处理用户 {username} 时出错: {e}")
                import traceback
                traceback.print_exc()

    finally:
        # 保存记录
        save_last_tweets(last_tweets)

    # 发送通知
    if all_new_tweets:
        print(f"\n📤 准备发送通知...")
        message = format_tweet_message(all_new_tweets)
        if message:
            await send_to_feishu(message)
    else:
        print(f"\n✅ 没有新内容，不发送通知")

    print("\n" + "=" * 50)
    print("✅ 监控完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
