# FMSDD 错误日志（原名 FMODD）

本文件记录已经定位并修复的问题（现象 → 根因 → 修复 → 回归证据），以及已知但尚未处理的问题。新问题先在这里登记，再决定是否进开发轮次。

## 第 75 轮（V2.9.4Beta，2026-10-21）

### E75-01 家庭首页信息堆叠导致操作层级混乱

- **现象**：家庭页同时常驻统计、家长、子女基本资料、成长节点、CA/PA、头像、丹药、试训和青训注册，页面过长且难以判断下一步操作。
- **根因**：`renderFamily()` 只有一个渲染分支，`familyChild()` 把摘要与所有管理操作放在同一张卡片。
- **修复**：新增四个家庭二级分区；总览只显示摘要和入口，子女档案承载按家长筛选的卡片，成长记录独立展示 3/6/9/12 岁节点，青训流程独立展示试训和原生计划状态。
- **回归**：`test_family_workspace_sections_and_academy_status_contracts`、子女/青训聚焦测试通过。

### E75-02 青训状态缺少独立的可读流程视图

- **现象**：用户无法清晰区分「试训通过」「已排入原生青训计划」「等待 FM 生成」「已获得真实 UID」。
- **根因**：旧版只在子女卡片底部显示一行 placement 文案，且没有主动刷新入口。
- **修复**：青训分区显示目标俱乐部、状态、真实 FM UID；增加刷新入口，复用 `/api/life/interactions` 的既有同步链路。仍由 `youth_plans_for_team`、`sync_child_placements` 和 `write_player_portrait` 维护真实数据，不在前端伪造球员。
- **限制**：真实 UID、俱乐部青训名单和头像写入仍依赖连接中的 Football Manager 原生生成周期；本轮未做实机验证。

### E75-03 新家庭文案缺少多语言覆盖

- **现象**：新增家庭分区使用 key 名称回退，非中文/英文语言无法正常显示。
- **根因**：家庭页新增文案未放入现有 children 语言模块，且不应把单语言字符串硬编码进渲染器。
- **修复**：新增 `i18n.family.v294.js`，11 种语言同构覆盖分区、总览、成长和青训文案，并在 `index.html` 中加载。
- **回归**：静态契约检查每个关键 key 均出现 11 次；两个新增 JS 文件通过语法检查。

## 第 74 轮（V2.9.4Beta，2026-10-20）

### E74-01 资产分组点击后展开全部资产

- **现象**：资产页筛选到「车库」等少量资产后，点某个城市或城区，同城其他城区/全部卡片一起展开。
- **根因**：`isOpen` 在小样本时默认所有未显式关闭的分组为展开；点击城市只切换城市键，没有为子城区写 `closed:`；点击城区也没有收起同城其他城区。筛选后旧的展开键也未清理。
- **修复**：打开城市时为所有子城区写 `closed:`，打开城区时为同城其他城区写 `closed:`；筛选时清空 `assetExpanded`；资产赠礼同一逻辑。
- **回归**：静态契约与无头 mock 验证「城市→城区标题→单城区卡片」三级展开。

### E74-02 怀孕 30 天即生产

- **现象**：受孕与预产期只差 30 天，缺少怀胎十月和预产期范围。
- **根因**：`PREGNANCY_GESTATION_DAYS=30`，`settle_periodic_events` 在 due 时才生成抉择事件，事件选择保留后立即创建孩子。
- **修复**：改为 252–301 天窗口、窗口内随机 due；抉择事件在受孕后 30 天才可查看；只有 `kept` 且到 due 才创建孩子；NPC 显示预产期范围。
- **回归**：`test_intimacy_round73.py` 验证保留后当天无孩子、到期才出生；`test_life_interactions_v290.py` 同步新语义。

### E74-03 子女姓名重复姓氏/无成长数据

- **现象**：孩子命名需要输入全名，容易重复玩家姓氏；孩子没有 CA/PA 与培养记录。
- **根因**：`name_child` 直接保存输入全名，`normalize_child` 没有姓氏、CA/PA、培养字段。
- **修复**：档案姓氏 + 名字组合；新增 CA/PA、位置、培养历史/节点/错过节点；新增仙丹与足球事件。
- **回归**：`test_child_training_v294.py` 验证张 + 小明 = 张小明、仙丹年龄上限、事件 CA/PA 提升。

### E74-04 背包礼物必须先进关系页

- **现象**：礼物只能跳转人物互动再赠送，成长仙丹没有背包入口。
- **根因**：背包礼物按钮只调用 `showPage("life-interactions")`；没有仙丹库存接口。
- **修复**：新增目标选择 dialog、`/gift` 直接调用和 `/children/elixir-items` 批量消耗；新增情感/子女商品。
- **回归**：静态契约覆盖 `data-gift-direct`、`data-use-child-elixir`、`inventory-target-dialog`。

### E74-05 商店/家庭界面不符合预期

- **现象**：商店仍是纵向分组，情感商品独立在商店；礼品精品店没有购物车；家庭页只有丹药按钮和立即青训按钮。
- **修复**：商店顶部品类栏（全部/比赛/属性/声望/积分/子女），情感/成人并入礼品精品店情趣类；每个礼物品类补 1–2 件；礼品精品店加入购物车和统一结算；家庭页改为成长仪表盘、3/6/9/12 岁节点、可展开成长档案、青训试训和低级别俱乐部选择。
- **回归**：静态契约与 `test_child_trial_v294.py` 覆盖试训年龄/低级别俱乐部/训练状态。

### E74-06 新品礼物不可见且图标重复

- **现象**：礼品精品店情趣/浪漫商品图标都是火焰，新增 1–2 件礼物没有出现在列表。
- **根因**：卡面只按礼品分类取图标；新增 SKU 只写进 `PRODUCTS`，没有同步到 `SHOP_SKUS`，目录查询把新品过滤掉。
- **修复**：补充全部新 SKU 到 `SHOP_SKUS`；新增 `SKU_ICONS` 逐商品图标。

### E74-07 未满一个月就显示预产期

- **现象**：受孕后立即显示「怀孕中 · 预产期 A–B」。
- **根因**：`public_view` 在 `expecting` 时直接投影 due 字段。
- **修复**：新增 `revealed`；受孕后 30 天内只返回 `possible=true` 并移除 due/days 字段，30 天后才返回预产期范围。
- **回归**：`test_intimacy_round73.py` 验证首月无 due 字段、30 天后显示范围并出现事件。

### E74-08 家庭页信息不足/CA、PA 固定

- **现象**：孩子卡片只有丹药按钮和固定 CA 22/PA 92，家长只是文字，成长事件年龄可被仙丹绕回。
- **修复**：家庭页改为家长列表 + 选中家长子女；出生 CA/PA 按父母影响与随机生成；事件只在 3/6/9/12 岁年龄档触发，跨龄未处理事件过期并记 missed。
- **回归**：`test_child_training_v294.py` 覆盖 CA/PA 范围、年龄档、错过惩罚。

### E74-09 家庭页缺头像/信息不足/事件不出现

- **现象**：左侧家长只有首字；孩子平铺；3 岁只显示节点不出现事件；详情信息少。
- **根因**：家长列表未调用头像组件；子女网格为多列；事件日期随机延后 120 天且卡片没有事件入口；详情只列已处理历史。
- **修复**：家长真实头像；子女单列；成长事件改到生日当刻触发，并在卡片增加 CTA；详情增加位置/CA/PA/生日/性别/各年龄节点/头像/试训。

### E74-10 改名无入口且 15 岁仍可改

- **现象**：改名按钮点开无反应；15 岁后仍可改名。
- **根因**：命名表单仅未命名孩子渲染；前端按钮只 toggle 不存在的表单；后端无年龄校验。
- **修复**：名字右侧改名按钮 + 二次确认 + 15 岁锁定；后端 `name_child` 同样拒绝已命名且满 15 岁。

### E74-11 头像无法进入 FM

- **现象**：15 岁选了头像，进入青训后 FM 里看不到。
- **根因**：头像只存在前端/状态，没有写 graphics 与 config.xml 的逻辑。
- **修复**：新增 `write_player_portrait`，原子写入 `graphics/FMSDD/faces/<uid>.png` 与 `FMSDD/config.xml` 的 person UID 记录；头像在原生青训拿到 player_id 后自动同步。

## 第 73 轮（V2.9.3Beta，2026-10-20）

### E73-01 夫妻无法约会

- **现象**：关系为「夫妻」时约会按钮显示「成为朋友后才能邀请约会」。
- **根因**：前端 `canInviteToDate` 白名单只有社交阶段，没有 `spouse` 等恋爱阶段；后端 `date_plan` 也只检查社交阶段。
- **修复**：前端加入恋爱阶段；后端对 `partner/secret_lover/spouse` 放行。
- **回归**：`test_intimacy_round73.py` 用社交阶段 `acquaintance` 的夫妻成功调用 `date_plan`。

### E73-02 孕期没有「可能怀孕」提示

- **现象**：完成共度夜晚后受孕，但界面一个月内没有提示；到期才突然出现事件。
- **根因**：`public_view` 对 `expecting` 且未到 due_day 的孕期直接清空。
- **修复**：孕期返回 `possible:true`、`days_remaining`；人物卡显示「可能怀孕 · 还有 N 天」；到期事件仍只在 `settle_periodic_events` 中生成。
- **回归**：受孕后 `possible=true`/30 天，到期产生 pregnancy 事件；未受孕无标识无事件。

### E73-03 资产赠礼没有城市/城区/车辆信息

- **现象**：房产赠礼只显示城市名，车辆没有图片、稀有度和车库。
- **根因**：`asset_gift_options` 未投影城市/城区 ID 与车库字段；前端只有平铺卡片。
- **修复**：后端补齐字段；前端增加城市/城区/类型筛选、两级折叠、厂商/等级/稀有度筛选和车辆图片/车库显示。
- **回归**：mock 验证 2 城市 4 城区 20 辆车与 20 张图片。

## 第 71 轮（V2.9.3Beta，2026-10-20）

### E71-01 资产页资产过多时难以浏览

- **现象**：288 处资产平铺成一张长列表，城市/城区信息只在卡片副标题里，难以定位。
- **根因**：`renderPropertiesPage` 只按资产类型过滤，没有分组层级。
- **修复**：按 `city_id → district_id` 两级分组，新增展开/收起（单组与全局），超过 24 处默认折叠城市。
- **回归**：mock 24 处资产 → 2 城市 4 城区；全部收起后卡片为 0，全部展开恢复。

### E71-02 批量购买 100+ 地块耗时数十秒

- **现象**：广州 123 块批量购买耗时 45.1 秒，界面像卡死。
- **根因**：`cProfile` 显示 `deepcopy` 占 42.9 秒：`_city_profile()` 每块地深拷贝含地形多边形的整份城市画像；`save_state()` 对已规范化的整份存档再次 `normalize_state` 深拷贝。
- **修复**：城市画像改为 `MappingProxyType` 缓存视图；`save_state(normalized=True)` 跳过二次规范化；定价与扣款拆成 `prepare` + 单次提交，扣款前在锁内重新过滤已持有地块。
- **回归**：广州 45.1s → 0.84s，深圳 0.52s，`prepare` 0.71s；新增测试确认 `prepare` 不扣款。

### E71-03 子女「家庭」页整页空白（只有标题）

- **现象**：切换到「家庭」后只剩标题与「还没有子女」，任何点击都没有反应。
- **根因**：`familyChild()` 使用了 `money()`，但 `money` 只在 `life_page.js` 内定义，`interactions_page.js` 抛出 `ReferenceError`，`paintWorkspace()` 中断，界面停留在上一个标签。
- **修复**：改用 `bridge().formatMoney` 的 `familyMoney()`，并把丹药名走 `life.interactions.family.elixir_name.*` 本地化。
- **回归**：mock 15 岁子女 → 1 张卡片、2 个丹药按钮、2 个投放按钮；无控制台异常。

### E71-05 「加入我的俱乐部青训」提示没有俱乐部

- **现象**：15 岁子女点击「加入我的俱乐部青训」提示「请先读取带当前俱乐部的存档」，即使已连接俱乐部。
- **根因**：`_life_interaction_view` 末尾重新赋值 `view["manager_identity"]` 时只保留 `id/name/team_name`，把前面写入的 `team_id` 覆盖成空，前端拿不到目标球队。
- **修复**：最终赋值保留 `managed_team_id` 与 `managed_club.name`；`_managed_club_target` 在俱乐部对象缺少 team id 时回退 `_life_manager_team_id()`。
- **回归**：API 测试设置 `club.team_id=42` 后，`manager_identity.team_id == 42`。

### E71-06 青训完成后子女状态一直停在「已排入」

- **现象**：青训计划已完成，子女卡片仍显示「已排入」，不出现球员 ID/「已在青训」。
- **根因**：`_child_placement_status_rows` 只读取 `active_youth_generation_plans`，该函数只返回 armed/waiting，天然看不到 completed 计划。
- **修复**：按子女 placement 的 team_id 调 `youth_plans_for_team`，读取 completed/refunded 计划及 `ability_result`；`sync_child_placements` 映射为 `playing`/`rejected`；rejected 允许重新投放。
- **回归**：`test_child_placement_status.py` 用 completed 计划同步到 `playing`；rejected 子女 `ready=True`。

### E71-07 中文子女名无法进入原生青训计划

- **现象**：中文名子女投放时配置被回退成 `Junior`，游戏内看不到玩家起的名字。
- **根因**：`ACADEMY_SON_NAME_PATTERN` 只接受 `[A-Za-z]{2,30}`，`child_academy_plan_config` 因此主动转 ASCII。
- **修复**：允许 Unicode 字母/空格/撇号/连字符（仍禁止数字与下划线），`child_academy_plan_config` 直接使用子女名；原生写入本身使用 UTF-8。
- **回归**：`小明` 可通过 `normalize_youth_plan_config`，`Alex 2` 仍被拒绝；测试已更新。

### E71-04 青训「指定子女投放」是否可行

- **现象**：需要确认能否在青训生成时把玩家指定子女投放进对应俱乐部。
- **证据**：REA 静态读取随包 `fmodd_hook_core.dll` 与 `fmodd_native_core.dll` 导出表，两者都没有青训相关导出；生成逻辑在 `src/tools/youth_generation_hook.py`，按 `GameLayout.youth_generation_gate_hook_rva / pa_hook_rva / state_hook_rva / son_hook_rva` 写运行时补丁。
- **结论**：复用 `academy_son` 计划即可完成投放，本轮新增的 `POST /api/life/interactions/children/academy` 直接调用 `arm_youth_plan` 并同步钩子。
- **限制**：静态证据，未在真实 FM 进程中验证；需要实机存档确认生成结果。

## 第 70 轮（V2.9.3Beta，2026-10-20）

### E70-01 余额 1.5 京时批量购买仍返回“请求无效”

- **现象**：北京 121 块地总额约 £22.3 亿，弹层显示可用资金 £1.5 京（约 1.5×10¹⁶），远高于总额；点击购买仍只显示“请求无效”。
- **根因**：后端批量购买调用
  `charge_combined_funds(amount, "life_property_batch_buy", ..., kind=kind, ...)`
  时，`kind` 既作为第二个位置参数传入，又作为关键字参数重复传入，Python 在扣款前直接抛出
  `TypeError: charge_combined_funds() got multiple values for argument 'kind'`；
  旧错误映射没有保留这个非 `ValueError` 细节，最终落到通用 `error.invalid_request`。与余额完全无关。
- **修复**：详情字段改为 `property_kind=kind`，不再与扣款函数的 `kind` 形参冲突；同时把读取存档、规划、扣款、提交的异常全部转换为可读错误，并写入 `Documents/FMODD/runtime/request-errors.log`。
- **回归**：新增 `tests/test_batch_purchase_charge_kind.py`，用真实函数签名断言 `property_kind` 不再穿透 `kind`。读取实际存档 `322857.manager-2002132538` 的临时副本，真实执行 120 块地扣款、提交、`public_view`：成功，金额 `2,218,770,921.21`，总地块从 3 增至 123；真实账户未被修改。

### E70-02 批量管理 footer 仍被弹层底边裁切

- **现象**：列表滚动正常，但最下方“移入车库”和“迁移/出售”按钮的下半截仍被弹层底边切掉。
- **根因**：前几轮只把 footer 设为 sticky/flex，footer 仍留在滚动内容宿主内；宿主高度、`overflow` 和弹层底边的组合会把按钮推到可视区外。
- **修复**：把 footer 从 `#life-garage-bulk-content` 移到 `.life-collection-dialog-shell`，使用绝对定位 `bottom:12px`；宿主按 footer 实际高度写入 `padding-bottom`，列表保持独立滚动，footer 不再参与内容高度竞争。
- **回归**：mock 28 辆车 + 长车库名，footer 完整位于弹层内；出售按钮矩形不再超出弹层底边。

### E70-02b 资产领取按钮点击无反应：拖动监听吞掉 click

- **现象**：资产等级卡片上的「领取车辆」按钮点击后没有任何请求或提示。
- **根因**：战令轨道在 `pointerdown` 上为了鼠标拖动执行 `preventDefault()` 和 `setPointerCapture()`，按钮也在轨道内，导致浏览器不派发后续 `click`。
- **修复**：拖动只对非交互目标生效；`pointerdown` 命中 `button/a/input/select/textarea/[role=button]` 时直接返回，不 preventDefault、不捕获指针。领取动作增加 loading、内联错误、成功后的本地视图刷新。
- **回归**：资产卡按钮恢复点击事件；领取中/失败/成功均有可见状态。

### E70-03 寄存车库容量写死 100

- **现象**：旧存档与新存档的寄存车库都只有 100 个车位，与 10000 容量需求不符。
- **根因**：`STORAGE_GARAGE`、`normalize_state` 的 storage 分支和前端回退值都写死 100；11 语言说明也写着 100。
- **修复**：统一改为 10000；旧 storage 读取时强制迁移；更新容量说明和测试夹具边界。
- **回归**：`test_storage_capacity_is_10000_for_new_and_legacy_saves`、storage/garage 子集 13 passed。

### E70-04 资产车辆自动发放导致满库时奖励丢失/不可领取

- **现象**：达到等级后车辆自动发放，车库满时只记录错误；玩家没有领取动作，也不清楚如何重试。
- **根因**：`sync_asset_level_rewards` 在每次视图刷新时尝试自动 `grant_vehicle_award`，把“查看”与“领取”混在一起。
- **修复**：同步只发属性点；新增显式领取接口和按钮；领取时优先 storage，再 club/任意车库；全部满时返回明确错误并保留未领取状态。
- **回归**：2–7 级车辆、storage 优先、后备车库、全满失败均通过；旧存档 2–6 级补车辆 ID 但保留未领取。

### E70-05 属性点记录显示内部代码

- **现象**：编辑档案的属性点记录出现 `asset_level`、`asset-level:7`、`vehicle-000405` 等内部字段。
- **根因**：`ledgerRow` 只查了旧 source 翻译，资产等级 source 不存在；reference 直接原样输出。
- **修复**：新增 11 语言 `ledger_source.asset_level`，解析 `asset-level:N`，车辆记录改用可读文案，隐藏内部 ID。
- **回归**：mock 档案显示“资产等级奖励 / 等级 7”“车辆奖励记录”。

### E70-06 声望依赖 FM 只读数据且显示 0 / 10000

- **现象**：FM26 布局没有可验证的 staff reputation 偏移，界面仍显示 `FM 声望：0 / 10000`，且声望不能像其他属性一样分配。
- **根因**：声望被设计成 FM 经理只读投影，不可用时仍渲染 scale/domestic/world 并传入 `null ?? 0`。
- **修复**：取消 FM 声望读取与所有 FM 标识；声望改为可分配属性，每点 5 属性点，保留金色样式；旧档通过 `reputation_migration` 保持可用点。
- **回归**：档案属性卡含金色声望、5 点成本、固定保存栏；不再出现 FM 文案或 0/10000。

## 第 69 轮（V2.9.2Beta，2026-10-20）

### E69-01 倍率按钮放在右侧操作区，单抽/十连只剩一个按钮

- **现象**：V2.9.1 的倍率按钮与目录/记录按钮挤在卡片右上角，抽取只有单按钮；倍率只改变单次抽数，无法快速十连。
- **根因**：V2.9.1 为了节省横向空间把倍率放进 `life-gacha-tier-actions`，并用 `draws=multiplier` 合并了两种抽取。
- **修复**：倍率移入标题行右侧；恢复两个按钮，`draws=multiplier` 与 `draws=multiplier*10`，价格分别计算；后端允许 1–1000 抽。
- **回归**：mock 页 3 池均显示单抽 ×1 / 十连 ×10，价格正确；`test_life_v292.py` 验证 3 抽价格与上限。

### E69-02 弹窗打开时 paint 被跳过，释放车位后抽卡按钮仍禁用

- **现象**：从寄存车库移出车辆后，关闭弹窗回到抽卡页，按钮仍显示禁用，直到下一次轮询或切换页面。
- **根因**：`paint()` 为避免弹窗内滚动/图片闪烁，在任意 life 弹窗打开时提前返回；`closeStorageDialog()` 只关闭弹窗未重绘，`state.data` 已更新但 DOM 未更新。
- **修复**：寄存/车库批量弹窗关闭后主动 `paint()`；抽卡按钮按最新 `garage.free` 重算。
- **回归**：mock 页面关闭寄存弹窗后按钮状态刷新；无头验证 `free=12` 时两组按钮可用。

### E69-03 批量管理底部操作区被长列表挤出视口

- **现象**：车辆很多时，批量弹窗只显示列表，底部的选中价值、目标车库、迁移/出售按钮不可见。
- **根因**：弹窗 shell 高度随内容增长，车辆列表没有独立滚动容器，指标/按钮成为列表后的普通流内容。
- **修复**：shell 固定高度，内容列 flex；列表独立滚动，footer 固定在底部；选择只局部刷新，不重建列表。
- **回归**：mock 28 辆车，列表 302px 独立滚动（scrollHeight 1300），footer 和按钮在 867px 视口内可见。

### E69-04 寄存车库勾选后列表跳回顶部

- **现象**：在寄存车库向下滚动后勾选车辆，列表立即回到顶部，无法连续选择。
- **根因**：`change` 事件调用 `paintStorageDialog()`，整窗 `innerHTML` 重建，滚动容器被重置；`paintStorageResults()` 再次重建列表。
- **修复**：新增 `refreshStorageSelectionUi()`，只更新选中数、估值、按钮、目标车位提示和警告，不替换列表 DOM。
- **回归**：mock 页面滚动到 900px 后勾选第 21 行，勾选前后 `scrollTop` 均为 900。

### E69-05 战令轨道与进度条共用 `.interaction-asset-pass-track`，卡片高度塌陷

- **现象**：资产等级弹层只显示一排卡片顶边和横向滚动条，卡片内容不可见。
- **根因**：进度条 `.interaction-asset-pass-track` 的 `height:9px; overflow:hidden` 同时命中了战令卡片轨道。
- **修复**：卡片轨道改名 `.interaction-asset-pass-rail-track`，进度条保留原名；轨道高度由卡片撑开。
- **回归**：mock 页面 12 张卡片可见，轨道 `scrollWidth=2651`、`clientWidth=1074`，当前 Lv.7 居中 `scrollLeft=899`。

### E69-06 资产等级弹窗仍按固定高度留白

- **现象**：战令内容只有约 660px，弹窗仍占满 843px，底部空白。
- **根因**：`.life-collection-dialog` 的固定 `height:min(880px, ...)` 比内容高；仅设置 `height:auto` 在模态 dialog 上仍被最大化。
- **修复**：资产等级 dialog 改为 `height:fit-content`，shell 高度自适应，内容区滚动。
- **回归**：弹窗高度贴合内容，战令卡片和提示完整显示。

## 第 68 轮（V2.9.1Beta，2026-10-20）

### E68-01 地产/车库批量弹窗放在隐藏页面内，showModal 后尺寸为 0

- **现象**：无头页面中 `#life-map-bulk-dialog` 的 `open=true`、`:modal=true`，但 `getBoundingClientRect()` 为 0×0，截图看不到弹窗。
- **根因**：两个 `<dialog>` 最初写在 `#page-life-map` / `#page-life-garage` 的 section 内；当所在页面不是当前页时，祖先 `display:none` 使 dialog 即使进入 top layer 也不参与渲染。
- **修复**：`openMapBulkDialog` / `openGarageBulkDialog` 首次打开时把 dialog 移到 `document.body` 并补 `life-page` 类，与既有 storage dialog 的做法一致。
- **回归**：无头 mock 页面打开后 parent 为 `BODY`、760×775，内容可见。

### E68-02 批量弹窗沿用固定高度壳，底部出现大面积空白

- **现象**：资产等级、地图批量购买弹窗内容只有上半屏，壳仍占满视口高度。
- **根因**：`.life-collection-dialog-shell` 默认高度适配内容较长的弹窗，资产/批量内容较短。
- **修复**：为资产、地图批量、车库批量弹窗增加 `height:auto; max-height:calc(100vh - 32px)`，内容区独立滚动。
- **回归**：弹窗高度贴合内容，仍保留长列表滚动。

### E68-03 全局替换版本号改到了 V2.9.0 历史段落

- **现象**：README.zh-CN / README.ko-KR 的 V2.9.0 历史段被写成“同步为 V2.9.1Beta / 2.9.0.0 / 64-dev”。
- **根因**：批量替换 `**V2.9.0Beta**` 时未区分“当前版本表”和“历史发布记录”。
- **修复**：把历史段落恢复为 V2.9.0Beta / 2.9.0.0 / 64-dev；当前版本表和徽章保留 V2.9.1Beta。
- **回归**：`Select-String` 检查历史段与当前段一致。

### E68-04 版本升级后测试仍断言 64-dev

- **现象**：`test_round49_exact_gold_statistics_and_luck_contract_and_translations` 失败。
- **根因**：测试硬编码旧开发标识。
- **修复**：更新为 `68-dev`。
- **回归**：`tests/test_life_system.py` 通过。

### E68-05 i18n 静态目录没有加载 v291 模块

- **现象**：`test_i18n_static` 报 `life.map.bulk_eyebrow` 在 en-GB/zh-CN/ko-KR 缺失。
- **根因**：测试的 `_catalog()` 文件列表与 index 脚本顺序仍停留在 v290。
- **修复**：把 `i18n.interactions.v291.js` 加入 catalog 与脚本顺序断言。
- **回归**：`tests/test_i18n_static.py` 5 passed。

## 第 67 轮（V2.9.0Beta，2026-10-19）

### E67-01 静音判定若只看未读，未勾选时也不会提醒（预防性修复）

- **现象（推演）**：沿用旧逻辑 `if (!announcementUnread()) return;` 时，未勾选“不再提醒”的第二次启动也不会弹出，与需求相反。
- **根因**：旧逻辑只按未读判定，没有“是否静音”这一维。
- **修复**：提前返回条件改为 `announcementMuted() && !announcementUnread(entries)`；未静音无条件弹出，静音时只在未读时弹出。
- **回归**：`test_announcement_mute_preference_controls_the_startup_popup` + 无头 Edge 行为测试。

### E67-02 赞助说明生硬、没有说明用途与“不影响使用”（已修复）

- **现象**：原文只写“赞助完全自愿，不解锁任何功能”，缺少成本背景，读者容易误解为变相收费或觉得突兀。
- **根因**：文案只做了免责声明，没有说明项目投入与赞助去向。
- **修复**：改为先说明“不影响任何功能、不解锁内容、不是购买授权”，再补充自费 150+ 元、累计约 20 亿 token、服务器与开发仍在投入，语气更委婉。
- **回归**：11 语言语言包检查与公告文案测试通过。

## 第 66 轮（V2.9.0Beta，2026-10-19）

### E66-01 中文界面下公告标题回退为英文（已修复）

- **现象**：公告正文、状态标签、工具栏都是中文，只有卡片标题是英文（截图示例：`FMSDD V2.9.0Beta Content Change Announcement…`）。
- **根因**：标题是独立语义键 `announce.entry.*.title`，与正文分开维护；当某语言只缺标题键、或标题被写成英文时，i18n 回退到 en-GB，而正文仍命中中文，于是出现“只有标题英文”。旧标题又以 `FMSDD V2.xBeta …` 开头，英文词占比高，进一步放大了观感。
- **修复**：六条标题全部改为内容优先的完整本地化文案，版本交给卡片徽标；新增“非英文语言的标题不得等于英文标题”“中文标题必须含汉字”“中文标题不得以 `FMSDD V` 开头”三项回归。
- **回归**：`tests/test_announcements_frontend.py` 全绿；无头 Edge 实测 zh-CN 六条标题全部中文。

### E66-02 公告图片必须限制来源（已实现）

- **风险**：直接支持 `<img>` 或任意 URL 会让公告具备脚本注入与本地文件探测能力。
- **处理**：图片只接受 `/assets/` 打包资源或 `https://`，拒绝 `data:`、`javascript:`、`../` 与反斜杠；输出统一转义，强制 `alt`、`loading="lazy"`、`decoding="async"`。
- **回归**：`test_markdown_renders_packaged_images_and_rejects_unsafe_sources`。

### E66-03 交流群二维码放进长公告会被折叠遮挡（已修复设计）

- **风险**：把二维码追加到永久公告会在默认折叠高度内被遮住，读者以为没有图。
- **处理**：改为独立的短卡片（3 个块、默认不折叠），二维码 280×280 直接可见；群号写成可复制文本。
- **回归**：无头 Edge 实测 `collapsed=false`、`figure` 存在、图片加载成功。

### E66-04 无头浏览器首帧读取图片得到 0×0（验证方法问题，非产品缺陷）

- **现象**：CDP 打开公告板后立即读取 `naturalWidth` 得到 0，`img.complete=false`。
- **根因**：`loading="lazy"` 图片在布局与滚动容器稳定前不会立即解码，测量发生在渲染后的同一帧。
- **处理**：验证脚本等待 1.5 秒后再读取，得到 640×640 与 280×280 的实际显示尺寸；产品代码不需要改为 eager，避免一次性解码所有卡片图片。
- **回归**：`tests/test_announcements_frontend.py` 只断言标记结构，真实加载由 CDP 验证。

### E66-05 收起高度不统一、正文被截在半句（已修复）

- **现象**：两条公告收起后显示的内容长度不同，长公告只在卡片底部露出一小段并被渐变截断，读者无法判断“收起”代表多少内容。
- **根因**：是否折叠由正文长度/块数判定，但卡片之间没有统一的预览高度契约；旧构建上 `is-collapsed` 的最大高度甚至没有生效，导致长短不一。
- **修复**：把收起高度收敛为单一变量 `--announcement-collapsed-height: 220px`，所有可折叠卡片共用；展开时移除 `max-height` 与 `overflow` 限制，完整显示全文；“交流群”卡片保持 `alwaysOpen`，避免二维码被折叠遮挡。
- **回归**：无头 Edge 实测五条可折叠公告收起高度均为 220px，展开后 `height == scrollHeight`（如 354px）且按钮切换为“收起”；`test_collapsed_cards_share_one_preview_height`。

## 第 65 轮（V2.9.0Beta，2026-10-19）

### E65-01 德语公告被英文功能词检查误判（已修复）

