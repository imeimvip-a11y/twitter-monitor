# Twitter 监控 + 飞书推送

自动监控指定 Twitter 博主的新推文，并推送到飞书群。

## 配置信息

- **监控账号**: @xiaoxiaodong01, @GeekCatX
- **推送时间**: 每天 07:00 和 17:00（北京时间）
- **推送方式**: 飞书群机器人

## 使用步骤

### 1. 获取 Twitter Cookie

1. 打开 [twitter.com](https://twitter.com) 并登录
2. 按 `F12` 打开开发者工具
3. 切换到 `Network` 标签
4. 刷新页面
5. 点击任意请求，查看 `Request Headers`
6. 找到 `Cookie` 那一行，复制完整内容

### 2. 创建 GitHub 仓库并上传

1. 在 GitHub 创建一个新仓库（私有或公开都可以）
2. 将本文件夹内容上传到仓库
3. 进入仓库的 `Settings` → `Secrets and variables` → `Actions`
4. 添加以下 Secrets：

| Name | Secret |
|------|--------|
| `FEISHU_WEBHOOK` | 你的飞书 Webhook URL |
| `TWITTER_COOKIE` | 上一步获取的 Twitter Cookie |

### 3. 启用 GitHub Actions

1. 进入仓库的 `Actions` 标签
2. 点击 `I understand my workflows, go ahead and enable them`
3. 在左侧选择 `Twitter Monitor` 工作流
4. 点击 `Run workflow` 手动测试一次

### 4. 完成！

现在每天 7:00 和 17:00 会自动检查并发送新推文到飞书。

## 手动触发

随时可以在 GitHub Actions 页面点击 `Run workflow` 手动运行。

## 注意事项

- Cookie 大约 30 天后会失效，需要重新获取
- 如果长时间没有新推文，可以手动运行测试
- 飞书群至少要有 2 个人才能添加机器人
