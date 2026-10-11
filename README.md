# Teft

Teft 是面向 macOS 的终端应用，基于 [gnachman/iTerm2](https://github.com/gnachman/iTerm2) 的独立 fork。我们希望把终端与自己的系统结合，逐步接入 Agent Deck、World Store 和 PolarisAtlas；这些深度集成目前仍是计划，尚未实现。

目前提供源码与开发构建流程。arm64 开发版已使用 Xcode 26.2、Swift 6.2.3 成功构建，并在运行 macOS 26.5.2 的 MacBook Pro 上安装、启动；尚未验证从干净克隆完成整套构建，也没有正式签名、公证的发行包。

## 当前状态

- 应用名称和主可执行文件为 `Teft`，主 bundle identifier 为 `com.teft.app`。
- 自有辅助组件使用 `com.teft.app.sandboxed-worker`、`com.teft.app.pidinfo` 和 `com.teft.app.import-status`。
- 主包及各语言的权限说明已同步品牌，尚未完成原生权限弹窗及完整 UI 验收；更换应用标识不代表获得 Computer Use 授权。
- 上游 Sparkle 更新已禁用。开发构建在独立目录中暂存，不覆盖已安装的 iTerm2。

## 从源码构建

需要 macOS、完整 Xcode 和 Homebrew；具体工具及原生依赖以 `doctor` 的检查结果为准。确认依赖就绪后，在仓库根目录依次执行：

```sh
git clone https://github.com/Kymorphius/teft.git
cd teft
tools/teft.sh prepare
tools/teft.sh doctor
tools/teft.sh deps
tools/teft.sh build
tools/teft.sh run
```

`prepare` 初始化子模块，`deps` 为当前 Xcode 重建原生依赖，`build` 创建版本化的 `Teft.app`，`run` 通过 macOS Launch Services 启动最新产物。开发配置 suite 取仓库目录名：上述克隆使用 `teft`，不会强制使用本地开发目录的 `system-term`。切换构建前先正常退出正在运行的 Teft。

详细的产物路径、日志、运行隔离及当前限制见 [Teft 开发说明](TEFT.md)。权限说明的 7 项回归测试可单独运行：

```sh
python3 tests/test_teft_stage_branding.py
```

GitHub Actions 会运行这组品牌回归测试并检查启动脚本语法；它不代替 macOS 原生构建和交互验收。

如需跟踪上游，可在首次克隆后添加 remote：

```sh
git remote add upstream https://github.com/gnachman/iTerm2.git
```

## 贡献与反馈

Teft 的问题和改动请提交到[本仓库](https://github.com/Kymorphius/teft)。上游的终端功能资料见 [iTerm2 文档](https://iterm2.com/documentation.html)，构建与开发约定见 [AGENTS.md](AGENTS.md) 和 [CLAUDE.md](CLAUDE.md)。

## 致谢与许可证

Teft 保留 iTerm2 的上游历史、版权及许可证声明。感谢 [George Nachman](https://github.com/gnachman) 和 [iTerm2 贡献者](https://github.com/gnachman/iTerm2/graphs/contributors) 提供的基础。

本仓库保留的 Sponsor 链接用于支持 iTerm2 上游开发。

许可证原文见 [LICENSE](LICENSE)、[COPYING](COPYING) 和 [README.license](README.license)。第三方组件保留各自许可证，例如 [Sparkle](ThirdParty/Sparkle/LICENSE)、[CoreParse](ThirdParty/CoreParse/LICENSE)、[ColorPicker](ColorPicker/LICENSE)；其余声明随 [ThirdParty](ThirdParty/)、[子模块](.gitmodules)及各组件源码保留。