- **现象**：`test_extension_locale_packs_have_no_english_function_word_fallbacks` 报德语 `announce.entry.v280_launch.body`、`announce.entry.feature_guide.title` 与 `announce.entry.feature_guide.body`。
- **根因**：德语疑问词/关系词 `was`（意为“什么”）与检查器的英文功能词表同形，按整词匹配被当成英文回退；文案本身并非英文。
- **修复**：三处改写为 `und nicht markierte Wettbewerbe`、`Alles vor V2.7.0: die Funktionen der Software`、`Sichert den Spielstand vor jedem Schreibvorgang.`，事实不变。
- **回归**：`tests/test_i18n_locale_packs.py` 12 项全部通过。

### E65-02 西语公告标题重复键（已修复）

- **现象**：`test_extension_locale_packs_do_not_generate_or_duplicate_fake_copy` 报 `announce.entry.v280_launch.title` 在同一对象中出现两次。
- **根因**：西语 V2.8.0 公告标题整行被复制，属于历史迁移残留。
- **修复**：迁移时对“相邻且完全相同”的整行只保留一行；其余键未受影响。
- **回归**：语言包重复键检查通过。

### E65-03 繁中公告残留「校驗」（已修复）

- **现象**：`test_traditional_chinese_pack_uses_taiwanese_ui_and_football_terms` 报 `校驗`。
- **根因**：繁中公告正文沿用大陆用词。
- **修复**：公告正文统一改为「驗證」。
- **回归**：繁中术语检查通过，且本轮新增繁中文案未引入简体专用字。

### E65-04 排序切换在当前公告集下结果相同（已知行为，非缺陷）

- **现象**：当前五条公告里只有 V2.9.0 一条普通置顶，永久公告固定第一，因此“置顶优先”和“最新优先”顺序一致。
- **说明**：实现按“永久 → 置顶 → 其余（各组时间倒序）”和“永久 → 其余（时间倒序）”两种规则计算；已有用例覆盖“置顶更旧、普通更新”的场景，公告增多后差异自然出现。
- **回归**：`test_newest_sort_overrides_pinning_but_keeps_the_permanent_notice`。

### E65-05 Markdown 链接正则未消费不安全目标（已修复）

- **现象**：`[x](javascript:alert(1))` 被渲染为 `x)`，残留一个右括号。
- **根因**：首版链接正则用 `[^)\s]+` 截取目标，遇到嵌套括号提前结束。
- **修复**：目标允许一层嵌套括号 `(?:[^()\s]|\([^()]*\))+`；不安全目标只保留标签文本并消费整个链接。
- **回归**：`test_markdown_escapes_html_and_rejects_unsafe_links`。

## 第 64 轮（V2.9.0Beta，2026-10-19）

### E64-01 交付前地形包只覆盖 59/68 城，新增城市会回退到无地形掩码

- **现象**：构建 68 城目录后检查 `city_terrain.json`，发现仅 59 个城市有地形数据，缺少杜塞尔多夫、马德里、布鲁塞尔、阿姆斯特丹、东京、名古屋、大阪、首尔、釜山。缺失城市虽然仍能生成资产，但无法使用水域/绿地多边形避让，存在把资产生成到海面、河面或公园的风险。
- **根因**：地形数据由维护脚本逐城抓取并增量写入；前一次命令覆盖到汉堡后尚未完成剩余城市，目录扩展与地形包完成状态之间没有交付前强制校验。
- **修复**：继续运行 `scripts/build_life_terrain_data.py`，逐城写入剩余 9 城；最终地形包包含 68/68 城市、13,403 个水域多边形与 15,384 个绿地多边形。运行时仍只读取本地 JSON，不发起网络请求。
- **回归**：`test_city_terrain_pack_covers_every_catalog_city_and_has_valid_rings` 与 68 城目录/避让测试通过；地形文件 41,459,736 bytes，缺失城市集合为空。

### E64-02 情商对数缩放把高属性收益压得过平

- **现象**：初始实现使用 `log10(1 + eq)` 计算情商系数，低值约 0.88、满值约 1.05，玩家把情商从 1 加到 100 的差异不够明显，无法体现“同样做法因属性不同而结果不同”的设计目标。
- **根因**：对数缩放适合防止极端值爆炸，但在本作 1～100 的常规分配区间内过早饱和，且与其它三项属性的线性区间不一致。
- **修复**：改为在 1～100 区间线性映射到 0.80～1.20；超过 100 的部分仍由 `_social_attribute_value()` 截断，保留防刷上限。
- **回归**：`EmotionalIntelligenceTests.test_higher_eq_improves_action_and_gift_results`、`SocialAttributeTests.test_appearance_ability_charisma_and_eq_drive_different_dimensions`、`test_social_effects_are_bounded_above_attribute_100` 均通过；互动域全套 86 项测试通过。

### E64-03 既有公告本地化检查仍有 3 项旧债（未在本轮修改）

- **现象**：运行 `tests/test_i18n_locale_packs.py` 时，西班牙语 `announce.entry.v280_launch.title` 出现重复键；德语公告正文残留英文功能词回退；繁中公告正文仍含旧的“校驗”用词。新增的 `i18n.interactions.v290.js` 自身键值与 11 语言静态测试通过。
- **根因**：这些内容来自 V2.8.0 公告历史稿，不是第 64 轮新增文案；当前轮的需求不涉及公告改稿，避免扩大范围未改动。
- **处理状态**：已记录，留待下一次公告或本地化专项统一修复；发布前已确认不影响本轮新增互动文案的键值完整性。
- **回归边界**：`tests/test_i18n_static.py` 通过；`tests/test_i18n_locale_packs.py` 的上述 3 项为已知未处理项，不能据此宣称整个本地化套件全绿。
## 第 63 轮（V2.8.9eBeta，2026-10-19）

### E63-01 结算弹窗右侧大片空白、按钮过高且内容松散

- **现象**：聊天、赠礼、约会与关系推进的结果弹窗沿用旧版 `life-collection-dialog-shell` 双栏壳，左列内容很高、右列长期空白；确认按钮被拉到整行高度，信息层级散乱，用户明确要求完全重制。
- **根因**：结果弹窗复用了为收藏/列表场景设计的双栏容器，内部没有独立的结果卡布局；内容区使用 `height: 100%`，在只有一列内容时把剩余高度分配给空列，按钮也被网格行拉伸。
- **修复**：结果弹窗改为 `interaction-result-dialog` + `interaction-result-card` 单栏结构，内容按“人物/结果 → 对白 → 数值 → 增益 → 确认”排列；确认按钮固定为 42px 高、112px 最小宽度，不再继承双栏壳。
- **回归**：`test_action_results_use_a_self_contained_single_column_card` 断言结果弹窗不含 `life-collection-dialog-shell`，并检查单栏卡、上下文、奖励与底部样式；JavaScript 语法检查通过。

### E63-02 亲密行为名称显示为空

- **现象**：亲密度面板中的行动按钮和结果标题只显示图标或空白，没有“拥抱”“亲吻”等名称。
- **根因**：`intimacyActionLabel()` 读取 `life.interactions.intimacy.action.<id>.label`，但 11 语言文案统一使用 `.title` 键，`t()` 返回键名或空值。
- **修复**：改为读取 `.title`；结果卡、时间线与 toast 共用同一标签函数，避免三处不一致。
- **回归**：前端契约检查 `intimacyActionLabel()` 读取 `.title`；API 测试确认 `result.action` 与 `action_cost` 返回。

### E63-03 亲密关系结算说明无法识别保密情人与夫妻

- **现象**：情侣关系会出现专属说明，但保密情人和夫妻关系的结果卡说明为空或退回通用文本。
- **根因**：`showActionResult()` 的关系备注只判断 `partner`，而服务端 `effective_romance_stage` 还会返回 `secret_lover` 与 `spouse`。
- **修复**：备注分支补齐 `secret_lover` 与 `spouse`，并对 `none` 与空值保持不显示；对白上下文仍由服务端稳定生成。
- **回归**：11 语言 `dialogue.partner_note`、`secret_lover_note`、`spouse_note` 键全部存在且占位符同构。

### E63-04 亲密行为结果卡显示消耗 0 行动点

- **现象**：亲密行为提交成功，但结果卡“行动力消耗”显示 0，用户无法确认本次行动实际扣了多少点。
- **根因**：`_action_payload()` 没有把 `action_cost` 合并进顶层结果，前端只能回退读取 `result.dialogue.action_cost`，而亲密行为对白不携带该字段。
- **修复**：`_action_payload()` 增加 `action_cost` 参数并写入结果；`intimacy_plan()` 传入实际 AP 成本，结果卡优先读取顶层字段。
- **回归**：`IntimacyTests.test_intimate_action_spends_action_points_and_intimacy` 断言 `action_cost=1`、亲密度剩余 17、行动点剩余 11。

### E63-05 schema 6 迁移后旧测试仍期待 schema 5

- **现象**：亲密度字段加入后，`normalize_state()` 正确返回 schema 6，但旧迁移测试仍断言 schema 5，定向测试出现 1 处失败。
- **根因**：测试与实现同轮升级时漏改版本断言。
- **修复**：迁移测试改为断言 schema 6，并保留对人物、关系、行动点与空流水的原断言。
- **回归**：`test_schema_five_migration_preserves_existing_people_and_points` 通过；完整定向测试 148 项全部通过。

### E63-06 亲密行为可用性测试与夫妻专属行动互相矛盾

- **现象**：测试先断言情侣的所有亲密行动都可用，随后又断言“谈论未来”不可用，导致同一测试自相矛盾。
- **根因**：新增 `future_plan` 仅夫妻可用后，旧断言仍把全部行动视为情侣可用。
- **修复**：测试只对 `stages` 包含 `partner` 的行动断言可用，并继续单独断言 `future_plan` 因阶段限制不可用。
- **回归**：`test_committed_stages_expose_intimacy_actions_and_public_view` 通过，且夫妻阶段 `future_plan.available=true`。

### E63-07 资产赠送成功后结算卡标题误显示为“交谈”

- **现象**：资产赠送流程已成功完成永久转移，但结果卡顶部标题显示成“交谈”，玩家会误以为提交了错误行动。
- **根因**：`commit_asset_gift()` 返回的领域结果缺少 `kind="asset_gift"` 判别字段；前端统一结果卡按 `kind` 选择标题，缺省时回退到聊天文案。
- **修复**：在 `commit_asset_gift()` 返回值中补齐 `kind`，并增加领域断言，确保资产赠送结果与聊天、普通行动保持同一结果契约。
- **回归**：`test_item_gift_and_permanent_asset_gift_flow` 断言 `result["kind"] == "asset_gift"`；人物互动聚焦测试全部通过。

## 第 62 轮（V2.8.9dBeta，2026-10-19）

### E62-01 赠送与邀请按钮白字透明底，只有悬停时可见

- **现象**：礼物选择弹窗和约会选择弹窗的确认按钮在默认状态下几乎不可见，鼠标移上去才出现背景，用户无法判断哪里可以点击。
- **根因**：`--int-*` 颜色变量只定义在 `.interactions-page` 内，而弹窗是 `body` 下的独立 `<dialog>`，按钮拿到 `var(--int-green)` 的空值，形成白字透明底。
- **修复**：把变量作用域扩展到 `.interaction-result-dialog`、`.interaction-chat-dialog`、`.interaction-choice-dialog`、`.interaction-profile-dialog` 与 `.interaction-ap-ledger-dialog`；禁用主按钮增加可见背景与边框，确认按钮增加阴影。
- **回归**：前端契约检查弹窗变量作用域与 `.interaction-choice-actions .interaction-button:disabled` 样式；11 语言按钮文案测试通过。

### E62-02 交谈发送按钮无法提交消息

- **现象**：聊天弹窗中的发送按钮显示正常，输入文字后点击没有反应，也不会扣除行动力。
- **根因**：`handleSubmit()` 只放行页面根节点和档案弹窗内的表单，新聊天弹窗位于 `body` 下，事件被提前 `return`。
- **修复**：表单门禁加入 `chatDialog()?.contains(form)`；`submitChat()` 继续通过 `performAction()` 扣点并刷新时间线。
- **回归**：`test_chat_workspace_has_a_live_composer_and_submit_gate` 检查聊天弹窗、`data-interaction-form="chat"`、`name="message" maxlength="500"` 和表单门禁；API 测试确认消息写入 `result.message` 与 `timeline.result.message`。

### E62-03 约会卡重复显示行动力，关系状态视觉层级不足

- **现象**：每个约会卡片同时显示右上角和底部两处行动点；人物关系徽标缺少底色，和普通文本混在一起。
- **根因**：约会卡早期为下拉框语义保留了两套成本文本；关系徽标只有全局灰色背景，未为初识、暧昧等状态补色阶。
- **修复**：约会卡只保留右上角闪电图标与大号点数；移除重复底部文本；为 `acquaintance` 与 `ambiguous` 增加独立底色，并统一人物头卡渐变背景。
- **回归**：界面契约检查 `.interaction-date-cost`、`data-date-activity` 与关系徽标样式；`node --check` 通过。

### E62-04 玩家档案中的声望仍被当作可分配属性

- **现象**：玩家档案把声望与颜值、能力、魅力并列，玩家可以消耗属性点提升声望，但游戏内真正的主教练声望没有体现。
- **根因**：档案模型沿用旧版四项属性；FM 经理发现结果没有把 staff reputation 投影到人物互动视图。
- **修复**：可分配属性收缩为三项；旧档案声望保留但不再计入点数。新增 `_manager_reputation()`，从当前经理 staff 完整对象读取 current/domestic/world，服务端投影 `manager_reputation`，前端只读展示 0–100 折算值与原始值。
- **回归**：档案迁移测试覆盖三项初始 `[1,1,1]`、197 可用点、旧四项档案 150 点消费与 50 点余额；API 测试覆盖 `7200` 当前声望与球队身份投影；无偏移布局返回 `available=false`。

### E62-05 旧聊天记录没有可读回复

- **现象**：升级后查看旧聊天时间线，只能看到互动摘要，无法看到当时说过什么，界面会显示空白或“历史不可用”。
- **根因**：旧时间线只保存 `deltas` 与 `topic`，没有 `message` 与 `dialogue`；新弹窗没有兼容回退。
- **修复**：新记录保存消息与模板回复；旧记录按话题生成 `history_reply` 兼容文案；聊天奖励单独成条，避免与回复混淆。
- **回归**：旧记录渲染分支与聊天结果测试通过；11 语言 `history_reply` 占位符同构。

### E62-06 新成品仍内嵌上一轮桌面宿主

- **现象**：源码和桌面工程已升级到 `2.8.9.4`，但第一次封装出的单文件仍携带 `src/desktop_host` 中的 `2.8.9.3` 宿主；若直接交付，窗口标题和宿主版本会与主程序不一致。
- **根因**：`dotnet build` 输出到 `src/desktop/bin/Release/net48`，而 `build_single_exe.py` 固定读取运行资源目录 `src/desktop_host`；旧流程依赖人工复制，步骤遗漏后脚本仍会成功。
- **修复**：打包脚本在暂存前自动同步 Release 宿主，并检查宿主内嵌窗口标题包含当前产品版本；随后重新生成单文件与源码运行包。
- **回归**：成品 FileVersion `2.8.9.4` / ProductVersion `V2.8.9dBeta`；CArchive 内嵌宿主与源码哈希一致，标题包含 `FMSDD V2.8.9dBeta` 且不含旧标题。

## 第 61 轮（V2.8.9cBeta，2026-10-19）

### E61-01 删除按钮加入后关系栏过窄，关系标签被挤断

- **现象**：人物关系列表新增删除按钮后，姓名、球队、关系标签和好感数值相互挤压，部分关系徽标无法完整显示，卡片右上角的排他徽标进一步占用标题空间。
- **根因**：人物工作区左侧列仍沿用第 60 轮的窄宽度，而关系行动作由两列变为“主体 + 删除 + 好感”三列；排他徽标又是额外的独立元素。
- **修复**：关系栏扩展为 `minmax(310px, 350px)`；移除关系卡片右上角的排他徽标，保留关系标签与关系进度中的排他语义；好感数值按五档着色，减少重复标签。
- **回归**：界面契约检查 `minmax(310px, 350px)`、`tone-${affectionTone(affection)}` 与五档颜色选择器；窄窗口继续按既有断点折叠单列。

### E61-02 关系网人物头像显示为姓名缩写

- **现象**：人物档案与关系列表已有头像，但总览关系网仍显示姓名缩写。
- **根因**：关系网使用独立的缩写渲染，没有走档案的 `portraitMarkup()`，因此没有读取头像开关、UID 偏移与 `/api/player-avatar`。
- **修复**：关系网人物按钮改用 `portraitMarkup(row.person, {small: true})`，与档案、列表和互动标题共用同一头像解析链路。
- **回归**：前端契约断言关系网包含 `portraitMarkup(row.person, {small: true})`。

### E61-03 住宅入住需要操作长下拉框，且看不到入住者

- **现象**：住宅入住是一行一条的下拉式选择，确认按钮与资产信息分离；卡片不显示谁已入住，玩家需要退出到关系列表反查。
- **根因**：旧界面只渲染住宅名称、面积与床位，入住者信息没有进入服务端住宅投影；选择、确认与迁出分散在多个控件。
- **修复**：`residence_rows()` 新增 `occupants` 投影；前端改为每行最多两张可选住宅卡，先选中再确认入住，卡片显示入住者头像、姓名、球队与关系徽标，并保留迁出按钮。
- **回归**：`test_residence_rows_project_occupant_identity_and_relationship_badges` 校验人物摘要、球队、社交阶段与恋爱阶段；界面契约校验 `residenceOccupantsMarkup` 与双列网格。

### E61-04 赠礼与约会选项使用长下拉框，难以浏览

- **现象**：赠送礼物只能在一个很长的下拉列表中逐行查看；约会活动同样如此，选项多时需要反复滚动，选择与确认不在同一视觉层级。
- **根因**：旧实现使用原生 `<select>`，只能显示单行文本，无法承载图标、库存数量、价值、偏好和阶段门槛。
- **修复**：移除两个下拉框，新增赠礼与约会选择弹窗。礼物按同名库存聚合，约会卡显示图标、AP、偏好与朋友阶段状态；确认按钮在弹窗底部，只有确认才扣 AP 或库存。
- **回归**：界面契约检查两个弹窗容器、`data-interaction-gift-choice`、`data-interaction-date-choice`、`giftGroups()` 聚合逻辑与 `.interaction-choice-dialog` 样式。

### E61-05 约会活动为空时摘要可能出现无穷大

- **现象**：服务端返回空活动列表时，约会摘要可能显示 `Infinity` 或 `-Infinity`，或让按钮状态异常。
- **根因**：直接对空数组调用 `Math.min(...[])` 与 `Math.max(...[])`。
- **修复**：先计算 `dateCosts`，为空时最小值和最大值均返回 0；`dateReady` 仍要求活动列表非空。
- **回归**：`node --check src/web/interactions_page.js` 与界面契约测试通过；服务端活动目录仍为唯一真值。

## 第 60 轮（V2.8.9bBeta，2026-10-18）

### E60-01 聊天与互动页面右侧仍有大白边

- **现象**：切换到聊天等互动视图后，内容只占左侧一部分，右侧留下整块空白，窗口越宽越明显。
- **根因**：人物工作区的网格子项仍继承旧版内容宽度，内部详情容器没有 `width: 100%` 与 `min-width: 0`；网格的 `1fr` 轨道被内容最小宽度限制，无法铺满可用空间。
- **修复**：为人物详情、互动面板和相关滚动容器补齐全宽与 `min-width: 0`，把聊天、赠礼、约会改为三列自适应网格；窄屏按既有断点回退单列。
- **回归**：前端契约检查三列布局、全宽容器与 `min-width: 0`；`node --check src/web/interactions_page.js` 通过。

### E60-02 熟悉度已经 100 却不是朋友，关系升级条件不可见

- **现象**：玩家把熟悉度刷满后仍无法从初识升为朋友，不知道还缺好感或信任，也不知道每个阶段的具体门槛。
- **根因**：后端社交阶段需要同时满足多个维度，但页面只显示五维数值和按钮，没有投影下一阶段条件；玩家只能靠失败提示猜测。
- **修复**：新增 `relationship_progress()`，由服务端返回下一社交/恋爱阶段及每项 `current/required/met`；前端新增“关系进度”标签逐项展示。朋友门槛为熟悉 25、好感 30、信任 20，后续阶段同样完整显示。
- **回归**：`test_relationship_progress_explains_every_social_and_romance_gate` 覆盖全部社交与恋爱门槛；API 投影测试确认 `social_progress` 随人物返回。

### E60-03 删除联系人可能被误解为连永久赠礼一起收回

- **现象**：关系列表没有删除入口；若直接删除关系记录，玩家无法判断已经赠出的房产或车辆会怎样处理。
- **根因**：删除只应停止未来互动，但永久赠礼账本与关系、住宅、时间线存放在同一文档，缺少明确的删除语义和提示。
- **修复**：新增 `remove_person()` 与 `/api/life/interactions/remove`。删除人物、关系、住宅分配与该人物时间线，保留 `gifted_assets`；确认弹窗显示将保留的赠礼数量，服务端响应报告保留数与删除时间线条数。
- **回归**：`test_contact_removal_clears_cached_history_but_keeps_permanent_gifts` 校验缓存、关系与时间线清除且赠礼保留；API 删除测试 5 项通过。

### E60-04 所有互动操作平铺，危险操作与日常互动混在一起

- **现象**：聊天、赠礼、约会、关系推进、分手和离婚同时铺在一个页面，内容拥挤，容易误触，也让界面缺少层次。
- **根因**：旧版只有人物主标签和档案/互动子标签，互动页内部没有再分组；所有关系按钮由同一个动作区渲染。
- **修复**：人物页拆为人物档案、互动、名下资产；互动页拆为互动首页与关系进度。日常互动留在首页，关系推进进入进度页，分手和离婚收进“更多操作”折叠区。
- **回归**：`test_people_workspace_delete_progress_ledger_and_network_contract` 检查二级标签、进度路由与危险操作折叠；相关前端脚本语法检查通过。

### E60-05 行动力只有当前值，无法核对消耗与恢复

- **现象**：玩家看到行动点减少，却无法查看是哪次聊天、赠礼、约会或每周恢复造成的变化。
- **根因**：行动力状态只有 `current/maximum/weekly_recovery`，扣点函数直接改数值，没有流水数据结构。
- **修复**：schema 升至 5，新增 `action_point_ledger`；所有扣点、每周恢复与 CDK 加点统一记录金额、余额、原因、人物、日期与详情。行动力卡新增明细弹窗，展示最近 100 条和总条数。
- **回归**：`test_action_point_ledger_records_chat_recovery_cdk_and_cap` 覆盖聊天、恢复、CDK 与封顶；`test_schema_five_migration_preserves_existing_people_and_points` 校验旧档迁移不丢人物与点数。

### E60-06 礼物元数据契约测试把仓库根目录当成 `src/`

- **现象**：新增 8 类礼物后，物品元数据测试在数量断言之后继续读取 `I18N_ARCHITECTURE.md` 时报告文件不存在。
- **根因**：测试中的 `ROOT` 指向 `src/`，该行却使用 `ROOT / "docs"`，实际查找 `src/docs/I18N_ARCHITECTURE.md`；此前先被旧物品数量断言遮蔽，未能暴露。
- **修复**：把文档路径改为 `ROOT.parent / "docs"`，同时把物品元数据期望值由 81 更新为新增 16 个名称/描述键后的 97。
- **回归**：`test_i18n_locale_packs.py::test_shop_item_metadata_is_complete_in_every_locale` 通过；礼物 beta、i18n API/audit/frontend 合计 **44 passed**。

## 第 59 轮（V2.8.9aBeta，2026-10-18）

### E59-01 寻找球员结果只占一行，结果区下方大量空白且无法继续翻页

- **现象**：宽屏搜索只显示单列球员，单页最多 15 人；结果区下方还有整块空白，但玩家无法继续查看第 16 名之后的球员，只能修改条件重新搜索。
- **根因**：搜索请求固定 `page_size=15`，前端使用单列布局；结果列表高度受外层容器限制，分页状态虽然存在于 API，却没有给玩家可操作的分页入口，也没有把分页栏与内部滚动区分开。
- **修复**：桌面结果改为每行两位球员，单页固定 30 人；`searchPage/searchPageCount/searchPageSize` 保存服务端回填的分页状态，分页栏固定在结果滚动区外，翻页后滚回顶部，只有一页时隐藏分页栏。
- **回归**：`test_people_search_and_portrait_layout_contract` 校验 `searchPageSize: 30`、翻页事件与双列网格；`test_player_search_combines_club_nationality_gender_and_age_filters` 校验分页参数随筛选条件传给世界球员索引；`node --check src/web/interactions_page.js` 通过。

### E59-02 头像图片编号无法按头像包规则整体偏移

- **现象**：头像包中图片文件名与 FM 球员 UID 存在 `+1` 或 `-1` 的偏移时，读取始终按原 UID 查找；玩家只能手工重命名成千上万张图片。
- **根因**：`portrait_path()` 直接把 `player_id` 当作文件编号，没有独立设置键；设置页也没有偏移输入，缓存和头像请求无法感知编号映射的变化。
- **修复**：新增 `portrait_uid_offset`，按 `face_uid = player_uid + offset` 查找，默认 0，范围 `-999..999`；设置接口严格校验并清空头像缓存，头像 URL 支持显式的 `portrait_offset` 参数，前端展示 `+1/-1` 示例。
- **回归**：`test_portrait_path_applies_positive_and_negative_uid_offsets`、`test_portrait_uid_offset_persists_and_rejects_out_of_range_values` 与头像设置 UI 契约通过；直接请求仍使用 `no-store`，不会命中旧偏移图片。

### E59-03 纯权益 CDK 没有金额，被金额转换误判为无效

- **现象**：输入 `日理万机` 或 `魅力四射` 时，兑换请求可能返回 `InvalidMoney`，兑换码没有生效。
- **根因**：`resolve_cdk_code()` 对每条码都执行 `to_minor(entry.get("amount"))`。金额码有 `amount`，纯权益码只有 `effect`，缺失值进入金额解析后被拒绝。
- **修复**：缺失金额按 `0` 处理，仅在有正向金额时写银行余额和 `cdk_redeem` 流水；纯权益码要求 `effect` 属于已登记的 `CDK_PERK_EFFECTS`，否则仍返回 `cdk.invalid`。
- **回归**：`test_interaction_perk_codes_are_claimed_once_without_bank_credit` 校验 `amount=0`、无银行流水及第二次兑换报 `cdk.redeemed`；`test_every_built_in_code_has_a_positive_grant_or_interaction_effect` 覆盖码表完整性。

### E59-04 CDK 与永久权益分开写入，可能码已消耗但权益未到账

- **现象**：权益码兑换成功并标记已使用时，若人物互动文档保存失败，玩家会看到“码已兑换”但行动力或关系倍率没有生效；重试又会被 `cdk.redeemed` 拒绝。
- **根因**：初版把兑换记录和权益状态作为两次独立写入，账户文档与 `life_interactions` 文档之间没有共同事务边界；纯权益码也没有明确要求当前存档作用域。
- **修复**：`AccountApplicationService.redeem_cdk` 在权益码分支中使用 `update_documents()`，一次原子提交 `economy.cdk_redemptions` 与 `life_interactions.entitlements`；未连接存档直接拒绝。重复兑换只返回 `cdk.redeemed`，不再发放权益或写流水。
- **回归**：`test_interaction_perk_requires_a_connected_save_before_claiming` 校验未连接存档时不会进入事务；`test_interaction_perk_redemption_updates_both_documents_in_one_transaction` 校验同一次容器事务同时产生兑换记录与权益状态；`test_interaction_perk_codes_are_claimed_once_without_bank_credit` 校验重复兑换不再写流水。

### E59-05 关系倍率若作用于所有增量，分手/离婚惩罚也会被放大 10 倍

- **现象**：测试 `魅力四射` 时，聊天和约会等正向收益需要乘以 10，但分手、离婚等负向关系变化不应跟着放大。
- **根因**：倍率最初被放在动作基础增量或统一 `_apply_deltas()` 入口，若不做符号判断，负向惩罚会和正向收益一起翻倍。
- **修复**：抽出 `_scale_positive_deltas()` 与 `_relationship_gain_multiplier()`，只对 `delta > 0` 应用倍率；聊天、物品赠礼、约会、关系推进、资产赠礼和资产赠礼预览全部复用这一规则，正式提交重新计算而不是信任前端预览。
- **回归**：`test_relationship_perk_multiplies_positive_gain_but_not_penalties` 与 `test_chat_uses_the_relationship_perk_after_activation` 覆盖正向收益和负向惩罚；资产赠礼预览和正式提交共用服务端倍率的既有 API 流程测试通过。

### E59-06 单文件 EXE 的 FileVersion 被构建脚本重置为 `2.8.9.0`

- **现象**：桌面宿主和文档已同步为 `2.8.9.1`，但首次构建的单文件成品显示 `FileVersion 2.8.9.0`，只有 `ProductVersion` 为 `V2.8.9aBeta`。
- **根因**：`build_single_exe.py` 的 `write_version_file()` 只从产品名提取三段数字，并硬编码第四段 `.0`；它没有读取 `WebViewHost.csproj` 已声明的 `FileVersion 2.8.9.1`，导致主程序与宿主内部版本漂移。
- **修复**：新增 `binary_version_numbers()`，从 `src/desktop/WebViewHost.csproj` 的 `<FileVersion>` 读取完整四段版本；`filevers`、`prodvers` 和 `FileVersion` 字符串统一使用该结果，项目文件缺失时才回退到产品名加 `.0`。
- **回归**：`py_compile scripts/build_single_exe.py` 通过，函数返回 `(2, 8, 9, 1)`；重新打包后只读核对 `dist/FMSDD-V2.8.9aBeta.exe` 为 `FileVersion 2.8.9.1` / `ProductVersion V2.8.9aBeta`。

## 第 58 轮（V2.8.9Beta，2026-10-18）

### E58-01 头像包来源分散在其他分类，玩家不知道应选择哪个路径

- **现象**：“球员头像包”和“读取球员头像”不在同一分类，路径按钮附近只有短提示，玩家无法确认应选择 FM graphics 根目录、`config.xml` 还是直接放置图片。
- **根因**：头像显示开关由人物互动模块追加，头像来源卡由设置页单独创建；两者虽然读写同一套 `player_portraits` 设置，但视觉和分类上互不关联。
- **修复**：将来源卡与开关合并为一张卡片并移入“显示”分类；卡片显示当前来源、XML 数量、三步配置指引、常见文件路径与姓名缩写回退。设置弹窗改为 980px 双列，窄屏回退单列。
- **回归**：`test_people_search_and_portrait_layout_contract` 校验分类归属、合并容器、状态字段和配置步骤；深色主题样式同步补齐。

### E58-02 人物头像偏小，左侧关系栏挤压档案与互动区

- **现象**：人物关系列表、档案和搜索结果中的头像不够醒目，姓名/UID 字体与软件其他区域不一致；关系栏占用过宽，右侧操作区显得紧凑。
- **根因**：列表头像只有小号尺寸，档案沿用旧的单列宽度，姓名/UID 继承独立字体；人物工作区左侧列没有按内容密度重新收窄。
- **修复**：常规头像改为 90×90、列表 58×58、档案 92×92，姓名与 UID 统一 `font-family: inherit`；工作区改为 `minmax(236px, 272px) minmax(0, 1fr)`，把节省的宽度交给档案和互动工具。
- **回归**：静态布局契约检查头像尺寸、关系栏网格与统一字体；`node --check` 校验页面脚本。

### E58-03 寻找球员只能按完整姓名搜索，缺少组合筛选

