# COMSOL 5.2a Windows 版 MCP

这个分支维护 COMSOL Multiphysics 5.2a 在本机的 MCP 接口，针对的版本是 **5.2.1.152，Windows x64**。仓库包含 MATLAB LiveLink 入口和 Python/MPh 工具服务。本次原生启动修复只验证了 5.2a，不承诺适用于 5.6 或 6.x。

[English](README.md) · [更新记录](CHANGELOG.md) · [启动故障说明](docs/comsol52a-startup.md)

遇到的故障是 Java 加载 `csutil.dll` 时报告找不到依赖库，随后出现 `FlLicense` 类初始化失败。文件实际存在，问题出在进程内的 DLL 加载环境。仓库中的 Java native agent 会在初始化前注册搜索目录并预加载 COMSOL 原生库。修复只作用于 MCP 及其子进程，不替换 COMSOL 文件，不改系统 PATH、注册表或 MATLAB 用户配置。

## 安装

直接把仓库放在希望使用的盘符下。Python 环境、编译临时文件和运行输出都放在仓库内的 `runtime`、`runs` 目录，不需要另装一份 COMSOL。

```powershell
git clone --branch codex/comsol-52a-base-compat https://github.com/Monika-shipship/COMSOL_Multiphysics_MCP.git D:\Repos\COMSOL_Multiphysics_MCP
cd D:\Repos\COMSOL_Multiphysics_MCP
.\scripts\setup_comsol52a.ps1 -Python 'D:\Program Files\Python313\python.exe'
```

把对应 GitHub Release 中的 `dllpath-rust-agent.dll` 放到 `runtime/native-loader`。已经有 Rust x64 Windows GNU 工具链时，也可以执行 `scripts/build_native_loader.ps1` 从源码编译；构建脚本使用 Rust 自带的链接器。

本机验证组合为 Python 3.13 x64、MPh 1.3.1、JPype 1.5.2 和 COMSOL 自带的 Java 8 (`1.8.0_66`)。LiveLink 使用 MATLAB R2025b；这只是本机实测结果，不代表 COMSOL 官方支持 5.2a 与该 MATLAB 版本的组合。Python/MPh 入口不需要 MATLAB。COMSOL、MATLAB 和模型所需模块的许可证由用户自行提供。

## 接入 Codex

按 [英文 README 的配置示例](README.md#codex-configuration)填写实际路径。两个入口都位于本仓库：`scripts/start_comsol52a.py --backend livelink` 提供四个 LiveLink 工具；`--backend mph` 启动原有的模型、几何、网格、求解和导出工具服务。启动脚本会定位仓库内的 loader，不要再保留旧的 `JAVA_TOOL_OPTIONS=-agentpath:...` 设置。

注册后新建 Codex 对话，让它加载工具。先调用 `status` 读取当前状态，再根据需要启动服务器。每次 `run_matlab` 都生成独立目录，保存脚本、标准输出和错误日志。

## 验证与使用边界

仓库内的 [comsol-automation 技能](skills/comsol-automation/SKILL.md)保存了已验证的 5.2a LiveLink 流程、原模型保护要求和结果检查方法。这是用 Codex 为本机编写的技能。可按[英文说明](README.md#codex-skill)，将 Codex 技能目录中的入口链接到本仓库源码；已有技能应先备份。技能不会自动注册 MCP 或安装运行环境。

即使仓库和输出都在 D 盘，COMSOL 仍可能向 C 盘用户目录写入恢复文件和日志。这些文件需要单独核查，不能把整个 `.comsol` 目录当缓存删除。

```powershell
$env:COMSOL_ROOT = 'D:\Program Files\COMSOL\COMSOL52a\Multiphysics'
$env:MATLAB_EXE = 'D:\Program Files\MATLAB\R2025b\bin\matlab.exe'
.\runtime\python52a\Scripts\python.exe .\scripts\verify_livelink52a.py
```

脚本通过真实 MCP 协议启动服务并求解一维 PDE，验收值是中点 `u=50`。报告记录退出结果、日志、进程、2036 端口以及实际输出文件。存在其他 COMSOL/MATLAB/Java 会话时脚本会退出，不接管已有进程。

批处理返回码 0 或端口监听不等于求解成功，必须一起检查求解日志、数值和输出 MPH。本轮原始 `comsolbatch.exe` 还在网格拓展阶段出现过独立失败；不要把 LiveLink 通过写成所有启动路线都通过。

处理自己的模型时，请先复制 MPH，另存求解结果。模型物理场、边界和容差要可追溯；较新 COMSOL 版本的 API 示例不能直接当作 5.2a 的依据。

停用时删除对应 MCP 配置即可。运行环境和日志留在仓库中，停掉相关进程后可按需清理，COMSOL 安装目录没有文件需要还原。

## 来源

本项目基于 [wjc9011/COMSOL_Multiphysics_MCP](https://github.com/wjc9011/COMSOL_Multiphysics_MCP)，代码许可证见 [LICENSE](LICENSE)。原版的[英文工具说明](docs/upstream-guide.md)和[中文说明](docs/upstream-guide-zh.md)仍然保留，其中较新版本的示例需要另行核对。
