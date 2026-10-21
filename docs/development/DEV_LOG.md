# FMSDD 开发日志（原名 FMODD）

本文件按「轮次」记录每一次交付的过程：需求、改动、关键决策、验证证据与遗留问题。用户可见的变化仍以 `CHANGELOG.md` 为准，本文件回答的是「怎么做的、为什么这么做、验证到什么程度、下一步该看哪里」。

> 历史说明：第 29–39 轮的过程细节主要记录在 `CHANGELOG.md` 与 `dist` 对应轮次总结中。本文件保留既有记录，不重写、不虚构缺失轮次；从第 40 轮起继续逐轮记录。

## 第 80 轮（V2.9.6cBeta · 快速分娩丹与公告清理，2026-10-21）

- **丹药**：`club_economy.PRODUCTS["instant_birth_pill"]`，价格 1,000,000,000，分类「子女」，`family=child`，进入 `SHOP_SKUS`。
- **生产逻辑**：抽出 `_deliver_child_now()` 供自然生产与丹药共用；`use_birth_pill()` 只接受 `pregnancy.status=="expecting"`，取消待决怀孕事件的 `pending` 状态，强制 `decision="kept"` 并把 `due_day/born_day` 设为当天。
- **接口**：`POST /api/life/interactions/children/birth-pill`，先保存生活状态，再 `consume_instant_item(item_id, "instant_birth_pill")`；消耗失败恢复快照。
- **背包**：`instant_birth_pill` 显示「使用」，调用 `/api/life/interactions` 过滤已揭示的怀孕关系，复用 `inventoryTargetDialog` 选择 NPC；未怀孕时提示没有目标。
- **公告**：删除内部 CDK，合并 2.9.6a/b 文案，新增快速分娩丹说明；`i18n.announce.v296.js` 11 语言同步。
- **测试**：`test_money_ap_v296b.py` 增加丹药价格、仅怀孕可用、立即生产与路由/背包接线检查。
- **版本**：`V2.9.6cBeta` / `2.9.6.3` / `76-dev`。
- **桌面打包**：`dist/FMSDD-V2.9.6cBeta.exe` `85,591,343` 字节，FileVersion `2.9.6.3`，ProductVersion `V2.9.6cBeta`，SHA-256 `04C219EEA90D8C4FE2431203171849B03D3676A2BF5C981CBD11B6EC1091D1CE`；成品未启动。

## 第 79 轮（V2.9.6bBeta · 送钱、行动力购买与三围模糊范围，2026-10-21）

- **送钱**：`money_gift_plan()` 校验 100,000–1,000,000,000，消耗 1 AP；`money_gift_life_interaction()` 先规划再 `adjust_bank_balance(-amount, "life_money_gift")`。增益 = 金额对数 × 性格 × 价值观 × 关系阶段 × 声望 × 既往收礼递减；写入 `gifted_value_total`、`counters.money_gift` 与 `money_gift` 时间线。
- **行动力购买**：`purchase_action_points()` 按缺口补充，单价常量 `ACTION_POINT_PURCHASE_PRICE = 50_000_000`；端点扣银行并写 `purchase` 行动力账本；`action_points` 暴露 `purchase_price`/`purchase_available`。
- **三围**：`_visible_person_for_relationship()` 用 `_stable_unit("measurement-span"/"measurement-lower", person_id, key, value, level)` 生成非对称区间，强制 `lower != upper`；真实值始终在 `[minimum, maximum]`。UI 提示不再显示 `±{cm}`。
- **UI**：互动主页新增「送钱」入口与金额对话框；行动力卡新增「补充」按钮与点数/价格报价；新增 `i18n.v296a.js` 文案。
- **公告**：`announcement_board.js` 新增 `2026-10-21-v296-update`，置顶并标记 `V2.9.6bBeta`；`v290_update` 改为非置顶。新增 `i18n.announce.v296.js` 覆盖 11 语言的 V2.9.0→V2.9.6b 汇总文案。
- **测试**：`test_money_ap_v296b.py` 覆盖价值观差异、递减、AP 价格/上限、非对称区间、路由静态接线；`test_announcements_frontend.py` 更新为 7 条公告并验证新置顶/V2.9.0 取消置顶。
- **版本**：`V2.9.6bBeta` / `2.9.6.2` / `75-dev`。
- **桌面打包**：`dist/FMSDD-V2.9.6bBeta.exe` `85,588,942` 字节，FileVersion `2.9.6.2`，ProductVersion `V2.9.6bBeta`，SHA-256 `9366A43A94C92B5956FBDF7B5C7A09DEE87229F586F36E161AE8FE3E3F39D450`；成品未启动。

## 第 78 轮（V2.9.6aBeta · 资产等级、旅途中人、独立头像源与服从度，2026-10-21）

- **资产等级根因**：`_asset_level_snapshot()` 返回 `current_level`，外出页面和 `travel_life_go_out()` 却读取 `level`，因此始终显示 Lv.0；已统一读取 `current_level`。概率仍只按资产等级计算。
- **旅途中人显示**：`personAffiliation()` 对 `source=encounter`/`npc=true` 显示职业，不再用空队名回退「自由球员」；`personNationality()` 显示国家；档案 chips 对旅途中人隐藏 CA/PA/声望。UID 保留。
- **数量**：没有固定预生成名单；按国家姓名池、10 种职业、6 种性格、21–37 岁动态生成并永久保存。30% 偶遇强制虚构，其余优先真实女足球员；没有女足时全部回退虚构。
- **独立头像源**：`app_settings` 新增 `portrait_sources`（path+offset，最多 12 行）；`set_portrait_source_rows()` 校验绝对目录和偏移；`player_portraits` 命中 sources 后只用 UID+offset 直接找图，不解析 XML。设置页改为可增删的路径/偏移行，复制粘贴即可。
- **服从度**：关系新增 `obedience`（0–100），亲密行为带 `obedience_gain`；`intimacy_options` 与 `intimacy_plan` 投影/写入；亲密页显示进度。新增 `command_night`。
- **受孕**：`stay_close`、`playful_night`、`blindfold_night`、`dice_night`、`command_night` 标记 `pregnancy`，均走 `_maybe_conceive()` 与防护消耗。
- **移除「谈论未来」**：从 `INTIMATE_ACTIONS` 删除 `future_plan`；旧存档字段保留。
- **验证**：生活/外出/头像源/i18n/家庭静态契约聚焦回归通过；未启动 FM。头像源新增 `test_portrait_sources_v296a.py`。
- **版本**：`V2.9.6aBeta` / `2.9.6.1` / `74-dev`。
- **桌面打包**：`dist/FMSDD-V2.9.6aBeta.exe` `85,569,372` 字节，FileVersion `2.9.6.1`，ProductVersion `V2.9.6aBeta`，SHA-256 `3C10E13D7EB676B58FB75349E343B2735CD5041C6B229FA69BDD15FF4FB2B536`；成品未启动。

## 第 77 轮（V2.9.6Beta · 外出偶遇、家庭页 v3 与成人门禁，2026-10-21）

- **范围确认**：只迁移参考 EXE 的「出门逛逛」框架与成人开关；不迁移 1000 亿启动资金、多配偶、家庭资金池、工作推荐、13 国/5 机型或飞机/跑车加成。目的地使用 SDD 现有 9 国 68 城。
- **外出状态**：`life_interactions` schema 8 新增 `travel`，人物快照保存 `source/npc/nationality_code/met_*` 等字段，关系保存 `contact_known` 与 `contact_source`；`normalize_state()` 兼容旧档，虚构人物 ID 使用 1.8e9 保留段，真实 FM UID 仍可放入 pending。
- **真实优先与回退**：`_travel_pick_real_person()` 按目的国俱乐部缓存读取女足球员候选；约 30% 的偶遇直接走虚构人物，其余候选不足时由 `create_encounter_person()` 生成女性旅途中人（21–37 岁、按国家取名与职业），二者都通过既有 `cache_person()` 进入关系系统。未索要到联系方式前，`public_view()` 不显示该关系，但 `travel_public_view()` 仍返回当前偶遇。
- **概率**：`life_travel.asset_bonus()` 只按资产等级每级 +2%，`encounter_chance()` 45% 起、80% 封顶；没有车辆或飞机加成。出门/地点 1 AP，索要联系方式不额外扣 AP。
- **API/前端**：新增 `GET /api/life/interactions/travel`、`POST .../travel/go-out`、`POST .../travel/encounter`；前端新增「外出」主标签、国家/城市/地点选择、偶遇阶段卡、最近足迹、资产等级/概率侧栏与成人锁定提示，城市列表按 9 个一页展开，避免 47 个城市一次铺满。
- **家庭 v3**：`renderFamily()` 重写为摘要卡、横向家长/子女选择、主工作区和常驻右侧栏；`familyChildRail()` 显示青训进度、CA/PA、FM UID、俱乐部、家庭和最近记录；档案页补成长节点/最近记录。青训名先排除纯数字，再按 `team_id` 解析，后端 `_team_display_name()` 同步补名。
- **成人门禁**：设置开关启用前 `fmoddConfirm` 18+ 确认；服务端仍拒绝关闭状态下的亲密接口和成人商品；新增 `i18n.travel.v296.js` 覆盖 11 语言，并补齐新标签/道具文案。
- **亲密道具**：新增 `playful_night` / `blindfold_night` / `dice_night` 三个 `requires_item` 行为；`intimacy_plan()` 接收 `protection` 与 `item_sku`，写入避孕窗口和道具加成；`intimacy_life_interaction()` 在计划成功后消耗背包物品并返回 `consumed_items`。
- **验证**：`test_travel_v296.py`、生活/子女/家庭/API/i18n 聚焦回归通过；生产渲染器用模拟数据生成外出/偶遇/家庭预览截图；`node --check` 通过。未启动 Football Manager 或成品 EXE。
- **遗留**：真实偶遇依赖存档内女足俱乐部与女性球员；没有女足时只能走虚构人物。亲密道具消耗在计划成功后、状态保存前，极端情况下经济写入失败仍可能先消耗道具，后续可改为同事务回滚。
- **版本**：`V2.9.6Beta` / `2.9.6.0` / `73-dev`。
- **桌面打包**：`dist/FMSDD-V2.9.6Beta.exe` `85,561,895` 字节，FileVersion `2.9.6.0`，ProductVersion `V2.9.6Beta`，SHA-256 `3F8362245FFC377660D60FB4F7A7B4A1988D6FE5894AF9372E1D8B63B8CDA189`；成品未启动。

## 第 76 轮（V2.9.5Beta · 家庭页重做、原生青训回写与打包，2026-10-21）

- **家长卡**：家庭总览与子女档案侧栏的头像固定为 40–44px 独立列，修复 58px 共享头像压住姓名的问题；从 `relationships[].relationship` 的 `effective_romance_stage` / `secret_lover` 生成配偶、恋人、秘密情人、暧昧或家长徽标，存档结构不变。
- **子女卡**：重做身份头、成长进度与档案/成长/青训三级视图；移除未定义的 `interaction-primary`，统一使用 `interaction-button`；成长页改为可换行的 3/6/9/12 岁节点与历史表，不再截断为“名…/边…”。
- **响应式**：900px 以下家长列表横向滚动，760px 以下统计卡、子女头图与成长节点单列；新增样式可见字号均不低于 13px。
- **青训入口**：`recommendable_clubs` 加入当前执教俱乐部；15 岁未安排时可保留试训，也可直接“加入我的俱乐部青训”启用 `academy_son`。
- **原生回写**：`_child_placement_status_rows` 返回 `ability_result` 的 `ca/pa/primary_position`；`sync_child_placements` 把真实 CA/PA/主位置同步到子女档案与 `placement`，青训页显示 FM UID。
- **Hook 未就绪**：计划已启用但原生 Hook 未安装时保留计划并返回警告，不再回滚；重启 FM/FMSDD 后刷新继续。
- **执教俱乐部青训**：根因是 `_sync_youth_generation_plans` 的 active team 只含已收购俱乐部，且 `_persist_youth_generation_progress` 用 `_owned_world_club_target` 收尾；执教中的俱乐部因此既不进 Hook 也不做名单核验。现把经理球队加入 active team，新增 `_youth_plan_club_target` / `_manager_team_context`，从俱乐部上下文或原生缓存恢复名称和地址，并用新 `/api/life/interactions/children/academy/refresh` 立即核验。
- **前端刷新**：子女子接口返回的是完整 life view，新增 `applyLifeView()` 同时兼容 `response.life` 与直接 view，修复改名/试训/入队/头像后界面不刷新的问题；青训页「刷新青训状态」现在触发原生核验。
- **验证**：家庭/子女/API/i18n/启动顺序聚焦回归 **62 passed**；桌面宿主 `dotnet build` 通过；未启动 Football Manager 或成品 EXE。
- **版本**：`V2.9.5Beta` / `2.9.5.0` / `72-dev`；`src/web/index.html`、桌面宿主标题与 README 同步。
- **桌面打包**：`dist/FMSDD-V2.9.5Beta.exe` `85,520,084` 字节，FileVersion `2.9.5.0`，ProductVersion `V2.9.5Beta`，SHA-256 `5C766A0FA084A3AFA265FF2218CAD622FDABF996A3929597AEA1B18844B082DC`；成品未启动。

## 第 75 轮（V2.9.4Beta · 家庭工作台分层与青训状态可视化，2026-10-21）

- **家庭界面重制**：家庭页从单一长页面拆为「家庭总览 / 子女档案 / 成长记录 / 青训流程」四个二级分区；总览只保留家庭摘要、下一成长节点、青训事项和家长入口，命名、成长工具、培养记录、头像与试训操作不再全部堆叠在首页。
- **子女档案**：保留按家长筛选的子女卡片，将成长时间线和头像上传移入可展开的档案详情；卡片摘要显示年龄、成长进度、CA/PA、位置及青训状态，青训完成后显示真实 FM UID。
- **青训流程**：新增独立流程面板，区分试训、已提交原生计划、等待生成、已应用和已进入青训等状态；增加「刷新青训状态」入口。刷新只重新请求互动快照，不触发人物全量刷新。
- **原生链路不变**：15 岁仍先参加试训；试训通过后由 `academy_son` 原生青训计划等待 Football Manager 生成真实球员，后台继续通过稳定 UID、球队反向引用和生成计划回写子女状态，未伪造 FM 球员。
- **本地化与样式**：新增 `src/web/i18n.family.v294.js`，覆盖 11 种界面语言；新增家庭分区、总览、成长和青训卡片样式，保持可见字号不低于 13px。
- **验证**：`node --check src/web/interactions_page.js`、`node --check src/web/i18n.family.v294.js` 通过；家庭/子女/青训聚焦回归 **19 passed**。未启动 Football Manager、Hook 或成品 EXE。
- **版本**：保持 `V2.9.4Beta` / `2.9.4.0` / `71-dev`，本轮不升级版本号。

## 第 74 轮（V2.9.4Beta · 十月怀胎、子女培养、情感商店与资产分组修复，2026-10-20）

- **资产分组**：修复资产页/资产赠礼中点击城市或城区后把同组全部资产展开的问题。新的两级展开语义是：打开城市只展开城区标题，打开城区只展开该城区卡片；打开一个城区会收起同城其他城区；筛选变化清空旧展开状态。`life_page.js` 与 `interactions_page.js` 同时修改。
- **实时刷新**：`loadGameClock` 广播 `fmodd:game-clock-changed`；生活页在日期变化时重新请求 `/api/life`（租金、施工、收益、车辆），时间变化时刷新界面；亲密/家庭页在日期变化时重载年龄、怀孕与子女事件。
- **怀孕**：`PREGNANCY_GESTATION_DAYS` 改为 280，新增 `PREGNANCY_EARLY_DAYS=252` / `PREGNANCY_LATE_DAYS=301`；受孕时生成预产期窗口和窗口内随机 `due_day`。怀孕事件在受孕后 **30 天**才进入可选队列（第一个月只显示「可能怀孕」），只决定是否留下孩子；`decision=kept` 后到 `due_day` 才自动出生并写入 `children`，因此家庭页不会提前出现孩子。NPC 怀孕标识显示预产期范围。
- **子女姓名**：`normalize_child` 增加 `surname/given_name/ca/pa/football_position/training_history/training_milestones/neglected_milestones`；`name_child` 用玩家档案姓氏组合全名，家庭页只要求输入名字。
- **成长仙丹**：新增 `growth_elixir` 商品（子女分类）和 `POST /api/life/interactions/children/elixir-items`；背包直接选择孩子、一次消耗多颗库存，每颗一岁，15 岁封顶。
- **青训 PA 映射**：`child_academy_plan_config` 把孩子的 `pa` 映射到原生 `academy_son` 允许的 PA 档位，训练事件提升/错过的 PA 会随青训计划进入原生生成；CA 仍按原生计划保留，避免把童年 CA 直接写成成年 CA。
- **足球培养**：孩子 3/6/9/12 岁触发 `child_football` 事件，事件日期在生日后 0–120 天随机；每次 2–5 个（实际 4 个）位置/CA/PA 选项；`apply_training` 提升 CA/PA 和位置，`apply_neglect_penalty` 对错过超过一年的节点永久扣减；家庭卡显示 CA/PA/位置/培养记录。
- **情感商店与礼物**：`intimate_condoms`、`intimate_pills`、`intimate_toy`、`intimate_lube`、`wedding_ring`、`growth_elixir`，礼物精品店新增 `gift_roses`、`gift_chocolate`；安全套/避孕药赠送后写入 `contraception`，受孕概率大幅降低。
- **背包直用**：礼物卡新增「直接赠送」目标选择 dialog；成长仙丹新增「选择孩子」和批量数量输入；不再必须先进入关系页。
- **求婚戒指**：`relationship_plan` 增加 `has_ring`；无戒指成功率 ×0.42，失败额外扣好感/信任/尊重；接口自动查找并消耗 `wedding_ring`；关系页显示持戒/无戒指提示。
- **商店 UI**：`app.css` 增加紧凑商店卡片规则（52px 图标、两行描述、230px 列宽）；新增情感/子女分组。
- **文案**：新增 `i18n.v294.js`（11 语言，怀孕范围、子女姓名、足球事件、戒指、商店、背包直用）；`i18n.round73.js` 覆盖怀孕事件新文案。
- **验证**：新增 `tests/test_child_training_v294.py`、`tests/test_proposal_ring_v294.py`、`tests/test_life_v294.py`；更新怀孕/子女/版本/i18n 测试；聚焦回归 **110 passed**，未启动 Football Manager 或 Hook。
- **版本**：`V2.9.4Beta` / `2.9.4.0` / `71-dev`。
- **桌面打包**：`dist/FMSDD-V2.9.4Beta.exe` `85,502,395` 字节，FileVersion `2.9.4.0`，ProductVersion `V2.9.4Beta`，SHA-256 `6B6744C1ACC42D27D11535E779EA8DF08291FC80DC4FEA8D5E35B87B7AD20ECF`；成品未启动。

- **本轮追加（商店/家庭重做）**：商店改为礼品精品店式顶部品类栏；情感/成人商品并入礼品精品店「情趣」，每个礼物品类补 1–2 件；礼品精品店新增购物车与统一结算。家庭页改为成长仪表盘：每个孩子显示 3/6/9/12 岁节点摘要与 CA/PA，点击节点或「成长档案」展开姓名、培养历史、道具和试训；取消 15 岁立即决定青训，改为选择俱乐部参加试训，低级别俱乐部也会出现在试训列表，试训通过才进入 `training` 状态。

- **本轮二次修正**：礼品精品店情感/浪漫商品改为逐 SKU 图标（盾、药丸、水滴、骰子、眼罩、戒指等），修复新品只有 4 件可见（`SHOP_SKUS` 未登记新 SKU）；未满 30 天只返回「可能怀孕」并隐藏预产期字段；家庭页改为左侧家长列表、右侧该家长子女；孩子 CA/PA 出生时按父母影响力与个体随机生成，3/6/9/12 岁事件只在对应年龄档触发，仙丹跨过年龄会使未处理事件过期并记入 missed。

- **本轮三次完善**：家庭页左侧家长使用真实头像，子女卡改为单列；成长事件在 3/6/9/12 岁生日当刻出现在卡片 CTA，点击打开事件框；成长选项扩到 12 种（含 CA/PA 增减、街头、体能、冒险、保护、名师、晚成、团队等）；孩子姓名右侧新增改名按钮，15 岁后锁定并二次确认；出生 CA=14–26+父母 CA 一半、PA=72–99+父母 PA 一半；15 岁卡片直接提供头像文件选择，正式进入原生青训并拿到 UID 后写入 `graphics/FMSDD/faces/<uid>` 与 `FMSDD/config.xml`。

## 第 73 轮（V2.9.3Beta · 夫妻约会、资产赠礼分类、亲密记录与怀孕提示，2026-10-20）

### 需求

- 修复夫妻无法约会。
- 资产赠礼中的房产按城市/城区/类型分类并支持折叠；车辆增加厂商、等级、稀有度分类，显示图片、等级、稀有度和当前车库。
- 优化亲密行为界面，把亲密记录做成二级/三级菜单。
- 怀孕概率随亲密度提高；完成「共度夜晚」后若怀孕显示「可能怀孕」，一个月后弹出怀孕事件；未怀孕不显示标识也不弹事件。

### 改动

- **夫妻约会**：前端 `canInviteToDate` 白名单加入 `ambiguous/couple/secret_lover/spouse`；后端 `date_plan` 对已承诺关系不再只依赖社交阶段，夫妻即使社交阶段尚未刷新也可约会。
- **资产赠礼**：后端 `asset_gift_options` 为房产补充 `city_id/district_id/district_name_zh/en`，为车辆补充 `garage_name_zh/en`；前端新增城市/城区/类型筛选、城市→城区两级折叠与全局展开；车辆按厂商分组，增加厂商/等级/稀有度筛选、车辆图片、等级、稀有度、车库信息。
- **亲密记录**：亲密行为页新增「亲密行为 / 亲密记录」二级菜单；记录按月份折叠，每条记录可再展开查看亲密度前后值、受孕概率和维度增量（三级）。
- **怀孕**：`_pregnancy_chance` 改为显式随亲密度单调上升的曲线；`public_view` 在孕期返回 `possible:true` 和剩余天数，人物卡显示「可能怀孕 · 还有 N 天」；到期仍由 `settle_periodic_events` 生成怀孕事件。未受孕时不会创建 pregnancy 记录，因此既无标识也不会产生事件。
- **文案**：新增 `src/web/i18n.round73.js`（11 语言 × 17 键），避免把新键混入既有 children 模块。

### 验证

- 新增 `tests/test_intimacy_round73.py`（5 项）：夫妻低社交阶段仍可约会；亲密度越高受孕概率越高；受孕后孕期显示可能怀孕并到期产生事件；未受孕无标识/无事件；资产赠礼返回城市、城区和车库字段。
- 无头浏览器 mock：夫妻约会按钮已启用；资产赠礼 2 城市 4 城区 20 辆车、20 张图片，车库文案正确；亲密记录 2 个月 5 条，二级/三级菜单可展开。
- 聚焦回归：**260 passed**（含本轮新增 5 项与全部相关既有测试）。

### 说明

- 怀孕判定仍是确定性的内部随机；真实 FM 存档未启动验证。
- 夫妻约会修复是前端白名单 + 后端关系判定双保险，避免只修按钮不修接口。

## 第 72 轮（V2.9.3Beta · 内部测试 CDK 10086，2026-10-20）

### 需求

- 测试时行动力经常不足，希望输入内部 CDK `10086` 立即把行动力补满，且不限使用次数。

### 改动

- **CDK 注册**：`src/tools/club_economy.py` 增加内部码 `10086`，效果为 `refill_action_points`，并标记 `internal`；兑换时识别，但不会写入一次性 `cdk_redemptions`。
- **行动力补满**：`src/tools/life_interactions.py` 新增 `refill_action_points()`，把当前行动力设为当前上限（含已激活的行动力权益），只写行动力流水，不写永久权益、不改上限/周恢复。
- **兑换分支**：`src/tools/account_application.py` 在 `effect` 分支中优先处理 `refill_action_points`，直接规范化互动存档并调用补满函数，跳过 `redeem_cdk_payload()` 的一次性检查，因此可重复使用。
- **界面**：`src/web/app.js` 增加 `settings.cdk.success.refill_action_points` 成功提示；`src/web/interactions_page.js` 监听 `fmodd:interaction-entitlements-changed` 并重新载入互动数据，兑换后行动力立即刷新。
- **本地化**：`src/web/i18n.children.v293.js` 增加 11 种语言的补满提示。

### 验证

- 新增 `tests/test_cdk_internal_10086.py`：
  - `10086` 解析为 `refill_action_points`；
  - 1/12 补满后再次从 3/12 补满，且 `entitlements` 始终为空；
  - `AccountApplicationService.redeem_cdk()` 连续兑换两次，仍不产生 `cdk_redemptions`。
- `tests/test_life_v293.py` 增加 11 语言提示键和前端分支契约。
- 聚焦回归：**255 passed**（原 252 + CDK 3 + 静态契约 6 的新增断言计入既有用例）。

### 说明

- 该码只补当前行动力，不改变上限；上限仍由「日理万机」等一次性权益决定。
- 内部码不显示在设置页的 CDK 列表中，需要手动输入 `10086`。

## 第 71 轮（V2.9.3Beta · 资产分组、批量性能与子女系统，2026-10-20）

### 需求

- 资产过多时界面混乱，希望按「城市 → 城区」分组，并支持展开/收起。
- 批量购买资产很卡，希望等待时间更短。
- 落实子女系统：玩家自主命名、价格昂贵的快速成长丹药；子女自然成长或丹药成长到 15 岁后，自动进入玩家俱乐部，或由玩家推荐到更高级俱乐部；并在青训生成时把指定子女投放到对应俱乐部的青训新成员中。

### 改动

- **资产分组**：`src/web/life_page.js` 把资产卡按 `city_id → district_id` 两级分组，新增 `life-asset-city` / `life-asset-district` 头部、城市资产数与市值、`asset-toggle-group` 单组切换与 `asset-toggle-all` 全局展开/收起；资产超过 24 处时默认折叠城市，避免首屏渲染过多卡片。样式在 `src/web/life.css` 的 V2.9.3 区块。
- **批量购买性能**：性能剖析定位到两个热点，`deepcopy` 占 42.9/45.1 秒：
  - `life_system._city_profile()` 每一块地都深拷贝整份城市画像（含地形多边形），现改为按城市缓存 `MappingProxyType` 只读视图；
  - `life_system.save_state()` 对已是 `normalize_state` 产物的整份存档再次深拷贝，新增 `normalized=True` 由批量路径跳过二次规范化。
  另把「定价 → 确认 → 扣款」拆成 `POST /api/life/property/buy-batch/prepare` 与一次 `buy_life_properties`：规划在锁外完成，扣款前在锁内剔除已被并发购买的地块后再最终计价，扣款与提交仍是单次原子操作。实测广州 123 块 45.1s → 0.84s、深圳 127 块 0.52s，准备接口 0.71s。
- **子女系统**：新增 `src/tools/life_children.py`：
  - `normalize_child` / `name_child`：玩家自主命名（≤40 字）与首选位置（GK…ST）；
  - `CHILD_ELIXIR_TIERS`：孩童成长丹 £2.5 亿 +1 岁、少年成长丹 £9 亿 +3 岁、天才成长丹 £32 亿 +6 岁、一步登天丹 £120 亿 +14 岁，永久生效且不可撤销；
  - `elixir_quote` / `apply_elixir`：按「目标年龄 − 当前年龄」回推 `born_day`，保留服用记录与交易号；
  - `eligibility`：15 岁且未投放才可入队；
  - `child_academy_plan_config`：把子女姓名/位置转成原生 `academy_son` 计划配置（原生只接受 2–30 个 ASCII 字母，非 ASCII 名回退 `Junior` 并保留中文显示名）。
- **青训投放**：`life_interactions.sync_child_placements()` 把原生青训计划的 `status` 映射为 `armed / pending / applied / playing / rejected` 写回子女记录；`POST /api/life/interactions/children/{name,elixir,academy}` 三个接口分别处理命名、丹药与投放，投放直接复用 `arm_youth_plan` + `_sync_youth_generation_plans`，与现有「儿子历练」共用同一套生成钩子，失败自动取消计划并退款。
- **档案最后一处身份覆盖**：`_life_interaction_view` 末尾重新赋值 `manager_identity` 时补回 `team_id/team_name`，否则「加入我的俱乐部青训」拿不到目标球队；`_managed_club_target` 在俱乐部对象缺少 team id 时回退经理球队。
- **投放状态闭环**：新增 `_child_placement_status_rows(scope, state)`，按子女 placement 的 team_id 读取 `youth_plans_for_team`（含 completed/refunded），不再依赖只返回 armed/waiting 的 `active_youth_generation_plans`；`rejected` 允许重新投放。
- **投放原子性**：原生计划创建/同步或子女存档任一步失败，都会 `disarm_youth_plan` 并再次同步钩子，避免留下无子女记录的计划。
- **推荐俱乐部选择**：家庭卡片为推荐模式提供俱乐部下拉框，不再默认发送到列表第一项。
- **中文名**：原生 `academy_son` 名字校验允许 Unicode 字母（仍拒绝数字/下划线），子女名直接写入；`小明` 不再回退成 `Junior`。
- **界面**：`src/web/interactions_page.js` 新增「家庭」主标签，卡片显示年龄进度、命名表单、丹药按钮（显示当前→目标年龄与价格）与「加入我的俱乐部青训 / 推荐到更高级的俱乐部」；样式在 `src/web/interactions.css`。
- **本地化**：新增 `src/web/i18n.children.v293.js`（40 键 × 11 语言），并在 `index.html` 中于 `i18n.interactions.v293.js` 之后加载。

### REA 证据

- `inspect_pe_resources` 读取随包原生模块：`fmodd_hook_core.dll`（SHA-256 `28dbcc3b…`，PE32+，无资源段）与 `fmodd_native_core.dll`（SHA-256 `9b176923…`）。
- 用 PE 导出表解析（同一次静态读取）确认 `fmodd_hook_core.dll` 只导出 `fmodd_hook_abi_version`、`fmodd_hook_pattern_matches`、`fmodd_hook_rel32`、`fmodd_hook_verified_write`；`fmodd_native_core.dll` 导出 `fmodd_decode_vector_header`、`fmodd_market_weights`、`fmodd_native_abi_version`、`fmodd_poisson`、`fmodd_score_matrix`、`fmodd_verified_write`。
- 结论：青训「定制生成」不在原生 DLL 里，而是 Python 侧 `youth_generation_hook.py` 按 `GameLayout.youth_generation_*_hook_rva` 写入运行时补丁；因此子女投放复用 `academy_son` 计划即可，无需新增原生导出。该结论是静态证据，未在真实 FM 进程上验证。

### 验证

- `tests/test_life_children_v293.py`（新增，5 passed）：年龄投影、命名、丹药跨 15 岁、投放状态同步、原生配置可通过 `normalize_youth_plan_config`。
- `tests/test_batch_purchase_charge_kind.py` 扩展为 2 项：扣款详情键不再遮蔽 `kind`；`prepare` 只报价不扣款。
- 聚焦回归（V293/子女/投放/批量/青年队/生活/API/i18n）：**252 passed**。
- 无头 Edge：24 处资产按 2 城市 4 城区分组，城市头显示数量与市值，「全部收起」后城区与卡片归零、「全部展开」后恢复；子女卡片在 15 岁显示 2 种丹药与 2 个投放按钮。
- 修复过程中发现并修正：family 面板误用 `money()`（互动页未定义，抛 `ReferenceError` 导致整页停留在总览），改用 `bridge().formatMoney`。

### 遗留

- 子女投放的真实生成结果依赖 FM 进程与本机布局偏移，需在实机存档中确认；本轮未启动 Football Manager。
- 丹药价格与年龄档位是设计默认值，可根据经济平衡再调。

## 第 70 轮（V2.9.3Beta · 批量购买、车库底部操作、寄存扩容与可领取资产奖励，2026-10-20）

### 需求

- 修复地产批量购买出现“请求无效”。
- 修复车库批量管理底部迁移/出售区域仍被裁切。
- 寄存车库容量改为 10000。
- 资产等级 2–6 增加五辆车；达到等级后可点击领取，优先寄存车库，其次其他有空位车库，全部满时失败提示。
- 优化编辑档案的属性点记录（去掉内部代码），取消 FM 经理声望读取，重制档案布局。
- 版本 2.9.3Beta；补 11 语言、测试、日志与成品。

### 关键决策

- **请求无效的真实原因**：截图中的整批总额为 £54.1 亿，而可用资金仅 £10.0 亿，后端扣款失败后只返回通用错误。修复不是绕过扣款，而是根因是批量扣款调用 `charge_combined_funds(..., kind=kind)` 与函数第二个位置参数 `kind` 冲突，扣款前抛 `TypeError`，旧错误映射只显示“请求无效”；改为 `property_kind=kind`。前端只提示资金缺口、不再用缓存读数阻断；后端扣款前最终校验，提交失败统一回滚并返回可读错误。
- **底部裁切**：上一轮只固定了 footer，但内容宿主仍有 `height:auto`，长列表把 footer 推出弹层。改为 `#life-garage-bulk-content { height:0; flex:1 1 0; min-height:0; overflow:hidden }`，footer `flex:0 0 auto` 且限制高度，列表唯一滚动。
- **寄存容量迁移**：`STORAGE_GARAGE.capacity=10000`，`normalize_state` 对旧 storage 强制写回 10000；界面回退值和 11 语言容量说明同步。测试中需要验证 100 边界的旧用例改为显式设置测试容量 100，避免再把测试夹具当产品常量。
- **手动领取**：`sync_asset_level_rewards` 只发属性点，不再自动发车；新增 `claim_asset_level_vehicle()` 与 `POST /api/life/interactions/asset-level/claim`。领取记录先写奖励账本，再调用 `grant_vehicle_award`；后者按 storage → club → 任意车库顺序分配，所有车库满则抛出“所有车库都没有空位…”，奖励保持未领取可重试。
- **已有等级补偿**：旧存档在 2–6 级已有 `points_awarded` 记录但没有车辆；同步时只在 `vehicle_catalog_id` 变化时补写车辆 ID，不重置 `vehicle_claimed`，因此老玩家会看到领取按钮，已领取 7/11 级的玩家不会重复领取。
- **档案可读性**：`ledgerRow()` 解析 `asset-level:N` 为“等级 N”，车辆记录不再显示内部 `vehicle-000405`；新增 11 语言 `ledger_source.asset_level` 与 reference 文案。
- **声望改为可分配属性**：取消 FM 经理声望读取与所有 FM 标识，声望改为与颜值/能力/魅力/情商并列的属性；每点消耗 `PROFILE_REPUTATION_COST=5` 属性点。旧档 `profile_model<3` 通过 `reputation_migration` 账本补点，保持原可用点不变；新档从 191 点可用开始。档案布局改为身份/属性双栏、金色声望卡、每点成本标签和 sticky 保存栏。

### 改动文件

- `src/tools/life_system.py`：storage 容量 10000 与迁移、`grant_vehicle_award` storage 优先、错误文案。
- `src/tools/life_interactions.py`：2–6 级车辆、手动领取函数、同步不再自动发车、车辆 ID 补偿。
- `src/fm_odds_web.py`：批量购买资金校验/可读错误、`claim_life_asset_level`、版本 2.9.3。
- `src/web/life_page.js`、`src/web/life.css`：可用资金/缺口、批量 footer flex、容量回退。
- `src/web/interactions_page.js`、`src/web/interactions.css`：领取按钮、领取动作、属性记录/声望展示。
- `src/web/i18n.life.js`、`src/web/i18n.interactions.v293.js`：11 语言容量、领取、资金、记录与声望文案。
- `src/web/index.html`：加载 v293 模块、V2.9.3 标题。
- `src/desktop/WebViewHost.csproj`、`src/desktop/WebViewHost.cs`：2.9.3.0 / V2.9.3Beta。
- `tests/test_life_v293.py`、`tests/test_life_interactions_v290.py`、`tests/test_life_system.py`、`tests/test_i18n_static.py`、`tests/test_api_http_dispatch.py`。

### 验证

- `tests/test_life_v293.py`：5 passed（2–7 级车辆、存储优先、后备车库、全满失败、10000 迁移、声望成本、静态契约）。
- `test_life_interactions_v290.py + test_life_v293.py`：21 passed。
- 最终聚焦回归（批量扣款/V293/i18n/API/关系/启动/档案）：**122 passed**；含 storage/garage/version 的子集：**13 passed**。
- 无头 Edge mock：地图批量弹层显示“可用资金”和资金缺口，最终由后端校验；批量管理 footer 的出售按钮完整在弹层内；资产等级 5 张领取按钮与 6 张车辆图；档案显示金色“声望 5 / 每点 5 属性点”、可读的等级/车辆/迁移记录和底部固定保存栏。
- 桌面打包：`dotnet build src/desktop/WebViewHost.csproj -c Release` + `py scripts\build_single_exe.py` 通过；成品 `dist/FMSDD-V2.9.3Beta.exe` `85,451,651` 字节，FileVersion `2.9.3.0`，ProductVersion `V2.9.3Beta`，SHA-256 `F2026B2CA63E421E349126DE2A24A62D3AB2350581E634F9325DECA213098800`。
- 使用实际存档 `322857.manager-2002132538` 的临时副本做端到端验证：120 块地真实扣款、提交、`public_view` 成功，金额 `2,218,770,921.21`，地块 3→123；真实账户未写入。
- 未启动 Football Manager、Hook 或真实存档；成品 EXE 未启动。

### 遗留

- 声望的 5 点成本、旧档迁移与 5 属性卡布局仍需在真实存档上人工复看；FM 经理声望读取已从档案 UI 移除。
- 批量购买的真实 HTTP 请求仍以用户复测为准；已增加 `Documents/FMODD/runtime/request-errors.log` 与前端 `fmodd:last-batch-error`，若仍失败可直接定位。
- 领取失败后的释放车位重试仍需人工复核。

## 第 69 轮（V2.9.2Beta · 抽卡布局、车库批量、重复出售与战令式资产等级，2026-10-20）

### 需求

- 倍率按钮移到卡池标题右侧并优化卡片布局；恢复单抽/十连，倍率同时作用于两个按钮；车位释放后刷新按钮状态。
- 修复车库批量管理长列表遮挡底部转移/出售操作区。
- 修复寄存车库勾选车辆时列表跳回顶部。
- 所有车库界面增加“一键出售重复车辆”，每个车型保留价值最高的一辆。
- 资产等级重制为可左右滑动的战令式界面，显示车辆图片，文字不可选中。
- 版本保持 V2.9.2Beta；补 11 语言、测试、开发/错误日志与成品。

### 关键决策

- **倍率作用域**：单抽按钮 `draws=multiplier`，十连按钮 `draws=multiplier*10`；后端从固定集合改为接受 `1..1000`，仍按每满 10 抽十连价、余数单抽价计价。按钮是否可用只看当前倍率对应抽数，不把倍率写死到 `×1`。
- **车位刷新**：`closeStorageDialog` / `closeGarageBulkDialog` 在关闭后主动 `paint()`；此前 `paint()` 为避免弹窗闪烁会在任意对话框打开时跳过，导致关闭后仍使用旧 `free`。
- **批量布局**：对话框 shell 固定高度、内容列 flex；汇总/筛选固定，车辆列表 `flex:1; min-height:0; overflow:auto`，底部指标/目标/按钮为固定 footer；选择只局部更新汇总与按钮，不重建列表。
- **寄存勾选**：从整窗 `paintStorageDialog()` 改为 `refreshStorageSelectionUi()`，只更新选中数、估值、按钮、目标提示；不替换列表 DOM，因此滚动位置保持。
- **重复判定**：以 `catalog_id`（缺失时用厂商+车型+年份）分组；以服务端 `vehicle_market_value` 为当前价值，保留最高一辆，同值保留较新购入者。服务端先计划全部出售，再一次性提交并调整银行；余额失败恢复快照。
- **战令式资产等级**：使用现有 `asset_level.levels[].vehicle.image`，不改后端数据；新建 `interaction-asset-pass-*` 组件，卡片展示等级、门槛、属性点、车辆图片/状态。轨道用 `overflow-x:auto` + scroll-snap；鼠标 pointer 拖动、滚轮、方向键、左右按钮和触控都可滚动；当前等级写入后自动居中。文本 `user-select:none`，图片 `draggable=false`。

### 改动文件

- `src/web/life_page.js`：倍率/单抽/十连、关闭弹窗重绘、寄存与批量局部选择刷新、重复出售按钮与动作、批量 footer 结构。
- `src/web/interactions_page.js`：战令式资产等级渲染、车辆图片、拖动/滚轮/方向键/按钮、当前等级居中、移除旧的重复滚轮监听。
- `src/web/life.css`、`src/web/interactions.css`：V2.9.2 抽卡/车库/批量/寄存布局与战令视觉。
- `src/web/i18n.interactions.v292.js`：11 语言重复出售与战令状态文案。
- `src/tools/life_system.py`：`duplicate_vehicle_sales()`、抽卡次数范围。
- `src/fm_odds_web.py`：`/api/life/vehicle/sell-duplicates`、V2.9.2Beta / 69-dev。
- `src/desktop/WebViewHost.csproj`、`src/desktop/WebViewHost.cs`、`src/web/index.html`：2.9.2.0 / V2.9.2Beta。
- `tests/test_life_v292.py`、`tests/test_life_system.py`、`tests/test_life_v291.py`、`tests/test_i18n_static.py`：新功能与版本回归。

### 验证

- `tests/test_life_v292.py`：4 passed（重复车辆保留最高价值、未知车库拒绝、3 抽价格、版本/控件静态）。
- `tests/test_life_v292.py + test_life_v291.py + test_i18n_static.py`：21 passed。
- 无头 Edge mock（1574×867）：抽卡 3 池 ×（单抽/十连）按钮分别显示 ×1/×10，倍率 ×1；车库 28 辆，批量弹窗列表 302px 独立滚动、footer 可见，移动/出售按钮可用；寄存车库勾选第 21 行前后 `scrollTop` 均为 900；战令 12 卡、2 张车辆图、当前 Lv.7 居中（scrollLeft 899）。
- 桌面打包：`dotnet build src/desktop/WebViewHost.csproj -c Release` + `py scripts\build_single_exe.py` 通过；成品 `dist/FMSDD-V2.9.2Beta.exe` `85,397,569` 字节，FileVersion `2.9.2.0`，ProductVersion `V2.9.2Beta`，SHA-256 `E14D5536AB42115719C9C72013561295FF58496D1CCC89FEBFDDC06E58705C98`。
- 使用实际存档 `322857.manager-2002132538` 的临时副本做端到端验证：120 块地真实扣款、提交、`public_view` 成功，金额 `2,218,770,921.21`，地块 3→123；真实账户未写入。
- 未启动 Football Manager、Hook 或真实存档；成品 EXE 未启动。

### 遗留

- 真实存档的长车库（数百辆）、寄存车库滚动与拖拽手感仍需人工复核。
- 战令卡片在窄屏（<860px）下显示 1–2 张，需确认实际窗口宽度。

## 第 68 轮（V2.9.1Beta · 多线关系、批量经营与车库扩展，2026-10-20）

### 需求

- 关系在初识、朋友、好友后按玩家/NPC 性别分支：夫妻线、闺蜜线、兄弟线；关系等级与“陌路/熟络”等关系描述分离。
- 资产等级从人物互动总览移到玩家名称右侧，弹层横向滚动。
- 地产地图一键购买按类型筛选、显示数量与金额、整城购买。
- 车库批量出售/转移，支持全选与厂商/等级/稀有度筛选。
- 展厅一键购买当前筛选车辆，仅展示车型排除。
- 神秘车库每池 ×1/×2/×5/×10/×100 倍率。
- 新增 64/96/128 车位车库；车库目录把购买车库资产排到房产附赠车位之前。
- 版本 V2.9.1Beta；补齐开发/错误日志与 11 语言文案。

### 关键决策

- **不重写旧字段**：保留 `social_stage`/`romance_stage` 兼容旧存档，新增 `bond_path`/`bond_stage`/`bond_line`；对外再投影统一的 `level` 与独立的 `tone`。旧 `confidant` 仍可读取，但新关系推进只到 `close_friend`，第四步改为显式选线。
- **关系线锁定**：在好友阶段由 `relationship_branch_capabilities` 计算夫妻/闺蜜/兄弟可用性；第一次选线写入 `bond_path`，之后另一条线会拒绝，避免关系等级回退或双线叠加。兄弟线再分两种：男性+男性/非二元为“搭档→兄弟→生死兄弟”，女性+男性为“搭档→同好→兄弟”（`bond_variant` 区分 `brotherhood_direct`/`brotherhood_kindred`）。
- **关系描述与等级解耦**：`tone` 由熟悉/好感/信任/尊重加权，不参与等级门槛；等级只由共同阶段、`romance_stage` 或 `bond_stage` 决定。
- **批量购买原子化**：地产整城购买先计算全部 `buy_property_plan`，一次性扣款；任一步提交失败则恢复状态快照并退款。车库批量沿用已有 `/vehicle/move-batch`、`/vehicle/sell-batch` 的 100 辆上限。
- **展厅批量**：后端 `buy_vehicle_batch_plan` 一次分配车位并生成互不冲突的车辆 ID，前端排除 `dealer_status=display_only`，车位不足时禁用。
- **倍率价格**：每满 10 抽按十连价，余数按单抽价；后端只接受 1/2/5/10/100，避免任意次数破坏价格曲线。
- **高车位生成**：非核心区按 `premium` 哈希概率生成 64/96/128 车位，面积至少按每车位 32 m² 扩展；旧城市包不强制重建，避免移动已购地块。

### 改动文件

- `src/tools/life_interactions.py`：关系线常量、能力矩阵、等级/关系描述、分支进度、关系计划与选项、状态迁移。
- `src/tools/life_system.py`：批量购车计划、高车位生成、倍率价格、车库容量分档。
- `src/fm_odds_web.py`：`/api/life/property/buy-batch`、`/api/life/vehicle/buy-batch`，版本 `V2.9.1Beta` / `68-dev`。
- `src/web/interactions_page.js`、`src/web/life_page.js`、`src/web/index.html`、`src/web/interactions.css`、`src/web/life.css`：资产弹层、关系线 UI、一键购买/批量车库/展厅/倍率。
- `src/web/i18n.interactions.v291.js`：11 语言新增文案。
- `tests/test_life_v291.py`、`tests/test_i18n_static.py`、`tests/test_life_system.py`：新功能与版本回归。
- `README*.md`、`CHANGELOG.md`、`docs/development/DEVELOPMENT.md`：版本与功能说明。

### 验证

- `py -X utf8 -m pytest tests/test_life_v291.py`：11 passed。
- `py -X utf8 -m pytest tests/test_i18n_static.py`：5 passed。
- `py -X utf8 -m pytest tests/test_life_interactions.py tests/test_life_interactions_api.py tests/test_life_system.py`：历史用例通过（版本断言已更新为 68-dev）。
- 无头 Edge + mock `/api/state`、`/api/life/interactions`：资产按钮、12 节点弹层、关系线面板（2 个可选线、3 个进度块）渲染通过。
- 无头 Edge + mock `/api/life`、`/api/life/city-packs`：地图“一键购买”弹层显示 3 块、总额 £612.0 万；车库批量弹层显示 2 辆车、筛选/目标/迁移/出售控件；对话框需挂到 `body` 才能显示（见 E68-01）。
- 桌面打包：`dotnet build src/desktop/WebViewHost.csproj -c Release` + `py scripts\build_single_exe.py` 通过；成品 `dist/FMSDD-V2.9.1Beta.exe` `85,385,930` 字节，FileVersion `2.9.1.0`，ProductVersion `V2.9.1Beta`，SHA-256 `956D678BFF3062FC6D1CA814AA9C238071656964DD50D5B53650F70CBF2A8936`。
- 使用实际存档 `322857.manager-2002132538` 的临时副本做端到端验证：120 块地真实扣款、提交、`public_view` 成功，金额 `2,218,770,921.21`，地块 3→123；真实账户未写入。
- 未启动 Football Manager、Hook 或真实存档；成品 EXE 未启动。

### 遗留

- 需在真实存档上复核关系线选择的 API 结果与 11 语言长文案换行。
- 车库批量/展厅批量/倍率在真实页面尚未逐项点击验证（受当前开发服务未连接存档限制）。
- 真实存档上的关系线 API 与长文案仍需人工复看；成品 EXE 首次启动行为未验证（按仓库约定未启动成品）。

## 第 67 轮（V2.9.0Beta · 公告“不再提醒”、启动提醒机制与赞助文案，2026-10-19）

### 需求

- 公告弹窗右上角（关闭按钮左侧）新增「不再提醒」勾选。
- 未勾选时每次打开软件或出现新公告都自动弹出；勾选后只有新公告才弹出。
- 赞助说明更委婉：补充自费 150+ 元、累计约 20 亿 token、服务器与开发仍在投入，并重点说明赞助不影响使用。
- 重新打包桌面端。

### 实现

- `src/web/index.html`：`#announcement-dialog` 头部右侧新增 `.announcement-head-actions`，内含 `#announcement-mute` 复选框（关闭按钮左侧），文案键 `announce.mute`。
- `src/web/app.js`：新增 `ANNOUNCEMENT_MUTE_STORAGE_KEY`（`fmsdd-announcements-mute`）、`announcementMuted` / `setAnnouncementMuted` / `syncAnnouncementMute`；`showStartupAnnouncements()` 改为“未静音每次启动都弹，已静音只在未读时弹”；打开公告板同步勾选状态，勾选变化即时写入本机偏好。
- 11 种语言新增 `announce.mute`；交流群公告正文改写赞助说明：自费 150+ 元、累计约 20 亿 token、服务器与开发投入继续，加粗“赞助不影响任何功能、不解锁内容、不是购买授权”。
- `src/web/app.css`、`src/web/dark-theme.css` 增加头部操作区与复选框样式。
- 测试：新增静音偏好的存储键、启动判定、头部顺序、11 语言文案回归。

### 关键决策

- 默认不勾选，符合“每次打开软件都提醒”的要求；勾选后才进入“只提醒新公告”。静音偏好只写本机，不随账户/存档切换。
- 静音不等于关闭公告：顶栏按钮始终可以手动打开；未读红点仍按最新公告判定。
- 赞助文案先说明“不影响使用”，再说明成本与补血需求，避免读者误以为付费才能用；金额与 token 数是作者自述，不做任何兑换或权益承诺。

### 验证证据

- `py -X utf8 -m pytest tests/test_announcements_frontend.py tests/test_i18n_static.py tests/test_i18n_locale_packs.py tests/test_app_boot_order.py tests/test_dark_mode_frontend.py -q`：54 passed；赞助文案改动后再跑相关 42 项通过；全量相关批次 298 passed。
- 无头 Edge 实测：勾选后写入 `localStorage["fmsdd-announcements-mute"]="1"`；静音且已读时 `showStartupAnnouncements()` 不打开；未静音时打开；复选框 14×14、位于关闭按钮左侧（x=828 vs 910）。
- 打包：`dist/FMSDD-V2.9.0Beta.exe` `85,357,872` 字节，SHA-256 `EA33A3B959554163A2BF315EE194B4E34FE44F4FB208CB500DF1F1AD913420D9`；解包核对 `#announcement-mute`、`announce.mute`、静音键与新赞助文案。
- 未启动 Football Manager、Hook 或打包后的 EXE。

### 改动文件

| 文件 | 作用 |
| --- | --- |
| `src/web/index.html` | 公告头部“不再提醒”复选框 |
| `src/web/app.js` | 静音偏好、启动提醒判定、勾选同步 |
| `src/web/app.css`、`src/web/dark-theme.css` | 头部操作区与复选框样式 |
| `src/web/i18n.static.js`、8 个语言包 | `announce.mute` 与赞助文案（11 语言） |
| `tests/test_announcements_frontend.py` | 静音、头部顺序、11 语言回归 |
| `docs/*`、`CHANGELOG.md` | 功能索引、UI 规范、运行时契约、开发/错误日志 |

### 遗留问题

- 静音偏好是安装级 localStorage，不随账户/存档；清空 WebView2 缓存或数据目录会恢复默认“提醒”。
- “新公告”只在本版本常量内判定；真正的线上推送不在当前架构内。
- 未在真实桌面 WebView2 中验收弹窗节奏与复选框在窄窗口下的换行。

## 第 66 轮（V2.9.0Beta · 公告图片与交流群、标题本地化与桌面打包，2026-10-19）

### 需求

- 公告标题不再出现英文：改为内容优先的中文/本地化标题，版本交给徽标。
- 公告支持图片，插入 FMSDD 交流群二维码；分享群号 `1131124119`。
- 完善公告内容，并完成桌面版打包。

### 实现

- `src/web/announcement_board.js` 增加 Markdown 图片：`![alt](/assets/…)` 独立成行渲染为带图注的 `figure`，行内图片渲染为 `img`；`src` 只接受 `/assets/` 打包资源或 `https://`，拒绝 `data:`、`javascript:`、`../` 与反斜杠；统一 `loading="lazy"`、`decoding="async"`，`plainText` 同时剥离图片语法。
- 五条既有公告标题改为内容优先，中文侧不再以 “FMSDD V2.xBeta …” 开头（版本由卡片徽标承担）：内容变更汇总、V2.8 系列更新汇总、更名与俱乐部股市上线、关于本版本与下注功能的说明、V2.7.0 之前的功能总览；11 种语言同步改写。
- 新增第六则置顶公告「交流群与反馈渠道」（`announce.entry.community`，2026-10-19 12:00，标签「说明 / 活动」）：群号 **1131124119**、交流群二维码与赞助作者二维码（一行两个）、入群与反馈须知，11 种语言。卡片标记 `alwaysOpen`，3 个块、任何语言都不折叠，两个码 287×287 直接可见。
- 新增运行时图片 `src/web/assets/community/qq-group.png`：由根目录 `QQ QRCode.png` 等比缩放到 640×640，242 KB；赞助二维码复用既有 `src/web/assets/author-support.png`（1014×1014）。
- `src/web/announcement_board.js` 支持“一行两个图片”：匹配双图语法后渲染为 `.announcement-media-row` 两列网格，窄屏（≤560px）降为单列；单独图片仍为 `figure`。
- `src/web/app.css`、`src/web/dark-theme.css` 增加图片、图注、双码行样式及暗色规则。
- 收起预览统一为 `--announcement-collapsed-height: 220px`：五条可折叠公告收起高度一致，展开时移除高度限制完整显示全文；“交流群”卡片保持 `alwaysOpen`，不被折叠遮挡。
- `tests/test_announcements_frontend.py` 增加图片渲染/不安全来源拒绝、双图一行、二维码与赞助码资源、群号存在性、`alwaysOpen` 不折叠、非英文标题不得等于英文标题、中文标题必须含汉字且不得以 `FMSDD V` 开头等回归。
- 桌面打包：`py scripts\build_single_exe.py` 生成 `dist\FMODD.exe`，按发布命名复制为 `dist\FMSDD-V2.9.0Beta.exe`（同一二进制）。

### 关键决策

- 标题不写产品名与版本，版本信息只由卡片右上角徽标承担：避免 11 种语言里出现半截英文，也让同一版本的两条公告可区分。
- 图片走 Markdown 而不是 HTML：渲染器仍然只输出受控标签，公告不能注入样式或脚本；二维码作为打包资源，开发版与冻结版都可用。
- 交流群单独成卡而不是塞进永久公告：永久公告已经很长，折叠后二维码会被遮住；独立卡片块数少，并用 `alwaysOpen` 保证英文等长译文也不会收起两个码。
- 赞助码与交流群码并排：两者都是“扫码动作”，一行两个比上下堆叠少占一屏；说明文字明确“赞助自愿、不解锁功能、不是授权”，避免被理解为付费版。
- 群号写成可复制的纯文本（`1131124119`）而不是图片，方便搜索与转发。
- 打包仍使用仓库的本地一致性构建，不替代官方受保护发布管线；产物未签名。

### 验证证据

- `py -X utf8 -m pytest tests/test_announcements_frontend.py tests/test_i18n_static.py tests/test_i18n_locale_packs.py tests/test_app_boot_order.py tests/test_dark_mode_frontend.py -q`：53 passed。
- 无头 Edge（`--headless=new` + CDP）实测 zh-CN：六条标题全部中文；交流群卡片不折叠、`.announcement-media-row` 为 `309px 309px` 两列，两个 `figure` 图注分别为「FMSDD 官方交流群二维码」「支持作者二维码」；交流群图 `640×640`、渲染 287×287，赞助图 `1014×1014`、渲染 287×287，均加载成功。
- 折叠实测：五条可折叠公告收起高度均为 `220px`；展开「关于本版本与下注功能的说明」后 `height == scrollHeight`（354px），按钮在「展开 / 收起」之间正确切换。
- `py src/tools/build_embedded_web_assets.py`：541 个文件重新内嵌，包含新二维码与双码样式。
- `py scripts\build_single_exe.py`：PyInstaller one-file 构建通过，`dist\FMODD.exe` 85,356,687 bytes（81.4 MiB），文件版本 `2.9.0.0`、产品版本 `V2.9.0Beta`；按发布命名复制为 `dist\FMSDD-V2.9.0Beta.exe`，SHA-256 `92BA87D7D692537631FBE83FDE829C2C60E29AE79CE4ED28C8C81645011C9004`。
- 解包核对（`PyInstaller.archive.readers.CArchiveReader`）：CArchive 638 项，含 `web\announcement_board.js`（`alwaysOpen` 与 `announcement-media-row`）、`web\assets\community\qq-group.png`、`web\assets\author-support.png`、`web\i18n.static.js`（含「内容变更汇总」「交流群与反馈渠道」「1131124119」与两个图片路径）以及 `web\app.css`（`.announcement-media-row`）。
- 未启动 Football Manager、Hook 或真实存档；打包后的 EXE 未在本轮启动（按仓库规则需另行授权），桌面实机窗口与扫码仍待用户验收。

### 改动文件

| 文件 | 作用 |
| --- | --- |
| `src/web/announcement_board.js` | Markdown 图片、双图一行、`alwaysOpen`、交流群条目 |
| `src/web/app.css`、`src/web/dark-theme.css` | 图片/图注/双码行样式与暗色规则 |
| `src/web/assets/community/qq-group.png` | 新增：交流群二维码（640×640） |
| `src/web/i18n.static.js`、8 个语言包 | 六条标题重写、交流群标题与正文（11 语言） |
| `tests/test_announcements_frontend.py` | 图片、二维码、标题本地化回归 |
| `docs/*`、`CHANGELOG.md` | 功能索引、UI 规范、运行时契约、开发/错误日志 |

### 遗留问题

- 其余 9 种语言的公告正文仍是原译文 prose + 标题结构；本轮只重写了标题与新增交流群卡片。
- 二维码为 640×640 PNG（242 KB），如后续需要更小体积可改 WebP，但需重新验证扫码。
- 未在真实桌面 WebView2 中扫码验证；图片显示与布局只在无头 Chromium 内核验证。

## 第 65 轮（V2.9.0Beta · 公告板 Markdown、状态标签与 V2.9.0 变更公告，2026-10-19）

### 需求

- 完善公告功能：至少支持 Markdown、多级标题、排序与状态标签，并在此基础上补齐筛选与搜索。
- 优化现有四条公告的内容与结构；取消 V2.8.5 公告的置顶；新增 V2.8.5～V2.9.0 的置顶变更公告。
- 版本号保持 V2.9.0Beta 不变；同步开发日志、错误日志、功能索引、UI 规范与运行时契约。

### 实现

- 新增 `src/web/announcement_board.js`：条目表（id / 日期 / 时间 / 置顶 / 版本 / 状态标签 / 文案键）、Markdown 子集渲染器、置顶与最新两种排序、标签筛选、全文搜索，以及卡片和筛选条标记。渲染器先转义 HTML 再套用格式，链接只接受 http(s)；支持 ATX 与旧 `【】` 标题、段落、扁平列表、引用、分隔线、管道表格、代码块，以及粗体、斜体、删除线、行内代码和链接。
- `src/web/app.js` 的公告段收敛为门面：未读判定改用**日期时间最新**的条目 id，排序偏好写入 `localStorage["fmsdd-announcements-view"]`，标签筛选与搜索每次打开重置，卡片展开状态只保存在当前会话；新增 `toggleAnnouncementCard` 与筛选、排序、搜索、清除绑定，并在界面语言切换时重绘。
- `src/web/index.html`：公告弹窗新增工具栏（标签筛选、搜索、排序），并在 `app.js` 之前加载 `announcement_board.js`。
- `src/web/app.css`、`src/web/dark-theme.css`：Markdown 标题/列表/引用/代码/表格/链接、八色状态标签、工具栏、筛选条与折叠样式；暗色主题补齐对应规则，所有可见字号不小于 13px。
- 文案：`i18n.static.js` 与 8 个语言包新增 17 个公告 UI 键和 `announce.entry.v290_update`；四条旧公告正文由 `【小节】` 统一转为 `##` 多级标题，中文与英文重写为“标题 + 要点列表”并保留全部事实，其余语言保留原译文、只同步结构。
- 新增第五则公告（置顶，排在永久公告之后）：V2.8.5→V2.9.0 变更清单，按 V2.8.6 / V2.8.7 / V2.8.8 / V2.8.9 / V2.9.0 分组，附公告板说明与兼容提醒，覆盖 11 种语言。
- 取消 V2.8.5 公告置顶（`pinned:false`），永久公告（开源说明）保持第一。

### 关键决策

- 公告数据、渲染与排序放进独立模块，`app.js` 只保留可变状态与 DOM 绑定：既避免继续膨胀两个大文件，也让渲染器可以被 Node 直接测试。
- 置顶契约保持不变：永久公告 → 其他置顶 → 普通；“最新优先”只取消置顶组的优先，不移动永久公告，避免读者找不到常驻说明。
- 排序持久化、筛选不持久化：持久化的筛选会在下次打开时遮住新公告，与未读提示冲突，因此每次打开都重置标签与搜索。
- 未读判定从“数组第一项”改为“日期时间最新”，排序或数组顺序变化不再产生假未读。
- 旧 `【小节】` 语法保留为渲染器兼容分支，同时把 11 种语言正文迁移到 `##`，防止个别语言包漏改时突然丢失标题。
- 顺带修掉三项既有本地化缺陷（西语重复键、德语 `was` 触发的英文功能词误判、繁中「校驗」），它们都在公告正文里，属于本轮范围。

### 验证证据

- `py -X utf8 -m pytest tests/test_announcements_frontend.py -q`：18 passed；覆盖弹窗工具栏、模块加载顺序、条目与标签、两种排序、永久公告优先、最新条目判定、筛选/搜索、Markdown 结构与转义、不安全链接拒绝、卡片与筛选条标记、11 语言文案与 `##` 结构。
- `py -X utf8 -m pytest tests/test_i18n_static.py tests/test_i18n_locale_packs.py tests/test_i18n_frontend.py tests/test_i18n_catalog_contract.py tests/test_i18n_api_contract.py tests/test_i18n_settings.py tests/test_i18n_shell_dynamic.py tests/test_i18n_audit.py tests/test_announcements_frontend.py tests/test_app_boot_order.py -q`：84 passed；原错误日志登记的 3 项语言包失败已转绿。
- `py -X utf8 -m pytest tests/test_dark_mode_frontend.py tests/test_shell_frontend_optimization.py tests/test_existing_page_hierarchy.py tests/test_frontend_font_sizes.py tests/test_frontend_source.py tests/test_utility_frontend_optimization.py tests/test_frontend_enhancement_optimization.py -q`：29 passed。
- `py -X utf8 -m pytest tests/test_home_desktop.py tests/test_frontend_refresh_recovery.py tests/test_frontend_state_sync.py tests/test_public_copy_hygiene.py tests/test_local_icon_assets.py tests/test_toast_layering.py -q`：164 passed。
- `node --check` 覆盖全部改动 JS；`py src/tools/build_embedded_web_assets.py` 重建内嵌资源；重启 7857 开发服务后确认首页与 `/announcement_board.js` 均可读取。
- 未启动 Football Manager、Hook、真实存档或成品 EXE；桌面 WebView 的实际字形、换行、折叠高度和窄窗口工具栏仍需实机/桌面验收。

### 改动文件

| 文件 | 作用 |
| --- | --- |
| `src/web/announcement_board.js` | 新增：条目标记、Markdown 子集渲染、状态标签、排序/筛选与卡片/筛选条 |
| `src/web/app.js` | 公告门面、未读判定、视图偏好、展开集合与工具栏绑定 |
| `src/web/index.html` | 公告工具栏、`announcement_board.js` 加载顺序 |
| `src/web/app.css`、`src/web/dark-theme.css` | Markdown、标签、工具栏样式与暗色规则 |
| `src/web/i18n.static.js`、8 个语言包 | 17 个 UI 键、V2.9.0 公告、四条旧公告结构与文案、3 项旧缺陷修复 |
| `tests/test_announcements_frontend.py`、`tests/test_app_boot_order.py`、`tests/test_i18n_static.py` | 新契约与脚本顺序回归 |
| `docs/*`、`CHANGELOG.md` | 功能索引、UI 规范、运行时契约、开发/错误日志 |

### 遗留问题

- 公告正文的 11 语言结构已同步，但除中英文外的译文仍是逐句 prose，只获得标题与段落结构；若要“要点化”还需按语言重译。
- 折叠阈值是纯文本 280 字符或 6 个块，长表格或长代码块可能提前折叠，仍需真实窗口高度验收。
- 未做浏览器/WebView 截图验收；窄窗口下筛选条换行与搜索框宽度只有 CSS 静态检查。

## 第 64 轮（V2.9.0Beta · 关系后果、情商、资产等级与 68 城地图，2026-10-19）

### 需求

- 亲密行为面板底部的说明文字不能继续左右分栏；窄窗口和长文案必须保持自上而下的单一阅读顺序。
- “共度夜晚”需要增加受孕概率，并在 30 天后生成怀孕抉择事件；结束妊娠应显著降低亲密度。亲密度改为可正可负，长期负值或极端负值应触发分手/离婚危机。
- 保密情人在多次“共度夜晚”或“私享旅行”后应累积暴露风险；暴露时显著削弱公开情侣/配偶的信任、好感与亲密度，并让玩家选择结束秘密关系或离开公开关系。
- 玩家档案新增情商；聊天、赠礼、约会、亲密行为与关系判定应受到颜值、能力、魅力、情商的不同维度影响，同一种做法因属性不同而得到不同结果。
- 总览玩家信息卡新增资产等级时间轴；等级门槛逐级拉大，达到等级时奖励属性点、传奇或特别车辆。
- 地图新增 23 座中国城市与 18 座海外城市；资产生成必须继续避让海洋、海岸、河流、沙滩、湿地、绿化与公园。
- 版本迭代到 V2.9.0Beta，并补齐开发日志、错误日志、契约与成品。

### 实现

- `src/web/interactions.css`：`.interaction-intimacy-meter-foot` 改为单列网格，两条说明按顺序纵向排列；新增关系事件、负亲密度、资产等级时间轴和窄屏适配样式，所有可见字号不低于 13px。
- `src/tools/life_interactions.py`：schema 升至 7；亲密度范围扩展为 -100～+100，新增五档负值语义、负值起始日、分手/离婚危机阈值与失败修复结果。新增 30 天孕期、保留/结束妊娠事件、持久子女记录、秘密关系累计风险与暴露事件。档案可分配属性新增 `eq`；情商参与全局社交校准、信任增益与危机修复，颜值/能力/魅力/情商分别通过边界限幅影响吸引、尊重、好感与信任。
- 资产等级设有 12 级，门槛从 200 万逐级扩展到 2,160 亿；达到等级后增加永久属性点，7 级与 11 级分别奖励 Bugatti Chiron 与 Aston Martin Valkyrie AMR Pro。奖励账本幂等；车库已满时车辆保留为待领取，后续加载自动重试。
- `src/fm_odds_web.py`：互动视图统一结算怀孕、暴露与关系危机事件，并在投影前同步资产等级奖励；新增 `/api/life/interactions/intimacy` 与事件处理路径。
- `src/web/interactions_page.js`、`src/web/index.html`：新增待决事件横幅、事件弹窗、秘密风险与孕期状态徽标、负亲密度刻度、情商分配项和资产等级时间轴；事件结果复用单栏结果卡。
- `src/web/i18n.interactions.v290.js`：新增情商、怀孕、暴露、危机、资产等级及事件文案，覆盖 en-GB、zh-CN、zh-TW、ko-KR、de-DE、es-ES、fr-FR、ru-RU、ja-JP、pt-BR、pt-PT 共 11 种界面语言。
- `src/assets/life/cities_extra_cn.json`、`cities_global.json`、`city_profiles_extra.json`：城市目录扩展到 9 国 68 城；新增中国 23 城、英国 4 城、德国 6 城，以及马德里、布鲁塞尔、阿姆斯特丹、东京、名古屋、大阪、首尔、釜山。
- `scripts/build_life_terrain_data.py` 与 `src/assets/life/city_terrain.json`：离线地形包补齐 68 城，共 13,403 个水域多边形与 15,384 个绿地多边形。运行时只读本地 `city_terrain.json`，不联网；地块中心及半径同时避让水岸 20 米、绿地 15 米。开放海岸仍需海岸线数据时，维护脚本保留 `--coastline-shapefile` 入口。
- 产品、页面标题、窗口标题、桌面宿主与文档同步为 V2.9.0Beta / `2.9.0.0` / `64-dev`。

### 关键决策

- 怀孕只对“男性玩家 + 成年女性 NPC”组合判定，单次受孕概率限制在 3.5%～38%，且已有待决孕期时不重复受孕；事件概率使用稳定哈希，读档不会因刷新页面反复改判。
- 危险事件不会静默解除关系：怀孕、暴露和关系危机都先生成待决事件，由玩家明确选择；危机修复失败时结果会明确返回失败并结束恋爱/婚姻。
- 关系负值同时支持“单次极低”和“持续低于阈值”两条触发路径，避免一次事件就永久锁死，也避免无限拖延。
- 情商与其余社交属性只增不减，但参与数值计算的贡献在 100 点后封顶，防止后期海量属性点破坏平衡。
- 资产等级按当前自有房产与车辆市值快照计算；奖励一旦领取不再因出售资产回退，避免反复买卖刷点。资产等级卡只显示服务端快照，不在前端保存经济真值。
- 地形掩码是构建产物，运行时离线读取；城市包生成只使用当前城市的 profile 与地形，避免一次性遍历全部城市。

### 验证证据

- `py -X utf8 -m pytest tests/test_life_interactions.py tests/test_life_interactions_beta.py tests/test_life_interactions_polish.py tests/test_life_interactions_v290.py tests/test_life_interactions_api.py -q`：86 passed。
- `py -X utf8 -m unittest tests.test_life_interactions_v290 -v`：15 passed；覆盖负亲密度、危机、怀孕、秘密暴露、情商差异、资产等级幂等与车库满重试。
- `py -X utf8 -m unittest tests.test_life_interactions_api -v`：9 passed；事件接口会从事件记录推导人物，不信任客户端传入的 `person_id`。
- `py -X utf8 -m pytest tests/test_life_system.py -q -k "city_catalog_expands or city_terrain_pack_covers or city_profile_exclusions or terrain_multipart or city_pack_is_deterministic"`：5 passed，耗时 411.21 秒；覆盖 68 城、地形环、内外孔洞、资产避让与城市包确定性。
- 地形包自检：68/68 城市，缺失 0；`city_terrain.json` 41,459,736 bytes；水域 13,403、绿地 15,384。
- `node --check src\web\interactions_page.js`、`node --check src\web\i18n.interactions.v290.js`、`node --check src\web\life_page.js`：全部通过。
- 静态本地化测试 `tests/test_i18n_static.py` 通过；第 64 轮新增的完整 11 语言键值由该测试覆盖。
- 成品：`dist\FMSDD-V2.9.0Beta.exe`，85,121,497 bytes，SHA-256 `DEE752BC4C17922D1A6BBC24ECA608839CEA95D4CF0CAF2D26480BB1EEC06531`；文件版本 `2.9.0.0`，产品版本 `V2.9.0Beta`。未启动 Football Manager、Hook、真实存档或成品 EXE。

### 改动文件

| 文件 | 作用 |
| --- | --- |
| `src/tools/life_interactions.py` | schema 7、负亲密度、怀孕、暴露、危机、情商与资产等级服务端逻辑 |
| `src/fm_odds_web.py` | 互动视图事件结算、资产奖励同步与 API 编排 |
| `src/web/interactions_page.js`、`src/web/index.html` | 事件弹窗、状态卡、情商与资产等级时间轴 |
| `src/web/interactions.css` | 单列说明、负亲密度、事件与资产等级布局 |
| `src/web/i18n.interactions.v290.js` | 11 语言新增文案 |
| `src/assets/life/cities_extra_cn.json`、`cities_global.json`、`city_profiles_extra.json` | 68 城目录与城市画像 |
| `scripts/build_life_terrain_data.py`、`src/assets/life/city_terrain.json` | 离线水域/绿地地形生成与 68 城数据 |
| `tests/test_life_interactions_v290.py`、`tests/test_life_interactions.py`、`tests/test_life_interactions_api.py`、`tests/test_life_system.py` | 本轮领域、API、前端口径与城市覆盖回归 |
| `README.md`、`CHANGELOG.md`、`docs/*` | 版本、功能索引、运行时契约、开发与错误日志 |

### 遗留问题

- 未启动 FM、Hook、真实存档或成品 EXE；真实窗口渲染、真实游戏日期推进与怀孕/暴露事件的实际弹窗节奏仍需在成品验收时复核。
- 68 城城市包全量回归约需 6 分 51 秒，主要耗时在逐城地形距离计算；当前不影响运行，但后续可增加按城市缓存的测试夹具。
- 仓库既有的 `tests/test_i18n_locale_packs.py` 仍有 3 项旧公告文案失败（西班牙语重复键、德语英文回退、繁中旧词），不属于本轮新增路径，已登记在错误日志，未在本轮扩大范围修改。
## 第 63 轮（V2.8.9eBeta · 结算卡重制、确定关系亲密度与亲密行为，2026-10-19）

### 需求

- 聊天、赠礼、约会、资产赠送、关系推进与亲密行为的结算界面必须彻底重制；旧界面右侧大片空白、按钮过高、内容松散，不能再沿用。
- 关系进度右侧新增只有情侣、保密情人或夫妻才可见的“亲密行为”标签，内部提供确定关系可进行的亲密活动，为后续子女系统预留家庭规划入口。
- 新增确定关系专属的亲密度：聊天、赠礼、约会和资产赠送都应增加亲密度；每个亲密行为按钮需要图标、背景强调色、行动点消耗与亲密度消耗，并同步补齐已有行为的确定关系文本。
- 版本迭代到 V2.8.9eBeta，补齐开发日志、错误日志、契约与成品验证。

### 实现

- `src/tools/life_interactions.py`：`SCHEMA_VERSION` 升至 6；新增 `INTIMACY_MAX=100`、五档亲密度带、情侣/保密情人/夫妻初始值 18/15/28 与 `INTIMATE_ACTIONS` 六个行动。`_add_intimacy()` 只对确定关系生效并在 100 封顶；聊天 `0.8 + 偏好 0.5`、赠礼 `1.0 + 价值系数 + 偏好 0.75`、约会 `2.0 + AP×0.8 + 偏好/旅行加成`、资产赠礼 `2.0 + 价值系数×3.2`，均复用魅力四射倍率。
- 关系记录新增 `intimacy`、`last_intimacy_day` 与 `family_plan_discussed`；关系升级时写入阶段初始亲密度，分手/离婚归零并清除家庭规划标记。`intimacy_options()` 返回阶段门槛、行动力、亲密度成本、阻塞原因与增益预览；`intimacy_plan()` 在同一次锁定中扣除行动力与亲密度并写时间线。
- `src/fm_odds_web.py`：新增 `POST /api/life/interactions/intimacy`；`public_view()` 为每段关系下发 `effective_romance_stage`、`is_intimate`、`intimacy`、`intimacy_band` 与 `intimacy_options`。
- `src/web/interactions_page.js`：`renderTabs(data, "interaction")` 仅在 `isIntimateRelationship()` 为真时追加“亲密行为”标签；新增亲密度面板、六张行动卡、当前进度、最近四次亲密历史与提交处理。`showActionResult()` 改为单栏自包含结果卡，覆盖成功、失败、关系升级、亲密度变化、家庭规划与 `action_cost`。
- `src/web/index.html`：结果弹窗改为 `interaction-result-dialog` + `interaction-result-card` 结构，移除 `life-collection-dialog-shell` 双栏壳；聊天/赠礼/约会/资产赠礼/关系推进/亲密行为共用同一结果卡。
- `src/web/interactions.css`：新增完整结果卡样式、亲密度英雄区、进度条、六种行动色、成本徽标、阻塞提示、历史行、深色主题与窄屏断点；移除结果弹窗对旧双栏壳的依赖，所有新增可见字号不低于 13px。
- `src/web/i18n.interactions.beta.js`：新增亲密度、六个行动、结果卡、亲密历史、家庭规划、错误与确定关系对白文案，覆盖 en-GB、zh-CN、zh-TW、ko-KR、de-DE、es-ES、fr-FR、ru-RU、ja-JP、pt-BR、pt-PT 共 11 种界面语言。
- `tests/test_life_interactions.py`、`tests/test_life_interactions_api.py`、`tests/test_life_interactions_polish.py`、`tests/test_life_interactions_beta.py`：新增 schema 6 迁移、确定关系解锁、双资源扣除、阶段门槛、家庭规划、聊天/赠礼/约会亲密度积累、API 端点与单栏结算卡/条件式亲密标签前端契约；修正旧测试中与 `future_plan` 仅夫妻可用相矛盾的断言。
- 资产赠送结果补齐 `kind="asset_gift"`，修复统一结算卡把成功赠礼误标为“交谈”的问题，并在领域测试中锁定该判别字段。
- 产品版本、页面标题、窗口标题、桌面宿主、README 与文档同步为 V2.8.9eBeta / `2.8.9.5` / `63-dev`。

### 关键决策

- 亲密度是确定关系的独立资源，不并入熟悉、好感、信任、吸引、尊重五维；这样既能让恋爱行为有双向成本，也不会改变既有社交阶段门槛。
- 亲密行为全部由服务端判定阶段、行动力、亲密度和增益，前端只渲染 `intimacy_options` 投影；不可用的行动保留卡片并说明原因，不静默隐藏。
- “谈论未来”只对夫妻开放并写入 `family_plan_discussed`，作为后续子女系统的稳定标记；分手或离婚必须清除，避免旧关系污染新关系。
- 结果卡采用单栏信息流，不再使用“左内容、右空白”的双栏壳；对白是主视觉，数值与状态作为次级信息，确认按钮只在底部出现一次。

### 改动文件

| 文件 | 作用 |
| --- | --- |
| `src/tools/life_interactions.py` | schema 6、亲密度资源、六个亲密行为、阶段门槛与 API 领域逻辑 |
| `src/fm_odds_web.py` | `/api/life/interactions/intimacy` 与关系投影 |
| `src/web/interactions_page.js` | 条件式亲密标签、亲密度面板、单栏结果卡与提交处理 |
| `src/web/index.html` | 单栏结果弹窗结构 |
| `src/web/interactions.css` | 结果卡、亲密度面板、行动色与响应式样式 |
| `src/web/i18n.interactions.beta.js` | 11 语言亲密度、亲密行为、结果卡与确定关系文案 |
| `tests/test_life_interactions*.py` | 领域、API、i18n 与前端契约回归 |
| `README*.md`、`CHANGELOG.md`、`docs/development/*`、`docs/FEATURE_INDEX.md`、`docs/RUNTIME_CONTRACTS.md`、`docs/ARCHITECTURE.md` | 发布、开发与契约文档 |

### 验证

- `node --check src/web/interactions_page.js`、`node --check src/web/i18n.interactions.beta.js`、`node --check src/web/app.js` 通过。
- `py -m py_compile src/tools/life_interactions.py src/tools/preview_cup_odds.py src/fm_odds_web.py` 通过。
- `py -X utf8 -m pytest -q tests/test_life_interactions.py tests/test_life_interactions_api.py tests/test_life_interactions_polish.py tests/test_life_interactions_beta.py tests/test_i18n_static.py tests/test_life_system.py` → **148 passed in 16.64s**。
- 打包前工程快照：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.9dBeta-r62-before-2.8.9e-20261019-014423`。
- `dotnet build src/desktop/WebViewHost.csproj -c Release` → **0 警告、0 错误**；宿主 FileVersion `2.8.9.5`，ProductVersion `V2.8.9eBeta`，窗口标题包含 `FMSDD V2.8.9eBeta`。
- `py -X utf8 scripts/build_single_exe.py` 构建成功；`dist/FMSDD-V2.8.9eBeta.exe` 为 **78,717,734 字节**，FileVersion `2.8.9.5`、ProductVersion `V2.8.9eBeta`，SHA-256 `9359EDE8F0F1335DA00BF81E5F8870D8708D94C3DF634EC49F2D99172E74A24F`。
- CArchive 内嵌校验：共 **635** 条目、PYZ **298** 模块，`web/`、`assets/`、`desktop_host/` 共 **556** 个资源文件与当前源码逐字节一致（缺失 0、差异 0），两个原生 DLL 亦一致；`/api/life/interactions/intimacy`、`V2.8.9eBeta`、`63-dev` 均已进入包内；内嵌宿主包含 `FMSDD V2.8.9eBeta`，不包含 `FMSDD V2.8.9dBeta`。
- 源码运行包目录共 `1045` 个文件；压缩包生成成功，最终大小与 SHA-256 记录在 `dist/FMSDD-V2.8.9eBeta-SHA256SUMS.txt` 和第 63 轮改动总结中，避免在包内写入自引用哈希。

### 遗留问题

- 本轮未启动 Football Manager、Hook、真实存档或成品 EXE；结果卡、亲密度面板和窄屏布局需在成品验收时再做真实渲染复核。
- 亲密行为目前只使用模板对白与确定性增益，尚未接入子女系统、怀孕/生育状态或 AI 对话。

## 第 62 轮（V2.8.9dBeta · 聊天工作区、按钮对比度与只读经理声望，2026-10-19）

### 需求

- 赠送与邀请按钮只在鼠标悬停时可见，需要恢复始终可见的操作层级；礼物与行动选项增加分类背景色。
- 约会选项重复展示“行动力”，应统一为右上角闪电图标 + 大号点数；人物关系等级需要更清晰的底色与颜色标识。
- 交谈界面空间利用率低、按钮不突出，需要重制为带聊天记录和输入框的微信式消息界面，并为后续 AI 接入预留结构。
- 玩家名称改用统一字体；声望从玩家可分配属性改为读取 FM 主教练声望。
- 版本迭代到 V2.8.9dBeta，补齐开发日志、错误日志与成品验证。

### 实现

- `src/web/interactions.css`：把 `--int-*` 主题变量作用域扩展到聊天、结果、选择、档案与行动力流水弹窗；新增微信式聊天布局、分类强调色、关系徽标底色、聊天奖励条与按钮高对比样式。所有新增可见文本保持至少 13px。
- `src/web/interactions_page.js`：新增 `chatDialog()`、`chatThreadRows()`、`chatThreadMarkup()`、`renderChatDialog()`、`openChatDialog()` 与 `closeChatDialog()`；交谈入口改为打开消息弹窗。表单提交门禁加入 `chatDialog()?.contains(form)`，修复发送按钮无法提交。
- 聊天时间线保存 `message`、`dialogue` 与 `reply_mode=template`；发送后保留当前话题并滚动到最新消息。旧记录没有原文时按话题生成兼容回复；互动增益统一放入 `.interaction-chat-reward` 结果条。
- 约会卡删除底部重复的行动点文本，只在右上角显示闪电与大号点数；礼物和约会人物头卡使用分类渐变背景，关系阶段徽标新增 `acquaintance`、`ambiguous` 等明确色阶。
- `src/tools/life_interactions.py`：`PROFILE_ATTRIBUTE_KEYS` 收缩为 `appearance/ability/charisma`；`reputation` 保留为旧档兼容字段，不再参与点数消费。新增 `MAX_CHAT_MESSAGE_CHARS = 500`，`chat_plan()` 接收并持久化玩家消息。
- `src/tools/preview_cup_odds.py`：新增 `_manager_reputation()`，按当前 `GameLayout` 的 staff 完整对象偏移读取 current/domestic/world 声望；没有已验证偏移时显式返回不可用，不猜测地址。所有经理构建分支与同存档回退分支均携带声望投影。
- `src/fm_odds_web.py`：互动视图新增 `manager_reputation` 与 `manager_identity`；聊天 API 截取并传递最多 500 字消息。
- `src/web/i18n.interactions.polish.js`：新增聊天与经理声望文案，覆盖 en-GB、zh-CN、zh-TW、ko-KR、de-DE、es-ES、fr-FR、ru-RU、ja-JP、pt-BR、pt-PT 共 11 种界面语言。
- `scripts/build_single_exe.py`：打包前自动把 `src/desktop/bin/Release/net48/FMODD.WebViewHost.exe` 同步到运行资源，并校验宿主内嵌窗口标题包含当前产品版本，防止旧宿主被封装进新成品。
- 产品版本、页面标题、桌面宿主与文档同步为 V2.8.9dBeta / `2.8.9.4` / `62-dev`。

### 关键决策

- 声望是 FM 主教练的只读事实，不再作为可购买、可分配的玩家属性；旧档案字段保留但不再返还可分配点数，避免改变旧档预算并造成负余额。
- 聊天采用模板对话外壳，当前不保存自由生成结果；消息原文与模板回复均进入时间线，后续接入 AI 时只需替换回复提供者，不改消息存储和 UI。
- 关系与礼物选项的颜色来自类别语义，不新增任意主题色；身份与关系状态仍由服务端真值决定。
- FM24 未提供已验证的 staff 声望偏移时显示“暂无 FM 数据”，不使用人物 reputation 或俱乐部 reputation 冒充经理声望。

### 改动文件

| 文件 | 作用 |
| --- | --- |
| `src/web/interactions_page.js` | 聊天弹窗、聊天历史、发送门禁、奖励条、关系徽标、FM 声望投影与档案字体 |
| `src/web/interactions.css` | 弹窗主题变量、微信式聊天、分类色、按钮和徽标对比度 |
| `src/web/index.html` | 聊天弹窗容器与页面版本标题 |
| `src/web/i18n.interactions.polish.js` | 11 语言聊天与经理声望文案 |
| `src/tools/life_interactions.py` | 三项可分配属性、消息持久化与时间线 |
| `src/tools/preview_cup_odds.py` | 当前经理声望读取与经理分支投影 |
| `src/fm_odds_web.py` | 互动视图与聊天 API 投影 |
| `src/desktop/WebViewHost.csproj`、`scripts/build_single_exe.py` | 桌面宿主版本同步与打包前标题校验 |
| `tests/test_life_interactions.py`、`tests/test_life_interactions_api.py`、`tests/test_life_interactions_polish.py`、`tests/test_life_system.py` | 档案迁移、聊天消息、经理声望和前端契约回归 |
| `CHANGELOG.md`、`README*.md`、`docs/development/*`、`docs/FEATURE_INDEX.md`、`docs/RUNTIME_CONTRACTS.md` | 发布、开发与契约文档 |

### 验证

- `node --check src/web/interactions_page.js`、`node --check src/web/i18n.interactions.polish.js`、`node --check src/web/app.js` 通过。
- `py -m py_compile src/tools/life_interactions.py src/tools/preview_cup_odds.py src/fm_odds_web.py` 通过。
- `py -X utf8 -m pytest -q tests/test_life_interactions.py tests/test_life_interactions_api.py tests/test_life_interactions_polish.py tests/test_life_interactions_beta.py tests/test_life_system.py` → **134 passed in 16.42s**。
- `dotnet build src/desktop/WebViewHost.csproj -c Release` → **0 警告、0 错误**；宿主文件版本 `2.8.9.4`，产品版本 `V2.8.9dBeta`。
- `py -X utf8 scripts/build_single_exe.py` 构建成功；`dist/FMSDD-V2.8.9dBeta.exe` 为 **78,694,649 字节 / 75.05 MiB**，FileVersion `2.8.9.4`、ProductVersion `V2.8.9dBeta`，SHA-256 `32C7C32B292B7BE35CE087DDE30B2611185E25321A3E1DB1FD4A97FB2533A29F`。
- CArchive 内嵌校验：`desktop_host/FMODD.WebViewHost.exe`、`web/app.js`、`web/index.html`、`web/interactions_page.js`、`web/interactions.css` 与当前源码逐字节一致；宿主同时包含 `FMSDD V2.8.9dBeta`，不再包含 `FMSDD V2.8.9cBeta`。
- 源码运行包目录共 `1045` 个文件；最终 ZIP 的哈希记录在 `dist/FMSDD-V2.8.9dBeta-SHA256SUMS.txt` 与第 62 轮改动总结中。
- 最终打包前工程快照：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.9cBeta-r61-before-2.8.9d-20261019-012116`。该目录中的源码已包含第 62 轮实现，`dist` 同时保留 V2.8.9cBeta 成品与源码包，可用于核对或恢复上一版发布物。

### 遗留问题

- FM24 的 staff 声望偏移尚未验证时，界面只能显示不可用状态；需要后续实机布局确认。
- 本轮未启动 Football Manager、Hook、真实存档或成品 EXE，聊天界面与头像、声望显示需在成品验收时复核。

## 第 61 轮（V2.8.9cBeta · 关系栏、关系网头像、住宅卡与可视化选择，2026-10-19）

### 需求

- 关系栏因新增删除按钮而宽度不足，关系标签被截断；移除关系卡片右上角的排他关系徽标，并让好感度按等级显示不同颜色。
- 关系网中的人物头像没有正确显示，需要与人物档案使用同一头像来源。
- 住宅入住操作繁琐：长下拉框、窄行列表与确认入住分离。改为一行两张可选资产卡，选中后再入住，并显示入住者头像、姓名与关系等级。
- 赠送礼物和约会活动是逐行长列表，操作体验差。改为点击后打开大型可视化选择弹窗。
- 版本迭代到 V2.8.9cBeta，补齐开发日志、错误日志、契约、测试与成品。

### 实现

- `src/web/interactions.css`：人物关系栏改为 `minmax(310px, 350px)`；新增 `.interaction-relation-affection` 五档颜色；关系网人物头像复用 `.interaction-avatar` 规格；新增住宅双列网格、入住者行、选择弹窗与响应式断点。新增可见字号均不低于 13px。
- `src/web/interactions_page.js`：`affectionTone()` 按 0/20/40/60/80 阈值返回 distant、guarded、warm、close、devoted；关系行不再渲染排他徽标；关系网改用 `portraitMarkup(row.person)`。
- `src/tools/life_interactions.py`：`residence_rows()` 新增 `occupants`。每位入住者包含去地址化的 `person` 摘要（ID、姓名、球队、性别）与 `relationship` 摘要（社交阶段、恋爱阶段、保密情人），前端不再从关系列表反查入住者。
- `renderResidencePanel()`：住宅卡改为按钮式双列卡；选中状态独立于当前入住状态；入住按钮只在选中可用住宅且不同于当前住宅时启用；迁出按钮保留。卡片显示入住者头像、姓名、球队与关系徽标。
- `giftGroups()`：同名、同类别、同价值的背包物品聚合为一张卡并累计数量；提交仍使用第一件真实库存的 `item_id`，不伪造合并库存。
- 新增 `#life-interactions-gift-dialog` 与 `#life-interactions-date-dialog`。`renderGiftPicker()` 展示礼物类别、价值、库存数量与 NPC 偏好；`renderDatePicker()` 展示活动图标、AP、偏好与朋友阶段门槛。点击遮罩可关闭，语言切换与状态变化会重绘已打开的弹窗。
- 移除赠礼与约会的下拉选择及 `syncDateAction()` 监听；确认操作继续通过 `performAction()` 的 `requestBusy` 防重复提交。
- 修复空活动列表：先求 `dateCosts`，为空时摘要返回 0，避免 `Math.min()`/`Math.max()` 产生 `Infinity`/`-Infinity`。
- `src/web/i18n.interactions.beta.js`：新增 `visualChoices` 文案组，覆盖 11 种界面语言，并与既有 `copy` 合并。
- 产品版本、页面标题、桌面宿主与文档同步为 V2.8.9cBeta / `2.8.9.3` / `61-dev`。

### 关键决策

- 关系栏仍保留删除按钮，但不把排他状态做成卡片角标；排他规则属于关系系统，状态已在关系标签与关系进度中体现，重复徽标只会挤占名称空间。
- 关系网头像不单独维护状态，直接复用档案头像函数，确保显示开关、UID 偏移和加载失败回退只有一套实现。
- 住宅卡片以“选择”与“当前入住”两种状态分离：已入住但容量已满的住宅仍可被当前住户选中；其他满员住宅禁用。入住提交仍由服务端复核容量、归属、自住模式与建设状态。
- 赠礼聚合只改变展示，不改变库存真值；同组内每件物品都有独立 ID，提交时必须落在真实背包条目上。
- 约会与赠礼弹窗只负责选择，不提前扣 AP 或库存；确认按钮沿用统一动作事务。这样关闭弹窗不会产生副作用，重复点击也由请求锁拦截。

### 改动文件

| 文件 | 作用 |
| --- | --- |
| `src/tools/life_interactions.py` | 住宅投影新增入住者摘要 |
| `src/web/interactions_page.js` | 关系栏、好感分档、关系网头像、住宅卡、赠礼/约会选择弹窗 |
| `src/web/interactions.css` | 关系栏宽度、好感颜色、住宅双列、弹窗与响应式样式 |
| `src/web/index.html` | 赠礼与约会选择弹窗容器、页面版本标题 |
| `src/web/i18n.interactions.beta.js` | 11 语言可视化选择与住宅文案 |
| `tests/test_life_interactions_beta.py` | 入住者投影与界面契约回归 |
| `src/fm_odds_web.py`、`src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj`、`src/web/app.js` | 版本与宿主同步 |
| `CHANGELOG.md`、`README*.md`、`docs/development/*`、`docs/FEATURE_INDEX.md`、`docs/RUNTIME_CONTRACTS.md` | 发布与开发文档 |

### 验证

- `node --check src/web/interactions_page.js`、`node --check src/web/i18n.interactions.beta.js` 通过。
- `py -X utf8 -m py_compile src/tools/life_interactions.py src/fm_odds_web.py src/fmodd_desktop.py` 通过。
- 人物互动基础、API、beta 与 polish：`57 passed`。
- 生活系统：`73 passed`。
- i18n audit、frontend、API contract、desktop host 与 static：`45 passed`。
- 桌面宿主：`dotnet build src/desktop/WebViewHost.csproj -c Release` 成功，0 警告、0 错误；FileVersion `2.8.9.3` / ProductVersion `2.8.9cBeta`。
- 单文件 EXE 只读复核：CArchive 635 条目、PYZ 298 模块；`web/`、`assets/`、`desktop_host/` 共 556 个资源文件与仓库逐字节一致，缺失 0、差异 0。
- PYZ 内确认 `V2.8.9cBeta`、`61-dev`、`occupants`；桌面宿主包含 UTF-16 标题 `FMSDD V2.8.9cBeta`，不含旧标题。
- 源码运行包：1,045 个文件 / 194.2 MiB，ZIP 完整性测试通过。
- 完整 `tests/test_i18n_locale_packs.py` 仍有 3 项既有失败，均来自旧 V2.8.0 公告文案（es-ES 标题重复、de-DE 英文泄漏判定、zh-TW 公告用词），与本轮关系栏/住宅/选择弹窗无关，本轮未扩大范围修改。

### 遗留问题

- 关系栏在小于 1080px 的窄窗口仍按既有断点折叠为单列；这是响应式回退，不是关系标签截断。
- 本轮未启动 Football Manager、Hook、真实存档或成品 EXE，真实游戏内头像与住宅数据仍需在成品验收时复核。

## 第 60 轮（V2.8.9bBeta · 联系人管理、礼物商店与互动工作台深化，2026-10-18）

### 需求

- 人物关系栏增加删除联系人的操作，并明确永久赠礼不会被收回。
- 物品一级菜单增加“礼物”二级页，可购买礼物并在人物互动中赠送。
- 重构互动操作界面，把关系推进等操作收进二级、三级菜单，修复聊天界面右侧空白。
- 明确从初识到朋友、朋友到好友等阶段的具体条件，解决熟悉度已满但仍无法升级的困惑。
- 在互动操作右侧增加“名下资产”，展示 NPC 收到的房产、车辆与永久赠礼。
- 行动力卡增加可打开的消耗与获得明细。
- 总览增加夫妻、情侣、情人、知己、好友与朋友的关系网。
- 版本迭代到 V2.8.9bBeta，补齐开发日志、错误日志、契约与成品。

### 实现

- `life_interactions.py` 的 schema 升至 `5`，新增 `action_point_ledger`。`_record_action_point_change()` 在聊天、物品赠礼、资产赠礼、约会、关系行动、每周恢复和 CDK 加点时记录日期、变化值、变动后余额、原因、人物与详情；`action_points()` 返回最近 100 条与总条数。
- 新增 `person_owned_assets()`，从 `gifted_assets` 按人物投影房产、车辆、数量、总价值与永久标记；`public_view()` 把结果放入每段关系的 `owned_assets`，不把资产重新写回玩家组合。
- 新增 `remove_person()` 与 `POST /api/life/interactions/remove`：移除人物快照、五维关系、住宅分配和该人物时间线，保留全部 `gifted_assets`，并在返回值中报告保留赠礼数与删除时间线条数。前端删除按钮使用统一确认弹窗，删除后由服务端回传完整工作区。
- 新增 `relationship_progress()`：服务端直接投影下一社交阶段与下一恋爱阶段，并为每一项返回 `current`、`required`、`met`。前端关系进度标签只渲染这份投影，不再自行推断门槛。
- `interactions_page.js` 增加人物页的“人物档案 / 互动 / 名下资产”和互动页的“互动首页 / 关系进度”二级标签；破坏性关系操作收进 `<details>` 更多操作。聊天、赠礼、约会改为三列网格，右侧空白由全宽与 `min-width: 0` 约束修复。
- 总览新增关系网卡，按配偶、情侣、保密情人、知己、好友、朋友选择人物最高关系分组，组内点击直接切换人物并打开档案。
- `club_economy.py` 增加 8 个 `family="gift"` 的商品 SKU，分别对应书籍、时尚、科技、美食、运动、音乐、艺术和奢侈品；购买沿用既有账户余额、库存与商店事务，礼物进入背包。
- 新增 `gift_shop_page.js`、`gift_shop.css` 与 `i18n.gifts.js`。礼物页从 `/api/state` 的商品目录读取 SKU，支持分类、数量、余额校验、二次确认与购买后刷新；互动首页提供直达入口。
- `index.html` 在物品菜单下加入 `data-page="gift-shop"`，`app.js` 注册页面渲染；新增文案覆盖 11 种界面语言。
- 产品版本、页面标题、桌面宿主和文档同步为 V2.8.9bBeta / `2.8.9.2` / `60-dev`。

### 关键决策

- 删除联系人是“停止互动”，不是撤销赠礼。永久资产一旦赠送就属于对方，因此删除只清除关系与缓存，不回滚 `gifted_assets`，并在确认框中提前说明。
- 关系门槛继续由服务端单一拥有。前端展示的 `current/required/met` 全部来自 `relationship_progress()`，避免界面条件与真正判定出现两套数值。
- 行动力明细只记录有意义的非零变化，旧档没有流水时补空数组而不伪造历史；界面最多显示 100 条，避免长档把状态响应撑大。
- 人物页与互动页使用二级标签而不是继续增加长滚动页面。关系推进、分手和离婚不与日常聊天混排，降低误操作。
- 礼物使用普通商品库存链路，不建立第二套钱包或背包；购买与赠送仍分别由商店和人物互动事务负责。

### 改动文件

| 文件 | 作用 |
| --- | --- |
| `src/tools/life_interactions.py` | schema 5、行动力流水、关系门槛投影、名下资产、删除联系人 |
| `src/tools/club_economy.py` | 8 类礼物商品与目录 |
| `src/fm_odds_web.py` | 删除联系人 API、互动状态投影接线、版本 |
| `src/web/interactions_page.js`、`src/web/interactions.css` | 二级标签、关系进度、关系网、名下资产、三列互动布局 |
| `src/web/gift_shop_page.js`、`src/web/gift_shop.css` | 礼物商店页面与响应式布局 |
| `src/web/i18n.gifts.js`、`src/web/i18n.interactions.beta.js` | 礼物、删除、进度、资产、流水与关系网文案 |
| `src/web/index.html`、`src/web/app.js` | 礼物二级菜单、页面注册、版本 |
| `src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj` | 窗口标题与桌面宿主版本 |
| `tests/test_life_interactions_beta.py`、`tests/test_life_interactions_api.py`、`tests/test_i18n_static.py` | 本轮行为、API 与本地化契约 |

### 验证

- JavaScript：`node --check` 通过 `interactions_page.js`、`gift_shop_page.js`、`i18n.gifts.js`、`i18n.interactions.beta.js`、`app.js`。
- Python：相关模块 `py_compile` 通过。
- 人物互动、API、polish、i18n 静态与生活系统聚焦测试：**101 passed**。
- 礼物元数据、互动 beta、i18n API/audit/frontend：**44 passed**。
- 桌面宿主 i18n、i18n 静态与生活系统：**83 passed**。
- 已知遗留：完整 `test_i18n_locale_packs.py` 仍有 3 项与旧 V2.8.0 公告文案相关的既有失败（es-ES 重复标题、de-DE 英文泄漏判定、zh-TW 用词检查），不属本轮礼物或互动改动，未扩大范围修改。
- 本轮未启动 Football Manager、Hook、真实存档或成品 EXE。

### 备份

- 动手前备份：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.9aBeta-r59-before-2.8.9b-20261018-233232`，保留 V2.8.9aBeta / `59-dev` 工程与成品基线。

### 交付与打包

- **桌面宿主**：`dotnet build src/desktop/WebViewHost.csproj -c Release` 成功（0 警告、0 错误），回拷为 `src/desktop_host/FMODD.WebViewHost.exe`；199,680 字节，FileVersion `2.8.9.2` / ProductVersion `2.8.9bBeta`，SHA-256 `11D061BF5CBE830C8164213E11258E43043B9F6E709DE2A8812C5B646888C9AD`。
- **单文件 EXE**：`py -X utf8 scripts/build_single_exe.py` 成功生成 `dist/FMODD.exe`，复制为 `dist/FMSDD-V2.8.9bBeta.exe`；78,672,800 字节，FileVersion `2.8.9.2` / ProductVersion `V2.8.9bBeta`，SHA-256 `F3D855741C63B9A28AE32074AB84A30CD90766417D9BD338C4AB941496A50280`。
- **成品只读复核**：`CArchiveReader` 共 635 条目、PYZ 298 模块；`web/`、`assets/`、`desktop_host/` 共 556 个资源文件与仓库源文件逐字节一致（缺失 0、差异 0），原生 DLL 亦一致；PYZ 内确认 `V2.8.9bBeta`、`60-dev`、`/api/life/interactions/remove`、`remove_person`、`relationship_progress`、`person_owned_assets`、`action_point_ledger` 与礼物 SKU；桌面宿主含 UTF-16 标题 `FMSDD V2.8.9bBeta`，不含旧标题。未启动成品 EXE。
- **源码运行包**：在代码与文档冻结后执行 `py -X utf8 scripts/build_source_runtime_package.py`，生成 1,045 个文件、194.2 MiB 的 `dist/FMSDD-V2.8.9bBeta-source-runtime`；ZIP 大小与 SHA-256 记录在外部 `dist/FMSDD-V2.8.9bBeta-第60轮改动总结.md` 与 `dist/FMSDD-V2.8.9bBeta-SHA256SUMS.txt`，避免包内文档自引用。

## 第 59 轮（V2.8.9aBeta · 球员搜索分页、头像编号偏移与永久互动权益，2026-10-18）

### 需求

- 寻找球员桌面结果改为每行两位球员，并利用结果区下方空间加入翻页，避免一次只能看到少量球员。
- 在球员头像包设置中增加文件编号偏移：默认 `0`；`+1` 读取 `球员 UID + 1`，`-1` 读取 `球员 UID - 1`，并给出清晰示例。
- 新增 CDK `日理万机`：永久提高行动点上限 12，并每周增加 24 点行动点恢复。
- 新增 CDK `魅力四射`：兑换后行动获得的 NPC 好感等关系值乘以 10。
- 版本迭代到 V2.8.9aBeta，补齐开发日志、错误日志、契约与成品。

### 实现

- `interactions_page.js` 把搜索状态扩展为 `searchPage/searchPageCount/searchPageSize`，默认每页 30 人；搜索、筛选与页码一起提交。结果容器在桌面固定双列，分页栏放在结果滚动区之外，只有一页时不显示；翻页请求失败或筛选变化时清空旧页数，成功后按服务端回填页码、总页数并滚回顶部。
- `interactions.css` 将结果网格改为 `repeat(2, minmax(0, 1fr))`，结果区使用受控高度与内部滚动，分页栏使用三段式网格；760px 以下回退单列与可换行分页，所有新增可见字号不低于 13px。
- `player_portraits.py` 先计算 `face_uid = player_id + portrait_uid_offset`，再沿用既有 XML/graphics 查找；玩家 UID 仍作为请求身份，头像文件名编号独立偏移。`app_settings.py` 新增 `portrait_uid_offset` 持久化、旧设置容错读取和 `-999..999` 服务端校验。
- `GET /api/player-avatar` 接受可选 `portrait_offset` 查询参数，`POST /api/player-portraits/offset` 保存全局设置并清理服务端头像缓存；前端保存后更新设置状态、刷新人物工作区并提示实际保存值。设置卡展示默认值、正负方向示例和合法范围。
- `club_economy.CDK_CODES` 新增两个纯权益码。`AccountApplicationService.redeem_cdk` 对权益码要求当前存档作用域，并通过 `update_documents()` 在同一账户事务内写入 `economy.cdk_redemptions` 与 `life_interactions.entitlements`；`resolve_cdk_code()` 对缺失 `amount` 的权益码不再执行金额转换。
- `life_interactions` schema 升至 `4`，新增 `entitlements`。`日理万机` 激活时把上限 `12→24`、每周恢复 `6→30`，首次兑换补 12 点当前行动力并封顶；`魅力四射` 把正向五维增量乘以 10。聊天、物品赠礼、约会、关系推进、资产赠礼与资产赠礼预览统一使用 `_relationship_gain_multiplier()`。
- 11 种界面语言新增分页、头像偏移、权益与兑换码说明；产品版本、页面标题、桌面宿主和文档同步为 V2.8.9aBeta / `2.8.9.1` / `59-dev`。

### 关键决策

- 每页人数固定在服务端上限 30，而不是前端无限堆叠。这样既利用双列空间，也让分页和响应体积保持可预测；滚动只发生在结果区，翻页按钮始终可见。
- 头像偏移按整数相加实现，不尝试猜测文件名规则。示例直接展示 `200001 + 1 = 200002` 与 `200001 - 1 = 200000`；设置接口严格拒绝布尔值、小数、非整数和越界值，读取旧设置时才做安全夹取。
- 权益码属于存档级永久状态，不能只当作一次钱包交易。兑换记录和权益状态必须同事务提交；纯权益码先要求连接存档，避免“兑换成功但不知道写入哪个存档”的歧义。
- `魅力四射` 只放大正向关系增量，分手、离婚等负向惩罚保持原值；预览和正式提交共用服务端倍率，避免玩家看到的结果与实际结算不一致。
- 搜索分页、头像偏移和权益只扩展人物互动文档与既有头像路由，不改原生 FM 存档、不引入 Hook、不启动游戏进程。

### 验证

- `node --check src/web/app.js`、`node --check src/web/interactions_page.js`、`node --check src/web/i18n.interactions.polish.js`、`node --check src/web/i18n.settings.js` 均通过。
- `py -X utf8 -m py_compile src/tools/app_settings.py src/tools/player_portraits.py src/tools/life_interactions.py src/tools/club_economy.py src/tools/account_application.py src/fm_odds_web.py` 通过。
- `py -X utf8 -m pytest tests/test_bank_cdk_redemption.py tests/test_player_portraits.py tests/test_settings_frontend_optimization.py tests/test_life_interactions.py tests/test_life_interactions_polish.py tests/test_life_interactions_api.py tests/test_account_application.py tests/test_life_system.py -q` → **167 passed**。
- 覆盖重点：30 人分页与页码回填、双列布局契约、头像 UID `+1/-1` 与越界拒绝、纯权益码无银行流水、权益与兑换记录同事务、重复兑换幂等、行动力上限/恢复投影、关系倍率仅作用于正向增量、11 语言文案与版本断言。
- 本轮未启动 Football Manager、Hook、真实存档或成品 EXE。

### 文件

| 文件 | 变更 |
| --- | --- |
| `src/web/interactions_page.js`、`src/web/interactions.css` | 双列搜索结果、每页 30 人、固定分页栏、翻页回顶与响应状态 |
| `src/web/app.js`、`src/web/app.css` | 头像编号偏移设置卡、保存/刷新流程、设置布局与样式 |
| `src/web/i18n.settings.js`、`src/web/i18n.interactions.polish.js` 及 `de/es/fr/ja/pt-BR/pt-PT/ru/tw` 语言包 | 分页、头像偏移、权益说明和兑换码文案的 11 语言覆盖 |
| `src/tools/app_settings.py`、`src/tools/player_portraits.py` | `portrait_uid_offset` 持久化、校验、缓存清理与文件编号解析 |
| `src/tools/club_economy.py`、`src/tools/account_application.py` | 两个权益码、缺失金额兼容、原子账户事务与纯权益码存档要求 |
| `src/tools/life_interactions.py` | schema 4、`entitlements`、动态行动力上限/恢复、关系增益倍率与预览/结算统一 |
| `src/fm_odds_web.py` | 分页参数、头像偏移路由、权益兑换接入与 11 语言设置投影 |
| `src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj`、`src/web/index.html` | 产品、窗口与桌面宿主版本同步到 V2.8.9aBeta / `2.8.9.1` |
| `scripts/build_single_exe.py` | 从桌面项目读取四段 `FileVersion`，修复单文件 EXE 的 `.0` 版本漂移 |
| `tests/test_bank_cdk_redemption.py`、`tests/test_player_portraits.py`、`tests/test_settings_frontend_optimization.py`、`tests/test_life_interactions*.py`、`tests/test_account_application.py`、`tests/test_life_system.py` | 本轮行为、布局、权益、事务与版本文档回归 |
| `CHANGELOG.md`、`README.md`、`README.zh-CN.md`、`README.ko-KR.md`、`docs/development/DEVELOPMENT.md`、`docs/FEATURE_INDEX.md`、`docs/RUNTIME_CONTRACTS.md`、`docs/development/ERROR_LOG.md` | 当前版本说明、功能索引、运行时契约与开发/错误日志 |

### 备份

- 动手前备份：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.9Beta-r58-before-2.8.9a-20261018-223933`，共 2,087 个文件、596,757,700 字节（569.1 MiB），保留 2.8.9Beta / `58-dev` 工程与成品基线。

### 交付与打包

- **桌面宿主**：`dotnet build src/desktop/WebViewHost.csproj -c Release` 成功（0 警告、0 错误），回拷为 `src/desktop_host/FMODD.WebViewHost.exe`；199,680 字节，FileVersion `2.8.9.1` / ProductVersion `2.8.9aBeta`，SHA-256 `578D937EC1888E43C1593F86132BBEAD11A5D6E131D6FC4215D7814A70A2BA56`。
- **单文件 EXE**：`py -X utf8 scripts/build_single_exe.py` 成功生成 `dist/FMODD.exe`，复制为 `dist/FMSDD-V2.8.9aBeta.exe`；78,633,288 字节，FileVersion `2.8.9.1` / ProductVersion `V2.8.9aBeta`，SHA-256 `E9904DB1BBB5A9B829E637D0F1A262C76FE7E2FBCB02BE2FBF0A9A9B67B09817`。
- **成品只读复核**：`CArchiveReader` 共 631 条目、PYZ 298 模块；`web/`、`assets/`、`desktop_host/` 与 `tools/` 共 554 个资源文件同仓库源文件逐字节一致（缺失 0、差异 0），PYZ 内确认为 `V2.8.9aBeta` 与 `59-dev`，并含 `portrait_uid_offset`、两个权益码、权益 schema 与搜索符号；桌面宿主含 UTF-16 标题 `FMSDD V2.8.9aBeta`、不含旧标题。未启动成品 EXE。
- **源码运行包**：在所有代码与文档冻结后执行 `py -X utf8 scripts/build_source_runtime_package.py`；包内文件数、ZIP 大小与 SHA-256 记录在 `dist/FMSDD-V2.8.9aBeta-第59轮改动总结.md` 与 `dist/FMSDD-V2.8.9aBeta-SHA256SUMS.txt`，避免包内文档自引用。

## 第 58 轮（V2.8.9Beta · 头像设置整合、多条件搜索与人物界面调优，2026-10-18）

### 需求

- 将“球员头像包”设置移入“显示”分类，与“读取球员头像”归为一类，并重新设计设置界面，使头像路径的配置方法足够明确。
- 放大人物关系列表、人物档案及搜索结果中的球员头像；统一档案姓名与 UID 字体；缩窄左侧关系栏，为右侧档案和互动工具让出宽度。
- 寻找球员支持单字或姓名子串搜索，并增加国籍、俱乐部、年龄等筛选条件，允许从俱乐部方向查找球员。
- 版本迭代到 V2.8.9Beta，维护开发日志、错误日志并重新构建成品。

### 实现

- 头像来源卡与头像显示开关合并到 `.portrait-source-setting`，设置分类由 `SETTINGS_TAB_GROUPS` 固定归入 Display；设置弹窗宽 980px，分类内容采用双列布局，窄屏回退单列。
- 头像卡新增当前 graphics 来源、`config.xml` 数量、三步配置说明、常见 `faces\face_<UID>.png` 规则和姓名缩写回退；深色主题补齐卡片、状态、步骤与按钮样式。
- 人物头像扩充为常规 90×90、列表 58×58、档案 92×92；档案姓名与 UID 使用 `font-family: inherit`。人物工作区改为 `minmax(236px, 272px) minmax(0, 1fr)`，关系栏不再挤占档案主体。
- 搜索页使用 `.interaction-search-layout` 左右分栏：左侧姓名查询与结果，右侧国籍、性别、18 岁以上年龄范围、俱乐部候选及重置操作；已选俱乐部、空结果与年龄下限均保留回显。
- `/api/life/interactions/search` 接受 `query`、`nationality_id`、`gender`、`min_age`、`max_age`、`club_id` 与分页参数。俱乐部候选来自 `/api/world-clubs?search=`，球员过滤由 `world_clubs.read_native_world_club_player_ids()` 取得原生关联名单 UID 后交给既有世界球员索引。
- `search_players_by_uids()` 在 UID 候选集上补回姓名条件：非空查询同时检查规范化姓名与去分隔符紧凑姓名，空查询仍保留“仅按俱乐部浏览”的行为，与普通搜索的匹配口径一致。
- 新增设置、搜索、年龄、俱乐部、空结果与头像步骤文案，覆盖 11 种界面语言；所有占位符保持同构。

### 关键决策

- 头像包来源与显示开关必须共用同一张卡片和同一套 `player_portraits` 设置，避免玩家把“显示头像”误认为另有一套图片目录。
- 俱乐部筛选只读取名单 UID，不展开完整球员资料；这样既保留既有会话级 Person 索引，也避免 15 家候选俱乐部各自触发大量资料读取。
- 成年限制仍由服务端强制，前端 `min=18` 只用于输入提示；空俱乐部名单直接返回结构化零结果，不能退化为无筛选的全量搜索。
- 本次不改头像缓存协议、关系阈值、行动力或资产账本，仅扩展人物搜索投影与界面布局。

### 验证

- `node --check src/web/app.js`、`node --check src/web/interactions_page.js`、`node --check src/web/i18n.interactions.polish.js` 均通过。
- `py -X utf8 -m py_compile src/fm_odds_web.py src/tools/world_clubs.py src/tools/database_index.py src/fmodd_desktop.py` 通过。
- `py -X utf8 -m pytest -q tests/test_frontend_refresh_recovery.py tests/test_player_portraits.py tests/test_life_interactions_polish.py tests/test_life_interactions_api.py tests/test_life_interactions.py tests/test_life_system.py tests/test_database_index.py` → **281 passed**。
- 本轮未启动 Football Manager、Hook、真实存档或成品 EXE。

### 文件

| 文件 | 变更 |
| --- | --- |
| `src/tools/world_clubs.py` | 新增只读 `read_native_world_club_player_ids()`，按俱乐部关联名单返回球员 UID |
| `src/fm_odds_web.py` | 搜索 API 增加国籍/性别/年龄/俱乐部组合过滤、俱乐部名单解析与版本升级 |
| `src/tools/database_index.py` | UID 候选搜索路径补回姓名子串/单字过滤，避免俱乐部筛选覆盖姓名条件 |
| `src/web/interactions_page.js` | 左右分栏搜索、筛选卡、俱乐部候选与结果回显、头像尺寸引用 |
| `src/web/interactions.css`、`src/web/app.css`、`src/web/dark-theme.css` | 人物头像/关系栏/搜索布局与设置双列、头像来源卡及深色主题 |
| `src/web/app.js` | 头像来源与显示开关合并、Display 分类归属、头像状态说明与版本回退值 |
| `src/web/i18n.interactions.polish.js` | 11 语言设置、头像、搜索与筛选文案 |
| `src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj`、`src/web/index.html` | 窗口标题、桌面宿主与页面版本同步到 V2.8.9Beta / `2.8.9.0` |
| `tests/test_life_interactions_polish.py`、`tests/test_life_interactions_api.py`、`tests/test_life_system.py`、`tests/test_database_index.py` | 布局/11 语言契约、组合过滤、成年下限、姓名片段与单字搜索回归 |

### 备份

- 动手前备份：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.8cBeta-before-2.8.9-20261018-214119`，共 2,084 个文件、596,393,056 字节，保留 2.8.8c 工程与成品基线。

### 交付与打包

- **桌面宿主**：`dotnet build src/desktop/WebViewHost.csproj -c Release` 构建成功（0 警告、0 错误），回拷为 `src/desktop_host/FMODD.WebViewHost.exe`；199,680 字节，FileVersion `2.8.9.0` / ProductVersion `2.8.9Beta`，SHA-256 `267506C516C4ED96FFD9C7A2A299AAE7F3657CCB8D72F72CF7F3B295979E9BF8`。
- **单文件 EXE**：`py -X utf8 scripts/build_single_exe.py` 成功生成 `dist/FMODD.exe`，复制为 `dist/FMSDD-V2.8.9Beta.exe`；78,621,499 字节，FileVersion `2.8.9.0` / ProductVersion `V2.8.9Beta`，SHA-256 `571EC1AA4B22F6737DD984D02EB546574892FAB0730A5EC06520FAD0C4453BAC`。
- **成品只读复核**：`CArchiveReader` 共 631 条目、PYZ 298 模块；`web/`、`assets/`、`desktop_host/` 与 `tools/` 共 554 个资源文件同仓库源文件逐字节一致（缺失 0、差异 0），PYZ 内确认为 `V2.8.9Beta` 与 `58-dev`，且 `search_players_by_uids` 包含姓名过滤所需符号；桌面宿主含 UTF-16 标题 `FMSDD V2.8.9Beta`。未启动成品 EXE。
- **源码运行包**：`dist/FMSDD-V2.8.9Beta-source-runtime` 共 1,040 文件 / 193.9 MiB，1,002 个工程源文件同仓库逐字节一致；最终 ZIP 的字节数与 SHA-256 记录在 `dist/FMSDD-V2.8.9Beta-SHA256SUMS.txt` 与 `dist/FMSDD-V2.8.9Beta-第58轮改动总结.md`，避免包内文档自引用。

## 第 57 轮（V2.8.8cBeta · 行动力预测、球员 UID 与资产赠礼预览，2026-10-18）

### 需求

- 细化人物互动总览的行动力卡：显示当前行动点、下次恢复、恢复至上限时间与各类行动消耗明细。
- 说明设置中的“读取球员头像”含义、头像位置和配置方式。
- 在球员姓名右侧显示 FM UID。
- 资产赠送页保持当前人物选择器单行，桌面资产卡改为一行四列，金额使用紧凑单位。
- 资产赠送消耗降至 1 AP，并在卡片上展示预计好感增幅与关系等级是否提升。
- 版本迭代到 V2.8.8cBeta，维护开发日志、错误日志并重新打包。

### 实现

- `action_points()` 新增 `next_recovery_gain`、`days_until_full`、`is_full` 与 `costs` 投影；恢复满时间按每周一恢复 6 点、上限 12 点计算跨周次数。
- 抽出纯函数 `_asset_gift_deltas()` 与 `_asset_gift_relationship_preview()`，用同一套封顶逻辑计算五维实际增量、预计好感与赠送后的社交阶段。`asset_gift_options()` 为每项可赠资产附上基础五维与 1 AP 成本，`public_view()` 再把按人物计算的预览挂到 `relationship.asset_gift_previews`。
- 资产赠礼计划直接携带 `affection_gain`、`social_stage_before/after` 与 `may_upgrade`，确认弹窗和资产卡不再自行猜测结果。
- 行动力卡增加恢复节奏、满值时间与五类行动成本；人物档案姓名右侧增加 UID；资产页接入 `formatCompactMoney()`，当前人物选择器使用不换行 flex 布局。
- 资产网格宽屏为四列，1280/980/760 px 以下依次降为三列、两列与一列；资产卡改为纵向弹性布局，标题最多两行，按钮固定在卡片底部。
- 头像来源区增加本地化帮助：默认 FM26/FM24 `graphics`、可选 graphics 根目录或单独 XML、常见 `faces\face_<UID>.png` 与姓名缩写回退。

### 关键决策

- 预览必须由服务端计算，避免前端复制关系阈值和 100 点封顶规则；预览不保存动作，正式提交时再重新生成并扣除 AP。
- 资产金额在该页面强制使用紧凑单位，仍尊重用户设置的英文 K/M/B 或中文万/亿体系。
- UID 使用缓存人物的 `person.id`，也是 `GET /api/player-avatar?player_id=` 和 face pack 映射使用的键。

### 验证

- `node --check`：`interactions_page.js`、`i18n.interactions.polish.js`、`app.js` 全部通过。
- `py_compile`：`life_interactions.py` 与两份人物互动测试通过。
- 聚焦测试：`test_life_interactions.py`、`test_life_interactions_api.py`、`test_life_interactions_polish.py`、`test_life_system.py`、`test_i18n_frontend.py` 共 **128 passed**。
- 本轮未启动 Football Manager、Hook、真实存档或成品 EXE。

### 文件

| 文件 | 变更 |
| --- | --- |
| `src/tools/life_interactions.py` | 资产赠礼 AP 降为 1；行动力恢复预测与成本明细；资产赠礼纯预览、人物级预览投影 |
| `src/web/interactions_page.js`、`src/web/interactions.css` | 行动力明细卡、UID、单行人物选择器、四列资产卡、紧凑金额与赠礼预览 |
| `src/web/app.js`、`src/web/app.css`、`src/web/dark-theme.css`、`src/web/i18n.interactions.polish.js` | 头像来源帮助、紧凑金额桥接与 11 语言新增文案 |
| `src/fm_odds_web.py`、`src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj`、`src/web/index.html` | 版本同步到 V2.8.8cBeta / `2.8.8.3` / `57-dev` |
| `tests/test_life_interactions.py`、`tests/test_life_interactions_polish.py` | 行动力预测、1 AP 成本、人物级赠礼预览和 11 语言占位符契约 |

### 备份

- 动手前备份：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.8bBeta-before-2.8.8c-20261018-211026`，保留 2.8.8b 工程与成品基线。

### 交付与打包

- **桌面宿主**：`dotnet build src/desktop/WebViewHost.csproj -c Release` 构建成功（0 警告、0 错误），并回拷为 `src/desktop_host/FMODD.WebViewHost.exe`；199,680 字节，FileVersion `2.8.8.3` / ProductVersion `2.8.8cBeta`，SHA-256 `29EBE44CA3452B571AB0014400DEF31EAA380A78D136F116EFB69B01D4D1BB45`。
- **单文件 EXE**：`dist/FMSDD-V2.8.8cBeta.exe`（由 `dist/FMODD.exe` 复制）为 78,609,141 字节，FileVersion `2.8.8.0` / ProductVersion `V2.8.8cBeta`，SHA-256 `65C4CCB980DA96AA60A21E26D41DD641F6A334B63B1C08A692D5E811F1A2A6D6`。
- **成品只读复核**：`CArchiveReader` 共 631 条目、PYZ 298 模块；`web/`、`assets/`、`desktop_host/` 与 `tools/` 共 554 个资源文件同仓库源文件逐字节一致（缺失 0、差异 0），PYZ 内确认为 `V2.8.8cBeta` 与 `57-dev`，桌面宿主含 UTF-16 标题 `FMSDD V2.8.8cBeta`。未启动成品 EXE。
- **源码运行包**：`dist/FMSDD-V2.8.8cBeta-source-runtime` 共 1,040 文件 / 193.9 MiB；压缩为 `dist/FMSDD-V2.8.8cBeta-source-runtime.zip`。ZIP `testzip()` 通过，1,002 个工程源文件逐字节一致，且不含 `dist/`、`build/`、`logs/`、`data/`、`src/data/` 或 `car_images/`。ZIP 最终字节数与 SHA-256 见 `dist/FMSDD-V2.8.8cBeta-SHA256SUMS.txt` 与 `dist/FMSDD-V2.8.8cBeta-第57轮改动总结.md`。

## 第 56 轮（V2.8.8bBeta · 档案直读、身份点数、只增属性与关系披露，2026-10-18）

### 需求

- 人物互动总览直接展示玩家核心属性，并扩大“编辑档案”按钮的可点击区域。
- 档案编辑消除右侧白边；姓氏与名字拆分；年龄、身高、体重按权重消耗身份点；颜值、能力、魅力、声望取消上限且建档后只增不减。
- 取消 50,000 资金付费重置，身份变化改为即时重算预算；旧档案必须可无损迁移。
- NPC 性格、价值观、喜爱与厌恶随关系增长解锁；女性三围早期显示范围，关系深入后逐步精确。
- 重做 NPC 档案布局，并修复点击一个已选人物后无法切换其他人的问题。
- 版本迭代到 V2.8.8bBeta，维护开发与错误日志并重新打包。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_interactions.py` | 档案 schema 升到 3；新增姓氏/名字拆分与组合、身份点模型、四项属性安全上限；旧档迁移补足身份点账本；移除重置计划费用；NPC 公开投影按关系等级裁剪性格、价值观、偏好、厌恶与女性三围范围 |
| `src/fm_odds_web.py` | 档案写入不再要求重置确认、不再扣款；产品版本更新为 `V2.8.8bBeta`，开发标识更新为 `56-dev` |
| `src/web/interactions_page.js` | 总览属性面板与大编辑按钮；姓氏/名字输入、身份成本预览、只增属性校验；NPC 档案两栏布局、披露徽标/进度/锁定位/三围范围；人物选择统一到 `data-interaction-person-select` |
| `src/web/interactions.css` | 档案弹窗全宽铺满、左右双栏、响应式重排；新增身份成本、属性面板、披露徽标、锁定提示与两栏 NPC 档案样式；删除旧付费重置提示样式 |
| `src/web/i18n.interactions.polish.js` | 为 11 种界面语言补齐 25 个档案/披露键，保持占位符同构 |
| `src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj`、`src/web/index.html`、`src/web/app.js` | 窗口标题、产品版本与回退标识同步到 `V2.8.8bBeta` / `2.8.8.2` / `56-dev` |
| `tests/test_life_interactions.py`、`tests/test_life_interactions_polish.py`、`tests/test_life_system.py` | 覆盖姓名拆分、身份成本、超过 99 的属性、只增校验、基准回调释放点数、旧档迁移、渐进披露、11 语言键与前端布局/人物切换契约 |
| `README*.md`、`CHANGELOG.md`、`docs/ARCHITECTURE.md`、`docs/FEATURE_INDEX.md`、`docs/RUNTIME_CONTRACTS.md`、`docs/development/DEVELOPMENT.md` | 同步版本、档案身份点/披露契约、功能索引与本轮交付说明 |

### 关键决策

- **身份点是目标成本，不是累计收费**：每次保存只按当前年龄、身高、体重重新计算总成本；玩家变老、变矮或变重可释放点数，但四项能力属性仍不可回退。
- **只增属性与总预算同时生效**：取消单属性 99 上限不代表无限免费加点，四项之和仍不得超过基础点与永久账本奖励。
- **披露在服务端裁剪**：未解锁的性格、价值观、偏好、厌恶和三围不会下发到浏览器，避免仅靠前端隐藏而被旧缓存或调试工具读取。
- **范围先于精确值**：女性三围按披露等级 0–3 依次使用 ±3/±2/±1/0 cm，关系档案既保留神秘感，也让升级有明确反馈。
- **旧档迁移优先于强制重填**：旧 `name` 字段自动拆成姓氏与名字，旧身份成本写入点数账本；已完成档案不会因升级突然变成负预算。

### 验证

- `node --check src/web/interactions_page.js`、`node --check src/web/i18n.interactions.js`、`node --check src/web/i18n.interactions.polish.js` 通过。
- `py -3 -X utf8 -m py_compile src/tools/life_interactions.py src/fm_odds_web.py src/fmodd_desktop.py` 通过。
- `py -3 -X utf8 -m pytest tests/test_life_interactions.py tests/test_life_interactions_api.py tests/test_life_interactions_polish.py -q -p no:cacheprovider`：**35 passed**。
- `py -3 -X utf8 -m pytest tests/test_life_system.py -q -p no:cacheprovider`：**73 passed**。
- `py -3 -X utf8 -m pytest tests/test_i18n_frontend.py tests/test_i18n_catalog_contract.py tests/test_i18n_audit.py -q -p no:cacheprovider`：**27 passed**；契约测试现允许“核心三语”或“完整十一语”词包，但要求每种已声明语言的键集合与占位符完全相同。
- 桌面宿主 `dotnet build src/desktop/WebViewHost.csproj -c Release`：**0 警告 / 0 错误**。
- 本轮未启动 Football Manager、Hook、真实存档或成品 EXE。

### 交付与打包

- **备份（动手前）**：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.8aBeta-before-2.8.8b-20261018-203955`，保留 2.8.8a 工程与成品基线。
- **桌面宿主**：`src/desktop_host/FMODD.WebViewHost.exe` 为 **199,680 字节**，FileVersion `2.8.8.2` / ProductVersion `2.8.8bBeta`，SHA-256 `5FBECA7A9E576F7656B857251C97FB0F1B2953FF2A2B9D87FF0FEF8B8080938A`。
- **单文件 EXE**：`dist/FMSDD-V2.8.8bBeta.exe` 为 **78,601,411 字节**，FileVersion `2.8.8.0` / ProductVersion `V2.8.8bBeta`，SHA-256 `E58A632E80DA35A68A9BC0EA74FF62CEC7C2F72773A320276A4519634F085CD9`。
- **成品内容复核**：`CArchiveReader` 共 **631 条目**；包内 `web/`、`assets/`、`desktop_host/` 共 **552** 个文件与仓库源文件逐字节一致（缺失 0、差异 0）。PYZ 中 `fm_odds_web` 的版本常量为 `V2.8.8bBeta` 与 `56-dev`，`tools.life_interactions` 含 `schema_version` / `surname` / `given_name`。
- **源码运行包目录**：`dist/FMSDD-V2.8.8bBeta-source-runtime` 为 **1,040 文件 / 203,228,812 字节**，包含更新后的 `interactions_page.js`、`interactions.css`、`i18n.interactions.js`、`i18n.interactions.polish.js`、开发/错误日志与桌面宿主。
- **源码运行包压缩**：`dist/FMSDD-V2.8.8bBeta-source-runtime.zip` 为 **148,003,264 字节 / 1,040 条目**，SHA-256 `0F8F9FB79794013B86F28625DA46D9A2F30E3A133A4E715C93B5E5604D56404A`；`zipfile.testzip()` 通过，12 个关键源码、测试、文档与宿主文件逐字节一致，包内不含 `dist/`、`build/`、`logs/`、`src/data/` 或 `car_images/`。本行在压缩后回填，因此压缩包内开发日志不含该最终哈希。

## 第 55 轮（V2.8.8aBeta · 人物工作台分区、点数档案与 NPC 属性扩展，2026-10-18）

### 需求

- 人物互动主界面按功能拆分主标签与子标签，减少玩家档案、搜索、人物列表和操作区混排。
- 玩家档案使用有限点数分配，完成后重置收费；后续购置资产等获得的新点数可继续加点。
- 为 NPC 增加身高、体重、性格、价值观和喜爱项，成年女性额外增加三围；对白要随话题、性格、价值观和关系变化。
- 设置中增加球员头像读取开关；没有头像时显示文字。
- 住宅入住与赠送资产名称按界面语言本地化。
- 版本迭代到 V2.8.8aBeta，并维护开发、错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/web/interactions_page.js` | 主界面拆为总览、人物、寻找球员、资产、时间线；人物分档案/互动，资产分住宅入住/资产赠送；新增点数预算、档案账本、NPC 外貌/性格/价值观/喜好/三围、头像与本地化资产名展示 |
| `src/web/interactions.css` | 新增主/子标签栏、档案分配卡、点数账本、档案表单全宽提示与响应式布局；档案弹窗与保存按钮不再被两列网格压缩 |
| `src/web/i18n.interactions.polish.js` | 新增头像设置文案与聊天、赠礼、约会、关系推进的 3 组对白变体，覆盖 11 种界面语言并保持占位符同构 |
| `src/tools/life_interactions.py` | 玩家档案改为 200 基础点分配与永久点数账本；完成档案降低已分配属性时要求付费重置；人物缓存增加身高、体重、性格、价值观、喜好、厌恶与成年女性三围；FM 顶层身高体重进入规范化与增量刷新 |
| `src/tools/app_settings.py`、`src/fm_odds_web.py` | 新增 `interaction_portraits_enabled` 设置与 `/api/settings/interaction-portraits`；档案重置费用通过原有账户账本扣除并在失败时退还 |
| `src/web/app.js` | 设置页挂载头像开关，保存后同步状态并刷新人物页；开发版本回退标识更新为 `55-dev` |
| `src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj`、`src/web/index.html` | 产品与窗口标题更新为 V2.8.8aBeta；桌面宿主程序集更新为 `2.8.8.1` |
| `tests/test_life_interactions.py`、`tests/test_life_interactions_api.py`、`tests/test_life_interactions_polish.py` | 覆盖点数档案、旧档迁移、付费重置、FM 身高体重两条缓存路径、女性三围、11 语言对白变体、标签结构、头像设置和资产名本地化 |
| `README*.md`、`CHANGELOG.md`、`docs/ARCHITECTURE.md`、`docs/FEATURE_INDEX.md`、`docs/RUNTIME_CONTRACTS.md`、`docs/development/DEVELOPMENT.md` | 同步版本、功能入口、点数/重置/头像/对白契约与本轮验证记录 |

### 关键决策

- **身份字段与能力点分开**：年龄、身高、体重、性别和简介是角色身份信息，不参与颜值、能力、魅力、声望四项的 200 点预算；这样重置只影响可由玩家重新分配的能力，不会让身高体重变成不合理的数值交易。
- **只在降低已分配属性时收费**：后续资产奖励的新点数可直接加到原有档案；只有撤销或重分配旧点数才触发 50,000 重置确认，避免玩家每次加点都重复付费。
- **对白变体由服务端稳定选择**：`variant` 同时混合话题、性格、价值观、社交阶段和关系阶段，客户端只按当前语言解析模板；刷新或重新打开存档不会随机改口。
- **头像读取是可关闭的展示层能力**：服务端只提供头像 URL，开关关闭或加载失败时立即回退姓名缩写，不把图片存在当成人物数据的一部分。
- **标签切换保留工作上下文**：主/子标签只改变当前投影，不清空已选人物、搜索条件或资产子页，减少来回切换后的重复操作。

### 验证

- `node --check src/web/app.js`、`node --check src/web/interactions_page.js`、`node --check src/web/i18n.interactions.polish.js` 通过。
- `py -m py_compile src/tools/life_interactions.py src/tools/app_settings.py src/fm_odds_web.py` 通过。
- 生活互动、互动 API、对白本地化、设置、球员头像、i18n、设置前端优化、生活系统与更新检查聚焦回归合计 **141 passed**；覆盖点数预算、旧档迁移、FM 身高体重规范化、女性三围、标签结构、头像设置契约和资产名语言选择。
- 桌面宿主构建成功，文件版本 `2.8.8.1`、产品版本 `2.8.8aBeta`；单文件 EXE 内嵌 PYZ 实测含 `PRODUCT_VERSION = "V2.8.8aBeta"` 与 `"55-dev"`。
- `dist/FMSDD-V2.8.8aBeta.exe`：78,588,207 bytes，SHA-256 `B41A827E08C2179486B79A327F5D7A3B423CF6E0DEBE4013C4388CC33695A0F6`。
- `dist/FMSDD-V2.8.8aBeta-source-runtime.zip`：147,901,778 bytes，SHA-256 `C6AABDA9DDE60E885977C90ED42AE8AE3E1BA90E2857A13A06A4558A837B0EF4`；解包清单确认含 `i18n.interactions.polish.js`、更新后的 `app.js` / `index.html` / `interactions.css` 与桌面宿主。
- 未启动 Football Manager、Hook、真实存档或成品 EXE；包装后的字体、头像 URL 与真实窗口视觉仍以用户运行验收为准。

### 遗留/后续

- 头像读取依赖用户已配置的 FM 头像来源；本轮只做静态契约与模拟流程验证，未在真实游戏进程内读取头像文件。
- 对白仍为用户确认的模板方案，不接 AI 或自定义 API；后续若接入，应保留当前 `dialogue` 契约与本地回退。

## 第 54 轮（V2.8.8Beta · 球员互动首版、模板对话与永久资产赠礼，2026-10-18）

### 需求（用户确认后的边界）

- “情人”作为保密关系类型，而不是公开主升级阶段；已有公开情侣或夫妻时，其他关系只能发展为情人。
- 公开情侣和夫妻默认排他；允许并行保密关系，暂不引入 NTR。
- 玩家档案按存档独立；行动力上限 12、每周恢复 6。
- 高价值房产、产业与车辆赠送永久转移、不可收回，并提供明确提醒。
- 住宅入住容量以面积为主、等级为辅；首版仅与球员互动，不包含职员。
- 首版使用模板化对话，不接 AI；范围包含人物缓存与增量刷新、玩家档案、五维关系、成年恋爱分支、行动力、聊天/赠礼/约会、NPC 偏好、住宅入住、物品与资产赠送、关系时间线。
- 版本迭代到 V2.8.8Beta，并维护开发日志、错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_interactions.py` | 新增存档级互动文档：成年球员缓存、玩家档案、五维关系、公开/保密关系规则、行动力、偏好、聊天/赠礼/约会、住宅入住、永久资产赠礼与时间线；互动结果返回模板对话描述，资产预览也显式标记永久且不可收回 |
| `src/fm_odds_web.py` | 接入 `/api/life/interactions` 及其搜索、档案、人物刷新、聊天、赠礼、约会、关系、住宅和资产赠送接口；单人物刷新支持 `person_id`；版本推进到 `V2.8.8Beta` / `54-dev` |
| `src/web/interactions_page.js` | 新增人物工作台、玩家档案、关系进度、偏好、搜索、聊天/赠礼/约会、入住、永久赠送二次确认、赠礼历史与时间线；新增本地化模板对白结果弹窗 |
| `src/web/interactions.css` | 新增完整互动页面主题、关系与资产面板、响应式布局及互动结果弹窗；用户可见字号不低于 13px |
| `src/web/i18n.interactions.js` | 提供 11 种界面语言互动文案；新增模板对白与互动结果键，所有语言共享同一键集与占位符 |
| `src/web/index.html`、`src/web/app.js`、`src/web/life_page.js` | 增加生活→人物导航与互动结果弹窗；永久赠送后同步刷新生活资产 |
| `src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj` | 窗口标题与桌面宿主程序集同步到 V2.8.8Beta / `2.8.8.0` |
| `tests/test_life_interactions.py`、`tests/test_life_interactions_api.py`、`tests/test_i18n_static.py` | 覆盖成年限制、偏好稳定性、行动力、关系按钮与后端阈值、排他/情人、分手后公开升级、住宅容量、永久赠礼、模板对话元数据和模拟存档 API 全链路 |
| `README*.md`、`CHANGELOG.md`、`docs/ARCHITECTURE.md`、`docs/FEATURE_INDEX.md`、`docs/RUNTIME_CONTRACTS.md`、`docs/development/DEVELOPMENT.md` | 同步版本、功能入口、所有权、存档/API/资产转移/模板对话契约和验证记录 |

### 关键决策

- **后端只做规则，模板对白在前端落地**：互动动作返回 `dialogue.kind`、`reaction` 和稳定参数，不返回某一种语言的成品句子。这样存档与其他语言不绑定，也不产生在线依赖。
- **秘密关系独立于主阶段**：`romance_stage` 继续表示公开路径，`secret_lover` 是并行布尔状态。公开伴侣存在时，`partner`/`spouse` 不可用，`secret_lover` 才可用。
- **一次动作、一份结果卡**：服务端完成扣行动力、关系变化和时间线写入后，前端统一弹出对方回应与五维变化，避免“只弹一句提示但看不到结果”。
- **永久赠礼以资产所有权为准**：预览与提交使用同一规则；房产会同时移除关联车库，车辆直接从生活资产文档移除，赠礼账本记录不可收回。
- **人物信息只按需读取**：搜索才读取完整球员行，已缓存人物可单人或批量增量刷新；普通页面渲染不触发全库扫描。

### 验证

- `node --check src/web/interactions_page.js`、`node --check src/web/i18n.interactions.js` 通过。
- `python -m py_compile src/tools/life_interactions.py src/fm_odds_web.py src/fmodd_desktop.py` 通过。
- `tests/test_life_interactions.py`：16 项通过。
- `tests/test_life_interactions_api.py`：2 项模拟存档链路通过，覆盖档案创建、加人、聊天、住宅入住、物品赠礼、永久车辆预览/确认。
- `tests/test_i18n_static.py`：键集同构、HTML 本地化属性与脚本顺序检查通过。
- 互动语言包占位符校验：11 种界面语言相对英文基线的 `{placeholder}` 差异为 0。
- `src/web/interactions.css`：所有显式 px 字号均不低于 13px。
- 约会提交按钮按当前活动费用同步文案与禁用状态；关系按钮与后端好感、信任、吸引门槛一致。
- 未启动 Football Manager、Hook、真实存档或成品 EXE。

### 遗留/后续

- AI 接口与玩家自定义 API 对话按用户要求不在首版实现，只保留模板对话数据结构。
- 职员互动按本轮边界不进入首版。
- 真实 FM 中的性别、年龄与人员字段仍需在用户授权的连接环境中做最终验收。

### 交付与打包

- **备份（动手前）**：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.7bBeta-r53-before-20261018-172515`，包含 `project/`、`dist/`、`SHA256-MANIFEST.json` 与备份说明。
- **Web 内嵌资源**：`py -3 -X utf8 src\tools\build_embedded_web_assets.py` 重新生成 `src\tools\embedded_web_assets.py`，共 **533** 个 Web 文件；生成文件 **81,614,100 字节**，SHA-256 `6DB71D707AECB018909FF000BDE8902FFBEB20FCBEC4F4AF89D7BC6CA54E4922`。
- **桌面宿主**：`dotnet build src\desktop\WebViewHost.csproj -c Release` → **0 警告 / 0 错误**；回拷 `src\desktop_host\FMODD.WebViewHost.exe` 为 **199,680 字节**，FileVersion `2.8.8.0` / ProductVersion `2.8.8Beta`，SHA-256 `E40DF913DADF37E51B79549B1E6C5EF5903D4F17057741493D76FA307677B74D`。
- **单文件 EXE**：`py -3 -X utf8 scripts\build_single_exe.py` 成功生成 `dist\FMODD.exe`，复制为 `dist\FMSDD-V2.8.8Beta.exe`。最终文件 **78,541,634 字节**，FileVersion `2.8.8.0` / ProductVersion `V2.8.8Beta`，SHA-256 `209E01C7CC54624D32A9A44D18C48EEDAA0376D395D365215D104E7EBC623E0F`。
- **成品内容复核**：`CArchiveReader` 共 **630 条目**；包内 `web/`、`assets/`、`desktop_host/` 共 **551** 个文件与仓库源文件逐字节一致（缺失 0、差异 0）。PYZ 中 `fm_odds_web` 的版本常量确认为 `V2.8.8Beta` 与 `54-dev`；桌面宿主二进制内含 UTF-16 串 `FMSDD V2.8.8Beta`。
- **源码运行包**：`py -3 -X utf8 scripts\build_source_runtime_package.py` → `dist\FMSDD-V2.8.8Beta-source-runtime`（**1,038 文件 / 202,946,921 字节**）；压缩为 `dist\FMSDD-V2.8.8Beta-source-runtime.zip`（**147,933,267 字节 / 1,038 条目**，SHA-256 `C59806AAD5D73C6009B855DF60E5FC0C810F11C6D490D9CCA6A7797CCF8F57BD`）。`zipfile.testzip()` 通过，14 个关键源码、文档、测试与宿主文件逐字节一致；包内不含 `dist/`、`build/`、`logs/`、`src/data/` 或 `car_images/`。本行是在包生成后回填的，因此包内开发日志不含源码运行包自身的最终哈希。
- **运行边界**：本轮未启动新构建的 EXE、Football Manager、Hook 或真实存档；实机视觉与真实球员字段验收仍需用户授权后进行。

## 第 53 轮（V2.8.7bBeta · 寄存车库筛选、弹窗稳定与收藏家出金调整，2026-10-18）

### 需求（用户原话要点）

- 寄存车库的车辆等级标识太大、会遮挡车辆图片；增加与图鉴一致的车辆分类，方便操作。
- 收藏家金库抽取记录打开一段时间后会闪烁抽搐，需要查明并修复。
- 神秘车库“本次交付”区域布局混乱，需要重新整理。
- 收藏家金库出金由 `S2 + Forza Edition` 或任意等级 `Donut Edition`，调整为 `S2 + 传奇 / Forza Edition` 或任意等级 `Donut Edition`。
- 版本迭代到 V2.8.7bBeta，并维护开发日志、错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | `GOLD_RULES.collector.rarities` 增加 `legendary`；结构化 OR 公开条件、自然抽取、软/硬保底、历史重算与统计自动复用 `_gacha_gold_hit()` |
| `src/web/life_page.js` | 新增 `LIFE_DIALOG_IDS` / `anyLifeDialogOpen()`；任一生活弹窗打开时 `paint()` 不再重建页面根节点；寄存车库新增厂商筛选、传奇与特别版聚合稀有度、搜索联动，筛选后的全选/迁移/出售统一使用当前可见车辆；本次交付头部改为标题/出金汇总/说明与三张等宽指标卡 |
| `src/web/life.css` | 寄存车库增加独立紧凑等级徽标、筛选栏网格与响应式布局；重排本次交付头部和指标卡，补齐 1100/760/520px 断点；历史行 S2 徽标改为相对定位并裁剪流光，修复金色亮带横贯记录弹窗 |
| `src/web/i18n.life.js` | 11 种界面语言的出金提示与基础概率说明同步为 `S2 + 传奇 / Forza Edition` 或任意等级 `+ Donut Edition` |
| `src/fm_odds_web.py`、`src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj`、`src/web/index.html`、`src/web/app.js` | 产品版本、窗口标题、程序集与开发标识同步为 V2.8.7bBeta / `2.8.7.2` / `53-dev` |
| `tests/test_life_system.py` | 更新收藏家 OR 规则断言，新增 S2 传奇正例、S1 传奇反例、任意等级 Donut 正例；覆盖弹窗轮询保护、厂商搜索、特别版聚合、紧凑徽标和交付布局契约 |
| `README.md`、`README.zh-CN.md`、`README.ko-KR.md`、`CHANGELOG.md`、`docs/ARCHITECTURE.md`、`docs/FEATURE_INDEX.md`、`docs/RUNTIME_CONTRACTS.md`、`docs/development/DEVELOPMENT.md` | 同步当前版本、出金规则、概率、寄存筛选与弹窗轮询契约 |

### 关键决策

- **弹窗打开时冻结下层页面**：闪烁的根因不是记录行本身，而是每 2.2 秒状态轮询后 `paint()` 清空页面根节点；即使重新渲染记录弹窗，滚动容器和图片水合队列仍会重建。现在四个生活弹窗任一打开时直接结束页面级重绘，弹窗内部按钮和筛选改为显式局部刷新。
- **分类筛选与批量操作同源**：厂商、等级、稀有度和搜索全部进入 `filteredStorageVehicles()`；全选、批量迁移与批量出售只处理当前结果，避免筛选后误操作不可见车辆。
- **紧凑但不突破可读性底线**：寄存图片内的等级徽标降至 13px，并减少内边距和阴影；其他页面仍保持 16px 醒目等级样式。
- **传奇并入等级内出金集合**：收藏家金库的 S2 传奇现在与 S2 Forza 同级计入金；Donut 继续作为跨等级直通条件。规则仍只有 `_gacha_gold_hit()` 一个判定入口。
- **玩家可见文案跟随后端规则**：11 种界面语言的出金规则与概率说明同步更新，避免实际判定已包含 S2 传奇、界面却仍只写 Forza 的信息错位。
- **流光必须由徽标自身建立包含块**：行内等级徽标不能使用 `position: static`，否则 S2 的绝对定位 `::after` 会以弹窗为参照。改为 `position: relative` 后，徽标的 `overflow: hidden` 才能裁切扫光，布局仍保持行内居中。

### 验证

- 语法：`node --check src\web\i18n.life.js`、`node --check src\web\life_page.js`、`node --check src\web\app.js`；`py -3 -m py_compile src\fm_odds_web.py src\tools\life_system.py src\fmodd_desktop.py` 通过。
- 概率：街头自然 `0.6657%`、含保底 `2.0244%`；性能 `0.3620%` / `1.8568%`；收藏家因 S2 传奇并入，自然 `4.0847%`、含保底 `4.2764%`，约每 `23.4` 抽一金。
- 聚焦回归：`py -3 -m pytest tests\test_life_system.py -q -p no:cacheprovider` → **73 passed**；其中契约测试额外约束 11 种语言的出金说明同时包含最高等级、传奇稀有度、Forza 与 Donut 条件。
- 成品核对：CArchive 共 **627 条目**；包内 548 个 `web\`、`assets\`、`desktop_host\` 资源与仓库源文件逐字节一致，缺失 0、差异 0。
- 视觉缺陷回归：收藏家金库历史行的 S2 流光被限制在徽标内部，不再以弹窗作为绝对定位包含块。
- 不以静态测试替代 WebView2、正式 EXE 或真实存档的实机视觉验收。

### 遗留

- 需在真实 WebView2 窗口中复核寄存筛选栏在窄窗口下的折行、紧凑徽标与抽取记录长时间打开时的稳定性。
- 生活文档 schema 仍为 9；本轮不迁移存档，出金规则对旧历史按当前规则重新计算展示。

### 交付与打包

- 桌面宿主保持 `2.8.7.2 / 2.8.7bBeta`；单文件成品重建为 `dist\FMODD.exe` 与 `dist\FMSDD-V2.8.7bBeta.exe`，两份均为 **78,455,759 字节**，SHA-256 `63A584FAD0A8B3ABDAE30613C7E513CA9D81F74CC36EF6B1202166DBB6C4B819`，版本资源 FileVersion `2.8.7.0` / ProductVersion `V2.8.7bBeta`。
- 源码运行包为 `dist\FMSDD-V2.8.7bBeta-source-runtime`（**1,033 文件 / 202,588,894 字节**）与 `dist\FMSDD-V2.8.7bBeta-source-runtime.zip`；ZIP 的最终字节数与 SHA-256 记录在 `dist\FMSDD-V2.8.7bBeta-第53轮改动总结.md`，避免文档自引用。
- 按仓库约束未启动 Football Manager、正式 EXE、Hook 或真实存档。

## 第 52 轮（V2.8.7aBeta · 生活资料预载、卡池图鉴、等级强化与抽卡确认，2026-10-18）

### 需求（用户原话要点）

- 各个卡池首次抽卡仍会卡顿很久，希望加载存档后自动读取生活资料，并显示开始与完成提示。
- 每个卡池标题右侧增加本卡池车辆图鉴，点击后以二级界面展示该池可抽车辆。
- 为车辆等级增加明显的 D、C、B、A、S1、S2 颜色或特效标识，并加大标识。
- 设置中增加开关，决定每次抽卡是否需要确认。
- 版本迭代到 V2.8.7aBeta，并维护开发日志、错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | `gacha_tiers()` 新增 `car_ids`，把该池经既有等级/稀有度过滤后的目录 ID 直接公开给卡池图鉴；当前三池分别为 236、325、241 辆，池内无重复 ID |
| `src/web/app.js` | 新增 `lifePreloadSignature`、失败冷却与 `lifePreloadPromise`；`maybePreloadLifeData()` 在最终 `/api/state` 渲染后、钱包就绪、游戏日变化与 `DOMContentLoaded` 后触发，按存档作用域和游戏日期去重；新增 `gachaConfirm` 持久化、设置渲染与 `gachaConfirmEnabled()` 桥接 |
| `src/web/life_page.js` | 新增共享预载 Promise 与作用域校验；`preload()` 并行读取生活文档和车辆目录，只有两者都成功才提示就绪；新增本池图鉴弹窗、搜索、等级/稀有度筛选、收藏状态和严格出金标记；新增统一 `vehicleClassBadge()`；抽卡确认由设置开关控制 |
| `src/web/index.html` | 新增全局 `#life-gacha-catalog-dialog` 与设置项 `#gacha-confirm`，默认勾选 |
| `src/web/life.css` | 等级徽标最小 16px，六档独立配色，S2 流光尊重 `prefers-reduced-motion`；补齐卡池图鉴、工具栏、摘要和窄屏布局 |
| `src/web/i18n.life.js` | 11 种语言新增预载开始/完成/失败、卡池图鉴与抽卡确认文案 |
| `src/fm_odds_web.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj`、`src/fmodd_desktop.py`、`src/web/index.html` | 产品版本、窗口标题、程序集与开发标识同步为 V2.8.7aBeta / `2.8.7.1` / `52-dev` |
| `tests/test_life_system.py`、`tests/test_app_boot_order.py` | 新增第 52 轮契约：三池 `car_ids` 数量与唯一性、预载去重/作用域/失败冷却、图鉴关闭路径、等级徽标字号与六档样式、确认开关、11 语言文案；启动尾部加入 DOM 初始化预载触发 |

### 关键决策

- **预载采用三段触发而非只依赖状态轮询**：仅看钱包状态会漏掉“钱包先就绪、connected 后完成”的顺序；最终状态载入、DOM 初始化与游戏日变化共同保证首次连接和跨日都能触发，同时用签名防止重复加载与重复提示。
- **图鉴只使用服务端公开的池内 ID**：前端不再从全目录反推卡池，避免等级、稀有度规则变化后混入不可抽车辆；目录只负责补齐图片、价格和收藏资料。
- **徽标使用唯一组件**：所有车辆卡片复用 `vehicleClassBadge()`，颜色由等级 class 决定，避免不同页面各写一套等级判断。
- **关闭确认不等于绕过校验**：设置只影响 `fmoddConfirm()`，抽卡仍提交相同请求，价格、车位、余额与保底始终以服务端为准。

### 验证

- 语法：`node --check src\web\app.js`、`src\web\life_page.js`、`src\web\i18n.life.js`、`src\web\i18n.settings.js` 通过；`py -3 -m py_compile src\fm_odds_web.py src\tools\life_system.py src\fmodd_desktop.py` 通过。
- 卡池数据：`street / performance / collector` 的 `car_ids` 数量分别为 236、325、241，单池无重复且全部存在于 425 辆目录。
- 合并回归：生活系统、设置、启动顺序、HTTP、状态载荷、i18n、桌面平衡与公开文案聚焦套件 **145 passed**。
- 不以静态测试替代 Football Manager、正式 EXE、WebView2 或真实存档的实机验证。

### 遗留

- 预载减少首次抽卡前的目录与生活文档等待，但真实存档下第一次服务端抽取、车辆图片首次写入浏览器缓存所需时间仍需成品验收。
- 卡池图鉴的 11 语言文案与样式已静态验证，WebView2 不同缩放比例下的最终视觉需玩家验收。
- 生活文档 schema 保持 9；本轮新增的 `car_ids` 是派生只读字段，不写入存档，不需要迁移。

### 交付与打包

- 桌面宿主 Release 重建成功，文件版本 `2.8.7.1`、产品版本 `2.8.7aBeta`；已替换 `src\desktop_host\FMODD.WebViewHost.exe`。
- 内嵌前端归档成功写入 530 个 `src\web\` 文件，归档大小 60,979,295 字节。
- 单文件成品：`dist\FMSDD-V2.8.7aBeta.exe`（78,454,364 字节，SHA-256 `F6D36FD2554D7904CBBCECF36896A3B5C0055AAD5B66428DCA80405783F97AE8`），`dist\FMODD.exe` 与其字节一致。EXE 的 ProductVersion 为 `V2.8.7aBeta`，FileVersion 由打包脚本记录为 `2.8.7.0`。
- 源码运行目录为 1,033 个文件、202,561,985 字节；同步生成 `dist\FMSDD-V2.8.7aBeta-source-runtime.zip`（147,731,622 字节，SHA-256 `60143FD9D8164A16B674330CA2BB4C273FC5766E4BE59442C75CDC3F9A0DC8A1`），ZIP 完整性检查通过。
- 按仓库约束未启动 Football Manager、正式 EXE、Hook 或真实存档；成品内预载、卡池图鉴、徽标和确认开关仍需真实 WebView2 验收。

## 第 51 轮（V2.8.7Beta · 图鉴可关闭、抽卡增量响应与 Donut 出金，2026-10-18）

### 需求（用户原话要点）

- 在神秘车库或车库点击收藏图鉴后，弹窗发灰且无法关闭，需要修复。
- 每次抽卡都会出现“正在读取生活资产…”，首次抽车等待尤其久，希望缩短等待并避免误以为卡死。
- 收藏家金库唯一一辆 Ford Donut 特别版概率为 `0.5%`，但旧出金要求 `S2 + Forza/Donut`，导致 S1 Donut 不计为出金；应改为 `S2 + Forza Edition` 或直接出 Donut Edition。
- 版本号迭代到 V2.8.7Beta，并继续维护开发日志、错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | `GOLD_RULES.collector` 增加 `any_class_rarities=("donut edition",)`；`_gacha_gold_hit()` 先判任意等级 Donut，再判 `S2 + Forza`；新增 `_gacha_public_rules()` / `_gacha_rule_rarities()`；`gacha_tiers()`、`gacha_plan()` 与历史行公开 `gold_rules`；新增 `gacha_patch()` 增量投影；`public_view()` 移除未使用的完整 `state` 深拷贝 |
| `src/fm_odds_web.py` | 产品版本 `V2.8.7Beta`、开发标识 `51-dev`；抽卡接口返回 `life_patch`，不再返回完整生活视图 |
| `src/web/life_page.js` | 新增 `mergeGachaLifePatch()`；抽取后只合并新增车辆、车库、图鉴和卡池计数；图鉴弹窗内点击纳入统一委托，支持关闭按钮、遮罩与 Esc；预热并发 4 → 2 且抽卡时暂停；抽取按钮使用 `life.gacha.drawing` |
| `src/web/life.css` | 主题变量与暗色主题扩展到 `.life-collection-dialog`，弹窗按钮、输入框与 `small` 保持至少 13px |
| `src/web/i18n.life.js` | 11 种语言新增“抽取中…”“任意等级 + 稀有度”“或”，并重写出金、硬保底、软保底和概率说明 |
| `src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj`、`src/fmodd_desktop.py` | 窗口标题、产品版本、程序集版本同步为 V2.8.7Beta / `2.8.7.0` |
| `tests/test_life_system.py`、`tests/test_api_http_dispatch.py` | 覆盖 S1/A + Donut 正例、S1 + Forza 反例、三池硬保底统一 OR 判定、增量响应、无完整 `state`/`life`、11 语言占位符、抽卡路由分派 |

### 关键决策

- **Donut 使用稀有度直通规则**：收藏家卡池的 Donut 车辆当前是 S1，不应为了让它出金而篡改车辆等级；规则改为“任意等级 + Donut Edition”，Forza 仍要求 S2，避免普通稀有度借 OR 规则混入。
- **增量响应只含会变化的数据**：新增车辆、车位/寄存、图鉴和卡池统计是抽卡唯一会变化的字段；房产、收益、车辆目录和未抽取卡池无需重复返回。前端保留已有完整生活状态并按 ID 合并新增车辆。
- **弹窗使用全局样式作用域**：图鉴、寄存车库与历史弹窗位于页面容器之外，不能只依赖 `.life-page` 上的 CSS 变量；三类弹窗继续共用 `.life-collection-dialog` 主题和事件关闭语义。
- **概率显示继续透明**：接口返回结构化 `gold_rules`，前端用“或”连接多个条件；硬保底提示使用完整 `{condition}`，不再只传最高等级与稀有度字符串。

### 验证

- 语法：`py -3 -m py_compile src\fm_odds_web.py src\tools\life_system.py src\fmodd_desktop.py`、`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js` 通过。
- 概率核对：自然出金率为 `0.6657% / 0.3620% / 0.6617%`，含保底长期期望为 `2.0244% / 1.8568% / 1.6218%`；公开等级与稀有度边际概率保持既有契约。
- 聚焦回归：`tests/test_life_system.py` **71 passed**；HTTP、i18n、字号、壳层与公开文案套件 **47 passed**；合计 **118 passed**。
- 增量响应回归：`gacha_patch()` 不含完整 `life` / `state` / `vehicles`，新增车辆、价值、车库摘要、图鉴、卡池计数与经理作用域均正确；抽卡 HTTP 路由分派到 `draw_life_gacha()`。
- 不以静态测试替代 FM、正式 EXE 或真实存档的实机验证。

### 遗留

- 未启动 Football Manager、正式 EXE 或真实存档；图鉴弹窗在 WebView2 不同缩放下的最终视觉、真实存档首次抽卡的感知耗时仍需成品验收。
- 现有存档 schema 保持 9，不需要迁移；旧历史记录会按新 OR 规则重新计算 `gold_hit`，因此过去抽到的 S1 Donut 会补显示为出金。

### 交付与打包

- 桌面宿主重建后为 `2.8.7.0 / 2.8.7Beta`，并已替换 `src\desktop_host\FMODD.WebViewHost.exe`；窗口标题与 PyInstaller 版本资源同步为 V2.8.7Beta。
- 单文件成品：`dist\FMSDD-V2.8.7Beta.exe`（78,447,109 字节，SHA-256 `A493E8383C459295BE4EAA98BF8BBCBFDFEDCCFD0FDB6067F8778E07C43755D8`），`dist\FMODD.exe` 与其字节一致。
- 内嵌前端：530 个 `src\web\` 文件全部写入归档，逐字节比对缺失 0、差异 0；EXE 内 `life_page.js`、`life.css`、`i18n.life.js` 与 `desktop_host\FMODD.WebViewHost.exe` 均与仓库源文件一致。
- 源码运行包：删除误生成的根目录 `$null` 后重建为 1,032 个文件；ZIP 通过 `zipfile.testzip()`，最终字节数与 SHA-256 记录在 `dist\FMSDD-V2.8.7Beta-第51轮改动总结.md`。
- 按仓库约束未启动 Football Manager、正式 EXE、Hook 或真实存档。

## 第 50 轮（V2.8.6Beta · 存档级图鉴、自然出金率与交付成本，2026-10-18）

### 需求（用户原话要点）

- 目前实测约一千抽大多依赖保底，希望在不大幅破坏既有概率结构的前提下提高一点自然出金率。
- 车辆图鉴改为按存档保存；交付中的“重复”要以当前车库是否已有同车型判断，而不是按历史抽出次数判断。
- 移除每个卡池“公开基础概率”标题右侧的等级、稀有度等重复说明。
- 神秘车库增加车辆图鉴入口；本次交付的车辆总价值旁增加成本对比，直观显示值不值。
- 重新整理上方交付车库区域，解决高度不统一和布局混乱。版本号保持不变，并维护开发日志、错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | 生活 `SCHEMA_VERSION` 8 → 9；图鉴迁入 `state.collection`，删除账户级 `COLLECTION_PATH` 读取路径；缺少图鉴的旧存档按已有车辆一次性重建；新增 `gold_weight_multiplier` 与 `_gacha_cell_scales()` 校准自然出金权重；每条抽取记录写入 `garage_duplicate` / `garage_copies_before`，十连内按顺序累计 |
| `src/fm_odds_web.py` | 开发标识推进到 `50-dev`，冻结产品版本保持 `V2.8.6Beta`；修正 `public_life()` 解包名与引用名不一致导致的生活首页未定义变量回归 |
| `src/web/life_page.js` | 神秘车库工具栏新增图鉴入口；交付显示总价值、成本、净收益与 ROI；重复徽标改读当前车库计数；移除概率标题右侧等级/稀有度说明 |
| `src/web/life.css` | 交付车库、容量、寄存车库、图鉴入口统一为一行等高卡片；新增交付指标组与净收益正负色；补齐窄屏换行 |
| `src/web/index.html` | 图鉴弹窗移至全局区域，车库与神秘车库共用同一个 `#life-collection-dialog`，避免页面切换时找不到弹窗 |
| `src/web/i18n.life.js` | 11 种界面语言补齐存档图鉴、当前车库重复、交付成本/净收益、容量与图鉴入口文案，并把出售提示改为当前存档图鉴 |
| `tests/test_life_system.py` | 覆盖 schema 9 存档隔离图鉴、旧存档重建、自然出金率与公开边际概率、十连车库重复判定、交付成本契约、全局图鉴入口、生活首页经理身份透传及 11 语言完整性 |

### 关键决策

- **图鉴与车辆使用同一存档边界**：图鉴记录的是当前存档的获取历史；卖车会移除车辆资产，但不会抹掉同一存档内已经获得的车型记录。旧 `life_collection.json` 是跨存档共享数据，无法无歧义拆分给某一个存档，因此保留文件但不读取、不自动合并，当前存档仅按已有车辆重建。
- **用权重校准而不是直接放大出金车辆**：直接乘出金车辆会改变公开等级与稀有度概率。`_gacha_cell_scales()` 在等级 × 稀有度网格上迭代校准，把额外权重集中到精确出金组合，同时维持原有公开边际概率。
- **自然出金率和长期期望分别展示**：本轮自然出金率提升到街头 `0.6657%`、性能 `0.3620%`、收藏家 `0.1617%`；含软/硬保底长期期望为 `2.0244% / 1.8568% / 1.3356%`，不把保底带来的长期概率伪装成单抽基础概率。
- **重复只看抽取前车库**：判断基准为当前存档车库中的同车型数量；十连第一抽之后把该车型计入后续判断，因此同一十连中的后一次同车型会正确显示重复，但不读取图鉴累计抽取数。
- **成本对比使用本次实际扣款**：总价值为车辆在抽取日的当前市场估值之和，成本来自服务端 `gacha_plan()` 的实际本次价格；净收益与 ROI 只作抽卡结果参考，不等于立即出售的净得款。
- **入口和弹窗复用**：车库与神秘车库都使用全局图鉴弹窗，避免复制两套图鉴状态、筛选与图片水合逻辑。

### 验证

- 语法：`py -3 -m py_compile src\fm_odds_web.py src\tools\life_system.py`、`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js` 通过。
- 概率核对：当前三池自然出金率为 `0.6657% / 0.3620% / 0.1617%`，长期期望为 `2.0244% / 1.8568% / 1.3356%`；公开等级与稀有度边际概率保持既有契约。
- 聚焦回归：`tests/test_life_system.py` **69 passed**；HTTP、i18n、字号、壳层与公开文案套件 **46 passed**；合计 **115 passed**。
- 额外回归：生活首页 `public_life()` 现在验证当前经理 ID 确实传入视图，防止发布前发现的解包名回归再次出现。

### 遗留

- 未启动 Football Manager、正式 EXE 或真实存档；交付工具栏、净收益颜色与图鉴入口在 WebView2 不同缩放和窄窗口下的最终视觉效果仍需成品验收。
- 旧账户级 `life_collection.json` 不会合并到任何存档；升级后当前存档的图鉴从该存档车库中的现有车辆重建，旧账户中已出售车辆的历史收藏无法恢复。

## 第 49 轮（V2.8.6Beta · 精确出金、卡池统计与欧气评级，2026-10-18）

### 需求（用户原话要点）

- 街头发现调整为单抽 `50 万`、十连 `400 万`；收藏家金库调整为单抽 `2000 万`、十连 `1.5 亿`。
- 出金不能只看最高等级，必须同时满足最高等级和最高稀有度：街头 `A + 史诗`、性能 `S1 + 传奇`、收藏家 `S2 + Forza/Donut`。
- 每个卡池记录总花费、出金次数与抽出车辆的总价值，并展示多个欧皇/非酋等级。
- 版本号保持不变，维护开发日志和错误日志，重新打包成品。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | 调整街头与收藏家价格；新增 `GOLD_RULES` 精确出金规则；软保底仅提升精确出金车辆，硬保底从精确出金池抽取；累计 `spent/gold_count/total_value`；历史行保存 `rarity/cost/value`；新增含保底的期望出金率与七档欧气评级 |
| `src/fm_odds_web.py` | 开发标识推进到 `49-dev`，冻结产品版本保持 `V2.8.6Beta`；抽卡 API 继续原样返回计划、历史与交付总值 |
| `src/web/life_page.js` | 出金徽标改为读取 `gacha_gold_hit/gold_hit`；卡池卡片显示累计统计；历史弹窗显示九项统计、七档欧气刻度、起算抽数、单抽分摊花费与车辆估值 |
| `src/web/life.css` | 新增出金条件卡、卡池统计条、欧气评级面板与历史费用列；放宽历史弹窗并补齐窄屏布局 |
| `src/web/i18n.life.js` | 11 种界面语言补齐精确出金、统计、旧存档起算说明与七档欧气文案 |
| `tests/test_life_system.py` | 更新价格；覆盖四类“等级够但稀有度不够”的反例、三类正例、三池硬保底、累计统计、旧历史兼容、七档评级与前端/API/11 语言契约 |

### 关键决策

- **出金是交集而非并集**：历史行与本次交付都以“最高等级且最高稀有度”重新判定；仅出最高等级不再复用旧的皇冠标记，也不重置保底。
- **概率按真实权重展示**：出金率直接汇总符合双条件的车辆权重，不使用等级概率乘稀有度概率的近似值；软保底只作用于这些车辆，硬保底保证返回双条件组合。
- **欧气评级使用保底后期望，不使用裸基础率**：三池基础出金率分别约 `0.427% / 0.202% / 0.114%`，但计入软/硬保底后的长期期望约为每 `52.9 / 56.5 / 76.3` 抽一次。若用裸基础率比较，几乎所有玩家都会因保底被判成欧皇，因此评级改用含保底期望率做 120 抽先验平滑。
- **小样本不强行评级**：少于 20 个计入统计的抽取显示“样本积累中”，避免十连结果直接给出极端标签；七档刻度始终展示，便于玩家理解完整等级范围。
- **旧存档统计可解释**：旧版本没有记录每次抽取的实际价格，且价格已经多次变化，无法可靠反推累计花费。旧历史、保底进度和车辆全部保留，花费/出金/价值统计从升级后的下一抽开始，并显示“统计从第 N 抽开始”。
- **扣款失败不写统计**：`gacha_plan()` 只生成计划；HTTP 入口在扣款成功后调用 `commit_gacha()`，因此余额不足等失败不会增加 `spent/gold_count/total_value` 或写入车辆与历史。

### 验证

- 语法：`py -3 -m py_compile src\fm_odds_web.py src\tools\life_system.py`、`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js` 通过。
- 规则核对：十组等级/稀有度组合覆盖正反例；三池硬保底均返回对应最高等级和最高稀有度；两次街头十连累计花费恰好 `800 万`，累计出金、车辆价值与逐条记录之和一致。
- 聚焦回归：`tests/test_life_system.py`、`tests/test_api_http_dispatch.py`、`tests/test_frontend_font_sizes.py`、`tests/test_i18n_frontend.py`、`tests/test_shell_frontend_optimization.py`、`tests/test_public_copy_hygiene.py` 合计 **110 passed**。

### 遗留

- 未启动 Football Manager、正式 EXE 或真实存档；欧气评级的长期分布、历史弹窗在 WebView2 不同缩放下的视觉效果仍需成品验收。
- 旧存档中被旧版本截断的历史、升级前的实际花费不可恢复；本轮只保证之后的数据完整累计。

## 第 48 轮（V2.8.6Beta · 抽卡概率重平衡、价格重整与交付总值，2026-10-18）

### 需求（用户原话要点）

- 降低性能寻猎 S1 的基础概率；S1 是该池最高等级，不应成为第二高概率。
- 性能寻猎加入 C 级，并整体优化该池所有等级概率；传奇概率降至 `2.5%`。
- 本次交付增加本次车辆价值总值显示。
- 重新定价：街头发现单抽 `20 万`、十连 `180 万`；性能寻猎单抽 `500 万`、十连 `4500 万`；收藏家金库单抽 `2500 万`、十连 `2 亿`。
- 收藏家金库 Donut 特别版概率提高到 `0.5%`，Forza 特别版降至 `0.25%`，传奇降至 `5%`，其余概率自行优化。
- 版本号保持不变，并维护开发日志与错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | 重设三档价格；性能寻猎加入 C 级并校准 C/B/A/S1 与稀有度权重；收藏家金库按传奇 `5%`、Forza `0.25%`、Donut `0.5%` 校准；每辆抽取车辆写入当前 `value`，`gacha_plan()` 返回 `total_value` |
| `src/fm_odds_web.py` | `/api/life/gacha/draw` 返回 `total_value`；开发标识推进到 `48-dev`，冻结产品版本保持 `V2.8.6Beta` |
| `src/web/life_page.js` | 本次交付保存并显示 `totalValue`；缺少服务端字段时按每辆车 `value || base_price` 回退求和 |
| `src/web/life.css` | 新增本次车辆总价值卡片与窄屏布局 |
| `src/web/i18n.life.js` | 11 种界面语言补齐 `life.gacha.total_value` |
| `tests/test_life_system.py` | 断言三档价格、性能/收藏家等级与稀有度概率、单车估值、交付总值，以及 API/前端/11 语言契约 |

### 关键决策

- **概率展示的是软保底生效前的基础概率**：卡池界面、目录返回值与实际抽取共享同一套权重；软保底和硬保底规则不因本轮重平衡而改变。
- **最高等级必须最稀有**：性能寻猎的 S1 基础概率低于 C/B/A，收藏家金库 S2 也低于 A/S1，避免“最高等级反而常见”的倒挂。
- **Donut 与 Forza 的定位拉开**：Donut 基础概率 `0.5%`，是 Forza `0.25%` 的两倍；传奇 `5%` 仍明显高于两种特别版。
- **总值按当前市场估值计算**：交付总值不是目录原价、抽取费用或购入价，而是所有结果记录在抽取游戏日的 `vehicle_market_value()` 之和，并由服务端统一汇总。
- **前端保留兼容回退**：旧后端或其他调用路径若没有 `total_value`，前端按车辆 `value` 求和，不因字段缺失阻断交付展示。

### 验证

- 语法：`py -3 -m py_compile src\fm_odds_web.py src\tools\life_system.py`、`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js` 通过。
- 概率核对：性能寻猎 C/B/A/S1 为 `24/38/33/5%`、传奇 `2.5%`；收藏家金库 A/S1/S2 为 `60/32/8%`、传奇/Forza/Donut 为 `5/0.25/0.5%`，各分类概率和为 1。
- 聚焦回归：`tests/test_life_system.py`、`tests/test_api_http_dispatch.py`、`tests/test_frontend_font_sizes.py`、`tests/test_i18n_frontend.py`、`tests/test_shell_frontend_optimization.py` 合计 **100 passed**。

### 遗留

- 未启动 Football Manager、正式 EXE 或真实存档；概率面板、总价值卡片与抽取结果在不同窗口尺寸和 WebView2 缩放下的最终视觉仍需成品实机验收。
- 本轮不改写既有存档中的抽取历史、保底计数、车辆或收藏记录；新价格与概率只影响后续抽取。

## 第 47 轮（V2.8.6Beta · 车行图片、全量抽卡记录与寄存租金，2026-10-18）

### 需求（用户原话要点）

- 修复汽车展厅车辆图片不显示；其他页面图片正常。
- 继续提高神秘车库价格：街头发现为当前 2 倍、性能寻猎 3 倍、收藏家金库 5 倍。
- 每个卡池保留全部抽取记录，并明确标记抽中该池最高等级的结果和保底命中；本次交付也要展示。
- 寄存车库按车辆总价值每日 1% 收租，并从神秘车库提供寄存入口。
- 版本号保持不变，开发前备份工程与成品，并维护开发/错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/web/life_page.js` | 车行卡片每次渲染、分页和搜索后重新水合车辆图片；卡池历史与本次交付增加最高等级/保底标记；新增神秘车库寄存入口、租金概览、选中车辆估值与结清信息 |
| `src/tools/life_system.py` | 生活 schema 升至 8；三档抽卡价格按 2/3/5 倍调整；移除 40 条历史截断；记录最高等级、自然/保底命中与保底进度；新增寄存起始日、结算日、累计租金和历史，并提供租金报价、提交与状态投影 |
| `src/fm_odds_web.py` | 读取生活状态时结算寄存租金，统一走 `charge_combined_funds` 并在保存失败时退款回滚；`_life_state()` 使用可重入生活锁，消除生活页与城市包读取并发重复结算的可能 |
| `src/web/life.css` | 新增最高等级皇冠、本次交付汇总、租金统计和神秘车库寄存入口样式；寄存弹窗概览改为响应式四列 |
| `src/web/i18n.life.js` | 11 种界面语言补齐全量历史、最高等级命中、保底命中、寄存租金和寄存入口文案 |
| `tests/test_life_system.py`、`tests/test_api_http_dispatch.py` | 覆盖新价格、全量历史、最高等级/保底标记、租金逐日计算、旧存档不追溯、扣款失败回滚、车行图片水合与 11 语言契约 |

### 关键决策

- **价格按轮次倍率而不是重新定档**：三档分别乘以 2、3、5，保留既有等级/稀有度权重、软保底与十连折扣；前端只读取目录返回值。
- **记录只追加、不再覆盖**：`commit_gacha()` 不再裁剪历史；旧版已经截断的 40 条无法恢复，因此发布说明和错误日志都明确这一不可逆边界。
- **最高等级与保底是两种信息**：最高等级表示抽中该池 `PITY_CLASS` 及以上，判断依据是等级；保底表示本次由硬保底强制命中。自然命中最高等级同样重置保底，但不会被误标为保底结果。
- **租金按持仓日逐日计价**：每日租金为当天寄存车辆市值的 1%，不是按结算日一次性乘总天数；寄存当天不计租，次日开始计费。旧存档首次迁移把结算日初始化为当前游戏日，不补收历史租金。
- **租金不是生活模块直接改余额**：领域层只报价并记录结算结果，实际资金通过现有银行/钱包账本扣除；写盘失败时对同一笔扣款退款，避免重复收费或余额与存档不一致。
- **锁下沉到状态入口**：`_life_state()` 自身获取 RLock，调用方继续保留外层锁时不会死锁；这样任何读取路径都不会绕过租金结算互斥。

### 验证

- 语法：`py -3 -m py_compile src\fm_odds_web.py src\tools\life_system.py`、`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js` 通过。
- 聚焦回归：`tests/test_life_system.py`、`tests/test_api_http_dispatch.py`、`tests/test_frontend_font_sizes.py`、`tests/test_i18n_frontend.py`、`tests/test_shell_frontend_optimization.py` 合计 **99 passed**。
- 发布构建：重新生成内嵌 Web 资源、单文件 EXE 与源码运行包，并核对包内资源与 `src/web/` 一致；最终大小和 SHA-256 记录在 `dist\FMSDD-V2.8.6Beta-第47轮改动总结.md`。

### 遗留

- 未启动 Football Manager、正式 EXE 或真实存档；车辆图片在 WebView2 中的实际显示、租金跨日结算和满车位时的界面体验仍需成品实机验收。
- 旧存档中已被第 46 轮及更早版本截断的抽卡记录不可找回；本轮只保证升级后不再截断。

## 第 46 轮（V2.8.6Beta · 车辆图片缓存、寄存车库与批量车辆管理，2026-10-18）

### 需求（用户原话要点）

- 车辆图片为全账户通用，首次加载后应持久缓存，之后打开不应反复等待本地服务。
- 统一神秘车库卡片布局；近期抽取记录移入各卡片右上角按钮，不再常驻卡片下方。
- 新增 100 车位寄存车库，自身车库不足时可寄存，并支持批量移动或出售。
- 神秘车库抽卡价格在当前基础上提高十倍。
- 保持版本号不变，并在开发前备份工程及成品。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | 生活 schema 升至 7；新增固定 `storage` 系统车库、旧存档补齐逻辑、抽卡价格十倍调整；自动分配车位时跳过寄存车库 |
| `src/fm_odds_web.py` | 新增 `/api/life/vehicle/move-batch`、`/api/life/vehicle/sell-batch`；批量出售合并入账并在失败时回滚；车辆图片静态资源改发一年期不可变缓存头；开发态标记推进到 `46-dev`，冻结产品版本仍为 `V2.8.6Beta` |
| `src/fmodd_desktop.py` | 回环服务改用 7856–7860 稳定候选并持久化上次端口，最后才回退系统动态端口，尽量保持 Cache Storage origin 不变 |
| `src/web/index.html` | 车库标题新增寄存车库入口与批量管理弹窗；新增抽取记录弹窗 |
| `src/web/life_page.js` | Cache Storage 图片缓存、受控并发、延迟加载与后台预热；统一抽卡卡片；卡片右上角历史按钮；寄存车库全选、迁移、出售与滚动位置保持 |
| `src/web/life.css` | 寄存车库、批量列表、抽取记录、卡片等高与响应式布局；清理旧常驻记录样式 |
| `src/web/i18n.life.js` | 11 种界面语言补齐寄存车库、批量操作与抽取记录文案 |
| `tests/test_life_system.py`、`tests/test_api_http_dispatch.py` | 覆盖旧存档自动补车库、100 车位上限、批量迁移/出售、缓存头、前端缓存与弹窗结构 |

### 关键决策

- **缓存同时覆盖两个层级**：Cache Storage 负责应用重启后的显式图片缓存，HTTP 一年期不可变响应头负责浏览器网络缓存回退；固定端口候选与上次端口记录共同降低 origin 变化导致的缓存失效。
- **后台预热不与首屏抢带宽**：视口内图片使用 5 个前台并发，完整目录仅在 `requestIdleCallback` 后以 4 个并发预热，兼顾首次体验与后续秒开。
- **寄存车库是系统资产而非商品**：固定 ID 为 `storage`，不可购买、不计房价，旧存档由 schema 7 自动迁移补齐；自动挪车不会占满寄存车位，只有用户显式操作才进入。
- **批量写操作由服务端一次完成**：前端只提交车辆 ID；后端统一校验车库、容量和所有权，出售金额合并为单笔银行入账，避免部分成功或重复入账。
- **历史记录只换入口不删数据**：保留既有每池最多 40 条记录，弹窗展示完整记录，卡片按钮显示实际记录数。

### 验证

- 语法：`py -3 -m py_compile src\fmodd_desktop.py src\fm_odds_web.py src\tools\life_system.py`、`node --check src\web\life_page.js` 通过。
- 聚焦回归：生活系统与 HTTP 路由 **69 passed**；i18n 与最小字号 **17 passed**；公告、壳层、页面层级与公共文案 **29 passed**；合计 **115 passed**。
- 发布构建：重新生成内嵌 Web 资源、单文件 EXE 与源码运行包，并核对包内资源与 `src/web/` 一致；最终大小和 SHA-256 记录在 `dist\FMSDD-V2.8.6Beta-第46轮改动总结.md`。

### 遗留

- 未启动 Football Manager、正式 EXE 或真实存档；首次全量图片预热的实际耗时、WebView2 缓存配额与系统缩放下的视觉效果仍需成品实机验收。
- Cache Storage 仍受 WebView2 用户数据目录和缓存配额约束；若用户手动清理浏览器数据或系统回收空间，首次打开会重新填充缓存。

## 第 45 轮（V2.8.6Beta · 收藏图鉴、稀有度定价与透明抽卡，2026-10-18）

### 需求（用户原话要点）

- 在继续开发前备份现有项目工程与成品。
- 将车库中的账户收藏图鉴移入车库标题右侧按钮，以完整、现代的图鉴弹窗展示厂商收集、传奇车辆收集等内容。
- 让稀有度成为车辆价格的最大影响因素，避免低等级老车和传奇车辆价格失真；传奇车辆可在展厅出现，但不可购买。
- 调整神秘车库价格、等级/稀有度爆率曲线并公开概率，避免十连收藏家金库轻易产出 S1。
- 版本迭代到 V2.8.6Beta，并继续维护开发日志与错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | 新增 `CAR_CLASS_PRICE_BANDS`、稀有度倍率/下限与 `rarity-class-v2` 定价；目录 schema 升到 2；按等级/稀有度重建三档卡池权重与软保底；新增 `dealer_status` 并在购买计划入口拒绝展陈车辆 |
| `src/assets/life/cars.json` | 重新生成 425 辆目录：319 辆可售、106 辆仅展示；保留 `source_price` 作为同档排序键 |
| `src/web/index.html` | 车库标题右侧新增收藏图鉴按钮与原生全屏 `<dialog>`；同步 4.5-dev 静态版本标记 |
| `src/web/life_page.js` | 移除车库常驻收藏条；新增图鉴统计、四个标签、筛选、厂商进度、传奇焦点、卡片与展陈按钮；展厅前端同时锁定仅展示车型 |
| `src/web/life.css` | 新增图鉴按钮、弹窗、统计卡、进度环、车型网格、稀有度描边、锁定态、展陈标记与概率面板样式，并补充 1180/900/620px 响应式规则 |
| `src/web/i18n.life.js` | 图鉴与概率文案补齐 11 种语言，并由 `messages` 全量合并 |
| `tests/test_life_system.py` | 新增稀有度价格层级、传奇价格下限、展陈服务端拒绝、收藏家概率、图鉴弹窗结构、11 语言完整性检查 |
| `src/fm_odds_web.py`、`src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj` | 产品/开发版本、窗口标题与宿主程序集同步到 V2.8.6Beta / 2.8.6.0 / 45-dev |

### 关键决策

- **价格仍保留旧目录信息**：不直接丢弃原抓取价格，而是保存为 `source_price`，用于同稀有度同等级车系内部的稳定排序，避免完全按哈希打乱收藏梯度。
- **稀有度决定价格档，等级决定档内带宽**：传奇与特别版拥有独立最低价，普通/稀有/史诗按等级带宽乘稀有度倍率，既修复“几万元传奇车”，也保留 D 级到 S2 的纵向差异。
- **展陈限制放在领域层**：前端禁用按钮只改善体验，真正的边界在 `buy_vehicle_plan()`，所有 HTTP/内部调用都必须经过同一拒绝规则。
- **概率公开但保留惊喜**：界面展示基础等级/稀有度概率、软保底规则和保底次数，不展示每一辆车的具体权重；实际抽取仍由账户种子、抽取序号与保底状态决定。
- **收藏图鉴按账户共享、车辆按存档保留**：弹窗只读取既有 `life_collection` 汇总与当前车辆目录，不改变重复车辆保留机制、售价或存档 schema。

### 验证

- 语法：`py -3 -m py_compile src\fm_odds_web.py src\fmodd_desktop.py src\tools\life_system.py`、`node --check src\web\app.js`、`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js` 均通过。
- 聚焦回归：`py -3 -m pytest tests\test_life_system.py tests\test_api_http_dispatch.py tests\test_i18n_frontend.py tests\test_frontend_font_sizes.py -q` → **78 passed**。
- 数据核对：425 辆中 319 辆可售、106 辆仅展示；收藏家金库基础概率总和为 1，A/S1/S2 约 85.16%/14.01%/0.83%，传奇/Forza/Donut 约 12.74%/0.43%/0.003%。

### 遗留

- 未启动 Football Manager、正式 EXE 或真实存档；图鉴弹窗在不同窗口尺寸、系统缩放、深浅主题与触控滚动下的最终视觉仍需成品实机验收。
- 现有账户收藏与旧车辆记录无需迁移，但旧存档中的已购车辆不会按新价格重新计价，仍按购入价与既有折旧规则估值。

### 交付与打包

- 重新生成内嵌 Web 资源、单文件 EXE 与源码运行包；最终文件大小和 SHA-256 记录在 `dist\FMSDD-V2.8.6Beta-第45轮改动总结.md`，避免包内自引用导致哈希无法闭合。
- 开发前备份位于 `F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.5Beta-r44-before-20261018-020028`，包含 1,941 个项目文件、3 个成品文件与 SHA-256 清单。

## 第 44 轮（V2.8.5Beta · 公告永久置顶，2026-10-18）

### 需求（用户原话要点）

- 将「关于本版本的说明，以及关于下注功能的重要提醒」永久置于公告板最顶端。
- 后续任何版本更新说明或其他置顶公告都只能排在该公告之下。
- 当前置顶此前更像是视觉标志，需要让“置顶”真正决定显示顺序。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/web/app.js` | 新增 `ANNOUNCEMENT_PERMANENT_TOP_KEY`；公告条目保留稳定 `key`；新增 `announcementDisplayEntries()`，按永久公告、其他置顶、普通公告三段稳定排序；公告板改用排序后的列表渲染 |
| `tests/test_announcements_frontend.py` | 增加永久公告常量、未来置顶公告排序与渲染入口契约；模拟后续版本公告，确认永久公告始终位于第一 |
| `src/web/app.css` | 修正公告板排序注释，明确置顶是实际排序规则，不只是标签样式 |
| `docs/UI_SYSTEM.md` | 记录公告板永久置顶、其他置顶与普通公告的显示顺序及未读判定边界 |
| `CHANGELOG.md`、`docs/development/ERROR_LOG.md` | 记录本轮用户可见变化与“置顶仅标记”问题的根因和回归证据 |

### 关键决策

- **按公告键识别永久公告**：永久位置绑定 `announce.entry.open_source`，而不是标题文本或数组下标；后续修改标题、插入新公告或调整语言不会破坏规则。
- **三段稳定排序**：永久公告不受 `pinned` 与日期影响；其他置顶按原数组顺序排在第二段；普通公告保留原顺序。这样未来新增公告时无需手工寻找插入位置。
- **未读语义与展示顺序分离**：展示顺序固定永久公告在前，但未读检测继续读取数组中的最新公告，保证新版本发布后仍会出现红点与启动公告。
- **不新增产品版本号**：本轮只修复公告秩序，继续使用 `V2.8.5Beta` / `2.8.5.0`，开发版本标记为 `44-dev`。

### 验证

- 语法：`node --check src\web\app.js`、`node --check src\web\i18n.js` 通过。
- 聚焦回归：`py -3 -m pytest tests\test_announcements_frontend.py tests\test_home_desktop.py tests\test_shell_frontend_optimization.py tests\test_i18n_frontend.py tests\test_frontend_font_sizes.py tests\test_existing_page_hierarchy.py -q` → **88 passed**。
- 排序用例：模拟“未来版本置顶公告 + V2.8.5 + V2.8.0 + 永久公告 + 操作说明”，输出顺序固定为永久公告、未来版本、V2.8.5、V2.8.0、操作说明。

### 遗留

- 按仓库边界未启动 Football Manager 或正式 EXE；公告板在深浅主题、不同语言与窄窗口下的最终换行和点击体验仍需成品实机验收。

### 交付与打包

- 重新生成内嵌 Web 资源、单文件 EXE 与源码运行包；最终文件大小和 SHA-256 记录在 `dist\FMSDD-V2.8.5Beta-第44轮改动总结.md`，避免包内自引用导致哈希无法闭合。
- 上一轮源码运行目录与压缩包保留为 `.r43-superseded`，便于回退。

## 第 43 轮（V2.8.5Beta · 首页传统色与 V2.8.5 汇总公告，2026-10-18）

### 需求（用户原话要点）

- 重新设计首页各功能图标的背景颜色，从中国色网站中挑选更合适的传统色。
- 取消 V2.8.0Beta 公告的置顶，新增 V2.8.5Beta 置顶公告，并汇总 V2.8.0～V2.8.5 的更改与新增内容。
- 版本号暂不改变，继续维护开发日志与错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/web/app.css` | 移除首页图标分散且重复的旧配色；为 12 个入口统一设置中国传统色及深色渐变落点，并注明中国色来源 |
| `src/web/app.js` | 公告板首位新增 `2026-10-18-v285-launch` 置顶公告；V2.8.0Beta 发布公告保留但改为非置顶 |
| `src/web/i18n.static.js`、八份独立语言包 | 11 种界面语言新增 `announce.entry.v285_launch.title/body`，覆盖 V2.8.0～V2.8.5 的股市、生活、资产、经营、首页与物品变化 |
| `tests/test_announcements_frontend.py` | 锁定新公告必须位于首位且置顶、旧 V2.8.0 公告必须取消置顶；公告目录辅助进程显式使用 UTF-8 解码 |
| `tests/test_home_desktop.py` | 锁定首页 12 个图标类名、传统色基色/深色落点、中国色来源注释及旧色移除 |
| `docs/UI_SYSTEM.md`、`CHANGELOG.md` | 记录色名、色值、白字对比度、配色边界与本轮变更 |

### 关键决策

- **不用过浅的苹果绿作图标底色**：`#bacf65` 与白色图标的对比度不足；改用荷叶绿等 12 个中深传统色，全部基色与白色对比度达到 4.5:1 以上。
- **颜色按功能语义分配**：投注用荷叶绿、积分榜用群青、世界用苍蓝、集团用赭石、物品用芒果棕、生活用海王绿、银行用靛青、股市用枫叶红、活动用桔梗紫、设施用飞泉绿、执教管理用苍绿、名人堂用苍黄。
- **历史公告不删除**：V2.8.0Beta 公告仍可供玩家查阅，只取消置顶；新公告插到数组首位，以触发一次新的未读标记和启动弹出。
- **公告内容按版本分段**：既说明当前 V2.8.5 的首页与物品变化，也完整回溯 V2.8.0～V2.8.4 的主要功能，避免玩家只看到最后一轮而缺少上下文。

### 验证

- 语法：全部改动的语言包、`src\web\app.js` 与 `src\web\i18n.js` 通过 `node --check`。
- 聚焦回归：`py -3 -m pytest tests\test_announcements_frontend.py tests\test_home_desktop.py tests\test_shell_frontend_optimization.py tests\test_i18n_frontend.py tests\test_frontend_font_sizes.py tests\test_existing_page_hierarchy.py -q` → **87 passed**。
- 本地化键：11 种语言合计 22 个新公告标题/正文键均可解析，无回退到键名的情况。
- 错误日志：本轮没有新增产品故障；测试进程的 GBK 解码问题属于验证工具编码边界，已在测试中显式固定 UTF-8，不登记为产品错误。

### 遗留

- 按仓库边界未启动 Football Manager 或正式 EXE；中国传统色在浅色/深色主题下的最终观感、公告长文在 11 种语言下的实际换行仍需成品实机验收。

### 交付与打包

- 内嵌 Web 资源：`py -3 -X utf8 src\tools\build_embedded_web_assets.py` → 530 个文件，归档 60,932,435 字节。
- 单文件 EXE：`py -3 -X utf8 scripts\build_single_exe.py` → `dist\FMSDD-V2.8.5Beta.exe`，78,386,068 字节，SHA-256 `1C47A79C159C1EE5A6981F733524B057375FFEC67E093D73802E730E7D8CFA2C`；FileVersion `2.8.5.0`、ProductVersion `V2.8.5Beta`。
- 源码运行包：`py -3 -X utf8 scripts\build_source_runtime_package.py` + ZIP_DEFLATED level 9 → `dist\FMSDD-V2.8.5Beta-source-runtime.zip`，1,032 个条目；最终字节数与 SHA-256 记录在 `dist\FMSDD-V2.8.5Beta-第43轮改动总结.md`，避免包内自引用导致哈希无法闭合。
- EXE 内嵌 530 个 Web 文件与 `src/web/` 全部逐字节一致；源码 ZIP 中 `app.css`、`app.js`、语言包、内嵌资源模块与说明文档均与工程一致。
- 上一轮源码运行目录与压缩包保留为 `dist\FMSDD-V2.8.5Beta-source-runtime.r42-superseded` / `.zip`；本轮摘要见 `dist\FMSDD-V2.8.5Beta-第43轮改动总结.md`。
- 未启动 Football Manager 或正式 EXE；本地开发版 / 成品中的最终视觉与点击验收仍需由用户完成。

## 第 42 轮（V2.8.5Beta · 首页生活入口与物品二级菜单，2026-10-18）

### 需求（用户原话要点）

- 先备份现有项目工程与成品，再开始本轮修改。
- 首页增加生活系统快捷入口，并删除原来的物品栏快捷入口。
- 侧边栏把物品设为一级菜单，下含商店与背包两个二级菜单；商店一级名称与首页快捷入口改称「物品」。
- 版本号迭代到 `V2.8.5Beta`，继续维护开发日志与错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/web/index.html` | 侧栏新增 `#items-toggle` / `#items-subnav`，下含 `shop` 与 `inventory`；首页快捷入口移除 `inventory`，新增 `life-map`，商店入口标签改为 `nav.items` |
| `src/web/app.js` | `shop` 与 `inventory` 归入 `items` 分组；一级菜单点击后展开分组并进入商店，两个子页面共享一级高亮与互斥展开行为 |
| `src/web/app.css` | 补齐 `items` 一级/二级菜单的图标、分组、展开与首页快捷入口样式，沿用现有导航视觉规范 |
| `src/web/i18n.static.js`、`src/web/i18n.js` 及九份语言包 | 11 种界面语言同步 `nav.items`、`nav.inventory`（背包）与物品页标题 |
| `tests/test_home_desktop.py`、`tests/test_shell_frontend_optimization.py` | 锁定首页 12 个快捷入口、生活入口、已移除的背包入口、物品父菜单和二级子菜单契约 |
| `src/fm_odds_web.py`、`src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj` | 产品版本、开发版本、窗口标题和宿主程序集版本同步到 `V2.8.5Beta` / `2.8.5.0` |
| `src/desktop_host/FMODD.WebViewHost.exe` | 重新执行 Release 构建并回拷桌面宿主 |

### 关键决策

- **只改导航层级，不改页面键**：继续使用 `data-page="shop"` 与 `data-page="inventory"`，避免 API、页面渲染分支、浏览器本地状态和旧存档兼容逻辑被无谓改动。
- **一级菜单同时承担入口与展开**：`#items-toggle` 带 `data-page="shop"`；点击时先展开物品分组，再进入商店。进入商店或背包后，父级保持高亮；这样一级菜单既是入口，也符合用户对二级菜单的预期。
- **首页仍保持 12 个快捷入口**：用生活替换物品栏，而不是继续增加卡片导致网格重排；商店快捷入口保留原有 `data-page="shop"`，仅同步显示名称为「物品」。
- **兼容标识不改名**：软件显示名称为 FMSDD，但字体目录、存档与 `FMODD` 兼容标识继续沿用原路径，避免升级后读不到用户数据。

### 验证

- 语法：`node --check src\web\app.js`、`node --check src\web\i18n.static.js`、`node --check src\web\i18n.js` 通过。
- 聚焦回归：`py -3 -m pytest tests\test_home_desktop.py tests\test_shell_frontend_optimization.py tests\test_i18n_frontend.py tests\test_frontend_font_sizes.py tests\test_existing_page_hierarchy.py -q` → **76 passed**。
- 测试注意：`tests/conftest.py` 的旧 zh-CN 投影可能让原始 HTML 字节断言看起来像页面被改写；首页测试改用 `read_frontend_source(..., mode="raw")`，实际 `index.html` 未变。
- 桌面宿主：`dotnet build src\desktop\WebViewHost.csproj -c Release` → **0 警告 / 0 错误**；回拷 `FMODD.WebViewHost.exe` 为 **199,680 字节**，FileVersion `2.8.5.0`、ProductVersion `2.8.5Beta`，SHA-256 `EA2403C37C53B1B8E42E4F59DFC0ABA52E54A93324808EECA90479921C2253B2`。
- 错误日志：本轮未复现新的产品故障，因此不新增虚构错误条目；上述测试投影现象只属于验证工具边界。

### 遗留

- 未启动 Football Manager 或正式 EXE；首页快捷入口、侧栏展开/收起、图标与最终点击热区仍需在交付成品中实机验收。
- 版本说明已在三份 README、`CHANGELOG.md` 与本开发日志中同步；错误日志无本轮产品错误可登记。

### 交付与打包

- **动手前备份**：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.4Beta-r41-before-20261018-005337`，包含 `project/`、`dist/`、`SHA256-MANIFEST.json` 与备份说明。
- 单文件 EXE、源码运行包与 ZIP 的最终大小和 SHA-256 记录在 `dist\FMSDD-V2.8.5Beta-第42轮改动总结.md`，避免包内自引用无法闭合。

## 第 41 轮（V2.8.4Beta · 水域地块、海外底图与资产卡片，2026-10-18）

### 需求（用户原话要点）

- 泉州地块已不在水域上，但香港、澳门、深圳、杭州等水域密集城市仍有大量地块落在水面，需要彻底修复。
- 国外城市缺少可用瓦片；高德没有海外数据，OpenStreetMap 在国内网络也不稳定，询问是否可换 Petal 地图或其他国内网络可用的底图。
- 商业与工业资产卡片当前布局仍不合理，需要继续优化。
- 版本号保持不变，继续维护开发日志与错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `scripts/build_life_terrain_data.py` | 地形构建支持 OSM `relation` 多面、内环陆地孔洞和海岸线 Shapefile；沿海城市可合并 OSM coastline 水体后按城市 bbox 裁剪，维护脚本仍可在中断后逐城续跑 |
| `src/tools/life_system.py` | 生活 schema 升至 6、城市包升至 2.3；旧资产快照迁移会重新校验地形，地形非法或原地块 ID 消失时迁移到同类型最近合法地块，并保留购买价、租约、施工、等级与累计收益；迁移合法性从只测中心改为“中心 + 按面积推导的地块半径” |
| `src/assets/life/city_terrain.json` | 重建 27 城离线地形掩码，补齐香港、澳门、深圳、杭州、泉州等城市的 relation 多面与海岸线水体 |
| `src/web/life_page.js` | 底图缓存键升级为 `fmsdd-life-basemap-v4`；自动模式中国高德、海外 Bing；手动支持自动/高德/Bing/OpenStreetMap；主底图失败时仅当前视图回退 OSM，不覆盖玩家偏好；Bing 沿用 WGS84→GCJ02 对齐逻辑 |
| `src/web/life.css` | 商业/工业卡片改为紧凑工作台：配置标题、字段、提交区和契约/操作区分离；1520px 以上使用三列布局，日收益独占整行，操作按钮按用途分组 |
| `src/web/i18n.life.js` | 11 种语言补齐 Bing、自动模式、通用回退提示与版权署名 |
| `tests/test_life_system.py`、`tests/test_i18n_frontend.py`、`tests/test_frontend_font_sizes.py` | 新增多面孔洞、水域密集城市地块合法性、旧资产半径校验、Bing 文案与 11 语言一致性回归 |
| `CHANGELOG.md`、三份 `README`、`docs/ARCHITECTURE.md`、`docs/FEATURE_INDEX.md`、`THIRD_PARTY_NOTICES.md` | 同步水域修复、已重建城市包、底图提供方、在线瓦片边界、卡片布局与第三方署名 |

### 关键决策

- **水域避让必须在构建期解决，而不是前端遮罩**。水面、海岸线和绿地来自 OSM 离线掩码；运行时不依赖地图提供方，也不把“看起来像水”作为交易校验。地块 ID 仍保持 `城市:区县:类型:序号`，重建时即使跳过候选点也不重排序号，老资产才能稳定迁移。
- **旧资产迁移是“保权益搬迁”**，不是删除重买。迁移只换地块地理与基础报价快照，原购买价、租约期限、施工进度、等级、经营业态和历史收益保留；迁移判断包含完整地块半径，避免中心在岸上但边界压入水面的情况。
- **海外底图不再依赖高德**。高德海外道路瓦片会返回 HTTP 200 的空占位图，浏览器触发 `load` 后不会走失败分支；因此自动模式改为中国高德、海外 Bing。Petal Maps 网站未暴露可用的公共 XYZ 瓦片端点，本轮不接入。Bing 若失败则临时回退 OSM；不永久切换，避免一次网络波动改写玩家设置。
- **卡片布局按操作语义分组**。经营配置与资产契约是两类信息，升级、出租、收租和出售也是不同风险级别；用分区与按钮组降低误操作，而不是单纯缩小字号。所有可见字号仍不低于 13px。
- **未实机验收地图视觉**。Bing 深圳 z18 已做静态预览对齐检查；香港、澳门等最终瓦片颜色、加载速度与卡片实际字体仍需要发布后实机确认。

### 验证

- 地形与迁移：`py -3 -m pytest tests\test_life_system.py -q` → **41 passed**；新增 `test_owned_property_legality_includes_the_parcel_radius`。
- 前端契约：`py -3 -m pytest tests\test_i18n_frontend.py tests\test_frontend_font_sizes.py -q` → **17 passed**；`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js` 通过。
- 全量地块复核：27 城 2,653 块，按中心与地块半径校验，水面/绿地保护区命中 **0**，跳过 **0**；单城 70–127 块。
- 已知非本轮失败：`tests\test_i18n_catalog_contract.py` 仍为预存在失败，本轮不处理。

### 遗留

- 高德海外底图无可用道路瓦片、Petal 无公开 XYZ 端点；若后续需要更稳定的海外底图，应单独评估有明确条款与 key 管理的提供商。
- 未启动 Football Manager、正式 EXE 或真实存档；水域迁移、租约/施工保留与卡片布局只通过领域测试、静态前端测试和预览图验证。

### 交付与打包

- 本轮成品与源码运行包复用 `V2.8.4Beta` 文件名，最终字节数与 SHA-256 记录在 `dist\FMSDD-V2.8.4Beta-第41轮改动总结.md`，避免包内自引用哈希无法闭合。

## 第 40 轮（V2.8.4Beta · 资产租约、施工周期、地形避让与融资上限修正）

### 需求（用户原话要点）

- 资产信息界面不合理，尤其是商业、工业的**经营业态**；升级、装修、确认产业都应更严格，并且需要时间建设、升级。
- 地块除买断外还要支持租借；房产标题改为「我的资产」，并按类别筛选，不能全部堆在一页。
- 地块生成应根据地图数据避让水面；工业资产不得生成在绿化上。
- 版本号保持 `V2.8.4Beta`，继续维护开发日志与错误日志。
- 追加修复：股市中融资/大宗的上限与 49% 收购门槛互相卡死，持股显示 49.00% 却仍差 1 股；把上限改为 49.9%，让玩家能越过收购门槛。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | 生活存档 schema 升至 5；新增 30/90/180/365 天租约、1.5 个月押金、续租、退租与到期暂停；升级与经营筹备改为按游戏日施工，施工期收益暂停；更换业态必须重新筹备；地块候选点读取离线 OSM 地形掩码，避让水面、公园、森林与其他绿地，工业继续避让市中心缓冲带；找不到合法点则跳过，不再回退到非法坐标；城市包版本升至 2.2 |
| `src/assets/life/city_terrain.json`、`scripts/build_life_terrain_data.py` | 新增 4 国 27 城离线地形掩码（OpenStreetMap ODbL 1.0），共 10,911 个简化多边形；维护脚本按城市抓取并支持断点续跑 |
| `src/fm_odds_web.py` | 新增 `/api/life/property/lease`、`renew-lease`、`release-lease`；施工扣款失败自动退款；租约与施工状态进入资产视图 |
| `src/tools/club_stock_market.py` | 融资持股上限由 49% 调整为 49.9%；收购门槛仍为 49%；接近上限时允许一笔小于常规 2% 的补足融资，避免「差 1 股」死锁；`trading_limits()` 公布 `takeover_gate` |
| `src/web/life_page.js`、`life.css`、`i18n.life.js`、`index.html` | 「我的房产」统一为「我的资产」；增加全部/住宅/商业/工业/车库/自有/租赁/施工中筛选与计数；地图详情提供买断与租用双栏、租期与费用预览；升级、开店、修改经营配置均二次确认；施工倒计时与租约面板 |
| `src/web/app.js` | 融资上限默认值同步 0.499；融资弹窗在临界状态计算「补足到 49% 收购门槛」的最小股数 |
| `tests/test_life_system.py`、`tests/test_club_stock_market.py`、`tests/test_stock_order_frontend.py` | 新增租约押金/续租/到期/退租、施工完成前收益暂停、经营筹备二次确认、地形规避、城市包升级与融资临界补足回归 |
| `CHANGELOG.md`、三份 README、`docs/ARCHITECTURE.md`、`docs/RUNTIME_CONTRACTS.md`、`docs/FEATURE_INDEX.md`、`THIRD_PARTY_NOTICES.md` | 同步租约、施工、schema 5、城市包 2.2、OSM 地形来源与融资上限 |

### 关键决策

- **施工先付费、按游戏日完成**：升级和经营筹备在提交时扣款并写入 `construction`，完成日之前收益为 0；施工中不能出售、续租、改业态或再次升级。这样「确认」不只是一次弹窗，而是有真实时间成本的状态。
- **租约与产权分开**：租约保存起止日、月租、预付租金、押金、续租次数和状态；租赁资产不能出售、不计入自有净值，租约到期后收益暂停，退租返还押金并移除资产与附赠车库。
- **地形掩码是构建期数据，运行期不联网**：城市包只读取随包发布的 `city_terrain.json`，不依赖高德/OSM 在线服务；OSM 只在地块生成维护脚本中抓取。城市包版本变化会重建地块，但地块 ID 仍按 `城市:区县:类型:序号` 生成，序号不因跳过非法点而重排，旧资产仍能按 ID 对应。
- **找不到合法点就跳过**：旧逻辑在随机尝试失败后会返回「最不坏」的点，正是水里/公园里出现资产的根因；现在改为扩大确定性螺旋搜索，仍无合法点则计入 `skipped_parcels`。
- **49.9% 不是新收购门槛**：收购门槛仍是 49%，49.9% 只是融资上限。临界补足融资解决了「持股 49.00% 但整数股差 1 股、常规 2% 融资又会超过上限」的死锁；补足股数按收购门槛反解，不小于 1 股且不超过剩余额度。

### 验证

- 语法：`py_compile`（`life_system.py`、`club_stock_market.py`、`fm_odds_web.py`）通过；`node --check`（`app.js`、`life_page.js`、`i18n.life.js`）通过。
- 生活系统：`tests/test_life_system.py` → **35 passed**，覆盖 27 城地形包完整性、租约、施工、严格经营确认、水面/绿地规避与存档迁移。
- 股市：`tests/test_club_stock_market.py + tests/test_stock_order_frontend.py` → **136 passed**，含 49.9% 上限与临界补足融资。
- 聚焦集：生活、API 分发、桌面运行时、首页、11 语言前端/静态文案、股市 → **265 passed**。
- 地形数据：27 城齐全，10,911 个多边形，`city_terrain.json` 7,392,797 字节。
- 包内核对：EXE 的 `web/life_page.js`、`life.css`、`i18n.life.js`、`index.html`、`app.js`、`assets/life/city_terrain.json`、`i18n.static.js` 与桌面宿主均与仓库逐字节一致（mismatch 0）。
- 实机边界：未启动 Football Manager、正式 EXE 或真实存档；未验证实际地图瓦片下的地块观感、租约/施工弹窗的真实交互与真实存档迁移。

### 交付与打包

- **动手前备份**：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.4Beta-r40-before-20261017-225019`，含 `project/`、`dist/` 与 `SHA256-MANIFEST.json`，共 15,706 文件、约 4.15 GB。
- **嵌入资源**：`src\tools\build_embedded_web_assets.py` 刷新 **530 个文件**，归档 **60,909,677 字节**。
- **单文件 EXE**：`dist\FMSDD-V2.8.4Beta.exe` **78,200,080 字节**，SHA-256 `5D5015240A13E519A322546ECB49E69DD35961C7F12DB507BB1EF2B871002BCE`；FileVersion `2.8.4.0` / ProductVersion `V2.8.4Beta`；CArchive **627 条目**。
- **源码运行包**：`dist\FMSDD-V2.8.4Beta-source-runtime` 与 ZIP 的最终大小/哈希见 `dist\FMSDD-V2.8.4Beta-第40轮改动总结.md`（文档在包内，自引用无法闭合）。
- **交付摘要**：`dist\FMSDD-V2.8.4Beta-第40轮改动总结.md`。

### 遗留

- 地块生成依赖 `city_terrain.json` 的 OSM 覆盖度；若某城 OSM 数据不足，可能出现跳过地块偏多，需要补抓或手动调整城市包版本。
- 生活资产的施工与租约只按游戏日推进，打开生活页或触发相关 API 时才结算到期/完工；如果后续要求严格实时，可把 `advance_lifecycle` 挂到存档每日 tick。
- 仍未做 FM 实机与真实存档验收；发布前建议用户先用副本存档验证租约、施工和水面/绿地规避。

## 第 39 轮（V2.8.4Beta · 已下载地块修复、城市层统计与产业收益调整）

### 需求（用户原话要点）

- 修复地块曾经下载、但进入地块层后仍无法查看的问题。
- 修复资产在城市层没有统计的问题，并消除新增的多个重复地区行。
- 明确产业营业额是一天还是一个月的口径；当前升级带来的产出提升偏少，需要适度提高。
- 版本号保持 `V2.8.4Beta`，继续维护开发日志与错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | 生活存档 schema 升至 4；新增 `district_id` 持久化与旧记录回填；城市层下载与地块包双向补齐；新增已安装城市层缺失地块包的幂等修复；城市层聚合按正式区县合并并隐藏空区县，无法归区的资产统一进入单个“其他区域”；住宅每级租金增益调整为 20%，商业/工业每级经营增益调整为 18% |
| `src/fm_odds_web.py` | `/api/life/city-packs` 在返回地图数据前自动修复旧版“只有城市层、没有地块包”的下载记录，并在响应中报告 `repaired_city_packs` |
| `src/web/life_page.js`、`src/web/life.css` | 产业收支卡明确显示月度营业额、月度工资、月度净收益与每日净收益；每日收益单独占用整行，避免窄卡片挤压 |
| `src/web/i18n.life.js` | 11 种语言同步月度收支口径与每日收益文案 |
| `tests/test_life_system.py` | 新增旧城市层缺包修复、城市层下载立即安装地块、旧资产区县合并、购买持久化区县、升级增益下限等回归 |
| `CHANGELOG.md`、`README.md`、`README.zh-CN.md`、`README.ko-KR.md`、`docs/FEATURE_INDEX.md`、`docs/RUNTIME_CONTRACTS.md`、`docs/ARCHITECTURE.md` | 同步同版本修复说明、schema 4、层包契约与生活系统行为边界 |

### 关键决策

- **旧城市层自动修复而非要求重下**：城市层摘要仍可用于判定玩家曾经下载过该城市。读取城市包列表时仅为“已安装城市层但缺少地块包”的城市重建确定性地块数据，不覆盖已有地块包，也不重建玩家资产。
- **区县兼容顺序固定**：优先使用已保存的 `district_id`，其次从确定性地块 ID 的 `city:district:kind:index` 段恢复，最后才用中英文区县名称匹配；避免多套历史记录生成重复“西城”等节点。
- **月度口径、按日入账**：界面中的营业额、工资和净收益均为月度值，实际累计使用 `月净收益 × 12 ÷ 365` 换算成每日收益；本次只提高升级倍率，不追溯改写已累计收益。
- **存档惰性迁移**：本轮未批量改动真实生活存档；首次读取时会按 schema 4 补齐缺失的区县字段并重新计算显示值，车辆、车库与房产记录继续保留。

### 验证

- 语法：`src/tools/life_system.py` 与 `src/fm_odds_web.py` 的 Python AST 解析通过；`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js` 通过。
- 回归：`tests\test_life_system.py tests\test_api_http_dispatch.py tests\test_update_check.py tests\test_desktop_runtime_parity.py tests\test_home_desktop.py tests\test_i18n_frontend.py tests\test_i18n_static.py` → **135 passed**；其中生活系统覆盖旧城市层修复、双向层包安装、区县合并、区县持久化与升级增益。
- 实机边界：未启动 Football Manager、正式 EXE 或真实存档进行 UI 验收；城市底图、点击热区和实际存档迁移仍需在交付包中由用户实机确认。

### 交付与打包

- **备份（动手前）**：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.4Beta-r39-before-20261017-204126`；工程快照 **2,279 文件 / 419.9 MiB**（排除可重建的 `dist/build` 与运行数据），旧成品 **3 文件 / 211.1 MiB**，并生成 `SHA256SUMS.txt`；旧 r38 运行包目录与临时 ZIP 已移入备份的 `superseded-artifacts`。
- **嵌入资源**：`src\tools\build_embedded_web_assets.py` 刷新 **530 个文件**，归档 **60,897,451 字节**。
- **单文件 EXE**：`dist\FMSDD-V2.8.4Beta.exe` 为 **76,081,804 字节**，SHA-256 `3455444BD47B90DA0182977738A386002578C7245D79CB0545FE4B3D3E329800`；FileVersion `2.8.4.0` / ProductVersion `V2.8.4Beta`。CArchive **626 条目**、PYZ **297 条目**；`web\life_page.js`、`web\life.css`、`web\i18n.life.js`、`web\index.html`、桌面宿主均与仓库逐字节一致（mismatch 0）。PYZ 内确认包含旧层修复函数、`district_id` 回填、20%/18% 增益和 `repaired_city_packs`，版本字符串仅含 `V2.8.4Beta`。
- **源码运行包**：`dist\FMSDD-V2.8.4Beta-source-runtime` 为 **1,030 文件 / 193,079,750 字节（184.1 MiB）**；压缩为 `dist\FMSDD-V2.8.4Beta-source-runtime.zip`（**145,305,823 字节**，SHA-256 `508766DDB58490C859F083AE0F5DA773EE70D8D70E67CA7399621F1CDB9ED83E`）。ZIP 内 `life_system.py`、`life_page.js`、`life.css`、`i18n.life.js`、`fm_odds_web.py` 与仓库逐字节一致。
- **交付摘要**：`dist\FMSDD-V2.8.4Beta-第39轮修复总结.md`。
- **实机边界**：按仓库规则未擅自启动正式 EXE；交付包未做 Football Manager/真实存档实机 UI 验收。

## 第 38 轮（V2.8.4Beta · 产业经营、27 城生活地图与四国国家层）

### 需求（用户原话要点）

- 在更新前备份当前项目工程与成品。
- 住宅应可选择自住或出租；商业地块选择开办的商业设施，工业地块选择建设的产业；车库可选择出租或自用。
- 产业支持升级与雇员，但经营保持简单：商业按城市等级、雇员和产业等级决定收支，工业同理；住宅升级装修提高租金；不做产业链。
- 除已有城市外，中国新增香港、澳门、汕头、厦门、泉州、福州、宁波、苏州、青岛、济南、天津、西安、重庆、贵阳、昆明与南宁；英国、法国、德国分别开放伦敦、巴黎与柏林。
- 版本号迭代到 `V2.8.4Beta`，维护开发日志与错误日志，并打包当前可发布版本。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/assets/life/cities_extra_cn.json` | 新增 16 座中国城市及其区县、基准住宅/商业/工业地价；中国城市总数达到 24 |
| `src/assets/life/cities_global.json` | 新增 `GB`、`FR`、`DE` 三个国家与伦敦、巴黎、柏林，城市目录合计 27 城 |
| `src/assets/life/city_profiles_extra.json` | 为 19 座新城市补充等级、城市类型、区县角色及水体/公园排除区；全部城市画像完整 |
| `src/tools/life_system.py` | schema 升至 3；新增商业/工业业态目录、雇员策略、城市等级系数、等级收益倍率、收支明细、收益分段、配置与升级 API 领域函数；国家目录、国家层包与国家聚合按 `country_code` 隔离；出租独立车库不计可用车位 |
| `src/fm_odds_web.py` | `/api/life/catalog` 返回业态目录；新增 `/api/life/property/configure` 与 `/api/life/property/upgrade`；层包安装接收 `country_code`；升级扣款失败时回滚退款 |
| `src/web/life_page.js`、`src/web/life.css` | 地图增加国家选择器与按国家筛选的城市列表；房产卡增加自住/出租/经营切换、业态选择、雇员输入、收支明细、等级和升级按钮；车库出租提示与车位锁定；新增国家选择、配置区和收支区响应式样式（最低 13px） |
| `src/web/i18n.life.js` | 11 种语言补齐国家、经营模式、业态、雇员、升级与收支文案 |
| `tests/test_life_system.py` | 新增城市/画像、四国层包与聚合、schema 迁移、住宅自用与升级、商业/工业雇员与业态、车库出租、收益分段、升级回滚、前端接线等 9 组回归 |
| `src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj` | 窗口标题、弹窗标题与程序集版本同步到 `V2.8.4Beta` / `2.8.4.0` |
| `README.md`、`README.zh-CN.md`、`README.ko-KR.md`、`CHANGELOG.md` | 更新版本徽章、当前版本与第 38 轮用户可见说明 |

### 关键决策

- **简单经营而非模拟器**：收入只读取资产原始租金/经营净额、城市等级、资产等级、业态倍率和雇员达成率；工资从毛收入中扣除，不引入原料、库存、供应链或跨资产联动，避免操作负担。
- **收益不可追溯改写**：模式、业态、雇员或等级变化前先调用 `_close_income_segment()`，把截至当天的收益写入 `accrued_income`，再从当天开启新收益段。旧存档只补默认值，不重算已领取或已累计收益。
- **车库出租必须空置**：有车辆时后端拒绝出租，前端同时显示迁移提示。出租状态进入 `_rented_garage_ids()` 后从总车位、自由车位与自动分配中剔除，避免“已出租但仍可停车”的双重收益。
- **国家数据隔离**：世界层、国家层、城市层和聚合统计都以国家代码寻址；旧版单一中国国家层仅在选中 `CN` 时作为兼容回退，避免法国、德国显示中国城市汇总。
- **城市数据按确定性生成**：新增城市没有手写固定地块表，而是复用城市画像和生成器，保证相同城市每次生成相同校验和，同时让工业地块留在外围并避开排除区。

### 验证

- 语法：`py_compile src\tools\life_system.py src\fm_odds_web.py src\fmodd_desktop.py` 通过；`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js` 通过。
- 回归：`tests\test_life_system.py tests\test_api_http_dispatch.py tests\test_update_check.py tests\test_desktop_runtime_parity.py tests\test_home_desktop.py` → **110 passed**；其中生活系统 **26 passed**，覆盖 27 城/4 国完整性、国家层安装、聚合隔离、schema 3 迁移、住宅自住/出租/升级、商业/工业雇员与业态、车库出租车位锁定、收益分段与升级提交失败退款。
- 多语言静态：`test_i18n_static.py` 通过；`test_i18n_locale_packs.py` 的 7 项通过，10 项因当前 Windows 终端的 `subprocess` 句柄错误 `WinError 6` 无法启动 Node 探针而中断，未发现生活页键集缺失；`node` 直接加载 `i18n.life.js` 验证 11 个语言包均为 211 键且键集一致。

### 遗留

- 本轮没有启动足球经理、正式 EXE 或真实存档，未做游戏内存与实机 UI 截图验证。
- 本轮只提供住宅、商业、工业、车库的简单经营；办公/酒店等业态不展开独立菜单、雇佣名册或供应链。
- 多语言 locale-pack 测试的 Node 子进程在当前终端被 `WinError 6` 阻断；该问题属于测试环境，发布前仍应换一个正常终端复核。

### 交付与打包

- **备份（动手前）**：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.3Beta-1-20261017`；工程备份 **2,268 文件 / 438,425,587 字节**，成品备份 **3,100 文件 / 1,445,364,036 字节**，并生成工程与成品 SHA-256 清单及备份说明。
- **资源与桌面宿主**：`build_embedded_web_assets.py` 刷新 **530 个文件**，归档 **60,897,306 字节**；`dotnet build src\desktop\WebViewHost.csproj -c Release` 通过（0 警告 / 0 错误），回拷宿主 **199,680 字节**（SHA-256 `7F1E000CFF43C2C8E4D98271B5CA35AFEAB1D3F79A743ECF51044D24BB64FF53`，FileVersion `2.8.4.0` / ProductVersion `2.8.4Beta`）。
- **单文件 EXE**：`dist\FMSDD-V2.8.4Beta.exe` 为 **76,079,121 字节**，SHA-256 `B271C306599E1EF918D203B5A196171856AAF6EEDA91B443FA4BB3A78DA34768`，版本资源 FileVersion `2.8.4.0` / ProductVersion `V2.8.4Beta`；CArchive **626 条目**。包内 `web\life_page.js`、`web\life.css`、`web\i18n.life.js`、`web\index.html`、三份新增生活 JSON 与 `desktop_host\FMODD.WebViewHost.exe` 均与仓库源文件逐字节一致（mismatch 0），入口脚本只含 `V2.8.4Beta`，不再含 `V2.8.3Beta`。
- **源码运行包**：清理误生成的根目录 `$null` 诊断文件后重建 `dist\FMSDD-V2.8.4Beta-source-runtime`，再以 deflate level 9 压缩为 `dist\FMSDD-V2.8.4Beta-source-runtime.zip`；最终大小与 SHA-256 以 `dist\FMSDD-V2.8.4Beta-第38轮改动总结.md` 为准。
- **交付摘要**：`dist\FMSDD-V2.8.4Beta-第38轮改动总结.md`。

## 第 37 轮（V2.8.3Beta · 资产购买提速、车位展示、车库双列与女足目录）

### 需求（用户原话要点）

- 购买资产耗时过长，看起来像卡死；已购置资产应在地图上带有标识。
- 资产详情要显示附带车位；车库车辆详情改为每行两辆并缩小车辆图片。
- 确认俱乐部读取中的国家名称是否实时读取，并适配 FM26 女足联赛，为后续女足球员互动打基础。
- 版本号迭代到 `V2.8.3Beta`，继续维护开发日志与错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | 城市包增加按 `(mtime_ns, size)` 校验的进程内 LRU 缓存（最多 64 个）；新增 `parcel_entry(parcel_id, city_id=None)`，购买时只读取目标城市包；新增 `parcel_parking_spaces()` 兼容旧包；新地块直接写入 `parking_spaces`，住宅/商业/工业/独立车库保持 1/2/4/8–40 车位 |
| `src/fm_odds_web.py` | `buy_life_property()` 接收 `city_id` 并使用定向查询；`/api/life/city-packs` 为旧城市包补算车位；世界俱乐部接口增加 `gender=men|women|all`；股市原始目录只保留男足行 |
| `src/tools/world_clubs.py` | 拆分女足标记与青年/预备/全明星标记；成年女足俱乐部保留在目录中并写入 `gender="women"`，非成年队继续排除；分页按性别筛选并重建对应分面 |
| `src/web/life_page.js`、`src/web/life.css` | 已持有地图针增加 `owned` 标识；地块详情和列表显示车位；购买按钮独立忙碌文案；车辆卡桌面双列、移动端单列并压缩图片与信息间距 |
| `src/web/app.js`、`src/web/index.html`、`src/web/app.css`、`src/web/i18n*.js` | 世界俱乐部增加男足/女足/全部范围下拉框，持久化选择并随查询发送；国家详情球员榜已有性别切换；11 种界面语言补齐俱乐部范围与选项文案 |
| `tests/test_life_system.py`、`tests/test_world_clubs.py`、`tests/test_stock_market_application.py`、`tests/test_world_nations.py` | 增加城市包缓存、定向购买、车位、持有标识、双列布局、女足分页、女足俱乐部保留、股市排除女足等回归 |
| `src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj` | 窗口标题、弹窗标题与程序集版本同步到 `V2.8.3Beta` / `2.8.3.0` |

### 关键决策

- **购买快路径必须有后端边界**：只在 CSS 或前端加 loading 不能解决根本问题。购买请求携带 `city_id`，服务端不再用全局地块索引扫描所有已安装城市包；旧调用仍可回退全局索引，保持兼容。
- **缓存只缓存不可变城市包**：缓存键包含文件修改时间和大小，文件替换后自动失效；缓存上限 64，避免城市包长期累积占用内存。
- **车位由后端投影、前端兼容旧数据**：不提升城市包 schema，避免升级后强制重建所有城市包；旧包缺少 `parking_spaces` 时按类型推导，新包直接持久化。
- **女足与青年队分流**：旧 `_looks_non_mens()` 把女足和青年队一起排除，导致女足联赛无法读取。现拆成性别识别与非成年识别，世界目录保留成年女足，股市仍只读男足，避免现有股市数据被新目录改变。
- **国家名称不猜偏移**：`NATION_NAMES` 来自 `src/assets/nation_mappings/nation_mappings_zh.json`；`Reader.national_team_name()` 只验证 Nation 指针后仍查该映射。没有 FM26 实机验证的 Nation 名称字段偏移，本轮不写入猜测地址，也不宣称模组改名可实时显示。

### 验证

- 静态：`py_compile src/fm_odds_web.py src/tools/life_system.py src/tools/world_clubs.py` 通过。
- 聚焦回归：`tests/test_life_system.py tests/test_world_nations.py tests/test_world_clubs.py tests/test_stock_market_application.py` → **237 passed / 34 subtests passed**。
- 新增回归覆盖：城市包缓存复用、按城市定向购买、旧包车位回退、地图持有标识、车辆双列布局、国家球员性别切换、女足成年人俱乐部保留且青年队排除、股市目录排除女足。

### 遗留

- 未启动真实 Football Manager 进程、未读写真实存档；国家名称与女足国家队容器仍需在明确授权的实机版本上验证偏移后才能进一步实时读取。
- 当前女足支持边界为：女足成年俱乐部进入世界目录，国家详情可按国籍筛选女足球员；世界国家页仍显示男足国家队容器，不宣称已读取女足国家队名单。

### 交付与打包

- **备份（动手前）**：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.2Beta-1-20261017`；`project\` **1,913 文件 / 349,526,949 字节**，`dist\` **2,069 文件 / 1,031,087,881 字节**，并生成工程与成品 SHA-256 清单及备份说明。
- **静态与聚焦验证**：`py_compile`（`fm_odds_web.py`、`life_system.py`、`world_clubs.py`、`fmodd_desktop.py`）通过；`node --check`（`app.js`、`life_page.js`、`i18n.world.js`）通过；六组聚焦回归 **267 passed / 34 subtests passed**。旧前端测试文件的中文投影会隐藏新增控件，本轮新接线断言改用 `raw_web_source()` 显式读取原始源码，产品代码未回退。
- **资源与桌面宿主**：`build_embedded_web_assets.py` 刷新 **530 个文件**，归档 **60,892,181 字节**；`dotnet build src\desktop\WebViewHost.csproj -c Release` 通过（0 警告 / 0 错误），回拷宿主 **199,680 字节**（SHA-256 `7E03A73D02FD9546986CD7B63007F27D9B3CE6840B329A780306568922EFFB98`，FileVersion `2.8.3.0` / ProductVersion `2.8.3Beta`）。
- **单文件 EXE**：`dist\FMSDD-V2.8.3Beta.exe` 为 **76,054,196 字节**，SHA-256 `153F7AC0270363AD1F918499A24E03509449AF922FCCC01755BE0DDCD9DA9288`，版本资源 FileVersion `2.8.3.0` / ProductVersion `V2.8.3Beta`；CArchive **623 条目**、PYZ **297 模块**。包内 `web\app.js`、`web\index.html`、`web\app.css`、`web\life_page.js`、`web\life.css`、`web\i18n.world.js`、`web\i18n.static.js` 与 `desktop_host\FMODD.WebViewHost.exe` 均与仓库源文件逐字节一致（mismatch 0），包内已包含 `world-club-gender` 与女足筛选接线。
- **源码运行包**：在回填本节与错误日志后重建 `dist\FMSDD-V2.8.3Beta-source-runtime`，并以 deflate level 9 压缩为 `dist\FMSDD-V2.8.3Beta-source-runtime.zip`；关键前端与宿主抽样逐字节一致。由于本文件本身随包发布，包内无法记录压缩包自身的最终字节数与 SHA-256，最终数字以 `dist\FMSDD-V2.8.3Beta-第37轮改动总结.md` 为准。
- **交付摘要**：`dist\FMSDD-V2.8.3Beta-第37轮改动总结.md`。

## 第 36 轮（V2.8.2Beta · 俱乐部资料头部、地产购买与地图定位）

### 需求（用户原话要点）

- 从交易所打开俱乐部信息后，顶部资料区左侧过窄、右侧松散，部分文字和数字被压缩，需要重新平衡布局。
- 生活系统中任何资产点击购买都显示“请求无效”，需要修复。
- 在地图右侧的可交易资产列表点击地块时，应跳转并定位到地图上的对应位置。
- 版本号迭代到 `V2.8.2Beta`，继续维护开发日志和错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/fm_odds_web.py` | 地块购买账本元数据 `kind` 改名为 `parcel_kind`，消除与 `charge_combined_funds(amount, kind, ...)` 的参数绑定冲突；`PRODUCT_VERSION` → `V2.8.2Beta` |
| `src/web/app.js` | 世界俱乐部资料页头部拆为 `.world-detail-profile-hero` 与 `.world-detail-profile-facts`：身份与收购操作独占主行，六项收购资料进入全宽资料板；保持原有收购按钮、进度条与事件绑定 |
| `src/web/app.css` | 头部改为两段式网格；资料板采用三列自适应卡片，长名称、长说明和大金额允许换行；窄屏在 760px / 520px 处分级改为两列 / 单列，所有可见字号保持至少 13px |
| `src/web/life_page.js` | 右侧地块行增加 `data-map-focus="true"`；点击时选中地块、以地块坐标居中地图并切到 z15；直接点击地图针仍只选中 |
| `tests/test_life_system.py` | 新增真实 API 路径购买回归，使用与生产签名一致的扣款桩，确保同类重复参数错误再次出现时会直接失败；补充地图定位静态断言 |
| `tests/test_stock_ticket_frontend.py` | 更新俱乐部资料头部结构、三列资料板与窄屏布局断言 |
| `src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj` | 窗口标题、弹窗标题与程序集版本同步到 `V2.8.2Beta` / `2.8.2.0` |
| `README.md`、`CHANGELOG.md`、`docs/development/DEVELOPMENT.md`、`docs/FEATURE_INDEX.md` | 同步版本、当前行为与地图交互边界 |

### 关键决策

- **修复参数绑定，不在前端吞错**：`请求无效` 只是 `TypeError` 被通用错误边界转换后的表现；根因修复点必须在服务端调用处，且新增测试使用参数名为 `kind` 的扣款桩才能复现旧错误。
- **资料头部是共享组件，不做股票专用补丁**：交易所、世界俱乐部目录与集团入口共用同一详情页，布局调整直接改共享结构和样式，避免三处行为漂移。
- **列表行与地图针分开处理**：只有右侧列表行带 `data-map-focus`，因此点击列表会居中并放大，点击地图针不会把地图从指针下方强行移走。
- **定位使用交易层最大级别 z15**：地块行只在 z13–15 出现；点击后以 z15 展示街道级位置，同时保留地块详情与选中状态。

### 验证

- 静态：`node --check src\web\app.js`、`node --check src\web\life_page.js`、`py_compile src\fm_odds_web.py src\tools\life_system.py` 通过。
- 聚焦回归：`tests\test_life_system.py tests\test_stock_ticket_frontend.py` → **29 passed**。
- 新增购买回归会以生产签名的 `charge(amount, kind, *, ...)` 桩捕获参数冲突；当前代码传入 `parcel_kind`，调用成功并完成资金扣款与地块提交。
- 版本与桌面宿主：Python 版本常量、窗口标题和 `.csproj` 程序集版本均已同步；最终单文件 EXE 与源码运行包在验证完成后重建。

### 遗留

- 尚未启动正式 EXE、未连接真实 Football Manager 存档，也未做实机点击验收；本轮验收边界为静态检查、聚焦测试、全量回归与包内容核对。

### 交付与打包

- **桌面宿主**：`dotnet build src\desktop\WebViewHost.csproj -c Release` 通过（0 警告 / 0 错误），重建后的 `FMODD.WebViewHost.exe` 为 **199,680 字节**，FileVersion `2.8.2.0` / ProductVersion `2.8.2Beta`，二进制内窗口标题为 `FMSDD V2.8.2Beta`。
- **内嵌资源**：`build_embedded_web_assets.py` 刷新 **530 个文件**，归档 **60,890,627 字节**；随后 `build_single_exe.py` 生成 `dist\FMODD.exe`（**76,046,810 字节**，SHA-256 `6D51E3A6CBB15E41A158CE65D7DD95AA852D236E7A144A878A8BCCB472F38901`），并复制为 `dist\FMSDD-V2.8.2Beta.exe`。
- **成品内容复核**：CArchive 共 **623 条**；包内 `web\app.js`、`web\app.css`、`web\life_page.js` 与 `desktop_host\FMODD.WebViewHost.exe` 均与仓库源文件逐字节一致。EXE 版本资源为 FileVersion `2.8.2.0` / ProductVersion `V2.8.2Beta` / ProductName 与 FileDescription `FMSDD`。
- **源码运行包**：`build_source_runtime_package.py` 生成 `dist\FMSDD-V2.8.2Beta-source-runtime`（**1,027 个文件 / 183.9 MiB**），并以 deflate level 9 打包为 `dist\FMSDD-V2.8.2Beta-source-runtime.zip`；包内关键源码、宿主与开发日志抽样比对一致。压缩包最终哈希记录在第 36 轮交付总结中，避免文档自引用导致哈希漂移。
- **实机边界**：未启动正式 EXE、未连接 FM、未读写玩家存档；因此本轮不宣称已完成实机点击验收。

## 第 35 轮（V2.8.1Beta · 车库归属、车辆出售与城市资产细化）

### 需求（用户原话要点）

- 修复上一版本购买的车辆在车库中无法显示图片的问题，并补上车辆出售选项。
- 初始不再提供住宅车库，改为最多停放两辆车的“俱乐部车库”。
- 车库应像住宅、商业和工业资产一样在地图上购买，并提供更多车位；住宅、商业、工业资产分别提供 1、2、4 个车位。
- 每城固定 54 块资产太少；工业生产不应落在市中心或公园，资产也不应落入水体。生成数量应按城市等级与类型调整，并让中心、商务区和郊区形成更合理的密度差异。
- 移除车库页中的公寓车库、高级车库和收藏仓库购买项；旧已购记录需要兼容。车库界面与交互需要按可变容量重新设计。
- 版本号暂不改变，继续维护开发日志和错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | schema 升至 2；旧 `home` 迁移为 2 车位 `club`；旧 `.jpg/.jpeg` 车辆图按 `catalog_id` 映射到当前 WebP；房产附赠 1/2/4 车位；新增独立车库地块与 8–40 车位；旧公寓/高级/仓库车库保留为历史车库；新增车辆出售计划与提交；有车房产禁止出售；按城市画像、区县角色和排除区生成 96–127 块资产 |
| `src/assets/life/city_profiles.json` | 新增 8 座支持城市的等级、类型、区县角色、水体/公园排除圆与工业中心缓冲配置 |
| `src/fm_odds_web.py` | 新增 `POST /api/life/vehicle/sell`，售车净额通过 `adjust_bank_balance` 入银行并在入账失败时恢复生活存档快照；移除旧的 `/api/life/garage/buy` 路由；`garage_types` 返回空数组 |
| `src/web/life_page.js` | 新增车库选择状态与工作台；按俱乐部、房产附赠、独立车库、历史车库分组；车位可视化与占用进度；车辆卡新增出售与迁移；地图新增车库筛选；房产页支持独立车库；移除旧车库购买卡片 |
| `src/web/life.css` | 新增车库目录 + 详情工作台、车位格、占用进度、历史车库和响应式布局；保留车辆图的浅色渐变底与 `object-fit: contain` |
| `src/web/i18n.life.js` | 11 种语言补齐俱乐部车库、车位来源、独立车库、历史车库、车辆出售、房产车库迁移和错误文案 |
| `tests/test_life_system.py` | 新增城市类型资产组合、旧车库/旧房产迁移、车辆出售手续费、售车接口入账与银行失败回滚；扩充房产车位和有车房产禁售测试 |
| `tests/test_api_http_dispatch.py` | 新增售车路由分发与旧车库购买路由移除的契约测试 |
| `README.md`、`CHANGELOG.md`、`docs/development/DEVELOPMENT.md`、`docs/FEATURE_INDEX.md`、`docs/ARCHITECTURE.md`、`docs/RUNTIME_CONTRACTS.md` | 同步当前车库归属、车辆出售、城市画像生成与 schema 2 边界 |

### 关键决策

- **车库是资产的附属能力，不再是一组固定商品**。车位来源与房产/地块绑定，出售房产时随之删除附赠车库；有车时先阻止出售，避免车辆失去停放位置。
- **旧存档只迁移、不丢资产**。旧 `home` 成为 `club`；旧公寓/高级/仓库车库不删除，归为“历史车库”且不再出售；旧房产按类型补建车位；旧 JPG 图优先通过当前车辆目录恢复，不只做字符串替换。
- **车辆出售不撤销账户图鉴**。图鉴是经理账户的历史收藏记录，售车只删除当前存档中的车辆资产；银行入账失败时恢复生活文档，避免存档与资金一边成功一边失败。
- **不把公园/水体判断写成单点随机排除**。城市画像保存区县角色、中心缓冲与水体/公园排除区，生成器先按角色决定类型数量，再按不同半径取点；工业地块最先受中心缓冲和排除区约束。
- **旧车库兼容优先于界面整齐**。历史车库只出现在目录，不再提供购买；这是避免升级后已购记录丢失的必要边界。
- **版本保持 `V2.8.1Beta`**：本轮是对首版生活系统的缺陷修复与内容细化，不提升产品版本、窗口标题或 FileVersion。

### 验证

- 静态：`py_compile src\tools\life_system.py src\fm_odds_web.py` 通过；`node --check src\web\life_page.js`、`src\web\i18n.life.js` 通过。
- 生活系统：`tests\test_life_system.py` → **14 passed**；覆盖城市类型资产组合、水体/公园排除、工业中心距离、旧车库/旧图迁移、1/2/4 车位、独立车库、有车房产禁售、车辆出售与银行失败回滚。
- HTTP 契约：`tests\test_api_http_dispatch.py` → **16 passed**；确认 `/api/life/vehicle/sell` 分发到生活服务，旧 `/api/life/garage/buy` 已不存在。
- 国际化：`test_i18n_frontend.py`、`test_i18n_static.py` → **36 passed**；`test_i18n_locale_packs.py` 在直接 Node 文件探针下 **9 passed / 3 failed**，3 条失败是既有 `docs/I18N_ARCHITECTURE.md` 缺失与旧语言包英文/繁中审计，与本轮 Life 文案无关。执行器默认管道句柄在 Windows 下会触发 `WinError 6`，因此使用无管道文件重定向复核。
- 全量回归：使用临时子进程兼容插件规避当前 Windows 执行器的 Node 管道句柄问题后，`pytest tests -q` → **3577 passed / 14 failed / 239 subtests passed**；14 条均为错误日志已登记的仓库既有或测试环境问题，本轮 Life、售车 API 与前端聚焦套件没有新增失败。

### 遗留

- 未启动正式桌面 EXE、未连接真实 Football Manager 存档，也未做实机地图/车库点击验收；本轮验收边界是静态检查、聚焦测试、全量测试与包内容核对。
- 城市画像目前覆盖 8 座中国城市；新增城市时必须同步补充角色与排除区，否则只能走通用半径规则，不能保证当地水体与公园精度。
- 14 条仓库既有全量测试失败仍不处理；本轮只确认没有新增失败。

## 第 34 轮（V2.8.1Beta · 地图四层、高德底图与透明车辆）

### 需求（用户原话要点）

- 地图在下载后仍然加载不出来；交易范围应停在 **z13–15**，世界层、国家层、城市层只显示在此国家/城市拥有多少资产和总资产，不能交易。
- 世界层、国家层、城市层、地块层均按需下载；只有地块层 `z13–15` 可以购买虚构地块。
- OpenStreetMap 在部分网络不可用，希望改用高德地图作为底图，同时保留其他底图选择。
- 车辆图片在亮色主题下是黑底，希望保持透明并略微缩小；车库图片是竖矩形且车辆显示不完整，需要调整 UI 布局。
- 版本号暂不变，继续维护开发日志和错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/web/life_page.js` | 地图缩放范围改为 `z3–15`，世界 `z3–5`、国家 `z6–9`、城市 `z10–12`、地块 `z13–15`；默认缩放改到 `z13`；底图默认高德，视口内无任何成功瓦片时，至少三张失败或 3 秒看门狗超时后回退 OSM；自动回退不再持久化；地图偏好键升级为 `fmsdd-life-basemap-v2`；修复车库容量标题错误引用 `life.garage.capacity` |
| `src/web/life.css` | 展厅、抽卡、收藏条与车库图片统一 `object-fit: contain`，背景改为主题浅色渐变；车库车辆卡改为 `16:9` 横向图片区与信息区，图片宽度约 31%，窄屏上下排列 |
| `src/web/i18n.life.js` | 11 种语言补齐四层地图、下载状态、只读汇总与 `z13–15` 交易说明文案 |
| `src/tools/life_system.py`、`src/fm_odds_web.py` | 世界/国家/城市层包与地块城市包按需安装；`/api/life/city-packs` 返回 `min_zoom=3`、`max_zoom=15`、`trade_min_zoom=13`、`trade_max_zoom=15`、层包摘要和资产聚合 |
| `src/assets/life/cars.json`、`src/web/assets/life/cars/` | 425 辆车全部改为透明 WebP；运行时目录移除旧 JPG；旧 JPG 只留在 `build/life-car-jpg-legacy/`，不进入成品 |
| `tests/test_life_system.py` | 新增地图范围、默认缩放、高德域名、回退不得写死、车库键与透明/容纳式图片样式护栏；补充底图偏好键 v2 断言 |
| `README.md`、`CHANGELOG.md`、`docs/FEATURE_INDEX.md`、`docs/ARCHITECTURE.md`、`docs/RUNTIME_CONTRACTS.md` | 同步地图四层边界、高德/OSM 底图与透明 WebP 说明 |

### 关键决策

- **高德默认、OSM 保留**：高德在目标用户网络下更稳定，OSM 仍留给需要其他底图或高德不可用的环境。底图选择只记录玩家主动选择；自动回退只影响当前视图，避免一次网络抖动永久污染偏好。回退有两条安全网：三张以上瓦片明确失败时快速切换，以及 3 秒内没有任何瓦片成功时处理请求挂起。
- **偏好键升级而不是迁移旧值**：旧版本在单张瓦片失败时曾自动写入 `osm`，已无法区分“玩家主动选择”与“网络故障写入”。改用 `fmsdd-life-basemap-v2` 让升级用户先回到可用的高德默认值，之后手动选择 OSM 仍会正常持久化。
- **层包不是离线瓦片**：世界/国家/城市层包保存本地资产汇总元数据，地块城市包保存本地生成的虚构地块；真实地影像始终按视口请求。这样下载体积可控，也避免把第三方瓦片打包分发。
- **只在 z13–15 交易**：`canTradeMap()` 同时检查当前层为 `parcel` 且缩放处于 `TRADE_MIN_ZOOM..TRADE_MAX_ZOOM`。`z3–12` 只做汇总和总值展示，避免用户在低缩放级别误买地块。
- **车辆素材先修源，再修布局**：黑底来自旧 JPG 本身和固定黑背景，单纯改 CSS 无法解决；因此运行时全部换成透明 WebP，再用 `contain`、浅色渐变和横向卡片保证整车完整显示。
- **版本不变**：本轮是 V2.8.1Beta 的地图与车辆修复，不提升版本号，窗口标题和 FileVersion 继续保持 `V2.8.1Beta` / `2.8.1.0`。

### 验证

- **静态检查**：`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js` 通过；`py_compile src\tools\life_system.py src\fm_odds_web.py` 通过。
- **网络探测**：开发机请求高德瓦片与 OpenStreetMap 瓦片均返回 `200 image/png`，下游下载可被 Pillow 解码为 `256×256` PNG；`index.html` 无 CSP 阻止外链底图。回退监听同时覆盖监听器挂载前已完成的失败图片，以及一直挂起、既不成功也不报错的请求。
- **聚焦回归**：`test_life_system`、`test_i18n_frontend`、`test_i18n_static` → **29 passed**；地图偏好键 v2 版本补充后的聚焦回归通过。
- **全量回归**：`py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3569 passed / 15 failed / 239 subtests passed**；15 条与 `ERROR_LOG.md` 的既有失败清单逐条同名，没有新增失败。测试运行使用空标准流包装，避免当前 PowerShell 的 stdin/stderr 句柄导致额外误报。
- **包内核对**：单文件 EXE 内共 622 个归档条目；`web\life_page.js`、`web\life.css`、`web\i18n.life.js`、`assets\life\cars.json` 与源码逐字节一致；车辆目录有 **425 张 WebP、0 张 JPG**，425 张均可解码、均有透明通道、无 0 字节文件。
- **边界**：未启动正式 EXE、未连接真实 Football Manager、未启动 Hook；本轮没有实机点击验收，验收依据为静态检查、聚焦/全量测试、网络探测和包内容核对。

### 遗留

- 当前城市目录只有中国城市，因此世界层和国家层聚合仍主要反映中国资产；后续新增国家时需要扩城市目录。
- 真实底图依赖网络；层包只保存本地资产数据，不会把高德或 OSM 瓦片变成离线地图。
- 15 条预存在测试失败不在本轮范围，未处理。

### 交付与打包

- **备份（动手前）**：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.1Beta-2-20261017` —— 第 35 轮修改前快照，`project` 3,311 个文件 / 980,543,912 字节，`dist` 1,036 个文件 / 540,807,117 字节。
- **单文件 EXE**：`dist\FMSDD-V2.8.1Beta.exe`，**76,048,209 字节**，SHA-256 `AF1C5F79A84292F00BBC4FB721A76EC56A0C71260788BF79FCB72AAAF6588BF5`；FileVersion `2.8.1.0`、ProductVersion `V2.8.1Beta`、ProductName/FileDescription 均为 `FMSDD`。包内 623 个归档条目，生活页面 CSS/JS/i18n、`cars.json`、`city_profiles.json` 与源码逐字节一致，车辆 WebP 为 425 张。
- **源码运行包**：在本文档与外部改动总结定稿后重建；ZIP 自身的最终字节数、条目数与 SHA-256 记录在 `dist\FMSDD-V2.8.1Beta-第35轮改动总结.md`，避免包内文档自引用哈希。

## 第 33 轮（V2.8.1Beta · 生活系统首版、地产与车辆收藏）

### 需求（用户原话要点）

- 新增生活一级菜单，下设地产地图、我的房产、车库、汽车展厅、神秘车库五个二级页面。
- 首版优先中国城市；地图使用真实城市底图，开放到城市层 z10–12，交易对象为本地虚构地块，城市包按需下载。
- 房产只做购买、出售、出租/经营切换与按游戏日累计收益，避免高频经营操作。
- 车辆作为存档资产进入车库；除展厅购买外，保留神秘车库抽卡玩法；重复车辆保留为独立车辆，不做零件或收藏积分转换。
- 资产按存档保存，车辆收藏图鉴按经理账户保存；正式首版仅收录已获授权的知名厂商车辆。
- 源站缺少 Lamborghini Revuelto 的图片时不补图，直接移除该车辆数据。
- 版本号迭代到 **V2.8.1Beta**，并继续维护开发日志与错误日志。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/tools/life_system.py` | 新增生活领域服务：城市包、虚构地块报价、房产收益、车库容量、车辆估值、展厅购买、神秘车库卡池与存档/账户作用域 |
| `src/web/life_page.js`、`src/web/life.css` | 新增五个生活页面的地图、房产、车库、展厅、抽卡交互与响应式样式 |
| `src/web/i18n.life.js` | 新增 Life 独立文案模块，接入 11 种界面语言与英文回退链；补齐房产收益相关提示 |
| `src/web/index.html`、`src/web/app.js` | 新增生活一级菜单、五个页面容器、状态轮询与 `FMSDDLifeBridge` 桥接 |
| `src/fm_odds_web.py` | 新增 `/api/life*` 路由与生活资产操作入口；版本提升到 `V2.8.1Beta` |
| `src/fmodd_desktop.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj` | 窗口标题、弹窗标题与程序集版本同步到 `V2.8.1Beta` / `2.8.1.0` |
| `scripts/build_single_exe.py`、`scripts/build_source_runtime_package.py` | 构建资源与源码运行包版本同步；开发图库 `car_images/` 不进入源码运行包 |
| `tests/` | 新增 Life 领域测试；同步侧边栏 Life 分组与静态国际化模块顺序的回归夹具 |
| `README.md`、`CHANGELOG.md`、`docs/FEATURE_INDEX.md`、`docs/ARCHITECTURE.md`、`docs/RUNTIME_CONTRACTS.md` | 补充 Life 功能、数据边界、运行时契约与首版说明 |

### 关键决策

- **真实底图、虚构交易**：OpenStreetMap 只提供城市底图，瓦片层级限制在 z10–12，并只请求当前视口；所有地块、区域、房产与价格均由本地城市包确定生成，不把第三方地图数据当成资产真值。
- **生活资产不写 FM 内存**：房产、车库、车辆和抽卡历史走生活存档文档，资金只通过既有银行与钱包账本结算；车辆图鉴单独按经理账户保存，避免污染 FM 原生存档。
- **城市包按需安装**：首版优先中国城市，完整城市包安装后落在 `life_packs/` 复用，避免启动时一次生成全球数据。
- **车辆目录精选而非全量**：运行时展厅与抽卡共用 425 辆授权目录；开发图库 `car_images/` 保留 901 张图片供后续扩展，但不进入源码运行包。
- **同模型重复车辆不合并**：每次购买或抽取都形成独立车辆记录，保留真实车库收藏语义，不引入零件、积分或折价转换。
- **版本同步到宿主**：窗口标题和程序集版本分别改在 Python 与 C# 宿主，单文件 EXE 需重新构建桌面宿主后才显示 `V2.8.1Beta`。

### 验证

- 静态检查：`node --check src\web\life_page.js`、`node --check src\web\i18n.life.js`、`node --check src\web\app.js` 通过；`py_compile src\tools\life_system.py src\fm_odds_web.py src\fmodd_desktop.py` 通过。
- 聚焦回归：`test_life_system`、`test_existing_page_hierarchy`、`test_i18n_frontend`、`test_app_boot_order`、`test_i18n_api_contract`、`test_api_http_dispatch`、`test_shell_frontend_optimization`、`test_dark_mode_frontend` → **76 passed**。
- 全量回归：`py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3566 passed / 15 failed / 239 subtests passed**；15 条与 `ERROR_LOG.md` 的既有失败清单逐条同名，没有新增失败。
- 资源检查：运行时车辆目录 425 辆、图片 425 张；Lamborghini Revuelto（ID 899）不再出现在运行时目录与图库中。
- 包内检查：冻结 Web 资源可正常提供首页与 Life 页面；单文件 EXE 内 `web\life_page.js`、`web\life.css`、`web\i18n.life.js` 与 425 张车辆图片均可从构建包中读取，并与源文件哈希一致。

### 遗留

- 未启动正式桌面 EXE、未连接真实 Football Manager 存档，也未做实机点击验收；本轮验收边界是静态检查、聚焦/全量测试、冻结 Web 冒烟与包内容核对。
- 部分 Life 次级文案在非中文/英文语言仍会回退到英文；核心入口、页面标题与主要操作已覆盖 11 种语言，后续可继续补齐长句翻译。
- 15 条预存在测试失败不在 Life 首版范围内，未处理。

### 交付与打包

- **单文件 EXE**：`dist\FMSDD-V2.8.1Beta.exe`，71,977,083 字节，SHA-256 `38245B0D28796D521B50A38CD08F55C570C85860F5040314A6C53784061DD536`；FileVersion `2.8.1.0`、ProductVersion `V2.8.1Beta`。
- **源码运行包**：`dist\FMSDD-V2.8.1Beta-source-runtime.zip`；包含自带 Python 3.14.6 运行时、启动脚本与 425 张车辆图片，最终字节数、条目数与 SHA-256 以 `dist\FMSDD-V2.8.1Beta-第33轮改动总结.md` 为准。
- **构建边界**：单文件 EXE 与桌面宿主在测试夹具修正前已经构建；本次修正只触及测试文件，不改变产品代码或 EXE 字节。源码运行包在日志补齐、缓存清理后重新构建。

## 第 32 轮（V2.8.0beta · FMODD → FMSDD、亮灯图标与车辆图库）

### 需求（用户原话要点）

- 上一版把名称改为 FMEDD 后，用户反馈 EDD 不好听；本版将软件名改为 **FMSDD**，**S = Stock（股票）**。
- 与上一版相同：只改软件标题、窗口边框和用户可见品牌，**软件文件夹名称、字体目录、存档路径不变**。
- 修改当前公告，更名说明必须写成 **FMODD → FMSDD**，公告中不再提及上一轮的过渡名称。
- 用根目录的 `fmsdd.png` 替换软件图标；首页在未连接存档时使用 `fmsddclose.png`，连接后使用 `fmsdd.png`，形成亮灯效果。
- 抓取 `https://fh5.wikylyu.xyz/cars` 的全部车辆图片，按厂商与车辆等级分类，存放在软件根目录供后续开发。
- 本轮未要求提升版本号，继续 `V2.8.0beta`。

### 改动

| 文件/目录 | 改动 |
| --- | --- |
| `src/web/index.html` | `<title>`、首页标题与顶栏品牌字改为 FMSDD；首页图标新增 `#home-brand-icon`，默认熄灯图 |
| `src/web/app.js` | `renderHome()` 按 `connected` 切换 `app-icon.png` / `app-icon-offline.png`；置顶公告 ID 加 `fmsdd` 后缀 |
| `src/web/i18n*.js` | 45 个产品/脚本/测试文件中的 761 处用户可见品牌改为 FMSDD；11 语言公告重写更名段 |
| `src/desktop/WebViewHost.cs` | 窗口标题 `FMSDD V2.8.0beta`，11 语言启动失败提示同步；`%LOCALAPPDATA%\FMODD` 路径不动 |
| `src/fmodd_desktop.py`、辅助工具 | 弹窗、窗口标题、诊断报告、存档编辑器、XGP 采集器品牌同步 |
| `src/assets/desktop/fmodd.ico`、`src/web/assets/app-icon.png` | 由 `fmsdd.png` 重新生成；文件名保持原样 |
| `src/web/assets/app-icon-offline.png` | 新增，由 `fmsddclose.png` 生成，256×256 |
| `scripts/build_single_exe.py`、`scripts/build_source_runtime_package.py` | 版本资源与源码包启动脚本改为 FMSDD；源码包跳过 `car_images/` |
| `scripts/fetch_fh5_car_images.py` | 新增 FH5 车辆目录图抓取器；支持并发、缓存、PNG 校验与 manifest |
| `car_images/` | 901 张 PNG，134 家厂商、6 个等级；源站缺图条目已移除，不提供替代图 |
| `tests/`（5 个文件） | 品牌期望字符串同步为 FMSDD |

### 关键决策

- **只改品牌，不改兼容标识**：保留全部 `FMODD` 路径、文件名、环境变量、HTTP 头、存档后缀与内存标记；`FMEDD_RUST_NATIVE_DLL` / `FMEDD_CPP_HOOK_DLL` 这两个既有环境变量名也继续保留，避免已有开发环境失效。
- **标题必须重建桌面宿主**：窗口标题写在 C# 宿主内，需重新编译并把产物复制为固定文件名 `FMODD.WebViewHost.exe`，否则单文件 EXE 仍显示旧标题。
- **图标沿用文件名**：`fmodd.ico` 与 `app-icon.png` 被构建脚本和页面引用，替换内容而不改名；首页熄灯态新增独立文件，避免影响 favicon 与启动图标。
- **公告精确改义**：仅做全局品牌替换会留下 “E = Equity” 的旧解释，因此 11 种语言逐条重写更名段，明确 S = Stock 与 FMODD → FMSDD。
- **车辆图库按“厂商 → 等级 → 车名”三层归类**：等级采用游戏 PI 分级 S2/S1/A/B/C/D，车辆类型保留在 manifest，便于后续同时按性能与车型筛选。
- **源站缺图不补位**：目录 API 中的缺图条目（ID 899）已从图库、manifest 与运行时车辆目录中移除；抓取器显式跳过该条目，避免重新抓取时写回。

### 验证

- 静态：`node --check src\web\app.js` 与 18 份 i18n 文件通过；`py_compile` 通过。
- 图标：`app-icon.png` 256×256 RGBA、`app-icon-offline.png` 256×256 RGBA、`fmodd.ico` 可解析。
- 公告：9 个语言文件共 154 条 `announce.*` 值，`FMEDD` 计数为 0；11 个 locale 的置顶标题与更名段逐条检查通过。
- 车辆：manifest 901 条 / failed 0，`source_failures` 与 `fallbacks` 均为空；901 张图均可由 Pillow 解码，尺寸约 587×425。
- 聚焦测试：`test_announcements_frontend`、`test_i18n_frontend`、`test_i18n_shell_dynamic`、`test_i18n_desktop_host`、`test_desktop_runtime_parity`、`test_diagnostic_code_report`、`test_club_legacy_frontend` → **95 passed**。
- 全量回归：`py -3 -X utf8 -m pytest tests -q -p no:cacheprovider` → **3560 passed / 15 failed / 239 subtests passed**；15 条与 `ERROR_LOG.md` 既有清单逐条同名，无新增失败。

### 交付与打包

- **备份（动手前）**：`F:\File\Other\Dev\_fmodd_backups\FMSDD-V2.8.0beta-1-20261017`。
- 单文件 EXE：`dist\FMSDD-V2.8.0beta.exe`，60,691,626 字节，SHA-256 `FA5BBA7DDF4A2187C232D80590273681BAA80AC3A84D068C2898AD3AE2914CFD`；FileDescription / ProductName 均为 FMSDD。
- 源码运行包：`dist\FMSDD-V2.8.0beta-source-runtime.zip`；最终大小、条目数与 SHA-256 见 `dist\FMSDD-V2.8.0beta-第32轮改动总结.md`。
- 包内核对：`web\index.html`、`web\app.js`、两个 app icon、`desktop_host\FMODD.WebViewHost.exe` 与源文件哈希一致；包内 21 份 i18n 文件 `FMEDD` 计数为 0。

## 第 31 轮（V2.8.0beta · FMODD → FMEDD 更名）

### 需求（用户原话要点）

- 软件名改为 **FMEDD**（E = Equity 股权）：软件标题与窗口边框名称要改，**软件文件夹名称不改**，确保字体、存档等文件的读取机制不受影响。
- 修改当前公告中有关内容并说明改名情况；把用户新给的 `F:\File\Other\Dev\football-manager-ODD-main\fmedd.png` 作为新的软件图标替换进去。
- 移除展开侧边栏时顶部的软件标题（截图红框内那一块）。
- 追加要求：置顶公告一里顺带说明**自定义字体、兑换码、盘口设置、连接存档后自动读取俱乐部信息**等功能，并且**兑换码要隐藏一点**，只有仔细看公告的玩家才能发现。
- 本轮**不提升版本号**，仍是 V2.8.0beta。

### 改动

| 文件 | 改动 |
| --- | --- |
| `src/web/index.html` | `<title>` 与首页大标题改 FMEDD、顶栏品牌字改 `Edd`、删除侧栏品牌块（`.sidebar-brand`）；图标引用路径不动 |
| `src/web/*.js`（含 9 份语言包） | 用户可见品牌串改 FMEDD；`window.FMODDI18n` / `X-FMODD-*` / `fmodd-*` 等标识符与本地存储键一律保留 |
| `src/web/i18n.static.js` + `i18n.tw/de/es/fr/ja/pt-BR/pt-PT/ru.js` | 公告一新增【更名说明】与【本版一并带来的其他功能】两段（自定义字体 / 盘口范围 / 连档自动读取 / CDK），标题同步说明更名；11 语言全覆盖 |
| `src/desktop/WebViewHost.cs` | 窗口标题与 11 语言启动失败提示改 FMEDD；`%LOCALAPPDATA%\FMODD\...` 日志与 `window-state.txt`、`WebView2\Default` 目录保持原样 |
| `src/fmodd_desktop.py` | 启动弹窗标题改 FMEDD；`FMODD-Desktop` 互斥体、`FMODD.WebViewHost.exe`、`%LOCALAPPDATA%\FMODD` 保持原样 |
| `src/fm_odds_web.py` | 用户可见中文提示改 FMEDD；`FMODDWorldPlayerWarmup`、`X-FMODD-*` 头名保持原样 |
| `src/assets/desktop/fmodd.ico`、`src/web/assets/app-icon.png` | 由 `fmedd.png` 生成（7 帧 16–256px / 256×256），文件名不变 |
| `src/tools/club_economy.py` | `CDK_CODES` 支持别名：`名取早耶香` / `Natori Sayaka` / `나토리 사야카` 归一化后同码，仍限每存档一次、金额不变 |
| `src/tools/fmodd_save_editor.py`、`src/tools/fm24_process_diagnostic.py`、`src/tools/xgp_probe_collector.py` | 窗口标题、`APP_TITLE`、报告标题等用户可见文案改 FMEDD；`Documents\FMODD\saves`、`*.fmodd`、`FmoddEditorError` 等标识符与路径保持原样 |
| `scripts/build_single_exe.py` | 版本资源的 CompanyName / FileDescription / ProductName 改 FMEDD；`InternalName` / `OriginalFilename` 仍为 FMODD（产物文件名未变） |
| `scripts/build_source_runtime_package.py` | 启动脚本改 `Start-FMEDD.cmd`、包目录改 `FMEDD-{version}-source-runtime`、包内 `README-运行说明.txt` 文案同步 |
| `tests/`（6 个文件） | 4 个 i18n/前端契约与诊断测试的期望文案改 FMEDD；新增 1 条 CDK 别名测试 |

### 关键决策

- **只改“独立品牌名”**：`FMODD` 在本工程里同时承担品牌名、Windows 路径（`Documents\FMODD`、`%LOCALAPPDATA%\FMODD`、`FMODD-Config`、`FMODD-WebView2-*`、`FMODD-Desktop`）、文件名（`FMODD.WebViewHost.exe`、`*.fmodd`）、环境变量（`FMODD_DATA_ROOT`）、HTTP 头（`X-FMODD-*`）、前端全局（`window.FMODDI18n`）、写入游戏内存的字节标记（`FMODDAG1` / `FMODDCG3` / `FMODDYG3`）与域名（`fmodd.com`）。用户明确要求“文件夹名不改、字体与存档读取不受影响”，所以替换按“独立词且不属于上述语境”筛选，逐条确认后才落盘；品牌替换：产品代码（`src/` 与 `scripts/`）40 个文件共 706 处 `FMODD`、18 处 `FModd`，测试 6 个文件 12 处，本轮文档自身 3 个文件（日志里会同时出现新旧两个名字）。
- **首轮替换误伤 6 处路径，全部回滚**（错误日志 E31-01）：`fmodd_desktop.py` 的 `%LOCALAPPDATA%\FMODD` ×2、`WebViewHost.cs` 的 `window-state.txt` 目录 / `WebView2\Default` 目录 / `LocalApplicationData\FMODD`、`app_paths.py` 的 `Documents\FMODD`。这些一旦改名，老存档、窗口状态与字体目录都会“消失”，是本轮最危险的坑。
- **改标题必须重建桌面宿主**：窗口标题写在 `WebViewHost.cs` 里，宿主以二进制随 EXE 打包，因此重建 `src\desktop_host\FMODD.WebViewHost.exe`（136,192 → **199,168 字节**）；不重建则 EXE 标题仍为旧名。
- **图标只换内容不换文件名**：`fmodd.ico` / `app-icon.png` 被构建脚本与 `index.html` 引用，改名会牵动打包链路，收益为零。
- **EXE 产物名仍由脚本写死 `FMODD.exe`**：不改 `--name` 与 `dist` 输出路径，构建链路零风险；交付时复制为 `dist\FMEDD-V2.8.0beta.exe`，并清理 `dist` 中同版本的旧 EXE 与旧 zip（旧产物已在 `_fmodd_backups\FMODD-V2.8.0beta-4-20261017` 留档）。
- **兑换码走“读完才发现”的线索**：公告末句写「本期这枚代码，恰好与公告板署名的那位同名，读到这里的人不妨试上一试」，不直接把码写出来；同时把中文名、拉丁转写与韩文名做成同一枚代码的别名，避免非中文界面玩家看不懂线索。兑换码只影响本地存档数据，不涉及真实金钱。
- **不动公告 id 与版本号**：公告未读状态按最新条目 id 判定，改 id 会让所有玩家重新收到未读提示；版本号按用户要求保持 V2.8.0beta。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 静态：`node --check` 覆盖 15 份前端文件、`py -X utf8 -m py_compile` 覆盖 15 份 Python 文件，全部通过。
- 聚焦：`test_announcements_frontend + test_i18n_frontend + test_i18n_desktop_host + test_home_desktop + test_club_legacy_frontend + test_i18n_shell_dynamic + test_frontend_refresh_recovery + test_desktop_runtime_parity + test_bank_cdk_redemption` → **242 passed**；辅助工具改动后 `test_diagnostic_code_report + test_fmodd_save_editor + test_fm24_diagnostic_connection_probe + test_fm26_diagnostic_save_probe + test_person_table_diagnostic + test_i18n_audit` → **44 passed**。
- 全量：`py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3560 passed / 15 failed / 239 subtests passed**，15 条与“预存在失败”清单逐条同名（第 30 轮 3559 + 本轮新增 1 条 CDK 别名测试，无新增失败）。
- 成品核对（`CArchiveReader` / `ZlibArchiveReader`，只读）：包内 `web\*`、`assets\*`、`desktop_host\*` 共 **112 个资源条目与仓库源文件逐字节一致**（mismatch 0）；`desktop_host\FMODD.WebViewHost.exe` 为新的 199,168 字节版本且含 UTF-16 串 `FMEDD V2.8.0beta`；PYZ（296 模块）内 `tools.club_economy` 含别名元组 `('Natori Sayaka', '나토리 사야카')`，`fm_odds_web` 同时含 `V2.8.0beta` 与开发态 `42-dev`。
- EXE 版本资源：`CompanyName` / `FileDescription` / `ProductName` = **FMEDD**；`FileVersion 2.8.0.0`、`ProductVersion V2.8.0beta`、`InternalName` / `OriginalFilename` = FMODD（文件名未变）。
- 实机核对：**未做**——未启动成品 EXE、未连接 FM，也未读写任何存档（遵守仓库规则）；图标用本机渲染的预览图目视确认。

### 遗留

- 仓库内部文档（`docs/ARCHITECTURE.md`、`docs/RUNTIME_CONTRACTS.md`、`docs/I18N_ARCHITECTURE.md` 等）仍以 FMODD 作为工程内部名称，未做全量改名；后续若要统一，建议单独一轮处理并同步文档链接。
- 有意保留原件：`src/desktop/CompatibleLauncher.cs`（V1.2 遗留启动器，不参与当前构建）、`src/tools/discord_community_setup.py`（`FMODD Community Setup • … • v1` 是已播种内容的匹配标记，改了会造成重复播种）、`src/tools/update_check.py` 的 `User-Agent: FMODD/…`（对外协议标识）。
- `dist\FMEDD-V2.8.0beta.exe` 内 `OriginalFilename` 仍写 FMODD.exe（因为构建脚本的输出名未改）；若后续希望资源面板也完全一致，可在某一轮把 `--name` 与输出路径一并改为 FMEDD.exe。

### 交付与打包

- **备份（动手前）**：`F:\File\Other\Dev\_fmodd_backups\FMEDD-V2.8.0beta-1-20261017` —— `project` 587 文件 / 71,963,758 字节、`dist` 5 文件 / 186,178,529 字节（第 30 轮成品 `FMODD-V2.8.0beta.exe` 60,385,312 字节 / `126D247E065D03E88A68DD6669C7A4E2F1AA84BC13EB56A3648417E0C16B8A06`、`FMODD-V2.8.0beta-source-runtime.zip` 65,396,472 字节 / `AF2E5C0B2668C7A40EF1F9B32B9FF01B3B013B6FA339CC60AA0A4E74C689BACA`）、`SHA256-工程清单.txt` 与 `README-备份说明.txt`。
- **宿主重建**：`dotnet build src\desktop\WebViewHost.csproj -c Release` 通过（0 警告 0 错误），产物回拷 `src\desktop_host\FMODD.WebViewHost.exe` —— **199,168 字节**（第 30 轮为 136,192 字节），二进制内含 UTF-16 串 `FMEDD V2.8.0beta`（旧名 0 处）。文件名保持 `FMODD.WebViewHost.exe`，避免改动 `fmodd_desktop.py` 与打包脚本的查找逻辑。
- **EXE**：`py -X utf8 scripts\build_single_exe.py` 一次通过，产物 `dist\FMODD.exe` **60,587,830 字节**，SHA-256 `6E64FC2DDE3E000275C8523F2E4856C59E41082A80631F0FAC54D6B8BB17B899`（PyInstaller 6.21.0，FileVersion 2.8.0.0 / ProductVersion V2.8.0beta，CompanyName / FileDescription / ProductName = FMEDD），复制为 `dist\FMEDD-V2.8.0beta.exe`；`dist` 中原先的 `FMODD.exe`、`FMODD-V2.8.0beta.exe` 与旧 zip 已清理（旧产物在 `_fmodd_backups\FMODD-V2.8.0beta-4-20261017` 留档），两份第 29/30 轮改动总结同步改名为 `FMEDD-…`。
- **source-runtime**：`py -X utf8 scripts\build_source_runtime_package.py` 重建 `dist\FMEDD-V2.8.0beta-source-runtime`（589 文件 / 90.8 MiB），以 Python `zipfile`（`ZIP_DEFLATED` level 9）压成 `dist\FMEDD-V2.8.0beta-source-runtime.zip` —— **65,541,881 字节 / 589 条目**，SHA-256 `970FEFD02F96AD1D11CF7390433CC250464A36A5A81049775B0EEDDC5036364A`；包目录在压缩后删除。本行的 EXE 哈希、zip 哈希与 `ERROR_LOG.md` 的 E31-04 条目写在打包之后（复核时又修掉 9 处免责声明旧名并重新打包），因此包内文档记录的是第一次打包的编号。
- **交付附带的总结文件**：`dist\FMEDD-V2.8.0beta-第31轮改动总结.md`（放在成品目录而不进 source-runtime 包）。

## 第 30 轮（V2.8.0beta · 交易所剪枝回归修复）

### 需求（用户原话要点）

用户勾选 52 个国家/地区、655 个联赛、17,671 家俱乐部；起初正常，游戏内过几天后筛选摘要仍是 655 / 17,671，但市场公告出现「635 个已勾选联赛不在当前存档中：无法开盘，已从交易所筛选中移除」（更早还有一条 777 个），实际只剩 6 个交易所，刷新俱乐部资料也不恢复。追加证据：读取显示的国家、联赛、俱乐部数量会在游戏时间推进后改变。用户明确要求：**公告与版本号本轮都不更新**。

### 定位过程（只读，未启动 FM / 未启动成品 EXE / 未改存档）

- 读用户存档 `C:\Users\名取早耶香\Documents\FMODD\saves\322857.manager-2002132538.fmodd` 的 `documents.stock_market`：`scope.leagues` 只剩 20 条（英格兰 2、中国 1、德国 1、意大利 1、日本 1、`未分类` 14），而 `state.nations`（交易所登记册）仍有 52 条；`notices` 里两条 `scope_prune`（777 / 2025-11-23、635 / 2025-11-30）、一条 `scope_add` 635。
- 读原生世界缓存 `cache\322857\world\native_clubs_fm26_career-3a0c90a906dc432baccdb3b9d88cd6fd.json`（18,327,265 B、36,792 家俱乐部、`source` 全为 `native_scan`）：把 635 条被删条目逐条对账，**635/635 全部存在于原生目录的 2,264 个联赛对里**——即它们不是「不在存档」，而是「被错误删除」。
- 结论：剪枝用的目录不是世界俱乐部数据库。旧 `_stock_market_tick` 以「当次 `_world_club_directory`（= 当天赛程窗口 + merge native + attach_result_competitions）」为唯一证据，赛程窗口随游戏日期滚动、盘口自定义范围又会收窄它，窗口外的联赛于是集体被判「不在存档」并**从 `scope` 里删除**。用户点过「刷新俱乐部信息」也没用，因为恢复需要世界目录在**同一次**判断里可用，而删除早已落盘。

### 改动

| 文件 | 改动 |
| --- | --- |
| `src/tools/club_stock_market.py` | 新增 `suspended_pairs` / `listed_scope` / `scope_without` / `parked_clubs`；`scope_league_index` 增 `world`（含 `source=native_scan` 行）；`reconcile_scope` 增 `authoritative`（假时只报告 `dropped`，`confirmed=False` 且不返回裁剪后的 scope）；`apply_scope_repair` **重写为 park**（写 `scope_suspended`、只报变化、`confirmed=False` 不动任何状态）；新增一次性 `restore_pruned_scope`；`registry_sync` / `_settle_missing_holdings` 增 `ignore`（暂存交易所的俱乐部不记失踪、不结算退市）；`apply_scope` 在写入新 `scope` 后收敛 `scope_suspended`；`_empty_view` / `market_view` 返回 `listed_scope(...)` 与 `scope_suspended` |
| `src/fm_odds_web.py` | `_stock_market_tick`：删掉「非世界目录也剪枝」的旧分支，改为 `authoritative = scope_index["world"] and not world_club_scanning` → `restore_pruned_scope` → `reconcile_scope(authoritative=…)` → `apply_scope_repair(confirmed=…)`，并把 `parked_clubs(state)` 传给 `registry_sync(ignore=…)`（`confirm_absent=authoritative`）；持久化条件改看 `scope_suspended` / `scope_resumed` / `scope_restored`；`_scope_filter_view` 增 `suspended` 并把「扫描中」时不做审计 |
| `src/web/app.js` | 筛选与盘口的选中模型并入 `suspended`（暂存条目保持勾选）、`*ParkedKeys()` 让待上市联赛不计入已开盘、摘要与行情板加「待上市」提示、`STOCK_NOTICE_KINDS` 增 `scope_suspend` / `scope_resume` / `scope_restore`、`stockHeroHtml` 显示 `stock.scope.suspended` |
| `src/web/app.css` | `.stock-scope-waiting`、`.stock-filter-summary em` 样式（13px，符合最小字号约束） |
| i18n（`i18n.stocks.js` + 8 个语言包） | 5 个新键 `stock.filter.waiting` / `stock.scope.suspended` / `stock.notice.scope_suspend` / `stock.notice.scope_resume` / `stock.notice.scope_restore`，11 语言全补齐；旧 `stock.filter.unresolved` 文案改为「等世界俱乐部数据、会自行恢复、可取消勾选」 |

### 关键决策

- **「暂存」而不是「删除」**：被目录点名不了的一根勾不是目录的东西。条目留在 `scope`，只进 `scope_suspended`，行情板 / 计数器 / 筛选 / 退市结算一起跳过它；世界目录再次列出时自动放行。这样一次误判最多让交易所晚几天开盘，不会丢数据。
- **裁决权给「世界俱乐部目录」**：`world` 标志（存在 `source=native_scan` 行）+ 扫描不在进行中，才是允许暂存与确认退市的充要条件；当天赛程窗口只折名 + 报告。这条把「薄目录删几百个联赛」的可能性从根上关掉，也让 `registry_sync` 的退市判定不再被赛程窗口误导。
- **一次性恢复只在真正恢复成功时才落标记**：首版在「没有 `scope_prune` 公告」与「公告命名但目录列不出」两种情况下都写 `state.scope_pruned_restored`，结果任何早于剪枝的开盘都会把这次机会花掉（新测试 `test_a_scope_pruned_by_a_window_comes_back_on_the_world_read` 抓到）。现在只有确实把联赛勾回来才落标记，其余情况保持机会开放。
- **暂存交易所的持仓不进退市通道**：`parked_clubs` 按持仓记录的 `nation` / `competition` 定位，`ignore` 只对「持仓 + 委托」这组被观察的俱乐部生效，范围足够小、不会顺带放过真正消失的俱乐部。
- **不动公告与版本号**：用户明确要求；市场公告里的 `scope_suspend` / `scope_resume` / `scope_restore` 是数据驱动的行情事件，不是应用公告板文案。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 静态：`node --check src\web\app.js` 与 9 份 i18n 文件通过；`py -X utf8 -m py_compile` 通过。
- 新增测试 8 条：`test_club_stock_market.py` 4 条（薄目录只报告 / 世界目录暂存与解冻 / 旧版删除的联赛一次性找回 / 暂存俱乐部不结算退市）、`test_stock_market_application.py` 5 条改写或新增（暂存并上报 / 世界目录重新列出后解冻 / 扫描中不暂存 / 赛程窗口不缩窄宽范围 / 旧版剪掉的联赛在世界读取时回来）、前端 1 条更新（待上市不计入已开盘联赛）。
- 聚焦：`test_club_stock_market + test_stock_market_application + test_stock_scope_display_frontend + test_stock_market_frontend + test_stock_workspaces_frontend + test_announcements_frontend + test_app_boot_order` → **230 passed**。
- 全量：`py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3559 passed / 15 failed / 239 subtests passed**，15 条与预存在失败清单逐条同名（第 29 轮 3553 passed + 本轮新增 6 条，无新增失败）。
- 真实数据试跑（只读，内存中，未写任何文件）：用户存档 `stock_market` 文档 + 原生世界缓存 → `restore_pruned_scope` 找回 **635** 条（20 → **655** 联赛），`reconcile_scope` 报 11 条连世界目录都列不出的青年/预备联赛 → `apply_scope_repair` 把它们暂存；最终开盘 **644 个联赛 / 17,511 家俱乐部 / 51 个国家/地区**，与用户当初勾选的 655 / 17,671 口径一致（差额正是被暂存的 11 条）。

### 遗留

- 极少数「旧名已被别名折到另一条联赛、而折后那条联赛恰好列不出」的勾不会进 `scope_suspended`（面板仍显示为待上市，行情板不列它）。影响面仅为 `未分类` 青年联赛这类条目，未处理。
- 15 条预存在失败照旧不处理（清单见 ERROR_LOG）。

### 交付与打包

- **备份（动手前）**：`F:\File\Other\Dev\_fmodd_backups\FMODD-V2.8.0beta-3-20261017`（第 29 轮快照，本轮以此为基线）。
- **本轮产物**：重建 `dist\FMODD-V2.8.0beta.exe` 与 `dist\FMODD-V2.8.0beta-source-runtime.zip`，并把改动总结写到 `dist\FMODD-V2.8.0beta-第30轮改动总结.md`；哈希见该文件与备份目录的 `README-备份说明.txt`。
- **交付哈希**：`dist\FMODD.exe` / `dist\FMODD-V2.8.0beta.exe` 均为 **60,385,312 字节**、SHA-256 `126D247E065D03E88A68DD6669C7A4E2F1AA84BC13EB56A3648417E0C16B8A06`（PyInstaller 6.21.0，FileVersion 2.8.0.0 / ProductVersion V2.8.0beta，图标 `src\assets\desktop\fmodd.ico`）；`dist\FMODD-V2.8.0beta-source-runtime.zip` **65,396,472 字节 / 589 条目**、SHA-256 `AF2E5C0B2668C7A40EF1F9B32B9FF01B3B013B6FA339CC60AA0A4E74C689BACA`（zip 在包内文档之后生成，因此本行与下表的备份行写在打包之后）。
- **包内容复核**：用 `PyInstaller.archive.readers.CArchiveReader` 核对包内 `web\app.js` / `web\app.css` / `web\i18n.*.js` 与仓库源文件逐字节一致，并确认新符号（`scope_suspended` / `scope_suspend` / `restore_pruned_scope` / `parked_clubs`）在包内可见。

## 第 29 轮（V2.8.0beta · 公告板改版）

- **需求**：移除既有两条公告，改为三条新公告，发布者统一署名「名取早耶香」。公告一对比 V2.7.0beta 说明 V2.8.0Beta 的更新内容并附股市系统操作说明；公告二说明本版本基于原作者 Starwish 的开源发布、由名取早耶香接手，并郑重提醒软件内下注仅为游戏；公告三整合 V2.7.0 及更早版本的功能与操作说明。用户明确授权补足其未考虑到的细节（备份提醒、免责声明、致谢等）。
- **改动**：`src/web/app.js` 的 `ANNOUNCEMENT_BOARD` 换为三条（`2026-10-17-v280-launch` / `2026-10-17-open-source` / `2026-10-16-feature-guide`，前两条 `pinned:true`）；`announce.author` 与 `announce.entry.*` 全量改写，涉及 `i18n.static.js`（en-GB / zh-CN / ko-KR）与 `i18n.tw.js`、`i18n.de.js`、`i18n.es.js`、`i18n.fr.js`、`i18n.ru.js`、`i18n.ja.js`、`i18n.pt-BR.js`、`i18n.pt-PT.js`。
- **关键决策**：公告区域以 `"announce.title"` 起、以 `announce.entry.stocks.body` 所在行为界，替换时**逐键保留**共用键（`announce.title` / `subtitle` / `pinned` / `expand` / `collapse` / `empty` / `unread`）——首版补丁误把整段覆盖，丢了 `announce.pinned` 等键，`test_announcement_copy_resolves_in_every_locale` 随即报 `en-GB is missing announce.pinned`，改为保留式重建后通过。语言包内嵌结构不一致（static 三语块的键序是 `top.*` 在前、`announce.*` 在 announce 段；部分语言包把 `\n` 写成字面两字符），因此补丁统一按「announce 段首行 → 旧条目末行」定位，不依赖 `top.settings` 锚点。
- **验证**：`tests/test_announcements_frontend.py` 9 条全绿（含逐语言解析三条公告的标题与正文）、`tests/test_i18n_frontend.py` 全绿、`node --check` 覆盖 10 份改动文件；全量 `pytest tests` → **3553 passed / 15 failed**，15 条逐条同名于预存在清单加本轮环境性两条（备份副本对照同样失败，非本轮引入）。备份：`F:\File\Other\Dev\_fmodd_backups\FMODD-V2.8.0beta-2-20261017`（本项目动手前基线，含第 28 轮成品）。
- **遗留**：公告板机制本身未动，未读状态仍以最新条目 id 判定。
- **交付哈希**：`FMODD-V2.8.0beta.exe` 60,377,013 字节 / `1C68FF1AD04096449BD0130AD1D1EDE2B94F1D7C6C4260FA641C4E8029A22EC5`；`FMODD-V2.8.0beta-source-runtime.zip` 65,065,825 字节 / `95EEDB83F0105DCDA862E758C49DEDA56DDDB502D457F77BDB2E0F026FDF98D6`；备份 `FMODD-V2.8.0beta-3-20261017`（project 582 文件 / 196,905,258 字节 + `SHA256-工程清单.txt`）。

## 使用约定

- 轮次编号只在开发日志内使用，把「需求 → 改动 → 验证 → 遗留」串起来；轮次与产品版本号解耦（一个版本可能包含多轮，一轮也可能不升版本号，例如第 13 轮）。
- 每个轮次结束都要补三样东西：本文件的轮次条目、`docs/development/ERROR_LOG.md` 的错误条目（本轮修了哪些问题）、可回滚的备份目录。
- 备份台账在下一节；完整开发环境、命令与验证口径见 `docs/development/DEVELOPMENT.md`。
- 验证结论只写在「验证」小节里，并且必须写清楚是静态契约、隔离测试还是实机核对；隔离测试通过不等于实机行为正确。

## 备份台账

备份目录位于 `F:\File\Other\Dev\_fmodd_backups`，每个目录含 `project`（工程）、`dist`（成品）与 `README-备份说明.txt`（含产物 SHA-256）。

| 备份目录 | 版本 | 主题 | 来源 |
| --- | --- | --- | --- |
| `FMODD-V2.7.0beta-20261015` | V2.7.0beta | 接手时基线；图标、自定义字体目录、单文件 EXE | 交付 1 |
| `FMODD-V2.7.2beta-20261015` | V2.7.2beta | 股市系统立项（自研，不采用他人 UI 与纯概率模型） | 交付 5 |
| `FMODD-V2.7.3beta-20261015` | V2.7.3beta | K 线图、中文金额单位、交易所筛选 | 交付 9 |
| `FMODD-V2.7.3beta-2-20261015` | V2.7.3beta | 筛选计数、全球其他联赛、排序 | 交付 10 |
| `FMODD-V2.7.3beta-3-20261015` | V2.7.3beta | 每日自动刷新、随机摆动、赛事声望加权 | 交付 11 |
| `FMODD-V2.7.4beta-1-20261015` | V2.7.4beta | 盘中刷新、赢球加成调参、窗口标题 | 交付 12 |
| `FMODD-V2.7.5beta-1-20261015` | V2.7.5beta | 每股股本、初始股份数公式、自动扩股 | 第 12 轮 |
| `FMODD-V2.7.5beta-2-20261015` | V2.7.5beta | 股本冻结、扩股区间与除权基准、交易窗横矩形 | 第 13 轮 |
| `FMODD-V2.7.6beta-1-20261016` | V2.7.6beta | 股本下限、资料页接入交易、专业 K 线、交易窗改版 | 第 14 轮 |
| `FMODD-V2.7.6beta-2-20261016` | V2.7.6beta | 指数点位、交易窗反查资料页、一屏下单条 | 第 15 轮 |
| `FMODD-V2.7.7beta-1-20261016` | V2.7.7beta | 首页图标打光、集团页头部重排、俱乐部卡片两态与背景信息 | 第 16 轮 |
| `FMODD-V2.7.7beta-2-20261016` | V2.7.7beta | 卡片展开修复、缩略单行、磁贴单行、盘口范围细化为国家/联赛、交易所冻结持仓 | 第 17 轮 |
| `FMODD-V2.7.7beta-3-20261016` | V2.7.7beta | 行情看板列宽重排（股价/市值封顶、战绩行移入名称列、持股/持仓加宽） | 第 18 轮 |
| `FMODD-V2.7.7beta-4-20261016` | V2.7.7beta | 持股饼图、交易分档（2%/10%/25%）、大宗与限价委托、交易冲击模型、融资（2%–10%、49% 上限） | 第 19 轮 |
| `FMODD-V2.7.7beta-5-20261016` | V2.7.7beta | 直购上限只看 2%（整手不再封顶）、退市改为两次可见（融资误判修复）、委托答复与委托面板、复牌交易所解冻 | 第 20 轮 |
| `FMODD-V2.7.7beta-6-20261016` | V2.7.7beta | 第 21 轮动手前的基线（含第 20 轮成品 `FMODD-V2.7.7beta.exe` 与 source-runtime 包） | 第 21 轮 |
| `FMODD-V2.7.8beta-1-20261016` | V2.7.8beta | 第 22 轮动手前的基线（含第 21 轮成品 `FMODD-V2.7.8beta.exe` 与 source-runtime 包） | 第 22 轮 |
| `FMODD-V2.7.8beta-2-20261016` | V2.7.8beta | 第 23 轮动手前的基线（含第 22 轮成品 `FMODD-V2.7.8beta-第22轮.exe` 与 source-runtime 包） | 第 23 轮 |
| `FMODD-V2.7.9beta-1-20261016` | V2.7.9beta | 第 24 轮（全球行联动）改动完成、打包前的工程快照；F: 盘剩余空间不足（1.7 GB），本轮只留 `project`，`dist` 仍在仓库 `dist\` 未复制 | 第 24 轮 |
| `FMODD-V2.7.9beta-2-20261016` | V2.7.9beta | 第 25 轮（集团全资俱乐部可在交易界面出售与回收股份）改动完成、打包前的工程快照；F: 盘剩余空间约 1.4 GB，本轮只留 `project`（582 文件 / 71,205,592 字节 + `SHA256-工程清单.txt`），`dist` 仍在仓库 `dist\` 未复制 | 第 25 轮 |
| `FMODD-V2.7.9beta-3-20261016` | V2.7.9beta | 第 26 轮（CDK 兑换、只看持仓重绘修复）改动完成、打包前的工程快照；F: 盘剩余空间约 1.09 GB，本轮只留 `project`（583 文件 / 71,280,041 字节 + `SHA256-工程清单.txt`），`dist` 仍在仓库 `dist\` 未复制。注意：`-2-` 快照是第 25 轮改动之前的状态（经核对不含 `buyback_room` / `stock.owned.recover`），因此回退到第 26 轮之前需从 `-2-` 重新叠加第 25 轮改动，或直接用 `dist\FMODD-V2.7.9beta-第25轮.exe` | 第 26 轮 |
| `FMODD-V2.7.9beta-4-20261017` | V2.7.9beta | 第 27 轮（股市二级菜单、持仓/交易记录/市场公告三页、顶栏公告板、版本升到 V2.8.0beta）改动完成、打包前的工程快照；F: 盘可用空间仅约 0.69 GB，本轮只留 `project`（583 文件 / 71,336,795 字节 + `SHA256-工程清单.txt`）与第 26 轮成品 `FMODD-V2.7.9beta.exe`（60,287,949 字节 / `02B795D41E77B9E0820AE6CB033DB8930EDCE1134124EC7CB4D0DC1A0B382296`），`dist` 未复制；本轮同时清理了 `dist` 里 V2.7.0–V2.7.8 的旧版成品与同版本重复开发包，清单见 `dist\FMODD-V2.8.0beta-第27轮改动总结.md` 的「清理记录」一节 | 第 27 轮 |
| `FMODD-V2.8.0beta-3-20261017` | V2.8.0beta | 第 29 轮（公告板改版：三条正式公告、署名「名取早耶香」）改动完成、打包后的工程与成品快照（project 582 文件、`dist` 含 `FMODD-V2.8.0beta.exe` 60,377,013 字节 / `1C68FF1AD04096449BD0130AD1D1EDE2B94F1D7C6C4260FA641C4E8029A22EC5`、`FMODD-V2.8.0beta-source-runtime.zip` 65,065,825 字节 / `95EEDB83F0105DCDA862E758C49DEDA56DDDB502D457F77BDB2E0F026FDF98D6`、第 29 轮改动总结） | 第 29 轮 |
| `FMODD-V2.8.0beta-4-20261017` | V2.8.0beta | 第 30 轮（交易所剪枝回归修复：只暂存不删除、世界目录才裁决、旧版删掉的联赛一次性找回）改动完成、打包后的工程与成品快照（project 597 文件 / 71,987,509 字节、`dist` 5 文件 / 186,178,529 字节，含 `FMODD-V2.8.0beta.exe` 60,385,312 字节 / `126D247E065D03E88A68DD6669C7A4E2F1AA84BC13EB56A3648417E0C16B8A06`、`FMODD-V2.8.0beta-source-runtime.zip` 65,396,472 字节 / `AF2E5C0B2668C7A40EF1F9B32B9FF01B3B013B6FA339CC60AA0A4E74C689BACA`、第 30 轮改动总结） | 第 30 轮 |
| `FMEDD-V2.8.0beta-1-20261017` | V2.8.0beta | 第 31 轮（FMODD → FMEDD 更名、新图标、公告补充）动手前的工程与成品快照（project 587 文件 / 71,963,758 字节、`dist` 5 文件 / 186,178,529 字节，含第 30 轮成品 `FMODD-V2.8.0beta.exe` 60,385,312 字节 / `126D247E065D03E88A68DD6669C7A4E2F1AA84BC13EB56A3648417E0C16B8A06`） | 第 31 轮 |

## 第 13 轮 · 股本冻结、扩股区间与交易窗（V2.7.5beta，2026-10-15）

### 需求（用户原话要点）

1. 扩股不应该让原有持股的价值下降，应按同等比例扩充持有股，确保持股市值不变。
2. 在持股区块点击不属于当前选中交易所的持仓时，K 线、估值、市值都没有正确显示；只有切到对应交易所才正常，需要修复。
3. 扩股区间从 110%–250% 调整为 100%–200%（最多一次翻倍）；每次扩股后的下一次扩股所需股价 = 本次扩股后股价 × 2（30 → 60 触发 → 扩股后 45 → 下次 90）。
4. 交易界面横向拉大（正方形或横矩形），整体更美观。
5. 版本号暂不变；做好开发日志、错误日志迭代。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/tools/club_stock_market.py` | 新增 `listed_shares`（上市股本冻结进记录 `i`）、`repair_legacy_capital`（一次性历史资本修复）、`legacy_priced` / `_legacy_lot`、`LEGACY_SHARES_OUTSTANDING` / `LEGACY_PRICE_BAND` / `CAPITAL_REPAIR_VERSION`；`SPLIT_RATIO_MIN/MAX` 改 1.00 / 2.00 并新增 `MIN_SPLIT_ISSUE`；`shares_at` 改读 `listed_shares`；`_sync_share_book` 回传 `(added, frozen)`；`holding_lots` 改用 `stock_public` + `price_history` + `_decorate` |
| `src/fm_odds_web.py` | `_stock_market_tick` 调用 `repair_legacy_capital`，回传 `capital_repairs` / `capital_repair_count` / `capital_repair_checked`，并把 `share_frozen`、`capital_repair_checked` 纳入保存条件；`public_stock_market` 的 `tick.capital_repairs` 暴露给前端 |
| `src/web/app.js` | `STOCK_NOTICE_KINDS` 新增 `capital`（图标 `split`、`stock.notice.capital`、`stock-flat`）；股票据的蜡烛图放大到 780 × 220（`stock-candle-dialog`、成交量、可交互） |
| `src/web/app.css` | 股票据改横矩形双列（`width:min(1060px, calc(100vw - 40px))`、`grid-template-areas:"chart form" "facts form"`）；≤1180px 改单列 `chart → facts → form`、事实网格 2 列；≤900px 事实网格 1 列 |
| `src/web/i18n.stocks.js` 及 8 个语言包 | 新增 `stock.notice.capital`，十一种界面语言补齐 |
| `tests/test_club_stock_market.py` | 股本冻结、扩股基准、扩股不减少持仓价值、旧资本修复、今日尺度不受影响、持仓行自带盘口 |
| `tests/test_stock_market_application.py` | 修复只跑一次并上公告、跨交易所持仓带完整盘口 |
| `tests/test_stock_capital_frontend.py` | `capital` 公告类型、11 语言文案、交易窗横矩形与窄屏单列、票据宽幅 K 线、票据合并看板与持仓 |

### 关键决策

- **股本冻结而不是每次重算**：`initial_shares` 依赖设施与声望读数，同一家俱乐部第二次读取可能得到不同数字，反复重读会让已上市俱乐部的股本偷偷漂移（老持仓跟着缩水或膨胀）。因此第一次上市就把股本写进记录 `i`，之后只有扩股能改股本；旧记录在首次同步时补写 `i` 并沿用当前股本，所以升级瞬间不会跳变。
- **除权基准固定为「本次扩股后的收盘价」**：用户要的是 30 → 60 触发 → 扩股后 45 → 下次 90。实现上扩股当天不再二次触发，并把除权收盘价写回基准 `b`，因此下一次触发价天然是「本次扩股后价格 × 2」，不需要额外字段。
- **扩股区间收窄到 1.00×–2.00×**：`split_ratio` 仍是确定性哈希（同一俱乐部第 n 次扩股永远同一倍率），但新增 `MIN_SPLIT_ISSUE` = 1% 的保底，避免抽到 1.00 时打印一条「扩股 0 股」的空公告。
- **历史资本修复只动持仓、不动股本**：旧的全局股本时代（1000 万股）成交的持仓，如果直接按新股本重读就会凭空缩水。修复的方式是重放该俱乐部的交易日志，把旧尺度成交价按 `price_then / price_now` 折算成今日尺度的股数与均价，钱不变、股数变；判据用 `LEGACY_PRICE_BAND` 区分尺度，今日尺度成交的持仓原样保留；用 `state["capital_repair"]` 保证只跑一次。
- **持仓行直接借盘口函数**：持仓面板过去只给「最后价格 + 均价」，所以另一个交易所的持仓打开交易窗时 K 线、估值、市值全是空。改成对任何有行情的持仓都调用 `stock_public` / `price_history` / `_decorate`，一次生成完整盘口，前端不需要区分「当前交易所」。
- **交易窗改横矩形**：股票据的图表需要横向空间才看得清 K 线，因此图表在左、表单固定在右（330px 起），事实网格横排在图表下方；窄窗口退回单列堆叠而不是压缩表单。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- `pytest tests\test_club_stock_market.py tests\test_stock_market_application.py tests\test_stock_capital_frontend.py tests\test_stock_market_frontend.py tests\test_world_clubs.py -q -p no:cacheprovider` → 282 passed / 34 subtests。
- 全量 `pytest tests -q`：3406 passed / 13 failed / 239 subtests。第 12 轮基线为 3394 passed / 13 failed，本轮新增 12 条测试；失败清单逐条一致，均为预存在失败（明细见 `docs/development/ERROR_LOG.md` 的「预存在失败」一节），未引入新回归。
- 只读离线演练：把上述修复逻辑跑在真实存档 `322857.manager-2002132538.fmodd` 的股市文档副本上（不写回），PSG（868）`23,612,584 → 163,872,461` 股、均价 `164.65 → 23.72`；已经在新尺度买入的亚眠（831）与今日成交的曼城（679）未被改动，公告尾部出现 `capital` 条目。
- 未实机核对：本轮不改监控/注入逻辑，未启动 FM 进程与成品 EXE，实机观感仍需用户自行验证。

### 遗留

- 13 条预存在失败测试（i18n 目录契约、商店条目元数据、冠军生命周期、赔率档案等）未在本轮处理；它们与本轮改动无关，且已在上份备份工程上逐条复现。
- `docs/I18N_ARCHITECTURE.md` 与测试里引用的 `src/docs/I18N_ARCHITECTURE.md` 路径不一致，属于预存在问题。
- 旧存档的 `capital` 修复公告只在首次开盘时产生一条，界面只显示当前存档的公告尾部（`NOTICE_LIMIT`），若玩家很久不打开股市页则可能看不到这条历史公告，属于可接受的提示损失。

## 第 14 轮 · 股本下限、俱乐部资料接入交易与专业 K 线（V2.7.6beta，2026-10-16）

### 需求（用户原话要点）

1. 股份数下限：`训练设施 × 青训设施 × 青训教练 × 青训招募 × 声望` 低于 100 万股的，按 100 万股作为初始股本（现行公式会算出几百股，导致单股价格高得离谱）。
2. 世界俱乐部（俱乐部资料）页要能呼出股市交易窗，并把交易窗改成与俱乐部资料页同一套观感。
3. K 线图要补全专业元素：日 K 线、横纵坐标、顶峰标点等。
4. 版本号迭代到 2.7.6Beta；继续做开发日志、错误日志迭代。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/tools/club_stock_market.py` | `MIN_SHARES_OUTSTANDING` 1000 → 1,000,000；新增 `MAX_ORDER_SHARE_CAP` 并重写 `max_shares_per_order`；新增 `reads_legacy_capital`（旧尺度判定改成「谁离今日市值更近」），`_legacy_lot` 改走该判据；新增 `club_lot_view`（任意一家俱乐部的一行完整盘口，含 K 线），`holding_lots` 复用它 |
| `src/fm_odds_web.py` | 新增 `LocalOddsState.public_stock_quote(club_id)` 与 `GET /api/stock/quote` 路由：把看板之外的俱乐部（别的交易所、未上市、股市未开启、未连接存档）也答清楚，失败给 `reason` 与服务端中文 `message` |
| `src/web/app.js` | `stockCandleChart` 重写（新增 `axes` / `marks` / `moving` 开关：网格、价格轴、日期轴、MA5/MA10 与图例、区间最高/最低标点徽标、6% / 1% 价格余量）；新增 `openStockTicketForClub`（先查看板缓存，缺了就打报价接口）；世界俱乐部资料页新增「股票交易」入口；`renderStockTicket` 重排成俱乐部资料页版式 |
| `src/web/app.css` | 新增 `.stock-candle-frame` / `.stock-candle-canvas` 与坐标轴、网格、均线、图例、标记、徽标样式；股票据改 1180px 三区网格（`hero` 横跨，`chart` 在左、`facts` 与 `form` 在右）；世界俱乐部资料头部改四列并新增 `.world-detail-stock-control` |
| `src/web/i18n.stocks.js` 及 8 个语言包 | 新增 `stock.chart.note`、`stock.ticket.chart`、`stock.ticket.facts`、`stock.ticket.order`、`world.detail.stock_open`、`world.detail.stock_note`、`stock.quote.unknown_club`、`stock.quote.no_save`、`stock.quote.market_closed`、`stock.quote.not_listed`，十一种界面语言补齐 |
| `tests/test_club_stock_market.py` | 股本下限、单笔上限随股本缩放、单俱乐部盘口、旧尺度判定取更近的一侧 |
| `tests/test_stock_market_application.py` | 报价路由注册、四种 `reason`、报价行与看板行逐字段一致 |
| `tests/test_stock_ticket_frontend.py`（新增） | 资料页入口、`openStockTicketForClub` 行为、成交后清缓存、票据版式、K 线坐标轴与均线、看板行仍是纯蜡烛 |
| `tests/test_stock_capital_frontend.py`、`tests/test_stock_market_frontend.py` | 跟随新版式与图表调用更新断言 |
| 版本号 | `src/fm_odds_web.py`、`src/desktop/WebViewHost.cs`、`src/desktop/WebViewHost.csproj`、`src/fmodd_desktop.py`、`src/web/app.js`、`src/web/app.css`、两个测试文件、`docs/development/DEVELOPMENT.md`、`docs/guides/PRODUCT_GUIDE.md` 一并升到 2.7.6beta |

### 关键决策

- **下限选 100 万股**：股本 = 四档设施 × 声望，理论上最低只有几百股；股价 = 当日市值 ÷ 当日股本，几百股的俱乐部会报出五位数一股的读数，看起来不像钱。100 万股让任何一家上市俱乐部都至少有 107 万级的可交易股数，报价回到可读区间；上限（16 亿股）与四档设施的取值口径都不变。
- **不回溯已经冻结股本的老俱乐部**：股本在第一次上市时写进记录 `i`（第 13 轮），已经上市的俱乐部若在下限抬高后重算股本，等于在玩家眼皮底下改尺子，持仓跟着跳变。因此下限只对「重新上市」的俱乐部生效：在「选择交易所」里取消再勾选，该分支数据会被删除并按当前公式重新初始化（`apply_scope` 的既有语义）。
- **单笔上限跟着股本缩放**：绝对上限仍是 100 万股，但股本只有 100 万股时那等于一次点击买下整家俱乐部，所以新增 `MAX_ORDER_SHARE_CAP = 0.25`：单笔 = `max(min(1,000,000, 股本 × 25%), 股本 × 2%)`。400 万股及以上的俱乐部规则完全不变，小俱乐部也不会被一次点击买空。
- **旧尺度判定改为「离今日市值更近的一侧」**：第 13 轮用价格带（`LEGACY_PRICE_BAND` 0.25×–4×）判断一笔成交属于旧尺度还是今日尺度；股本量级变化后两种读法可能同时落在带内，于是 `reads_legacy_capital` 在价格带成立的前提下再比较 `price × 旧股本` 与 `price × 现股本` 谁离今日市值更近，平局保留今日尺度——宁可少修，不可错修。
- **单俱乐部报价独立成路由**：俱乐部资料页可能在另一家交易所上、甚至看的是未上市俱乐部，看板缓存里没有它的行，`stockById` 查不到就只能开出空窗。`/api/stock/quote` 读同一份市场文档（先 `advance_stock_market` 补齐当日行情）返回与看板逐字段一致的盘口行；前端只在 `ready` 时开窗，否则按 `reason` 给「未上市 / 请先连接存档 / 股市未开启」的本地化提示，服务端 `message` 只作兜底。
- **K 线的标注用 HTML 叠在 SVG 上**：蜡烛画在固定 viewBox 里再拉伸，同一份标记同时服务 38px 的看板行和 220px 的交易窗；文字若也放进 viewBox 会跟着被压扁，所以价格轴、日期轴、均线图例与高低徽标都做成覆盖层，保住 13px 的真实字号。
- **看板行保持纯蜡烛**：38px 高的一行放不下坐标轴与均线，硬塞只会变成噪声；专业元素只出现在大图（指数图 560×150、交易窗 640×220）。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 聚焦：`pytest tests\test_club_stock_market.py tests\test_stock_market_application.py tests\test_stock_capital_frontend.py tests\test_stock_ticket_frontend.py tests\test_stock_market_frontend.py tests\test_world_clubs.py -q -p no:cacheprovider` → 299 passed / 34 subtests。
- 全量 `pytest tests -q`：3423 passed / 13 failed / 239 subtests。第 13 轮基线为 3406 passed / 13 failed，本轮新增 17 条测试（`test_club_stock_market` +3、`test_stock_market_application` +6、新文件 `test_stock_ticket_frontend` 8 条），失败清单逐条一致，均为预存在失败（见 `docs/development/ERROR_LOG.md` 的「预存在失败」一节），未引入新回归。
- 文案：10 个新键 × 11 种界面语言全部就位；`i18n.es.js` 的 `stock.quote.not_listed` 改写措辞以避开英文虚词检查。
- 契约核对：报价行与看板行做逐字段比对（`test_a_quote_matches_the_board_row_it_stands_in_for`），因此资料页开出的交易窗与看板开出的交易窗不会出现两套数据。
- 打包：`dotnet build src/desktop/WebViewHost.csproj -c Release` 重建宿主（`src/desktop_host/FMODD.WebViewHost.exe` 更新为 7B49FD8EEE8374A74BBE171CC3ECFF4B639DA52BB059201181261B74E1103B71），PyInstaller 产出 `dist/FMODD-V2.7.6beta.exe`（60,154,547 字节，SHA-256 `6E61A8BE0CF58BC5BCE8263B823324F4E2D46A72C6A6E2B9D0C11F00D5BAF13A`）与 `dist/FMODD-V2.7.6beta-source-runtime.zip`（65,104,340 字节，SHA-256 `23AA26053CDAC72EAC94B67F7188E544237EF6100E4575E0222F2CC507FA8312`）；备份 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.6beta-1-20261016`（project 579 文件、dist 3472 文件 / 1.38 GiB），哈希与工程树逐文件复核通过；打包前后聚焦测试均为 299 passed。
- 未实机核对：本轮不涉及监控/注入链路，未启动 FM 进程与成品 EXE；K 线观感与交易窗版式需要用户实机确认。

### 遗留

- 已经上市并冻结股本的小俱乐部不会回溯补股；要按新下限重开，需要在「选择交易所」里取消再勾选该俱乐部所在的国家/联赛（该分支数据会被删除并按当前公式重新初始化）。
- 13 条预存在失败测试清单不变，未在本轮处理。
- K 线只画蜡烛、成交量、均线与区间高低标点，没有 MACD / KDJ 之类的副图指标；用户未提出需求，暂不引入。

## 第 15 轮 · 指数点位、交易窗反查俱乐部资料与一屏下单条（V2.7.6beta，2026-10-16）

### 需求（用户原话要点）

1. 图一：国家指数的单位不是货币，`£1,361.07` 这样的读法是错的，要修。
2. 图二：去掉世界俱乐部资料页里的「股票交易」按钮——上一轮把方向做反了。用户要的是「在股市的交易界面里能查看俱乐部资料」，不是「在俱乐部资料页里能交易」，所以世界俱乐部资料页要恢复原样。
3. 图三：在交易界面的 `CLUB EXCHANGE` 右侧加一个小图标按钮，点击跳转到俱乐部资料页；**不是新建界面，而是引用世界俱乐部模块中的俱乐部资料界面**，返回时回到交易界面。
4. 图五：交易界面下方布局不好，尽量让整个交易界面不靠滑块就能看全；买入/卖出不要放在右上「今日收购价」右侧，要利用「股价走势」与「俱乐部股本」下方的空白区域排布，这一部分的 UX 尤为重要。
5. 版本号暂不变；继续做开发日志、错误日志迭代。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/web/app.js` | 新增 `stockCandleFormats`（`money` / `index`）与 `stockCandleChart` 的 `format` 选项，价格轴 / MA 图例 / 高低徽标 / `stockCandleTooltipHtml` 共用同一 formatter，指数图改 `format:"index"`；新增 `openStockTicketClubInfo`（借用 `#world-club-detail-dialog` 与 `openWorldClubDetail`）；`openWorldClubDetail` 新增 `fallbackName` 参数；`renderWorldClubDetailContent` 删除股票入口与 `[data-world-detail-stock]` 监听；`renderStockTicket` 重排（hero 去掉买卖切换，下单条横贯底部）；删除 `openStockTicketForClub`、`state.extras`；`#world-club-detail-dialog` 的 `close` 事件清理借来的返回按钮 |
| `src/web/app.css` | 世界俱乐部资料页两行样式整行还原（`.world-detail-profile` 与 700px 媒体查询）；交易窗段落重写（1180px 宽度、`hero` / `chart` + `facts` / `order` 三段网格、下单条四列、`.stock-quote` 三格成交拆解、`.stock-ticket-club-info` 与 `.stock-club-info-back`、1180px 与 900px 媒体查询） |
| `src/fm_odds_web.py` | 删除 `LocalOddsState.public_stock_quote`、`_get_stock_quote_route` 与 `/api/stock/quote` 路由注册 |
| `src/web/i18n.stocks.js` 及 8 个语言包 | 新增 `stock.ticket.club_info`、`stock.ticket.club_info_back`；退役 `world.detail.stock_open`、`world.detail.stock_note`、`stock.quote.unknown_club`、`stock.quote.no_save`、`stock.quote.market_closed`、`stock.quote.not_listed`，十一种界面语言同步 |
| `tests/test_stock_ticket_frontend.py` | 重写（10 条）：新键 11 语言、退役键不在任何语言、世界俱乐部资料页恢复原样、交易窗借资料页与返回清理、下单条标记、指数非货币格式化、K 线坐标轴与均线、大图开关、看板行纯蜡烛 |
| `tests/test_stock_market_application.py` | 删除「单俱乐部报价」一节（6 条：路由注册与四种 `reason`、报价行与看板行一致） |
| `tests/test_stock_capital_frontend.py`、`tests/test_stock_market_frontend.py` | 跟随新版式尺寸 / 网格与 `stockCandleTooltipHtml` 签名更新断言 |
| 文档 | `docs/FEATURE_INDEX.md`（路由表去掉 `/api/stock/quote`、删「单俱乐部报价」行、渲染行补下单条与反查资料页、`club_lot_view` 改为只服务持仓行）、`docs/RUNTIME_CONTRACTS.md` 第 72 行改述版式与新入口方向、`CHANGELOG.md` V2.7.6beta 补第 15 轮小节、三个 `README*.md` 的 V2.7.6beta 段落改写 |

### 关键决策

- **撤销「资料页 → 交易窗」而不是留着**：上一轮把用户「在交易界面里看俱乐部资料」理解成了「在俱乐部资料页里交易」，加出的按钮与 `.world-detail-stock-control` 让世界俱乐部模块多出一个它不该有的入口。既然入口方向反转，`/api/stock/quote`、`public_stock_quote`、`openStockTicketForClub` 与前端 `state.extras` 缓存全部退役——留着会让同一个能力有两套实现，将来必然分叉。`club_lot_view` 保留，因为它现在只服务 `holding_lots`（持仓行自带盘口），没有对外路由。
- **反查复用同一个对话框，不新建界面**：用户明确要求「引用世界俱乐部模块中的俱乐部信息界面」。实现上不绘制第二份资料页，而是打开同一个 `#world-club-detail-dialog` 并调用既有的 `openWorldClubDetail` / `renderWorldClubDetailContent`，因此资料内容、加载状态、收购入口与实机核对手感都只有一份；唯一的新增是头部的返回按钮，它在对话框 `close` 时被移除，所以下一次从世界俱乐部模块打开资料页时不会残留。
- **返回按钮走自定义 class 而不是 `.close-dialog`**：`.close-dialog` 在全局被绑定为「关闭对话框」，返回按钮要的只是「关闭并回到交易窗」，复用同一个 class 会把两件事混成一件。自定义 `.stock-club-info-back` 只绑自己的 click，视觉上仍与关闭按钮同排（塞进 `.dialog-head-actions`）。
- **买卖切换搬进下单条**：切换按钮原本在 hero 右上「今日收购价」旁边，用户下单时视线要往上跳一次再回来。改成下单条的左端，与股数、成交拆解、确认按钮同处一条横带，买卖是同一个动作的两个方向，放在一起才不会点错。
- **下单拆解从纵向列改成三格**：`股价 / 股数 / 金额` 与 `手续费 / 合计 / 可用` 过去是纵向的 `dl`，占掉整列高度，是滚动条的主要来源。改成三列两行的格子后，下单条压到约 150px 高，1180px 宽的桌面窗口一屏放得下 hero + chart/facts + 下单条。
- **指数用 `format:"index"` 而不是给货币格式化加开关**：指数是相对刻度、股票是金额，两者的读数规则不一样（前者不该有货币符号，后者必须有），所以做成 `stockCandleFormats` 里的两个 formatter，由图表自己选，而不是在 `formatChartAxisMoney` 内部判断「这次画的是不是指数」。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 聚焦：`pytest tests\test_stock_ticket_frontend.py tests\test_stock_capital_frontend.py tests\test_stock_market_frontend.py tests\test_stock_market_application.py tests\test_club_stock_market.py tests\test_world_clubs.py -q -p no:cacheprovider` → 295 passed / 34 subtests。
- 全量 `pytest tests -q -p no:cacheprovider`：3419 passed / 13 failed / 239 subtests。第 14 轮基线为 3423 passed / 13 failed，本轮净减 4 条：删掉单俱乐部报价 6 条、交易窗契约由 8 条增到 10 条（+2），账目吻合 (`3423 - 6 + 2 = 3419`)；失败清单与第 14 轮逐条一致，均为预存在失败（见 `docs/development/ERROR_LOG.md` 的「预存在失败」一节），未引入新回归。
- 文案：新增 2 个键 × 11 种界面语言就位；退役 6 个键在 `src/web/` 内 0 处引用，英文虚词检查通过（`Back to the trade` 避开了 `the|this|that|...|and` 黑名单，故 `club_info_back` 的返回文案不用英文句式）。
- 契约核对：`test_stock_ticket_frontend.py` 断言世界俱乐部资料页内 `data-world-detail-stock` 与 `.world-detail-stock-control` 均为 0 处、交易窗内 `data-stock-side` 只在下单条出现 2 次、`#world-club-detail-dialog` 的 `close` 事件带 `[data-stock-club-info-back]` 清理，因此「入口方向」「不新建界面」「按钮不残留」三条都有静态证据。
- 打包：`dotnet build src/desktop/WebViewHost.csproj -c Release` 通过且产物无变化（本轮未改 C#，`src/desktop_host/FMODD.WebViewHost.exe` 哈希仍是 `7B49FD8EEE8374A74BBE171CC3ECFF4B639DA52BB059201181261B74E1103B71`，因此无需回拷）。PyInstaller 产出 `dist/FMODD.exe`（60,153,830 字节）并覆盖 `dist/FMODD-V2.7.6beta.exe`，SHA-256 `CEE706EF87671ED44A6F2BD8B9A780328FB02746C6D73FDCEFF41E7DE2250B50`；源码便携包重跑后 `Compress-Archive` 得到 `dist/FMODD-V2.7.6beta-source-runtime.zip`（65,110,477 字节，584 条目，SHA-256 `3DB5CA4A4006A42D3BD523347BE0893328A2EC362F6A68A57B4A049BB4C99263`，包内 581 文件 / 89.2 MiB）。
- 备份 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.6beta-2-20261016`（project 566 文件、dist 3472 文件 / 1.384 GiB，含 `README-备份说明.txt`）；备份内三个产物的 SHA-256 与工程 `dist/` 逐字节一致。打包前后聚焦测试各跑一次，均为 295 passed / 34 subtests。
- 未实机核对：本轮不改监控/注入链路，未启动 FM 进程与成品 EXE；交易窗的一屏观感、图标按钮的位置与 K 线读数需要用户实机确认。

### 遗留

- 交易窗的「一屏看全」按 1180px 及以上宽度的桌面窗口设计；更窄的窗口（≤1180px）仍按 hero → chart → facts → order 单列堆叠并出现滚动条，这是布局约束而不是缺陷。
- 13 条预存在失败测试清单不变，未在本轮处理。
- K 线仍只有蜡烛、成交量、均线与区间高低标点，没有 MACD / KDJ 副图；用户未提出需求，暂不引入。

## 第 16 轮 · 首页图标打光、集团页头部重排与旗下俱乐部卡片两态（V2.7.7beta，2026-10-16）

### 需求（用户原话要点）

1. 图一：优化首页中各个板块图标的背景颜色与展示效果。
2. 图二（集团页展开态）：整体宽大松散、没有布局标准；「查看 / 出售」按钮风格与软件主体不搭；左侧俱乐部信息太少，希望补充俱乐部背景信息；整体优化布局。
3. 图三（缩略态）：卡片本来就能点击展开，所以要**去掉「更多」按钮**，展开态也去掉「收起」按钮；缩略态左侧俱乐部名称区块没有在框内纵向居中，可点击区域（以及背景）只有名称文字附近，需要铺满。
4. 去掉「更多」之后，缩略态的「查看」按钮要放大到与展开态一样，并纵向居中。
5. 图五：删掉玩家集团里那条绿色标题（`GROUP OFFICE · MY GROUP` + 集团名 + 铅笔），只保留下方五个俱乐部信息按钮；把改名按钮移到上方「我的集团」标题右侧，并让这个标题直接显示玩家集团名称；右侧「当前估值」等六项集团信息移到「刷新」按钮旁，空出位置给集团名。
6. 版本号迭代到 2.7.7Beta；继续做开发日志、错误日志迭代。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/web/app.css` | `.home-app-icon` 改为 74 × 74 / 圆角 20px 的渐变方块，新增 `::before` 左上柔光层、图标 `drop-shadow`、悬停上浮与十二套板块配色（含新的 `.stocks`）；新增 `.my-clubs-rename`、`.my-clubs-header-tools` 与 `.fmodd-sr-only`；重写 `.owned-club-row-*` 全部规则（卡片 `gap: 14px 16px`、名称区块 `align-content: center` 纵向居中、删除 `.owned-club-row-toggle`、新增 `.owned-club-row-background`、操作按钮改用 `var(--green-2)` / `var(--red)`、901px / 1200px / 1100px / 900px / 700px / 600px 六档响应式重排）；顺手清掉第 16 轮之前残留在 578–585 行的旧卡片规则（旧四栏网格、`margin:-22px 0`、缩略态 36px 按钮） |
| `src/web/index.html` | 集团页标题 `#my-clubs-page-title` 保留 `data-i18n="page.my_clubs.title"` 作为回退，旁边新增改名按钮 `#my-clubs-rename`；`#my-clubs-summary`、`#my-clubs-sync-status`、`#my-clubs-refresh` 收进 `.my-clubs-header-tools` |
| `src/web/app.js` | `worldClubCard`：删掉可见的 `data-owned-club-toggle` 按钮，改为 `fmodd-sr-only` 的 `data-owned-club-toggle-state` 状态文本；展开/收起由名称区块（`role="button"` + Enter/Space）与右侧操作列触发；新增 `ownedClubBackgroundFacts` / `ownedClubBackgroundHtml`；`setExpanded` 不再重写按钮 HTML，只同步 `aria-expanded` / `aria-label` 与隐藏状态文本；`portfolioControlDeck` 删除绿色标题；新增 `renderMyClubsHeader(index)` 并接入 `renderMyClubs` |
| `src/web/dark-theme.css` | 为 `.owned-club-row-background`、描边版 `.owned-club-row-sell` 与名称区块悬停态补深色主题覆盖 |
| `src/tools/world_clubs.py` | 新增 `club_background_metrics(information)`；`read_native_world_club_metrics` 在读取 `_club_information` 之后整理出 `background` 字段并随经营指标返回（估值失败路径也带上） |
| 版本号 | `src/fm_odds_web.py`（`PRODUCT_VERSION`）、`src/desktop/WebViewHost.cs`（窗口标题）、`src/desktop/WebViewHost.csproj`、`src/fmodd_desktop.py`、`docs/development/DEVELOPMENT.md`、`docs/guides/PRODUCT_GUIDE.md` 一并升到 2.7.7beta |
| 文案 | 新增 11 条 `portfolio.background.*`：`i18n.world.js`（en / zh-CN / ko-KR 三元组）+ `i18n.tw/de/es/fr/ru/ja/pt-BR/pt-PT.js` |
| 测试 | `tests/test_player_card_frontend.py`：卡片布局契约改为新的单行网格、缩略态契约断言 `data-owned-club-toggle-state` 与 `.owned-club-row-background`、集团改名断言改为 `my-clubs-rename` / `renderMyClubsHeader` |
| 文档 | `docs/FEATURE_INDEX.md` 的 `owned-clubs-performance` 行、`docs/RUNTIME_CONTRACTS.md` 新增俱乐部背景段、`CHANGELOG.md` 新增 V2.7.7beta 段、三个 `README*.md` 新增 V2.7.7beta 段 |

### 关键决策

- **去掉按钮而不是保留一个更小的按钮**：用户指出卡片本来就能点击展开，按钮是重复入口。可访问性不能跟着消失，所以保留一个 `.fmodd-sr-only` 的状态文本节点（`data-owned-club-toggle-state`），展开/收起仍会播报「更多 / 收起」，`portfolio.more_data` / `portfolio.collapse_data` 两个键继续被引用，`test_i18n_locale_packs` 的紧凑动作文案断言不受影响。
- **整块名称区域可点，而不是只放大文字**：把 `data-owned-club-disclosure` 继续留在名称区块上，区块本身 `align-self: stretch` + `align-content: center`，点击判定仍由卡片上的委托监听完成（`event.target.closest("[data-owned-club-disclosure]")`），所以背景铺满、命中区域等于视觉区域，按钮、链接、输入框、文本选择仍然被排除。
- **背景信息复用已经发生的读取**：`read_native_world_club_metrics` 本来就为经营指标读 `_club_information`（成立年份、球场、上座、设施等级都在里面），因此把这份读取顺手整理成 `background` 字段，而不是另开一次原生读取——展开卡片不会让「读取经营指标」变慢，也不会多一次进程访问。
- **缩略态与展开态共用一套网格，用 `grid-template-areas` 分档**：缩略态是 `identity | metrics | view` 一行，展开态是 `identity/metrics/view` + `form`、`background` 占满整行。这样两种状态的视觉语言一致，也避免再出现「同一张卡片有两条互相覆盖的旧规则」——本轮顺带删掉了 578–585 行残留的旧四栏规则。
- **背景条只显示读得到的字段**：`ownedClubBackgroundFacts` 过滤掉空值，标题、成立年份、球场、容量、上座、身价、人数、四项设施等级谁有数据谁出现；一条都没有时整条不渲染，卡片退回纯指标视图。
- **集团标题就是集团名**：`#my-clubs-page-title` 保留 `data-i18n` 作为兜底文案，`renderMyClubsHeader` 在渲染时把 `app.worldClubs.group_name` 写进去；改名铅笔复用既有的 `openGroupRenameDialog`，未连接存档时禁用。这样「标题 = 集团名」只有一处真值，命令面板里那条重复的绿标题可以直接删掉。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 聚焦：`pytest tests\test_player_card_frontend.py tests\test_dark_mode_frontend.py tests\test_i18n_frontend.py tests\test_world_clubs.py tests\test_i18n_locale_packs.py tests\test_i18n_world_portfolio.py -q -p no:cacheprovider` → `test_player_card_frontend` 33 passed、其余 171 passed / 34 subtests，唯一失败是既有的 `test_i18n_locale_packs::test_shop_item_metadata_is_complete_in_every_locale`（`src/docs/I18N_ARCHITECTURE.md` 缺失，预存在）。
- 全量 `pytest tests -q -p no:cacheprovider`：3419 passed / 13 failed / 239 subtests，与第 15 轮基线逐条一致，无新增失败。
- 文案：`portfolio.background.*` 11 个键 × 11 种界面语言就位（英 / 简中 / 韩在 `i18n.world.js` 三元组，其余 8 种在各自语言包）；繁体沿用既有「球場 / 陣容」等译法，德语、西语、法语、俄语、日语、葡语沿用各自语言包里已有的球场与设施术语。
- 契约核对：删除 `.owned-club-row-toggle` 样式后 `tests/test_dark_mode_frontend.py` 仍通过（该测试检查的是深色主题审计块，`dark-theme.css` 中保留的 `.owned-club-row-toggle` 条目未动）；`tests/test_player_card_frontend.py` 的布局与缩略态断言按新网格改写并通过。
- 未实机核对：未启动 FM 进程与成品 EXE；首页图标打光、集团页头部排布与卡片两态观感需要用户实机确认。
- 记录口径：以下两条为打包完成后回填，`dist\FMODD-V2.7.7beta-source-runtime.zip` 内的 `docs/development/DEV_LOG.md` 快照为回填前版本、只缺这两条验证记录，其余内容与工作区一致；`FMODD-V2.7.7beta.exe` 的哈希不受文档编辑影响。
- 打包与备份：`dotnet build src\desktop\WebViewHost.csproj -c Release` 通过，回拷宿主 `src\desktop_host\FMODD.WebViewHost.exe`（136,192 字节，SHA-256 `2D9B301080460C7C81B8B28FEB92B2D51905FC2984CDE1EE51F8131C88A578BA`）；`py -X utf8 scripts\build_single_exe.py` 产出 `dist\FMODD.exe` 并另存 `dist\FMODD-V2.7.7beta.exe`（60,155,040 字节，SHA-256 `C4F9EB445EF0E1B917DBB6B516050150E4A419F830F236943DEBDB5B0FA45579`，两份一致）；`py -X utf8 scripts\build_source_runtime_package.py` 产出 `dist\FMODD-V2.7.7beta-source-runtime`（581 文件 / 89.3 MiB），压缩为 `dist\FMODD-V2.7.7beta-source-runtime.zip`（65,123,115 字节，SHA-256 `472A5F52ADD64377B870F0FBFED49882DA54AB797D08928C390C15A603DD0249`）。成品内 `web\app.js` / `web\app.css` / `web\index.html` 用 `CArchiveReader` 解包复核，`owned-club-row-background`、`portfolio.background.title`、`owned-club-toggle-state`、`my-clubs-rename` 均在包内。
- 备份：本轮基线落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.7beta-1-20261016`（`project` 566 文件 / 69,312,020 字节；`dist` 4055 文件 / 1,704,593,470 字节；两份产物 SHA-256 与工程 `dist` 一致），`README-备份说明.txt` 写入 11 条更新要点、验证结论与还原方式。

### 遗留

- 卡片缩略态在 ≥1200px 宽时显示 3 个指标，1100–1200px 显示 2 个，≤1100px 显示 1 个，≤600px 又回到 2 个（单列布局）；这是有意的分档而不是缺陷，若实机觉得收敛太早可以整体后移。
- `.owned-club-row-metrics[data-owned-club-disclosure]` 的旧光标规则、深色主题里的 `.owned-club-row-toggle` 条目都保留未删（前者无害、后者被深色主题审计测试引用）。
- 13 条预存在失败测试清单不变，未在本轮处理。

## 第 17 轮 · 卡片展开修复、盘口范围细化与交易所冻结持仓（V2.7.7beta，2026-10-16）

### 需求（用户原话要点）

1. 图一：旗下俱乐部点击「俱乐部名称区域」可展开的详细信息不见了，要求恢复。
2. 图二：缩略状态右侧的数据改为**一行**显示。
3. 图三：集团信息五个信息板块**一行**显示，不要分两行。
4. 设置中细化盘口读取范围：与股票系统一致，做成可勾选**国家、联赛**的功能；并优化读取流程——连接存档后先读国家、联赛、俱乐部信息，再按设定的启用国家、联赛进行盘口刷新与股市初始化。
5. 图四 / 图五：关闭某个交易所后重开会导致所有持仓消失，要求修复；用户建议做成「关闭后持仓资本被冻结、重开才解锁」。
6. 版本号暂时不变；做好开发日志、错误日志迭代，以备后续开发。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/web/app.js` | `initializeOwnedClubCardInteractions` 的 `setExpanded(card, expanded)` 去掉 `button` 参数（根因见下）；删除 `[data-owned-club-toggle]` 的点击绑定，点击委托与键盘处理改为直接翻转 `card.classList.contains("is-expanded")`，`aria-expanded` / `aria-label` 与 `[data-owned-club-toggle-state]` 文案保持同步；`stockHoldingHtml` 增加 `is-frozen` / `stock-frozen-badge` / `frozen_note`，`stockPortfolioHtml` 在 `frozen_value > 0` 时追加冻结市值指标，`stockScopeChangeText` 与 `stockInitBannerHtml` 支持 `scope_freeze` / `scope_unfreeze` 公告；新增整套 `oddsScope*` 模块（约 400 行，位于 `stockChangeText` 之前）：选择集、待提交差异、`syncOddsScopePicker`、联赛懒加载、三态 `oddsScopeCycleNation`、滚动与焦点保持、`renderOddsScopeDialog`、`ensureOddsScopeDialog`（动态创建 `#odds-scope-dialog`，复用交易所筛选的 `.stock-filter-*` 样式）、`saveOddsScopeSelection`；`autoReadStockData` 在 `ensureWorldDataScan()` 之后补 `refreshOddsAfterWorldScan()`，再走股市范围与行情；`#odds-scope` 的 change 与 `#odds-scope-picker` 的 click 接上开关与对话框 |
| `src/web/app.css` | 缩略态指标改回一行（`repeat(4, minmax(0,1fr))`），删除 1200px / 1100px 的逐级隐藏与 600px 的复活规则，900px 以下回落两列；新增 `.portfolio-command-deck > .portfolio-command-grid` 的 `repeat(5, minmax(0,1fr))` 压过 900px 断点的两列；新增 `.odds-scope-custom` / `.odds-scope-picker` 与冻结持仓的 `.stock-holding-row.is-frozen`、`.stock-frozen-badge`、`.stock-holding-frozen-note`、`.stock-portfolio > div.is-frozen dd` |
| `src/web/dark-theme.css` | 为冻结持仓行、悬停态与冻结徽标补深色主题覆盖 |
| `src/web/index.html` | `#odds-scope` 新增 `<option value="custom" data-i18n="settings.market_scope_custom">`；`#apply-odds-reading` 之后新增 `#odds-scope-custom` 区块，内含 `#odds-scope-picker`、`#odds-scope-count` 与 `#odds-scope-note` |
| `src/tools/club_stock_market.py` | `SCHEMA_VERSION` 4 → 5；新增 `_freeze_holdings`（打 `frozen` / `frozen_game_date`、按最后已知报价更新 `last_price`，不卖出）与 `_unfreeze_holdings`；`apply_scope` 的 leavers 改冻结、joiners 改解锁，`settlements` 清空、`cash_credit` 为 0，结果新增 `frozen` / `unfrozen`，公告改为 `scope_freeze` / `scope_unfreeze`；`_settle_missing_holdings` 跳过 `frozen`；`sellable_qty` 对冻结持仓返回 0；`sell_plan` 对冻结持仓抛「该交易所已关闭，持仓已冻结」；`_decorate`、`holding_lots`、`market_view` / `_empty_view` 补 `frozen` 与 `totals.frozen_value` / `frozen_count` |
| `src/tools/app_settings.py` | `ODDS_SCOPE_OPTIONS` 新增 `custom`；新增 `CUSTOM_ODDS_SCOPE`、`MAX_ODDS_SCOPE_NATIONS` = 500、`MAX_ODDS_SCOPE_LEAGUES` = 2000 与 `normalize_odds_scope_selection`（排序、去重、丢弃空值、限量）；`load_settings` 返回 `odds_nations` / `odds_leagues`；`set_odds_reading` 仅在调用方显式传参时写入选集，因此切回预设不丢已勾选范围 |
| `src/tools/preview_cup_odds.py` | 新增 `odds_scope_signature`（预设为空签名，向后兼容旧缓存）、`_custom_scope_index_has_data`、`fixture_in_custom_scope`（按赛事自身国家/地区与两支球队的国家/地区、联赛归属判定）；`filter_fixture_rows_for_odds`、`read_upcoming_fixture_snapshot`、`generate_all_odds` 增加 `custom_scope` 参数与 `custom` 分支；返回体新增 `odds_scope_signature` |
| `src/fm_odds_web.py` | 新增模块级 `expected_odds_scope_signature` 并接入 `startup_cache_validation`（签名不符或缺失判 `settings_changed`）；四条赛程快照比较函数纳入签名相等判断；`_stock_market_caches` 新增 `odds_scope_key` / `odds_scope` 槽位与 `_odds_scope_context`（构建 `competition_nation` / `competition_id_nation` / `club_nation` / `club_league`）；`_refresh_worker` 与 `_schedule_probe` 传入自定义范围；新增 `odds_scope_options()`、`_unverified_scope_filter_view()` / `_scope_filter_view()` 抽取与 `GET /api/settings/odds-scope` 路由；`_post_settings_odds` 透传 `nations` / `leagues`；`apply_stock_market_scope` 文档字符串改为冻结语义并回传 `frozen` / `unfrozen` |
| 文案 | 新增 `stock.filter.frozen`、`stock.filter.unfrozen`、`stock.holding.frozen`、`stock.holding.frozen_note`、`stock.metric.frozen_value`、`stock.notice.scope_freeze`、`stock.notice.scope_unfreeze`、`odds.filter.*` 5 条与 `settings.market_scope_custom` / `_pick` / `_pick_count` / `_custom_note` 4 条；英 / 简中 / 韩写入 `i18n.stocks.js`、`i18n.static.js` 三元组，其余 8 种写入各自语言包；`stock.filter.remove_confirm` 全语言改为冻结语义 |
| 测试 | 新增 `tests/test_odds_scope_custom.py`（22 条：选择集规范化与限量、设置读写与预设保留、签名稳定性、归属判定、赛程过滤、启动缓存签名、前端与路由契约）；`tests/test_club_stock_market.py` 与 `tests/test_stock_market_application.py` 改为冻结 / 解锁断言 |
| 文档 | `docs/RUNTIME_CONTRACTS.md`（交易所范围改冻结语义、`holding_lots` 带 `frozen`、新增盘口 `custom` 范围契约段）、`docs/FEATURE_INDEX.md`（交易所范围行、数据与副作用行、`settings` 行）、`CHANGELOG.md`（V2.7.7beta 新增「集团页、股市界面与交易所冻结（第 17 轮）」小节）、本文件与 `docs/development/ERROR_LOG.md` |

### 关键决策

- **卡片点击失效是「删了按钮没清引用」**：第 16 轮把可见的 `data-owned-club-toggle` 换成无障碍状态文本，但 `setExpanded` 仍然 `card.querySelector("[data-owned-club-toggle]")` 取那个已经不存在的按钮，取到 `null` 后命中 `if (!card || !button ...) return;` 直接返回——所以看起来像「详细信息不见了」，实际是展开动作整条链路被短路。本轮把 `setExpanded` 的按钮依赖彻底去掉（`setExpanded(card, expanded)`），展开状态只由卡片自身的 `is-expanded` 类决定，交互入口有多少个就不再与渲染结构耦合。这条也写进错误日志当作「删除可见元素前先清引用」的教训。
- **「一行显示」按窗口宽度保留分档**：用户要的是一行，但 5 个磁贴在 900px 窗口里一行会挤到读不出数字，因此 `repeat(5, …)` 只覆盖 >900px，≤900px 仍回到两列、≤600px 单列；缩略态指标同理，>900px 一行四格、≤900px 两列。这样满足「一行」的主诉求，又不牺牲窄窗口的可用性。
- **关闭交易所 = 冻住资产，不是卖掉资产**：用户给了两个选项（冻结或结算），并且在需求里说「可以询问我」。选择直接冻结的理由是：取消勾选是一个**范围操作**，玩家点错一次不该产生税务与盈亏事件、也不该改变持仓成本；冻结后 `frozen_value` / `frozen_count` 继续计入总览，重开时按新报价重算，语义上「资产还在、只是暂时不可动」，与真实交易所停牌的直觉一致。结算路径没有被删除：存档里**真的消失**的俱乐部（`_settle_missing_holdings` 的退市扫描）仍按最后收盘价结算，只是跳过带 `frozen` 的持仓，所以两条语义不会互相污染。
- **冻结市值取最后已知报价**：交易所关闭后该所不再有当日报价，若强行按当日纯函数重算就等于变相开市。因此冻结时把 `last_price` 固定下来，面板显示的是「最后看到的市值」，解锁后自然按新报价刷新——既不虚构价格，也不让持仓凭空缩水。
- **自定义盘口范围必须能「不限制」**：`fixture_in_custom_scope` 在范围为空、或俱乐部目录尚未就绪（`_custom_scope_index_has_data` 为假）时一律返回 `True`。原因是盘口刷新可能早于世界俱乐部扫描完成；如果那时按空目录判定归属，会把整窗比赛过滤成 0 场并覆盖掉上一份可用盘口——用「读不到就不过滤」换取「绝不清空盘口」。同理，范围未覆盖时始终保留执教球队的比赛，避免玩家自己的比赛从盘口里消失。
- **缓存签名只对 `custom` 生成**：三个预设的签名恒为空字符串，所以升级前保存的快照仍然等于自身、不会在第一次启动时被无谓地判为 `settings_changed`；只有真正启用了 `custom` 才要求签名匹配，并且缺失签名也算不匹配（旧的 custom 快照不会带着错误范围的赛程继续用）。
- **读取顺序按用户描述重排**：`autoReadStockData` 现在是「读国家/联赛/俱乐部（`ensureWorldDataScan`）→ 按启用范围刷新盘口 → 股市范围与行情」，其中盘口补刷只在 `odds_scope === "custom"` 且世界扫描刚完成时触发一次，失败静默——盘口刷不出来不该阻塞股市自动读取，这与既有的「失败资源独立、不弹无关错误」口径一致。
- **`set_odds_reading` 只在显式传参时写入选集**：否则「切到预设再切回自定义」会把玩家的勾选清空；同时旧请求体（不带 `nations` / `leagues`）继续可用。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 语法与静态检查：`node --check` 覆盖 `app.js`、`i18n.static.js`、`i18n.stocks.js` 与 8 个语言包；`ast.parse` 覆盖 `app_settings.py`、`preview_cup_odds.py`、`fm_odds_web.py`、`club_stock_market.py`。
- 新增聚焦测试：`pytest tests\test_odds_scope_custom.py -q -p no:cacheprovider` → 22 passed（选择集规范化 / 限量、默认值、读写往返、预设保留、非法范围拒绝、签名顺序无关与成员敏感、空范围与缺目录不限制、赛事/联赛/俱乐部三级归属、赛程过滤保留执教球队、启动缓存签名三态、前端与路由契约）。
- 冻结与股市回归：`pytest tests\test_club_stock_market.py tests\test_stock_market_application.py tests\test_stock_market_frontend.py tests\test_stock_capital_frontend.py tests\test_stock_scope_display_frontend.py tests\test_stock_ticket_frontend.py tests\test_stock_market_daily_refresh_frontend.py tests\test_player_card_frontend.py tests\test_dark_mode_frontend.py tests\test_odds_scope_custom.py -q` → 241 passed。
- 盘口与前端回归：`pytest tests\test_odds_profiles.py tests\test_home_desktop.py tests\test_save_context_v2.py tests\test_frontend_refresh_recovery.py tests\test_odds_auto_refresh.py -q` → 218 passed / 2 subtests，唯一失败是既有的 `test_odds_profiles.py::test_pure_profile_import_does_not_load_fm_or_storage_runtime`（子进程 `ModuleNotFoundError: No module named 'tools'`，预存在）。
- i18n 契约：`pytest tests\test_i18n_static.py tests\test_i18n_frontend.py tests\test_i18n_settings.py tests\test_i18n_locale_packs.py tests\test_i18n_catalog_contract.py -q` → 36 passed，两条失败均为预存在（`test_i18n_locale_packs::test_shop_item_metadata_is_complete_in_every_locale` 因 `src/docs/I18N_ARCHITECTURE.md` 缺失；`test_i18n_catalog_contract::test_every_loaded_domain_catalog_has_locale_and_parameter_parity` 因既有的 `i18n.departure.js` 单模块注册 11 种语言）。新增 16 个键在 11 种界面语言中的覆盖由 `test_extension_locale_packs_load_before_core_and_cover_the_english_catalog` 与 `..._placeholders_match_authoritative_english` 验证通过。
- 全量 `pytest tests -q -p no:cacheprovider`：**3441 passed / 13 failed / 239 subtests**（第 16 轮基线 3419 passed / 13 failed，差值正是本轮新增的 22 条测试），13 条失败与基线逐条一致，无新增失败。
- 打包：C# 桌面宿主本轮无改动（`src/desktop/WebViewHost.cs` 未动），因此复用上一轮构建的 `src\desktop_host\FMODD.WebViewHost.exe`（136,192 字节，SHA-256 `2D9B301080460C7C81B8B28FEB92B2D51905FC2984CDE1EE51F8131C88A578BA`），跳过 `dotnet build`；`py -X utf8 scripts\build_single_exe.py` 产出 `dist\FMODD.exe`（60,174,693 字节）并另存 `dist\FMODD-V2.7.7beta.exe`（字节数与 SHA-256 `2297BFE98B901104728BECA75CB7D0AEADD94007B1F904155115F2322A8D8AFD` 与前者一致）；`py -X utf8 scripts\build_source_runtime_package.py` 产出 `dist\FMODD-V2.7.7beta-source-runtime`（582 文件 / 89.4 MiB），压缩为 `dist\FMODD-V2.7.7beta-source-runtime.zip`（65,151,554 字节，SHA-256 `BBC5B69AEB1577CEE3874F2B2B58A9B162EE990EE3A15103328E768BFB59547A`）。
- 成品内容复核：用 `CArchiveReader` 解包 `dist\FMODD-V2.7.7beta.exe`（191 条目），逐文件确认包内 `web\app.js`（2,081,398 字节，含 `oddsScopeCycleNation` / `odds-scope-dialog` / `frozen_note`）、`web\app.css`（745,658 字节，含 `stock-holding-row.is-frozen` / `stock-frozen-badge` / `portfolio-command-deck>.portfolio-command-grid`）、`web\index.html`（105,940 字节，含 `odds-scope-picker` / `odds-scope-custom` / `value="custom"`）、`web\dark-theme.css`、`web\i18n.stocks.js`（含 `stock.filter.frozen` / `odds.filter.title`）与 `web\i18n.static.js`（含 `settings.market_scope_custom`）；再经 `ZlibArchiveReader` 读取包内 `PYZ.pyz`（296 模块）确认 `tools.club_stock_market`（`_freeze_holdings` / `_unfreeze_holdings`）、`tools.preview_cup_odds`（`odds_scope_signature` / `fixture_in_custom_scope`）、`tools.app_settings`（`normalize_odds_scope_selection`）与 `fm_odds_web`（`expected_odds_scope_signature` / `/api/settings/odds-scope`）均已随包发布；包内 `desktop_host\FMODD.WebViewHost.exe` 的 SHA-256 与工作区副本一致，确认宿主未被意外替换。
- 未实机核对：本轮不改监控 / 注入链路，未启动 FM 进程与成品 EXE，卡片展开手感、缩略态与磁贴一行的观感、设置里国家/联赛勾选对话框、关闭交易所后持仓的冻结显示都需要用户实机确认。
- 记录口径：上一条「成品内容复核」与「打包」为打包完成后回填，`dist\FMODD-V2.7.7beta-source-runtime.zip` 内的 `docs/development/DEV_LOG.md` 快照为回填前版本（缺这两条验证记录），其余内容与工作区一致；`FMODD-V2.7.7beta.exe` 的哈希不受文档编辑影响。
- 备份：本轮基线落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.7beta-2-20261016`（`project` 567 文件 / 69,401,751 字节，为本轮代码改动后的工程状态；`dist` 4055 文件 / 1,704,593,470 字节，为**重新打包前**的成品，因此保留第 16 轮那版 `FMODD-V2.7.7beta.exe` 供对照回滚）。上一轮的 `FMODD-V2.7.7beta-1-20261016` 是本轮改动前的真基线，回滚到「第 17 轮之前」请用那一份，回滚到「第 17 轮代码但第 16 轮成品」请用 `-2`。

### 遗留

- 冻结持仓的总览把市值计入 `frozen_value` / `frozen_count`，但**已实现盈亏与冻结部分的均价仍在持仓行内**展示；若实机觉得总览需要一个「可动市值」，可以再加一个 `sellable_value` 指标。
- `_freeze_holdings` 按最后已知报价冻结，因此一个长期关闭的交易所（跨越多次扩股或除权）在解锁时会一次性看到较大的市值跳变。这是「按新报价重算」的定义结果，不是缺陷；若实机反馈跳变过于刺眼，可以改成解锁时把冻结期间的价格序列补算进持仓曲线。
- 盘口 `custom` 范围的归属判定依赖世界俱乐部目录（`competition_nation` / `club_nation` / `club_league`）。目录尚未扫描时**不过滤**，所以在「刚连接存档、目录还没读完」的短窗口内可能读到超出勾选范围的比赛；读取顺序重排已经把目录扫描放在盘口刷新之前，这个窗口在实践中只出现在手动强制刷新的瞬间。
- 900px 以下缩略态指标与集团磁贴仍回到两列（有意保留的分档），如果用户认为窄窗口也必须一行，需要连带调整卡片整体网格与字号。
- 13 条预存在失败测试清单不变，未在本轮处理。

## 第 18 轮 · 行情看板列宽重排（V2.7.7beta，2026-10-16）

### 需求（用户原话要点）

1. 先备份当前项目工程与成品。
2. 图一：行情看板各列宽度不合理。俱乐部代码、名称（含所在联赛）列与 K 线图列宽度**保持不变**；**股价列、市值列太宽**，要缩小，把被挤到的持股列与持仓列让出来。
3. 图二：把持股列里的**比赛情况、联赛排名、声望**移到第 2 列俱乐部名称那一列的联赛名称下方。
4. 持股列与持仓列**拉长**：持股列保留成交量、原始股本、俱乐部持股、扩股数据；持仓列保留持仓股本、持仓资本、成本、可售股本。
5. 自选股按钮、买入卖出按钮**保持不变**；**整体行情看板宽度保持不变**，所有变化只在看板内部调列宽。
6. 版本号暂时不变；做好开发日志、错误日志迭代，以备后续开发。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/web/app.js` | `stockRowHtml` 新增 `formNote`（`stockRankText` 的结果 + `stock.card.reputation`），并在 `.stock-row-name` 内新增 `<small class="stock-row-meta">`：战绩药丸 `.stock-form`（`stockFormText`）+ 排名/声望文本，`title` 给出「完整战绩句 · 排名 · 声望」；`.stock-row-fundamentals` 只留成交量与股本两行，删掉其中的 `.stock-form` 与排名/声望行。`.stock-row-chart`、`.stock-row-price`、`.stock-row-cap`、`holdingHtml`、`.stock-row-actions` 三处按钮均未改动 |
| `src/web/app.css` | `.stock-row` 主规则的 7 条轨道改为 `minmax(148px,1.45fr) 104px minmax(96px,132px) minmax(88px,118px) minmax(150px,1.55fr) minmax(140px,1.4fr) auto`；新增 `.stock-row-name small.stock-row-meta`（`display:flex` + `flex-wrap:wrap`、`white-space:normal`、`text-overflow:clip`、`overflow:visible`）；1440px 断点改为 `minmax(124px,1.25fr) minmax(96px,132px) minmax(88px,118px) minmax(132px,1.3fr) auto`、1180px 断点改为 `minmax(132px,1.3fr) minmax(96px,132px) auto` |
| 文案 | 无新增键：战绩行复用 `stock.card.form_line` / `stock.card.no_form`、`stock.card.league_rank`、`stock.card.reputation`，持股列复用 `stock.summary.turnover` 与股本行 |
| 测试 | 新增 `tests/test_stock_board_layout_frontend.py`（11 条：身份与蜡烛轨道不变、价格与市值封顶、成交量与持仓轨道加宽、三个断点的轨道数与封顶值、战绩行归属名称列、fundamentals 不再含战绩/声望、持仓字段保留、按钮不变、换行覆盖、字号 ≥13px、看板外壳未动） |
| 文档 | 本文件、`docs/development/ERROR_LOG.md`（E18-01 ~ E18-03）、`docs/FEATURE_INDEX.md`（`stock-market` 的界面与样式行、渲染与事件行、初始测试候选行与修改指引句）、`CHANGELOG.md`（V2.7.7beta 新增「行情看板列宽重排（第 18 轮）」小节） |

### 关键决策

- **价格列与市值列从「等分弹性」改成「封顶弹性」**：两列原来分别是 `minmax(112px,.95fr)` 与 `minmax(104px,.9fr)`，列里只有一个金额和一行小字，窗口越宽它们越宽——这是整个看板最浪费的宽度来源，也正是持股列与持仓列被挤窄的原因。改成 `minmax(96px,132px)` / `minmax(88px,118px)` 后两列内容仍然放得下（`132px` / `118px` 由真实字体度量反推），超过封顶的像素按弹性比例回流给持股列（`1.55fr`）与持仓列（`1.4fr`）。**没有动 `.stock-row` 之外的任何宽度定义**，所以看板整体宽度不变。
- **战绩行并入名称列，而不是新开一列**：用户要的是「移到俱乐部名称那一列的联赛名称下方」，而不是「再腾一列」。名称列本来就是弹性列且高度最低（代码 + 名称 + 联赛三行），把战绩行放在它下面既不新增轨道、也不改变 7 列语义，看板总宽因此保持不变。
- **窄窗口下战绩行换行而不是截断**：`.stock-row-name small` 原本是 `overflow:hidden` + `text-overflow:ellipsis` + `white-space:nowrap`，直接搬进来的话战绩会被省略号吃掉。1440px 以下持股列整列隐藏（`.stock-row-fundamentals` 在断点里 `display:none`），那时这行是看板上唯一还能看到战绩的地方，所以显式覆盖为 `white-space:normal` / `text-overflow:clip` / `overflow:visible` 并允许 `flex-wrap:wrap`——宁可这一行占两行高度，也不要把战绩读成半句。
- **字号与看板外壳一律不动**：所有字号沿用原值（13 / 14 / 15px），天然满足「用户可见字号 ≥13px」的契约；`.stock-shell`、`.stock-board`、`.stock-row-actions` 未改，所以「整体宽度不变」与「按钮不变」两条是结构性保证，不是靠调参对齐的。
- **不加运行时字段**：本轮是纯前端布局重排，`/api/stock/market` 的字段与语义、股本与行情计算都没有变化，因此没有改 `docs/RUNTIME_CONTRACTS.md`（本轮无运行时契约变化）。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 语法检查：`node --check src\web\app.js` 通过。
- 真实字体度量：用 Pillow 与系统字体（`msyh.ttc` / `msyhbd.ttc` / `segoeui.ttf`）复刻 CSS grid 的轨道分配算法，在看板宽度 1650px / 2200px / 1200px 三档下逐单元格测量：1650px 时价格列拿到封顶 132px、市值列 118px、持股列 367px、持仓列 336px，中英文所有单元格均不溢出；2200px 时全部适配（价格与市值仍停在封顶值——这正是本次要的「不再随窗口变宽」）。另用同一套字体渲染了一张仿真看板图做目视确认（临时文件，未入库）。
- 聚焦测试：`pytest tests\test_stock_market_frontend.py tests\test_stock_capital_frontend.py tests\test_stock_ticket_frontend.py tests\test_stock_scope_display_frontend.py tests\test_stock_market_daily_refresh_frontend.py tests\test_dark_mode_frontend.py tests\test_stock_board_layout_frontend.py -q -p no:cacheprovider` → **71 passed**。
- 全量：`pytest tests -q -p no:cacheprovider` → **3452 passed / 13 failed / 239 subtests**，13 条失败与接手基线逐条一致（`test_account_store`、`test_championship_lifecycle`、`test_championship_odds`、`test_club_policies`、`test_i18n_catalog_contract`、`test_i18n_locale_packs`、`test_league_points_item`、`test_odds_profiles`、`test_owned_club_operations`×2、`test_pending_result_search`、`test_profit_analysis_colors`、`test_refresh_optimization`），无新增失败。
- 未实机核对：本轮没有启动 FM 进程与成品 EXE。列宽手感、战绩行在真实窗口宽度下的换行位置、深色主题下的观感都需要用户实机确认；深色主题只做静态复核（`.stock-form` 的药丸样式原样复用，`dark-theme.css` 的既有覆盖因此继续生效，无需新增色值）。
- 记录口径：本节的「打包」与「成品内容复核」为打包完成后回填，`dist\FMODD-V2.7.7beta-source-runtime.zip` 内的 `docs/development/DEV_LOG.md` 快照为回填前版本（缺这两条），其余内容与工作区一致；`FMODD-V2.7.7beta.exe` 的哈希不受文档编辑影响。

- 打包：C# 桌面宿主本轮无改动（`src/desktop/WebViewHost.cs` 未动），因此复用既有的 `src\desktop_host\FMODD.WebViewHost.exe`（136,192 字节，SHA-256 `2D9B301080460C7C81B8B28FEB92B2D51905FC2984CDE1EE51F8131C88A578BA`），跳过 `dotnet build`；`py -X utf8 scripts\build_single_exe.py` 产出 `dist\FMODD.exe`（60,174,306 字节，SHA-256 `5199D1F3572A0E518A186AB4D3C913E06EE8A173F424E1AFFCC7C73D5943A477`）并另存 `dist\FMODD-V2.7.7beta.exe`（哈希相同）；`py -X utf8 scripts\build_source_runtime_package.py` 产出 `dist\FMODD-V2.7.7beta-source-runtime`（583 文件 / 93,742,539 字节），压缩为 `dist\FMODD-V2.7.7beta-source-runtime.zip`（65,160,372 字节，SHA-256 `39B6B6DD53671D26F09D384CA1389F0A90537790BADD85A0073B3B43B221419B`）。打包前删除了 `.tmpcheck/`（第 17 轮的教训：临时目录会被 source-runtime 包照单收下）；本次第一次打包仍混入了一个临时的仓根辅助脚本（584 文件），删除后重建为 583 文件，与「第 17 轮 582 文件 + 本轮新增 1 个测试文件」对得上。
- 成品内容复核：用 `CArchiveReader` 解包 `dist\FMODD-V2.7.7beta.exe`（191 条目），确认包内 `web\app.js`（2,081,580 字节，含 `stock-row-meta` 与 `const formNote = [`）、`web\app.css`（745,840 字节，含 `minmax(96px,132px)` / `minmax(88px,118px)` / `minmax(150px,1.55fr)` / `minmax(140px,1.4fr)` / `.stock-row-name small.stock-row-meta`，且旧的 `minmax(112px,.95fr)` 已不在包内）、`desktop_host\FMODD.WebViewHost.exe`（136,192 字节，SHA-256 与工作区副本一致，确认宿主未被意外替换）；经 `ZlibArchiveReader` 读取包内 `PYZ.pyz`（296 模块）确认 `fm_odds_web`、`tools.club_stock_market`、`tools.preview_cup_odds` 随包发布；条目清单里没有 `.tmpcheck`、没有临时脚本。source-runtime 包内 `docs/development/DEV_LOG.md`、`docs/development/ERROR_LOG.md`、`CHANGELOG.md` 均含第 18 轮内容，新增测试 `tests/test_stock_board_layout_frontend.py` 也在包内。
- 打包期插曲：打包时机器上有一个**运行中的第 17 轮实例**（`dist\FMODD-V2.7.7beta.exe`，PID 5172 / 27248，14:23 启动），Windows 不允许覆盖运行中的可执行映像，因此把旧文件改名为 `dist\FMODD-V2.7.7beta-round17-in-use.exe`（60,174,693 字节，SHA-256 `2297BFE98B901104728BECA75CB7D0AEADD94007B1F904155115F2322A8D8AFD`，与第 17 轮记录逐位一致）之后才写入新构建。改名不影响正在运行的进程；该副本在实例关闭前一直处于锁定状态，实例关闭后已删除（删除后 `dist/` 里 V2.7.7beta 相关条目只剩 `FMODD-V2.7.7beta.exe`、`FMODD-V2.7.7beta-source-runtime/` 与其 `.zip`），第 17 轮那版可执行文件仍保存在本轮的备份目录里。
- 备份：本轮基线落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.7beta-3-20261016`（`project` 567 文件 / 69,426,695 字节，为**本轮改动之前**的工程状态——即第 17 轮交付的代码，加上其后为打包回填的文档改动；`dist` 4056 文件 / 1,704,772,033 字节，为**重新打包前**的成品，因此里面留着的第 17 轮那版 `FMODD-V2.7.7beta.exe`（60,174,693 字节，SHA-256 `2297BFE9…8AFD`）与上一条「运行中实例」改名后的副本哈希一致，可互相印证；它同时说明本轮的备份是一份**真正在改动之前**的基线）。回滚到「第 18 轮之前」用 `FMODD-V2.7.7beta-2-20261016`，回滚到「第 17 轮之前」用 `FMODD-V2.7.7beta-1-20261016`。

### 遗留

- 1440px 以下持股列整列隐藏，战绩行落到名称列换行显示；1180px 以下市值列也隐藏。若用户认为窄窗口也必须看到股本与持仓，需要重新分配断点而不是继续压这一行。
- 价格列与市值列的封顶值（132px / 118px）是按「金额 + 一行小字」在系统中文字体下的实测宽度反推的；若后续金额单位显示方式改变（例如中文单位延长了 `stock.trade.market_cap` 这类小字），封顶值需要重新测量。
- 13 条预存在失败测试清单不变，未在本轮处理。

## 第 19 轮 · 持股饼图、交易分档、大宗/限价委托与融资（V2.7.7beta，2026-10-16）

### 需求（用户原话要点）

1. 把持股列里的**成交量**移到股价列的行情系数下方；持股列做成**饼图**，鼠标移动可查看各持股多少、占比百分之多少；**扩股数据不在此列显示**。
2. 用户交易会导致股价波动，**涉及的百分比越大影响越大**。
3. 添加**大宗交易**与**当日限制交易**：单次交易最大可直购 2% 股本数量的股票，超过 2% 需要提交大宗交易申请，单日单次申请最多 10% 股本；持仓占比超过该俱乐部当前总股本的 **25%** 时无法再进行大宗买入或普通买入，但可市价出售或定价抛售，这些行为都会对股价造成波动。
4. 交易界面「俱乐部股本」模块右侧添加**融资**按钮：按当前股价提供自定义股本数量的资金，最低 2%、单日单次最多 10%；持仓占比达到 **49%** 时不再可以融资。
5. 版本号暂时不变；做好开发日志、错误日志迭代。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/tools/club_stock_market.py` | `SCHEMA_VERSION` 5 → 6；`state` 新增 `impact` / `finance` / `orders`（`_normalize` 补空值，旧存档无需迁移）；新增常量 `MAX_DIRECT_BUY_RATIO` 0.02 / `MAX_BLOCK_BUY_RATIO` 0.10 / `MAX_BUY_STAKE` 0.25 / `MIN_FINANCE_RATIO` 0.02 / `MAX_FINANCE_RATIO` 0.10 / `MAX_FINANCE_STAKE` 0.49 / `BLOCK_PRICE_PREMIUM` 0.01 / `BLOCK_SIZE_WEIGHT` 1.25 / `MAX_PENDING_ORDERS` 8 / `TRADE_IMPACT_*`；新增 `trade_impact_delta` / `impact_decay` / `trade_impact` / `plan_impact` / `_record_impact` / `_drop_impact`、`market_extras` / `finance_extras` / `extras_signature` / `impact_of` / `finance_of`、`submit_block_order` / `place_limit_sell` / `cancel_order` / `cancel_orders_for` / `fill_pending_orders` / `order_slots` / `reserved_qty` / `drop_order` / `restore_order`、`max_finance_shares` / `finance_plan` / `commit_finance`（新到手的股写 `locked_qty` / `locked_ordinal`，与买入同样锁定到下一个游戏日）/ `revert_finance`、`trading_limits` / `share_record` / `trading_quote(kind=…)` / `club_lot_view`；`max_direct_shares` 重写为 `max(1, min(整手, 股本 × 2%))`、`max_block_shares` 重写为 `max(1, 股本 × 10%)`（整手从此只压不抬）；`_normalize` 补齐三个新字段并把低于当前版本的文档版本号提到 `SCHEMA_VERSION`；`market_cap` 叠加 `finance_of`；`detect_splits` 改用 `finance_extras`；`market_view` / `stock_public` 透传 `limits` / `orders` / extras，`prev_close` 用今日股本 + 融资 |
| `src/fm_odds_web.py` | 缓存键纳入 `extras_signature`；`_stock_market_factors` 传 `market_extras`（收购价跟随股市）；`_stock_market_tick` 调 `fill_pending_orders` + `_settle_stock_order_cash`；新增 `submit_stock_order` / `cancel_stock_order` / `finance_stock` 与路由 `/api/stock/orders`、`/api/stock/orders/cancel`、`/api/stock/finance`；`club_economy.TRANSACTION_LABELS` 新增 `stock_block_order` / `stock_block_rollback` / `stock_order_refund` / `stock_limit_sell` / `stock_finance` / `stock_finance_rollback` |
| `src/web/app.js` | 饼图族 `stockHoldingSlices` / `stockPieLabel` / `stockPieHtml` / `stockPieTooltipNode` / `stockPieHoverStart` / `stockPieHoverEnd` / `stockPieHoverTarget`；`stockRowHtml` 把成交量移到股价列（`.stock-row-turnover`）、持股列换成饼图；限额族 `stockMarketLimits` / `stockRatioText` / `stockStakeText` / `stockImpactPreview` / `stockDirectCap` / `stockBlockCap` / `stockStakeRoom` / `stockAffordableQty`；票据重构 `stockTicketMode` / `stockTicketQuote` / `stockLimitStripHtml` / `stockOrderStripHtml` / `renderStockTicket` / `updateStockTicketQuote` / `submitStockTicket`（大宗与限价走 `/api/stock/orders`）/ `cancelStockOrder`；融资族 `stockFinanceState` / `stockFinanceRoom` / `openStockFinance` / `renderStockFinance` / `updateStockFinanceQuote` / `submitStockFinance`；公告新增 `order` / `order_fill` / `order_cancel` / `finance` 四类卡与 `stockTradeHtml` 的 `finance` 面 |
| `src/web/app.css`、`dark-theme.css` | 删除 `.stock-row-fundamentals` 系列规则，改为 `.stock-row-turnover` 与 `.stock-pie-*`（ring / track / slice / mine / club / dot / center / note / legend / tooltip）；新增 `.stock-mode-toggle`、`.stock-limit-field` / `.stock-limit-strip`、`.stock-quote-impact`、`.stock-block-switch`、`.stock-order-strip` / `-row` / `-cancel` / `-empty`、`.stock-ticket-fact-finance`、`.stock-finance-action`、`.stock-finance-dialog` 与对应深色覆盖；窄屏隐藏 `.stock-row-pie`；字号全部 ≥13px |
| 文案 | 59 个新键 × 11 语言（英 / 简中 / 韩写入 `i18n.stocks.js` 三元组，其余八个语言包各自补齐），全部 `node --check` 通过 |
| 测试 | 新增 `tests/test_stock_order_frontend.py`（59 键 × 9 文件校验 + 12 条契约：成交量归属、饼图与悬停、限额读接口、直购/申请分档、模式文案、大宗与限价下单载荷、委托队列与撤单、冲击预估、融资、公告、样式）；`tests/test_club_stock_market.py` 扩到 78 条；`tests/test_stock_board_layout_frontend.py` / `test_stock_capital_frontend.py` / `test_stock_ticket_frontend.py` 的 6 条断言随列归属迁移 |
| 文档 | 本文件、`docs/development/ERROR_LOG.md`（E19-01 ~ E19-03）、`docs/FEATURE_INDEX.md`（`stock-market` 的别名段、界面与样式行、渲染与事件行、交易行、数据与副作用行、初始测试候选行与修改指引句）、`docs/RUNTIME_CONTRACTS.md`（股市契约的 extras / 分档 / 委托 / 融资 / 饼图）、`CHANGELOG.md`（V2.7.7beta 新增「市场持股饼图、交易分档、大宗/限价委托与融资（第 19 轮）」小节） |

### 关键决策

- **整手从「抬上限」改成「只压上限」**：历史上为 100 万股的小俱乐部保留过一手 25% 的点击量（那时天花板就是 25%），但本轮把 2% / 10% / 25% 写成硬规则之后，`max(整手, 2%)` 就变成了「小俱乐部一次点击直购 25%」——不但违反用户明说的 2%，还会一次吃掉全部持股额度，把大宗申请这条路径整个跳过。修正是把整手放进 `min`：`max_direct_shares = max(1, min(整手, 股本 × 2%))`，于是整手只在「股本大到 2% 超过 100 万股」时生效（5 千万股以上保留历史点击量），小俱乐部一律退回 2%，想多买只能走大宗。大宗侧则完全去掉整手兜底，严格 10%——股本下限的 10% 已是 10 万股，让整手抬高等于把上限交给一笔申请。
- **限额是「占比分档」而不是一个数字**：单次直购 2%、单笔大宗申请 10%、持仓天花板 25%、融资单次 2%–10%、融资天花板 49%——五条限制都写成「当日股本的百分比」而不是绝对股数，因为 100 万股的小俱乐部与 16 亿股的大俱乐部在绝对股数上差三个数量级，只有占比能同时约束两头。所有百分比只出现在模型层 `trading_limits()`，前端 `stockMarketLimits` 读它、服务端 `trading_quote` 也读它，因此文档里说的「2%」不会在三个地方各写一遍。
- **大宗交易是「申请」而不是「立刻成交」**：用户说的是「提交大宗交易申请」，所以它落在 `state.orders` 队列里由 `fill_pending_orders` 在下一个游戏日交割，而不是当场吃掉 10% 的股本。钱在申请时就扣（俱乐部是「被通知交割」而不是「被问愿不愿意」），撤单原额退回——这样账户在交割日绝不会临时缺钱，也不会出现「点了申请但钱被别的操作花掉」的中间态。
- **委托队列上限 8 笔**：不设上限的话，玩家可以用几百笔待成交申请把 tick 的推进成本推高；8 笔足够正常玩法（同一所同时挂着几笔大宗与几笔限价），超过就报错而不是静默丢弃。
- **定价抛售预留股份**：限价卖出在下单时就把股份从 `sellable` 里扣掉（`reserved_qty`），否则玩家可以一边挂单一边把同一批股票市价卖掉，成交时才发现没有股票。触价当天按**市价**成交（不低于委托价），因此卖方拿到的永远不比挂单价差。
- **交易冲击是「衰减的位移」而不是「即时乘子」**：`trade_impact_delta` 的量级 = `TRADE_IMPACT_K` × 股数占比，按 10 天半衰期衰减、保底 30%，与新闻脉冲用同一套衰减口径——所以买一笔会把报价抬起来一段时间，然后像新闻一样把价格交还给俱乐部的战绩。这也让「占比越大影响越大」是结构性的（量级直接正比于占比），而不是靠调系数拼出来的。
- **`finance_extras` 隔离扩股判定**：`detect_splits` 用「没有冲击、只有增资」的 extras。否则一笔大宗把报价抬到基准价 2 倍就会替俱乐部触发一次扩股，等冲击衰减回原值，俱乐部就被永久定在远低于自身基本面的价位——这是本轮最容易踩、也最隐蔽的坑。
- **融资是增资，不是拉高股价**：`market_cap = intrinsic_value × market_factor + finance_of`，而股本同时增加 `finance_of / price` 股，所以当日单股报价不动，涨的是市值与收购价。用户要的是「提供资金」，不是「用钱把股价买上去」；把两者分开也让 49% 天花板有确定含义。
- **饼图与 K 线共享一套指针逻辑**：`pointermove` 只驱动 `stockPieHoverTarget` 一次，找不到扇区就收掉提示，因此一行不会挂两套事件、也不会在两者之间闪烁。
- **成交量搬去股价列而不是删除**：用户要的是「移到行情系数下方」，而且成交量本来就属于价格信息（与 K 线的成交量带同一口径），放在持股列才是不合理的归属。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 聚焦：`pytest tests/test_club_stock_market.py tests/test_stock_market_application.py -q -p no:cacheprovider` → **140 passed**（模型层 90 = 原有 78 + 本轮新增 12 条分档/委托/融资/冲击/schema 契约，应用层 48）；`pytest tests -q -p no:cacheprovider -k "stock or world_club or wallet_transfer"` → **362 passed / 37 subtests**；前端八套件（`test_stock_market_frontend.py`、`test_stock_capital_frontend.py`、`test_stock_ticket_frontend.py`、`test_stock_scope_display_frontend.py`、`test_stock_market_daily_refresh_frontend.py`、`test_dark_mode_frontend.py`、`test_stock_board_layout_frontend.py`、`test_stock_order_frontend.py`）→ **83 passed**；`node --check src/web/app.js` 与九个 `i18n*.js` 全部通过。
- 模型层覆盖：本轮新增的 12 条契约把分档上限、大宗申请的扣款/交割/裁量与退款、限价抛售的预留与触价成交、冲击的量级与衰减、融资的报价不动 + 市值上抬 + T+1 锁定、`detect_splits` 对自有冲击的隔离、以及 schema 5 → 6 的读入归一化全部钉住。它们在交付前抓出了两个真实缺陷（见 `docs/development/ERROR_LOG.md` 的 E19-06 / E19-07），这正是模型层必须有测试的原因。
- 全量：`pytest tests -q -p no:cacheprovider` → **3478 passed / 13 failed / 239 subtests passed**，13 条失败与接手基线逐条一致（`test_account_store`、`test_championship_lifecycle`、`test_championship_odds`、`test_club_policies`、`test_i18n_catalog_contract`、`test_i18n_locale_packs`、`test_league_points_item`、`test_odds_profiles`、`test_owned_club_operations`×2、`test_pending_result_search`、`test_profit_analysis_colors`、`test_refresh_optimization`），无新增失败。
- 契约迁移：`test_the_board_row_and_the_holding_card_quote_the_capital` / `test_the_volume_column_keeps_only_turnover_and_capital` / `test_the_all_shortcut_stops_at_the_club_and_the_order_cap` / `test_the_capital_lines_keep_the_house_type` / `test_the_small_rows_keep_the_plain_candles` / `test_the_ticket_checks_the_club_book_before_the_order_cap` 六条随本轮设计变更重写（行内不再有股本句、校验顺序变成「可售 → 分档上限 → 天花板 → 资金」），不是放宽断言。
- 未实机核对：本轮没有启动 FM 进程与成品 EXE。饼图在真实行高下的观感、悬停提示的定位、委托条在窄窗口的折行、以及冲击系数 `TRADE_IMPACT_K` 0.75 的手感都需要用户实机确认；深色主题只做静态复核（新增色值都写在 `dark-theme.css` 的既有变量上）。
- 记录口径：本节的「打包」与「成品内容复核」为打包完成后回填，`dist\FMODD-V2.7.7beta-source-runtime.zip` 内的 `docs/development/DEV_LOG.md` 快照为回填前版本（缺这两条），其余内容与工作区一致；`FMODD-V2.7.7beta.exe` 的哈希不受文档编辑影响。

- 打包：C# 桌面宿主本轮无改动（`src/desktop/WebViewHost.cs` 未动），因此复用既有的 `src\desktop_host\FMODD.WebViewHost.exe`（136,192 字节，SHA-256 `2D9B301080460C7C81B8B28FEB92B2D51905FC2984CDE1EE51F8131C88A578BA`），跳过 `dotnet build`；`py -X utf8 scripts\build_single_exe.py` 产出 `dist\FMODD.exe`（60,219,043 字节，SHA-256 `7FF8F4AA1C01AE6DEE4AA96C3BF96B6ACFB9E08D73271510F2A6DA774D07E254`）并另存 `dist\FMODD-V2.7.7beta.exe`（哈希相同）；`py -X utf8 scripts\build_source_runtime_package.py` 产出 `dist\FMODD-V2.7.7beta-source-runtime`（584 文件 / 89.6 MiB，即上一轮 583 文件 + 本轮新增的 `tests/test_stock_order_frontend.py`），压缩为 `dist\FMODD-V2.7.7beta-source-runtime.zip`（65,253,418 字节，SHA-256 `183BE2567CAD906A624F0C1D617CFB890DCE49A066FAB4354F98591F476C83E5`）。打包前删除了 `.tmpcheck/`（第 17 轮的教训：临时目录会被 source-runtime 包照单收下），并核对包内没有 `.tmpcheck`、没有 `ODD.ico`、没有 `dist/`。
- 成品内容复核：用 `CArchiveReader` 解包 `dist\FMODD-V2.7.7beta.exe`（191 条目），确认包内 `web\app.js`（2,111,253 字节，含 `function stockPieHtml(` / `stockHoldingSlices` / `stock-row-turnover` / `function stockFinanceState(`）、`web\app.css`（751,661 字节，含 `.stock-row-pie` / `.stock-pie-tooltip` / `.stock-order-strip` / `.stock-finance-dialog` / `.stock-row-turnover` / `.stock-pie-legend b { font-variant-numeric:tabular-nums; }`，且旧的 `.stock-row-fundamentals` 已不在包内）、`desktop_host\FMODD.WebViewHost.exe`（136,192 字节，SHA-256 与工作区副本一致，确认宿主未被意外替换）；经 `ZlibArchiveReader` 读取包内 `PYZ.pyz`（296 模块）确认 `fm_odds_web`、`tools.club_stock_market`、`tools.club_economy` 随包发布；source-runtime 包内 `src/tools/club_stock_market.py` 是 `SCHEMA_VERSION = 6` 且含整手修正（`min(_order_lot(capital), int(round(capital * MAX_DIRECT_BUY_RATIO)))`）、大宗 10% 取整、融资 T+1 锁定与 `_normalize` 版本戳，五份文档（`DEV_LOG` / `ERROR_LOG` / `CHANGELOG` / `FEATURE_INDEX` / `RUNTIME_CONTRACTS`）都含第 19 轮内容。
- 备份：本轮基线落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.7beta-4-20261016`（`project` 568 文件 / 69,451,993 字节，为**本轮改动之前**的工程状态——第 18 轮交付的代码加上其后为打包回填的文档改动，核对点为 `SCHEMA_VERSION` 仍是 5、`tests/` 里没有 `test_stock_order_frontend.py`；`dist` 4057 文件 / 1,704,803,491 字节，为**重新打包前**的成品，即第 18 轮那版 `FMODD-V2.7.7beta.exe` 60,174,306 字节 / SHA-256 `5199D1F3…3A477` 与 `FMODD-V2.7.7beta-source-runtime.zip` 65,160,372 字节 / SHA-256 `39B6B6DD…419B`）。回滚到「第 19 轮之前」用 `FMODD-V2.7.7beta-4-20261016`，回滚到「第 18 轮之前」用 `FMODD-V2.7.7beta-3-20261016`。
- 交付附带的总结文件：`dist\FMODD-V2.7.7beta-第19轮改动总结.md`（约 6 千字，逐条列出本轮全部改动、格式/schema 变更与验证证据），放在成品目录而不进 source-runtime 包。

### 遗留

- `TRADE_IMPACT_K` 0.75 是按「2% 直购 ≈ 一天的摆动量级、10% 大宗 ≈ 几天的新闻」反推的；只有实机连续交易才能判断它是否过强或过弱，需要用户实机反馈后再调。
- 大宗交割固定「下一个游戏日」，没有按提交时刻（游戏内小时）细分；如果后续要给申请加排队序号或部分成交，`fill_pending_orders` 是唯一改动点。
- 委托队列上限 8 笔是拍板值，未做真实玩家的频率统计。
- 13 条预存在失败测试清单不变，未在本轮处理。


## 第 20 轮 · 直购上限、退市判定与复牌交易所（V2.7.7beta，2026-10-16）

### 需求（用户原话要点）

1. 普通交易单笔最大只有 100 万股，但占比总股本却不是 2%；占总股本 2% 且小于 100 万股的却不受影响——**超过 100 万股但未达 2% 也会被强制要求大宗交易**，要修复。
2. 融资后过一天会被当成**退市结算**，并且**大宗申请也没有弹出窗口反馈**，要重点排查。
3. **英格兰交易所关闭后重启**，游戏时间过了两天，股价、英格兰指数与 K 线都不变化；其他交易所正常，要查明原因。
4. 版本号暂时不变（仍 V2.7.7beta）；做好开发日志、错误日志迭代。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/tools/club_stock_market.py` | `SCHEMA_VERSION` 6 → **7**（新增 `state["missing"]` 与 `_normalize` 补空值）；删除 `MAX_ORDER_SHARE_CAP` 与 `_order_lot`，`max_direct_shares` 改为 `max(1, round(股本 × MAX_DIRECT_BUY_RATIO))`，`MAX_SHARES_PER_ORDER` 降级为「票据默认整手 + 空股本兜底」；新增 `listing_day`（未来的上市日不是上市日）、`watched_club_keys` / `_remember_absence` / `_forget_absence`；`_settle_missing_holdings` 改为覆盖「持仓 ∪ 待成交委托」并返回 `(settlements, credited, unconfirmed, forgotten)`；`registry_sync` 新增 `confirm_absent` 参数、把未来的 `listed_ordinal` 写回当日（`listing_repaired`）并回报 `missing_forgotten`；`fill_pending_orders` 只在缺席被确认后撤单、未确认时记录当日并回报 `unconfirmed`；`_sync_share_book` 以存量记录为底（离场俱乐部保留股本记录）；`_close_order` 的撤单公告不再被 `refund` 为 0 吞掉 |
| `src/fm_odds_web.py` | `_stock_market_tick` 传入 `confirm_absent=not world_club_scanning`，回报 `order_refunds` / `order_unconfirmed`，并把 `unconfirmed` / `order_unconfirmed` / `missing_forgotten` / `listing_repaired` 加进落盘条件（否则「两次可见」的第一次记不入库，判定永远不成立）；`public_stock_market` 的 `view["tick"]` 新增 `unconfirmed` |
| `src/web/app.js` | 新增 `stockOrdersPanelHtml`（持仓面板与成交记录之间的委托面板，复用 `stockOrderRowHtml`）与 `#stock-content` 上一次性的 `data-stock-order-cancel` 事件委托（模板重渲染后仍可撤单） |
| `tests/test_club_stock_market.py` | 重写 3 条随契约变化的既有测试（2% 上限、schema 7 与 `missing`、退市两次可见），新增 3 条契约测试 |
| `tests/test_stock_market_application.py` | 重写 `test_delisting_settles_the_holding_into_the_bank`（两次可见），新增 3 条回归测试 |
| `docs/RUNTIME_CONTRACTS.md`、`docs/FEATURE_INDEX.md`、`CHANGELOG.md` | 同步 2% 上限公式、`missing` 字段与 schema 7、退市两次可见、委托面板与复牌解冻 |

### 关键决策

- **2% 是唯一的点击上限**：整手写进 `min(整手, 2%)` 会同时制造两个方向的错误——大俱乐部被压到 100 万股（用户看到曼城 13.9 亿股本的「单笔上限 100.0万」，2% 应是 2780 万股），而比 100 万股小的点击又被强制转大宗。整手只保留为「票据默认值」，不再参与上限；`MAX_SHARES_PER_ORDER` 仍用于空/非法股本的兜底与前端默认量，避免一次点击变成 0 股。
- **退市判定改为「两次可见」而不是「相信一次目录」**：根因是世界俱乐部扫描是异步增量的，`_stock_market_directory` 拿到的是「已经读到的那些俱乐部」，第一次读取时大量俱乐部还没进目录，于是任何持仓都可能在下一次 tick 被判退市。改法是让缺勤需要证据：第一天只记 `state["missing"]`（tick 汇报 `unconfirmed`），只有「缺席首日早于今天」才结算；扫描进行中（`world_club_scanning`）整个 tick 以 `confirm_absent=False` 运行。冻结持仓、范围外俱乐部、快照未就绪的目录都继续跳过。
- **落盘条件必须跟着判定条件一起改**：`state["missing"]` 是判定的输入，如果第一次记不入库，下次启动就从零开始等——真退市的持仓永远结算不掉（症状只是「再也不会出现退市」，比误退市更难发现）。因此 `unconfirmed` / `order_unconfirmed` / `missing_forgotten` / `listing_repaired` 都进入 `_stock_market_tick` 的存盘条件。
- **委托队列与持仓共用同一套缺席证据**：`watched_club_keys` = 持仓 ∪ 待成交委托的俱乐部，`_settle_missing_holdings` 因此会给「只有委托、没有持仓」的俱乐部也记一笔缺席；否则这类委托永远等不到确认、钱一直卡在托管里（本轮自查时发现的缺口，已补）。确认后撤单写 `order_cancel` 公告（`refund` 为 0 的限价撤单也写），并且股市侧栏多一个常驻委托面板，让「申请已提交 / 已成交 / 已撤回」都能被看见——这就是用户说的「大宗申请没有弹窗反馈」的正面修复。
- **复牌冻结的根因是「未来的上市日」**：关闭交易所后重开、而游戏时钟回拨过时，`entry["listed_ordinal"]` 会落在存档走不到的将来；`listing_day` 过去把它当上市日，于是 `first = max(first, listed) > ordinal`，K 线窗口为空、`fresh` 为真把所有涨跌幅抹成 0，指数与蜡烛一起静止。现在 `listing_day` 只认「不晚于今天」，`registry_sync` 把越界的 `listed_ordinal` 写回当日并回报 `listing_repaired`，图表立即恢复。
- **离场俱乐部保留股本记录**：`_sync_share_book` 改为以存量记录为底。目录是增量的，俱乐部「暂时不在目录里」与「真的离开存档」在第一次读取时无法区分；删记录会让它回来时按新价格重新上市、抹掉已经发生的扩股与融资。此行为变化同步改写了 `test_registry_sync_freezes_one_share_record_per_listed_club` 的断言。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 隔离测试（`py -X utf8 -m pytest ... -q -p no:cacheprovider`）：`tests/test_club_stock_market.py` 95 passed（92 → 新增 3 条）；`tests/test_stock_market_application.py` 51 passed（48 → 新增 3 条）；`tests/test_stock_order_frontend.py` 12 passed。
- 相关面全跑：`pytest tests -k "stock or world_club or wallet_transfer or exchange"` → 369 passed / 37 subtests passed。
- 前端：`node --check src\web\app.js` 通过；前端与 i18n 套件 `pytest tests -k "frontend or i18n or money or unit"` → 698 passed / 6 failed，6 条与接手基线逐条一致（`championship_odds`、`i18n_catalog_contract`、`i18n_locale_packs`、`league_points_item`、`pending_result_search`、`profit_analysis_colors`）。
- 全量：`pytest tests` → 3484 passed / 13 failed / 239 subtests passed；13 条与接手基线逐条一致，未在本轮处理。
- 新增契约测试：`test_max_order_is_two_percent_of_the_capital_and_never_a_round_lot`、`test_a_directory_that_is_still_being_read_never_delists_a_lot`、`test_an_application_waits_out_the_reading_and_is_withdrawn_when_proven_gone`、`test_a_listing_day_from_the_future_never_freezes_an_exchange`、`test_a_financed_lot_survives_a_reading_that_has_not_reached_the_club`、`test_an_exchange_listed_in_the_future_trades_again_the_next_game_day`、`test_a_click_past_a_million_shares_is_still_a_plain_buy`。
- 未实机核对：本轮没有启动 FM 进程与成品 EXE（规则禁止）。2% 上限在真实存档下的手感、委托面板在窄窗口的观感、以及「两次可见」在一天多开存档的节奏都需要用户实机确认。

- 记录口径：本节的「打包」「成品内容复核」「备份」为打包完成后回填，`dist\FMODD-V2.7.7beta-source-runtime.zip` 内的 `docs/development/DEV_LOG.md` 快照为回填前版本（缺这三条），其余内容与工作区一致；`FMODD-V2.7.7beta.exe` 的哈希不受文档编辑影响。

- 打包：C# 桌面宿主本轮无改动（`src/desktop/WebViewHost.cs` 未动），因此复用既有的 `src\desktop_host\FMODD.WebViewHost.exe`（136,192 字节，SHA-256 `2D9B301080460C7C81B8B28FEB92B2D51905FC2984CDE1EE51F8131C88A578BA`），跳过 `dotnet build`；`py -X utf8 scripts\build_single_exe.py` 产出 `dist\FMODD.exe`（60,222,139 字节，SHA-256 `B88DA55F253093A7171CC8078C9EBD0240DF1AFEA1999E07EA4D59673E63D55A`）并另存 `dist\FMODD-V2.7.7beta.exe`（哈希相同）；`py -X utf8 scripts\build_source_runtime_package.py` 产出 `dist\FMODD-V2.7.7beta-source-runtime`（584 文件 / 89.6 MiB，与上一轮文件数相同），压缩为 `dist\FMODD-V2.7.7beta-source-runtime.zip`（64,805,114 字节，SHA-256 `AC5BF8B5E71CC264195AC72A16A35AF1E82F456D3E8B5ED45798B72467F73569`，584 条目）。本轮 `Compress-Archive` 被当前命令行策略拒绝，改用 Python `zipfile`（ZIP_DEFLATED level 9）生成压缩包；打包前删除了上一轮探针留下的临时文件（`tests/__pycache__` 里的 `test_zz_r20_*.pyc`，源码本体早已删除），并核对包内没有 `.tmpcheck`、没有 `ODD.ico`、没有 `dist/`。
- 成品内容复核：用 `CArchiveReader` 解包 `dist\FMODD-V2.7.7beta.exe`（191 条目），确认包内 `web\app.js`（2,112,687 字节，含 `function stockOrdersPanelHtml(` / `data-stock-order-cancel` / `stockDirectCap` / `stockFinanceState` / `stockOrderRowHtml`）、`web\app.css`（751,661 字节，含 `.stock-order-row` 与 `.stock-panel`）、`desktop_host\FMODD.WebViewHost.exe`（136,192 字节，SHA-256 与工作区副本一致，确认宿主未被意外替换）；经 `ZlibArchiveReader` 读取包内 `PYZ.pyz`（296 模块）确认 `fm_odds_web`、`tools.club_stock_market`、`tools.club_economy` 随包发布，并对前两个模块的全部代码对象做递归扫描：`fm_odds_web` 的 `registry_sync` 调用点带 `confirm_absent` 关键字实参（关键字名元组 `('game_date', 'ordinal', 'season', 'confirm_absent')`），`listing_repaired` / `order_unconfirmed` / `missing_forgotten` 三个读数常量都在包里；`tools.club_stock_market` 里 `listing_day` / `watched_club_keys` / `_settle_missing_holdings` / `max_direct_shares` / `held_back` 都在，而 `MAX_ORDER_SHARE_CAP` **不在**（确认旧上限常量已随包消失）。source-runtime 包内 `src/tools/club_stock_market.py` 是 `SCHEMA_VERSION = 7`、含 `missing` / `listing_day` / `watched_club_keys` 且已删 `MAX_ORDER_SHARE_CAP`，`src/web/app.js` 含 `stockOrdersPanelHtml` 与 `data-stock-order-cancel`，五份文档里 `DEV_LOG` 含「## 第 20 轮」、`ERROR_LOG` 含「### E20-01」、`CHANGELOG` 含第 20 轮小节。
- 备份：本轮落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.7beta-5-20261016`（`project` 592 文件 / 70,912,734 字节，是**本轮代码改完之后、打包之前**的快照——`SCHEMA_VERSION` 已是 7、`MAX_ORDER_SHARE_CAP` 已删、`tests/` 里已有本轮新增的 6 条契约测试、`CHANGELOG.md` 与两份 `docs/` 契约文档含第 20 轮内容，但 `DEV_LOG` / `ERROR_LOG` 的两份日志是打包后回填的、不在该快照里；`dist` 4059 文件 / 1,705,210,343 字节，是**重新打包之前**的成品，即第 19 轮那版 `FMODD-V2.7.7beta.exe` 60,219,043 字节 / SHA-256 `7FF8F4AA1C01AE6DEE4AA96C3BF96B6ACFB9E08D73271510F2A6DA774D07E254` 与 `FMODD-V2.7.7beta-source-runtime.zip` 65,253,418 字节 / SHA-256 `183BE2567CAD906A624F0C1D617CFB890DCE49A066FAB4354F98591F476C83E5`）。本轮**没有另做「改动前」基线**：第 20 轮的起点就是第 19 轮交付的那份代码，回滚到第 19 轮用该目录 `dist\` 里的 exe 与 source-runtime.zip（指引写在该目录的 `README-备份说明.txt`），回滚到第 18 轮用 `FMODD-V2.7.7beta-4-20261016`。这是与第 13 ~ 19 轮不同的口径，记在这里以免下一次误以为 `-5-` 是「改动前」快照。
- 交付附带的总结文件：`dist\FMODD-V2.7.7beta-第20轮改动总结.md`（15,580 字节，逐条列出本轮三个用户报告的缺陷与一个自查缺陷、schema 6 → 7 的变更、测试证据与四个产物的哈希），放在成品目录而不进 source-runtime 包。

### 遗留

- 「两次可见」把真退市的确认推迟了一个游戏日；如果后续要更快，只能让目录在收盘审核时被读全（扫描完成回调），不要退回到「读一次就判」。
- 委托面板与公告条都只列出最近 24 条（`market_view` 的既有口径）；如果玩家堆满 8 笔委托并连续撤单，历史会被截断。
- 13 条预存在失败测试清单不变，未在本轮处理。


## 第 21 轮 · 每日直购预算、成交回执与融资意愿（V2.7.8beta，2026-10-16）

### 需求（用户原话要点）

1. 普通交易（市价交易）买入每日单俱乐部最高只能买入该俱乐部股本的 2%，达到 2% 后必须申请大宗交易才能继续购入。
2. 股价影响希望在**市价交易与大宗交易的股数变化时就能显示**，而不是得切换市价/大宗才显示。
3. 大宗交易完成后**弹窗**提示「大宗交易已完成」，附带股本百分比变化、股价变化等信息。
4. 股权饼图**去除中间的百分比**，图例以玩家集团名称 + 持股、俱乐部名称 + 持股显示，百分比保留。
5. 新增**融资意愿**：股价过高或过低、俱乐部持续亏损都会增加融资意愿；玩家发起融资时按意愿判定，意愿低时可能不通过。
6. 版本号迭代到 2.7.8Beta；做好开发日志、错误日志迭代；动手前先备份工程与成品。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/tools/club_stock_market.py` | `SCHEMA_VERSION` 7 → **8**（新增 `state.daily` / `state.receipts`，`_normalize` 补空值）；新增每俱乐部每日直购账 `daily_direct_used` / `daily_direct_room` / `record_direct_buy` / `forget_direct_buy`，`buy_plan` 的 direct 分支改用「2% − 当日已用」校验，`commit_buy` / `revert_buy` 只在 direct 记账；新增 `receipt`（上限 `RECEIPT_LIMIT` 40 条）与 `fill_pending_orders` 的两处写入（大宗 `block_fill`、限价 `limit_fill`）；新增 `form_slump` / `finance_appetite`（确定性每日一次抽签，`accept` 为假时 `finance_plan` 抛 `ValueError`）；`trading_limits` 补 `daily_direct` / `appetite_*`，`trading_quote` 与 `market_view` 的行补 `direct_used` / `direct_room` / `appetite`，`market_view` 返回 `receipts` |
| `src/fm_odds_web.py` | `_stock_market_appraise` 行里透传 `balance`（融资意愿的亏损判定）；`buy_stock` 用当日已用量构造 direct 计划；`finance_stock` 把 `trading_quote` 的 `appetite` 传给 `finance_plan`；`PRODUCT_VERSION` → `V2.7.8beta` |
| `src/web/app.js` | 饼图 `stockPieLabel`（按集团/俱乐部命名）与 `stockPieHtml`（删环内百分比节点，图例加 `title` 与 `data-stock-pie-club`，悬停提示改名）；新增 `stockDirectRoom`，`stockTicketQuote` 产出 `directRoom` / `impactKind` 并无条件计算 `impact`；`renderStockTicket` 常显 `.stock-quote-impact`、`updateStockTicketQuote` 不再 `hidden=true`；回执 `stockReceiptDialog` / `stockReceiptHtml` / `openStockReceipt` / `stockReceiptFeed`（首读只记位置，会话内新回执才弹）；融资意愿 `stockFinanceReasonText` / `stockFinanceAppetiteHtml` / `stockFinanceQuote` / `updateStockFinanceQuote` |
| `src/web/i18n.stocks.js` + 8 个语言包 | 22 个新键：`stock.pie.holder`、`stock.trade.daily`、`stock.limit.daily`、`stock.finance.appetite` / `_note` / `reason.gap|debt|slump|none`、`stock.receipt.kicker|block_title|limit_title|qty|price|cost|capital|stake|quote|move|dropped|close|note` |
| `src/web/app.css` + `dark-theme.css` | `.stock-finance-appetite*` 与 `.stock-receipt-dialog` / `-body` / `-facts` / `-note`，并补深色主题覆盖 |
| 版本号 | `fm_odds_web.py`、`fmodd_desktop.py`、`WebViewHost.cs`、`WebViewHost.csproj`（2.7.8-beta / 2.7.8beta / 2.7.8.0）、`docs/development/DEVELOPMENT.md`、三份 README（含 badge）、`docs/guides/PRODUCT_GUIDE.md` |
| `tests/` | `test_club_stock_market.py`（schema 8、每日预算跨日与回退、两类回执、融资意愿与拒绝）、`test_stock_market_application.py`（点击花掉当日额度、回执到达页面、拒绝融资不发行）、`test_stock_order_frontend.py`（每日额度、结算回执、融资意愿）、`test_stock_capital_frontend.py`（`stockDirectCap` → `stockDirectRoom`） |

### 关键决策

- **2% 是「每日预算」而不是「每次点击上限」**：把 2% 留在「单笔」语义上，玩家只要把一笔拆成多笔就能买到远超 2% 的股本，规则实际不成立；改成按游戏日累计（`state.daily` 记 `ordinal` + `qty`，跨日靠序数不等自然归零）之后，「一次 2%」与「十次 0.2%」给出同一个上限，而且不需要任何清理任务。大宗与限价委托不占这笔预算，因为它们的约束本来就是另一套（10% / 25% / 委托队列）。
- **影响预估不该藏在模式切换里**：玩家问的「买多少会抬多少」与「走直购还是大宗」是同一个问题的两个部分，所以 `stockTicketQuote` 无条件算 `impact`，票据常显这一行；越过当日额度时只加一个「· 大宗买入」后缀，而不是等玩家切模式才显示。
- **回执是「同一会话里的新消息」，不是队列快照**：`state.receipts` 随存档长期存在，如果前端每次读取都弹第一条，读档、切换交易所、每个交易日刷新都会重复弹同一条历史回执。因此 `stockReceiptFeed` 第一次读取只记下 `receiptSeen`，只有 ID 变化时才弹——「玩家看过什么」属于前端会话状态，模型层不需要知道。
- **融资意愿做成「概率 + 每日一次抽签」而不是硬门槛**：用户的诉求是「意愿低时可能不通过」，而不是「低于某值就永远拒绝」。所以 `chance` 由偏离 / 亏损 / 低迷三档加成决定（0.45 基础值，夹在 0.20–0.97 之间），`accept` 由 `_hash01(club_id ^ 0x2F17, 游戏日)` 抽签；同一家俱乐部同一天反复提交得到同一答复（刷不出额外机会），换一天才是新的一次。判定只在模型层，前端只显示意愿与理由。
- **饼图去掉数字、名字挪到图例**：42px 的环里写百分比在任何缩放下都读不清，而「谁的份额」比「多少百分比」更是理解成本所在；因此环内清空、图例按持有人命名（集团名 / 俱乐部名缺省时回退通用键），百分比保留在图例右侧与悬停提示里。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 隔离测试（`py -X utf8 -m pytest ... -q -p no:cacheprovider`）：`tests/test_club_stock_market.py` 101 passed（95 → 新增 6 条：每日预算跨日与回退、大宗回执、限价回执、融资意愿、每日一次抽签、意愿不足时拒绝）；`tests/test_stock_market_application.py` 54 passed（51 → 新增 3 条：点击花掉当日额度、回执到达页面、拒绝融资不发行）；`tests/test_stock_order_frontend.py` 16 passed（12 → 新增 3 条并改写受影响断言）；`tests/test_stock_capital_frontend.py` 随 `stockDirectRoom` 更新。
- 前端：`node --check src\web\app.js` 通过。
- 全量：`pytest tests` → 3496 passed / 13 failed / 239 subtests passed；13 条与接手基线逐条一致，未在本轮处理。
- 未实机核对：本轮没有启动 FM 进程与成品 EXE（规则禁止）。每日预算在真实存档的手感（一次买满 2% 与分次买入）、回执弹窗在连打多笔成交后的观感、融资意愿的数值松紧都需要用户实机确认。

### 遗留

- 每日预算只记直购，大宗成交不占；如果后续希望「大宗也消耗当日额度」，要重新定义预算语义，而不是在 `daily_direct_room` 上叠加。
- 回执队列上限 40 条，且同一会话内只弹最新一条；多笔委托同日交割时其余回执留在队列里，不会逐条弹出。
- 融资意愿是每俱乐部每日一次抽签、与申请笔数无关；如果后续想让「反复提交」有成本，需要在服务端另记尝试次数。
- 13 条预存在失败测试清单不变，未在本轮处理。

### 交付与打包

- 打包：`dotnet build src\desktop\WebViewHost.csproj -c Release` 通过；本轮 C# 宿主有改动（`WebViewHost.cs` 窗口标题 → `V2.7.8beta`），产物回拷 `src\desktop_host\FMODD.WebViewHost.exe`（136,192 字节，SHA-256 `A7FCB0D296535320EDDB45BF52D2BFBD4F08E2767A6F56DF0FCB1E45D4679833`；上一轮为 `2D9B3010…`，标题改动因此可验证）。
- 成品：`py -X utf8 scripts\build_single_exe.py` → `dist\FMODD.exe`，另存 `dist\FMODD-V2.7.8beta.exe`（60,237,966 字节，SHA-256 `B1976594315C3D41B2C3F880BF809ACAF60253D67BE42686E36D8467A1C686D1`）；第 20 轮的 `dist\FMODD-V2.7.7beta.exe` 保留未覆盖。
- 成品内容复核：用 `CArchiveReader` 解包 `dist\FMODD-V2.7.8beta.exe`（191 条目），确认包内 `web\app.js`（2,121,346 字节，含 `function stockReceiptHtml(` / `function stockDirectRoom(` / `stock.pie.holder` / `function stockFinanceAppetiteHtml(`）、`web\app.css`（753,151 字节，含 `.stock-receipt-dialog` / `.stock-finance-appetite`）、`web\i18n.stocks.js`（35,291 字节，含 `stock.receipt.block_title` / `stock.trade.daily`）、`web\dark-theme.css`（92,723 字节，含 `.stock-receipt`）与 `desktop_host\FMODD.WebViewHost.exe`（哈希与回拷的宿主逐字节一致）；PYZ 内 `tools.club_stock_market` 含 `finance_appetite` / `daily_direct_room` / `record_direct_buy` / `receipt`，`fm_odds_web` 含 `V2.7.8beta`。
- source-runtime：`py -X utf8 scripts\build_source_runtime_package.py` → `dist\FMODD-V2.7.8beta-source-runtime`（584 文件 / 89.7 MiB），用 Python `zipfile`（`ZIP_DEFLATED` level 9）压成 `dist\FMODD-V2.7.8beta-source-runtime.zip`（64,865,061 字节，SHA-256 `9BF6037ED977EE161288A5FDD150786CA939645378383A89F073018F9210BF18`）。
- 备份：本轮落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.7beta-6-20261016`（`project` 546 文件 / 69,541,242 字节，`dist` 4,059 文件 / 1,640,702,624 字节，`README-备份说明.txt` 3,350 字节），是**本轮动手之前**的基线，含第 20 轮的全部成品。
- 交付附带的总结文件：`dist\FMODD-V2.7.8beta-第21轮改动总结.md`（8,754 字节，SHA-256 `83298D61499AB057633CCC75897E942C25CE0168D235D555ABD5B481AA03ACA8`），放在成品目录而不进 source-runtime 包。
- 记录口径：`dist\FMODD-V2.7.8beta-source-runtime.zip` 内的 `docs/development/DEV_LOG.md` 快照为回填本节之前的版本（缺以上六条），其余内容与工作区一致。

## 第 22 轮 · 联赛目录修复、收购交接与融资意愿校准（V2.7.8beta，2026-10-16）

### 需求（用户原话要点）

1. 有些国家的联赛在筛选里找不到（丹麦超级联赛、荷兰超级联赛等，很多都没有），仔细检查并修复。
2. 启用了 36 个国家，但左侧国家/地区栏只有 29 个，排查原因。
3. 已收购的俱乐部股权没有交接给玩家集团，而且玩家依旧可以买入，这是问题。
4. 绝大部分俱乐部融资意愿都在 90% 以上，明显不对，请优化。
5. 动手前先备份工程与成品；版本号暂不变；做好开发日志、错误日志迭代。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/tools/world_clubs.py` | `merge_native_world_clubs` 只在 native 有 `balance` 时才覆盖盘口快照的结余；新增 `_competition_id_of` / `_competition_names_by_id` / `_apply_canonical_competition`（同一赛事 id 取最长名做正名、旧名进 `competitions`）与 `attach_result_competitions`（把赛果历史的名字并入每支俱乐部的 `competitions`） |
| `src/tools/club_stock_market.py` | 新增 `scope_league_index`（pairs + aliases 别名表）/ `canonicalize_scope`（别名与 `未分类` 单归属折叠）/ `reconcile_scope`（空目录不裁决）/ `apply_scope_repair`（剪枝 + `scope_prune` 公告）；`in_scope` / `scope_rows` 改用全部赛事名匹配；`save_competition_index` 同时读 `competition_formats` 与 `competitions`；融资意愿改 `market_cap` 口径并调参（BASE 0.25 / GAP 0.35 / DEBT 0.35 / SLUMP 0.20 / CAP 0.92 / FLOOR 0.05 / GAP_SCALE 0.40）；新增 `TAKEOVER_SOURCE` / `takeover_ids` / `takeover_lot` / `take_over_club` / `release_takeover` / `assert_tradable` / `sync_takeovers`，`_decorate` 加 `owned` 且 owned 时 `sellable=0`，`trading_quote` 加 `takeover`，`holding_lots` 每条加 `owned` / `source`，`_settle_holdings` 跳过 takeover 持仓 |
| `src/fm_odds_web.py` | 新增 `_stock_market_scope_index` / `_stock_market_scope_plan`（读路径统一折名）；`_stock_market_directory` / `apply_stock_market_scope` / `stock_market_scope_leagues` / `_stock_market_tick` 改用 plan；tick 里 `reconcile_scope` + `apply_scope_repair`（`result["scope_pruned"]` / `scope_prune_notice`）与 `sync_takeovers`（`result["takeovers"]`）；新增 `_stock_market_owned_clubs` / `_stock_market_sync_club_ownership` / `_stock_market_release_club`，收购与出售俱乐部时同步登记册；`_settle_stock_order_cash` 把交接撤销的委托退款入账；`_scope_filter_view` 返回 `unresolved` |
| `src/web/app.js` | `stockRowHtml` 对 `owned` 行显示「已收购」徽章；`stockTicketFactsHtml` / `renderStockTicket` 对 owned 显示说明条并隐藏买卖表单；`STOCK_NOTICE_KINDS` 加 `scope_prune`；筛选面板加 `stock.filter.unresolved` 提示条 |
| `src/web/i18n.stocks.js` + 8 个语言包 | 4 个新键：`stock.owned.badge` / `stock.owned.note` / `stock.filter.unresolved` / `stock.notice.scope_prune`，十一种界面语言补齐 |
| `src/web/app.css` | `.stock-owned-badge` / `.stock-ticket-form[data-stock-owned="1"]` / `.stock-owned-note` / `.stock-filter-unresolved` |
| `tests/` | `test_club_stock_market.py` +8（别名折叠、`未分类` 不硬折、reconcile 不裁决空目录、剪枝公告、`save_competition_index` 双扫描、收购交接与撤单退款、owned 三路拒单、双向登记册与释放自选）；`test_stock_market_application.py` +6（剪枝与公告、扫描期间不剪、旧名折叠、筛选 `unresolved`、收购交接 + 买入报错、出售收回） |

### 关键决策

- **两套联赛名字要折，不要删**：盘口快照与俱乐部扫描对同一联赛各印一套名字，直接在目录里删掉旧名会让按旧名存下的范围彻底失效。做法是先建别名表（`pairs` + `aliases`），存下的范围在读取时折叠到当日正名；只有目录完全解析不到、而且目录确实非空（`confirmed`）时才剪枝，并把剪掉的联赛写进 `scope_prune` 公告——玩家能看到「为什么少了」而不是悄悄消失。世界扫描进行中（`world_club_scanning`）目录本身不完整，`reconcile_scope` 的 `confirmed=False` 语义保证不误剪。
- **`未分类` 只在单归属时折叠**：早期扫描把找不到联赛的俱乐部堆在共享桶里，若该联赛名在目录里恰好只属于一个国家，就折回那个国家；两个国家都有同名联赛时不猜，保留原条目等目录给出答案。
- **收购是「整本登记册交接」，不是「顺手送一笔持仓」**：真正的收购意味着俱乐部不再持有自己的股份。用 `source="takeover"` 的持仓表达这个状态，三路交易（买 / 卖 / 融资）都由 `assert_tradable` 明确拒绝，看板与交易窗换文案；登记册的同步做成双向（`sync_takeovers`），因为收购可能发生在交易所关闭时、市场数据可能是旧格式、卖出可能发生在市场关闭时——只靠收购当次的事件写一次会在这些路径下漂移。撤销该俱乐部待成交委托并把托管金退回，是因为登记册已经不再属于市场，任何未交割的委托都不该继续。
- **`owned` 持仓不参与退市结算**：`_settle_holdings` 跳过 takeover 持仓，因为「集团自己的俱乐部」不存在从市场退市的概念。
- **融资意愿用两组数比：整家对整家**：偏离的本意是「这报价相对这家俱乐部值多少钱」，所以必须拿 `market_cap`（股价 × 股本）与 `intrinsic`（整家估值）比。拿每股价格对整家估值，任何价格都会显得「便宜 100 倍」，这才让全部俱乐部撞上上限。参数重新定为 BASE 0.25 / GAP 0.35 / DEBT 0.35 / SLUMP 0.20 / CAP 0.92 / FLOOR 0.05：健康的俱乐部意愿不高（25% 上下），要说服董事会得靠亏损、低迷或明显的估值偏离。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 隔离测试：`tests/test_club_stock_market.py` **110 passed**、`tests/test_stock_market_application.py` **60 passed**（两文件合计 169 passed）；`pytest tests -k "stock or world_club"` 368 passed 与本轮改动前基数一致。
- 真实存档复现（只读，未启动 FM）：`merge_native_world_clubs` + `scope_league_index` 重建目录 36,952 家；`reconcile_scope` 精确剪掉 7 条 `大洋职业联赛` 条目后覆盖国家数与筛选界面一致（29）；`save_competition_index` 复测丹麦（丹超 / 丹甲 / 丹乙 / 丹丙）与荷兰（荷甲 / 荷乙）均在存档内；融资意愿全量 1627 家 min 0.250 / median 0.260 / max 0.289、0 家 > 0.5。
- 前端：`node --check src\web\app.js` 与各语言包通过。
- 未实机核对：没有启动 FM 或成品 EXE（规则禁止）。收购后交易窗、看板徽章的实机观感，筛选剪枝公告是否在玩家存档里按预期出现，需要用户实机确认。

### 遗留

- 旧存档里被剪掉的联赛（如 `大洋职业联赛`）如果目录后续补齐该赛事，重新勾选即可从初始状态上市；剪枝本身不迁移持仓（那些条目本来就没有俱乐部挂靠）。
- 融资意愿的 `slump` 一档依赖 `fundamentals` 的近期战绩读数；没有战绩数据的俱乐部只走 BASE + gap。
- 13 条预存在失败测试清单不变，未在本轮处理。

### 交付与打包

- 打包：本轮未改 `WebViewHost.cs`，无需重建宿主；`py -X utf8 scripts\build_single_exe.py` 共跑两遍。第一遍成品（60,256,080 字节 / SHA-256 `EAF0903676AB7A6097B803192EFE31F5C4F2CDFC49CC4409CC5AD36C56901B1D`）在复核时暴露了一处**前端回归**：`stockRowHtml` 给交易卡挂 `is-owned` 类时改写了 `renderStockTicket` 依赖的 `'class="stock-ticket-card stock-ticket-form"'` 静态锚点；改成独立的 `data-stock-owned="1"` 属性契约（并同步 `tests/test_stock_ticket_frontend.py` 锚点与 owned 断言）后重建。交付用第二遍的 `dist\FMODD.exe` → **60,256,023 字节**，SHA-256 `468D9F0CF8E524FD594B8BE230C5758A4EE4541A381492BD6378496F8A529550`，内部版本 `V2.7.8beta`，另存 `dist\FMODD-V2.7.8beta-第22轮.exe`（同哈希，逐字节比对通过）。第一遍的旧构建改名留在 `dist\FMODD-V2.7.8beta-第22轮-旧构建.exe`（复核时该实例仍在运行，Windows 不允许删除运行中的镜像，关闭后可删）；第 21 轮的 `dist\FMODD-V2.7.8beta.exe` 保留未覆盖。
- 成品内容复核（对重建后的成品再做一次完整复验）：解包 `dist\FMODD-V2.7.8beta-第22轮.exe`（CArchive 191 条目），确认包内 `web\app.js`（2,122,410 字节，含 `data-stock-owned` / `stock-owned-badge` / `stock.filter.unresolved` / `scope_prune`）、`web\app.css`（754,296 字节，含 `.stock-owned-badge` / `.stock-owned-note` / `.stock-filter-unresolved`）、`web\i18n.stocks.js`（36,695 字节，含 `stock.owned.badge` / `stock.owned.note` / `stock.filter.unresolved` / `stock.notice.scope_prune`），三份前端资源与 `src\web\` 源文件逐字节一致；PYZ 内 `tools.club_stock_market` 含 `reconcile_scope` / `canonicalize_scope` / `scope_league_index` / `apply_scope_repair` / `take_over_club` / `release_takeover` / `sync_takeovers` / `assert_tradable` / `takeover_lot` / `takeover_ids` / `row_competition_names` 与 `FINANCE_APPETITE_BASE` / `FINANCE_APPETITE_GAP` / `FINANCE_APPETITE_DEBT` / `FINANCE_APPETITE_SLUMP` / `FINANCE_APPETITE_CAP` / `FINANCE_ACCEPT_FLOOR` 常量名，`fm_odds_web` 含 `_stock_market_scope_plan` / `_stock_market_scope_index` / `_stock_market_sync_club_ownership` / `_stock_market_release_club` / `_stock_market_owned_clubs` / `takeover_refund` / `scope_pruned` 与版本串 `V2.7.8beta`，`tools.world_clubs` 含 `attach_result_competitions` / `_apply_canonical_competition` / `_competition_names_by_id`。
- source-runtime：`py -X utf8 scripts\build_source_runtime_package.py` → `dist\FMODD-V2.7.8beta-source-runtime`（584 文件 / 94,156,112 字节），用 Python `zipfile`（`ZIP_DEFLATED` level 9）压成 `dist\FMODD-V2.7.8beta-source-runtime.zip`（64,887,578 字节 / 584 条目，SHA-256 `BA54ED50C32F4F5B00B176D4886A3A603E4649261002B58245DC6027D73ABB16`；前端回归修复后与 exe 一起重建，包内 `src\web\app.js` 等与仓库源文件逐字节一致）；第 21 轮的同名目录与 zip 改名保留为 `-第21轮` 后缀。
- 备份：本轮落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.8beta-1-20261016`（`project` 549 文件 / 68,407,923 字节，`dist` 4,646 文件 / 1,859,907,784 字节，`README-备份说明.txt` 含关键产物 SHA-256），是**本轮动手之前**的基线，含第 21 轮成品 `FMODD-V2.7.8beta.exe`。
- 交付附带的总结文件：`dist\FMODD-V2.7.8beta-第22轮改动总结.md`（放在成品目录而不进 source-runtime 包）。
- 记录口径：`dist\FMODD-V2.7.8beta-source-runtime.zip` 与其中的 `docs/development/DEV_LOG.md` 快照在回填本节数据之前打包，所以包内快照缺「交付与打包」六条；成品与 zip 的哈希 / 字节数以本节为准，`dist\FMODD-V2.7.8beta-第22轮改动总结.md` 同步已刷新。

## 第 23 轮 · 收购门槛、集团俱乐部交易与全球范围（V2.7.9beta，2026-10-16）

### 需求（用户原话要点）

1. 市值达到 100 亿以上的俱乐部，必须持股达到 49% 才可以进行收购；不管市值多少，收购有收购意愿，当俱乐部股价连续增长、且**收购价**比估值高很多时，收购意愿极低；当收购价比估值低很多时，收购意愿会很高；并且当在该俱乐部有持仓时，收购实付价格应当等于收购价减去持仓资本。
2. 集团收购之后，依旧可以进行股权售卖以及玩家进行融资；只有自己的集团下的俱乐部融资才会将以 10% 的百分比为俱乐部当前结余注入资金。
3. 勾选交易所界面添加**全球**选项，与其他勾选项一致，点击一次仅开启联赛，再点击一次，开启全部俱乐部；盘口自定义选项也如此。
4. 设置中的“连接存档后自动读取俱乐部信息”功能深化：开启后，连接存档后自动刷新世界俱乐部模块中的俱乐部，以便股市系统读取俱乐部信息。
5. 版本号迭代到 2.7.9Beta；动手前先备份工程与成品；做好开发日志、错误日志迭代。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/tools/club_stock_market.py` | 新增收购门槛与意愿：`TAKEOVER_STAKE_GATE_VALUE` 100 亿 / `TAKEOVER_STAKE_GATE_RATIO` 49% / `TAKEOVER_APPETITE_BASE` 0.60 / `TAKEOVER_APPETITE_PREMIUM` 0.55 / `TAKEOVER_APPETITE_DISCOUNT` 0.30 / `TAKEOVER_APPETITE_GAP_SCALE` 0.35 / `TAKEOVER_APPETITE_STREAK` 0.10 / `TAKEOVER_STREAK_LIMIT` 3 / `TAKEOVER_APPETITE_CAP` 0.95 / `TAKEOVER_APPETITE_FLOOR` 0.03，新增 `takeover_stake_gate` / `takeover_appetite` / `price_streak` / `holding_capital` / `takeover_charge` / `takeover_keep_qty` 与 `TAKEOVER_KEEP_NUMERATOR` 51 / `CLUB_BALANCE_INJECTION_RATIO` 0.10 / `GLOBAL_SCOPE = "*"`；`assert_tradable` 改为只拒买入（卖出与融资放行），`sell_plan` / `commit_sell` 对 owned 行强制保留 51% 且清仓留空批次，`finance_plan` 对 owned 跳过意愿抽签、上限按现有股本计并返回 `injection`；`_decorate` 补 `keep_shares`，`finance_room` 对 owned 用股本；`in_scope` / `scope_rows` / `canonicalize_scope` / `reconcile_scope` / `apply_scope` 支持全球条目（全球永不被剪枝） |
| `src/tools/preview_cup_odds.py` | 新增 `GLOBAL_SCOPE = "*"`；`fixture_in_custom_scope` 认得 `("*",)` 与 `(("*", "*"),)` |
| `src/fm_odds_web.py` | 新增 `_stock_market_takeover_view`（只读返回 owned / gate / appetite / streak / held / shares / credit / gross / net）与 `_finance_owned_club_injection` / `_rollback_finance_injection`（可写会话 + `expected` 旧值校验 + 失败回滚）；`_apply_stock_market_detail` 把 `takeover` 写进 detail 与 acquisition；`_execute_world_club_acquisition` 先查门槛、再查意愿，实付按 `takeover.credit` 抵扣后走 `charge_combined_funds`，行与响应补 `acquisition_credit` / `acquisition_charge` / `acquisition_appetite` 与 `charge` / `takeover`；`finance_stock` 在 commit 前取注资、异常回滚，响应补 `injection`；`_stock_market_scope_stats` / `_scope_filter_view` 支持全球（返回 `total_leagues` / `league_nations` / `league_clubs` / `global`）；`PRODUCT_VERSION` → `V2.7.9beta` |
| `src/web/app.js` | 新增 `STOCK_SCOPE_WORLD` 与 `stockScopeWorldState` / `stockScopeCycleWorld` / `stockScopeOptionKeys` / `stockFilterWorldStats` / `oddsScopeWorldStats` / `stockFilterWorldRowHtml` / `oddsScopeWorldRowHtml`；交易所筛选与盘口自定义列表顶部多一行「全球」并按两段循环切换；`autoReadStockData` 在 `ensureWorldDataScan()` 后追加 `refreshWorldClubsAfterScan()`；交易窗对 owned 放开卖出与融资；收购档案加 `worldTakeoverBlockedText` / `worldTakeoverFactsHtml` |
| `src/web/i18n.stocks.js` + 8 个语言包 | `stock.filter.world` / `_hint` / `_all_hint` / `_leagues` / `_all` / `_save`、`stock.scope.world`、`odds.filter.world`、`stock.finance.owned_note`、`stock.finance.injected`；`stock.owned.note` 改写为“可卖回 / 可融资 / 彻底退出走集团模块” |
| `src/web/i18n.world.js` + 8 个语言包 | `world.acquisition.gate` / `_value` / `_ok` / `_need`、`world.acquisition.appetite` / `_note`、`world.acquisition.credit` / `_note` |
| 版本与文档 | `PRODUCT_VERSION` / 窗口标题 / `WebViewHost.csproj`（2.7.9-beta / 2.7.9beta / 2.7.9.0）/ `fmodd_desktop.py` / `docs/development/DEVELOPMENT.md` / 三份 README（含 badge 与版本段落）/ `docs/guides/PRODUCT_GUIDE.md` / `CHANGELOG.md` / `docs/FEATURE_INDEX.md` / `docs/RUNTIME_CONTRACTS.md` |
| `tests/` | `test_club_stock_market.py`（修 2 条 owned 旧断言 + 新增 7 条：keep/sellable、`takeover_keep_qty`、`holding_capital` / `takeover_charge`、`price_streak`、`takeover_appetite`、`takeover_stake_gate`、全球范围）；`test_stock_market_application.py`（owned 改断 `keep_shares`） |

### 关键决策

- **门槛量市值，不量估值**：`market_cap` 是交易所里那张价牌上的数字，而 `intrinsic_value` 是 ODD 对整家俱乐部的估值——买家面对的是前者。交易所关掉时市场行不存在，这时才回退到估值，否则只要先关掉英格兰交易所就能把曼联当小俱乐部买。拒绝时把市值、当前持股与还差多少股一并报出来，玩家能直接去交易所补足而不是反复试错。
- **意愿是「今天的情绪」而不是判决**：倾向与抽签分开——`value` 把报价偏离、连涨天数算成一个可读的百分比，`accept` 再用 `_hash01(club_id ^ 0x51D7, 游戏日)` 每日一抽，因此同一天同一家俱乐部的答复固定、换一天重新抽，而且与其他市场随机共用同一套确定性哈希。连涨天数用 K 线自己的收盘价数（`price_streak`）而不是另算一套，避免画面与判定不一致。上限 0.95 而不是 1.0，是因为总要给玩家一个“今天不行，明天再来”的口子。
- **实付抵扣用成本而不是市值**：`holding_capital` 取每条持仓的 `qty × avg_cost`（玩家已经付过的钱）而不是当前市值，否则浮盈会让收购变贵、浮亏会让收购变得无限便宜；抵扣不超过收购价本身（`takeover_charge` 不倒找钱）。成交后原持仓转为 takeover 登记，回执记下 `acquisition_credit` 与 `acquisition_charge`，对账时能看出拕扣发生过。
- **集团俱乐部不离开市场，但不再被卖空**：`assert_tradable` 只拒买入；卖回俱乐部需保留 51% 控制权（`takeover_keep_qty` 向上取整，清仓后 `commit_sell` 留一条 `qty=0` 空批次），否则俱乐部会处于“集团拥有但不持有任何股份”的矛盾状态，`sync_takeovers` 也会在下次开盘时把它当作已出售收回。
- **注资只给自己的俱乐部，且写进游戏**：一般融资只是市场里的增资；集团旗下俱乐部的融资是业主注资，所以额外按 10%记入 FM 原生结余。写内存走请求级可写 `GameOperationSession`（用完即关，不把写权限提升为常驻），写前读结余、`write_club_balance(expected=旧值)` 校验、写后回读；发行入账失败时整笔回滚，不让“银行上没扣钱但俱乐部多了钱”的中间态留在存档里。
- **全球只作为列表顶部的一个条目**：它与国家级互斥（`nations` 含 `*` 时不再输出联赛对），`in_scope` 把 `*` 展开成全部国家，因此看板、盘口、统计三处都走同一条路；全球条目永不被 `reconcile_scope` 剪枝，避免一次扫描不全就把全市场关掉。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 隔离测试：`tests/test_club_stock_market.py` + `tests/test_stock_market_application.py` **176 passed**；股市前端六个契约文件（`test_stock_market_frontend.py` / `test_stock_scope_display_frontend.py` / `test_stock_ticket_frontend.py` / `test_stock_market_daily_refresh_frontend.py` / `test_stock_capital_frontend.py` / `test_stock_order_frontend.py`）**66 passed**。
- 文案与语言包：`test_i18n_locale_packs.py` 的 “新键无英文泄露 / 占位符一致 / 语言齐全” 四项聚焦测试 4 passed；`node --check` 覆盖 `app.js` 与全部改过的语言包。
- 广域回归：`pytest tests -k "stock or world_club or acquisition or owned_club"` 得 522 passed / 2 failed，两条失败（`test_owned_club_operations.py` 的并发与降级用例）已在备份基线工程里逐条复现，属旧有基线失败，本轮未动。
- 未实机核对：没有启动 FM 或成品 EXE（规则禁止）。收购门槛的实际感受、注资写入后的俱乐部结余读数、「全球」行在真实存档里的列表量级，都需要用户实机确认。

### 遗留

- 全球行在 3.6 万家俱乐部的存档里会一次性启用全部交易所，初始化耗时仍然与启用量成正比，界面只在第二步提示量级，没有额外的进度条；如果实测过慢，下一轮可以考虑分批初始化。
- 收购意愿只读当日，不保存历史；玩家看不到「这周意愿走向」。
- 100 亿门槛与 49% 比例写在常量里，尚未提供界面配置。

### 交付与打包

- 打包：本轮改了 `WebViewHost.cs`（窗口标题 → `FMODD V2.7.9beta`），因此先 `dotnet build src\desktop\WebViewHost.csproj -c Release`（0 警告 / 0 错误）并回拷 `src\desktop_host\FMODD.WebViewHost.exe`（**136,192 字节**，SHA-256 `E6F91448372B8E12614BAF3703462DDDC69A366FE59C1D1B0EE99BAC66401893`；上一轮为 `A7FCB0D296535320EDDB45BF52D2BFBD4F08E2767A6F56DF0FCB1E45D4679833`，两者字节数相同、差别只在版本串，`VersionInfo` 确认 `FileVersion 2.7.9.0` / `ProductVersion 2.7.9beta`）；随后 `py -X utf8 scripts\build_single_exe.py` 一次通过，产物 `dist\FMODD.exe` **60,273,039 字节**，SHA-256 `87CDCBF815ECBA3C7CECF1275E166EE15EB4D8719A357A0E859D03A555AEA781`，内部版本 `V2.7.9beta`，另存 `dist\FMODD-V2.7.9beta-第23轮.exe`（同哈希）；第 22 轮的 `dist\FMODD-V2.7.8beta-第22轮.exe` 与 `dist\FMODD-V2.7.8beta.exe` 保留未覆盖。
- 成品内容复核：用 `PyInstaller.archive.readers.CArchiveReader` 解包 `dist\FMODD.exe`（CArchive **191 条目**），确认包内 `web\app.js`（2,134,764 字节，含 `stock.filter.world` / `stock-filter-world` / `data-stock-filter-world-state` / `oddsScopeWorldRowHtml` / `stockFilterWorldStats` / `stock.finance.injected` / `worldTakeoverFactsHtml` / `worldTakeoverBlockedText` / `stockScopeCycleWorld` / `refreshWorldClubsAfterScan`）、`web\app.css`（754,296 字节）、`web\i18n.stocks.js`（38,806 字节，含 `stock.finance.owned_note` / `stock.owned.note` / `stock.scope.world` / `odds.filter.world`）、`web\i18n.world.js`（189,172 字节，含 `world.acquisition.gate` / `credit` / `appetite`）、`web\dark-theme.css`（92,723 字节）与 `desktop_host\FMODD.WebViewHost.exe`（136,192 字节）**全部与 `src\` 源文件逐字节一致**；PYZ（296 模块）内 `tools.club_stock_market` 命中 `takeover_appetite` / `takeover_stake_gate` / `holding_capital` / `takeover_charge` / `takeover_keep_qty` / `price_streak` 与 `TAKEOVER_STAKE_GATE_VALUE` / `TAKEOVER_STAKE_GATE_RATIO` / `TAKEOVER_APPETITE_BASE` / `TAKEOVER_KEEP_NUMERATOR` / `CLUB_BALANCE_INJECTION_RATIO` / `GLOBAL_SCOPE`，`fm_odds_web` 命中 `_stock_market_takeover_view` / `_finance_owned_club_injection` / `_rollback_finance_injection` 与版本字面量 `V2.7.9beta`，`tools.preview_cup_odds` 命中 `fixture_in_custom_scope` / `GLOBAL_SCOPE`，主脚本 `fmodd_desktop` 命中 `FMODD V2.7.9beta`。
- source-runtime：`py -X utf8 scripts\build_source_runtime_package.py` → `dist\FMODD-V2.7.9beta-source-runtime`（**584 文件 / 94,241,656 字节**），抽样比对 `src\web\app.js` / `src\fm_odds_web.py` / `src\web\i18n.stocks.js` / `README.md` / `CHANGELOG.md` / `docs\development\DEV_LOG.md` 均与仓库源文件逐字节一致；用 Python `zipfile`（`ZIP_DEFLATED` level 9）压成 `dist\FMODD-V2.7.9beta-source-runtime.zip`（**64,914,549 字节 / 584 条目**，SHA-256 `89F1CFCDD13ECCE3E53AFFD6DCA1EAEDE878C4622B6E94499DCD8774AA2C3483`）。
- 备份：本轮落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.8beta-2-20261016`（`project` 912 文件 / 90,006,113 字节，`dist` 5,234 文件 / 2,139,490,711 字节，`SHA256-工程清单.txt` 与 `README-备份说明.txt`），是**本轮动手之前**的基线；基线关键产物：`dist\FMODD.exe` 60,256,023 / `468D9F0C…`、`dist\FMODD-V2.7.8beta-source-runtime.zip` 64,887,578 / `BA54ED50…`、宿主 `FMODD.WebViewHost.exe` 136,192 / `A7FCB0D2…`。第 22 轮回归时被运行中实例锁住的 `dist\FMODD-V2.7.8beta-第22轮-旧构建.exe`（60,256,080）一并保留作留痕。
- 交付附带的总结文件：`dist\FMODD-V2.7.9beta-第23轮改动总结.md`（放在成品目录而不进 source-runtime 包）。
- 记录口径：`dist\FMODD-V2.7.9beta-source-runtime.zip` 与其中的 `docs/development/DEV_LOG.md` 快照在回填本节数据之前打包，所以包内快照缺「交付与打包」五条；成品与 zip 的哈希 / 字节数以本节为准。

## 第 24 轮 · 全球行联动交易所筛选与盘口范围（V2.7.9beta，2026-10-16）

### 需求（用户原话要点）

1. 点击一次「全球」后显示五千多家俱乐部，实际启用的却是全部三万多家，请修复。
2. 「全球」要与下方的国家选项联动：点击一次全球 → 下方所有国家同步启用一次；点击两次全球 → 下方所有国家同步完全启用；关闭全球 → 下方所有国家同步关闭。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/web/app.js` | 删除 `stockScopeCycleWorld`（用 `*` 代码原地切换的旧模型），新增 `stockScopeWorldNext`（`none → leagues → world → none`）与 `stockScopeWorldRows`（本次勾选覆盖的国家行）；`stockFilterWorldState` / `oddsScopeWorldState` 先识别旧 `*` 代码（`legacy`），否则从真实条目反推三态（所有可见国家整国选中 → `world`；所有可见国家的已列联赛全选且有勾选 → `leagues`）；新增 `stockFilterWorldApply` / `oddsScopeWorldApply`（清空后按 mode 写真实国家与联赛条目）、`stockFilterCycleWorld` / `oddsScopeCycleWorld`（异步：先 `ensureTables` 再写再刷新）、`stockFilterEnsureTables` / `oddsScopeEnsureTables`（一次 `GET /api/stock/scope/leagues?nation=*` 读全量联赛表，按 `saveId` 缓存）、`stockFilterAdoptWorld` / `oddsScopeAdoptWorld`（打开面板或换存档时展开旧 `*`，只进 pending）；`stockFilterPendingStats` / `oddsScopePendingStats` 与 `stockFilterWorldRowHtml` / `oddsScopeWorldRowHtml` 改用真实条目计数（旧 `*` 才回退 `stockFilterWorldStats` / `oddsScopeWorldStats`）；`stockFilterSyncIndeterminate` / `oddsScopeSyncIndeterminate` 的全球节点按 `WorldState().leagues` 判定半选；`stockFilterPendingDiff` 增 `world` 标志，删除确认据此选 `stock.filter.remove_world_confirm` |
| `src/fm_odds_web.py` | `stock_market_scope_leagues` 支持 `nation="*"`：返回 `{"ready":True,"nation":"*","bulk":True,"save_ready":…,"tables":{国家: [联赛行…]}}`；单国家路径行为不变，没有联赛的国家/地区回空数组而不是缺键 |
| `src/tools/app_settings.py` | `MAX_ODDS_SCOPE_LEAGUES` 2000 → **6000**（含注释），否则一次「全球」在 36 个国家的存档里写下 2278 个联赛条目会被截断 |
| `src/tools/preview_cup_odds.py` | 补 `from tools.club_stock_market import GLOBAL_SCOPE`（`fixture_in_custom_scope` 上一轮引用了这个未导入的名字） |
| `src/web/i18n.stocks.js` + 8 个语言包 | `stock.filter.world_hint` 改写为三态说明；新增 `stock.filter.remove_world_confirm`（十一种语言） |
| `tests/test_stock_market_application.py` | 新增 `test_the_whole_directory_answers_in_one_read_for_the_worldwide_row`、`test_a_nation_without_a_league_answers_with_an_empty_list` |
| `tests/test_stock_market_frontend.py` | 新增 `test_the_worldwide_row_writes_real_nations_and_leagues`（断言 `stockScopeWorldNext` / `stockFilterWorldApply` / `filter.nations[name] = true` / `?nation=*` 的契约与顺序） |
| `tests/test_odds_scope_custom.py` | 新增 `test_the_worldwide_row_reuses_the_exchange_picker_machinery` |

### 关键决策

- **不再用一个 `*` 代码代表「全球」**。旧模型的矛盾是结构性的：面板按“本存档有联赛的俱乐部”报数，后端按“整座目录”上市，两者永远对不上。改成把「全球」点击展开成真实的国家/地区与联赛条目写进待保存选择，显示、统计与启用范围就是同一份名单，联动也不需要额外规则——国家行本来就按条目渲染，写入真实条目后它的勾选/半选状态自然同步。
- **旧存档仍可读**。后端的 `GLOBAL_SCOPE`、`in_scope`、`scope_rows`、`reconcile_scope` 一概不动，`*` 继续被认、继续不剪枝；展开只发生在前端打开面板时（`AdoptWorld`），而且要玩家点保存才落盘，避免静默改写旧存档。
- **世界行与国家级共用同一个三态**（`stockScopeWorldNext`），两处的“点一次 = 全部联赛、点两次 = 整国、第三次 = 清空”不至于各说各话；盘口自定义范围复用交易所筛选的整套机件（`oddsScope*` 与 `stockFilter*` 同构）。
- **联赛表一次读全量**。逐国读 36 次会让「全球」点击慢且易碎，改成一个批量响应；响应带 `save_ready`，前端按 `saveId` 缓存，换存档即失效。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 静态：`node --check src\web\app.js` 与九个改过的语言包全部通过。
- 聚焦：`py -X utf8 -m pytest tests/test_club_stock_market.py tests/test_stock_market_application.py tests/test_stock_market_frontend.py tests/test_stock_scope_display_frontend.py tests/test_stock_ticket_frontend.py tests/test_stock_order_frontend.py tests/test_stock_capital_frontend.py tests/test_stock_market_daily_refresh_frontend.py tests/test_stock_board_layout_frontend.py tests/test_odds_scope_custom.py -q -p no:cacheprovider` → **279 passed**。
- 语言包：`tests/test_i18n_catalog_contract.py` + `tests/test_i18n_locale_packs.py` → **14 passed / 2 failed**，两条失败是本轮之前就在的既有失败（见错误日志 E24-05）；新增键的“键齐全 / 占位符一致 / 无英文函数词泄漏 / 无重复键”契约全部通过。
- 广域：`py -X utf8 -m pytest tests -q -k "stock or world_club or acquisition or owned_club or odds_scope or odds_reading"` → **548 passed / 2 failed**，两条失败与本轮动手前的备份工程逐条一致（`tests/test_owned_club_operations.py` 的并发与降级用例）。
- 全量复核：`py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3,521 passed / 13 failed / 239 subtests passed**，13 条失败与 `ERROR_LOG.md` 的「预存在失败」清单逐条同名（本轮改动没有新增失败；上一轮引入的 `test_odds_scope_custom.py` 5 条失败被本轮修掉）。
- 未实机核对：没有启动 FM 或成品 EXE（规则禁止）。「一次点击全球」在真实存档里要展开多少行、保存要多久，需要用户实机确认。

### 遗留

- 一次「全球」会写入上千个条目（36 国 / 2278 个联赛量级），保存请求体与 `odds_leagues` 文档随之变大；若用户反馈保存变慢，下一轮可以考虑在文档里记目录快照版本再压缩表达。
- 展开依赖一次 `?nation=*` 的全量读；目录特别大时这一步会慢，界面目前只有行内 loading 与禁用保存，没有进度条。
- `stock.filter.remove_world_confirm` 只在“存储里还有旧 `*` 条目”时出现；等所有旧存档都保存过一次之后，这条文案会自然退场。

### 交付与打包

- 打包：本轮**不改** `WebViewHost.cs`（版本号未变），`src\desktop_host\FMODD.WebViewHost.exe` 保持 136,192 字节 / `E6F91448372B8E12614BAF3703462DDDC69A366FE59C1D1B0EE99BAC66401893`；直接 `py -X utf8 scripts\build_single_exe.py` 一次通过，产物 `dist\FMODD.exe` **60,280,319 字节**，SHA-256 `1E51C467B11A2279F4D726E95AC84E7E5CB24E6F43E6AB06843483763431D407`，内部版本 `V2.7.9beta`（`FileVersion 2.7.9.0` / `ProductVersion V2.7.9beta`），另存 `dist\FMODD-V2.7.9beta-第24轮.exe`（同哈希）；第 23 轮的 `dist\FMODD-V2.7.9beta-第23轮.exe` 与更早成品保留未覆盖，上一轮的 `dist\FMODD-V2.7.9beta-source-runtime.zip` 与 `-source-runtime\` 一并改名为 `…-第23轮.zip` / `…-第23轮\` 留痕。
- 成品内容复核：用 `PyInstaller.archive.readers.CArchiveReader` 解包 `dist\FMODD.exe`（CArchive **191 条目**），确认包内 `web\app.js`（2,143,569 字节，含 `stockScopeWorldNext` / `stockScopeWorldRows` / `stockFilterWorldState` / `oddsScopeWorldState` / `stockFilterWorldApply` / `oddsScopeWorldApply` / `stockFilterCycleWorld` / `oddsScopeCycleWorld` / `stockFilterEnsureTables` / `oddsScopeEnsureTables` / `stockFilterAdoptWorld` / `oddsScopeAdoptWorld` / `stock.filter.remove_world_confirm` / `?nation=*` / `data-stock-filter-world-state`）、`web\app.css`（754,296 字节）、`web\i18n.stocks.js`（40,294 字节，含 `stock.filter.remove_world_confirm` / `stock.filter.world_hint`）、`web\i18n.tw.js` / `de` / `ja` / `pt-BR`、`web\dark-theme.css` 与 `desktop_host\FMODD.WebViewHost.exe` **全部与 `src\` 源文件逐字节一致**；PYZ（296 模块）内 `tools.app_settings` 命中 `MAX_ODDS_SCOPE_LEAGUES` / `6000`，`tools.preview_cup_odds` 命中 `GLOBAL_SCOPE` / `fixture_in_custom_scope` / `tools.club_stock_market`，`fm_odds_web` 命中 `stock_market_scope_leagues` / `bulk` / `tables` 与版本字面量 `V2.7.9beta`。
- source-runtime：`py -X utf8 scripts\build_source_runtime_package.py` → `dist\FMODD-V2.7.9beta-source-runtime`（**584 文件 / 94,287,492 字节**），抽样比对 `src\web\app.js` / `src\fm_odds_web.py` / `src\tools\app_settings.py` / `src\tools\preview_cup_odds.py` / `CHANGELOG.md` / `docs\development\DEV_LOG.md` / `docs\development\ERROR_LOG.md` / `docs\FEATURE_INDEX.md` / `docs\RUNTIME_CONTRACTS.md` / `README.md` 均与仓库源文件逐字节一致；用 Python `zipfile`（`ZIP_DEFLATED` level 9）压成 `dist\FMODD-V2.7.9beta-source-runtime.zip`（**64,890,540 字节 / 584 条目**，SHA-256 `EA9420323CD0C762B495F3770AD1149C1FFFF942761692D0A2E243B617B6C51D`）。
- 备份：本轮落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.9beta-1-20261016`，是本轮改动完成、打包之前的**工程快照**（`project` 582 文件 / 71,200,683 字节 + `SHA256-工程清单.txt` + `README-备份说明.txt`）。本轮 F: 盘可用空间只剩约 1.7 GB，而当前 `dist\` 约 2.1 GB，因此**没有复制 `dist\`**（避免写满磁盘，成品以仓库 `dist\` 为准）；要回到第 23 轮交付状态请用 `FMODD-V2.7.8beta-2-20261016\project`。快照时点的关键产物：`dist\FMODD.exe` 60,273,039 / `87CDCBF8…`（第 23 轮成品）、`dist\FMODD-V2.7.9beta-source-runtime.zip` 64,914,549 / `89F1CFCD…`、宿主 `FMODD.WebViewHost.exe` 136,192 / `E6F91448…`。
- 交付附带的总结文件：`dist\FMODD-V2.7.9beta-第24轮改动总结.md`（放在成品目录而不进 source-runtime 包）。
- 记录口径：交付的 zip 在写完「验证 / 遗留」之后、回填本节之前重建过一次，因此包内 `docs/development/DEV_LOG.md` 含本节内容；但包内写着的 zip 自身哈希 / 字节数必然是重建前的旧值（自引用无法闭合）。成品与 zip 的字节数 / 哈希一律以本节为准，`dist\FMODD-V2.7.9beta-第24轮改动总结.md` 已同步刷新。

## 第 25 轮 · 集团全资俱乐部的出售与回收（V2.7.9beta，2026-10-16）

### 需求（用户原话要点）

1. 「集团全资控股的俱乐部我希望在交易界面可以进行出售与回收股份。」

（背景：第 23 轮把 `assert_tradable` 从「买卖融三路全拒」收窄成「只拒买入」，于是玩家把股份卖回俱乐部之后再也买不回来，界面上也没有任何回收入口；本轮把买入这一路补成「从俱乐部自持账上回收股份」。）

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/tools/club_stock_market.py` | `assert_tradable` 对 owned 放行买入（语义改为回收，拒绝语改成「只能出售或回收股份」）；`buy_plan` 新增 owned 分支（可回收量 = 俱乐部自持 `capital − held`，不受 `MAX_BUY_STAKE` 25% 约束，保留每日 2% 预算与大宗 10% 单笔上限，文案「俱乐部手中已无股份可回收」/「俱乐部手中仅剩 N 股可回收」/「该俱乐部今日回收额度还剩 N 股」/「单次大宗回收申请上限为 N 股（股本的 10%）」）；`commit_buy` 在 owned 成交时递减 `takeover_sold`、`revert_buy` 回退；`fill_pending_orders` 的 owned 交割用 `room = max(0, capital − held)`；`_decorate` 新增 `buyback_room` 并让 `buy_room` 同值；`trading_limits()` 新增 `keep`（= 0.51） |
| `src/web/app.js` | `stockRowHtml` 对 owned 行画「回收」按钮（`buyback_room` 为 0 时禁用）并压窄 `stock-owned-badge`；`stockMarketLimits` 读 `keep`；`stockTicketQuote` 的 owned 报价改走回收（空库存 / 库存不足文案）；`stockLimitStripHtml` 第三、四条换成「集团至少保留 51% 股权」与「可回收 N 股」；`renderStockTicket` / `submitStockTicket` 的标题、买卖切换、模式与确认按钮、回执文案改说回收 |
| `src/web/app.css` | 新增 `.stock-row-actions .stock-owned-badge.is-compact`（32px 图标、隐去文字，行内列宽不变）；删除旧的 `form[data-stock-owned="1"] > …` 只读隐藏规则 |
| `src/web/i18n.stocks.js` + 8 个语言包 | 新增 `stock.owned.recover` / `.recover_title` / `.confirm_recover` / `.mode_block` / `.block_action` / `.cash_note` / `.room` / `.keep` / `.empty` / `.limit` / `.toast_recovered` / `.toast_block`，改写 `stock.owned.note`（十一种语言） |
| `tests/test_club_stock_market.py` | 改写 `test_a_club_the_group_owns_refuses_buy_but_still_sells_and_finances` → `test_a_club_the_group_owns_trades_its_own_book_only`；新增 `test_a_block_recovery_is_delivered_out_of_the_clubs_own_book` |
| `tests/test_stock_market_application.py` | 改写 `test_an_acquired_club_hands_its_register_to_the_group`（交接后回收 10 股，`takeover_sold` 递减） |
| `tests/test_stock_ticket_frontend.py` | 新增 `test_every_recovery_key_is_translated_in_every_locale` / `test_an_owned_club_quotes_a_recovery_instead_of_a_market_buy` / `test_the_ticket_of_a_group_club_names_both_moves` / `test_the_limits_of_a_group_club_quote_its_control_stake` |
| `tests/test_stock_board_layout_frontend.py` | 新增 `test_a_group_club_keeps_both_moves_in_the_row` |

### 关键决策

- **买入这一路不是「再买回来」，而是「回收」**。owned 俱乐部的股份本来就在集团账上（收购时整册登记交接），玩家卖回去的那部分落在俱乐部自持账上；所以可回收量的上限是「俱乐部自持」而不是「当日股本 − 我的持仓」，25% 市场持股天花板也不适用——它不是从市场里买。每日 2% 直购预算与大宗 10% 单笔上限保留，避免一次点击把整个俱乐部买空，也保持与普通交易同一套节奏与文案结构。
- **`takeover_sold` 必须跟着成交量递减**。`sync_takeovers` 把「集团持仓 − 51%」交给俱乐部，`takeover_sold` 记录已交出去的股数；回收相当于把股份从俱乐部拿回集团，如果不递减，下一次同步会认为这 51% 已经不再被集团持有而重新交接一遍，玩家白拿持仓。因此 `commit_buy` 递减、`revert_buy` 回退，并要求 `takeover_sold` 不为负。
- **界面按「两个动作」重画**。owned 行的两个按钮是「回收 / 卖出」，交易窗里买卖两侧分别说「回收」与「卖回」，限制条说「集团至少保留 51%」与「可回收 N 股」——玩家看到的是「我把股份卖给谁、能拿回多少」，而不是六个百分比。
- **旧只读规则整块删除，而不是加权重**。第 23 轮的 `[data-stock-owned]` 隐藏规则是为「owned 窗只读」写的；现在同一个标记落在可交易的回收窗上，继续保留只会互相打架，直接删掉并在契约测试里锁住「owned 窗同时有回收与卖出两路」。
- **文案形态照旧**：`i18n.stocks.js` 是三元素数组，其余八个语言包是单串；`stock.owned.room` / `.keep` 的占位符（`{qty}` / `{ratio}` + `{qty}`）在各语言里保持一致，由 `test_stock_ticket_frontend.py` 的 `OWNED_KEYS` 契约与 `test_i18n_locale_packs.py` 共同把关。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 静态：`node --check src\web\app.js` 与九个语言包全部通过。
- 聚焦：`tests/test_club_stock_market.py` + `tests/test_stock_market_application.py` **179 passed**（2.8 s）；股市前端六个契约文件（ticket / board_layout / capital / order / market_frontend / odds_scope_custom）全绿；`tests/test_stock_order_frontend.py` 恢复全绿。
- 广域：`py -X utf8 -m pytest tests -q -p no:cacheprovider -k "stock or world_club or acquisition or owned_club"` → **531 passed / 2 failed**，两条失败是 `tests/test_owned_club_operations.py` 的 `_stock_market_factors`（预存在失败）。
- 全量：`py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3,527 passed / 13 failed / 239 subtests passed**；13 条失败与 `docs/development/ERROR_LOG.md` 的「预存在失败（非本轮引入，未处理）」清单逐条同名（基线 3,521 → 3,527，本轮新增 6 条用例，无新增失败）。
- 本轮**不改**版本号：产品版本仍是 `V2.7.9beta`，窗口标题与 `WebViewHost.csproj`、`fmodd_desktop.py` 不动，因此宿主 `FMODD.WebViewHost.exe` 无需重建（保持 136,192 字节 / `E6F91448…`）。

### 遗留

- 回收与大宗回收都要占每日 2% 预算，大宗回收还受每所 8 笔待成交队列限制；这两条限制在「先大宗卖出、再大宗回收」的连招下会让玩家等到下一个游戏日，界面上只有限制条文字没有解释来源，下一轮若收到反馈可以考虑在票据里写明「今日已用」。
- owned 交易窗的「卖回」侧仍是 51% 保留额度的口径，回收侧不设上限但受俱乐部自持限制；两个额度放在同一行 chip 里，超宽窗口下数值会先换行，未做进一步压缩。
- 全量 3,527 passed 的口径只在当前机器与本轮快照上成立，`dist\` 里的成品仍是压缩后的形态，不能反过来当成源码验证。

### 交付与打包

- 打包：本轮**不改** `WebViewHost.cs`（版本号未变），`src\desktop_host\FMODD.WebViewHost.exe` 保持 136,192 字节 / `E6F91448372B8E12614BAF3703462DDDC69A366FE59C1D1B0EE99BAC66401893`；直接 `py -X utf8 scripts\build_single_exe.py` 一次通过，产物 `dist\FMODD.exe` **60,284,061 字节**，SHA-256 `CE1A6487C7531050154714859D3CDCF83A4224F026F4E86D026A0C3B0EADEEA0`，内部版本 `V2.7.9beta`（`FileVersion 2.7.9.0` / `ProductVersion V2.7.9beta`），另存 `dist\FMODD-V2.7.9beta-第25轮.exe`（同哈希）；第 24 轮的 `dist\FMODD-V2.7.9beta-第24轮.exe` 与更早成品保留未覆盖，上一轮的 `dist\FMODD-V2.7.9beta-source-runtime.zip` 与 `-source-runtime\` 一并改名为 `…-第24轮.zip` / `…-第24轮\` 留痕。
- 成品内容复核：用 `PyInstaller.archive.readers.CArchiveReader` 解包 `dist\FMODD.exe`（CArchive **191 条目**），确认包内 `web\app.js`（2,145,648 字节，含 `buyback_room` / `stock.owned.recover` / `stock.owned.toast_block` / `stock.owned.keep`）、`web\app.css`（754,496 字节，含 `.stock-owned-badge.is-compact`）、`web\i18n.stocks.js`（42,236 字节，含 12 个 `stock.owned.*` 新键）与 `web\i18n.tw.js` / `de` / `es` / `fr` / `ru` / `ja` / `pt-BR` / `pt-PT`、`web\dark-theme.css`、`desktop_host\FMODD.WebViewHost.exe` **全部与 `src\` 源文件逐字节一致**；PYZ（296 模块）内 `tools.club_stock_market` 命中 `buyback_room` / `takeover_sold` / `takeover_keep_qty` / `takeover_appetite` 与回收文案（「俱乐部手中已无股份可回收」「俱乐部手中仅剩 」「该俱乐部今日回收额度还剩 」「单次大宗回收申请上限为 」），`tools.app_settings` 命中 `MAX_ODDS_SCOPE_LEAGUES`，`fm_odds_web` 命中 `stock_market_scope_leagues` 与版本字面量 `V2.7.9beta`，`tools.preview_cup_odds` 命中 `GLOBAL_SCOPE` / `fixture_in_custom_scope`。
- source-runtime：`py -X utf8 scripts\build_source_runtime_package.py` → `dist\FMODD-V2.7.9beta-source-runtime`（**584 文件 / 94,331,258 字节**），抽样比对 `src\web\app.js` / `src\web\app.css` / `src\web\i18n.stocks.js` / `src\tools\club_stock_market.py` / `CHANGELOG.md` / `docs\development\DEV_LOG.md` / `docs\development\ERROR_LOG.md` / `docs\FEATURE_INDEX.md` / `docs\RUNTIME_CONTRACTS.md` / `README.md` 均与仓库源文件逐字节一致；用 Python `zipfile`（`ZIP_DEFLATED` level 9）压成 `dist\FMODD-V2.7.9beta-source-runtime.zip`（**64,902,557 字节 / 584 条目**，SHA-256 `1A1F3CAFAC81098FB48F2ACBC762B0C568F6287B9001EE0A5DEDCB9DEF88CC4F`）。
- 备份：本轮落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.9beta-2-20261016`，是本轮改动完成、打包之前的**工程快照**（`project` 582 文件 / 71,205,592 字节 + `SHA256-工程清单.txt` + `README-备份说明.txt`）。F: 盘可用空间约 1.4 GB 而当前 `dist\` 约 2.6 GB，因此**没有复制 `dist\`**（成品以仓库 `dist\` 为准）；要回到第 24 轮交付状态请用 `FMODD-V2.7.9beta-1-20261016\project`，或直接取 `dist\` 里的 `FMODD-V2.7.9beta-第24轮.exe` / `FMODD-V2.7.9beta-source-runtime-第24轮.zip`。快照时点的关键产物：`dist\FMODD.exe` 60,280,319 / `1E51C467…`（第 24 轮成品）、`dist\FMODD-V2.7.9beta-source-runtime.zip` 64,890,540 / `EA942032…`、宿主 `FMODD.WebViewHost.exe` 136,192 / `E6F91448…`。
- 交付附带的总结文件：`dist\FMODD-V2.7.9beta-第25轮改动总结.md`（放在成品目录而不进 source-runtime 包）。
- 记录口径：本轮先构建一次交付物、回填本节的打包数字，随后又重建一次源码运行包（`…-source-runtime\` 与 `.zip`），好让包内的 `docs/development/DEV_LOG.md` 也带上本节。因此**包内 / 包目录里写着的数字是重建前的旧值**（zip 64,902,138 字节 / `279A6703DC2787FA066701858B2792CF477764C9B008AB5A8992B28EFA713984`，目录 94,327,397 字节），自引用无法闭合；**实际交付的重建后值以本节为准**（目录 584 文件 / 94,331,258 字节，zip 64,902,557 字节 / 584 条目 / `1A1F3CAFAC81098FB48F2ACBC762B0C568F6287B9001EE0A5DEDCB9DEF88CC4F`），`dist\FMODD-V2.7.9beta-第25轮改动总结.md` 已同步刷新；成品 EXE 不受文档改动影响，其字节数与哈希始终如上。

## 第 26 轮 · CDK 兑换与交易所侧栏重绘修复（V2.7.9beta，2026-10-16）

### 需求（用户原话要点）

1. 「当点击左侧国家栏中的只看持仓按钮后，会正确跳到持仓的交易所。当此时没法点击并跳转到任意一个交易所的行情看板。只有点击刷新行情后，才可以进行点击跳转其他交易所行情看板。同理，当关闭只看持仓后，依旧得击刷新行情后，才可以进行点击跳转其他交易所行情看板。」
2. 「我想知道目前中银行有 1.5 京的额度是在哪里决定的，我希望软件初始银行中不提供金钱，仅保持 1 万现金初始资金即可。」
3. 「可以在设置中添加一个 CDK 兑换功能，目前先内置一个‘名取早耶香’可获得银行 1.5 京余额的 CDK。」

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/web/app.js` | 新增 `bindStockNationRows`，`stockRefreshNationList` 重画后重新绑定国家/地区行点击，`bindStockBoard` 改为调用它（不再内联）；`#redeem-cdk` 点击处理器（空码本地提示 → `POST /api/cdk/redeem` → `applyStatePatchOrReload` → 清空输入 → `settings.cdk.success` 带 `formatCompactMoney` 到账金额）；`localizeServerError` 增加 `cdk.empty` / `cdk.invalid` / `cdk.redeemed` 三条映射；`SETTINGS_TAB_GROUPS` 的 general 组纳入 `.cdk-setting` |
| `src/web/index.html` | `.save-account-setting` 之后新增 `.cdk-setting` 区块（说明、`#cdk-code`、`#redeem-cdk`，`data-i18n-placeholder` / `data-i18n-aria-label` 齐备） |
| `src/web/app.css` | 新增 `.settings-content .cdk-setting` 系列样式（两列输入+按钮、13px 字号、与其它设置块一致的边框与配色） |
| `src/web/dark-theme.css` | `.cdk-setting` 及其 `strong` / `small` / `input` / `button` 纳入既有的深色规则选择器 |
| `src/tools/club_economy.py` | 新增 `CDK_CODES`（`名取早耶香` → 15e15）、`_cdk_key`（全角空格/空白/大小写归一）、`redeem_cdk`（校验 → 写余额 → 记 `cdk_redeem` 流水 → 记 `cdk_redemptions` → 返回含 `cdk` 回执的公共经济投影）；`TRANSACTION_LABELS` 增 `cdk_redeem`，`transaction_category` 的 income 集合纳入它 |
| `src/tools/account_application.py` | `AccountApplicationService.redeem_cdk`（`data_scope_id` 走账户 guard，`economy_patch(result, transient=("cdk",))`） |
| `src/fm_odds_web.py` | `LocalOddsState.redeem_cdk`；`payload_routes` 注册 `POST /api/cdk/redeem` |
| `src/web/i18n.settings.js` + 8 个语言包 | 新增 9 个 `settings.cdk.*` 键，十一种语言补齐 |
| `tests/test_bank_cdk_redemption.py` | 新增：内置码入账与幂等、空白/大小写归一与拒绝码、码表金额下限、路由注册 |
| `tests/test_account_application.py` | 参数化表新增 `redeem_cdk` 行，并把 `redeem_cdk` 纳入「按钱包作用域绑定」的断言分支 |
| `tests/test_stock_market_frontend.py` | 新增 `test_the_exchange_rail_rebinds_its_rows_after_a_repaint` |
| `tests/test_settings_frontend_optimization.py` | 新增 `test_the_cdk_block_posts_to_the_bank_and_localises_refusals` |

### 关键决策

- **失效的是「监听」，不是「数据」**。国家/地区行的 HTML 每次重画都是全新的节点，旧节点随 `innerHTML` 一起被丢掉，因此点击当然没反应；「刷新行情」之所以有效，是因为它走 `renderStockMarket` → `bindStockBoard` 整板重绘。修法是把「重画」和「绑定」绑在一起（`stockRefreshNationList` 内直接 `bindStockNationRows`），而不是在 `change` 处理器里补一次 `bindStockBoard` —— 后者会把整板十几个选择器的监听重复注册一遍。
- **CDK 只做加法，不动既有余额**。玩家存档里的 1.5 京是历史 `refund_bug_liquidation` 退款留下的，代码层初始银行本来就是 0；用户要的「初始不给钱」已经成立，所以本轮不去改用户存档、也不加「清空历史退款」的隐式行为，只把兑换能力做成显式、可审计、每档只能领一次的入口。余额变更走 `_set_bank_balance_minor` + `_transaction`，与其它银行流水同一套记账。
- **兑换回执不进状态补丁**。`cdk` 字段只服务这一次的 toast（到账金额），如果混进 `state_patch.economy` 就会污染前端经济状态；`transient=("cdk",)` 把它剔出去，前端拿 `response.cdk.amount` 显示，之后 `app.state.economy` 里不会留下这个一次性字段。
- **错误码在前端本地化**。后端 `redeem_cdk` 抛 `ValueError("cdk.invalid")` 这类稳定 token，经 `normalize_error` 变成 `invalid_request`；前端 `localizeServerError` 把三个 token 映射成 `settings.cdk.*` 文案，玩家看到的是「兑换码无效」而不是 `cdk.invalid`。空输入在前端先拦一次（避免一次无意义请求），后端仍然独立校验，不依赖前端。
- **码写进代码表而不是设置文件**。`CDK_CODES` 是模块常量，`code` 作键、`amount` 作值，后续加码只要加一行；`_cdk_key` 把全角空格折成半角并去掉首尾空白、忽略大小写，避免玩家从聊天窗复制的码带不可见字符而白白失败。
- **文案形态照旧**：`i18n.settings.js` 是三元素数组（en / zh-CN / ko），其余八个语言包是单串；键名统一 `settings.cdk.*`，深度色板由 `dark-theme.css` 的既有选择器列表承接，不新写一套配色。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 后端：`tests/test_bank_cdk_redemption.py`（4 passed，含幂等与拒绝码）、`tests/test_account_application.py`（16 passed，新增 `redeem_cdk` 参数化行）。
- 前端契约：`tests/test_stock_market_frontend.py` + `tests/test_settings_frontend_optimization.py`（29 passed），覆盖「侧栏重画后重新绑定」与「CDK 区块请求/回执/错误文案本地化/文案键分组」。
- 语言：`tests/test_i18n_locale_packs.py`、`tests/test_i18n_settings.py`、`tests/test_i18n_catalog_contract.py` 中与新增键相关的用例全通过（仅保留既有失败）。
- 广域：`pytest tests -k "stock or cdk or account or i18n or settings or money or bank"` → **626 passed / 3 failed**，3 条与预存在清单逐条同名，本轮无新增失败。
- `node --check` 通过 `app.js` 与九个语言包。

### 遗留

- CDK 目前只有一条内置码，`CDK_CODES` 的扩展方式是把码作为键、`{"amount": …}` 作为值直接加行；如果后续要支持「一码多档」或「一次性码」，需要把 `cdk_redemptions` 的值从记录改成计数。
- 用户存档里那 1.5 京历史退款仍在；本轮没有提供清零手段，如需清零应作为显式功能另行确认。

### 交付与打包

- 打包：本轮**不改** `WebViewHost.cs`（版本号未变），`src\desktop_host\FMODD.WebViewHost.exe` 保持 136,192 字节 / `E6F91448372B8E12614BAF3703462DDDC69A366FE59C1D1B0EE99BAC66401893`；直接 `py -X utf8 scripts\build_single_exe.py` 一次通过，产物 `dist\FMODD.exe` **60,287,949 字节**，SHA-256 `02B795D41E77B9E0820AE6CB033DB8930EDCE1134124EC7CB4D0DC1A0B382296`，内部版本 `V2.7.9beta`（`FileVersion 2.7.9.0` / `ProductVersion V2.7.9beta`），另存 `dist\FMODD-V2.7.9beta-第26轮.exe`（同哈希）；第 25 轮的 `dist\FMODD-V2.7.9beta-第25轮.exe` 与更早成品保留未覆盖，上一轮的 `dist\FMODD-V2.7.9beta-source-runtime.zip` 与 `-source-runtime\` 一并改名为 `…-第25轮.zip` / `…-第25轮\` 留痕。
- 成品内容复核：用 `PyInstaller.archive.readers.CArchiveReader` 解包 `dist\FMODD.exe`（CArchive **191 条目**），确认包内 `web\app.js`（2,147,160 字节，含 `bindStockNationRows` / `redeem-cdk` / `settings.cdk.success` 与 `cdk.empty` / `cdk.invalid` / `cdk.redeemed` 三条本地化映射）、`web\index.html`（106,514 字节，含 `.cdk-setting` 与 `#cdk-code` / `#redeem-cdk`）、`web\app.css`（755,326 字节，含 `.cdk-setting` 样式）、`web\dark-theme.css`（92,814 字节，含深色 `.cdk-setting` 选择器）、`web\i18n.settings.js`（25,831 字节，含 9 个 `settings.cdk.*` 键）、`web\i18n.tw.js` / `de` / `es` / `fr` / `ru` / `ja` / `pt-BR` / `pt-PT` 与 `desktop_host\FMODD.WebViewHost.exe` **全部与 `src\` 源文件逐字节一致**；PYZ（296 模块）内 `tools.club_economy` 命中 `CDK_CODES` / `名取早耶香` / `cdk_redeem` / `cdk.empty` / `cdk.invalid` / `cdk.redeemed`，`tools.account_application` 命中 `AccountApplicationService.redeem_cdk`，`fm_odds_web` 命中 `/api/cdk/redeem` 与 `redeem_cdk`。
- source-runtime：`py -X utf8 scripts\build_source_runtime_package.py` → `dist\FMODD-V2.7.9beta-source-runtime`（**585 文件 / 94,362,022 字节**），抽样比对 `src\web\app.js` / `src\web\index.html` / `src\web\app.css` / `src\web\dark-theme.css` / `src\web\i18n.settings.js` / `src\web\i18n.ja.js` / `src\tools\club_economy.py` / `src\tools\account_application.py` / `src\fm_odds_web.py` / `tests\test_bank_cdk_redemption.py` / `CHANGELOG.md` / `docs\FEATURE_INDEX.md` / `docs\RUNTIME_CONTRACTS.md` / `docs\development\DEV_LOG.md` / `docs\development\ERROR_LOG.md` 均与仓库源文件逐字节一致；用 Python `zipfile`（`ZIP_DEFLATED` level 9）压成 `dist\FMODD-V2.7.9beta-source-runtime.zip`（**64,913,007 字节 / 585 条目**，SHA-256 `09F365B091FBA959A78A54836BE7DB415A663C0E331036358E491B8AFAA1E3F7`）。
- 备份：本轮落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.9beta-3-20261016`，是本轮改动完成、打包之前的**工程快照**（`project` 583 文件 / 71,280,041 字节 + `SHA256-工程清单.txt` + `README-备份说明.txt`）。F: 盘可用空间约 1.09 GB 而当前 `dist\` 约 2.6 GB，因此**没有复制 `dist\`**（成品以仓库 `dist\` 为准）。快照时点的关键产物：`dist\FMODD.exe` 60,284,061 / `CE1A6487…`（第 25 轮成品）、`dist\FMODD-V2.7.9beta-source-runtime.zip` 64,902,557 / `1A1F3CAF…`（第 25 轮 zip）、宿主 `FMODD.WebViewHost.exe` 136,192 / `E6F91448…`。回滚到第 26 轮之前请用 `FMODD-V2.7.9beta-2-20261016\project` 再叠加第 25 轮改动，或直接用 `dist\FMODD-V2.7.9beta-第25轮.exe`。
- 交付附带的总结文件：`dist\FMODD-V2.7.9beta-第26轮改动总结.md`（放在成品目录而不进 source-runtime 包）。
- 记录口径：本轮先构建一次交付物、回填本节的打包数字，随后又重建一次源码运行包（`…-source-runtime\` 与 `.zip`），好让包内的 `docs/development/DEV_LOG.md` 也带上本节。因此**包内 / 包目录里写着的数字是重建前的旧值**，自引用无法闭合；**实际交付的重建后值以 `dist\FMODD-V2.7.9beta-第26轮改动总结.md` 为准**；成品 EXE 不受文档改动影响，其字节数与哈希始终如上。

## 第 27 轮 · 股市二级菜单与应用内公告板（V2.8.0beta，2026-10-17）

### 需求（用户原话要点）

1. 「左侧侧边栏的功能模块栏中，目前股市系统只有一级菜单，我想做成二级菜单，即股市分为交易所、持仓、交易记录、市场公告四个部分。就像世界分为世界俱乐部、世界球员、世界国家三个二级菜单一样。不过点击股市一级菜单会自动跳到交易所二级菜单，交易所目前的布局保持不变。」
2. 「切换到持仓会打开新的界面展现玩家的所有持仓。交易记录以及市场公告同理。」
3. 「在上方右侧的邮件左侧新增一个『公告』按钮，来显示软件的公告。目前先内置启动软件后的弹窗公告……这个公告应当类似 QQ 群公告一样，可多条展示。」
4. 「版本号迭代到 2.8.0Beta。做好开发日志、错误日志迭代，以备后续开发。检查工程文件，移除冗余不必要文件，如旧版备份、同版本开发包等等，目前可仅保留 2.7.9Beta 版本工程及成品文件。」
5. 动手前要求「先备份现有的项目工程以及成品」。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/web/index.html` | 股市由单按钮改为 `#stocks-toggle` + `#stocks-subnav` 分组（四个 `data-page`：`stocks` / `stock-holdings` / `stock-trades` / `stock-notices`）；新增 `#page-stock-holdings` / `#page-stock-trades` / `#page-stock-notices` 三张页面（各含 `*-content`、`*-sync` 与 `[data-stock-refresh]` 按钮）；顶栏 `#mail-button` 之前插入 `#announcement-button`（含 `#announcement-dot`）；`#mail-dialog` 之后新增 `#announcement-dialog`（`#announcement-subtitle` + `#announcement-content`） |
| `src/web/app.js` | `SIDEBAR_GROUP_IDS` 增 `stocks`；`showPage` 增函数作用域 `stockPage` 标记（驱动侧栏分组展开、`active` 与 `if (stockPage)` 的行情加载），`renderers` 增三个工作区渲染器，`[data-page]` 点击处理增 `stocks-toggle` 分支；`renderStockMarket()` 在自身早退之前调用 `renderStockWorkspaces()`；`refreshStockMarket()` 同时接管 `#stock-refresh-button` 与所有 `[data-stock-refresh]`；新增约 430 行工作区与公告板实现：`stockWorkspaceFilters` / `stockWorkspaceSignature` / `resetStockWorkspaceSignature` / `renderStockWorkspaces` / `stockWorkspaceRender` / `stockBindWorkspace` / `stockReceiptById` / `stockHoldingLotHtml` / `stockHoldingsHtml` / `renderStockHoldings` / `stockLedgerSideKey` / `stockLedgerTone` / `stockLedgerRowHtml` / `stockReceiptRowHtml` / `stockTradesHtml` / `renderStockTrades` / `stockNoticeGroup` / `stockNoticeTapeHtml` / `stockNoticesHtml` / `renderStockNotices`，以及 `ANNOUNCEMENT_SEEN_STORAGE_KEY` / `ANNOUNCEMENT_COLLAPSE_LENGTH` / `ANNOUNCEMENT_BOARD` / `announcementEntries` / `announcementSeenId` / `announcementUnread` / `announcementCardHtml` / `renderAnnouncements` / `renderAnnouncementBadge` / `markAnnouncementsSeen` / `openAnnouncements` / `showStartupAnnouncements` / `bindAnnouncementBoard`；`showInitialUsageNotice` 的两条提前退出与欢迎确认按钮都接上 `showStartupAnnouncements()`；`bindAnnouncementBoard()` 紧接在 `$("#mail-button")` 绑定之前执行 |
| `src/web/app.css` | `.stocks-page` 与 `.stock-workspace-page` 共享调色板；追加 `.stock-workspace*` / `.stock-lot-row`（5 列网格 + 1440 / 1180 / 900 三档断点）/ `.stock-row-action` / `.stock-ledger-row` / `.stock-slip-row` / `.stock-tape-row` / `.stock-order-badge` / `.announcement-*` / `.top-action-dot` |
| `src/web/dark-theme.css` | 上述新增块全部补深色覆盖（`.stock-workspace-filters button:hover` 用 `rgba(255,255,255,.08)` 而不是八位十六进制，避免 `test_dark_mode_frontend` 把 `background:#fff…` 当成硬编码白底） |
| `src/web/i18n.stocks.js` | 新增 27 个键：`nav.stock_exchange` / `nav.stock_holdings` / `nav.stock_trades` / `nav.stock_notices`、`stock.holdings.*`、`stock.trades.*`、`stock.notices.*`、`stock.holding.reserved` / `.orders` / `.stake` |
| `src/web/i18n.static.js` | 新增 13 个公告键：`top.announcements`、`announce.title` / `.subtitle` / `.author` / `.pinned` / `.expand` / `.collapse` / `.empty` / `.unread`，以及两条内置公告的标题与正文（`announce.subtitle` 必须带 `{count}`） |
| `src/web/i18n.tw.js` + de / es / fr / ru / ja / pt-BR / pt-PT | 同步上述 27 + 13 个键，十一种语言全部补齐 |
| `src/fm_odds_web.py` | `PRODUCT_VERSION` → `V2.8.0beta`；非 FROZEN 的 `APP_VERSION` → `42-dev` |
| `src/fmodd_desktop.py` | 弹窗标题 → `FMODD V2.8.0beta` |
| `src/desktop/WebViewHost.cs` / `.csproj` | 窗口标题 → `FMODD V2.8.0beta`；Version `2.8.0-beta` / InformationalVersion `2.8.0beta` / AssemblyVersion & FileVersion `2.8.0.0` |
| `tests/test_shell_frontend_optimization.py` | 侧栏分组用例的元素数组与关闭态断言补上 `stocks` |
| `tests/test_stock_workspaces_frontend.py` | 新增 9 条：侧栏四段结构、分组切换只认股市页面、三张页面各自带内容根与刷新控件、渲染器注册、`stockPage` 只声明一次且在导航块之前、看板在早退之前扇出工作区、工作区签名按页缓存、刷新覆盖全部控件、27 个键在十一种语言可解析 |
| `tests/test_announcements_frontend.py` | 新增 9 条：公告按钮在邮件左侧且带未读点、弹窗结构、公告表条目完整且 id 唯一、卡片逐条渲染与空态、展开收起、未读键与小红点、欢迎界面关闭后弹出一次、绑定位置在顶栏、全部键在十一种语言可解析且 `announce.subtitle` 带 `{count}` |
| `README.md` / `README.zh-CN.md` / `README.ko-KR.md` | badge、`V2.8.0beta` 发行段与「当前版本」行 |
| `docs/guides/PRODUCT_GUIDE.md`、`docs/development/DEVELOPMENT.md` | 版本号与当前版本说明 |
| `CHANGELOG.md` | 新增 `## V2.8.0beta（2026-10-17）` 小节 |
| `docs/FEATURE_INDEX.md` | `stock-market` 行改为四页入口，新增 `announcements` 行，`## stock-market` 详细链路补上本轮覆盖点 |
| `docs/RUNTIME_CONTRACTS.md` | 「前端交互契约」补「四页共用一份载荷 + 工作区签名 + 只翻转忙碌态」与「公告板无后端真值、未读只写本机」两段 |

### 关键决策

- **一级菜单仍然落到交易所**。`#stocks-toggle` 同时是分组开关和 `data-page="stocks"` 的导航按钮：点击时先按 `club-toggle` 的既有写法切换展开态，再交给 `showPage("stocks")`，所以「点一级菜单进交易所」是导航的自然结果，而不是额外分支。
- **三张新页面不新增后端接口**。交易所页面已经把整份 `/api/stock/market`（持仓、成交、回执、公告、指数、委托与限额）读进 `stockMarketState()`，持仓 / 交易记录 / 市场公告因此只做投影：`renderStockMarket()` 在**自身早退之前**调用 `renderStockWorkspaces()`，四个页面共享同一次读取、同一次重绘，切换页面零成本。工作区各自持有渲染签名，避免「在看板上敲搜索框也把另外三页整段重画」。
- **`stockPage` 必须是函数作用域变量**。第一版把 `const stockPage = [...]` 写在 `app.navigationRenderSignature !== navigationSignature` 块里，而真正触发行情加载的 `if (stockPage)` 在块外——`node --check` 查不出块级作用域越界，却会让整页在每次切页时抛 `ReferenceError`。已把声明提到 `navigationSignature` 之后（详见错误日志 E27-01），并新增一条测试锁住「只声明一次且在导航块之前」。
- **公告是编译期常量，不是配置**。`ANNOUNCEMENT_BOARD` 用 `Object.freeze`，条目只写 `id` / `date` / `time` / `pinned` / `version` / `key`，正文全部走 `announce.entry.*.title` / `.body` 语言键，因此同一条公告在十一种语言下都可读，也不需要任何后端接口或存档字段。未读状态只写本机 `localStorage["fmodd-announcements-seen"]`（保存最新条目 id），不进存档、不随账户切换。
- **公告板不抢欢迎弹窗的焦点**。`showStartupAnnouncements()` 在 `announcementUnread()` 为假或 `#usage-notice-dialog` 仍打开时直接返回；欢迎界面有两条提前退出路径（已展示过、仍在「不再提示」窗口内），两条都与确认按钮一起接上 `showStartupAnnouncements()`，所以无论玩家怎么关掉欢迎界面，公告板都恰好弹出一次。
- **`.stock-workspace-page` 与 `.stocks-page` 共用调色板**，不复制一套变量；深色覆盖写进 `dark-theme.css` 的既有追加区，避免出现第二套配色真源。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 新增：`tests/test_stock_workspaces_frontend.py` **9 passed**、`tests/test_announcements_frontend.py` **9 passed**（两条都含「十一种语言可解析」的 node/vm 契约）。
- 聚焦：`tests/test_shell_frontend_optimization.py` + `tests/test_home_desktop.py` + `tests/test_i18n_frontend.py` + `tests/test_existing_page_hierarchy.py` → **73 passed**（侧栏分组用例补 `stocks` 后恢复全绿）。
- 深色：`tests/test_dark_mode_frontend.py` → **9 passed**。
- 广域：`pytest tests` → 与预存在清单逐条同名（详见「交付与打包」一节的实测数字），本轮无新增失败。
- `node --check` 通过 `src/web/app.js` 与九个语言包文件；`app.css` / `dark-theme.css` 花括号配平。

### 遗留

- 公告板目前只有两条内置公告，加公告的方式是在 `ANNOUNCEMENT_BOARD` 加一行并在十一种语言的 `i18n.static.js` / 语言包里补 `announce.entry.*.title` / `.body`；如果后续要做「服务端下发公告」，需要另外设计来源与缓存，不能直接复用本机未读键。
- 持仓页与交易记录页共用看板的项目符号口径，暂未提供导出、排序或分组记忆；市场公告页跟随看板范围，没有独立的交易所筛选。
- `APP_VERSION` 的非 FROZEN 值升到 `42-dev`，仅影响开发态显示，不进入打包产物。

### 交付与打包

- **全量复核**：`py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3,552 passed / 13 failed / 239 subtests passed**，13 条失败与本文档「预存在失败（非本轮引入，未处理）」清单逐条同名（`test_account_store`、`test_championship_lifecycle`、`test_championship_odds`、`test_club_policies`、`test_i18n_catalog_contract`、`test_i18n_locale_packs`、`test_league_points_item`、`test_odds_profiles`、`test_owned_club_operations` 2 条、`test_pending_result_search`、`test_profit_analysis_colors`、`test_refresh_optimization`），本轮没有新增失败。
- **实机核对**：**未做**——本轮没有启动成品 EXE，也没有连接 FM 进程或读写玩家存档（遵守仓库规则）。窗口标题、版本资源与包内容只用静态解包核对。
- **宿主重建**：本轮改了 `WebViewHost.cs`（窗口标题），因此用 `dotnet build src\desktop\WebViewHost.csproj -c Release` 重建（Build Tools 的 MSBuild 缺 `.NET SDK`，改用 `dotnet build` 通过，0 警告 0 错误），产物复制回 `src\desktop_host\FMODD.WebViewHost.exe`：**136,192 字节** / SHA-256 `EB62BD8808A86A710CA074A85B8359F9BC832AB81D43D369874FDC82D5D7E3FC`，`FileVersion 2.8.0.0` / `ProductVersion 2.8.0beta`，二进制内含 UTF-16 串 `FMODD V2.8.0beta`（上一轮为 `E6F91448…`，标题不同所以字节不同）。
- **打包**：`py -X utf8 scripts\build_single_exe.py` 一次通过，`dist\FMODD.exe` **60,353,961 字节**，SHA-256 `2FDD39D7372292077342103AE88E8052F3BAFDD70C719EE18C7E7020FB320128`（`FileVersion 2.8.0.0` / `ProductVersion V2.8.0beta`），另存 `dist\FMODD-V2.8.0beta.exe`（同哈希）。
- **成品内容复核**：用 `PyInstaller.archive.readers.CArchiveReader` 解包 `dist\FMODD.exe`（CArchive **191 条目**），确认包内 `web\app.js`（2,158,246 字节）/ `web\index.html` / `web\app.css` / `web\dark-theme.css` / `web\i18n.stocks.js` / `web\i18n.static.js` / `web\i18n.tw.js` / `web\i18n.de.js` / `web\i18n.es.js` / `web\i18n.fr.js` / `web\i18n.ru.js` / `web\i18n.ja.js` / `web\i18n.pt-BR.js` / `web\i18n.pt-PT.js` / `desktop_host\FMODD.WebViewHost.exe` 与仓库源文件**逐字节一致**（mismatch 0）；包内 `web\app.js` 含 `stock-holdings` / `ANNOUNCEMENT_BOARD` / `fmodd-announcements-seen` / `renderStockWorkspaces` / `const stockPage = `，入口脚本 `fmodd_desktop` 含 `FMODD V2.8.0beta`（且不再含 `V2.7.9beta`），PYZ 内 `fm_odds_web` 的常量为 `PRODUCT_VERSION = "V2.8.0beta"` 与开发态 `APP_VERSION = "42-dev"`。
- **source-runtime**：`py -X utf8 scripts\build_source_runtime_package.py` → `dist\FMODD-V2.8.0beta-source-runtime`（**587 文件 / 90.2 MiB**），抽样比对 `src\web\app.js` / `src\web\index.html` / `src\web\app.css` / `src\web\dark-theme.css` / `src\web\i18n.stocks.js` / `src\web\i18n.static.js` / `src\web\i18n.tw.js` / `src\web\i18n.pt-PT.js` / `src\fm_odds_web.py` / `src\fmodd_desktop.py` / `src\desktop\WebViewHost.cs` / `src\desktop\WebViewHost.csproj` / `src\desktop_host\FMODD.WebViewHost.exe` / `CHANGELOG.md` / `docs\FEATURE_INDEX.md` / `docs\RUNTIME_CONTRACTS.md` / `docs\development\DEV_LOG.md` / `docs\development\ERROR_LOG.md` / `tests\test_stock_workspaces_frontend.py` / `tests\test_announcements_frontend.py` 均与仓库源文件逐字节一致（mismatch 0）；用 Python `zipfile`（`ZIP_DEFLATED` level 9）压成 `dist\FMODD-V2.8.0beta-source-runtime.zip`（**64,995,819 字节 / 587 条目**，SHA-256 `d77d84e3f5a9fa51ba81f43212960ae261bbf8f86cd46e01987127db30cc06f2`）。**该数字是第一次构建的值**，回填本节后又重建过一次，最终交付值见下一条。
- **F: 盘与网络**：打包时 F: 可用空间约 96 GB（不再受第 24–26 轮的 0.7–1.7 GB 限制），因此本轮 `dist` 与备份都完整落盘。`scripts\build_source_runtime_package.py` 会先取 `%TEMP%\python-3.14.6-embed-amd64.zip`（缓存命中则校验 SHA-256 后直接使用）；本轮 python.org 直连下载停滞（`urllib` 无整体超时，首次运行卡在读取阶段），改用国内镜像 `https://registry.npmmirror.com/-/binary/python/3.14.6/python-3.14.6-embed-amd64.zip` 取得同一文件（12,570,832 字节，SHA-256 `DF901E84A896FF1EE720AD03377E0C8D8C2244FDA79808AEEAFF6316DF1CB75C`，与脚本内置常量一致），脚本据此走缓存分支、不再联网。
- **清理**：本轮删除 `dist\` 内 **44 个条目 / 2,737,668,086 字节**（V2.7.0beta–V2.7.8beta 全部成品与源码包、V2.7.9beta 第 23–25 轮成品 / 源码包 / 摘要、`FMODD-V2.7.8beta-第22轮-旧构建.exe` 等同版本重复开发包），删除前后均校验路径在 `dist\` 之内；完整清单见 `dist\FMODD-V2.8.0beta-第27轮改动总结.md` 的「清理记录」一节。清理后 `dist\` 只留 V2.7.9beta 第 26 轮成品与 V2.8.0beta 本轮产物。
- **备份**：本轮落在 `F:\File\Other\Dev\_fmodd_backups\FMODD-V2.7.9beta-4-20261017`，是**动手前的工程与成品快照**（`project` 583 文件 / 71,336,795 字节 + `SHA256-工程清单.txt` + `README-备份说明.txt`，另含第 26 轮成品 `FMODD-V2.7.9beta.exe` 60,287,949 字节 / `02B795D41E77B9E0820AE6CB033DB8930EDCE1134124EC7CB4D0DC1A0B382296`）。备份 README 已声明「删除清单见 `dist\FMODD-V2.8.0beta-第27轮改动总结.md` 的清理记录」，该文件本轮已生成，声明闭合。
- **交付附带的总结文件**：`dist\FMODD-V2.8.0beta-第27轮改动总结.md`（放在成品目录而不进 source-runtime 包）。

- **最终交付的 source-runtime**：回填本节并重建一次后，`dist\FMODD-V2.8.0beta-source-runtime.zip` = **64,997,251 字节 / 587 条目**，SHA-256 `639a51ccd7d1988b7d472aa407ee6e909158141874d5567a43679573fcb97e87`；包内 `docs\development\DEV_LOG.md` 已含本轮全部改动与成品 EXE 的数字，但不含本行（自引用无法闭合）。
- **记录口径**：文档里的打包数字按「先构建、再回填、重建一次」的顺序记录，因此包内的 zip 字节数与哈希是**重建前**的值；**实际交付值以 `dist\FMODD-V2.8.0beta-第27轮改动总结.md` 为准**。成品 EXE 不受文档改动影响，其字节数与哈希始终如上（60,353,961 / `2FDD39D7…`）。

## 第 28 轮 · 启动顺序修复：未连档启动的三联症（V2.8.0beta，2026-10-17）

### 需求（用户原话要点）

1. 「修复打开软甲未连接存档时，首页的功能图标不显示的问题。」
2. 「修复公告、邮件、设置等按钮无法点击失效的问题。」
3. 「修复股市行情一直处于『正在读取俱乐部行情...』的问题。」
4. 沿既有口径，动手前先备份项目工程与成品。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `src/web/app.js` | 启动段 4 行（`initializeCustomSelects(); bindEvents(); … renderIcons();`、`checkForUpdates({silent:true});`、`showPage("home");`、`showInitialUsageNotice();`）从第 27 轮版的第 31231–31234 行整体移到文件末尾，成为**文件最后一条语句**；文件末尾新增「Boot 必须是文件最后一条语句」说明注释；原位置衔接处保留一个空行，文件净增一段注释 |
| `tests/test_app_boot_order.py` | 新增 3 条启动顺序护栏：启动行唯一且是文件最后一条语句（其后只允许注释与已知的三条启动语句）、启动行之后不允许出现顶层 `const/let/class`、公告板与股市常量必须声明在启动行之前 |
| `CHANGELOG.md` | V2.8.0beta 增加「启动顺序修复：未连档启动的三联症（第 28 轮）」小节 |
| `docs/development/ERROR_LOG.md` | 新增 E28-01（TDZ 链、三症状同源、修复与回归） |
| `docs/FEATURE_INDEX.md` | `announcements` 行补充「公告常量与绑定函数必须整体位于文件末尾 Boot 段之前」的约定与回归指向 |
| `docs/development/DEV_LOG.md` | 本节 |

### 关键决策

- **三个症状是同一个根因**。第 27 轮把「股市工作区 + 公告板」约 430 行整段插在启动行之后，而 `bindEvents()` 内部（第 30386 行附近）启动时就会调用 `bindAnnouncementBoard()` → `renderAnnouncementBadge()` → `announcementUnread()` → `announcementEntries()`，沿途读取 `ANNOUNCEMENT_BOARD` 等三个 `const`；脚本自上而下求值时启动行先执行，这些 `const` 仍在暂时性死区，抛 `ReferenceError: Cannot access 'ANNOUNCEMENT_BOARD' before initialization`。后果：`bindEvents()` 在 30386 行中断（邮件 30387 / 设置 30423 / 钱包 30559 等监听器全部未注册）、启动行其余部分与 `bootstrapState()` / `renderIcons()` / `showPage("home")` 不再执行（首页图标不渲染，未连档时尤其明显——连接存档后是 `render()` 顺手补上的图标），启动行以下 18 个顶层 `const`（`STOCK_SORT_KEYS` 起）与公告板永远停留死区（股市读取路径一碰就抛，页面停在「正在读取俱乐部行情…」）。
- **修法选择「把 boot 沉到文件末尾」，而不是「把公告块提到启动行之前」**。那 430 行的新块只要将来再多一个被启动路径读到的常量，同类事故就会复发；把启动行放到最后，让「启动时任何顶层 `const` 都已求值」成为文件级不变量，也便于写成一条廉价的静态测试。
- **测试口径选「最后一条语句」**。与其逐个点名当前会被读到的常量，不如约束整段启动块的位置；未来的新功能只要遵守「声明在 boot 之前」就不会再踩。
- **不改版本号、不动第 27 轮功能**。这是第 27 轮缺陷的修复轮，产品版本仍是 `V2.8.0beta`，窗口标题与 FileVersion 不变；四页工作区与公告板行为按第 27 轮原样保留。
- **未启动 FM、未启动成品 EXE、未改动存档**：验证全部走静态检查、契约测试与包内容比对。

### 验证

- **二次扫描**：抽查改用「独立词 `FMODD`（排除路径、域名、标识符）」的口径重扫一遍 `src/`，抓到 9 处漏改——三条公告里的免责声明句「FMODD 是面向 Football Manager 的非官方辅助工具…」（11 种语言中的 9 种仍写旧名，pt-BR / pt-PT 已是新名），已逐条改为 FMEDD 并**重新打包**；最终成品哈希见本节「交付与打包」。

- 静态：`node --check src\web\app.js` 通过；启动行唯一且位于文件末尾（其后仅有 `checkForUpdates` / `showPage("home")` / `showInitialUsageNotice` 三条）。
- 新增护栏：`tests/test_app_boot_order.py` → **3 passed**。
- 聚焦：`test_app_boot_order + test_announcements_frontend + test_stock_workspaces_frontend + test_stock_market_frontend + test_home_desktop + test_shell_frontend_optimization + test_update_check + test_frontend_refresh_recovery + test_dark_mode_frontend + test_existing_page_hierarchy + test_i18n_frontend` → **245 passed**。
- 全量：`py -X utf8 -m pytest tests -q -p no:cacheprovider` → **3555 passed / 13 failed / 239 subtests passed**；13 条与「预存在失败（非本轮引入，未处理）」清单逐条同名（第 27 轮 3552 passed + 本轮新增 3 条护栏，无新增失败）。
- 包内核对（CArchiveReader）：EXE 内 `web\app.js` / `index.html` / `app.css` / `dark-theme.css` / `i18n.stocks.js` / `i18n.static.js` / `desktop_host\FMODD.WebViewHost.exe` 与仓库源文件逐字节一致（mismatch 0）；包内 `app.js` 中公告板常量与股市常量均位于启动行之前（顺序断言 True）。

### 遗留

- 无新增遗留；13 条预存在失败照旧不处理（清单见 ERROR_LOG）。

### 交付与打包

- **备份（动手前）**：`F:\File\Other\Dev\_fmodd_backups\FMODD-V2.8.0beta-1-20261017` —— `project` 551 文件 / 70,200,014 字节、第 27 轮成品 `FMODD-V2.8.0beta.exe`（60,353,961 字节 / `2FDD39D7372292077342103AE88E8052F3BAFDD70C719EE18C7E7020FB320128`，README 已注明其为带缺陷快照）、`SHA256-工程清单.txt` 与 `README-备份说明.txt`。
- **EXE**：`py -X utf8 scripts\build_single_exe.py` → `dist\FMODD.exe`（**60,354,145 字节**，SHA-256 `de15b6fda335338c1a7ab43eb90d3438ed54ebdf711f460f63bd7234496e447b`，FileVersion 2.8.0.0 / ProductVersion V2.8.0beta），复制为 `dist\FMODD-V2.8.0beta.exe`。构建未联网。
- **source-runtime**：先确认 `%TEMP%\python-3.14.6-embed-amd64.zip` 缓存命中（SHA-256 校验通过、未触发 python.org 下载），再 `py -X utf8 scripts\build_source_runtime_package.py` 重建 `dist\FMODD-V2.8.0beta-source-runtime`，并以 Python `zipfile`（`ZIP_DEFLATED` level 9）压成 `dist\FMODD-V2.8.0beta-source-runtime.zip`。**zip 自身的最终字节数与 SHA-256 记录在 `dist\FMODD-V2.8.0beta-第28轮改动总结.md`**（文档在包内，自引用无法闭合）。
- **交付附带的总结文件**：`dist\FMODD-V2.8.0beta-第28轮改动总结.md`（放在成品目录而不进 source-runtime 包）。
- **上一轮卡顿的交代**：第 27 轮打包曾卡在 python.org 直连下载（urllib 无整体超时）；本轮缓存命中后脚本直接走校验分支，打包全程无网络等待。

## 下一轮起始检查清单

1. 读 `docs/development/DEV_LOG.md`（本节）与 `docs/development/ERROR_LOG.md`，确认要处理的问题是否已有条目。
2. 读 `CHANGELOG.md` 最新版本段落与 `docs/FEATURE_INDEX.md` 的股市行，确认改动归属模块。
3. 检查 Git 状态与目标 diff（本仓库当前无 Git，用备份目录做基线）。
4. 改动后按 `docs/development/DEVELOPMENT.md` 的聚焦测试口径验证，再补本文件与错误日志。
5. 打包前先备份（project + dist + 说明文件），打包后核对 SHA-256。





## 第 72 轮 · 家庭青训状态与子女工作台修复（2026-10-21）

### 改动

- 将本地试训通过与 FM 原生青训生成拆成 `trial_passed` / `playing`，旧档无 UID 的 `training` 自动兼容迁移。
- 青训投放接口只允许试训通过记录进入原生 `academy_son` 计划；Hook 安装、地址扫描或写入失败时保留具体诊断并回滚。
- 家庭页子女档案改为“家长列表 → 子女选择器 → 当前子女详情”，避免成长、头像、历史和青训操作全部堆在同一张卡片集合中。

### 验证边界

- 未启动 FM、未启动成品 EXE、未读写用户存档；旧版 1.5.1 EXE 仅作静态包与青训模块证据参考。
- 聚焦测试覆盖试训迁移、原生计划完成同步和家庭页前端结构。

## 第 72 轮构建记录 · V2.9.4Beta EXE（2026-10-21）

- 使用 `py scripts\build_single_exe.py` 构建本地单文件测试分发包。
- 输出：`dist\FMODD.exe` 与 `dist\FMSDD-V2.9.4Beta.exe`。
- 文件大小：85,554,296 字节；SHA-256：`3d395d163d5a1d61c07871c3bbedc98a784b4856bfc25dc72442e99ea94dcca9`。
- 版本资源：FileVersion `2.9.4.0`，ProductVersion `V2.9.4Beta`，ProductName `FMSDD`。
- 静态包核对：PyInstaller 归档 645 项，包含 `fm_odds_web`、`tools.life_children`、`tools.life_interactions`。
- 未启动成品 EXE，未连接 Football Manager，未读取或修改用户存档。