- **现象**：输入单字或姓名片段不会得到结果，也无法按国籍、俱乐部、年龄过滤；玩家只能记住完整球员名后才能找到目标。
- **根因**：搜索页只提交单一 `query`，后端没有俱乐部筛选入口，前端也没有筛选状态与俱乐部候选区。
- **修复**：搜索页改为左侧结果、右侧筛选卡；支持姓名子串/单字、国籍、性别、成年年龄范围和俱乐部。后端新增组合过滤参数，并把年龄下限强制为 18 岁。
- **回归**：`test_player_search_combines_club_nationality_gender_and_age_filters` 校验全部参数与候选 UID；`test_player_search_never_allows_a_filter_below_adult_age` 校验过小年龄会被提升到成年门槛。

### E58-04 俱乐部筛选若逐个展开球员资料会过慢，中文别名交集还会导致空结果

- **现象**：初版俱乐部过滤需要为候选名单读取完整球员资料，几千人名单会造成明显等待；俱乐部候选名称与本地中文别名/规范化名称做二次交集时，可能出现俱乐部已找到但球员结果被全部过滤掉。
- **根因**：俱乐部过滤与既有世界球员索引职责重叠，候选集合被当成完整球员投影处理；名称过滤又混用了服务端规范化名与前端显示名。
- **修复**：新增 `read_native_world_club_player_ids()`，只读关联原生名单 UID，再以 `candidate_uids` 进入既有索引；俱乐部候选只负责选择 `club_id`，最终球员筛选统一由服务端规范化字段完成，不再用显示名做二次交集。
- **回归**：`test_player_search_combines_club_nationality_gender_and_age_filters` 校验 `candidate_uids` 与俱乐部名回传；新增 API 空名单用例校验零结果仍保留完整筛选状态。

### E58-05 空俱乐部和低于成年年龄的筛选回显不完整

- **现象**：俱乐部没有可读名单时，结果可能退化成无筛选全量搜索；输入低于 18 岁的年龄后，响应中的筛选值与前端输入可能不一致。
- **根因**：空候选只在主搜索分支之后处理，`interaction_filter` 没有统一的零结果投影；年龄下限仅由前端 `min=18` 提示，缺少服务端回显断言。
- **修复**：空名单在进入世界球员索引前直接返回结构化零结果，完整保留国籍、性别、年龄、俱乐部和分页字段；服务端用 `MIN_ADULT_AGE` 归一化上下限。
- **回归**：`test_player_search_never_allows_a_filter_below_adult_age` 同时校验 `filters.min_age` 与 `interaction_filter.min_age`。

### E58-06 俱乐部 UID 候选路径忽略姓名条件

- **现象**：输入姓名片段或单字并同时选择俱乐部后，只要球员 UID 属于该俱乐部，即使姓名不匹配也会出现在结果中；俱乐部筛选实际覆盖了姓名条件。
- **根因**：`search_players_by_uids()` 先构造俱乐部 UID 候选集，但随后只应用性别、国籍、年龄和能力等条件，`query` 仅用于响应回显，没有像普通搜索那样检查 `searchable_names` / `compact_searchable_names`。
- **修复**：在 UID 候选集上恢复与 `_filtered_person_search_rows()` 一致的姓名判断；非空查询同时支持规范化姓名和去分隔符紧凑姓名，空查询则跳过姓名条件，保留仅按俱乐部浏览。
- **回归**：新增 `test_person_search_by_uids_applies_name_filters_within_club_candidates`，覆盖多字姓名片段、单字中文、空查询与无匹配；`test_database_index.py` 共 36 条通过。

## 第 57 轮（V2.8.8cBeta，2026-10-18）

### E57-01 行动力卡只显示下周恢复，缺少满值时间与行动成本

- **现象**：行动力卡只显示“每周恢复 6 点”和“X 天后恢复”，玩家无法判断何时恢复至上限，也看不到聊天、赠礼、约会等行动的成本差异。
- **根因**：`action_points()` 只返回 `days_until_recovery`；前端没有总成本投影，也没有按恢复上限计算跨周次数。
- **修复**：新增 `next_recovery_gain`、`days_until_full`、`is_full` 与 `costs`；总览卡展示下次恢复、满值时间和五类行动消耗参考。
- **回归**：`test_action_points_report_recovery_forecast_and_cost_breakdown` 校验 5 点需两周回满、11 点一周回满与行动成本投影。

### E57-02 资产赠礼缺少结果预览，且 3 AP 成本与卡片文案分散

- **现象**：赠送前只能看到资产价值，无法知道大约增加多少好感、是否足以升级；资产赠送按钮固定显示 3 AP。
- **根因**：赠礼五维公式只存在于 `asset_gift_plan()` 的提交路径，`asset_gift_options()` 没有预览；成本常量也未统一投影到页面。
- **修复**：抽出纯预览函数，按当前人物计算封顶后的好感与社交阶段，并把 `action_cost` 随资产投影下发；成本改为 1 AP，允许预览与正式提交共享同一公式。
- **回归**：资产赠礼测试校验 1 AP、预览字段与 `asset_gift_previews`；API 流程测试保持通过。

### E57-03 资产页当前人物控件换行，资产卡两列过宽

- **现象**：资产赠送页的“当前人物”中文标签和下拉框在窄宽度下换行；资产卡每行两列，长名称与操作区占用大量纵向空间，金额仍按完整数字显示。
- **根因**：人物选择器继承通用 flex 但未禁止标签换行，工具栏上限 430px；资产网格固定两列，卡片使用普通文本金额。
- **修复**：标签使用不换行 flex 项，工具栏扩展至 680px；桌面宽屏改为四列，卡头、两行标题、预览和底部按钮重新布局，金额改用紧凑单位。
- **回归**：静态页面与样式契约检查通过；`node --check src/web/interactions_page.js` 通过。

### E57-04 头像设置只有开关，没有说明头像来源和路径

- **现象**：设置中的“读取球员头像”容易被理解为头像存储在存档或软件目录，玩家不知道应选择 graphics 根目录、XML 还是直接放置图片。
- **根因**：设置控件只有标题和简短提示，没有暴露 `player_portraits.py` 的实际读取规则。
- **修复**：在头像来源区增加本地化帮助，说明 FM26/FM24 默认 graphics 路径、XML 映射、`faces\face_<UID>.png` 与无图时姓名缩写回退；补充 11 种语言文案。
- **回归**：`test_action_and_asset_gift_copy_covers_every_locale_and_keeps_placeholders` 校验全部语言的键与占位符。

## 第 56 轮（V2.8.8bBeta，2026-10-18）

### E56-01 总览看不到核心属性，编辑按钮难以点击

- **现象**：玩家需要先打开档案弹窗才能看到颜值、能力、魅力与声望；总览的编辑按钮视觉与点击区域过小。
- **根因**：总览只渲染姓名、年龄、性别、身高和体重，编辑按钮沿用普通小号金色按钮，没有专属尺寸。
- **修复**：档案卡增加四项属性面板与可用点数摘要；编辑按钮改为至少 46px 高、148px 宽并带图标与文字。
- **回归**：`test_asset_names_follow_the_saved_locale_and_bilingual_ledger_fields` 校验属性面板、编辑按钮与最小高度样式。

### E56-02 档案弹窗右侧留出大白边，姓名无法拆分保存

- **现象**：档案编辑弹窗内容宽度远小于弹窗外壳，右侧显示空白；姓名只能作为一个字段编辑。
- **根因**：通用生活弹窗宽 1180px，档案 shell 被单独限制为 1000px，且表单没有统一 `width: 100%` / `min-width: 0`；档案模型只有单一 `name`。
- **修复**：档案弹窗改为 1120px 并让 shell/content/form 全宽铺满；保存 `surname` 与 `given_name`，显示名由两字段组合。旧 `name` 按中文复姓、普通中文姓名和西文姓名规则迁移。
- **回归**：新增姓名拆分与旧档迁移测试；前端契约校验两个独立输入与 `profileDisplayName()`。

### E56-03 档案重置收费与属性上限阻碍长期成长

- **现象**：完成档案后调整属性必须支付 50,000；四项属性上限 99，资产奖励点最终无可用之处。
- **根因**：第 55 轮把重置作为撤销旧点数的唯一路径，并用 99 同时限制输入与存储。
- **修复**：移除客户端确认、服务端扣款与退款；四项属性安全上限提升到 1,000,000,000，界面不设上限，但建档后仅允许增加。旧档身份差异通过 `identity_migration` 账本迁移。
- **回归**：`test_completed_attributes_have_no_upper_cap_and_cannot_decrease`、`test_legacy_identity_profile_migration_keeps_a_valid_budget` 通过。

### E56-04 年龄、身高、体重没有真实点数成本

- **现象**：玩家可免费填写 18 岁、200 cm、60 kg，与普通 30 岁档案消耗相同点数。
- **根因**：第 55 轮把这些字段定义为不参与预算的身份资料。
- **修复**：以 30 岁、180 cm、75 kg 为基准计算身份成本；年龄使用 `2.2 × gap^1.4`，身高每厘米 1.15 点，低于 75 kg 每千克 0.9 点。成本按当前目标值重算，调回基准会释放点数。
- **回归**：身份成本、年轻溢价、身高/体重成本和基准回调释放点数测试通过。

### E56-05 关系未加深却一次显示全部私密资料

- **现象**：初次认识即可看到全部性格、价值观、喜好、厌恶和精确三围，关系成长没有信息收益。
- **根因**：人物公开投影直接复制缓存的完整 `traits`，没有按社交/恋爱阶段裁剪。
- **修复**：服务端增加 0–3 级披露投影：性格 1/1/2/2 项，价值观 0/1/1/2 项，每组偏好 1/2/3/3 项，厌恶在 2 级后开放；女性三围按等级使用 ±3/±2/±1/0 cm。
- **回归**：`test_relationship_depth_controls_npc_trait_disclosure` 校验初识只下发部分资料、深知阶段下发完整资料和精确三围。

### E56-06 点击一个已选人物后无法切换到另一人物

- **现象**：关系列表已选中人物后，再点其他行不会改变档案。
- **根因**：列表行绑定旧的 `data-interaction-select`，而事件委托只识别新的统一人物选择属性。
- **修复**：关系列表与所有人物下拉统一使用 `data-interaction-person-select`，点击与 change 两条路径共用同一状态更新。
- **回归**：前端契约禁止旧属性并校验关系行与事件委托使用统一属性。

### E56-07 欧洲葡萄牙语词包缺少 82 个互动修订键

- **现象**：i18n 契约测试发现 `i18n.interactions.js` 的 `pt-PT` 比英文基准少 82 个键，关系档案、身份成本与披露文案会回退到英文。
- **根因**：`ptPT` 仅从 `ptBR` 复制基础词典，而后来追加的 `revisionCopy` 只补了 `pt-BR`，遗漏 `pt-PT`。
- **修复**：补齐 82 个欧洲葡萄牙语键，沿用当地拼写与称谓；契约测试收紧为“核心三语或完整十一语”，并对所有已声明语言逐键校验键集合与占位符。
- **回归**：i18n 三组测试 **27 passed**；`node --check src/web/i18n.interactions.js` 通过。

## 第 55 轮（V2.8.8aBeta，2026-10-18）

### E55-01 人物互动主界面信息密度过高

- **现象**：玩家档案、人物搜索、关系列表、聊天/赠礼/约会和资产操作堆在同一页面，玩家需要长距离滚动才能定位功能。
- **根因**：首版以快速交付为目标，所有面板只按单页纵向布局，没有主功能与子功能层级。
- **修复**：主界面拆为总览、人物、寻找球员、资产、时间线；人物再分档案/互动，资产再分住宅入住/资产赠送。切换标签保留当前选择与搜索条件，标签栏支持横向滚动。
- **回归**：`test_people_workspace_is_split_into_main_and_sub_tabs` 校验五组主标签和两组子标签契约。

### E55-02 玩家档案没有可分配预算，重置也没有账户结算

- **现象**：玩家可直接修改四项属性且没有总额限制；完成后任意调整都不会产生代价，资产奖励也没有长期记录。
- **根因**：旧档案只保存四个整数，没有基础点、奖励点、已用点或重置计划。
- **修复**：新档案按 200 基础点分配，四项各至少 1；奖励点写入永久账本。已用属性降低时服务端要求 `reset_confirmed`，先经账户账本扣 50,000，再保存档案；保存失败自动退款。旧档保留原分配并补足历史余额。
- **回归**：点数预算、旧档迁移与付费重置 API 流程通过，`test_life_interactions.py` 覆盖 196 点初始余额和旧档 200 点保留。

### E55-03 FM 身高体重未进入规范化人物缓存

- **现象**：搜索后即时缓存能看到身高体重，但重新加载或保存后的 `normalize_state()` 路径可能丢掉顶层的 `height_cm` / `weight_kg`。
- **根因**：增量缓存路径合并了顶层字段，规范化路径只读取内层 `traits`。
- **修复**：`_person_traits_source()` 统一把顶层身高体重并入 `traits`，`normalize_state()` 与 `cache_search_row()` 共用；新增回归直接对原始人物行执行规范化。
- **回归**：`test_normalize_state_preserves_top_level_fm_measurements` 校验顶层与 `traits` 四处读数一致。

### E55-04 所有球员只显示同一种回应

- **现象**：聊天结果对不同人物、话题和关系几乎总是同一句话，NPC 性格与价值观没有可见差异。
- **根因**：首版每种互动只有一个本地模板，服务端虽返回模板标识，但没有可供选择的多变体文案。
- **修复**：聊天、赠礼、约会成功/失败与关系成功/失败各提供 3 个变体，11 种界面语言占位符同构；变体由话题命中、性格、价值观、社交阶段、关系阶段和游戏日稳定生成。
- **回归**：`test_dialogue_variants_cover_every_locale_and_keep_placeholders` 检查所有语言均存在 3 个不同变体。

### E55-05 设置缺少球员头像读取开关

- **现象**：后端已有头像接口与前端文字回退，但玩家无法在设置中决定是否读取 FM 头像。
- **根因**：`interaction_portraits_enabled` 未挂载到设置页，状态签名与事件刷新也未包含该字段。
- **修复**：设置页新增 `#interaction-portraits`，默认开启；保存调用 `/api/settings/interaction-portraits`，成功/失败均有本地化提示，变更后派发设置事件刷新人物页。
- **回归**：`test_interaction_portrait_setting_round_trip_contract` 覆盖控件、API、状态签名和事件刷新。

### E55-06 住宅入住与赠礼资产名固定显示英文

- **现象**：界面切到中文后，住宅入住下拉与赠礼记录仍显示英文资产名。
- **根因**：资产选择只读 `name_en` / 新账本字段，未优先读取当前已保存的 `ui_locale`，旧账本也缺少双语字段。
- **修复**：`currentThemeLocale()` 优先读取桥接状态中的 `ui_locale`；住宅与赠礼分别读取 `name_zh/name_en`、`city_name_zh/city_name_en` 与 `asset_name_zh/asset_name_en`，旧记录回退原名称。
- **回归**：`test_asset_names_follow_the_saved_locale_and_bilingual_ledger_fields` 覆盖已保存语言和双语账本字段。

### E55-07 新增头像控件曾破坏既有设置测试切片

- **现象**：头像设置控件插入原有头像来源辅助函数之后，使旧测试切片意外包含一个新的 `<input>`，导致既有契约失败。
- **根因**：旧测试按函数边界截取 `ensurePortraitSourceControl()` 到更新检查控件之间的源码。
- **修复**：调整函数定义顺序，把 `ensureInteractionPortraitControl()` 放在既有头像来源函数之前，不修改或放宽旧测试。
- **回归**：设置、球员头像、i18n 与前端优化聚焦回归全部通过。

## 第 54 轮（V2.8.8Beta，2026-10-18）

### E54-01 对话模板只有标识，没有可见对白

- **现象**：初版互动动作只返回 `template: chat-warm/chat-calm`，页面仍以 toast 和时间线为主，玩家看不到具体对话。
- **根因**：模板标识没有和前端文案、交互展示建立契约；更早的实现也没有统一的结果弹窗。
- **修复**：`chat_plan`、`gift_plan`、`date_plan`、`relationship_plan` 统一返回 `dialogue` 描述；新增本地化模板文案和互动结果弹窗，展示对方回应、成功率和五维变化。模板仍为本地离线规则，不涉及 AI 请求。
- **回归**：`test_life_interactions_api.py` 断言聊天和赠礼结果含 `dialogue`；i18n 键集检查通过。

### E54-02 永久资产预览缺少不可收回标记

- **现象**：资产赠送预览返回了不可逆警告，但没有机器可读的 `permanent/recoverable` 字段，前端只能依赖文案判断。
- **根因**：`asset_gift_plan()` 与 `commit_asset_gift()` 的返回结构不一致。
- **修复**：预览计划也返回 `permanent: true`、`recoverable: false`；确认提交继续写入永久赠礼账本。模拟 API 流程验证车辆预览和确认均保持不可收回。
- **回归**：`test_item_gift_and_permanent_asset_gift_flow` 通过。

### E54-03 新互动页面可能回退英文

- **现象**：互动页新增约 20 个结果/对白键，如果只写入英文，其他界面语言会回退英文。
- **根因**：本地化目录按语言覆盖，缺失键时依赖英文回退，视觉上容易误以为切换失败。
- **修复**：为互动结果、模板对白在 11 种界面语言中补齐同一键集与占位符，并让语言合并顺序为“英文基线 → 互动模板 → 现有覆盖”。
- **回归**：`test_static_catalog_is_complete_and_isomorphic` 通过；新增键在 11 个 locale 中均存在。

### E54-04 首版误把职员纳入互动范围

- **现象**：需求确认后只保留球员互动，但早期范围描述仍提到职员。
- **根因**：需求从“球员和职员”收敛为“仅球员”后，功能边界与错误文案未同步。
- **修复**：缓存、搜索、API 过滤和错误映射统一只接受 `player` 对象；职员不会进入互动缓存，错误文案明确提示首版仅支持球员。
- **回归**：现有缓存/年龄测试与模拟 API 搜索链路通过。

### E54-05 约会按钮按 2 AP 固定判断，实际活动可能消耗 3–4 AP

- **现象**：行动力只剩 2 时仍可选择“共进晚餐”等 3 AP 活动，提交按钮保持可用，请求随后被后端以“行动力不足”拒绝。
- **根因**：活动下拉已经显示每项费用，但提交按钮的禁用判断和文案写死为 2 AP，没有随当前选择更新。
- **修复**：每个约会选项携带 `data-interaction-date-cost`，按钮标签与禁用状态由 `syncDateAction()` 按当前活动费用刷新；切换活动时即时更新，渲染后也会对新表单重新同步。
- **回归**：`node --check src/web/interactions_page.js` 通过；服务端原有行动力扣减测试继续通过。

### E54-06 关系按钮可用条件比后端阈值宽松

- **现象**：部分暧昧、情侣、秘密情人和求婚按钮在好感、吸引或信任尚未达到服务端门槛时仍可点击，点击后才收到拒绝提示。
- **根因**：`relationship_options()` 只检查阶段与排他性，没有复用 `relationship_plan()` 的数值前置条件。
- **修复**：四个关系推进选项分别补齐好感/吸引/信任门槛；秘密情人仍要求存在公开伴侣，求婚仍要求公开情侣且未标记秘密关系。
- **回归**：新增 `test_options_match_backend_relationship_thresholds`；生活互动聚焦测试 18 项通过。

## 第 53 轮（V2.8.7bBeta，2026-10-18）

### E53-01 收藏家金库抽取记录周期性闪烁、滚动跳动

- **现象**：打开收藏家金库的抽取记录后，界面每隔一段时间闪烁、抽搐，滚动位置被重置。
- **根因**：主壳层状态轮询触发 `FMSDDLife.render()`，`paint()` 无条件替换 `#life-gacha-content` 根节点，再重建仍在打开的历史弹窗；长列表与图片水合节点被反复销毁。
- **修复**：新增 `LIFE_DIALOG_IDS` 与 `anyLifeDialogOpen()`；图鉴、寄存车库、抽卡历史、卡池图鉴任一打开时，页面级 `paint()` 只更新余额/入口计数后立即返回。弹窗筛选、勾选、迁移等操作各自局部调用对应绘制函数。
- **回归**：契约测试覆盖四个弹窗 ID 与 `paint()` 提前返回；生活系统聚焦回归 73 passed。真实窗口长时间观察仍列入验收。

### E53-02 寄存车库等级徽标遮挡车辆图片

- **现象**：上一轮统一放大的等级徽标在寄存车库缩略图中过大，覆盖车头或车身。
- **根因**：寄存车库沿用了展厅/车库的 16px、38×30 徽标尺寸，但图片宽度仅 104px。
- **修复**：仅对 `.life-storage-photo .life-class-badge` 使用 13px、27×20、较小内边距和阴影；其他页面尺寸不变。
- **回归**：CSS 契约与全站最小 13px 字号约束通过。

### E53-03 寄存车库缺少按图鉴维度筛选的批量操作

- **现象**：车辆较多时只能按等级/稀有度粗略筛选，缺少厂商分类；搜索框和筛选下拉没有完整绑定，不能快速定位品牌或特别版车辆。
- **根因**：`state.storage` 只有查询、等级、稀有度，输入处理未覆盖寄存车库；全选仍直接使用全部寄存车辆。
- **修复**：新增厂商筛选、`special` 聚合稀有度、搜索事件与结果刷新；`storage-select-all`、迁移和出售统一从 `filteredStorageVehicles()` 取集合。
- **回归**：筛选状态、事件绑定与全选来源契约通过。

### E53-04 收藏家金库将 S2 传奇排除在出金之外

- **现象**：收藏家金库抽到 S2 传奇车辆不会获得金冠、不会重置保底，与新版期望不符。
- **根因**：`GOLD_RULES.collector.rarities` 仅包含 `forza edition`，`any_class_rarities` 仅包含 `donut edition`。
- **修复**：等级内集合改为 `("legendary", "forza edition")`；Donut 跨等级规则保持不变。公开条件、自然概率、保底、历史重算与前端徽标由同一入口自动同步。
- **回归**：S2 传奇正例、S1 传奇反例、任意等级 Donut 正例；收藏家自然出金率更新为 4.0847%；11 种界面语言的出金与概率说明同步通过键集与内容契约。

### E53-05 本次交付头部信息拥挤

- **现象**：抽取成功的标题、出金汇总、价值、成本、净收益和说明挤在一条底对齐布局中，十连结果显得混乱。
- **根因**：左右两块内容使用 `flex-end` 混合排列，指标卡宽度不一致，提示文本又占用右侧剩余空间。
- **修复**：头部改为两列网格；左侧放标题/金冠/说明，右侧放三张等宽指标卡；1100px 以下自动上下排列，520px 以下指标卡单列。
- **回归**：交付头部结构、CSS 网格和响应式断点契约通过。

### E53-06 收藏家金库记录页出现横贯弹窗的金色流光

- **现象**：打开收藏家金库抽取记录后，一条金色亮带从左向右扫过整个弹窗，周期性闪烁。
- **根因**：历史行使用 `.life-class-badge.is-inline`，该变体曾把 `position` 设为 `static`；S2 徽标的 `::after` 是绝对定位伪元素，失去徽标这个包含块后改以弹窗为参照，`overflow: hidden` 也无法裁切，最终形成横贯整页的金色扫光。
- **修复**：行内徽标改为 `position: relative` 并显式保留 `overflow: hidden`，让 S2 流光的包含块与裁剪区域始终是徽标自身；尺寸、居中方式和历史行布局不变。
- **回归**：CSS 契约断言行内徽标必须为相对定位；生活系统聚焦回归 73 passed。

## 第 52 轮（V2.8.7aBeta，2026-10-18）

### E52-01 首次抽卡仍需等待生活资料读取

- **现象**：上一轮虽已改为增量抽卡响应，但各卡池第一次抽取仍会长时间等待，玩家无法判断是预载、抽卡还是卡死。
- **根因**：预载只在少数状态轮询路径中尝试，且 `app.js` 先于 `life_page.js` 执行；连接完成、钱包就绪和模块加载的时序不保证命中。预载把 `/api/life` 成功但车辆目录失败也当成成功。
- **修复**：最终状态渲染后、钱包就绪、游戏日变化与 `DOMContentLoaded` 四处触发；用 `data_scope_id|game_date` 去重，失败后 30 秒冷却；只有生活文档与车辆目录都成功才提示“生活资料已就绪”。开始、完成、失败分别提示。
- **回归**：静态验证触发点、作用域签名和冷却；开启预载后首次打开生活页可直接复用已载入数据。真实存档首次抽取耗时仍需成品验收。

### E52-02 卡池缺少只展示本池车辆的图鉴

- **现象**：玩家只能进入全量收藏图鉴，无法确认某个卡池究竟能抽出哪些车辆，也不知道哪些车辆满足该池严格出金规则。
- **根因**：`gacha_tiers()` 只公开数量与概率，没有公开池内车辆 ID；前端只能使用完整展厅目录。
- **修复**：接口新增 `car_ids`；每个卡池标题右侧增加卡池图鉴按钮，打开只属于该池的二级档案，支持搜索、等级/稀有度筛选、收藏状态和可出金标记。
- **回归**：三池 ID 数量与唯一性、目录交集、按钮和弹窗结构、11 语言文案通过。

### E52-03 车辆等级标识不够醒目

- **现象**：D/C/B/A/S1/S2 徽标偏小，颜色区分有限，车辆卡片之间等级差异不直观。
- **根因**：等级信息仅由小型文字徽标表达，各页面没有统一尺寸与特效规则。
- **修复**：统一为 `vehicleClassBadge()`，最小字号 16px，六档独立配色，S2 增加可关闭的流光；应用范围覆盖展厅、车库、寄存车库、收藏、抽取结果和卡池图鉴。
- **回归**：六档 CSS 选择器、最小字号、S2 动画和组件调用数量通过。

### E52-04 缺少抽卡前确认开关

- **现象**：玩家希望连续抽取时跳过每次确认，但仍需要保留默认的安全确认行为。
- **根因**：确认弹窗此前始终显示，没有账户本地设置。
- **修复**：设置新增“每次抽卡前确认”，默认开启并持久化到 `fmsdd-gacha-confirm`；只控制确认弹窗，不改变服务端请求与校验。
- **回归**：默认值、设置渲染、变更持久化、桥接与抽卡分支通过。

### E52-05 本轮未实机验证（已知边界）

- **状态**：按仓库约定未启动 Football Manager、正式 EXE、Hook 或真实存档。
- **处理**：若首次抽卡仍有明显停顿，应记录游戏版本、存档规模、触发时间、预载提示是否出现、Network 中 `/api/life` 与 `/api/life/catalog` 的耗时、抽卡请求耗时和 WebView2 控制台错误。

## 第 51 轮（V2.8.7Beta，2026-10-18）

### E51-01 从车库或神秘车库打开的图鉴弹窗发灰且无法关闭

- **现象**：点击收藏图鉴后，图鉴窗口整体发灰、内容缺少正常配色，关闭按钮也无法使用；从车库与神秘车库进入均可复现。
- **根因**：全局 `#life-collection-dialog` 位于生活页面容器之外，但 CSS 主题变量只定义在 `.life-page`；同时点击委托只接受 `.life-page` 内的 `data-life-action`，关闭按钮虽在弹窗内却被过滤。
- **修复**：主题与暗色变量扩展到 `.life-collection-dialog`；点击委托接受 `.life-page, .life-collection-dialog`；为图鉴、寄存车库和历史弹窗统一注册关闭按钮、遮罩点击与 `cancel`（Esc）处理，打开图鉴前关闭同级弹窗。
- **回归**：断言弹窗关闭委托、遮罩与 `cancel` 事件、主题选择器和 11 语言键；实机 WebView2 视觉仍需成品验收。

### E51-02 每次抽卡都显示“正在读取生活资产…”且首次抽取等待很久

- **现象**：神秘车库抽取时长时间显示生活资产加载提示，首次抽车尤其明显，容易误判为卡死。
- **根因**：抽卡接口复用完整 `public_view()` 响应，重复返回全部房产、车辆目录、历史与未抽取卡池；前端重新解析并重绘整页。抽取按钮还复用 `life.loading` 文案；车辆图片预热与抽卡同时争用本地服务。
- **修复**：新增 `gacha_patch()`，仅返回新增车辆、价值、车库/寄存、图鉴与卡池统计；接口改用 `life_patch`，前端 `mergeGachaLifePatch()` 原位合并。`public_view()` 移除未使用的 `state` 深拷贝；图片预热 4 → 2 路并在 `state.busy` 时暂停；抽取按钮改用独立 `life.gacha.drawing`。
- **回归**：断言增量响应不含完整 `life` / `state` / `vehicles`，新增车辆、图鉴、卡池计数与总价值正确；抽卡路由分派测试通过。

### E51-03 收藏家金库的 S1 Donut 车辆抽出后不显示金冠、不重置保底

- **现象**：Ford Supervan 3 “Donut Media Edition” 基础概率为 `0.5%`，但抽出后不算出金，金冠与出金统计均不出现。
- **根因**：旧规则要求收藏家同时满足 `S2` 与 `Forza/Donut` 稀有度；卡池中唯一 Donut 车辆实际为 `S1`，因此永远无法满足等级条件。
- **修复**：`GOLD_RULES.collector` 改为 `S2 + Forza Edition` 或任意等级 `+ Donut Edition`；`_gacha_gold_hit()` 统一用于自然抽取、软保底、硬保底、历史重算与前端徽标；接口公开 `gold_rules`，前端显示 OR 条件。
- **回归**：覆盖 `S1/A + Donut` 为正例、`S1 + Forza` 为反例、三池硬保底统一判定；新自然出金率为 `0.6657% / 0.3620% / 0.6617%`，长期期望为 `2.0244% / 1.8568% / 1.6218%`。

### E51-04 本轮未实机验证（已知边界）

- **状态**：按仓库约定未启动 Football Manager、正式 EXE、Hook 或真实存档；WebView2 中的图鉴关闭交互、首次抽卡等待和 Donut 金冠展示仍需成品验收。
- **处理**：若仍有问题，应记录入口、主题、窗口缩放、抽取卡池、抽取前后保底、返回体是否包含 `life_patch` 及浏览器控制台错误。

## 第 50 轮（V2.8.6Beta，2026-10-18）

### E50-01 自然出金率偏低，实测长期依赖保底

- **现象**：玩家反馈约一千抽中大多数结果靠近保底，自然抽出精确金的机会太少，缺少持续抽车的正反馈。
- **根因**：三池自然权重完全由车辆池直接形成，没有额外的精确出金权重校准；街头/性能/收藏家的基础出金率仅为 `0.4273% / 0.2018% / 0.1140%`。
- **修复**：为三池增加 `gold_weight_multiplier`，并用 `_gacha_cell_scales()` 在“等级 × 稀有度”网格上做迭代比例校准，把新增权重集中到精确出金组合；公开等级和稀有度边际概率保持不变。
- **回归**：基础出金率提升到 `0.6657% / 0.3620% / 0.1617%`，含保底长期期望提升到 `2.0244% / 1.8568% / 1.3356%`；既有等级、稀有度概率契约继续通过。

### E50-02 图鉴原为账户级，跨存档共享且无法对应单个存档

- **现象**：不同存档共用同一份车辆图鉴，出售车辆后账户图鉴仍保留；玩家要求图鉴随存档保存。
- **根因**：`record_collection()` / `collection_view()` 读写数据根下的 `life_collection.json`，生活文档本身却按存档作用域保存，两者边界不一致。
- **修复**：生活 `SCHEMA_VERSION` 升至 9，图鉴写入存档文档 `state.collection`；删除 `COLLECTION_PATH` 读取路径；缺少图鉴的旧存档按已有车辆一次性重建。旧账户文件不删除、不读取，也不自动合并到当前存档。
- **回归**：两个独立生活状态分别记录图鉴后互不影响；旧存档 `vehicles` 可重建图鉴车型、数量与最后获得日；车库、抽卡与出售路径均继续使用同一存档视图。

