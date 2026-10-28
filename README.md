<p align="center">
  <img src="./ICON.png" width="256" height="256" alt="XWUIDCollection">
</p>
<h1 align="center">XWUIDCollection</h1>

xwuid小合集，依赖 [XutheringWavesUID](../XutheringWavesUID) 的数据与渲染。
每个子目录（`wwncee`、`wwbingo`、`wwtappo` …）是一个独立小功能，统一挂在 `ww` 前缀下（可在插件管理里改前缀）。

## 指令

| 指令 | 说明 |
| --- | --- |
| `wwc帮助` / `ww合集帮助` | 本合集帮助 |
| `ww高考` | 鸣潮成绩单（需有已上传记录总排行） |
| `ww宾果` | 6×6 角色宾果图 |
| `ww充值` / `ww充钱` | 充值商品列表；`ww充值1+2` 等生成订单确认图 |
| `wwtp` / `wwtappo` | Tappo 开箱，一次十连；`wwtp10` 为 10 次十连 |
| `wwtp图鉴` | Tappo 收集图鉴，可筛选 `角色` / `配件` / `表情`、稀有度、系列或角色名，如 `wwtp图鉴长离表情` |
| `wwtp合成` | 一键合成：同品类同稀有度 10 份重复升一阶，最高阶 5 份换一个未拥有的 |

## 配置

`data/XWUIDCollection/config.json`：

- `BingoRoleIds`：6×6 = 36 个角色ID（行优先）。**留空 → 每次随机生成合法组合**；填了就用填的（不足随机补、超出截断）。想固定成参考图顺序，把 `wwbingo/config.py` 里的 `REFERENCE_BINGO_IDS` 填进来即可。
- `BingoWith4Star`：随机时是否带四星，默认关（只随五星）。标题也随之自动切换（`鸣潮五星角色` / `鸣潮角色`）。

`data/XWUIDCollection/tappo.json`：每日开箱上限（默认 100）、各稀有度概率、史诗保底、十连保底，默认按官方（90 / 9.5 / 0.49 / 0.01，无保底）。

开箱记录存在 `data/XWUIDCollection/tappo/`，按当前特征码区分（`切换` 后看的是另一份）：有 token 的存 `uid/<uid>.json`（token 过期也算），仅绑定存 `user/<user_id>_<uid>.json`，未绑定存 `user/<user_id>.json`；绑定或登录后旧记录自动并入。每日次数跟着这份记录走。

充值默认仅预览，在控制台 `XWUIDCollectionRecharge` 开启「允许下单」后可下单，开启后自行负责。
