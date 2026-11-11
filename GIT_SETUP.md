# Git 提交说明

这是独立源码副本，不包含原父仓库历史。真实配置在用户目录的 Library/Application Support/WeChatAIStudio/config.json，不在此仓库。
config.py 是程序模块，应提交；config.example.json 是空白示例，可提交。不要在 config.py 中填写真实密钥。

首次提交：

```bash
git status --short
git diff --cached --stat
git commit -m "Initial import of WeChat AI Studio"
```

在 GitHub/Gitee 创建空仓库后，将下面占位地址替换为自己的仓库地址：

```bash
git remote add origin <你的仓库地址>
git push -u origin main
```

当前没有配置远程、没有提交、没有上传。源码已经暂存供审查。
.gitignore 只影响未跟踪文件，不能清除已提交的密钥。本副本采用源码白名单导出并检查了默认凭据与常见密钥格式，但扫描不能保证识别所有敏感信息；之后提交前仍检查 git diff --cached。
后续应在此副本开发；原目录修改不会自动同步过来。README 中的运行环境需要在此副本重新安装。