### E50-03 交付“重复”按账户历史累计次数而不是当前车库

- **现象**：车库中实际没有同车型时仍可能显示“重复 ×N”，或当前车库已有车辆却不显示，因为旧逻辑读取的是账户图鉴历史总数。
- **根因**：`gachaResultCard()` 读取 `state.data.collection.cars[].count`，而该计数包含过去多次抽取与出售前记录，不代表抽取前车库库存。
- **修复**：`gacha_plan()` 按 `garage_catalog_counts` 写入 `garage_copies_before` 与 `garage_duplicate`，每生成一辆车后递增同车型计数；前端只展示这两个服务端字段。
- **回归**：空车库首抽不标记重复；把同车型放入车库后重抽，标记为重复且抽前数量为 1；同一十连的后续同车型按顺序正确累计。

### E50-04 神秘车库缺少图鉴入口、概率标题重复说明且交付信息与布局不完整

- **现象**：图鉴只能在车库打开；卡池“公开基础概率”右侧重复显示等级/稀有度；本次交付只有总价值，没有与成本对比；交付车库、容量、寄存车库和入口卡片高度不一致。
- **根因**：图鉴弹窗只在车库页内使用；概率标题同时渲染 `odds_title` 与 `odds_base_note`；交付数据未消费 `draw.cost`；旧工具栏是不同内容密度的 flex 区块，没有统一卡片高度。
- **修复**：图鉴弹窗移到全局并新增神秘车库入口；移除非必要标题说明；交付显示总价值、成本、净收益与 ROI；工具栏改为同一行等高卡片网格，窄屏按断点折叠。
- **回归**：全局弹窗只出现一次并位于支持弹窗之后；神秘车库入口存在；移除 `odds_base_note` 调用；交付成本来自 `state.lastGacha.draw.cost`；11 种语言与新增样式契约通过。

### E50-05 生活首页解包名与引用名不一致（发布前回归）

- **现象/风险**：`public_life()` 将 `_life_context()` 第四项解包为 `_manager_id`，随后仍引用 `manager_id`，请求生活会触发未定义变量错误。
- **根因**：清理未使用变量时误改了仍被 `_life_view()` 使用的解包名。
- **修复**：恢复为 `manager_id`，并新增聚焦测试断言 `public_life()` 将当前经理 ID 传入视图。
- **回归**：`test_public_life_passes_the_selected_manager_to_the_view` 通过，完整生活系统回归 `69 passed`。

### E50-06 本轮未实机验证（已知边界）

- **状态**：按仓库约定未启动 Football Manager、正式 EXE 或真实存档；新工具栏、净收益配色、图鉴入口与十一语言文案在 WebView2 不同缩放和窄窗口下的最终视觉仍需成品验收。
- **处理**：发布说明保留该边界；若图鉴或重复标记异常，应记录存档作用域、升级前图鉴文件是否存在、车辆当前车库、抽取卡池、抽取前后 `garage_copies_before` 与交付截图。

## 第 49 轮（V2.8.6Beta，2026-10-18）

### E49-01 最高等级被单独误判为出金

- **现象**：街头发现抽到任意 A 级车都会显示“最高等级”并重置保底，即使稀有度只是普通或稀有；性能寻猎的 S1、收藏家金库的 S2 也存在同样问题。
- **根因**：旧实现把“最高等级”直接等同于“出金”，历史行只有单个 `top_hit`，软保底和硬保底也只按等级筛选。
- **修复**：新增三池精确规则：街头 `A + 史诗`、性能 `S1 + 传奇`、收藏家 `S2 + Forza/Donut`。自然抽取、软保底权重、硬保底候选池和历史重新判定统一调用 `_gacha_gold_hit()`，同时保留旧字段兼容但写入精确 `gold_hit`。
- **回归**：覆盖 `A + 稀有`、`S1 + 史诗`、`S2 + 传奇`、`S1 + Forza` 等反例，以及 `A + 史诗`、`S1 + 传奇`、`S2 + Forza/Donut` 正例；三池硬保底均断言等级与稀有度同时命中。

### E49-02 卡池历史缺少累计花费、出金次数与车辆总价值

- **现象**：玩家只能逐条查看抽取结果，无法知道某个卡池累计花了多少钱、出金几次、抽出的车辆总估值是多少。
- **根因**：旧历史只保存抽取结果、保底前后值和单次交付汇总，没有在同一次已扣款的计划中分摊花费或累计车辆估值。
- **修复**：`gacha_plan()` 为每条记录写入 `cost` 与 `value`，`commit_gacha()` 只在扣款成功后累计 `spent/gold_count/total_value`；`public_view()` 投影 `stats`，历史弹窗与卡池卡片展示统计，旧历史仍完整可见并重新计算精确出金。
- **回归**：两次街头十连累计花费断言为 `800 万`；累计出金、车辆总价值与计划及逐条历史之和一致；旧历史缺少费用字段时不伪造金额，并显示统计起算抽数。

### E49-03 以裸基础率计算欧气会让保底玩家普遍成为欧皇

- **现象/风险**：精确出金的基础概率很低，而硬保底最多 60/80 抽必出；若直接用“实测出金率 ÷ 基础出金率”评级，几乎所有持续抽取的玩家都会得到最高欧皇等级。
- **根因**：旧版没有欧气算法；新增统计时若只使用单抽独立基础概率，会忽略软保底和硬保底对长期分布的显著抬升。
- **修复**：按每个保底状态的真实权重计算完整出金周期，返回 `expected_gold_rate` 与 `expected_pulls_per_gold`；欧气指数用 120 抽先验对实测值平滑后与该含保底期望比较，并设置 20 抽最低样本门槛与七档区间。
- **回归**：三池期望周期分别断言约为 `52.9 / 56.5 / 76.3` 抽；构造样本验证欧皇三阶、平稳、非酋三阶与样本积累中均可到达。

### E49-04 本轮未实机验证（已知边界）

- **状态**：按仓库约定未启动 Football Manager、正式 EXE 或真实存档；历史弹窗和七档刻度在 WebView2 实际缩放、窄窗口及长期大数据量下的视觉效果未验收。
- **处理**：发布说明保留该边界；若出现统计或显示异常，应记录卡池、升级前总抽数、升级后统计抽数、累计花费、出金次数、车辆总价值和历史弹窗截图。

## 第 48 轮（V2.8.6Beta，2026-10-18）

### E48-01 性能寻猎最高等级概率倒挂

- **现象**：性能寻猎的 S1 是最高等级，但基础概率为第二高，玩家抽到顶级的频率与等级定位不符。
- **根因**：旧权重按车辆池数量直接配置，未对最高等级设置足够强的边际收缩；加入 C 级后，原有权重也不能继续表达新的等级梯度。
- **修复**：性能寻猎加入 C 级并重新校准权重，基础等级概率变为 C `24%`、B `38%`、A `33%`、S1 `5%`，S1 成为最低概率等级；传奇基础概率同步降至 `2.5%`。
- **回归**：`test_collector_gacha_publishes_probabilities_and_curbs_top_tier_results` 断言性能池等级集合、四项基础概率、S1 为最低概率及传奇 `2.5%`。

### E48-02 Donut 特别版比 Forza 特别版更稀有

- **现象**：收藏家金库中 Donut 特别版的提示概率低于 Forza 特别版，与两种特别版的定位和本轮目标相反。
- **根因**：旧概率权重直接来自历史配置，未按特别版概率重新归一化；修改传奇概率后，旧比例也不能继续使用。
- **修复**：收藏家金库稀有度权重重新校准为普通稀有 `12%`、史诗 `82.25%`、传奇 `5%`、Forza `0.25%`、Donut `0.5%`；等级概率为 A `60%`、S1 `32%`、S2 `8%`。
- **回归**：同一聚焦测试断言 Forza 与 Donut 的绝对概率及 Donut 高于 Forza 的相对关系，并验证等级、稀有度概率和均为 1。

### E48-03 本次交付缺少车辆价值总值

- **现象**：十连抽取后只展示逐车结果，玩家无法直接看到本次交付的车辆总价值。
- **根因**：`gacha_plan()` 只保存单车记录，`/api/life/gacha/draw` 未返回汇总值，前端也没有独立展示字段。
- **修复**：每辆抽取车辆写入抽取日的 `vehicle_market_value()`，`gacha_plan()` 汇总 `total_value`，API 原样返回，前端在本次交付标题区显示；旧响应缺少字段时按每辆车估值回退求和。
- **回归**：校验 `total_value` 等于记录 `value` 之和、每辆车估值大于零，并覆盖 API、前端类和 11 语言文案契约。

### E48-04 本轮未实机验证（已知边界）

- **状态**：按仓库约定未启动 Football Manager、正式 EXE 或真实存档；概率面板、十连总价值和长期抽取分布未在真实用户环境验收。
- **处理**：发布说明保留该边界；若概率显示异常，应记录卡池、游戏版本、抽取次数、基础概率面板、本次交付总值与抽取记录。

## 第 47 轮（V2.8.6Beta，2026-10-18）

### E47-01 汽车展厅车辆图片空白

- **现象**：车库、抽卡等其他生活页面能显示车辆图片，汽车展厅的车辆卡片却无图。
- **根因**：车行列表在初次渲染、分页和搜索后只生成 `<img>`，没有调用统一的车辆图片水合函数；延迟加载观察器没有被绑定到新生成的卡片。
- **修复**：`paintDealerResults()` 在替换卡片 HTML 后统一调用 `scheduleVehicleImageHydration(host)`，与车库和抽卡结果共用同一套缓存/加载流程。
- **回归**：前端契约检查覆盖车行渲染后的水合调用，以及分页、搜索重建 DOM 后的再次水合；真实 WebView2 图片显示仍需成品验收。

### E47-02 抽卡历史只保留少量记录，最高等级命中不透明

- **现象**：卡池只保留固定数量记录，玩家无法回看完整抽取过程；抽中最高等级并重置保底时没有醒目标记，本次交付也无法汇总金色结果。
- **根因**：`commit_gacha()` 将历史裁剪为 40 条；历史行只保存结果与保底前后值，没有显式 `top_hit`/`guaranteed` 语义，前端只能靠推断。
- **修复**：移除历史截断，后续记录全部追加；历史行写入 `top_class`、`top_hit`、`guaranteed`、`pity_before/after`，卡池弹窗、本次交付和完成提示增加皇冠与最高等级汇总，并区分自然命中与保底命中。
- **回归**：超过 40 次抽取后历史长度保持完整；最高等级自然命中、保底命中与普通结果分别断言；11 种语言文案完整性纳入回归。
- **不可逆边界**：旧存档此前已经被截断的历史无法恢复，本轮只阻止未来再次丢失。

### E47-03 寄存车库缺失持续租金

- **现象**：寄存车库提供 100 个免费车位，车辆寄存后不产生任何持有成本。
- **根因**：寄存车库只实现了容量和批量移动/出售，没有独立租金账本字段、逐日计价或幂等结算。
- **修复**：新增 `storage_entered_day`、`storage_rent_settled_day`、`storage_rent_lifetime`、`storage_rent_history`；按每个游戏日寄存车辆市值的 1% 累计，通过银行/钱包统一账本结算。旧存档首次迁移从当前日开始，不追溯收费。
- **回归**：覆盖单日/多日金额、寄存当天不计租、旧存档迁移、成功记账、保存失败退款与状态投影。

### E47-04 生活状态并发路径可能重复结算租金（预防性修复）

- **现象/风险**：生活页请求外层已有生活锁，但城市包读取路径直接进入 `_life_state()`；若多个请求同时跨日，可能重复读取同一未结算日期并重复扣租。
- **根因**：互斥只存在于部分调用方，没有下沉到共享的状态加载/结算入口。
- **修复**：`_life_state()` 内使用 `life_system.life_lock()`（RLock，可重入），所有读取路径共享同一结算边界。
- **回归**：既有生活系统与 HTTP 路由测试全部通过；租金提交与退款路径由聚焦测试覆盖。

### E47-05 本轮未实机验证（已知边界）

- **状态**：按仓库约定未启动 Football Manager、正式 EXE 或真实存档；车行图片、抽卡皇冠标记、寄存租金跨日和 WebView2 布局未在真实用户环境验收。
- **处理**：发布说明保留该边界；若租金日期异常，应记录游戏日期、存档作用域、车辆寄存日、结算日、账本交易 ID 与 `storage_rent_history` 末条记录。

## 第 46 轮（V2.8.6Beta，2026-10-18）

### E46-01 车辆图片每次启动都重新请求本地服务

- **现象**：车库、展厅和抽卡图片虽然在本地，但每次打开应用仍逐张请求，图片区域需要等待；大量图片同时出现时更明显。
- **根因**：旧前端直接使用 `<img src>`，服务端静态资源统一发送 `no-store`；没有应用级图片缓存，而且端口回退可能改变 WebView 的 origin，使浏览器缓存无法复用。
- **修复**：改用 Cache Storage 保存车辆 WebP，并与普通图片一起使用受控并发、视口延迟加载和空闲预热；车辆图片响应改为一年期不可变缓存；桌面服务优先尝试固定端口并记忆上次成功端口。
- **回归**：`test_vehicle_images_send_a_long_lived_shared_cache_header` 校验缓存头；前端契约测试检查 `caches.open`、延迟加载、后台预热与统一图片标签。

### E46-02 既有存档可能缺少寄存车库

- **现象**：新增 100 车位寄存车库后，新存档能看到入口，但旧存档若 schema 版本已经是最新值，规范化状态不会产生保存标记，车库入口可能长期为空。
- **根因**：`ensure_state()` 只用 schema 版本差异判断是否需要回写，没有同时检查 `garages.storage` 是否存在。
- **修复**：生活系统 schema 从 6 升至 7，并在 `ensure_state()` 显式检查 `storage`；任一条件成立都会保存补齐后的状态。
- **回归**：`test_ensure_state_persists_storage_garage_for_existing_saves` 用同版本但缺少 storage 的存档验证 `changed=True` 且自动补出 100 车位。

### E46-03 寄存车库勾选车辆后滚动位置跳回顶部

- **现象**：寄存车库车辆较多时，向下滚动并勾选一辆车，列表会重新渲染并跳回顶部，批量选择很难操作。
- **根因**：每次复选框变化都调用 `paintStorageDialog()` 整体替换 `innerHTML`，没有保存 `scrollTop`。
- **修复**：重绘前记录内容容器滚动位置，重建列表后恢复；批量选择状态与目标车库仍即时更新。
- **回归**：生活系统前端契约检查保留滚动位置恢复代码；最终滚动体验仍需成品实机验收。

### E46-04 抽卡记录入口计数少于弹窗内容

- **现象**：卡片右上角历史按钮只按最近 5 条计数，但弹窗实际展示完整保留记录，按钮数量与内容不一致。
- **根因**：渲染按钮时复用了旧的 `slice(-5)` 常驻列表变量。
- **修复**：按钮改用 `historyCount = (tier.history || []).length`，弹窗继续展示完整记录；移除卡片下方旧常驻记录布局及废弃样式。
- **回归**：前端契约测试检查完整记录计数变量与旧样式已删除。

### E46-05 本轮未实机验证（已知边界）

- **状态**：按仓库约定未启动 Football Manager、正式 EXE 或真实存档；缓存命中率、首次预热耗时和 WebView2 配额未在真实用户环境测量。
- **处理**：发布说明保留该边界；若仍出现重复慢加载，应记录启动次数、端口日志、WebView2 用户数据目录是否可写、缓存配额和 DevTools 网络面板结果。

## 第 45 轮（V2.8.6Beta，2026-10-18）

### E45-01 账户收藏图鉴长期挤占车库首页

- **现象**：车库页顶部常驻一整块账户收藏摘要和横向车辆条，既占用主要操作空间，也让车库本身的目录、车位和车辆列表显得松散。
- **根因**：图鉴信息被直接嵌入 `renderGaragePage()`，没有独立入口和详情层；横向卡片只能显示名称，无法承载厂商、稀有度、等级和全目录筛选。
- **修复**：移除车库常驻收藏条，在标题右侧新增按钮与原生 `<dialog>`；弹窗提供总览、全部车型、厂商、传奇与特别版四标签，搜索与四类筛选，未收集车辆灰阶锁定。收藏仍按账户跨存档共享，车库车辆仍按存档保留。
- **回归**：`test_garage_collection_moves_into_a_full_dialog_with_all_locales` 检查按钮、弹窗、目录加载、标签、CSS 与 11 语言键；生活系统聚焦回归通过。

### E45-02 旧目录价导致传奇车与低等级老车价格失真

- **现象**：不少传奇级车型只需几万或几十万即可购买，价格主要由旧目录原始价决定，稀有度和车辆等级没有形成稳定层级。
- **根因**：展厅价格直接使用抓取价格，未对稀有度设最低价，也未控制同一等级内普通/稀有/史诗/传奇的倍率关系。
- **修复**：生成 `source_price` 并建立 `rarity-class-v2`：稀有度倍率与最低价先决定档位，旧价格只在同稀有度同等级内排序；传奇最低 500 万，Forza/Donut 特别版最低 1500 万。
- **回归**：`test_vehicle_pricing_puts_rarity_first_and_locks_legendary_showroom_cars` 校验同等级 median 价格随 common→rare→epic→legendary 单调增加、特别版 floors 与 106 辆展陈目录。

### E45-03 展厅所有车辆均可购买，展陈限制只停留在视觉层

- **现象**：传奇与特别版虽然应作为展厅陈列，但前端或直接 API 调用仍可发起购买。
- **根因**：目录没有 `dealer_status` 字段，购买计划只校验车库空间与余额，没有领域级可售状态。
- **修复**：为传奇、Forza、Donut 统一写入 `display_only`；展厅显示展陈徽标和禁用按钮，购买计划在任何扣款前抛出拒绝错误，HTTP 入口复用该计划。
- **回归**：`test_vehicle_dealer_rejects_a_display_only_catalog_model` 直接以展陈车辆调用购买计划并确认拒绝；前端契约检查 `dealer_status` 分支。

### E45-04 收藏家金库十连 S1 过高且概率不可见

- **现象**：十连收藏家金库很容易出现 S1 车辆，玩家无法判断各等级与稀有度的基础概率，价格与产出预期也不一致。
- **根因**：旧卡池按展厅价格分段，阶级权重和稀有度权重没有显式公开；收藏家池 S1 权重过高，且软保底只存在于抽取算法中。
- **修复**：按等级/稀有度重建三档权重，收藏家 S1 基础概率降至约 14.01%、S2 约 0.83%；加入明确软保底与主等级保底；前端公开基础概率、软保底起始、增幅、封顶和保底次数。单抽/十连价格同步调整。
- **回归**：`test_collector_gacha_publishes_probabilities_and_curbs_top_tier_results` 校验三档价格、概率和为 1、S1/S2/Forza/Donut 上限和透明字段；`test_frontend_font_sizes.py` 保证概率面板字号不低于 13px。

### E45-05 本轮未实机验证（已知边界）

- **状态**：未启动 Football Manager、正式 EXE 或真实存档；新图鉴弹窗的滚动、系统缩放、触控操作和深浅主题观感只经过静态契约与 CSS 检查。
- **处理**：发布说明保留该边界；若成品出现卡片裁切或滚动异常，应记录窗口尺寸、缩放比例、主题、语言与截图，优先检查 `.life-collection-dialog`、`.life-catalog-grid` 和 `.life-collection-dialog-content` 的覆盖规则。

## 第 44 轮（V2.8.5Beta，2026-10-18）

### E44-01 公告“置顶”仅显示标签，未保证实际排序

- **现象**：公告板把「关于本版本的说明，以及关于下注功能的重要提醒」标为置顶，但后续新增公告插在数组前方时，这条公告会下移；置顶看起来只是一个视觉标志，而不是稳定规则。
- **根因**：公告板直接按 `ANNOUNCEMENT_BOARD` 数组顺序渲染，`pinned` 只控制卡片样式和标签，没有参与排序；日期也没有成为排序依据，因此“置顶”与“排在顶部”是两套互不保证的语义。
- **修复**：用 `ANNOUNCEMENT_PERMANENT_TOP_KEY` 识别永久公告，并通过 `announcementDisplayEntries()` 执行“永久公告 → 其他置顶 → 普通公告”的三段稳定排序；同一段内保留原数组顺序。未读检测仍读取原始数组第一条，保持新公告红点行为不变。
- **回归**：`test_permanent_notice_precedes_every_other_pin` 模拟未来版本置顶公告并验证顺序；公告、首页、壳层、i18n、字号与页面层级聚焦测试合计 **88 passed**。
- **边界**：未启动 Football Manager 或正式 EXE，最终公告板视觉与滚动表现仍以成品实机验收为准。

## 第 41 轮（V2.8.4Beta，2026-10-18）

### E41-01 水域密集城市仍生成水面/海岸地块

- **现象**：泉州已基本正常，但香港、澳门、深圳、杭州仍出现大量地块落在水面、海面或海岸线外侧。
- **根因**：地形提取只处理 OSM 的 way 级闭合多边形，遗漏了 `relation` 多面（尤其是大型水域和海岸线），也没有处理内环陆地孔洞；沿海城市仅靠湖泊/河流 way 无法覆盖海面，导致候选点落在无地形的“空白水域”。
- **修复**：构建器支持 relation multipolygon、内环孔洞与 coastline Shapefile，按城市 bbox 裁剪海岸水体；重建 27 城地形掩码与城市包 2.3。地块候选点严格按中心 + 地块半径避让水面/绿地，找不到合法点则跳过，不回退到非法坐标。
- **回归**：27 城 2,653 块逐块校验，非法 0、跳过 0；`test_city_profile_exclusions_and_industrial_distribution_are_respected` 与 `test_terrain_multipart_polygon_treats_inner_holes_as_land` 通过。

### E41-02 旧资产迁移只校验中心点，边界仍可能压水

- **现象**：旧存档中部分资产原地块 ID 已不存在，但迁移判断只看坐标中心；面积较大的地块中心在岸上、边界跨入水面时仍被判定合法。
- **根因**：`_property_coordinate_is_legal()` 传入 `parcel_radius_m=0.0`，与生成地块时使用的 `max(8, sqrt(area)×0.5)` 半径不一致。
- **修复**：迁移判断按资产 `area_sqm` 推导同一半径，再走 `_excluded_distance_m()`；新增半径回归测试，确保中心合法但边界压水时会触发搬迁。
- **回归**：`test_life_system.py` 41 passed，含 `test_owned_property_legality_includes_the_parcel_radius`。

### E41-03 高德海外瓦片返回“成功”的空占位图，前端无法回退

- **现象**：伦敦、巴黎、柏林等海外城市底图为空白；控制台没有明显的 HTTP 错误，自动回退 OSM 不触发。
- **根因**：高德海外道路瓦片返回 HTTP 200 和约 179 字节的空白占位图，浏览器图片 `load` 事件仍会触发，原失败检测只看 `error`。
- **修复**：底图自动模式改为中国高德、海外 Bing；手动保留高德/Bing/OSM；主提供方加载失败时对当前视图临时回退 OSM，不写入新偏好；缓存键升级避免旧瓦片状态污染。Petal Maps 未发现公开 XYZ 端点，不接入。
- **回归**：`node --check` 通过；Bing 深圳 z18 预览对齐正常；11 语言 Bing/回退/署名文案通过前端契约测试。

### E41-04 商业/工业资产卡片信息与操作混杂

- **现象**：经营业态、员工、升级、出租、收租和出售按钮挤在同一区域，宽屏留白大但控件松散，窄屏又容易换行错位。
- **根因**：卡片只用一套通用网格，没有区分配置字段、收益摘要、契约信息和不同风险级别操作。
- **修复**：`life_page.js` 输出独立 config header/fields/submit 与 action/deed 分组；`life.css` 在宽屏使用三列紧凑布局，日收益独占整行，窄屏回落单列。
- **回归**：`test_frontend_font_sizes.py` 通过，所有用户可见字号仍 ≥13px；预览图 `build/card_preview2.png` 已人工检查。

### E41-05 本轮未实机验证（已知边界）

- **状态**：未启动 Football Manager、正式 EXE 或真实存档；水域生成与旧资产迁移只通过领域测试和静态数据校验，最终地图视觉需要实机验收。
- **处理**：发布时说明已知边界；若仍出现水面地块，应记录城市 ID、地块 ID、坐标、面积、地形包版本与截图，便于定位具体 OSM 关系或缓存旧包。

## 第 40 轮（V2.8.4Beta，2026-10-17）

### E40-01 资产升级、装修与经营业态瞬时生效，缺少施工期和严格确认

- **现象**：升级地块或选择商业/工业业态后立即生效，没有建设时间；切换业态、调整雇员等操作缺少明确的费用与后果确认，玩家很容易误操作。
- **根因**：旧实现把升级、业态配置和雇员调整都当作即时写值，收益段也直接按新状态继续累计；没有 `construction` 状态，也没有「工程进行中」的互斥校验。
- **修复**：升级和经营筹备改为付费施工：提交时扣款并写入 `construction`（目标等级/业态、起止日、费用、目标雇员），完成日之前资产收益为 0，且不能出售、续租、改业态或再次升级；施工完成时按目标状态生效并重开收益段。前端在提交前列出费用、工期和雇员数，要求二次确认。
- **回归**：`test_construction_blocks_repeat_work_and_resumes_income_by_game_day`、`test_managed_property_staffing_and_business_type_change_net_income` 及既有升级/业态测试通过。

### E40-02 地块只可买断，没有租约与到期处理

- **现象**：所有地块只能购买；玩家无法以较低前期成本租用商业/工业地块，也没有押金、续租、退租或到期收益暂停。
- **根因**：资产记录只有买断价格和收益参数，没有 `tenure`、租期、押金或租约状态字段。
- **修复**：新增 30/90/180/365 天租约，预付整期租金并缴纳 1.5 个月押金；支持续租与退租，租约到期后收益暂停，租赁资产不能出售、不计入自有净值；租赁地块同样可经营，但租期必须覆盖施工工期。
- **回归**：`test_property_lease_deposit_renewal_expiry_and_release`、`test_leased_property_is_not_counted_as_owned_net_worth`、`test_property_purchase_creates_typed_parking_and_blocks_sale_while_occupied` 通过。

### E40-03 地块会生成在水面、公园或绿地上

- **现象**：部分工业资产生成在市中心或公园里，部分地块落在水面；旧逻辑在随机尝试失败后会返回「最不坏」的坐标，仍然非法。
- **根因**：城市包只有圆形排除区，没有真实水面/绿地几何；`_candidate_point` 的兜底分支直接返回最后一个候选点，未做合法性检查。
- **修复**：新增随包发布的 OSM 离线地形掩码 `city_terrain.json`，运行时读取水面、公园、森林、草地、保护区等多边形；所有地块候选点按多边形边界并留出缓冲距离，工业地块继续避让市中心缓冲带；随机尝试失败后改用确定性螺旋搜索，仍找不到合法点则跳过并计入 `skipped_parcels`，不再回退到非法点。
- **回归**：`test_city_profile_exclusions_and_industrial_distribution_are_respected`、`test_city_terrain_pack_covers_every_catalog_city_and_has_valid_rings`；27 城 10,911 个多边形全部通过环有效性检查。

### E40-04 融资上限 49% 与收购门槛 49% 互相卡死，持股 49.00% 仍差 1 股

- **现象**：俱乐部资料显示「需持股 49.00%，当前 49.00%，还需买入 1 股」，但买入被 25% 持股上限拦住，融资又因 49% 上限无法再增发，收购按钮始终不可用。
- **根因**：融资上限与收购门槛同为 0.49；`max_finance_shares` 向下取整后可能停在门槛下方 1 股，而常规融资最低 2% 股本的额度又会把持股推过 49%，形成无解区间。
- **修复**：融资上限改为 49.9%，收购门槛仍为 49%；接近上限且常规 2% 额度会越界时，允许一笔「补足到收购门槛」的小额融资，最小股数按 `(49% × 股本 - 已持)/(1 - 49%)` 反解并不少于 1 股，且不超过剩余额度。前端融资弹窗同步计算该最小股数，避免输入 1 股却没有效果。
- **回归**：`test_a_final_financing_may_be_a_one_share_top_up_near_the_ceiling`、`test_the_board_publishes_every_percentage_the_ticket_quotes`、`test_stock_order_frontend` 通过。

### E40-05 香港地形抓取遇到 Overpass HTTP 500（构建期）

- **现象**：首次批量生成 `city_terrain.json` 时，香港请求返回 Overpass `HTTP 500`，脚本中止，已完成的城市数据已落盘。
- **根因**：Overpass 公共实例在高峰期限流/过载；脚本已有两次重试和备用端点，但单城仍可能连续失败。
- **修复**：保留断点续跑设计（每城完成即写盘），失败后单独重跑 `py -X utf8 scripts\build_life_terrain_data.py hongkong`，再继续巴黎、柏林；最终 27 城齐全。
- **回归**：`test_city_terrain_pack_covers_every_catalog_city_and_has_valid_rings` 通过；地形文件 7,392,797 字节。

### E40-06 本轮未实机验证（已知边界）

- **状态**：未启动 Football Manager、正式 EXE 或真实存档；租约、施工、地图点击热区与真实存档迁移只通过领域/API/前端静态测试验证。
- **处理**：交付摘要保留此边界；实机若出现问题，应记录城市、资产 ID、租约起止日、施工起止日、操作前后余额与浏览器/桌面宿主错误信息。

## 第 39 轮（V2.8.4Beta，2026-10-17）

### E39-01 城市层显示已下载，但地块层仍不可查看

- **现象**：玩家下载城市层后，城市概览可见；缩放到 z13–15 时地块层仍显示未下载或没有可交易资产，重新点击下载也可能继续提示成功。
- **根因**：早期 `install_layer_pack("city")` 只写入 `layers/<country>/<city>.json`，没有同步生成 `packs/<country>/<city>.json`；下载入口只调用 `load_city_pack()`，文件不存在时直接返回，却仍把操作报告为成功。旧版已下载城市因此永久停留在“有城市摘要、无地块包”的半安装状态。
- **修复**：城市层下载现在写入城市层后立即安装地块包；地块包安装也会补齐城市层。新增 `repair_installed_city_layer_parcels()`，在读取 `/api/life/city-packs` 时幂等扫描旧城市层，仅为缺失地块包的城市重建确定性地块数据。
- **回归**：`test_installed_city_layer_repairs_missing_parcel_pack` 从仅有汕头城市层的文件状态出发，验证修复后地块包存在且地块数大于零；`test_city_layer_download_installs_parcels_immediately` 验证城市下载及反向安装均保持两层同步。

### E39-02 城市层未统计资产并出现多个重复地区

- **现象**：进入城市层后资产数量与总资产不完整；北京等城市出现多个重复“西城”节点，右侧同时列出大量资产数为零的地区。
- **根因**：旧版购买记录没有保存 `district_id`，聚合器无法把资产归入正式区县，只能按每项资产生成独立节点；同时聚合结果无条件返回城市所有区县，导致空地区也被展示。
- **修复**：schema 4 在购买时持久化 `district_id`；旧存档依次按已存区县、确定性地块 ID 前缀、中英文区县名称回填。聚合先按区县合并，再只返回至少有一项资产的区县；无法匹配的资产进入唯一的“其他区域”节点。
- **回归**：`test_property_aggregates_merge_legacy_district_rows_and_hide_empty_districts` 验证两条旧西城车库合并为一个节点、金额合计正确且所有返回地区均非空；`test_property_purchase_persists_the_parcel_district` 验证新购买记录保存区县字段。

