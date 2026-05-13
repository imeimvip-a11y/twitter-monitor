#!/usr/bin/env python3
"""
Twitter 监控脚本
监控指定用户的新推文，并推送到飞书
"""

import os
import json
import re
import time
from datetime import datetime
from pathlib import Path

import httpx

# ============ 配置 ============
TWITTER_USERS = os.getenv("TWITTER_USERS", "GeekCatX").split(",")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
TWITTER_COOKIE = os.getenv("TWITTER_COOKIE", "")
DATA_FILE = Path("data/last_tweet.json")

# 清理 Cookie（去掉换行符）
TWITTER_COOKIE = TWITTER_COOKIE.strip().replace('\n', '').replace('\r', '')

# Twitter API 端点 (GraphQL)
GRAPHQL_URL = "https://twitter.com/i/api/graphql/jOtTfsr0mvpSYPvm6yUE0A/UserTweets"

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3DZ1lq57BRhc7uxyCj36OsTC7Xz5L9oHqHqaAUECWkbnK",
    "X-Twitter-Auth-Type": "OAuth2Session",
    "X-Twitter-Active-User": "yes",
    "X-Csrf-Token": "",
}

# ============ 工具函数 ============


def load_last_tweets():
    """加载上次处理的推文记录"""
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}


def save_last_tweets(data):
    """保存推文记录"""
    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def extract_csrf_token(cookie):
    """从 Cookie 中提取 CSRF token"""
    match = re.search(r'ct0=([^;]+)', cookie)
    return match.group(1) if match else ""


def get_user_id(username, client):
    """获取用户的 rest_id"""
    print(f"🔍 获取用户 {username} 的 ID...")

    # 通过用户主页获取
    resp = client.get(
        f"https://twitter.com/{username.lstrip('@')}",
        headers=HEADERS.copy(),
        follow_redirects=True
    )

    if resp.status_code != 200:
        print(f"❌ 获取用户 {username} 主页失败: {resp.status_code}")
        return None

    # 从页面中提取 user_id
    match = re.search(r'"rest_id":"(\d+)"', resp.text)
    if match:
        user_id = match.group(1)
        print(f"✅ 用户 {username} 的 ID: {user_id}")
        return user_id

    print(f"❌ 无法从页面中提取 {username} 的 user_id")
    return None


def get_user_tweets(user_id, username, client):
    """获取用户的推文"""
    print(f"📥 获取用户 {username} 的推文...")

    # 更新 CSRF token
    csrf_token = extract_csrf_token(TWITTER_COOKIE)
    HEADERS["X-Csrf-Token"] = csrf_token
    HEADERS["Cookie"] = TWITTER_COOKIE

    # 构建请求
    variables = {
        "userId": user_id,
        "count": 20,
        "includePromotedContent": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withVoice": True,
        "withV2Timeline": True
    }

    features = {
        "rweb_lists_timeline_redesign_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": False,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": False,
        "responsive_web_media_download_video_enabled": False,
        "responsive_web_enhance_cards_enabled": False
    }

    params = {
        "variables": json.dumps(variables),
        "features": json.dumps(features)
    }

    resp = client.get(GRAPHQL_URL, headers=HEADERS, params=params)

    if resp.status_code != 200:
        print(f"❌ 获取推文失败: {resp.status_code}")
        print(f"响应: {resp.text[:500]}")
        return []

    try:
        data = resp.json()
        tweets = []

        # 解析推文
        instructions = data.get("data", {}).get("user", {}).get("result", {}).get("timeline_v2", {}).get("timeline", {}).get("instructions", [])

        for instruction in instructions:
            if instruction.get("type") == "TimelineAddEntries":
                entries = instruction.get("entries", [])
                for entry in entries:
                    content = entry.get("content", {})
                    if content.get("entryType") == "TimelineTimelineItem":
                        item_content = content.get("itemContent", {})
                        tweet_results = item_content.get("tweet_results", {})
                        result = tweet_results.get("result", {})

                        if result.get("__typename") == "Tweet":
                            tweet_info = result.get("legacy", {})
                            tweet_id = result.get("rest_id", "")

                            # 解析图片
                            media = []
                            media_entities = tweet_info.get("entities", {}).get("media", [])
                            for media_entity in media_entities:
                                media_url = media_entity.get("media_url_https", "")
                                media_type = media_entity.get("type", "")
                                if media_url:
                                    media.append({
                                        "url": media_url,
                                        "type": media_type
                                    })

                            tweets.append({
                                "id": tweet_id,
                                "text": tweet_info.get("full_text", ""),
                                "created_at": tweet_info.get("created_at", ""),
                                "media": media,
                                "username": username,
                                "user_id": user_id
                            })

        print(f"✅ 获取到 {len(tweets)} 条推文")
        return tweets

    except Exception as e:
        print(f"❌ 解析推文失败: {e}")
        print(f"响应: {resp.text[:500]}")
        return []


def send_to_feishu(message):
    """发送消息到飞书"""
    if not FEISHU_WEBHOOK:
        print("⚠️ 未配置飞书 Webhook")
        return False

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

    try:
        resp = httpx.post(FEISHU_WEBHOOK, json=data, timeout=10)
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
            created_at = tweet.get("created_at", "")
            try:
                dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                time_str = dt.strftime("%m-%d %H:%M")
            except:
                time_str = created_at

            lines.append(f"**{time_str}**")

            # 文本（最多200字）
            text = tweet.get("text", "")
            if len(text) > 200:
                text = text[:200] + "..."
            lines.append(f"{text}")

            # 图片链接
            media = tweet.get("media", [])
            if media:
                lines.append(f"📎 图片/媒体: {len(media)}个")
                for m in media[:3]:  # 最多显示3个
                    lines.append(f"- {m['url']}")
                if len(media) > 3:
                    lines.append(f"- ...还有 {len(media)-3} 个")

            lines.append(f"🔗 [查看原推](https://x.com/{username.lstrip('@')}/status/{tweet['id']})")
            lines.append("")

    return "\n".join(lines)


def main():
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

    # 创建 HTTP 客户端
    client = httpx.Client(timeout=30.0, follow_redirects=True)

    # 存储新推文
    all_new_tweets = {}

    try:
        # 遍历每个用户
        for username in TWITTER_USERS:
            username = username.strip()
            if not username:
                continue

            print(f"\n{'='*20} {username} {'='*20}")

            # 获取用户 ID
            user_id = get_user_id(username, client)
            if not user_id:
                print(f"⚠️ 跳过用户 {username}")
                continue

            # 获取推文
            tweets = get_user_tweets(user_id, username, client)

            # 过滤新推文
            new_tweets = []
            last_id = last_tweets.get(username, "")

            for tweet in tweets:
                tweet_id = tweet["id"]
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
                    last_tweets[username] = tweets[0]["id"]
            else:
                print(f"✅ 没有新推文")

            # 避免请求过快
            time.sleep(2)

    finally:
        client.close()

    # 保存记录
    save_last_tweets(last_tweets)

    # 发送通知
    if all_new_tweets:
        print(f"\n📤 准备发送通知...")
        message = format_tweet_message(all_new_tweets)
        if message:
            send_to_feishu(message)
    else:
        print(f"\n✅ 没有新内容，不发送通知")

    print("\n" + "=" * 50)
    print("✅ 监控完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
