<p align="center">
  <img src="./ICON.png" width="256" height="256" alt="XWUIDCollection">
</p>
<h1 align="center">XWUIDCollection</h1>

xwuid小合集，依赖 [XutheringWavesUID](../XutheringWavesUID) 的数据与渲染。
每个子目录（`wwncee`、`wwbingo` …）是一个独立小功能，统一挂在 `ww` 前缀下（可在插件管理里改前缀）。

## 指令

| 指令 | 说明 |
| --- | --- |
| `ww高考` | 鸣潮成绩单（需有已上传记录总排行） |
| `ww宾果` | 6×6 角色宾果图 |

## 配置

`data/XWUIDCollection/config.json`（统一在此）：

- `BingoRoleIds`：6×6 = 36 个角色ID（行优先）。**留空 → 每次随机生成合法组合**；填了就用填的（不足随机补、超出截断）。想固定成参考图顺序，把 `wwbingo/config.py` 里的 `REFERENCE_BINGO_IDS` 填进来即可。
- `BingoWith4Star`：随机时是否带四星，默认关（只随五星）。标题也随之自动切换（`鸣潮五星角色` / `鸣潮角色`）。
- `BingoUIStyle`：宾果界面样式，可在 GsCore 控制台下拉选择。`classic` 使用原版界面，`wcl` 使用深色黄边连线收集图风格。