### E39-03 营业额口径不清，升级产出提升偏低

- **现象**：产业卡只显示一个未标周期的收益数字，玩家无法判断是日收入还是月收入；资产从 1 级升到 5 级后的产出增幅有限，升级投入与回报不直观。
- **根因**：底层一直采用月度经营口径，但界面文案只写“收益”；住宅每级 14%、商业/工业每级 12% 的增益在 5 级时分别只有约 1.56 倍和 1.48 倍，缺少与升级成本相称的收益感。
- **修复**：界面明确标注月营业额（税前）、月工资支出、月净收益，并增加每日净收益行；实际入账仍按 `月净收益 × 12 ÷ 365` 逐日累计。住宅每级租金增益提高到 20%（5 级约 1.8 倍），商业/工业每级经营增益提高到 18%（5 级约 1.72 倍）。
- **回归**：`test_property_upgrade_has_a_meaningful_income_gain` 固定住宅 5 级相对 1 级至少 1.75 倍，并断言两项增益不低于 20%/18%；既有雇员、业态和收益分段测试继续通过。

### E39-04 本轮未实机验证（已知边界）

- **状态**：未启动 Football Manager、正式 EXE 或真实存档；已下载层修复、区县聚合与产业数值通过领域、API 分发与前端静态测试验证，不等于实机地图 UI 验收。
- **处理**：交付摘要保留此边界；实机若仍有无法查看的城市，应记录国家、城市、缩放级别、层包是否安装及浏览器/桌面宿主错误信息。

## 第 38 轮（V2.8.4Beta，2026-10-17）

### E38-01 非中国国家层错误回退为中国层

- **现象**：地图增加英国、法国、德国后，切换国家仍可能读取旧版单一中国国家层摘要，显示错误的国家资产汇总和“已安装”状态。
- **根因**：`mapLayerSummary("country")` 在国家代码查不到时无条件回退 `state.packs.layers.country`；这个字段是旧版中国国家层的兼容别名，不对应英国、法国或德国。
- **修复**：只有 `state.map.countryCode === "CN"` 时才允许旧字段回退；其他国家只读取 `state.packs.layers.countries[countryCode]`。
- **回归**：新增前端接线断言，四国国家层安装测试验证 `countries.CN/GB/FR/DE` 各自独立摘要。

### E38-02 房产改配置与升级可能改写已赚取收益

- **现象**：若直接在房产上修改自住/出租、业态、雇员或等级，下一段收益会按新参数覆盖整个持有期，旧选择应得的收入被追溯改写。
- **根因**：旧收益只保存单一 `monthly_income`，没有“当前收益段起点”和累计段收益，配置或升级后无法区分变更前后的收入。
- **修复**：schema 3 增加 `income_since_day`、`accrued_income` 与 `accrued_days`；所有配置和升级提交前先 `_close_income_segment()`，领取收益时再清空累计段。旧存档按领取日和购置日建立默认收益段。
- **回归**：`test_property_reconfiguration_keeps_accrued_income_segments` 验证第 100–110 天的租金在改为自住后仍保持为 10 天应收。

### E38-03 房产升级扣款后提交失败的退款边界

- **现象**：升级流程如果已扣银行/钱包资金，但房产提交或保存失败，玩家会损失升级费用而没有获得等级。
- **根因**：扣款、领域提交与存档不在同一存储事务中；只靠抛错无法自动返还已经移动的合并资金。
- **修复**：`upgrade_life_property()` 捕获提交或保存异常，调用 `refund_combined_funds()` 将完整付款退回，再向上抛出错误；不改变成功路径。
- **回归**：`test_property_upgrade_refunds_payment_when_commit_fails` 使用真实 API 方法、扣款桩和失败提交桩验证退款分类为 `life_property_upgrade_rollback`。

### E38-04 本轮未实机验证（已知边界）

- **状态**：未启动 Football Manager、正式 EXE 或真实存档；本轮 27 城、经营面板和四国国家层由静态/领域测试覆盖，不等于实机 UI 验收。
- **处理**：发布说明保留此边界；若实机发现城市瓦片或布局问题，应在下一轮记录具体国家、城市、缩放级别和截图证据。

## 第 37 轮（V2.8.3Beta，2026-10-17）

### E37-01 购买地块耗时过长，看起来像程序卡死

- **现象**：点击任意资产购买后长时间停留在“正在读取生活资产…”状态，没有成功或失败反馈。
- **根因**：`buy_life_property()` 每次购买都调用全局 `parcel_index()`，遍历所有已安装城市包并建立全量索引；城市包数量增加后，单次购买成本随全部城市包规模增长，而不是只随目标城市增长。
- **修复**：购买请求携带 `city_id`，服务端通过 `parcel_entry(parcel_id, city_id)` 只读取目标城市包；城市包加载增加按文件大小与修改时间校验的 LRU 缓存，重复购买复用解析结果。前端购买按钮改用独立 `life.map.buying` 状态。
- **回归**：`test_city_pack_cache_reuses_an_unchanged_file`、`test_buying_a_plot_with_a_city_hint_avoids_the_global_parcel_index`；购买路径走真实 `LocalOddsState.buy_life_property()` 扣款桩。

### E37-02 已购资产与附带车位不可见

- **现象**：地图上已购买的资产与可购买资产没有视觉区别；资产详情和车库资产详情不显示住宅、商业、工业或独立车库附带的停车位。
- **根因**：地图 marker 没有 `owned` 状态类；旧城市包没有 `parking_spaces` 字段，房产/车库记录也只保存容量而没有统一投影到 API。
- **修复**：已持有 marker 增加金色描边与右上角圆点；`/api/life/city-packs` 通过 `parcel_parking_spaces()` 为旧数据回退计算；地块详情、列表和车库资产详情显示车位数。不提升城市包 schema，避免升级时强制重建。
- **回归**：`test_life_system.py` 静态断言 `owned` 样式、车位文案和购买状态；`test_city_pack_cache_reuses_an_unchanged_file` 覆盖缓存路径。

### E37-03 女足成年俱乐部被当成非男足目录项排除

- **现象**：世界俱乐部目录没有女足联赛俱乐部，无法为后续女足球员互动建立基础。
- **根因**：`_looks_non_mens()` 同时检查女足标记和青年/预备队标记，`build_world_clubs()` 与 `merge_native_world_clubs()` 把女足成年俱乐部一并丢弃；分页也没有性别字段。
- **修复**：拆分为 `_looks_womens()`、`_looks_non_senior()` 和 `_world_club_gender()`；目录保留女足成年俱乐部并写入 `gender`，分页支持 `men|women|all` 并重建对应分面。股市 `_stock_market_raw_directory()` 明确只保留男足，避免交易所数据变化。
- **回归**：`test_keeps_womens_senior_clubs_but_still_excludes_youth_sides`、`test_world_club_gender_scope_keeps_womens_facets_separate`、`test_stock_market_directory_excludes_womens_clubs`。

### E37-04 编辑器模组修改国名后软件仍显示旧名称（已知边界）

- **现象**：玩家在国家编辑器中修改国家名称，FMSDD 读取俱乐部信息仍显示内置名称。
- **根因**：当前实现使用 `src/assets/nation_mappings/nation_mappings_zh.json` 的 FM 国家 ID 映射；`Reader.national_team_name()` 只验证 Nation 指针，再按键查表，没有经过实机验证的 Nation 名称字段偏移。
- **处理**：本轮不猜测内存地址，也不把联赛名或俱乐部名当作国家名回退；在开发日志中明确当前边界。若要支持模组国名，需要先取得明确授权的 FM26 实机样本并提供 Nation 对象字符串布局验证。
- **状态**：未修复，按设计保留内置映射；不影响女足俱乐部与球员筛选。

### E37-05 旧前端测试投影遮蔽新增世界俱乐部控件

- **现象**：新增的 `test_world_club_gender_scope_is_wired_to_the_query_and_selector` 在源码中明明存在 `data-i18n="world.female_clubs"`，测试读取到的 HTML 却不包含该控件。
- **根因**：`tests/conftest.py` 会为历史前端结构测试把 `index.html`/`app.js` 投影为旧版中文视图；`test_world_clubs.py` 在该兼容清单内，新增的原生选择器被投影层按设计移除。属于测试读取口径问题，不是产品页面缺失。
- **修复**：该接线测试改用 `frontend_source.raw_web_source()` 读取未投影源码；其他依赖旧中文结构的断言保持不变。
- **回归**：该测试单独运行与六组聚焦套件均通过，后者为 **267 passed / 34 subtests passed**。

## 第 36 轮（V2.8.2Beta，2026-10-17）

### E36-01 所有生活资产购买都返回“请求无效”

- **现象**：在地产地图右侧选择任意住宅、商业、工业或车库地块并点击购买，均提示“请求无效”，余额没有变化，也没有生成房产。
- **根因**：`buy_life_property()` 调用 `charge_combined_funds(plan["total"], "life_property_buy", kind=...)`，第二个位置参数已经绑定到该函数的 `kind`，关键字参数再次传入 `kind` 时 Python 在函数体执行前抛出 `TypeError: got multiple values for argument 'kind'`。通用错误边界把未标记为安全的 `TypeError` 显示为“请求无效”。
- **修复**：账本元数据改名为 `parcel_kind`；不改变扣款、退款和地块提交顺序。用 AST 搜索确认 `src/fm_odds_web.py` 中没有其他 `charge_combined_funds` 调用同时传入第二个位置参数和 `kind=`。
- **回归**：`test_buying_a_plot_keeps_parcel_kind_out_of_the_charge_kind` 使用与生产签名一致的扣款桩走 `LocalOddsState.buy_life_property()`，断言分类为 `life_property_buy`、元数据键为 `parcel_kind`、房产成功写入。

### E36-02 俱乐部资料头部被压缩、左窄右松

- **现象**：从股市交易窗打开俱乐部信息后，顶部绿色区域将俱乐部名称、最多六项资料和固定的收购控件挤在同一行；左侧名称与说明被压窄，右侧留白过多，资料文字难以阅读。
- **根因**：`.world-detail-profile` 使用 `minmax(0,1fr) auto auto` 三列，身份、资料 `dl` 和 220px 收购控件共享一行；资料数量和长中文说明变化后没有独立的版面空间。
- **修复**：共享资料页改为 `world-detail-profile-hero`（身份 + 收购操作）与 `world-detail-profile-facts`（全宽三列资料板）；`min-width:0`、`overflow-wrap:anywhere` 和响应式两列/单列避免内容被截断。
- **回归**：`tests/test_stock_ticket_frontend.py` 断言新结构、三列资料板、收购控件保留与旧单行网格移除。

### E36-03 右侧地块列表点击后地图没有跳到资产位置

- **现象**：右侧“可交易资产”列表点击地块只更新选中项和详情，地图仍停在原来的城市视图，需要手动拖拽和缩放寻找地块。
- **根因**：列表行与地图针共用 `map-marker` 动作，处理分支只写入 `parcelId` 并重绘，没有读取地块坐标或调整地图层级。
- **修复**：列表行标记 `data-map-focus="true"`；处理时通过 `findParcel()` 读取坐标，设置 `center` 并把 `zoom` 提到 `TRADE_MAX_ZOOM`（z15）。地图针不带该标记，保持仅选中。
- **回归**：`tests/test_life_system.py` 静态断言列表标记、居中坐标赋值和 z15 缩放；`node --check src\web\life_page.js` 通过。

## 第 35 轮（V2.8.1Beta，2026-10-17）

### E35-01 上一版本购买的车辆没有图片

- **现象**：升级后车库中上一版本购买的车辆卡片没有正常车辆图，只有空白或旧路径。
- **根因**：第 34 轮已把运行时车辆图片从 `.jpg` 替换为透明 `.webp`，但旧生活存档仍保存旧 JPG 路径；旧图片已不再进入运行时包，前端只能加载失败。只修 CSS 无法恢复。
- **修复**：`schema_version` 升至 2；`normalize_state()` 和 `public_view()` 通过车辆 `catalog_id` 查询当前目录中的 `image`，找不到时再把 `.jpg/.jpeg` 后缀替换为 `.webp`；账户收藏图鉴同样走该映射。
- **回归**：`test_normalize_state_migrates_legacy_home_and_vehicle_images` 验证旧 JPG 映射到 `car-16.webp`；`test_collection_counts_duplicates_without_converting_them` 验证旧图鉴路径同步。

### E35-02 车库是独立商品，和房产资产没有关系

- **现象**：初始住宅车库与公寓/高级/仓库购买项独立存在，房产购买后不会增加车位，新地图也没有可购买的车库资产；用户无法按资产来源管理车位。
- **根因**：首版把车库建模成固定商品表，容量和资产脱节，无法表达“住宅 1、商业 2、工业 4、独立车库 8–40”的规则。
- **修复**：删除固定 `GARAGE_TYPES`，把车位绑定到房产记录并生成 `property_parking` 车库；地块层新增 `garage` 类型，购买后生成 `standalone` 车库；初始 `club` 车库为 2 车位；旧公寓/高级/仓库车库保留为 `legacy`，不再提供购买。
- **回归**：`test_property_purchase_creates_typed_parking_and_blocks_sale_while_occupied` 验证 1/2/4 与独立车库容量；`test_normalize_state_migrates_legacy_home_and_vehicle_images` 验证旧车库保留与旧 `home` 迁移。

### E35-03 每城固定 54 块，工业/资产落在市中心、公园或水里

- **现象**：地图资产数量少，所有城市使用同一套均匀分布，工业生产可能出现在市中心或公园，部分点落在水体。
- **根因**：生成器只有单一距离和随机角度，没有城市画像、区县角色、工业中心缓冲和水体/公园排除区，也没有按城市类型调整住宅/商业/工业比例。
- **修复**：新增 `city_profiles.json`，以城市等级、城市类型、区县角色、排除圆和工业缓冲驱动确定性生成；每城提升至约 96–127 块，工业只在外围，核心/景区区县不生成工业，资产数量按画像调整。
- **回归**：`test_city_pack_is_deterministic_and_uses_city_profile`、`test_city_profile_exclusions_and_industrial_distribution_are_respected`、`test_city_type_changes_the_asset_mix`；当前 8 城生成点全部在排除区外，工业点均距中心至少 2.8 km。

### E35-04 出售带车的房产会连带删除车库并丢失车辆停车位置

- **现象（风险）**：房产出售会删除附赠车库，但车辆仍留在存档中，形成指向不存在车库的悬空引用。
- **修复**：`sell_property_plan()` 在报价阶段检查附赠车库占用，存在车辆时拒绝出售并提示先迁移；提交阶段再次按键删除车库，配合锁保证一致性。
- **回归**：`test_property_purchase_creates_typed_parking_and_blocks_sale_while_occupied` 断言有车时抛出“迁移”错误。

### E35-05 本地测试执行器的 Node 子进程管道句柄无效（环境问题，非产品）

- **现象**：`test_i18n_locale_packs.py` 通过 Python 管道启动 Node 时出现 `OSError: [WinError 6] 句柄无效`，但同一脚本在直接 Node 文件探针下可执行。
- **根因**：当前 Windows 执行器提供的标准句柄在 Python 3.14 的 `subprocess.run(capture_output=True)` 路径中不可继承；不是 Life 文案或运行时代码抛出的断言。
- **处理**：用 `stdin=DEVNULL`、stdout/stderr 文件重定向的安全探针复核；11 种 locale 契约测试结果为 **9 passed / 3 failed**，3 条失败为既有 `docs/I18N_ARCHITECTURE.md` 缺失与旧语言包英文/繁中审计，与本轮 `i18n.life.js` 无关。未修改产品代码或测试来掩盖该环境问题。
- **最终全量结果**：以临时子进程兼容插件运行全量测试 → **3577 passed / 14 failed / 239 subtests passed**。14 条失败均属于本文件登记的既有历史失败或当前 Windows 测试环境路径问题；本轮 Life、车辆出售 API 与前端聚焦测试无新增失败。

## 第 34 轮（V2.8.1Beta，2026-10-17）

### E34-01 地图空白，且一次网络抖动会把底图永久锁在 OSM

- **现象**：用户安装城市包后仍看不到底图，页面左下角显示 OpenStreetMap 归属，地图区域只有空白或少量资产标记。
- **根因**：旧实现将 OSM 作为默认底图；部分网络访问 OSM 瓦片失败时，单张瓦片错误就可能触发底图切换并把 `osm` 写入 `localStorage`。之后重启仍读取这个旧偏好，即使高德可用也不会重新尝试，表现就像地图彻底坏掉。
- **修复**：默认底图改为高德；当前视口必须没有任何瓦片成功，并且至少三张瓦片失败（等待 900ms 确认）或 3 秒看门狗内仍无任何成功加载，才自动回退；已完成但失败的图片在监听器挂载前也能被计数。自动回退不再持久化；偏好键升级为 `fmsdd-life-basemap-v2`，升级用户先回到高德默认值，主动选择 OSM 仍会保存。
- **回归**：`tests/test_life_system.py` 增加默认缩放 `z13`、高德域名、回退不得写死 `saveMapProvider("osm")` 与偏好键 v2 断言；开发机实测高德/OSM 瓦片返回 `200 image/png`。

### E34-02 车辆黑底、图片裁切与车库竖矩形卡片

- **现象**：亮色主题下展厅和车库车辆图片仍是黑色背景；车库中的车辆只显示局部，卡片是竖矩形，整车无法完整看到。
- **根因**：运行时使用带黑色背景的旧 JPG，CSS 又用固定黑底与 `object-fit: cover`；车库图文布局没有给 16:9 车辆图足够的横向空间。仅改 CSS 无法移除图片本身的黑色背景。
- **修复**：425 张运行时车辆图统一重建为透明 WebP，旧 JPG 移到 `build/life-car-jpg-legacy/`；CSS 改为主题浅色渐变、`object-fit: contain`，车库卡片采用 16:9 横向图片区与右侧信息区，窄屏改为上下布局；图片增加内边距并略微缩小。
- **回归**：EXE 内核对 425 张 WebP 全部可解码、均带透明通道、0 张 JPG、0 字节文件为 0；`test_life_system.py` 检查 `object-fit: contain`、31% 图片列与浅色渐变。

### E34-03 车库容量标题直接显示原始 i18n 键

- **现象**：车库卡片标题上方显示 `life.garage.capacity`，而不是“容量”或对应语言的文案。
- **根因**：前端引用了不存在的键名，i18n 回退逻辑只能把键名原样返回。
- **修复**：改为实际存在的 `life.capacity`。
- **回归**：`test_life_system.py` 增加“不再引用 `life.garage.capacity`”的静态断言。

### E34-04 预存在失败复核（非本轮引入）

- **现象**：全量测试 **3569 passed / 15 failed / 239 subtests passed**。
- **处理**：15 条与既有失败清单逐条同名，本轮没有修改相关模块，也未新增失败；仍不处理无关历史缺陷。

## 第 33 轮（V2.8.1Beta，2026-10-17）

### E33-01 Life 加入侧边栏后，互斥展开测试仍只造五个分组

- **现象**：`test_shell_frontend_optimization.py::test_sidebar_group_open_state_keeps_only_the_latest_group_expanded` 失败。测试夹具只创建 `world / facilities / club / relations / stocks` 五个分组的 DOM 假元素，而 `SIDEBAR_GROUP_IDS` 已新增 `life`，遍历到 `#life-toggle` 时得到 `undefined`。
- **根因**：夹具的分组清单与产品实际分组脱钩；新增 Life 一级菜单后没有同步测试夹具。
- **修复**：在假元素生成列表与「其余分组应关闭」的断言中加入 `life`，并让 Life 也参与「只展开最后一个分组」的验证；产品代码未改。
- **回归**：`tests/test_shell_frontend_optimization.py` 全绿。

### E33-02 静态国际化审计没有加载 Life 文案模块

- **现象**：`test_i18n_static.py` 两条失败：`index.html` 中的 `nav.life` 在审计词典中不存在；脚本顺序尾段也与预期不符。
- **根因**：静态审计的 `_catalog()` 文件清单和 `index.html` 启动顺序白名单只列到 `i18n.stocks.js`，没有同步新增的 `i18n.life.js` 与页面模块 `life_page.js`。
- **修复**：把 `i18n.life.js` 加入审计加载列表，把 `/i18n.life.js` 和 `/life_page.js` 加入脚本顺序断言；产品页面加载顺序本身已正确。
- **回归**：`tests/test_i18n_static.py` → **5 passed**。

### E33-03 源站缺少 Lamborghini Revuelto 图片

- **现象**：车辆目录中的 Lamborghini Revuelto（ID 899）没有可用渲染图；按用户要求不再补图。
- **修复**：从运行时车辆目录、图库图片与 manifest 中移除该条目，抓取器继续保持排除，避免后续重新抓取时写回。
- **回归**：运行时车辆目录 **425 辆 / 425 张图片**，ID 899 不再出现；全部图片可由 Pillow 解码。

### E33-04 Life 长句在部分语言仍回退英文（已知，未处理）

- **现象**：`i18n.life.js` 的 11 个 locale 均有完整键集合，但除简体/繁体中文外，部分长句仍引用英文基准值。
- **处理**：首版先保证入口、页面标题与主要操作可读，英文回退链由现有 i18n 运行时兜底；长句翻译列为后续完善项，不阻塞 Life 初版打包。

## 第 32 轮（V2.8.0beta，2026-10-17）

### E32-01 公告只替换品牌会留下错误的字母释义

- **现象**：公告原文解释的是上一轮的 `E = Equity`；若只把名称替换成 FMSDD，会变成“S 名称却是 E = Equity”，与用户要求的 S = Stock 矛盾。
- **根因**：更名不仅是一个字符串，还包含字母释义、来源名称与兼容边界。
- **修复**：11 种语言逐条重写置顶公告的【更名说明】，统一写明 `FMODD → FMSDD`、`S = Stock（股票）`，并保留“程序文件夹、数据目录、存档、字体目录不变”的兼容说明。
- **回归**：`test_announcements_frontend.py`；额外脚本解析 154 条公告值，确认 `FMEDD` 为 0。

### E32-02 全局改名可能误伤路径与既有环境变量

- **现象（风险）**：运行时数据路径、WebView 宿主文件名、存档后缀、HTTP 头与环境变量都包含 `FMODD`，若把它们一起改成新品牌，会导致老存档、字体、窗口状态与开发环境“消失”。
- **修复**：仅替换独立品牌词；刻意保留 `Documents\FMODD`、`%LOCALAPPDATA%\FMODD`、`FMODD.WebViewHost.exe`、`*.fmodd`、`FMODD_DATA_ROOT`、`X-FMODD-*`、`window.FMODDI18n` 等兼容标识。上一轮已存在的 `FMEDD_RUST_NATIVE_DLL` / `FMEDD_CPP_HOOK_DLL` 也继续保留。
- **验证**：`rg` 扫描产品代码，剩余 `FMEDD` 仅为这两个环境变量名；相关 i18n/desktop parity 测试通过。

### E32-03 源站车辆目录中的 899 号条目没有图片

- **现象**：902 条车辆目录里，ID 899 的 `image` 字段为空；请求 `/assets/images/cars/899.png` 返回 SPA HTML 而非 PNG。
- **根因**：上游站点数据缺失，不是抓取脚本的 PNG 校验问题。
- **修复**：按用户要求不提供替代图；从运行时车辆目录、图库清单与目录图片中移除该条目，并在抓取器中增加排除规则，后续重新抓取不会写回。
- **回归**：manifest `count=901`、`failed=0`、`source_failures=[]`、`fallbacks=[]`；运行时车辆目录 425 辆且没有该条目，全部图片可解码。

## 第 13 轮（V2.7.5beta，2026-10-15）

### E13-01 扩股会让原有持股的价值下降

- **现象**：俱乐部触发扩股后，玩家持仓的股数按 `shares_after / shares_before` 变多、均价同比降低，但界面显示的持仓市值反而下降，看起来像被凭空稀释。
- **根因**：股本没有被冻结。`shares_at` 每次都从 `initial_shares(row)` 重算，而 `initial_shares` 依赖设施与声望的当次读数；扩股写回基准价时又会把「当日价 × 2」当成下一次阈值，导致同一家俱乐部的股本和阈值在重读之间漂移，持仓估值随之跳动。
- **修复**：新增 `listed_shares(row, book)`，把上市股本冻结进股本记录的 `i`；`shares_at` / `stock_public` 全部改读冻结值，只有扩股能改股本。旧记录在 `_sync_share_book` 首次同步时补写 `i`（沿用当前股本，不跳变）。`detect_splits` 按同等比例扩充持仓（股数变多、均价同比降低），所持市值不变。
- **回归**：`tests/test_club_stock_market.py::test_a_listed_club_keeps_the_capital_it_listed_with`、`test_an_issue_never_cuts_a_lot_below_the_value_it_had`、`tests/test_stock_market_application.py::test_a_holding_scales_with_the_issue_and_still_trades`。

### E13-02 非当前交易所的持仓打开交易窗时 K 线、估值、市值全为空

- **现象**：在持仓区块点击一家属于另一个交易所（当前看板选中的不是它所在的交易所）的持仓，交易窗里 K 线、估值、市值都不显示或为 0；只有先切到它所在的交易所再点才正常。
- **根因**：`holding_lots` 对持仓过去只补 `last_price` / `avg_cost` / `qty` 这一组最小字段，`intrinsic` / `market_cap` / `factor` / `shares` / `history` 都为 0 或空；前端 `stockById` 会先命中持仓行，于是交易窗拿到的是这份残缺数据。
- **修复**：`holding_lots` 改为对任何有行情的持仓调用 `stock_public` + `price_history` + `_decorate` 生成完整盘口（估值、系数、市值、股本、K 线、涨跌），行不存在时才回退旧的最小字段集。
- **回归**：`tests/test_club_stock_market.py::test_holding_lots_carry_the_board_their_ticket_draws`、`tests/test_stock_market_application.py::test_a_lot_on_another_exchange_still_carries_its_board`、`tests/test_stock_capital_frontend.py::test_the_ticket_merges_the_board_and_the_holdings`。

### E13-03 扩股区间与下一次触发价不符合预期

- **现象**：扩股倍率区间是 110%–250%（一次最多可扩到 2.5 倍），而且下一次扩股仍然按最初的基准价 ×2 判断，玩家看到「扩股后价格 45，却仍要回到 60 才再扩」。
- **根因**：`SPLIT_RATIO_MIN/MAX` 为 1.10 / 2.50，且基准价 `b` 只在首次上市时写入，扩股后没有按除权口径更新。
- **修复**：区间改为 1.00–2.00 并新增 `MIN_SPLIT_ISSUE` 1% 保底（不会打印空扩股）；扩股后用除权收盘价写回基准 `b`，因此下一次触发价 = 本次扩股后价格 × 2（30 → 60 → 45 → 90）。
- **回归**：`tests/test_club_stock_market.py::test_split_ratio_is_deterministic_and_inside_the_band`、`test_the_next_issue_is_measured_from_the_price_after_the_last_one`、`tests/test_stock_market_application.py::test_an_issue_reaches_the_tape_the_board_and_the_next_order`。

### E13-04 旧的全局股本持仓在新模型下会凭空缩水

- **现象**：升级到每股股本模型后，2.7.4beta 及更早版本买下的持仓在新模型里股数没变、价格尺度变了，市值直接少了一个数量级（1000 万股尺度 → 各俱乐部自己的股本尺度）。
- **根因**：旧版本所有俱乐部共用一个全局股本 `LEGACY_SHARES_OUTSTANDING`，成交价是那个尺度下的每股价格；新模型的每股价格 = 市值 ÷ 俱乐部自己的股本，两者相差 `capital / LEGACY` 倍。
- **修复**：新增一次性修复 `repair_legacy_capital`，重放该俱乐部的交易日志，把旧尺度成交按 `price_then / price_now` 折算成今日尺度的股数与均价（买入累加、卖出/退市按均价扣减），只改持仓、从不动股本；`legacy_priced` 用 `LEGACY_PRICE_BAND` 判定一笔成交属于哪个尺度，今日尺度成交的持仓原样保留；`state["capital_repair"]` 保证只跑一次，并在公告里写一条 `capital`。
- **回归**：`tests/test_club_stock_market.py::test_a_legacy_capital_lot_is_repaired_into_the_clubs_own_scale`、`test_the_legacy_repair_leaves_a_lot_bought_on_todays_scale_alone`、`tests/test_stock_market_application.py::test_a_legacy_lot_is_repaired_once_and_the_tick_says_so`。

### E13-05 交易界面横向过窄

- **现象**：股票据是竖长条（宽 560px 左右），K 线被压扁、数字与按钮挤在一列，看起来不像交易界面。
- **根因**：`.stock-ticket-dialog` 沿用通用工具对话框宽度，正文是单列纵向堆叠。
- **修复**：股票据改横矩形（`width:min(1060px, calc(100vw - 40px))`），正文双列 `chart / facts | form`，图表放大到 780 × 220（208px 高、带成交量与悬停十字线）；≤1180px 窗口自动改为 `chart → facts → form` 单列堆叠（事实网格 2 列），≤900px 事实网格 1 列。
- **回归**：`tests/test_stock_capital_frontend.py::test_the_ticket_is_a_wide_sheet_and_stacks_on_narrow_windows`、`test_the_ticket_draws_the_wide_candle_series`。

## 第 14 轮（V2.7.6beta，2026-10-16）

### E14-01 小俱乐部的股本太小，单股价格虚高

- **现象**：设施与声望都不高的俱乐部（例如四档设施都在 5 级上下、声望几千）算出来的股本只有几百股，股价 = 当日市值 ÷ 当日股本，于是报出「一股几千上万」这样看不出是钱的读数；同一天里大俱乐部一股几块、小俱乐部一股上万，价格体系不可读。
- **根因**：`initial_shares` 是 `训练设施 × 青训设施 × 青训教练 × 青训招募 × 声望` 的直乘，最低可能落到几百；第 13 轮引入的下限 `MIN_SHARES_OUTSTANDING` 只有 1000 股，等于没有约束。
- **修复**：下限抬到 **100 万股**（`MIN_SHARES_OUTSTANDING = 1_000_000`），`initial_shares` 用 `max(MIN_SHARES_OUTSTANDING, product × reputation)` 收口；上限与四档设施的取值口径不变。已经上市并冻结股本（记录 `i`）的俱乐部不回溯补股，避免在玩家眼皮底下改尺子；要按新下限重开，需在「选择交易所」里取消再勾选该俱乐部所在的国家/联赛。
- **回归**：`tests/test_club_stock_market.py::test_a_tiny_club_lists_at_the_one_million_share_floor`。

### E14-02 世界俱乐部资料页没有股市入口，交易窗也只能从股市看板打开

