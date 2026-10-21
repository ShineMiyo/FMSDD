(() => {
  "use strict";
  const modules = window.FMODDI18nModules = window.FMODDI18nModules || [];
  const title = {
    "en-GB": "What changed from V2.9.0 to V2.9.6",
    "zh-CN": "内容更新汇总：V2.9.0 → V2.9.6",
    "zh-TW": "內容更新彙總：V2.9.0 → V2.9.6",
    "ko-KR": "V2.9.0 → V2.9.6 업데이트 정리",
    "de-DE": "Was sich von V2.9.0 bis V2.9.6 geändert hat",
    "es-ES": "Cambios de V2.9.0 a V2.9.6",
    "fr-FR": "Ce qui a changé de V2.9.0 à V2.9.6",
    "ru-RU": "Что изменилось с V2.9.0 по V2.9.6",
    "ja-JP": "V2.9.0 → V2.9.6 の更新まとめ",
    "pt-BR": "O que mudou da V2.9.0 até a V2.9.6",
    "pt-PT": "O que mudou da V2.9.0 até à V2.9.6",
  };
  const en = `> From V2.9.0 to V2.9.6: relationship lines, asset levels, garage and storage, children and youth intake, outside encounters, the rebuilt family page, intimacy, cash gifts and bought action points.

## V2.9.1 · Relationship lines and batch management
- Relationships now branch by gender: friend, couple, sibling or close-friend lines; the first step locks the line.
- A separate 11-step relationship level and a tone description replace the old single progress label.
- Asset level moved to its own timeline beside the player name; property, garage and showroom gain one-click and batch buying.

## V2.9.2 · Draw layout, duplicate sales and the asset track
- Mystery garage multipliers move beside each pool and apply to single and ten-draws.
- Garage and storage gain fixed batch footers, local selection updates and one-click duplicate-car sales.
- Asset levels become a horizontally browsable 12-level reward track.

## V2.9.3 · Asset grouping and children
- Assets group by city and district with expand and collapse.
- A new Family page supports child naming, preferred positions, growth elixirs and youth intake at 15.

## V2.9.4 · Pregnancy, child training and the intimacy shop
- Pregnancy lasts about 252–301 days; only a birth adds the child to the family.
- Children gain football events at 3, 6, 9 and 12 with position, CA and PA choices.
- The intimacy shop adds protection, toys, a proposal ring and growth elixirs; gifts and elixirs can be used from the backpack.

## V2.9.5 · Family page and native academy write-back
- The family page is rebuilt around parent cards, child cards and profile, growth and academy views.
- Academy placements now use the real club name and write the generated CA, PA and position back to the child.

## V2.9.6 · Outside encounters, adult gate and portrait folders
- The 9-country, 68-city, 388-place travel framework arrives; encounters cost 1 AP and favour real FM women players, with about 30% fictional travellers.
- Family page v3 and the 18+ gate land; intimate actions can require toys and protection.
- 2.9.6 fixes the asset-level read, shows a traveller's profession instead of “free agent”, hides CA/PA for non-players, and reads multiple portrait folders by UID plus a per-folder offset without config.xml.
- R18 adds obedience and two new actions; the three item actions can now conceive.
- The children shop adds the Instant Birth Pill for 1,000,000,000; use it from the backpack on a pregnant NPC to deliver immediately.
- 2.9.6 adds cash gifts whose gain depends on personality, values, bond and reputation; buys missing action points at 50,000,000 each; and makes measurement ranges asymmetric so the midpoint no longer reveals the exact value.

## Compatibility
- Back up the save before any write. Cash gifts and action points are paid from the bank and fail before saving when funds are short.
- Betting, odds and the market remain in-game virtual systems with no real money.`;
  const zh = `> 从 V2.9.0 到 V2.9.6：关系线、资产等级、车库与寄存、子女与青训、外出偶遇、家庭页重做、亲密度、送钱与购买行动力。

## V2.9.1 · 多线关系与批量经营
- 关系按性别分支：朋友、夫妻、闺蜜或兄弟线；迈出第一步后锁定。
- 新增 11 级关系等级与独立关系描述，不再和关系阶段混用。
- 资产等级移到玩家名旁的独立入口；地产、车库与展厅支持一键和批量购买。

## V2.9.2 · 抽卡布局、重复出售与资产战令
- 神秘车库倍率移到卡池标题旁，单抽与十连共用倍率。
- 车库/寄存新增固定批量底栏、局部勾选更新与一键出售重复车辆。
- 资产等级改为可横向浏览的 12 级奖励轨道。

## V2.9.3 · 资产分组与子女
- 资产按城市、城区两级分组，支持单组和全部展开。
- 新增家庭页：子女命名、首选位置、成长仙丹，15 岁后可投放青训。

## V2.9.4 · 十月怀胎、子女培养与情感商店
- 孕期约 252–301 天，只有出生后孩子才进入家庭。
- 子女 3/6/9/12 岁触发足球培养事件，可选择位置、CA 与 PA。
- 情感商店新增防护用品、情趣玩具、求婚戒指与成长仙丹；礼物和仙丹可在背包直接使用。

## V2.9.5 · 家庭页重做与原生青训回写
- 家庭页改为家长卡、子女卡与档案/成长/青训三级视图。
- 青训投放显示真实俱乐部名，并把生成的 CA、PA 与位置回写到子女档案。

## V2.9.6 · 外出偶遇、成人门禁与独立头像源
- 接入 9 国 68 城 388 个地点的外出框架；出门消耗 1 行动力，优先真实 FM 女足球员，约 30% 为虚构旅途中人。
- 家庭页 v3 与 18+ 门禁上线；亲密行为可要求道具与防护。
- 2.9.6 修复资产等级读取；旅途中人显示职业而非「自由球员」，非球员隐藏 CA/PA；头像改为多文件夹、每行独立 UID 偏移，不读取 config.xml。
- R18 新增服从度与两个新行为；情趣之夜、盲眼游戏、骰子之夜均可受孕。
- 子女商店新增「快速分娩丹」，一颗 10 亿；在背包中对正在怀孕的 NPC 使用，立即生产。
- 2.9.6 新增送钱：收益取决于性格、价值观、关系与声望；可按每点 5000 万购买缺失行动力；三围改为非对称模糊范围，中点不再等于精确值。

## 兼容与提醒
- 任何写存档操作前请先备份。送钱和购买行动力从银行扣款，余额不足会在保存前失败。
- 下注、赔率与股市仍为游戏内虚拟玩法，不涉及真实货币。`;
  const zhTW = `> 從 V2.9.0 到 V2.9.6：關係線、資產等級、車庫與寄存、子女與青訓、外出偶遇、家庭頁重做、親密度、送錢與購買行動力。

## V2.9.1 · 多線關係與批量經營
- 關係按性別分支：朋友、夫妻、閨蜜或兄弟線，邁出第一步後鎖定。
- 新增 11 級關係等級與獨立關係描述。
- 資產等級改為獨立入口；地產、車庫與展廳支援一鍵與批量購買。

## V2.9.2 · 抽卡版面、重複出售與資產戰令
- 神秘車庫倍率移到卡池標題旁，單抽與十連共用。
- 車庫／寄存新增固定批量底欄與一鍵出售重複車輛。
- 資產等級改為可橫向瀏覽的 12 級獎勵軌道。

## V2.9.3 · 資產分組與子女
- 資產按城市、城區兩級分組。
- 新增家庭頁：子女命名、首選位置、成長仙丹，15 歲後可投放青訓。

## V2.9.4 · 十月懷胎、子女培養與情感商店
- 孕期約 252–301 天，出生後孩子才進入家庭。
- 子女 3/6/9/12 歲觸發足球培養事件。
- 情感商店新增防護用品、情趣玩具、求婚戒指與成長仙丹。

## V2.9.5 · 家庭頁重做與原生青訓回寫
- 家庭頁改為家長卡、子女卡與檔案／成長／青訓視圖。
- 青訓投放顯示真實俱樂部名，並回寫 CA、PA 與位置。

## V2.9.6 · 外出偶遇、成人門禁與獨立頭像來源
- 接入 9 國 68 城 388 個地點；出門消耗 1 行動力，約 30% 為虛構旅途中人。
- 家庭頁 v3 與 18+ 門禁上線。
- 2.9.6 修復資產等級；旅途中人顯示職業；頭像改為多資料夾、每行獨立 UID 偏移，不讀 config.xml。
- R18 新增服從度與兩個新行為；三個道具行為均可受孕。
- 子女商店新增「快速分娩丹」，一顆 10 億；在背包中對正在懷孕的 NPC 使用，立即生產。
- 2.9.6 新增送錢、按每點 5000 萬購買行動力、非對稱三圍模糊範圍。

## 相容與提醒
- 寫入存檔前請先備份。送錢與購買行動力從銀行扣款，餘額不足會在保存前失敗。
- 下注、賠率與股市仍為遊戲內虛擬玩法。`;
  const ja = `> V2.9.0 から V2.9.6 まで：関係ライン、資産レベル、ガレージと保管、子供とユース、外出、家庭ページ、親密さ、送金と行動力購入。

## V2.9.1 · 関係ラインと一括経営
- 関係が性別ごとのラインに分岐し、最初の一歩で固定。
- 11 段階の関係レベルと関係トーンを追加。
- 資産レベルを独立入口に移し、物件・ガレージ・展示場の一括購入を追加。

## V2.9.2 · 抽選画面、重複売却、資産トラック
- ミステリーガレージの倍率を各池の横へ移動。
- ガレージと保管に固定フッターと重複車の一括売却を追加。
- 資産レベルを横スクロール式の 12 段階報酬トラックに変更。

## V2.9.3 · 資産グループ、子供
- 資産を都市と地区でグループ化。
- 家庭ページを追加し、子供の命名、成長丹、15 歳からのユース投入に対応。

## V2.9.4 · 妊娠、子供育成、親密ショップ
- 妊娠期間は約 252–301 日で、出生後に家庭へ追加。
- 3/6/9/12 歳でサッカー育成イベントが発生。
- 親密ショップに避妊具、玩具、求婚指輪、成長丹を追加。

## V2.9.5 · 家庭ページと青訓書き戻し
- 家庭ページを保護者カード、子供カード、プロフィール／成長／青訓に再構成。
- 青訓で実クラブ名を表示し、CA・PA・ポジションを書き戻し。

## V2.9.6 · 外出、成人ゲート、独立肖像フォルダー
- 9 か国 68 都市 388 地点の外出を追加。1 行動力、約 30% は架空の旅人。
- 家庭ページ v3 と 18+ ゲートを追加。
- 2.9.6 で資産レベルを修正し、旅人の職業を表示。肖像は複数フォルダーと UID オフセットで読み、config.xml は使わない。
- R18 に服従度と 2 つの新行動を追加。3 つの道具行動で妊娠可能。
- 子供ショップに「即時出産丹」を追加。1 個 10 億で、妊娠中の NPC にバッグから使用すると即時に出産します。
- 2.9.6 で送金、1 ポイント 5000 万での行動力購入、非対称の三囲範囲を追加。

## 互換性
- 書き込み前にセーブをバックアップしてください。送金と行動力購入は銀行から引き落とされます。
- 賭け、オッズ、市場はゲーム内の仮想システムです。`;
  const ko = `> V2.9.0 → V2.9.6: 관계 라인, 자산 레벨, 차고와 보관, 자녀와 유스, 외출, 가족 페이지, 친밀도, 송금과 행동력 구매.

## V2.9.1 · 관계 라인과 일괄 경영
- 관계가 성별에 따라 친구·부부·자매·형제 라인으로 분기되고 첫 단계에서 고정됩니다.
- 11단계 관계 레벨과 관계 톤을 추가했습니다.
- 자산 레벨을 별도入口로 옮기고 부동산·차고·전시장 일괄 구매를 추가했습니다.

## V2.9.2 · 뽑기 화면, 중복 판매, 자산 트랙
- 미스터리 차고 배율을 각 풀 옆으로 옮겼습니다.
- 차고와 보관에 고정 하단 바와 중복 차량 일괄 판매를 추가했습니다.
- 자산 레벨을 가로로 넘기는 12단계 보상 트랙으로 바꿨습니다.

## V2.9.3 · 자산 그룹, 자녀
- 자산을 도시와 구역으로 그룹화했습니다.
- 가족 페이지에서 자녀 이름, 성장 단약, 15세 유스 배치를 지원합니다.

## V2.9.4 · 임신, 자녀 육성, 친밀 상점
- 임신 기간은 약 252–301일이며 출생 후 가족에 추가됩니다.
- 3/6/9/12세에 축구 육성 이벤트가 발생합니다.
- 친밀 상점에 피임용품, 장난감, 청혼 반지, 성장 단약을 추가했습니다.

## V2.9.5 · 가족 페이지와 유스 기록
- 가족 페이지를 보호자 카드, 자녀 카드, 프로필/성장/유스 보기로 재구성했습니다.
- 유스 배치에 실제 클럽 이름을 표시하고 CA·PA·포지션을 기록합니다.

## V2.9.6 · 외출, 성인 게이트, 독립 초상화 폴더
- 9개국 68개 도시 388개 장소의 외출을 추가했습니다. 1 행동력, 약 30%는 가상 여행자입니다.
- 가족 페이지 v3와 18+ 게이트를 추가했습니다.
- 2.9.6에서 자산 레벨을 고치고 여행자의 직업을 표시합니다. 초상화는 여러 폴더와 UID 오프셋으로 읽고 config.xml을 사용하지 않습니다.
- R18에 복종도와 두 가지 행동을 추가했고 세 가지 아이템 행동으로 임신할 수 있습니다.
- 자녀 상점에 즉시 출산 단약을 추가했습니다. 1개 10억이며, 임신 중인 NPC에게 가방에서 사용하면 즉시 출산합니다.
- 2.9.6에서 송금, 포인트당 5천만 행동력 구매, 비대칭 신체 치수 범위를 추가했습니다.

## 호환성
- 저장 전에 백업하세요. 송금과 행동력 구매는 은행에서 차감됩니다.
- 배팅, 배당, 시장은 게임 내 가상 시스템입니다.`;
  const de = `> Von V2.9.0 bis V2.9.6: Beziehungslinien, Asset-Level, Garage und Lager, Kinder und Jugend, Ausflüge, Familienseite, Intimität, Geldgeschenke und gekaufte Aktionspunkte.

## V2.9.1 · Beziehungslinien und Batch-Verwaltung
- Beziehungen verzweigen sich nach Geschlecht in Freundschaft, Paar, Schwester- oder Bruderlinie; der erste Schritt fixiert die Linie.
- Elf Beziehungsstufen und ein eigener Beziehungston ersetzen das alte Fortschrittslabel.
- Asset-Level erhält eine eigene Zeitleiste; Immobilien, Garage und Showroom bekommen Ein-Klick- und Batch-Käufe.

## V2.9.2 · Ziehungsansicht, Doppelverkauf und Asset-Track
- Die Multiplikatoren der Mystery-Garage liegen neben jedem Pool.
- Garage und Lager erhalten feste Batch-Fußzeilen und den Verkauf doppelter Fahrzeuge.
- Asset-Level wird zu einem horizontalen 12-Stufen-Belohnungspfad.

## V2.9.3 · Asset-Gruppen und Kinder
- Assets gruppieren sich nach Stadt und Bezirk.
- Die Familienseite unterstützt Namen, Wachstumselixiere und Jugendeinlass ab 15.

## V2.9.4 · Schwangerschaft, Kinderförderung und Intimshop
- Eine Schwangerschaft dauert etwa 252–301 Tage; erst die Geburt fügt das Kind hinzu.
- Fußball-Ereignisse für Kinder mit 3, 6, 9 und 12 Jahren bieten Position, CA und PA.
- Der Intimshop ergänzt Schutz, Spielzeug, einen Heiratsring und Wachstumselixiere.

## V2.9.5 · Familienseite und Jugend-Rückschreibung
- Die Familienseite wird aus Elternkarten, Kinderkarten und Profil-, Wachstums- und Jugendansichten neu aufgebaut.
- Jugendplatzierungen zeigen den echten Vereinsnamen und schreiben CA, PA und Position zurück.

## V2.9.6 · Ausflüge, Adult-Gate und Portraitordner
- Die Reise mit 9 Ländern, 68 Städten und 388 Orten kostet 1 AP; etwa 30 % sind fiktive Reisende.
- Familienseite v3 und das 18+-Gate kommen; intime Aktionen können Spielzeug und Schutz verlangen.
- 2.9.6 korrigiert das Asset-Level, zeigt den Beruf Reisender und verbirgt CA/PA bei Nichtspielern. Portraits lesen mehrere Ordner per UID und eigenem Offset, ohne config.xml.
- R18 ergänzt Gehorsam und zwei neue Aktionen; die drei Gegenstandsaktionen können empfangen.
- Der Kindershop erhält die Sofortgeburt-Pille für 1.000.000.000; im Rucksack bei einer schwangeren NPC einsetzen und sofort entbinden.
- 2.9.6 ergänzt Geldgeschenke, Aktionspunkte für je 50.000.000 und asymmetrische Körpermaßbereiche.

## Kompatibilität
- Vor jedem Schreiben ein Backup anlegen. Geldgeschenke und Aktionspunkte werden von der Bank abgebucht.
- Wetten, Quoten und Markt bleiben virtuelle Spielsysteme.`;
  const es = `> De V2.9.0 a V2.9.6: líneas de relación, niveles de activos, garaje y almacén, hijos y cantera, salidas, página familiar, intimidad, dinero y puntos de acción.

## V2.9.1 · Líneas de relación y gestión por lotes
- Las relaciones se ramifican por género en amistad, pareja, hermandad o línea de amigas; el primer paso fija la línea.
- Once niveles de relación y un tono propio sustituyen la etiqueta única de progreso.
- El nivel de activos pasa a su propia línea temporal; inmuebles, garaje y exposición admiten compra única y por lotes.

## V2.9.2 · Sorteos, venta de duplicados y pista de activos
- Los multiplicadores del garaje misterioso se mueven junto a cada grupo.
- Garaje y almacén añaden pie de acciones fijo y venta de coches duplicados.
- El nivel de activos se convierte en una pista horizontal de 12 niveles.

## V2.9.3 · Grupos de activos e hijos
- Los activos se agrupan por ciudad y distrito.
- La página familiar permite nombrar hijos, usar elixires de crecimiento e ingresar en la cantera a los 15.

## V2.9.4 · Embarazo, formación infantil y tienda íntima
- El embarazo dura unos 252–301 días; solo el nacimiento añade al hijo.
- A los 3, 6, 9 y 12 años hay eventos de fútbol con posición, CA y PA.
- La tienda íntima añade protección, juguetes, anillo de compromiso y elixires.

## V2.9.5 · Página familiar y escritura de cantera
- La página familiar se reconstruye con tarjetas de padres e hijos y vistas de perfil, crecimiento y cantera.
- La cantera muestra el club real y escribe CA, PA y posición en el hijo.

## V2.9.6 · Salidas, puerta adulta y carpetas de retratos
- Llega el viaje de 9 países, 68 ciudades y 388 lugares; cuesta 1 AP y cerca del 30 % son viajeros ficticios.
- Llegan la página familiar v3 y la puerta 18+; las acciones íntimas pueden pedir juguetes y protección.
- 2.9.6 corrige el nivel de activos, muestra la profesión del viajero y oculta CA/PA a no jugadores. Los retratos leen varias carpetas por UID y desplazamiento propio, sin config.xml.
- R18 añade obediencia y dos acciones; las tres acciones con objeto pueden concebir.
- La tienda infantil añade la píldora de parto inmediato por 1.000.000.000; úsala desde la mochila en una NPC embarazada para dar a luz al instante.
- 2.9.6 añade dinero, puntos de acción a 50.000.000 cada uno y rangos asimétricos de medidas.

## Compatibilidad
- Haz una copia antes de escribir. El dinero y los puntos se pagan desde el banco.
- Apuestas, cuotas y mercado siguen siendo sistemas virtuales.`;
  const fr = `> De V2.9.0 à V2.9.6 : lignes de relation, niveaux d’actifs, garage et stockage, enfants et centre de formation, sorties, page famille, intimité, argent et points d’action.

## V2.9.1 · Lignes de relation et gestion par lots
- Les relations se divisent selon le genre : ami, couple, sœur ou frère ; le premier pas verrouille la ligne.
- Onze niveaux de relation et un ton distinct remplacent l’ancien libellé unique.
- Le niveau d’actifs a sa propre chronologie ; biens, garage et showroom gagnent l’achat en un clic et par lots.

## V2.9.2 · Tirages, vente des doublons et piste d’actifs
- Les multiplicateurs du garage mystère passent à côté de chaque pool.
- Garage et stockage ajoutent un pied d’actions fixe et la vente des voitures en double.
- Le niveau d’actifs devient une piste horizontale de 12 niveaux.

## V2.9.3 · Groupes d’actifs et enfants
- Les actifs se regroupent par ville et quartier.
- La page famille permet de nommer les enfants, d’utiliser des élixirs et d’entrer au centre à 15 ans.

## V2.9.4 · Grossesse, formation des enfants et boutique intime
- La grossesse dure environ 252–301 jours ; seule la naissance ajoute l’enfant.
- Des événements football à 3, 6, 9 et 12 ans proposent poste, CA et PA.
- La boutique intime ajoute protection, jouets, bague de fiançailles et élixirs.

## V2.9.5 · Page famille et écriture du centre
- La page famille est refaite avec cartes parents, cartes enfants et vues profil, croissance et centre.
- Le centre affiche le vrai club et réécrit CA, PA et poste chez l’enfant.

## V2.9.6 · Sorties, contrôle adulte et dossiers de portraits
- Le voyage de 9 pays, 68 villes et 388 lieux coûte 1 PA ; environ 30 % sont des voyageurs fictifs.
- La page famille v3 et le contrôle 18+ arrivent ; les actions intimes peuvent exiger jouets et protection.
- 2.9.6 corrige le niveau d’actifs, affiche le métier des voyageurs et masque CA/PA des non-joueurs. Les portraits lisent plusieurs dossiers par UID et décalage, sans config.xml.
- R18 ajoute l’obéissance et deux actions ; les trois actions à objet peuvent concevoir.
- La boutique enfant ajoute la pilule d’accouchement immédiat à 1 000 000 000 ; utilisez-la depuis le sac sur une PNJ enceinte pour accoucher aussitôt.
- 2.9.6 ajoute l’argent, les points d’action à 50 000 000 chacun et des plages de mesures asymétriques.

## Compatibilité
- Sauvegardez avant toute écriture. L’argent et les points sont débités de la banque.
- Paris, cotes et marché restent des systèmes virtuels.`;
  const ru = `> С V2.9.0 по V2.9.6: линии отношений, уровни активов, гараж и хранение, дети и академия, выезды, семейная страница, близость, деньги и очки действий.

## V2.9.1 · Линии отношений и пакетное управление
- Отношения делятся по полу на дружбу, пару, сестринскую или братскую линию; первый шаг фиксирует линию.
- Добавлены 11 уровней отношений и отдельный тон отношений.
- Уровень активов получил отдельную шкалу; недвижимость, гараж и салон покупаются одним нажатием и пакетно.

## V2.9.2 · Розыгрыши, продажа дублей и шкала активов
- Множители тайного гаража перенесены к каждому пулу.
- Гараж и хранение получили фиксированную панель и продажу дублей.
- Уровень активов стал горизонтальной шкалой из 12 наград.

## V2.9.3 · Группы активов и дети
- Активы группируются по городу и району.
- Семейная страница поддерживает имена детей, эликсиры роста и академию с 15 лет.

## V2.9.4 · Беременность, развитие детей и интимный магазин
- Беременность длится около 252–301 дня; ребёнок появляется только после рождения.
- В 3, 6, 9 и 12 лет происходят футбольные события с позицией, CA и PA.
- В интимном магазине появились защита, игрушки, кольцо и эликсиры.

## V2.9.5 · Семейная страница и запись академии
- Семейная страница перестроена: карточки родителей и детей, профиль, рост и академия.
- Академия показывает реальный клуб и записывает CA, PA и позицию ребёнка.

## V2.9.6 · Выезды, взрослый режим и папки портретов
- Путешествия по 9 странам, 68 городам и 388 местам стоят 1 ОД; около 30% — вымышленные путешественники.
- Появились семейная страница v3 и режим 18+; интимные действия могут требовать игрушки и защиту.
- 2.9.6 исправляет уровень активов, показывает профессию путешественника и скрывает CA/PA у не-игроков. Портреты читаются из нескольких папок по UID и смещению без config.xml.
- R18 добавляет послушание и два действия; три действия с предметами могут привести к зачатию.
- В детском магазине появилась пилюля мгновенных родов за 1 000 000 000; используйте её из рюкзака на беременной NPC, чтобы сразу родить.
- 2.9.6 добавляет деньги, очки действий по 50 000 000 и асимметричные диапазоны мерок.

## Совместимость
- Перед записью сделайте резервную копию. Деньги и очки списываются с банка.
- Ставки, коэффициенты и рынок остаются виртуальными.`;
  const ptBR = `> Da V2.9.0 à V2.9.6: linhas de relacionamento, níveis de patrimônio, garagem e armazenamento, filhos e base, saídas, página da família, intimidade, dinheiro e pontos de ação.

## V2.9.1 · Linhas de relacionamento e gestão em lote
- Os relacionamentos se dividem por gênero em amizade, casal, irmãs ou irmãos; o primeiro passo fixa a linha.
- Onze níveis de relacionamento e um tom próprio substituem o rótulo antigo.
- O nível de patrimônio ganha linha própria; imóveis, garagem e showroom têm compra única e em lote.

## V2.9.2 · Sorteios, venda de duplicados e trilha de patrimônio
- Os multiplicadores da garagem misteriosa vão para o lado de cada pool.
- Garagem e armazenamento ganham rodapé fixo e venda de carros duplicados.
- O nível de patrimônio vira uma trilha horizontal de 12 níveis.

## V2.9.3 · Grupos de patrimônio e filhos
- O patrimônio é agrupado por cidade e distrito.
- A página da família permite nomear filhos, usar elixires e entrar na base aos 15.

## V2.9.4 · Gravidez, formação dos filhos e loja íntima
- A gravidez dura cerca de 252–301 dias; só o nascimento adiciona o filho.
- Aos 3, 6, 9 e 12 anos há eventos de futebol com posição, CA e PA.
- A loja íntima adiciona proteção, brinquedos, anel de noivado e elixires.

## V2.9.5 · Página da família e gravação da base
- A página da família é refeita com cartões de pais e filhos e visões de perfil, crescimento e base.
- A base mostra o clube real e grava CA, PA e posição no filho.

## V2.9.6 · Saídas, porte adulto e pastas de retratos
- Chega a viagem de 9 países, 68 cidades e 388 locais; custa 1 PA e cerca de 30% são viajantes fictícios.
- Chegam a página da família v3 e o porte 18+; ações íntimas podem exigir brinquedos e proteção.
- 2.9.6 corrige o nível de patrimônio, mostra a profissão do viajante e esconde CA/PA de não jogadores. Retratos leem várias pastas por UID e deslocamento, sem config.xml.
- R18 adiciona obediência e duas ações; as três ações com item podem conceber.
- A loja infantil adiciona a pílula de parto imediato por 1.000.000.000; use-a na mochila em uma NPC grávida para dar à luz na hora.
- 2.9.6 adiciona dinheiro, pontos de ação a 50.000.000 cada e faixas assimétricas de medidas.

## Compatibilidade
- Faça backup antes de escrever. Dinheiro e pontos saem do banco.
- Apostas, odds e mercado continuam virtuais.`;
  const ptPT = ptBR.replace("Da V2.9.0 à V2.9.6", "Da V2.9.0 até à V2.9.6").replace("você", "você");
  const messages = {
    "en-GB": {"announce.entry.v296_update.title": title["en-GB"], "announce.entry.v296_update.body": en},
    "zh-CN": {"announce.entry.v296_update.title": title["zh-CN"], "announce.entry.v296_update.body": zh},
    "zh-TW": {"announce.entry.v296_update.title": title["zh-TW"], "announce.entry.v296_update.body": zhTW},
    "ko-KR": {"announce.entry.v296_update.title": title["ko-KR"], "announce.entry.v296_update.body": ko},
    "de-DE": {"announce.entry.v296_update.title": title["de-DE"], "announce.entry.v296_update.body": de},
    "es-ES": {"announce.entry.v296_update.title": title["es-ES"], "announce.entry.v296_update.body": es},
    "fr-FR": {"announce.entry.v296_update.title": title["fr-FR"], "announce.entry.v296_update.body": fr},
    "ru-RU": {"announce.entry.v296_update.title": title["ru-RU"], "announce.entry.v296_update.body": ru},
    "ja-JP": {"announce.entry.v296_update.title": title["ja-JP"], "announce.entry.v296_update.body": ja},
    "pt-BR": {"announce.entry.v296_update.title": title["pt-BR"], "announce.entry.v296_update.body": ptBR},
    "pt-PT": {"announce.entry.v296_update.title": title["pt-PT"], "announce.entry.v296_update.body": ptPT},
  };
  modules.push({messages});
})();