- **现象**：在世界俱乐部里看一家俱乐部时，只能看到收购入口，想买它的股票必须退到股市模块、切换交易所、再从看板点进去；而如果那家俱乐部属于另一家交易所（或还没上市），交易窗就开不出来。
- **根因**：交易窗的数据来自股市看板的缓存行（`stockById`），而看板同一时刻只装一个交易所的行；俱乐部资料页也没有任何入口去请求单家俱乐部的盘口。
- **修复**：`LocalOddsState.public_stock_quote` + `GET /api/stock/quote?club_id=…` 让任意页面都能问一家俱乐部的完整盘口（`club_lot_view`：报价、估值、市值、系数、股本、K 线），并给出 `reason`（`unknown_club` / `no_save` / `market_closed` / `not_listed`）；前端新增 `openStockTicketForClub`，先查看板缓存、缺了才打接口，成功缓存进 `state.extras[club_id]` 并在成交后失效；世界俱乐部资料头部加「股票交易」按钮。
- **回归**：`tests/test_stock_market_application.py::test_the_quote_route_is_registered`、`test_a_quote_without_a_club_or_a_save_says_why`、`test_a_quote_reports_a_closed_exchange`、`test_a_quote_reports_a_club_outside_the_enabled_exchanges`、`test_a_quote_carries_the_ticket_row_the_account_trades`、`test_a_quote_matches_the_board_row_it_stands_in_for`、`tests/test_stock_ticket_frontend.py`（资料页入口与开窗行为）。

### E14-03 K 线图只有走势，没有坐标轴、均线与峰谷标点

- **现象**：大图里的 K 线只有一排蜡烛，看不出价格刻度、日期刻度，也认不出这段时间的最高/最低点在哪一根上；看盘时得自己去数蜡烛。
- **根因**：`stockCandleChart` 只有「蜡烛 + 成交量」两种图元，坐标、均线与标点都没有实现。
- **修复**：新增 `axes` / `marks` / `moving` 三个开关：右侧价格轴（4 条网格线 + `formatChartAxisMoney`）、底部日期轴（最多 5 个刻度，`MM-DD`）、MA5 / MA10 折线与图例、区间最高/最低点的圆点与徽标，价格范围留 6%（或 1% 收盘价）余量；文字类标注用 HTML 覆盖层实现，保证 13px 不被 viewBox 拉伸压扁。指数图（560×150）与交易窗（640×220）开启全部开关，38px 的看板行仍保持纯蜡烛。
- **回归**：`tests/test_stock_ticket_frontend.py`（坐标轴、均线、峰谷标记与 CSS 规则、大图开关、看板行保持纯蜡烛）。

### E14-04 交易窗与俱乐部资料页风格不统一

- **现象**：从俱乐部资料页开出的交易窗是旧版式（竖向堆叠、深色表头与资料页的深绿头部不是一套语言），与用户在外层看到的俱乐部资料页拼在一起很割裂。
- **根因**：`renderStockTicket` 沿用股市看板时代的版式，只做过一次「加宽」而没有和世界俱乐部资料页对齐。
- **修复**：股票据重排成资料页版式——`stock-ticket-hero` 深绿头栏（俱乐部名 + 股本 + 股价 / 估值 / 今日收购价 + 买卖切换）、左侧 `chart` 图表卡（640×220、成交量、可交互十字线）、右侧 `facts` 事实卡与 `form` 下单卡；宽 1180px，≤1180px 按 `hero → chart → facts → form` 单列堆叠，≤900px 再收窄。世界俱乐部资料头部改四列（名称、资料、股票交易、收购），窄屏改单列。
- **回归**：`tests/test_stock_capital_frontend.py::test_the_ticket_is_a_wide_sheet_and_stacks_on_narrow_windows`、`tests/test_stock_ticket_frontend.py`（票据版式标记）。

### E14-05 股本下限抬高后，单笔上限对小俱乐部等于「买空」

- **现象**（实现下限时发现的连带缺陷，未流入用户版本）：单笔绝对上限是 100 万股，而股本下限恰好是 100 万股，于是股本在 100–400 万股之间的俱乐部，一次点击就能把俱乐部手里的股票全部买走，报价随即失去流动性。
- **根因**：`max_shares_per_order` 只有「绝对上限 100 万股 / 股本 2% 取大」两条规则，没有考虑股本本身可能只有 100 万股。
- **修复**：新增 `MAX_ORDER_SHARE_CAP = 0.25`，单笔 = `max(min(1,000,000, 股本 × 25%), 股本 × 2%)`；股本 400 万股及以上的俱乐部结果与旧规则完全一致。
- **回归**：`tests/test_club_stock_market.py::test_max_order_scales_with_the_capital_but_keeps_a_round_lot`。

## 第 15 轮（V2.7.6beta，2026-10-16）

### E15-01 国家指数被当成货币显示

- **现象**：股市页与指数卡的读数带货币符号（`£1,361.07`、`£1,394.47`），指数越高、数字越大，看上去像一笔可以持有的金额。
- **根因**：`stockCandleChart` 的价格轴、MA 图例、区间高低徽标与 `stockCandleTooltipHtml` 全部硬编码 `formatChartAxisMoney`，而那是给个股价格用的货币格式化函数；指数卡复用了同一个图表组件，于是沿用了货币口径。
- **修复**：新增 `stockCandleFormats`（`money` = `stockMoney` / `formatChartAxisMoney`，`index` = 纯点位千分位、两位小数，坐标轴一位小数），`stockCandleChart` 新增 `format` 选项，图表内所有文字（价格轴、MA 图例、高低徽标）与 `renderStockTicket` 一样的悬停提示都走所选 formatter；节点带 `data-stock-candle-format` 便于契约测试。指数图调用改成 `format:"index"`，股票据保持 `money`。
- **回归**：`tests/test_stock_ticket_frontend.py`（指数非货币格式化）、`tests/test_stock_market_frontend.py`（悬停提示读取 `data-stock-candle-format`）、`tests/test_stock_capital_frontend.py`。

### E15-02 世界俱乐部资料页多出一个股票交易入口，方向做反

- **现象**：世界俱乐部模块的俱乐部资料页在「收购」旁边多出「股票交易」按钮；用户的原意是「在股市的交易界面里能查看俱乐部资料」，于是资料页多了一个它不该有的入口。
- **根因**：上一轮把「查看俱乐部资料」的需求理解成了「从资料页发起交易」，为此还专门加了 `/api/stock/quote` 路由、`public_stock_quote`、前端 `openStockTicketForClub` 与 `state.extras` 缓存，让任意页面都能凭俱乐部号开出交易窗。
- **修复**：世界俱乐部资料页整行还原（模板去掉 `.world-detail-stock-control` 与 `[data-world-detail-stock]` 监听、CSS 两行回滚到上一版）；`/api/stock/quote`、`LocalOddsState.public_stock_quote`、`_get_stock_quote_route`、`openStockTicketForClub` 与 `state.extras` 一并退役，`club_lot_view` 保留给 `holding_lots`；文案 `world.detail.stock_open` / `world.detail.stock_note` / `stock.quote.<reason>` 四条从 9 个语言包删除。
- **回归**：`tests/test_stock_ticket_frontend.py`（世界俱乐部资料页恢复原样、退役键不在任何语言）、`tests/test_stock_market_application.py`（单俱乐部报价一节移除后其余用例不受影响）、`tests/test_world_clubs.py`。

### E15-03 交易窗要滚动才能下单，买卖切换位置不友好

- **现象**：交易窗的下单区被压在「订单」卡片的纵向 `dl` 里，1180px 宽的窗口也要上下滚动才看得到确认按钮；买卖切换在右上角「今日收购价」旁边，下单时视线要在窗口两角之间来回跳。
- **根因**：第 13 / 14 轮把交易窗加宽成横矩形时沿用了更早的 `chart + form` 双列骨架，下单卡的每一格都是纵向堆叠，高度随字段数量线性增长；买卖切换是 hero 的一部分，与它实际要影响的下单表单分处两地。
- **修复**：`renderStockTicket` 的网格改成 `hero` 横跨 + `chart` / `facts` 两栏 + 底部横贯的 `order` 下单条；`stock-side-toggle` 移进表单，与股数输入、单笔成交拆解（三列两行的 `.stock-quote`）和确认按钮同处一条横带；窗口宽度 1180px、`max-height:calc(100vh - 28px)`，≤1180px 依 hero → chart → facts → order 单列堆叠，≤900px 下单条继续收窄。
- **回归**：`tests/test_stock_ticket_frontend.py`（下单条标记与买卖切换位置）、`tests/test_stock_capital_frontend.py::test_the_ticket_is_a_wide_sheet_and_stacks_on_narrow_windows`（新版尺寸与网格区域）。

## 第 16 轮（V2.7.7beta，2026-10-16）

### E16-01 首页十二个板块图标看起来是十二块互不相干的色块

- **现象**：首页应用网格里的图标是纯色圆角方块，颜色之间只有色相差、没有明暗与光照关系；悬停时整块按钮平移，图标本身没有反馈，整片网格看起来松散。
- **根因**：`.home-app-icon` 只有 `border-radius` 与 `background`，`::before` / `::after` 只在 `.locked` 状态下被使用；十六进制色值是平涂的单一颜色，没有渐变、没有内高光、没有投影，图标 `svg` 也没有任何 `filter`。
- **修复**：`.home-app-icon` 改为 74 × 74、圆角 20px 的渐变方块并加 `box-shadow`（外投影 + 顶部内高光）；新增 `::before` 左上柔光层（`radial-gradient(130% 96% at 24% -8%)`）与图标 `drop-shadow`；十二个板块（含新的 `.stocks`）的配色改成同色相深浅渐变；悬停时图标上浮 3px 并加强投影，`prefers-reduced-motion` 下取消上浮。
- **回归**：`tests/test_i18n_frontend.py` 的首页文案断言、`tests/test_home_*` 系列不涉及图标几何；样式改动通过聚焦测试与全量 `pytest tests` 验证，观感需用户实机确认。

### E16-02 集团卡片缩略态：按钮是重复入口，名称区块没有铺满

- **现象**：缩略态卡片左侧的俱乐部名称只在文字附近可点、背景也没有铺满整块；「更多 / 收起」按钮与「点击卡片展开」是同一个动作的两个入口；缩略态的「查看」按钮被压到 36px，与展开态的 48px 不一致。
- **根因**：`data-owned-club-disclosure` 挂在名称区块上，但区块自身是 `align-self: stretch` + 顶部对齐的网格项，`h2` 只有文字宽度；缩略态另有一条 `height: 36px; font-size: 13px` 的按钮规则，以及一个可见的 `owned-club-row-toggle` 按钮在承担「更多 / 收起」。
- **修复**：删除可见的展开按钮（保留 `.fmodd-sr-only` 状态文本用于播报）；名称区块改为 `align-content: center` 纵向居中，命名区块与右侧操作列都能展开/收起；缩略态不再压缩按钮，操作列固定 132px 宽、按钮与展开态同高；`getExpanded` 的按钮参数改为可选，`setExpanded` 不再重写按钮 HTML。
- **回归**：`tests/test_player_card_frontend.py::test_owned_club_collapsed_card_uses_inline_disclosure_without_misclicks`、`tests/test_player_card_frontend.py::test_owned_club_cards_default_collapsed_and_expand_in_requested_order`。

### E16-03 集团页头部与卡片布局过于松散、重复，操作按钮风格不统一

- **现象**：展开态卡片宽大松散、左侧信息过少；「查看 / 出售」用的是绿色与红色渐变，和软件主体的操作按钮不是一套语言；集团页把集团名重复显示在 `GROUP OFFICE · MY GROUP` 绿标题里，头部六项统计挤在标题右侧。
- **根因**：卡片在某个版本里同时存在两条互相覆盖的网格规则（旧的四栏 `minmax(260px,1.5fr) minmax(250px,1fr) minmax(190px,.8fr) 92px` 与新规则），缩略态遗留 `margin:-22px 0` 这类旧尺度；按钮用的是自绘渐变而不是 `var(--green-2)` / `var(--red)`；`portfolioControlDeck` 额外渲染了一条绿色标题。
- **修复**：清理 578–585 行残留的旧卡片规则，把两种状态统一到 `grid-template-areas` 的显式网格；「查看」改用 `var(--green-2)` 实心主按钮、「出售」改为白底 `var(--red)` 描边按钮；删除命令面板的绿色标题（`.portfolio-group-title` 等样式一并移除）；集团标题 `#my-clubs-page-title` 改为显示集团名，改名铅笔移到标题右侧，六项统计与刷新收进 `.my-clubs-header-tools`；展开态新增 `.owned-club-row-background` 背景条（成立年份、球场与容量、上座、身价、人数、四项设施等级）。
- **回归**：`tests/test_player_card_frontend.py`（卡片布局契约与封面、集团改名断言）、`tests/test_dark_mode_frontend.py`（深色主题覆盖）、全量 `pytest tests` 与第 15 轮基线逐条一致。

## 第 17 轮（V2.7.7beta，2026-10-16）

### E17-01 旗下俱乐部点击名称区块不再展开，详细信息条整体消失

- **现象**：集团页里点击俱乐部名称区域（或右侧操作列）完全没有反应，展开态的详细信息条再也不出现，看起来像「详细信息功能被删掉了」。
- **根因**：第 16 轮把可见的 `[data-owned-club-toggle]` 按钮改成了 `.fmodd-sr-only` 的状态文本节点，但 `initializeOwnedClubCardInteractions` 里仍然用 `card.querySelector("[data-owned-club-toggle]")` 去取那个已经不存在于 DOM 的按钮；`setExpanded(card, button, expanded)` 的首行守卫 `if (!card || !button || ...) return;` 于是每次都直接返回。删掉的是渲染产物，没删掉的是对它的依赖——展开动作被静默短路，既不报错也不改类名。
- **修复**：`setExpanded(card, expanded)` 去掉 `button` 形参，展开状态只由 `card.classList.contains("is-expanded")` 决定；删除 `[data-owned-club-toggle]` 的点击绑定，点击委托与键盘处理直接翻转该类名，`aria-expanded` / `aria-label` 与 `[data-owned-club-toggle-state]` 文案继续同步；保留 `[data-owned-club-disclosure][role="button"]`（名称区块）与右侧操作列两条入口。
- **回归**：`tests/test_player_card_frontend.py`（卡片布局与两态契约、`data-owned-club-toggle-state`）、`tests/test_dark_mode_frontend.py`；全量 `pytest tests` 与基线逐条一致。
- **教训**：删除可见元素时必须同时清掉所有按选择器取它的代码路径；「取不到就 return」这类守卫会把结构变更伪装成功能缺失，静态测试抓不到，只有实机点击才暴露。

### E17-02 `holding_lots` 的回退分支引用未定义的 `watchlist`，持仓面板会抛 NameError

- **现象**：点击持仓面板里某些交易所的持仓时，行情 / K 线 / 估值没有正常显示（对应第 13 轮已修过的「非选中交易所读不到值」的同类症状）。
- **根因**：`holding_lots` 的回退分支（目录或缓存缺失时构造最小视图）里引用了 `watchlist`，但该名字只在函数另一条分支中被赋值；走到回退分支就抛 `NameError`。同时该分支没有补齐 `holding_value` / `holding_cost` / `profit` / `profit_ratio`，即使不抛错也会让面板显示空值。
- **修复**：在 `holding_lots` 里补上 `watchlist` 局部变量与 `holding_value` / `holding_cost` / `profit` / `profit_ratio` 字段，每条 lot 写入 `frozen` 并在冻结时把 `sellable` 置 0，使回退分支与主分支返回同一形状。
- **回归**：`tests/test_club_stock_market.py`、`tests/test_stock_market_application.py`、`tests/test_stock_scope_display_frontend.py`。

### E17-03 行情 tick 把「冻结持仓」误判成退市，重开交易所后持仓与资本一起消失

- **现象**：关闭某个交易所（取消勾选对应国家/地区或联赛）后再重新开启，该所全部持仓消失；用户描述为「重开这个交易所会导致所有的持仓全部消失」。
- **根因**：关闭交易所走的是**结算 + 删除**路径——`apply_scope` 对移除范围里的交易所按当日收盘价强制卖出全部持仓、把现金以 `stock_delist_settlement` 入银行，再删除注册表条目与指数。玩家重新勾选时该所从初始状态重新上市，于是「持仓全部消失」，资产变成了现金。对一个范围切换操作而言，卖出是过度副作用。此外 `_settle_missing_holdings` 与 `sync_holding_quotes` 只按「目录里找不到这只俱乐部」判定退市，冻结持仓的所属交易所已从注册表移除，会被当成退市再结算一次。
- **修复**：`SCHEMA_VERSION` 4 → 5；新增 `_freeze_holdings`（给每条持仓打 `frozen` / `frozen_game_date`、按最后已知报价更新 `last_price`，不卖出、不产生盈亏、不写银行流水）与 `_unfreeze_holdings`；`apply_scope` 的移除分支改冻结、新增分支改解锁，`result["settlements"]` 清空、`cash_credit` 为 0，新增 `frozen` / `unfrozen` 结果字段，公告由 `scope_remove` 改为 `scope_freeze` / `scope_unfreeze`；`_settle_missing_holdings` 与 `sync_holding_quotes` 跳过 `frozen` 持仓（存档里真的消失的俱乐部仍按最后收盘价退市结算）；`sellable_qty` 对冻结持仓返回 0，`sell_plan` 抛「该交易所已关闭，持仓已冻结；重新开启交易所后解锁」；`market_view` / `_empty_view` 的 `totals` 新增 `frozen_value` / `frozen_count`；前端持仓行加 `is-frozen` / 冻结徽标 / 说明与冻结市值指标。
- **回归**：`tests/test_club_stock_market.py`（冻结 / 解锁、冻结不结算、冻结持仓不可卖、退市扫描跳过冻结）、`tests/test_stock_market_application.py`（范围切换结果字段与公告）、`tests/test_stock_scope_display_frontend.py`（持仓行的冻结标记与冻结市值）。

### E17-04 `dark-theme.css` 新增的冻结配色写成了 `#3a3categoriesel`

- **现象**：深色主题下冻结持仓行的底色 / 描边不生效，控制台看到无效颜色值。
- **根因**：手写十六进制色值时把 `#3a3218` 误敲成 `#3a3categoriesel`——编辑过程中有别的单词被插进了颜色值中间。CSS 解析器丢弃无效声明，因此表现为「样式静默不生效」而不是报错，这类错误只有逐条复核新增色值才能发现。
- **修复**：改回 `#3a3218`，并复核本轮 `dark-theme.css` 中新增的全部色值。
- **回归**：`tests/test_dark_mode_frontend.py`（深色主题审计块）；建议后续给 `dark-theme.css` 加一条「所有 `#` 开头的声明必须是合法 3/4/6/8 位十六进制」的静态断言。

### E17-05 自定义盘口范围在「未勾选」或「目录未就绪」时会把整窗比赛过滤成 0 场

- **现象**：把盘口读取范围切到「自定义国家/联赛」但还没勾选任何范围时，盘口可能整体变空；刚连接存档、世界俱乐部目录尚未扫描完成时也会出现同样结果。
- **根因**：`filter_fixture_rows_for_odds` 的 `custom` 分支直接按归属判定逐条过滤。范围列表为空时所有赛事都不属于任何国家/地区，判定恒为假；目录未就绪时 `competition_nation` / `club_nation` / `club_league` 全为空，同样恒为假。结果是「读不出来 = 全部不匹配」，随后这条空赛程还会被写进缓存并覆盖上一份可用盘口。
- **修复**：`fixture_in_custom_scope` 在 `nations` 与 `leagues` 都为空、或 `_custom_scope_index_has_data` 为假（目录没有任何归属数据）时返回 `True`，即「不限制」；范围未覆盖时始终额外保留执教球队的比赛；读取顺序重排为「读国家/联赛/俱乐部 → 按启用范围刷新盘口 → 股市范围与行情」，把目录扫描放在盘口刷新之前；`autoReadStockData` 里的盘口补刷失败静默，不阻塞股市自动读取。
- **回归**：`tests/test_odds_scope_custom.py::FixtureInCustomScopeTests`（空范围、缺目录、赛事/联赛/俱乐部三级归属）、`tests/test_odds_scope_custom.py::FilterFixtureRowsForOddsTests`（保留执教球队、窗口仍然生效）。

## 第 18 轮（V2.7.7beta，2026-10-16）

### E18-01 股价列与市值列按弹性无上限增长，把持股列与持仓列挤窄

- **现象**：行情看板里股价列与市值列过宽，后面的持股（成交量 / 股本）与持仓数据显得拥挤；窗口拉得越宽越明显。
- **根因**：这两列是等分弹性轨道——`minmax(112px,.95fr)` 与 `minmax(104px,.9fr)`。弹性上限「没有」，而列内容只有一个金额加一行小字（`stock.trade.factor`、`stock.trade.market_cap`），是整行里最短的两格。窗口每多一个像素，按 fr 比例分给这两列的像素就再也拿不回来，于是空白留给了内容最少的列，内容最多的两列（持股、持仓）反而只有 `minmax(118px,1fr)` 与 `minmax(112px,.95fr)`。这类「短内容 + 无上限弹性」的组合是典型的宽度倒挂。
- **修复**：两列改成**封顶弹性** `minmax(96px,132px)`（股价）与 `minmax(88px,118px)`（市值），上限由真实字体度量反推（系统中文字体下「金额 + 小字」的实测宽度）；让出来的像素按弹性比例回流给持股列 `minmax(150px,1.55fr)` 与持仓列 `minmax(140px,1.4fr)`。`.stock-shell` / `.stock-board` 未改，看板整体宽度不变。
- **回归**：`tests/test_stock_board_layout_frontend.py`（封顶值、轨道数与弹性下限）、全量 `pytest tests` 与基线逐条一致。

### E18-02 比赛情况 / 联赛排名 / 声望挤在持股列，与股本数据语义混在一起

- **现象**：持股列同时显示「成交量、原始股本、俱乐部持股、扩股」与「战绩、排名、声望」两类完全不同的数据，导致这一列既窄又杂；用户要求把战绩三项移到俱乐部名称那一列的联赛名称下方。
- **根因**：渲染层把两类语义塞进了同一个容器——`.stock-row-fundamentals` 既渲染成交量与股本（`stockCapitalText` / `stockSplitTitle`），又渲染 `stockFormText(stock.fundamentals)` 的战绩药丸与排名/声望行，没有独立的归属。列宽与语义因此同时失焦：想加宽股本数据就必然连带拉宽战绩，反之亦然。
- **修复**：`stockRowHtml` 里把战绩与排名/声望组装成 `formNote`，渲进 `.stock-row-name` 内新增的 `<small class="stock-row-meta">`（战绩仍是 `.stock-form` 药丸，`title` 保留完整战绩句），`.stock-row-fundamentals` 只留成交量与股本两行。列数仍是 7 条轨道，因此不新增列、不改变看板总宽。
- **回归**：`tests/test_stock_board_layout_frontend.py`（`stockRowHtml` 的列归属断言：meta 在名称列、fundamentals 不再含 `stock-form` / `stockRankText` / 声望，持仓字段仍完整）。

### E18-03 移动后的战绩行在窄窗口被省略号截断

- **现象**：战绩行移入名称列后，窄窗口下只剩「近 5 场 3胜…」这类半句，排名与声望读不出来。
- **根因**：`.stock-row-name small` 的既有规则是 `overflow:hidden` + `text-overflow:ellipsis` + `white-space:nowrap`（原本用来把过长的联赛名压成一行）。新加的 `.stock-row-meta` 直接继承这套规则，于是换行能力被静默关掉——CSS 不会报错，只是把内容裁掉。
- **修复**：为 `.stock-row-name small.stock-row-meta` 显式覆盖 `white-space:normal`、`text-overflow:clip`、`overflow:visible`、`display:flex` + `flex-wrap:wrap`。这一行在 1440px 以下格外重要：那个断点会整列隐藏持股列（`.stock-row-fundamentals`），战绩只能从名称列读到，因此宁可让它占两行高度也不能截断。字号沿用原值（13px），满足「用户可见字号 ≥13px」契约。
- **回归**：`tests/test_stock_board_layout_frontend.py`（换行覆盖与字号断言）。

## 第 19 轮（V2.7.7beta，2026-10-16）

### E19-01 玩家买入后股价不动，行情看板继续返回成交前的报价

- **现象**：本轮要求「用户交易会导致股价波动，涉及的百分比越大影响越大」。成交本身是成功的（持仓、账单都对），但看板上的股价、涨跌幅与收购价在成交之后仍然是原来的数字，要重启软件或换交易所才会看到新的报价——从玩家视角就是「我买了一大笔，股价纹丝不动」。
- **根因**：看板的缓存键只包含交易所范围、目录规模与 `data_version` 这类**存档外部**的状态，而交易冲击（`state.impact`）与融资注入的资本（`state.finance`）都是**玩家自己写进文档**的数据。键没覆盖它们，缓存因此判定「输入没变」，直接把上一秒的那份报价还了回来。这类缺陷的隐蔽之处在于：数据层是对的、API 是对的，只有「同一份输入」的定义漏了一项。
- **修复**：模型层新增 `extras_signature`（冲击事件条数 + 增资总额的廉价指纹），应用层把它的结果并入股市相关缓存键；报价合成函数（`market_factor` / `market_cap`）也改为接收 `market_extras(state)`，因此缓存一旦失效，重算出来的就是带玩家足迹的价格。回归：`tests/test_stock_market_application.py` 的缓存失效断言与 `tests/test_stock_order_frontend.py` 的冲击预估契约。
- **教训**：缓存键必须覆盖**所有**会进定价的输入；「玩家自己的操作」是最容易被漏掉的一类输入，因为它不在存档快照里，而在 ODD 自己的文档里。

### E19-02 大宗交易把报价抬到 2 倍，替俱乐部触发了一次扩股，冲击衰减后俱乐部被永久压在低位

- **现象**：实现完交易冲击后，一笔 10% 的大宗申请会在交割当天让报价脱离基本面。设计上这没问题（玩家确实把价格买上去了），但如果这笔冲击恰好把收盘价推过「基准价 × 2」，`detect_splits` 就会判定「俱乐部到价了」并自动扩股，把股本翻倍；等冲击按 10 天半衰期衰减回原值，除权后的价格就永久低于俱乐部自身的基本面——一次玩家的交易把俱乐部**永久**改写成了另一个价位。
- **根因**：`detect_splits` 与 `share_price` / `market_cap` 读的是同一份 extras。扩股判定本应只看「俱乐部自己值多少钱」，却把「玩家刚刚买出来的价格」也算进了估值。
- **修复**：新增 `finance_extras`——它在 `market_extras` 的基础上去掉 `impact`、保留 `finance`，并让 `detect_splits` 只读这一份。之所以保留 `finance`，是因为融资注入的是俱乐部**真实持有**的钱（且当日不改单股报价），它就该算进俱乐部价值；而成交冲击是市场价格，不是俱乐部的资产。回归：`test_club_stock_market.py` 中「大宗交易不触发扩股、融资注入仍计入市值」的断言。
- **教训**：同一个「价格」在不同判定里的语义可能不同。凡是「判定事实」的地方（扩股、退市、结算）都要问一句：这里的价格应该是俱乐部的基本面，还是市场的瞬时读数。

### E19-03 响应里缺 `max_order` / `block_order` 时，「全部」快捷键会变成 0 股

- **现象**：交易窗的「全部」按钮在正常情况下工作，但在看板行来自旧响应（或字段缺失）时，点下去会显示可买 0 股，玩家会以为「这只股票不能买了」。
- **根因**：上限走的是 `Math.floor(Number(stock.max_order || 0))` 这条链——缺失字段读成 `0`，而 `0` 在 `Math.min` 里是「最严格的限制」而不是「没有限制」。服务端算得再对，前端也会把「未知」当成「零」。
- **修复**：`stockDirectCap` / `stockBlockCap` 采用「给值就用、缺失就按当日股本 × 对应比例自己算」（`stockStakeRoom` 同理回退到 25% 天花板），`stockAffordableQty` 里的 `capped()` 再把「算不出来的 0/负数」翻译成 `Infinity`（未知的上限不参与收缩）。因此「未知」永远是「不限制」，而不是「归零」。回归：`test_stock_capital_frontend.py::test_the_all_shortcut_stops_at_the_club_the_board_and_the_stake`（断言 `amount > 0 ? amount : Infinity`）。
- **教训**：`|| 0` 是前端最危险的写法之一——它把「没有这个字段」和「这个字段是零」合并成同一个值，而这两种含义在限额判断里正好相反。

### E19-04 挂着的限价卖单与市价卖出可以卖同一批股票

- **现象**：本轮新增定价抛售（限价挂单）后，玩家可以先把 1000 股挂成限价卖单，再把这 1000 股市价卖掉。两笔都会成交：市价那笔把持仓清空，限价那笔在触价时再卖一次同一批股票（`commit_sell` 会把持仓夹到 0，但成交记录、账单与冲击都按 1000 股记），等于凭空多卖了一份。
- **根因**：`sellable` 只按「当日股本 − 我的持仓 − T+1 锁定」计算，没有任何字段记住「已经挂在场上待成交的那部分」。委托与持仓因此是两套互不知情的数字。
- **修复**：限价卖出在下单的瞬间就把股数从可售里扣掉（`reserved_qty` 汇总该所全部 `pending` 的限价卖单，`sell_plan` 与看板 `sellable` 都减去它），撤单或成交后立刻归还。回归：`test_club_stock_market.py` 的 `reserved_qty` / `sell_plan` 断言与 `test_stock_order_frontend.py` 的委托条契约。
- **教训**：任何「挂单」都是一笔占用承诺，必须在**下单那一刻**从可动用余额里扣掉，而不是等成交时才检查。

### E19-05 存档格式从 schema 5 升到 6：v5 文档缺 `impact` / `finance` / `orders` 三个字段

- **现象**：本轮把 `SCHEMA_VERSION` 从 5 升到 6，文档新增 `state.impact`（成交冲击序列）、`state.finance`（融资增资额）、`state.orders`（委托队列）三个顶层字段。用 v5 存档进入股市时，任何一处「直接按下标取用」的代码（例如 `order_slots` 里的 `len(state["orders"])`、`_record_impact` 里的 `state.setdefault("impact", {})` 之外的路径）都会在旧文档上抛 `KeyError`，而这类错误发生在**玩家打开页面**的时刻，表现为整个股市页打不开。
- **根因**：`save_state` 会写 `version`，但读路径上的 `_normalize` 只做过 `nations` / `holdings` 的补齐，新增字段没有一起补。旧文档不会自动获得新字段，而新代码假定字段存在。
- **修复**：`_normalize` 的补齐清单扩到 `("nations", "holdings", "impact", "finance")`（字典）与 `("notices", "trades", "watchlist", "orders")`（列表），并且只在类型不对时才重建，因此不覆盖玩家数据。**不需要一次性迁移**：v5 文档读进来时字段被补成空值，语义等价于「这个存档还没发生过交易冲击、也没融资、也没有挂单」，与真实情况一致。`_migrate_legacy` 仍只为更老的全局股本时代服务（`capital_repair`）。回归：`test_club_stock_market.py` 的旧文档读入用例（v5 载荷 `_normalize` 后 `impact` / `finance` / `orders` 均为空且不抛错）。
- **教训**：schema 升版不一定需要迁移脚本，但**一定**需要在读路径上做「缺字段就补空值、类型不对就重建」的归一化；只要有一处代码假设字段存在，旧存档就会在最不该失败的时刻失败。


### E19-06 小股本俱乐部的「单笔直购」被整手抬到股本的 25%，与 2% / 10% 分档冲突

- **现象**：本轮把「一次点击最多直购 2%、超过要走大宗申请、单笔申请最多 10%、持仓 25% 封顶」写成硬规则并做进界面，测试却发现一个 1,684,800 股的小俱乐部 `max_order` 与 `block_order` **相等且都是 421,200 股（股本的 25%）**：一次点击既超过了 2%，也超过了大宗的 10%，而且直接吃掉全部 25% 的持股额度——分档与大宗申请在这类俱乐部上等于不存在。
- **根因**：老的整手规则是 `max(min(MAX_SHARES_PER_ORDER 100 万股, MAX_ORDER_SHARE_CAP 25% × 股本), MAX_ORDER_SHARE_RATIO 2% × 股本)`。它诞生在「单笔天花板上限就是股本 25%、没有大宗档、也没有持股天花板」的年代，`max(...)` 这一步的作用是**抬高**小俱乐部的点击量（让 100 万股的小俱乐部一次能点 25%）。本轮把 2% / 10% 变成规则之后，这个「抬高」就变成了违规：整手（25% 股本）永远大于 2%，所以 `max` 在小俱乐部上总是选整手。本轮新增的 `max_block_shares` 又照着同样的 `max(_order_lot, 10%)` 写了一遍，把同一个错误复制到第二处。
- **修复**：把整手放进 `min`——`max_direct_shares = max(1, min(整手, 股本 × 2%))`。整手从此只能把上限**往下压**：股本 5 千万股以上时 2% 超过 100 万股，整手（100 万股）生效，历史点击量原样保留；1–4 百万股的小俱乐部一律退回 2%，想多买只能提交大宗申请，而大宗这条路径正好是用户想要的。`max_block_shares` 则直接等于 `股本 × 10%`，不再做整手兜底——股本下限 100 万股的 10% 已经是 10 万股，让整手抬高等于把整个上限交给一笔申请。回归：`test_max_order_scales_with_the_capital_but_keeps_a_round_lot`（重写为「整手只压不抬」的契约）、`test_one_click_is_two_percent_and_a_block_application_is_ten`、`test_the_board_publishes_every_percentage_the_ticket_quotes`（断言 10% 的大宗仍远低于 25% 的持股天花板）。
- **教训**：把一条新的**上限**叠加到一条旧的**下限**上时，必须问一句「这两个方向能相加吗」。`max(旧下限, 新上限)` 这种写法在两条规则方向相反时必然失效，而且失效的方向恰好是最危险的：它把上限放大成下限。

### E19-07 融资新发行的股当日就能卖出，绕开了买入的 T+1 锁定

- **现象**：融资成功后立刻打开交易窗，`sellable` 就等于刚融资买到的全部新股（实测 168,480 股），而同一天用普通买入买到的股 `sellable` 是 0。同一天里「融资买入」比「普通买入」少了一条约束，玩家可以融资后立刻抛掉，把融资当成当日往返的工具。
- **根因**：`commit_finance` 只更新了 `holding["qty"]` 与 `avg_cost`，没有像 `commit_buy` 那样写 `locked_qty` / `locked_ordinal`。资金扣款、股本增发、账单入账都做了，唯独漏了「这批股是今天买的」这一条持仓状态——因为融资走的是自己的一条新路径，而不是复用买入的收尾逻辑。
- **修复**：`commit_finance` 在更新持仓后按 `commit_buy` 的同一套写法记录锁定：同一天内累加 `locked_qty`，换一天则重置为本次股数并把 `locked_ordinal` 设为当日序数。回归：`test_a_financing_grows_the_capital_without_moving_the_quote` 断言融资后 `sellable == 0`（并且断言当日单股报价不动、市值与收购价上抬）。
- **教训**：任何「用钱换资产」的新入口都要在收尾处与既有入口对齐（持仓、锁定、账单、公告、缓存失效），漏掉其中一项不会报错，只会让新入口比旧入口更宽松——而更宽松的那一侧总是会被玩家先找到。


## 第 20 轮（V2.7.7beta，2026-10-16）

### E20-01 单笔直购被「整手」封在 100 万股：占比不到 2% 也被强制转大宗

- **现象**：界面上曼彻斯特城（股本 13.9 亿）的「单笔上限」显示 `100.0万`，点「全部」只能填 1,000,000 股，再多一点就报「单笔股数过大」并要求改用大宗；`2% x 13.9 亿 = 2780 万` 却买不到。反过来，股本 2% 小于 100 万股的俱乐部（例如 100.0 万股本的 `单笔上限 2.0万`）完全正常。用户原话：「超过 100 万股尽管未达到 2% 限制也会被强制要求大宗交易」。
- **根因**：上一轮把「整手」从 `max(整手, 2%)` 改成 `min(整手, 2%)` 只解决了小俱乐部被**抬高**的一侧，没解决大俱乐部被**压低**的一侧：`_order_lot(capital) = min(MAX_SHARES_PER_ORDER 100 万股, MAX_ORDER_SHARE_CAP 25% x 股本)`，只要股本超过 5 千万股，整手就恒等于 100 万股，`min(100 万股, 2% x 股本)` 于是把 2% 的额度削到 100 万股。两个方向其实是同一个错误：**把一个「默认手数」写进了「上限」的表达式**。
- **修复**：`max_direct_shares = max(1, round(股本 x MAX_DIRECT_BUY_RATIO))`，2% 是点击唯一的硬上限；删除 `MAX_ORDER_SHARE_CAP` 与 `_order_lot`，`MAX_SHARES_PER_ORDER`（100 万股）只保留为票据默认整手与「股本为空/非法」时的兜底，不再参与上限计算。`max_block_shares` 保持 `股本 x 10%`。回归：`test_max_order_is_two_percent_of_the_capital_and_never_a_round_lot`（含 `max_shares_per_order(MAX_INITIAL_SHARES) > MAX_SHARES_PER_ORDER` 与 50 次点击仍装得下一个俱乐部的边界）、`test_a_click_past_a_million_shares_is_still_a_plain_buy`（应用层：1,000,001 股直接成交、不进委托队列）。
- **教训**：上限公式里出现任何一个「与股本无关的常数」时，都要回答「这个常数在股本趋于无穷时会发生什么」。100 万股在小股本上是保护，在大股本上就是枷锁，而它当时是被当成「历史点击量」保留下来的，所以只在老玩家的大股本持仓上暴露。

### E20-02 融资后过一天被当成退市结算（以及大宗申请静默消失）

- **现象**：融资成功后过一天，成交记录里出现「退市结算 116550 x £39.81」「退市结算 100000 x £41.76」，刚融资买到的持仓被强制卖回（用户图四）；同时提交的大宗申请没有任何反馈，只是钱被退回来。其他没有融资的持仓也偶尔出现同样的退市结算。
- **根因**：`registry_sync` -> `_settle_missing_holdings` 把「当天目录里没有的持仓」一律按退市结算。而世界俱乐部目录是**异步增量**扫描出来的（`world_club_scanning`，界面显示「正在读取赛程并生成盘口 76127/95230」），`_stock_market_directory` 只返回「已经读到的那些俱乐部」，因此第一次 tick 时大量俱乐部还没进目录——刚融资/买入的持仓正好落在这个窗口里，被读成「这家俱乐部从存档里消失了」。同一处根因还造成第二类症状：`fill_pending_orders` 对 `row is None` 直接撤单，而撤单路径只在有退款时才写公告，于是大宗申请「静默消失」。
- **修复**：缺勤改为**两次可见**——第一次读不到只把当日写进新增的 `state["missing"]` 并在 tick 里回报 `unconfirmed`，只有「缺席首日早于今天」的俱乐部才按最后收盘价结算；扫描进行中整个 tick 以 `confirm_absent=False` 运行（只记不判）。`state["missing"]` 与仓库一同持久化（`unconfirmed` / `missing_forgotten` / `listing_repaired` 都加进落盘条件——第一次记不入库，判定就永远不成立，真退市的持仓会永远卡住）。委托队列共用同一套证据（`watched_club_keys` = 持仓 ∪ 待成交委托），确认后才撤单并写 `order_cancel` 公告（`refund` 为 0 的限价撤单也写），未确认前留队并回报 `unconfirmed`；另外股市侧栏新增常驻委托面板（`stockOrdersPanelHtml`），让「申请已提交 / 已成交 / 已撤回」都能被看见。`SCHEMA_VERSION` 6 → 7（新增 `missing`，`_normalize` 补空值，旧存档不需要迁移）。回归：`test_a_directory_that_is_still_being_read_never_delists_a_lot`、`test_an_application_waits_out_the_reading_and_is_withdrawn_when_proven_gone`、`test_a_financed_lot_survives_a_reading_that_has_not_reached_the_club`、重写后的 `test_registry_sync_settles_a_holding_whose_club_left_the_database` 与 `test_delisting_settles_the_holding_into_the_bank`。
- **教训**：把「不在我这次看到的数据里」当成「已经不存在」，是异步增量数据源上最容易犯的错；这类判定的成本不是 false positive 的金额，而是**玩家刚做过的操作被系统悄悄回滚**。凡是「判死」的路径（退市、撤单、清除）都必须问一句：这条数据是「权威的全量」还是「我恰好读到的部分」？

### E20-03 只有大宗委托、没有持仓的俱乐部，委托永远不会被撤

- **现象**：本轮的「两次可见」改完后自查发现：`_settle_missing_holdings` 只遍历 `state["holdings"]`，因此「只有委托、没有持仓」的俱乐部根本不进 `state["missing"]`；`fill_pending_orders` 的 `_absence_confirmed` 永远读到 0，申请就一直挂在队列里，托管的钱既不会被交割也不会被退回。这类申请在玩家侧表现为「钱少了、什么也没有」。
- **根因**：缺勤证据只跟「持仓」这一种被监视对象绑定，而本轮新增的「委托」是第二种对象；同一个规则没有被应用到第二处。
- **修复**：新增 `watched_club_keys(state)`（持仓 ∪ 待成交委托）与 `_remember_absence` / `_forget_absence`；`_settle_missing_holdings` 按这个并集判定（只有委托的俱乐部也会被记一笔，但不会产生结算），`fill_pending_orders` 在未确认时记录当日、确认后撤单并遗忘。回归：`test_an_application_waits_out_the_reading_and_is_withdrawn_when_proven_gone` 的第一天断言 `unconfirmed == 1` 且 `state["missing"] == {"3": 序数}`，第二天才撤单并退款。
- **教训**：「谁需要被判定」的清单本身就是契约的一部分。本轮引入第二类被监视对象（委托）时，只改了撤单那一步，没改「证据从哪来」，于是判定的输入端漏了一个集合——这类漏洞不会让测试变红，只会让玩家的钱静默卡住，所以补完主修复后要顺着数据流把同一个问题再问一遍。

### E20-04 交易所关闭后重启，英格兰的股价、指数与 K 线全部静止

- **现象**：英格兰交易所关闭后重启，游戏时间过了两天，英格兰的股价、指数（1,228.76 不变）与 K 线都不变化，其他交易所正常。
- **根因**：`entry["listed_ordinal"]` 被写成了**未来的游戏日**（关闭、重开与游戏时钟回拨的组合会留下这种时间戳）。`stock_public` / `price_history` / `index_series` / `nation_index` 都把 `listed = _int(since) or None` 当上市日使用，而 `price_history` 里 `first = max(first, listed)`：当 `listed > ordinal` 时 `first > ordinal`，`days_back` 直接为空；`market_view` 又把 `fresh = listed >= ordinal` 判成「今天刚上市」，于是所有涨跌幅被抹成 0、指数上一日取今日、蜡烛画不出来。表面看就是「这个交易所死了」，重启软件才恢复。
- **修复**：新增 `listing_day(since, ordinal)`——`since <= 0` 或 `since > ordinal` 时返回 `None`（未来的日期不是上市日），上述四处一并改走它，`market_view` 的 `fresh` 改为 `listed is not None and listed >= ordinal`；`registry_sync` 会把越界的 `listed_ordinal` 写回当日、`listed_game_date` 同步，并回报 `listing_repaired`（该计数进入落盘条件，避免每次启动都重算）。回归：`test_a_listing_day_from_the_future_never_freezes_an_exchange`（含 `listing_day` 的边界与「换算回当日之后涨跌幅非 0、K 线 3 根、指数序列收盘价不止一个值」）、`test_an_exchange_listed_in_the_future_trades_again_the_next_game_day`（应用层：复牌前一天英格兰全部 25 家俱乐部次日都换价）。
- **教训**：任何「起始日 / 有效期」字段都要假设它可能落在未来（时钟回拨、存档回档、切换存档），判据写成「`since` 存在就当作已上市」等价于把一整个交易所静音；正确的写法是把它与「今天」比较一次，并且**越界的值要被写回**而不是只在下游兜住——否则同一份坏数据会在每个入口各暴露一次。

## 第 21 轮（V2.7.8beta，2026-10-16）

### E21-01 大宗成交回执引用了同一分支里尚未赋值的 `refund`（UnboundLocalError）

- **现象**：新写的 `fill_pending_orders` 大宗回执块一跑测试就抛 `UnboundLocalError`，整个行情 tick 中断，当日所有委托都不交割。
- **根因**：回执要写「未成交部分的退款」，而 `refund = money(收单总额 − 实际成交额)` 在结算 / 关单那一段才赋值；`receipt()` 调用被放在了 `refund` 赋值之前，于是读到一个还不存在的局部变量。限价分支没暴露这个问题，只是因为它的净额早就装在 `plan` 里。
- **修复**：大宗 `receipt(...)` 移到 `refund` 赋值与 `_close_order` 之后，两个分支的顺序统一为「结算 → 关单 → 写回执」。
- **教训**：回执是「结算的产物」，必须写在结算语句之后；把它当普通日志顺手插在告警旁边，就会绕过赋值顺序。新增写盘字段时先问一句「这个字段在哪一行之后才存在」。

### E21-02 限价成交的契约测试没有推进游戏日，且用 `==` 比较四舍五入后的价格

- **现象**：为新回执写的限价成交测试一开始撮合不出来（队列没有成交、断言拿不到 `price`），把时间推进后价格断言又因为末尾小数差异失败。
- **根因**：两件事叠在一起——`fill_pending_orders` 只处理 `ordinal` 早于今天的委托（T+1），测试直接在同一天调用它，`today <= order["ordinal"]` 分支直接 `continue`；而成交价走 `share_price(...)` → `quote()` 的两位小数四舍五入，手算的期望值天然对不齐。
- **修复**：测试改为先 `trading_quote(...)` 取当日报价，再以 `ordinal + 1` 推进交割，价格断言改用 `pytest.approx`（既锁 T+1，也锁服务端自己的报价口径）。
- **教训**：任何「下一个游戏日才生效」的写入，时间推进本身就是测试步骤；期望值优先取服务端自己的报价函数，而不是在测试里重算一个常数。

### E21-03 饼图补丁的文本锚点被注释里的同名标识符抢走

- **现象**：写「图例按持有人命名」的补丁时，脚本按 `between("function stockPieLabel", ...)` 取到的区间与预期不符，命中断言直接失败。
- **根因**：这个函数上方的注释里也写了 `stockPieLabel` / `stockPieHtml` 这些名字，而本项目的补丁流程没有 `apply_patch`，只能按字面查找、不区分注释与代码。
- **修复**：锚点改成「函数定义行 + 紧随其后的实现首行」的组合定位，并保留 `assert count == 1` 的命中断言。
- **教训**：文本锚点要选「只可能出现在代码里」的字串（`function <name>(`），不要选裸标识符；注释与锚点共用同一份文本时，命中位置必须显式校验。

## 历史条目（回溯整理，来源为 `CHANGELOG.md` 对应版本段落）

| 编号 | 版本 | 现象 | 修复要点 |
| --- | --- | --- | --- |
| E-01 | V2.7.0beta | 自行打包的单个 EXE 进入后按钮点不动、菜单图标丢失 | 桌面宿主与资源定位修复，改为单文件打包脚本产出的成品 |
| E-02 | V2.7.0beta | 设置里提示字体已切换，但界面字体没有变化 | 字体应用链路修复，自定义字体目录与刷新按钮生效 |
| E-03 | V2.7.2beta | 交易所筛选界面勾选一次就弹回最顶端 | `stockRefreshFilterList` 只重绘列表并还原滚动位置与焦点 |
| E-04 | V2.7.3beta | 重启后勾选国家/地区仍生效，但筛选摘要的俱乐部数量显示 0 | `stockFilterPendingStats` 改走 `stockFilterLeagueClubs`，并用 `scope_leagues` 兜底 |
| E-05 | V2.7.3beta | 侧栏交易所标题附近的搜索框与图标超出卡片边界 | `.stock-exchange-rail` / `.stock-rail-list` 约束最小宽度并裁剪横向溢出 |
| E-06 | V2.7.3beta | 行情日期停在最后一次刷新的日期，手动刷新无效，只有重启才跳到最新 | `_stock_market_live_game_date` 跟随游戏时钟；轻量赛果刷新每日调用 `advance_stock_market` |
| E-07 | V2.7.3beta | 主界面 chip 的「已启用俱乐部数量」与筛选界面不一致 | `stockHeroHtml` 改统计整个已启用范围（与筛选界面同一口径） |
| E-08 | V2.7.4beta | 晚上 8 点的胜利当天不体现、赢球日股价反而下跌 | 新闻脉冲按开赛当天全额计入并按日期衰减；重新调参（`FORM_WEIGHT` 0.26、噪声 0.05、摆动 0.005），赢球日必定收涨 |

## 预存在失败（非本轮引入，未处理）

以下 13 条测试在接手时的基线上就失败，已用上份备份工程逐条复现，与本轮改动无关：

`test_account_store`、`test_championship_lifecycle`、`test_championship_odds`、`test_club_policies`、`test_i18n_catalog_contract`、`test_i18n_locale_packs`、`test_league_points_item`、`test_odds_profiles`、`test_owned_club_operations`（2 条）、`test_pending_result_search`、`test_profit_analysis_colors`、`test_refresh_optimization`。

## 第 22 轮（V2.7.8beta，2026-10-16）

### E22-01 部分国家的联赛没有出现在交易所筛选里（丹麦超级联赛、荷兰甲级联赛等）

- **现象**：交易所筛选界面里找不到丹麦超级联赛、荷兰超级联赛（荷甲）等联赛；设置里明明启用了 36 个国家，左侧国家/地区列表却只显示 29 个，两者对不上。
- **根因**：两个原因叠加。其一，筛选界面判定「这个联赛在不在存档里」只用 `output["competition_formats"]`（盘口快照的格式解析结果），凡是解析器暂时答不出的联赛都不进列表；真实存档的 `competitions` 列表里明明列着丹超（id 6）、丹甲（id 7）、荷甲（id 29）等。其二，盘口快照与俱乐部扫描对同一联赛各印一套名字（95 个共享 id 里有 86 个名字不同，例如快照印 `“CampoBet”丹乙联赛`、扫描印 `“CampoBet”丹麦足球乙级联赛`），按旧名写进 `scope` 的联赛在目录里解析不到；`大洋职业联赛` 这个名字在快照与扫描里根本不存在（只有赛果历史里有），7 条无法解析的条目让覆盖国家数比实际能开的交易所多 7 个。
- **修复**：`save_competition_index` 同时读取 `competition_formats` 与 `competitions` 两份扫描；新增 `scope_league_index` 建别名表（同一赛事 id 取最长名作正名，旧名与赛果历史名都进 `aliases`），`canonicalize_scope` 把存下的旧名折到正名；`reconcile_scope` + `apply_scope_repair` 把目录完全解析不到的条目从 `scope` 剪掉并写 `scope_prune` 公告。世界俱乐部目录还通过 `attach_result_competitions` 把赛果历史里的名字并入俱乐部条目，别名表因此覆盖更多历史标签。目录为空或世界扫描进行中时不剪（`confirmed=False`）。
- **回归**：`tests/test_club_stock_market.py::test_scope_labels_fold_onto_the_leagues_the_directory_lists`、`test_reconcile_scope_names_the_leagues_the_directory_cannot_list`、`test_apply_scope_repair_prunes_the_league_and_leaves_a_notice`、`test_save_competition_index_reads_the_plain_competition_scan_too`、`tests/test_stock_market_application.py::test_a_league_that_never_listed_is_pruned_and_reported`、`test_a_scan_still_running_never_prunes_the_scope`、`test_a_stored_scope_folds_onto_the_listed_league_label`、`test_the_filter_reports_the_leagues_it_cannot_list`。

### E22-02 收购后的俱乐部股权没有交给玩家集团，玩家还能继续买入

- **现象**：通过集团模块收购一家俱乐部后，股市里该俱乐部仍然可以正常买入；持股饼图仍显示俱乐部自己 100% 持股（例如博德/格里姆特，持股记录里根本没有一行属于集团）。
- **根因**：收购只写 `acquired_clubs` 文档，`club_stock_market.py` 里没有任何一处引用该文档；买入 / 卖出 / 融资三条路径都不知道这家俱乐部已经被集团收购。饼图的 100% 是前端在 `qty=0` 时把全部股本归给俱乐部的显示兜底，掩盖了「登记册根本没交接」。
- **修复**：新增 `take_over_club`（把全部股本登记到集团名下、`source="takeover"`、撤销该俱乐部全部待成交委托并退回托管金）、`sync_takeovers`（每次开盘时以 `account_acquired_clubs` 为准双向对齐：新增的接管、已出售的收回）、`release_takeover`、`assert_tradable`（买 / 卖 / 融资三路明确报错）；`_decorate` 给 owned 行 `sellable=0` 与 `owned=True`，`_settle_holdings` 跳过 takeover 持仓。应用层 `_stock_market_sync_club_ownership` 在收购成功后立即刷新登记册，`sell_world_club` 在出售时收回；`_settle_stock_order_cash` 把交接时撤销的委托退款入账。前端 owned 行显示「已收购」徽章、交易窗显示说明条并隐藏买卖表单。
- **回归**：`tests/test_club_stock_market.py::test_the_board_hands_a_bought_club_over_and_closes_its_tickets`、`test_a_club_the_group_owns_refuses_buy_sell_and_finance`、`test_the_register_follows_the_owned_clubs_both_ways`、`test_release_takeover_leaves_the_watchlist_too`、`tests/test_stock_market_application.py::test_an_acquired_club_hands_its_register_to_the_group`、`test_selling_a_club_takes_its_register_back_from_the_group`。

### E22-03 融资意愿对全部俱乐部都顶在 90% 以上

- **现象**：几乎每家俱乐部的融资意愿都显示 90% 以上，融资申请几乎没有被拒绝的可能。
- **根因**：`finance_appetite` 里 `gap = abs(price / intrinsic - 1)` 拿**每股价格**与**整家俱乐部估值**比较（两者相差股本数量级），任何报价都会得到 gap≈1.0 的满分偏离，`gap_bonus` 直接吃满，再用 0.45 基础值 + 0.45 加成把意愿顶到 0.97 上限。真实数据复现：1627 家俱乐部 100% ≥ 0.9。
- **修复**：改用 `market_cap`（`stock["market_cap"]`，缺省回退 `price × shares`）与 `intrinsic` 比较；参数重新定为 BASE 0.25 / GAP 0.35 / DEBT 0.35 / SLUMP 0.20 / CAP 0.92 / FLOOR 0.05 / GAP_SCALE 0.40。真实存档复测：min 0.250 / median 0.260 / max 0.289，0 家超过 0.5。
- **回归**：`tests/test_club_stock_market.py::test_a_club_in_the_red_or_far_from_its_appraisal_wants_the_money_more`（改为市值口径并断言 BASE / GAP / CAP 三个锚点）。

### E22-04 交易卡的稳定类名字符串被 owned 标记冲掉（本轮自己引入、打包前拦下）

- **现象**：给已收购俱乐部挂 `is-owned` 类之后，`tests/test_stock_ticket_frontend.py` 失败——它用 `between(ticket, '<section class="stock-ticket-card stock-ticket-form"', "</div>`;")` 这段**整串字面量**当解析锚点，模板里插进 `is-owned` 后锚点再也匹配不到，交易窗的布局断言全部落空。
- **根因**：用「往既有 class 属性里追加一个类」表达「已收购」状态。类列表本身仍然包含 `stock-ticket-form`（CSS 与运行时选择器照常命中），但类属性和的**字面量**变了——凡是靠这串字面量定位模板片段的工具（前端契约测试、文档示例）都会失配。第一遍成品（`EAF09036…`）就是这么打出来的。
- **修复**：改成独立属性契约 `data-stock-owned="1"`，CSS 走 `.stock-ticket-form[data-stock-owned="1"]>...`；`tests/test_stock_ticket_frontend.py` 的锚点保留原字面量并新增 owned 契约断言（`data-stock-owned` 与 `class="stock-owned-note"`）。修好后重建成品，交付哈希 `468D9F0C…`。
- **回归**：`tests/test_stock_ticket_frontend.py`（10 passed，含 owned 契约断言）。

## 第 23 轮（V2.7.9beta，2026-10-16）

### E23-01 「全球」条目被同时算作国家与联赛对，统计翻倍

- **现象**：选中「全球」之后，勾选界面的摘要与统计（已启用国家数、联赛数、俱乐部数）会把同一件事算两遍。
- **根因**：范围里的 `*` 在两步循环里语义不同（第一步只开联赛、第二步开全部俱乐部），而 `stockFilterOptionKeys` / `oddsScopeOptionKeys` 把 `nations` 与 `leagues` 直接拼成勾选键列表，没把「已经用国家条目覆盖整段」这件事折掉。
- **修复**：抽出 `stockScopeOptionKeys(scope, keyOf)`，nations 含 `*` 时把对应的联赛对从键列表里过滤掉；`stockScopeCycleWorld` 保证两步状态互斥（进入第二步时删掉第一步的联赛对，回到第一步时删掉 `nations`）。
- **回归**：`tests/test_stock_market_frontend.py`、`tests/test_stock_scope_display_frontend.py`、`tests/test_odds_scope_custom.py`（全球条目与国家级互斥、集合不重复）。

### E23-02 收购档案的门槛 / 意愿 / 实付三行事实被内联表格覆盖（自己引入、开发中拦下）

- **现象**：世界俱乐部资料页加了 `worldTakeoverFactsHtml` 之后，这三行事实在界面上不出现（既不报错，也不报警）。
- **根因**：`.world-detail-profile dl` 的内容是在渲染尾声用 `dl.innerHTML = ...` 整体重建的，`insertAdjacentHTML` 插在赋值之前，新内容随即被该次赋值覆盖。
- **修复**：把 `profile.querySelector("dl")?.insertAdjacentHTML("beforeend", worldTakeoverFactsHtml(takeover))` 移到 `dl.innerHTML` 赋值之后，并且只在 `takeover && !takeover.owned` 时插入。
- **回归**：`tests/test_stock_market_frontend.py`（收购事实行与加载提示字段）。

### E23-03 owned 契约的既有测试与新行为冲突（判定为行为变更，不是回归）

- **现象**：改完交易路径后，`tests/test_club_stock_market.py` 有 2 条 owned 用例失败（断言 owned 行 `sellable == 0`、三路交易全部拒绝），`tests/test_stock_market_application.py` 同样断言 `sellable == 0`。
- **根因**：本轮把「收购后整本登记册冻结」改成「只拒买入，允许卖回与融资」，旧断言测的是上一轮的契约。
- **修复**：逐条确认失败原因都是契约过期而不是代码回归（买入仍然拒绝、卖出受 51% 保留线约束、融资跳过意愿抽签），随后把断言改为 `keep_shares` 与新文案，并补 7 条新用例覆盖新规则（保留线、实付抵扣、连涨计数、意愿、门槛、全球范围）。
- **回归**：`tests/test_club_stock_market.py` + `tests/test_stock_market_application.py` **176 passed**。

### E23-04 备份基线的既有失败（非本轮引入，逐条复现）

- **现象**：广域回归 `py -X utf8 -m pytest tests -k "stock or world_club or acquisition or owned_club"` 有 2 条失败：`tests/test_owned_club_operations.py::test_acquisition_degrades_native_failures_but_rolls_back_persistence_failures` 与 `::test_concurrent_duplicate_acquisition_charges_once_and_replays_result`（`AttributeError: 'types.SimpleNamespace' object has no attribute '_stock_market_factors'`）。
- **定位**：把这两条用例放到本轮动手前的备份工程（`_fmodd_backups\FMODD-V2.7.8beta-2-20261016\project`）里跑，结果相同；同一备份的全量基线为 13 failed / 3,510 passed。
- **处理**：属既有基线缺陷，本轮不修（不处理无关缺陷），仅在此记录。

### E23-05 语言包契约的既有失败（非本轮引入）

- **现象**：`tests/test_i18n_locale_packs.py::test_shop_item_metadata_is_complete_in_every_locale` 与 `tests/test_i18n_catalog_contract.py::test_every_loaded_domain_catalog_has_locale_and_parameter_parity` 失败。
- **定位**：前者按 `src/docs/I18N_ARCHITECTURE.md` 找文档，而仓库里实际只有 `docs/I18N_ARCHITECTURE.md`（`Test-Path src\docs\I18N_ARCHITECTURE.md` 为 `False`）；后者断言域目录声明的 locale 集合等于旧的三语言集，而实际包含十一种语言。两者都是本轮之前就在的失败。
- **处理**：本轮不修；本轮新增的 `stock.*` / `world.acquisition.*` 键用聚焦用例（新键无英文泄露、占位符一致、语言齐全）验证，4 passed。
## 第 24 轮（V2.7.9beta，2026-10-16）

### E24-01 点一次「全球」报数与实际启用的交易所不是一个量级

- **现象**：交易所筛选面板勾选一次「全球」后，行内提示是“本存档 5405 家”、摘要显示已选 2278 个联赛，但实际启用的却是整座目录 36952 家俱乐部；面板与实际说的不是一回事，玩家也无从判断到底开了多少。
- **根因**：旧模型把「全球」存成一个 `*` 代码。`GET /api/stock/scope` 的第一段（面板计数）按“存档里真正有联赛的俱乐部”算，后端 `in_scope` / `scope_rows` 对同一个 `*` 却按 `every_league` 把整座目录上市，两边各自解释同一个代码，注定对不上。同时前端只在 `*` 与「无」之间切换，下方国家行读的是真实条目，所以「全球」与各国家行也谈不上联动。
- **修复**：改存真实条目。`stockScopeWorldNext` 给出下一态，`stockFilterWorldApply` / `oddsScopeWorldApply` 把该态展开成每个列出国家/地区的联赛条目（第一步）或国家条目（第二步），`stockFilterEnsureTables` / `oddsScopeEnsureTables` 用一次 `GET /api/stock/scope/leagues?nation=*` 读回全量联赛表；面板计数、摘要与后端统计从此读同一份名单，国家行也自然同步。旧 `*` 条目由 `stockFilterAdoptWorld` / `oddsScopeAdoptWorld` 在打开面板时展开（只进待保存状态），后端语义保持不变。
- **回归**：`tests/test_stock_market_frontend.py::test_the_worldwide_row_writes_real_nations_and_leagues`、`tests/test_stock_market_application.py::test_the_whole_directory_answers_in_one_read_for_the_worldwide_row`、`tests/test_odds_scope_custom.py::test_the_worldwide_row_reuses_the_exchange_picker_machinery`。

### E24-02 `fixture_in_custom_scope` 引用了没有导入的 `GLOBAL_SCOPE`

- **现象**：`tests/test_odds_scope_custom.py` 有 5 条用例失败，报 `NameError: name 'GLOBAL_SCOPE' is not defined`；自定义盘口范围的过滤函数一走到全球分支就抛异常。
- **根因**：上一轮把全球条目接进 `preview_cup_odds.fixture_in_custom_scope` 时，只用了名字没有补 `import`（上一轮的成品里这条路径只在玩家真的存过全球范围时才会被走到，静态测试没覆盖到）。
- **修复**：在 `src/tools/preview_cup_odds.py` 的既有 `from tools.database_index …` 之前补 `from tools.club_stock_market import GLOBAL_SCOPE`；修好后该文件 23 passed。
- **回归**：`tests/test_odds_scope_custom.py`（由 5 failed / 18 passed 变 23 passed）。

### E24-03 新增文案 `stock.filter.remove_world_confirm` 起初漏进语言包（开发中拦下）

- **现象**：`saveStockScope` 在删除确认时按 `diff.world` 选 `stock.filter.remove_world_confirm`，但该键当时一个语言包都没有：运行时会回退成裸键名并把参数 `{nations}` / `{leagues}` 原样显示。
- **根因**：前端先改、文案后补，而 `i18n.stocks.js` 的值是 `[en, zh-CN, ko]` 三元组数组，与八个单语文件的单串形态不同，补键时容易只补一半。
- **修复**：九个文件（`i18n.stocks.js` + `i18n.tw.js` / `de` / `es` / `fr` / `ru` / `ja` / `pt-BR` / `pt-PT`）按各自形态补齐，`test_i18n_locale_packs.py` 的键齐全与占位符一致契约随即通过。
- **回归**：`tests/test_i18n_catalog_contract.py` + `tests/test_i18n_locale_packs.py`（新增键相关四项契约全绿）。

### E24-04 三元组文件里插入成裸字符串导致语法错误（自己引入、开发中拦下）

- **现象**：`node --check src\web\i18n.stocks.js` 报 `SyntaxError: Unexpected string`，整包语言目录都加载不了。
- **根因**：批量插键时统一按单串写，只有 `i18n.stocks.js` 的值必须是三元素数组，于是写出了 `"key": "en…", "zh…", "ko…",`。
- **修复**：识别该文件的形态，把值包成 `[…]` 再写回；复查 `node --check` 对九个语言包全部通过。
- **回归**：`node --check`（九个语言包）+ `tests/test_i18n_catalog_contract.py`。

### E24-05 既有失败（非本轮引入，逐条复现）

- **现象**：`tests/test_owned_club_operations.py::test_acquisition_degrades_native_failures_but_rolls_back_persistence_failures` 与 `::test_concurrent_duplicate_acquisition_charges_once_and_replays_result` 失败（`AttributeError: 'types.SimpleNamespace' object has no attribute '_stock_market_factors'`）；`tests/test_i18n_locale_packs.py::test_shop_item_metadata_is_complete_in_every_locale` 与 `tests/test_i18n_catalog_contract.py::test_every_loaded_domain_catalog_has_locale_and_parameter_parity` 也失败。
- **定位**：前者在上一轮（第 23 轮）已逐条复现并记录为 E23-04；后者分别是“按 `src/docs/I18N_ARCHITECTURE.md` 找文档但仓库里只有 `docs/I18N_ARCHITECTURE.md`”与“断言域目录只声明三种语言”，与 E23-05 同一条。
- **处理**：本轮不修（不处理无关缺陷），仅在此记录；本轮广域回归的 2 failed 与备份基线完全一致。
- **全量复核**：`py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3,521 passed / 13 failed / 239 subtests passed**，13 条失败与本文档「预存在失败（非本轮引入，未处理）」清单逐条同名（`test_account_store`、`test_championship_lifecycle`、`test_championship_odds`、`test_club_policies`、`test_i18n_catalog_contract`、`test_i18n_locale_packs`、`test_league_points_item`、`test_odds_profiles`、`test_owned_club_operations` 2 条、`test_pending_result_search`、`test_profit_analysis_colors`、`test_refresh_optimization`），本轮没有新增失败；上一轮引入的 `tests/test_odds_scope_custom.py` 5 条失败被本轮修掉后已不在清单里。

## 第 25 轮（V2.7.9beta，2026-10-16）

### E25-01 集团全资俱乐部卖出去就买不回来

- **现象**：第 23 轮把 `assert_tradable` 收窄成「owned 只拒买入」之后，玩家在交易界面把股份卖回俱乐部，再想买回来一律被拒绝；交易窗里也没有任何回收入口，只能把整个俱乐部在集团模块里卖掉。
- **根因**：owned 分支当时只补了卖出与融资两条路，买入被当成「与市场交易」整体拒绝；即使放行，买入额度也套着 `MAX_BUY_STAKE` 25% 与「当日股本 − 我的持仓」这两条属于市场买入的口径，算出来可买数量也是错的。
- **修复**：`assert_tradable` 放行 owned 的买入并把语义定为**回收**：`buy_plan` 的 owned 分支把可回收量限在俱乐部当前自持 `capital − held`，`_decorate` 用 `buyback_room` 报给前端（`buy_room` 同值），`fill_pending_orders` 的 owned 交割同口径（`room = max(0, capital − held)`）；`commit_buy` 递减 `takeover_sold`、`revert_buy` 回退，`sync_takeovers` 因此不会把回收过的股份再交接一次；前端看板行、交易窗与限制条改说回收。
- **回归**：`tests/test_club_stock_market.py::test_a_club_the_group_owns_trades_its_own_book_only`、`::test_a_block_recovery_is_delivered_out_of_the_clubs_own_book`、`tests/test_stock_market_application.py::test_an_acquired_club_hands_its_register_to_the_group`。

### E25-02 第 23 轮的只读隐藏规则把回收表单一起关掉了

- **现象**：后端已放行回收，但 owned 俱乐部的交易窗依旧只有顶部「集团持股」提示：买卖切换、股数输入、报价拆解与确认按钮全不可见（第 23 轮的成品截图就是这个形态），玩家看不到任何可操作控件，只能以为「功能没做」。
- **根因**：`src/web/app.css` 里为第 23 轮的「owned 窗只读」保留了一整块 `form[data-stock-owned="1"] > .stock-side-toggle / .stock-ticket-order-qty / .stock-quote / .stock-ticket-order-actions { display:none; }`；该标记现在同时出现在可交易的回收窗上，于是新功能被旧规则整段隐藏。
- **修复**：删掉整块规则（替换为说明注释），owned 交易窗恢复完整下单条；回执文案改由 `quote.stock.owned` 判定。
- **回归**：`tests/test_stock_ticket_frontend.py::test_an_owned_club_quotes_a_recovery_instead_of_a_market_buy`、`::test_the_ticket_of_a_group_club_names_both_moves`、`tests/test_stock_board_layout_frontend.py::test_a_group_club_keeps_both_moves_in_the_row`。

### E25-03 回执文案内联进 `uiText` 会打破既有断言（开发中拦下）

- **现象**：把「大宗回收 / 已回收」写进 `submitStockTicket` 的 toast 时，`tests/test_stock_order_frontend.py::test_an_application_is_the_same_order_with_a_kind_on_it` 失败，报找不到字面量 `uiText("stock.toast.block"`。
- **根因**：该契约按字面量检查前端是否还走既有的两条回执分支（`stock.toast.block` / `stock.toast.bought`）；把三态选择写进 `uiText(a ? "x" : "y", …)` 之后，这两个字面量在源码里不再出现。
- **修复**：保留原有的嵌套三元（`recovered ? uiText("stock.owned.toast_block", …) : uiText("stock.toast.block", …)`），新键只在 owned 分支上追加；该文件随之恢复全绿。
- **回归**：`tests/test_stock_order_frontend.py`。

### E25-04 既有失败（非本轮引入，逐条复现）

- **现象**：全量 `py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3,527 passed / 13 failed / 239 subtests passed**，13 条失败与本文档「预存在失败（非本轮引入，未处理）」清单逐条同名；广域 `-k "stock or world_club or acquisition or owned_club"` 的 2 failed 也是同一批（`tests/test_owned_club_operations.py` 的 `_stock_market_factors`）。
- **处理**：本轮不修（不处理无关缺陷）。本轮新增 6 条用例全部通过，基线 3,521 → 3,527 的差额即这 6 条，没有新增失败。

## 第 26 轮（V2.7.9beta，2026-10-16）

### E26-01 「只看持仓」重画国家列表后，交易所行点击全部失效

- **现象**：勾选左侧「只看持仓」后列表正确收窄到有持仓的交易所，但此时点任何国家/地区都跳不过去；关闭「只看持仓」也一样。只有点一次「刷新行情」让整块看板重绘，点击才恢复。
- **根因**：`src/web/app.js` 的 `#stock-nation-holdings` change 与 `#stock-nation-search` input 都只调用 `stockRefreshNationList(root)`，而该函数用 `list.innerHTML = stockNationRowsHtml(...)` 整段重画列表；`[data-stock-nation]` 的 click 监听只在 `bindStockBoard(root)` 首次渲染时挂过，重画后新按钮是「裸」的。刷新行情之所以能修好，是因为它走 `renderStockMarket` → `bindStockBoard`。
- **修复**：把行绑定抽成 `bindStockNationRows(root)`，`stockRefreshNationList` 在写完 innerHTML 后调用它；`bindStockBoard` 里原来那段内联绑定替换成同一个函数调用，避免整板监听被重复注册。
- **回归**：`tests/test_stock_market_frontend.py::test_the_exchange_rail_rebinds_its_rows_after_a_repaint`。

### E26-02 用户存档里的 1.5 京并非代码初始值（先定位再决定不动手）

- **现象**：用户报告「银行里有 1.5 京的额度」，并希望软件初始银行不给钱、只保留 1 万现金。
- **定位**：`src/tools/club_economy.py::_new_state` 的 `general_balance` 一直是 `0.0`，钱包 `betting_account.INITIAL_BALANCE` 是 `10000.0`，代码里没有 1.5 京的初始来源。用户存档（`Documents\FMODD\saves\<scope>.fmodd`）里 `economy.general_balance = 1.4999962789127684e+16`，对应的是一笔 2026-10-15T19:52:40 的 `refund_bug_liquidation` **+1.5e16** 流水；该字符串在当前代码库里已经不存在，是旧版本或外部写入留下的退款。
- **处理**：本轮不改用户存档、不加隐式扣减（账户真值不能静默改动），只在 `CHANGELOG.md` 与本节写清来源，并把「按需发钱」做成显式的 CDK 兑换入口。若用户需要清零，应作为单独确认的功能实现。
- **回归**：无需代码回归；相关记录写入 `CHANGELOG.md` 第 26 轮小节。

### E26-03 既有失败（非本轮引入，逐条复现）

- **现象**：本轮广域 `py -X utf8 -m pytest tests -q -p no:cacheprovider -k "stock or cdk or account or i18n or settings or money or bank"` → **626 passed / 3 failed**；失败为 `tests/test_account_store.py::AccountStoreTests::test_clear_cache_preserves_result_history_and_pending_snapshot`、`tests/test_i18n_catalog_contract.py::test_every_loaded_domain_catalog_has_locale_and_parameter_parity`、`tests/test_i18n_locale_packs.py::test_shop_item_metadata_is_complete_in_every_locale`。
- **定位**：三条都在本文档「预存在失败（非本轮引入，未处理）」清单里（`src/docs/I18N_ARCHITECTURE.md` 路径假设、域目录只声明三种语言的旧断言、缓存清理的历史断言）。
- **处理**：本轮不修（不处理无关缺陷），仅记录；本轮新增用例全部通过，没有新增失败。

## 第 27 轮（V2.8.0beta，2026-10-17）

### E27-01 `showPage` 里的 `stockPage` 越出块作用域，切页即抛 ReferenceError

- **现象**：股市改成四页分组后，只要调用 `showPage(…)` 让侧栏渲染块真正执行一次，页面就会抛 `ReferenceError: stockPage is not defined`，导航、行情加载与图标渲染全部中断（`node --check` 语法检查通过，静态检查看不出来）。
- **根因**：`const stockPage = ["stocks", "stock-holdings", "stock-trades", "stock-notices"].includes(page);` 被写在 `if (app.navigationRenderSignature !== navigationSignature) { … }` 块内部，而驱动行情加载的 `if (stockPage) { … }` 在块**外面**。`const` / `let` 是块级作用域，块内声明对外不可见；只有导航签名未变化（块被跳过）时才不会立刻报错，因此问题极易漏过。
- **修复**：把声明提到 `const navigationSignature=…` 之后、导航块之前，作为 `showPage` 的函数作用域变量；块内不再重复声明。`tests/test_stock_workspaces_frontend.py::test_show_page_declares_the_stock_group_flag_once_in_function_scope` 锁住「只声明一次、且在导航块与 `if (stockPage)` 之前」，避免以后被挪回块内。
- **回归**：`tests/test_stock_workspaces_frontend.py`（9 passed）、`tests/test_announcements_frontend.py`（9 passed）、`tests/test_shell_frontend_optimization.py`、`tests/test_home_desktop.py`、`tests/test_i18n_frontend.py`、`tests/test_existing_page_hierarchy.py`（合计 73 passed）。

### E27-02 侧栏分组单测缺少 `stocks` 元素，新增分组后直接崩溃

- **现象**：`tests/test_shell_frontend_optimization.py::test_sidebar_group_open_state_keeps_only_the_latest_group_expanded` 在加入 `stocks` 分组后失败——node runner 里 `for (const id of ["world", "facilities", "club", "relations"])` 只造了四个分组的假元素，而 `SIDEBAR_GROUP_IDS` 现在会遍历到 `stocks`，`$("#stocks-toggle")` 返回 `undefined`。
- **根因**：测试夹具写死了分组清单，与 `SIDEBAR_GROUP_IDS` 的真实内容脱钩；这是夹具跟随代码的问题，不是产品缺陷。
- **修复**：元素数组补上 `"stocks"`，并把关闭态断言循环改成 `("world", "club", "relations", "stocks")`，让新分组也参与「只展开最后一个」的验证。
- **回归**：`tests/test_shell_frontend_optimization.py` 全绿。

### E27-03 深色主题护栏把新写的 `background:#ffffff14` 当成硬编码白底

- **现象**：新增深色覆盖后，`tests/test_dark_mode_frontend.py` 的 `test_betting_market_interaction_states_stay_dark` 与 `test_purchase_confirmation_breakdown_stays_dark` 两条由绿转红。
- **根因**：两条用例把 `dark-theme.css` 从某个注释切片之后的部分做 `re.search(r"background\s*:\s*#fff", …)`，本意是禁止硬编码白色背景；新加的 `.stock-workspace-filters button:hover { background:#ffffff14; }` 虽然只是 8% 白的半透明叠色，但前缀正好命中 `#fff`。
- **修复**：把这处叠色改写成 `rgba(255,255,255,.08)`，语义不变、也不再落进护栏正则；没有去改测试的判定口径。
- **回归**：`tests/test_dark_mode_frontend.py` → 9 passed。

### E27-04 既有失败（非本轮引入，逐条复现）

- **现象**：本轮全量 `py -X utf8 -m pytest tests -q -p no:cacheprovider` 的失败清单与本文件「预存在失败（非本轮引入，未处理）」逐条同名（`test_account_store`、`test_championship_lifecycle`、`test_championship_odds`、`test_club_policies`、`test_i18n_catalog_contract`、`test_i18n_locale_packs`、`test_league_points_item`、`test_odds_profiles`、`test_owned_club_operations` ×2、`test_pending_result_search`、`test_profit_analysis_colors`、`test_refresh_optimization`）。
- **处理**：本轮不修（不处理无关缺陷），仅记录；本轮新增与触及的用例全部通过，没有新增失败。

## 第 28 轮（V2.8.0beta，2026-10-17）

### E28-01 启动行排在公告板常量之前：TDZ ReferenceError 让整段模块级初始化静默中止

- **现象**：未连接存档打开软件时，首页各功能磁贴与顶栏按钮只剩色块、图标全不显示；公告、邮件、设置等顶栏按钮点击无反应；连接存档后点开股市，行情页永远停在「正在读取俱乐部行情…」。
- **根因**：第 27 轮把「股市工作区 + 公告板」约 430 行整段插在启动行（`initializeCustomSelects(); bindEvents(); …`）之后，而 `bindEvents()` 内部（第 30386 行附近）就会调用 `bindAnnouncementBoard()` → `renderAnnouncementBadge()` → `announcementUnread()` → `announcementEntries()`，沿途读取 `ANNOUNCEMENT_BOARD` 等三个 `const`。脚本自上而下求值时启动行先执行，这些 `const` 仍在暂时性死区，抛 `ReferenceError: Cannot access 'ANNOUNCEMENT_BOARD' before initialization`；此后启动行以下的所有顶层语句（`bootstrapState()` / `renderIcons()` / `showPage("home")`、股市常量 18 个、公告板本身）永远不再执行，`bindEvents()` 后半段的监听器（邮件、设置、钱包等）也一起丢掉。`node --check` 只查语法，当时的静态测试未覆盖启动顺序，因此第 27 轮 3552 条测试全绿也没拦住。
- **修复**：把启动段 4 行整体移到 `src/web/app.js` 末尾作为最后一条语句，并加「Boot 必须是文件最后一条语句」注释；顶层 `const/let/class` 一律先于启动行求值。
- **回归**：新增 `tests/test_app_boot_order.py`（3 条）；聚焦 11 个前端契约文件 245 passed；全量 3555 passed / 13 failed（与预存在清单逐条同名，无新增失败）。

## 第 30 轮（V2.8.0beta，2026-10-17）

### E30-01 游戏内过了几天，几百个已勾选联赛被判「不在当前存档」并从交易所里删除

- **现象**：勾选 52 个国家/地区、655 个联赛、17,671 家俱乐部后，游戏内推进几天，市场公告出现「635 个已勾选联赛不在当前存档中：无法开盘，已从交易所筛选中移除」（更早还有一条 777 个），左栏只剩 6 个交易所；筛选摘要仍显示 655 / 17,671，刷新俱乐部资料不恢复。
- **根因**：`_stock_market_tick` 把**当次读到的目录**当作存档的权威清单，而这份目录可能是当天赛程窗口（`build_world_clubs(output)` 只列今天开赛的联赛）或盘口自定义范围收窄后的一小片。旧 `apply_scope_repair` 直接把这些联赛**从 `state.scope` 删除**并写 `scope_prune` 公告，删除一旦落盘就无法自愈。存档内可复现：`scope.leagues` 从 655 条缩到 20 条，而公告点名的 635 条在原生世界缓存（2,264 个联赛对）**全部存在**，即 635/635 都是误删。
- **修复**：① `scope_league_index` 报 `world`（目录含 `source=native_scan` 行）；② `reconcile_scope(..., authoritative=…)` 在非世界目录下只报告不裁决；③ `apply_scope_repair` 改为**暂存**（写 `state.scope_suspended` + `scope_suspend` 公告，只在集合变化时写），世界目录重新列出时解冻（`scope_resume`），条目永不因目录而删除；④ 新增一次性 `restore_pruned_scope`，从最新的 `scope_prune` 公告把还能列出的联赛勾回 `state.scope`（写 `scope_restore`，`scope_pruned_restored` 防重复）；⑤ `registry_sync(confirm_absent=authoritative, ignore=parked_clubs(state))`——暂存交易所的俱乐部不记失踪、不结算退市。
- **回归**：`tests/test_club_stock_market.py::test_a_window_directory_reports_the_leagues_it_cannot_list`、`test_a_world_directory_parks_the_league_it_cannot_list_and_releases_it`、`test_a_league_deleted_by_an_earlier_build_comes_back_on_the_world_read`、`test_a_parked_exchange_keeps_its_lots_out_of_the_delisting_read`；`tests/test_stock_market_application.py::test_a_league_that_never_listed_is_parked_and_reported`、`test_a_league_the_world_directory_lists_again_resumes`、`test_a_scan_still_running_never_parks_the_scope`、`test_a_fixture_window_never_narrows_a_wide_scope`、`test_a_scope_pruned_by_a_window_comes_back_on_the_world_read`。
- **真实数据核对（只读）**：用户存档 + 原生世界缓存在内存中试跑 → 找回 635 条（20 → 655 联赛），11 条青年/预备联赛连世界目录也列不出而转入暂存，最终开盘 644 个联赛 / 17,511 家俱乐部 / 51 个国家/地区。

### E30-02 tick 里 `result` 先于赋值被使用（本轮内部缺陷，未进入交付）

- **现象**：改成 park 语义后聚焦测试一次性 49 failed / 175 passed，`test_stock_market_application.py` 几乎全挂。
- **根因**：把 `result["scope_suspended"] = …` 等四行写在了 `result = stock_market.registry_sync(...)` **之前**（`UnboundLocalError`），同时残留了旧版的 `result_prune` 两行引用（该变量在新分支里已不存在）。
- **修复**：把 scope 结果赋值移到 `registry_sync` 之后，删除 `scope_pruned` / `scope_prune_notice` 两行残留；`parked_clubs` 作为 `ignore` 的计算插在 `registry_sync` 之前。
- **回归**：聚焦套件 230 passed（0 failed）。

### E30-03 一次性恢复的机会被任何一次早于剪枝的开盘花掉

- **现象**：新增的 `test_a_scope_pruned_by_a_window_comes_back_on_the_world_read` 失败——世界目录明明列出了公告点名的联赛，`scope` 却没有变化，且 `state.scope_pruned_restored` 已被置 1。
- **根因**：`restore_pruned_scope` 在「找不到 `scope_prune` 公告」与「公告命名但目录列不出」两种情况下都写 `scope_pruned_restored = 1`。用户只要在旧版剪枝**之前**用新版打开过一次存档，这次修复机会就永久失效；模块级测试因为是在同一份状态上顺序调用而没暴露。
- **修复**：只有真正把联赛勾回来时才落标记并写公告，其余情况保持机会开放（每 tick 多扫一次公告，成本可忽略）；顺带把「目录不是世界数据库时不消费机会」的早退保留。
- **回归**：`tests/test_club_stock_market.py::test_a_league_deleted_by_an_earlier_build_comes_back_on_the_world_read`（含 `authoritative=False` 不消费断言）与 `tests/test_stock_market_application.py::test_a_scope_pruned_by_a_window_comes_back_on_the_world_read`。

## 第 29 轮（V2.8.0beta，2026-10-17）

### E29-01 公告文案补丁丢掉共用 announce.* 键

- **现象**：三条新公告与署名写入后，`tests/test_announcements_frontend.py::test_announcement_copy_resolves_in_every_locale` 报 `AssertionError: en-GB is missing announce.pinned`；对照语言包仍未解析出 `announce.pinned` / `announce.expand` 等键。
- **根因**：补丁把「`announce.author` 到下一个锚点」整段当成可替换区，但该段里除了发布者与四条旧版条目，还夹着 `announce.title` / `subtitle` / `pinned` / `expand` / `collapse` / `empty` / `unread` 七个共用键；整段覆盖等于把它们一并删除，`uiText("announce.pinned")` 只能回退键名。
- **修复**：改为**保留式重建**——先按 `announce.entry.stocks.body` 所在行确定旧区尾，再逐键把共用键的值原样抄进新块，只替换发布者、删除两条旧条目、插入三条新条目；随后用「旧区必须含 7 个共用键」的断言守住这条边界。
- **回归**：`tests/test_announcements_frontend.py` 9 条全绿，`tests/test_i18n_frontend.py` 全绿。

### E29-02 锚点 `top.settings` 落在公告区之外

- **现象**：第二次补丁虽然通过了语法检查，但语言包内的公告区被截断，`"ko-KR": {` 之类的标题在后续文件里被吞掉，脚本报 `AssertionError: ko-KR`；`i18n.static.js` 里出现韩文混进 zh-CN 段。
- **根因**：补丁以 `top.settings` 作为公告区结束锚点，但各语言包键序不一致（zh-CN / ko-KR 的 `top.*` 排在 `announce.*` 之前，en-GB 位于其后），而且同一文件里 `"ko-KR": {` 既出现在消息对象里、也出现在结尾 `legacy` 字面量里；按「第一个匹配」定位就会切在错误位置，并把后续语言块的头一起剪掉。
- **修复**：停止依赖 `top.settings`，改为「公告段首行（`announce.title` 所在行）→ 旧条目末行（`announce.entry.stocks.body` 所在行）」；static 多语文件按出现次序取第 1/2/3 段，其余语言包各取第 1 段，并断言旧区含全部共用键。改错后先从未污染的备份副本 `_fmodd_backups\FMODD-V2.8.0beta-2-20261017` 恢复，再重新落补丁。
- **回归**：`node --check` 覆盖 10 份改动文件；`tests/test_announcements_frontend.py`、`tests/test_i18n_frontend.py`、`tests/test_app_boot_order.py` 全绿；全量 3553 passed / 15 failed，15 条逐条同名于预存在清单（本轮新增的两条环境性失败在备份副本中同样失败）。

### E29-03 预存在失败清单变动说明

- **现象**：全量测试由第 28 轮的 13 条失败变为 15 条。
- **根因**：新增两条环境性失败——`tests/test_i18n_locale_packs.py::test_shop_item_metadata_is_complete_in_every_locale` 依赖 `src/docs/I18N_ARCHITECTURE.md`（该文件在公开源码树中不存在，报 `FileNotFoundError`），`tests/test_i18n_catalog_contract.py::test_every_loaded_domain_catalog_has_locale_and_parameter_parity` 在仓库目录下只加载到三个内嵌语块（`en-GB` / `zh-CN` / `ko-KR`），与期望的 11 语言集合不符。两者都在动手前的备份副本中复现，与第 29 轮改动无关。
- **处理**：登记为已知环境问题，不在本轮修复；后续若要消除，需要么补齐 `src/docs/I18N_ARCHITECTURE.md`，要么让该契约在公开源码树下跳过。

## 第 31 轮（V2.8.0beta，2026-10-17）

### E31-01 全局替换把 6 处 Windows 路径一起改名成 FMEDD

- **现象**：首轮按“所有 `FMODD` → `FMEDD`”做批量替换后，`fmodd_desktop.py` 与 `WebViewHost.cs` 里的日志目录、窗口状态文件目录、WebView2 用户数据目录，以及 `app_paths.py` 的 `Documents\FMODD` 都变成了 FMEDD。这三个目录正是存档、窗口位置/大小与自定义字体的落点。
- **根因**：`FMODD` 在本工程里同时是品牌名与路径名，纯字符串替换无法区分。若带着这版改动发布，用户升级后程序会去 `Documents\FMEDD\saves` 找存档（空目录）、重新创建 WebView2 用户数据并丢掉窗口状态，等同“存档与字体消失”。
- **修复**：按“品牌名才改、路径/文件名/协议名不改”的口径逐条复核全部替换点，回滚 6 处路径（`fmodd_desktop.py` ×2、`WebViewHost.cs` ×3、`app_paths.py` ×1），并把这些名字写进本轮开发日志的保留清单；复核后 `Documents\FMODD`、`%LOCALAPPDATA%\FMODD`、`FMODD-Config`、`FMODD-WebView2-*`、`FMODD-Desktop`、`FMODD.WebViewHost.exe`、`*.fmodd` 全部维持原样（可用 `rg "FMODD" src/fmodd_desktop.py src/tools/app_paths.py` 逐条比对）。
- **回归**：`tests/test_desktop_runtime_parity.py`、`tests/test_account_store.py` 相关用例（存档目录解析）与全量套件均与预存在失败清单一致，无新增失败。

### E31-02 公告补丁首版按“一个文件两种字面量”写死，在三语合并文件上必然中止

- **现象**：第一版公告改写脚本对每个语言包直接 `re.subn` 并断言“命中 2 处”（标题 + 正文），运行到 `i18n.static.js` 时断言失败——该文件里同时住着 en-GB / zh-CN / ko-KR 三种语言，`announce.entry.v280_launch.title|body` 共 6 份字面量。
- **根因**：脚本把“语言 = 文件”当成了前提，而 `i18n.static.js` 是多语合并文件，其余语言包才是单语文件。断言在写盘之前触发，因此没有污染任何文件。
- **修复**：改成按“字面量之前最近的 locale 头”（`"en-GB": {`、`"zh-CN": {` …）判定该条属于哪种语言，再逐条替换，并在写盘后断言“本次覆盖的语言集合等于该文件应有的语言集合”；同时对 `i18n.static.js` 用整体切分（先取全部命中、再按位置切片重组）而不是多次 `re.subn`，避免匹配位置在替换过程中漂移。
- **回归**：`tests/test_announcements_frontend.py`（含逐语言解析三条公告标题与正文）→ 9 passed；`tests/test_i18n_frontend.py`、`tests/test_i18n_catalog_contract.py` 等 9 个契约文件 → **242 passed**。

### E31-03 预存在失败复核（非本轮引入）

- **现象**：本轮全量 `py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3560 passed / 15 failed / 239 subtests passed**。
- **处理**：15 条与第 30 轮失败清单逐条同名（`test_account_store`、`test_championship_lifecycle`、`test_championship_odds`、`test_club_policies`、`test_i18n_catalog_contract`、`test_i18n_locale_packs` ×3、`test_league_points_item`、`test_odds_profiles`、`test_owned_club_operations` ×2、`test_pending_result_search`、`test_profit_analysis_colors`、`test_refresh_optimization`），本轮新增的 1 条 CDK 别名测试计入 passed，未新增失败；这些历史失败仍不在本轮范围内。

### E31-04 三条公告的免责声明句仍写着旧名（打包后复核抓到）

- **现象**：第一次打包完成后，用「独立词 `FMODD`（排除 Windows 路径、`fmodd.com` 域名、`FMODDI18n` / `X-FMODD-*` 等标识符）」的口径重扫 `src/`，在公告正文里抓到 **9 处漏改**：面向玩家、说明「FMODD 是面向 Football Manager 的非官方辅助工具，与 Sports Interactive 及 SEGA 无隶属或合作关系」的免责声明句，在中文简繁、英、日、韩、德、西、法、俄九种语言里仍是旧名（pt-BR / pt-PT 已是新名，所以首轮品牌替换时没有被列为「品牌串」）。
- **根因**：首轮替换以「`FMODD` 作为独立词出现且不在保护清单语境里」为口径，但这句免责声明里有句子级上下文（`\n` 之后紧跟品牌名），而一处命中还带着韩文助词 `는`，被 `\w` 边界规则挡掉；人工确认清单只覆盖到界面标题与提示，漏掉了公告正文中段的这一句。
- **修复**：逐语言把该句的旧名改为 FMEDD（七份语言包 + `i18n.static.js` 三语块共 9 处），`node --check` 全部通过，随后**重新打包**并在包内复核 `i18n.static.js` 三语块的免责声明已为新名；EXE 与 source-runtime 包哈希随之为最终值（见开发日志第 31 轮「交付与打包」）。
- **回归**：`test_announcements_frontend + test_i18n_frontend + test_i18n_desktop_host + test_i18n_shell_dynamic` → **34 passed**；重新打包后包内 112 个 `web/`、`assets/`、`desktop_host/` 资源条目与仓库源文件逐字节一致。
- **教训**：品牌改名不能只扫「独立词」——句子中段的品牌名、带 Unicode 边界的语言（韩文助词、日文助词）都要单独覆盖；交付前应当「打一次包、再用另一套正则扫一遍、必要时重打」。
# E72-01 子女试训通过被误显示为已进入 FM 青训

- **现象**：试训通过后子女记录写入 `training`，界面把它当成已在青训，后续原生投放失败时玩家仍误以为孩子已经进入 FM。
- **根因**：本地模拟试训状态与原生 `academy_son` 计划状态共用同一个枚举值；`player_id` 尚未存在时没有区分“通过试训”和“FM 已生成球员”。
- **修复**：新增 `trial_passed`；旧档无 UID 的 `training` 在规范化时迁移。只有原生计划同步取得真实 UID 后才进入 `playing`。Hook 错误透传到 API，计划失败时回滚。
- **回归**：`tests/test_child_trial_v294.py`、`tests/test_child_placement_status.py`。

