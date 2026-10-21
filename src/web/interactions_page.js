/* FMSDD People workspace. Relationship outcomes and asset transfers stay server-owned. */
(() => {
  "use strict";

  const bridge = () => window.FMSDDLifeBridge;
  const t = (key, parameters = {}) => bridge()?.uiText(key, parameters) || key;
  const translated = (key, parameters = {}) => {
    const value = t(key, parameters);
    return value && value !== key ? value : "";
  };
  const esc = (value) => {
    if (bridge()?.escapeHtml) return bridge().escapeHtml(String(value ?? ""));
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
  };
  const fullMoney = (value) => bridge()?.formatFullMoney(Number(value) || 0) || String(Number(value) || 0);
  const compactMoney = (value) => (
    bridge()?.formatCompactMoney?.(Number(value) || 0, 1)
    || bridge()?.formatMoney?.(Number(value) || 0)
    || fullMoney(value)
  );
  const percent = (value, digits = 0) => `${(Number(value || 0) * 100).toFixed(digits)}%`;
  const AP = () => t("life.interactions.ap.short");

  const DIMENSIONS = Object.freeze([
    ["familiarity", "life.interactions.dimension.familiarity", "familiarity"],
    ["affection", "life.interactions.dimension.affection", "affection"],
    ["trust", "life.interactions.dimension.trust", "trust"],
    ["attraction", "life.interactions.dimension.attraction", "attraction"],
    ["respect", "life.interactions.dimension.respect", "respect"],
  ]);
  const SOCIAL_KEYS = Object.freeze({
    acquaintance: "acquaintance", friend: "friend",
    close_friend: "close_friend", confidant: "confidant",
  });
  const ROMANCE_KEYS = Object.freeze({
    ambiguous: "ambiguous", partner: "partner", spouse: "spouse",
  });
  const GIFT_CATEGORY_KEYS = Object.freeze({
    book: "book", fashion: "fashion", technology: "technology", food: "food",
    sport: "sport", music: "music", art: "art", luxury: "luxury",
  });
  const TIMELINE_KEYS = Object.freeze({
    chat: "chat", gift: "gift", date: "date", relationship: "relationship",
    residence: "residence", asset_gift: "asset_gift", intimacy: "intimacy",
    event: "event",
  });
  const TABS = Object.freeze([
    ["overview", "life.interactions.tabs.overview", "layout-dashboard"],
    ["people", "life.interactions.tabs.people", "heart-handshake"],
    ["travel", "life.interactions.tabs.travel", "plane"],
    ["search", "life.interactions.tabs.search", "user-round-search"],
    ["assets", "life.interactions.tabs.assets", "landmark"],
    ["family", "life.interactions.tabs.family", "baby"],
    ["timeline", "life.interactions.tabs.timeline", "history"],
  ]);

  const state = {
    data: null, loading: false, error: "", scope: "", selectedId: 0,
    tab: "overview", peopleTab: "dossier", interactionTab: "home", assetsTab: "residence",
    timelineAll: false, searchResults: null, searchQuery: "", searchGender: "all",
    searchNationalityId: 0, searchMinAge: "", searchMaxAge: "",
    searchClubId: 0, searchClubName: "", searchClubQuery: "",
    searchClubOptions: [], searchNationalities: [], searchTotal: null,
    travelCatalog: null, travelLoading: false, travelCountry: "", travelCity: "",
    travelPlace: "", travelBusy: false, travelCityLimit: 9,
    searchPage: 1, searchPageCount: 0, searchPageSize: 30,
    searchBusy: false, searchClubBusy: false, requestBusy: false, bound: false,
    claimLevel: 0, claimError: "", childBusy: "", familyParentId: 0, familyChildId: "",
    familySection: "children", familyChildView: "profile",
    giftItemId: "", dateActivityId: "", chatTopic: "",
    intimacyTab: "actions",
    giftPropertyCity: "", giftPropertyDistrict: "", giftPropertyKind: "",
    giftPropertyExpandAll: null, giftPropertyExpanded: new Set(),
    giftVehicleBrand: "", giftVehicleClass: "", giftVehicleRarity: "",
    giftVehicleExpandAll: null, giftVehicleExpanded: new Set(),
    residenceSelectionPerson: 0, residenceSelectionId: "",
    eventId: "", dismissedEventIds: new Set(),
  };

  function pageRoot() { return document.getElementById("page-life-interactions"); }
  function profileDialog() { return document.getElementById("life-interactions-profile-dialog"); }
  function resultDialog() { return document.getElementById("life-interactions-result-dialog"); }
  function chatDialog() { return document.getElementById("life-interactions-chat-dialog"); }
  function giftDialog() { return document.getElementById("life-interactions-gift-dialog"); }
  function dateDialog() { return document.getElementById("life-interactions-date-dialog"); }
  function eventDialog() { return document.getElementById("life-interactions-event-dialog"); }
  function assetLevelDialog() { return document.getElementById("life-interactions-asset-level-dialog"); }

  function affectionTone(value) {
    const score = Math.max(0, Math.min(100, Number(value || 0)));
    if (score >= 80) return "devoted";
    if (score >= 60) return "close";
    if (score >= 40) return "warm";
    if (score >= 20) return "guarded";
    return "distant";
  }

  function initials(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return Array.from(parts[0]).slice(0, 2).join("").toUpperCase();
    return `${Array.from(parts[0])[0] || ""}${Array.from(parts[parts.length - 1])[0] || ""}`.toUpperCase();
  }

  function currentThemeLocale() {
    return String(
      bridge()?.getState?.()?.settings?.ui_locale
      || window.FMODDI18n?.locale
      || "en-GB"
    );
  }

  function placeName(record, chineseKey = "name_zh", englishKey = "name_en") {
    const locale = currentThemeLocale();
    return locale === "zh-CN" || locale === "zh-TW"
      ? String(record?.[chineseKey] || record?.[englishKey] || "")
      : String(record?.[englishKey] || record?.[chineseKey] || "");
  }

  function assetGiftName(record, fallback = "") {
    return placeName(record, "asset_name_zh", "asset_name_en")
      || String(record?.asset_name || fallback || "");
  }

  function formatGameDay(value) {
    const ordinal = Number(value || 0);
    if (!Number.isFinite(ordinal) || ordinal < 719163) return "";
    try {
      return new Intl.DateTimeFormat(currentThemeLocale(), {
        year: "numeric", month: "short", day: "2-digit",
      }).format(new Date((ordinal - 719163) * 86400000 + 43200000));
    } catch (_error) {
      return String(value || "");
    }
  }

  function portraitEnabled() {
    return bridge()?.getState?.()?.settings?.interaction_portraits_enabled !== false;
  }

  function portraitMarkup(person, {small = false} = {}) {
    const name = String(person?.name || "");
    const uid = Number(person?.id || person?.uid || 0);
    const fallback = `<span class="interaction-avatar-fallback">${esc(initials(name))}</span>`;
    const className = `interaction-avatar${small ? " small" : ""}`;
    if (!uid || !portraitEnabled()) return `<span class="${className}">${fallback}</span>`;
    const offset = Number(bridge()?.getState?.()?.settings?.portrait_uid_offset || 0);
    return `<span class="${className} has-portrait"><img src="/api/player-avatar?player_id=${uid}&amp;portrait_offset=${offset}" alt="" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false">${fallback.replace('class="interaction-avatar-fallback"', 'class="interaction-avatar-fallback" hidden')}</span>`;
  }

  function selectedRow() {
    return rowFor(state.selectedId);
  }

  function rowFor(personId) {
    if (!state.data) return null;
    return (state.data.relationships || []).find(
      (row) => Number(row.person?.id || 0) === Number(personId || 0),
    ) || null;
  }

  function applyData(data, selectedId = 0) {
    state.data = data || null;
    state.error = "";
    state.scope = String(data?.scope_id || bridge()?.getState?.()?.data_scope_id || "");
    const requested = Number(selectedId || data?.selected_person_id || state.selectedId || 0);
    const relationships = Array.isArray(data?.relationships) ? data.relationships : [];
    state.selectedId = relationships.some((row) => Number(row.person?.id || 0) === requested)
      ? requested : Number(relationships[0]?.person?.id || 0);
  }

  async function requestJson(path, options = {}) { return bridge().request(path, options); }
  async function postJson(path, body) {
    return requestJson(path, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body || {}),
    });
  }

  async function loadInteractions({announce = false} = {}) {
    if (state.loading) return;
    state.loading = true;
    state.error = "";
    paintWorkspace();
    try {
      const response = await requestJson("/api/life/interactions");
      applyData(response);
      if (announce) bridge()?.toast(t("life.interactions.loaded"));
    } catch (error) {
      state.error = String(error?.message || error || t("life.interactions.error"));
    } finally {
      state.loading = false;
      paintWorkspace();
    }
  }

  function stageBadge(relationship) {
    const badges = [];
    const level = String(relationship?.level || "");
    if (level) {
      const levelClass = ["friend"].includes(level) ? "friend"
        : ["close_friend"].includes(level) ? "close"
          : ["ambiguous", "couple", "spouse"].includes(level) ? "partner" : "friend";
      badges.push(`<span class="interaction-badge ${levelClass}">${esc(levelLabel(level))}</span>`);
    } else {
      const social = String(relationship?.social_stage || "acquaintance");
      const socialClass = social === "friend" ? "friend" : social === "close_friend" ? "close" : "acquaintance";
      badges.push(`<span class="interaction-badge ${socialClass}">${esc(t(`life.interactions.social.${SOCIAL_KEYS[social] || "acquaintance"}`))}</span>`);
    }
    if (relationship?.secret_lover) {
      badges.push(`<span class="interaction-badge secret">${esc(t("life.interactions.romance.secret_lover"))}</span>`);
    }
    const tone = String(relationship?.tone?.key || "");
    if (tone) {
      badges.push(`<span class="interaction-badge tone">${esc(toneLabel(tone))}</span>`);
    }
    return badges.join("");
  }

  function relationshipStatusChips(relationship) {
    const chips = [];
    const risk = Number(relationship?.secret_risk || 0);
    const threshold = Number(relationship?.secret_exposure_threshold || 0);
    if (relationship?.secret_lover && risk > 0 && threshold > 0) {
      chips.push(`<span class="interaction-badge secret"><i data-lucide="eye"></i>${esc(t("life.interactions.relationship.secret_risk", {value: Math.round(risk), threshold: Math.round(threshold)}))}</span>`);
    }
    if (String(relationship?.pregnancy?.status || "") === "expecting") {
      const pregnancy = relationship.pregnancy;
      const days = Math.max(0, Number(pregnancy.days_remaining || 0));
      const early = Number(pregnancy.due_early || 0);
      const late = Number(pregnancy.due_late || 0);
      const label = pregnancy.revealed === false
        ? t("life.interactions.relationship.pregnancy_maybe")
        : early && late
          ? t("life.interactions.relationship.pregnancy_range", {
            early: formatGameDay(early), late: formatGameDay(late),
          })
          : t("life.interactions.relationship.pregnancy_possible", {days});
      chips.push(`<span class="interaction-badge partner"><i data-lucide="sprout"></i>${esc(label)}</span>`);
    }
    return chips.join("");
  }

  function isIntimateRelationship(relationship) {
    if (!relationship) return false;
    if (relationship.is_intimate === true) return true;
    const stage = String(relationship.effective_romance_stage || relationship.romance_stage || "none");
    return ["partner", "spouse"].includes(stage)
      || (stage === "ambiguous" && Boolean(relationship.secret_lover));
  }

  function intimacyActionLabel(action) {
    return t(`life.interactions.intimacy.action.${String(action || "")}.title`);
  }

  function intimacyBandLabel(band) {
    return t(`life.interactions.intimacy.band.${String(band || "new")}`);
  }

  function preferenceChips(relationship) {
    const preferences = relationship?.preferences || {};
    const chips = [];
    if (preferences.gift_known && preferences.gift) {
      chips.push(t("life.interactions.preference.gift_known", {
        value: t(`life.interactions.gift_category.${GIFT_CATEGORY_KEYS[preferences.gift] || "luxury"}`),
      }));
    }
    if (preferences.disliked_gift_known && preferences.disliked_gift) {
      chips.push(t("life.interactions.preference.disliked", {
        value: t(`life.interactions.gift_category.${GIFT_CATEGORY_KEYS[preferences.disliked_gift] || "luxury"}`),
      }));
    }
    if (preferences.activity_known && preferences.activity) {
      chips.push(t("life.interactions.preference.activity_known", {
        value: t(`life.interactions.activity.${preferences.activity}`),
      }));
    }
    if (preferences.topic_known && preferences.topic) {
      chips.push(t("life.interactions.preference.topic_known", {
        value: t(`life.interactions.topic.${preferences.topic}`),
      }));
    }
    if (!chips.length) chips.push(t("life.interactions.preference.gift_hint"));
    return chips.map((chip) => `<span>${esc(chip)}</span>`).join("");
  }

  function actionPointsReady(data, cost = 0) {
    return Number(data?.action_points?.current || 0) >= Number(cost || 0);
  }

  function tabCounts(data) {
    return {
      overview: Number(data.summary?.people || 0),
      people: Number(data.summary?.relationships || 0),
      search: Array.isArray(state.searchResults) ? state.searchResults.length : 0,
      assets: Number(data.assets?.properties?.length || 0) + Number(data.assets?.vehicles?.length || 0),
      timeline: Array.isArray(data.timeline) ? data.timeline.length : 0,
    };
  }

  function relationshipNetworkGroups(data) {
    const definitions = [
      ["spouse", "life.interactions.level.spouse", "heart", (row) => String(row.relationship?.level || row.relationship?.romance_stage || "") === "spouse"],
      ["couple", "life.interactions.level.couple", "heart-handshake", (row) => String(row.relationship?.level || row.relationship?.romance_stage || "") === "couple"],
      ["ambiguous", "life.interactions.level.ambiguous", "sparkles", (row) => String(row.relationship?.level || row.relationship?.romance_stage || "") === "ambiguous"],
      ["secret_lover", "life.interactions.romance.secret_lover", "venetian-mask", (row) => Boolean(row.relationship?.secret_lover)],
      ["best_friend", "life.interactions.level.best_friend", "users-round", (row) => String(row.relationship?.level || "") === "best_friend"],
      ["sworn_brother", "life.interactions.level.sworn_brother", "shield", (row) => String(row.relationship?.level || "") === "sworn_brother"],
      ["brother", "life.interactions.level.brother", "handshake", (row) => String(row.relationship?.level || "") === "brother"],
      ["kindred", "life.interactions.level.kindred", "user-round-check", (row) => String(row.relationship?.level || "") === "kindred"],
      ["partner", "life.interactions.level.partner", "users", (row) => String(row.relationship?.level || "") === "partner"],
      ["close_friend", "life.interactions.level.close_friend", "users-round", (row) => String(row.relationship?.level || "") === "close_friend"],
      ["friend", "life.interactions.level.friend", "user-round-check", (row) => String(row.relationship?.level || "") === "friend"],
      ["acquaintance", "life.interactions.level.acquaintance", "user-round", (row) => String(row.relationship?.level || "") === "acquaintance"],
    ];
    const claimed = new Set();
    const rows = Array.isArray(data.relationships) ? data.relationships : [];
    return definitions.map(([key, labelKey, icon, predicate]) => {
      const members = rows.filter((row) => {
        const id = Number(row.person?.id || 0);
        if (!id || claimed.has(id) || !predicate(row)) return false;
        claimed.add(id);
        return true;
      });
      return {key, labelKey, icon, members};
    });
  }

  function renderRelationshipNetwork(data) {
    const groups = relationshipNetworkGroups(data);
    const total = groups.reduce((sum, group) => sum + group.members.length, 0);
    return `<section class="interaction-panel interaction-network-card">
      <header class="interaction-panel-head"><div><h2>${esc(t("life.interactions.network.title"))}</h2><p>${esc(t("life.interactions.network.detail"))}</p></div><span class="interaction-badge">${esc(t("life.interactions.network.members", {count: total}))}</span></header>
      <div class="interaction-panel-body">${total ? `<div class="interaction-network-grid">${groups.map((group) => `<article class="interaction-network-lane tone-${group.key}"><header><span><i data-lucide="${group.icon}"></i><strong>${esc(t(group.labelKey))}</strong></span><b>${group.members.length}</b></header><div class="interaction-network-members">${group.members.map((row) => `<button type="button" class="interaction-network-person" data-interaction-person-select="${Number(row.person?.id || 0)}" data-interaction-open-dossier title="${esc(t("life.interactions.network.open", {name: row.person?.name || ""}))}">${portraitMarkup(row.person, {small: true})}<span><strong>${esc(row.person?.name || "")}</strong><small>${esc(row.person?.team_name || t("life.interactions.free_agent"))}</small></span></button>`).join("") || `<span class="interaction-network-none">—</span>`}</div></article>`).join("")}</div><small class="interaction-network-legend"><i data-lucide="mouse-pointer-click"></i>${esc(t("life.interactions.network.legend"))}</small>` : `<div class="interaction-empty compact"><i data-lucide="network"></i><span>${esc(t("life.interactions.network.empty"))}</span></div>`}</div>
    </section>`;
  }

  function elixirName(tier) {
    const row = tier || {};
    const key = String(row.id || row.tier || "");
    const label = translated(`life.interactions.family.elixir_name.${key}`);
    if (label) return label;
    const locale = String(bridge()?.getState?.()?.settings?.ui_locale || "").toLowerCase();
    const zh = locale.startsWith("zh");
    return String(zh ? (row.name_zh || row.name_en || key) : (row.name_en || row.name_zh || key));
  }

  function familyMoney(value) {
    const format = bridge()?.formatMoney;
    return typeof format === "function" ? format(Number(value || 0)) : `${Number(value || 0).toLocaleString()}`;
  }

  function childMilestoneRows(child) {
    const age = Number(child.age || 0);
    const completed = new Set((child.training_milestones || []).map(Number));
    const neglected = new Set((child.neglected_milestones || []).map(Number));
    const history = new Map((child.training_history || []).map((row) => [Number(row.age || 0), row]));
    return [3, 6, 9, 12].map((milestone) => {
      let status = "upcoming";
      if (history.has(milestone) || completed.has(milestone)) status = "done";
      else if (neglected.has(milestone)) status = "missed";
      else if (age >= milestone) status = "due";
      return {age: milestone, status, row: history.get(milestone) || null};
    });
  }

  function childMilestoneLabel(row) {
    if (row.status === "done") {
      const option = row.row?.option || "";
      const label = option ? eventOptionLabel("child_football", option) : t("life.interactions.family.milestone_done");
      return row.row ? `${label} · CA ${Number(row.row.ca || 0)}` : label;
    }
    if (row.status === "missed") return t("life.interactions.family.milestone_missed");
    if (row.status === "due") return t("life.interactions.family.milestone_due");
    return t("life.interactions.family.milestone_locked");
  }

  function parentRelationshipRow(parentId) {
    const rows = Array.isArray(state.data?.relationships) ? state.data.relationships : [];
    return rows.find((row) => Number(row.person?.id || 0) === Number(parentId || 0)) || null;
  }

  function parentRelationMeta(parentId) {
    const relationship = parentRelationshipRow(parentId)?.relationship || {};
    if (relationship.secret_lover) {
      return { label: t("life.interactions.romance.secret_lover"), tone: "secret" };
    }
    const stage = String(relationship.effective_romance_stage || relationship.romance_stage || "");
    if (stage === "spouse") return { label: t("life.interactions.romance.spouse"), tone: "spouse" };
    if (stage === "partner") return { label: t("life.interactions.romance.partner"), tone: "partner" };
    if (stage === "ambiguous") return { label: t("life.interactions.romance.ambiguous"), tone: "ambiguous" };
    return { label: t("life.interactions.family.parent"), tone: "family" };
  }

  function relationBadge(parentId) {
    const meta = parentRelationMeta(parentId);
    return `<span class="interaction-relation-badge is-${meta.tone}">${esc(meta.label)}</span>`;
  }

  function childStatusMeta(child) {
    const placement = child.placement || {};
    const status = String(placement.status || "");
    const team = placementTeamName(placement);
    if (status === "trial_passed") {
      return { label: t("life.interactions.family.trial_done"), tone: "trial" };
    }
    if (status === "playing" || status === "applied") {
      return {
        label: status === "playing"
          ? t("life.interactions.family.placement.playing", { team })
          : t("life.interactions.family.placement.applied", { team }),
        tone: "playing",
      };
    }
    if (status === "armed" || status === "pending" || status === "recommended") {
      return {
        label: t(`life.interactions.family.placement.${status}`, { team }),
        tone: "queued",
      };
    }
    if (status === "rejected" || status === "cancelled") {
      return {
        label: t("life.interactions.family.placement.rejected", { team }),
        tone: "rejected",
      };
    }
    if (Number(child.age || 0) >= Number(child.adult_age || 15)) {
      return { label: t("life.interactions.family.academy_ready"), tone: "ready" };
    }
    return {
      label: t("life.interactions.family.grow_note", {
        years: Math.max(0, Number(child.adult_age || 15) - Number(child.age || 0)),
      }),
      tone: "growing",
    };
  }

  function placementTeamName(placement) {
    const teamId = Number(placement?.team_id || 0);
    const raw = String(placement?.team_name || "").trim();
    if (raw && !/^\d+$/.test(raw)) return raw;
    const clubs = recommendableClubs();
    const club = clubs.find((row) => Number(row.team_id || row.id || 0) === teamId);
    if (club && String(club.name || "").trim()) return String(club.name);
    const fallback = t("life.interactions.family.club_unknown");
    return raw ? `${fallback} #${raw.slice(-4)}` : fallback;
  }

  function milestoneSteps(child) {
    return `<div class="interaction-child-steps">${childMilestoneRows(child).map((row) => {
      const title = row.row
        ? eventOptionLabel("child_football", String(row.row.option || ""))
        : childMilestoneLabel(row);
      const note = row.row
        ? `CA ${Number(row.row.ca || 0)} · PA ${Number(row.row.pa || 0)}`
        : childMilestoneLabel(row);
      const icon = row.status === "done" ? "check"
        : row.status === "missed" ? "x"
          : row.status === "due" ? "sparkles" : "lock";
      return `<div class="interaction-child-step is-${row.status}">
        <span class="interaction-child-step-mark"><i data-lucide="${icon}"></i></span>
        <div class="interaction-child-step-copy"><strong>${row.age}</strong><span>${esc(title)}</span><small>${esc(note)}</small></div>
      </div>`;
    }).join("")}</div>`;
  }

  function familyChild(detail) {
    const child = detail || {};
    const placement = child.placement || {};
    const age = Number(child.age || 0);
    const adultAge = Number(child.adult_age || 15);
    const name = String(child.name || "").trim();
    const busy = state.childBusy === String(child.id || "");
    const status = childStatusMeta(child);
    const milestones = childMilestoneRows(child);
    const next = milestones.find((row) => row.status === "due")
      || milestones.find((row) => row.status === "upcoming")
      || null;
    const displayCa = Number(placement.ca || child.ca || 0);
    const displayPa = Number(placement.pa || child.pa || 0);
    const displayPosition = String(
      placement.position || child.football_position || child.preferred_position || "",
    );
    const growthEvent = child.growth_event || null;
    const growthEventCta = growthEvent
      ? `<button type="button" class="interaction-child-event-cta" data-interaction-event="${esc(growthEvent.id)}"><span class="interaction-child-event-icon"><i data-lucide="sparkles"></i></span><span><strong>${esc(t("life.interactions.family.growth_event"))}</strong><small>${esc(t("life.interactions.family.growth_event_hint", { age: Number(growthEvent.data?.milestone || age) }))}</small></span><i data-lucide="chevron-right"></i></button>`
      : "";
    const history = (child.training_history || []).slice().reverse().map((row) => `<div class="interaction-child-history-row"><span>${esc(t("life.interactions.family.training_age", { age: Number(row.age || 0) }))}</span><strong>${esc(eventOptionLabel("child_football", String(row.option || "")))}</strong><small>CA ${Number(row.ca || 0)} · PA ${Number(row.pa || 0)}${row.position ? ` · ${esc(row.position)}` : ""}</small></div>`).join("");
    const renameLocked = name && age >= adultAge;
    const renameButton = name
      ? `<button type="button" class="interaction-child-rename" data-interaction-action="rename-child" data-child-id="${esc(child.id)}" ${busy || renameLocked ? "disabled" : ""} title="${esc(renameLocked ? t("life.interactions.family.rename_locked") : t("life.interactions.family.rename_hint"))}"><i data-lucide="${renameLocked ? "lock" : "pencil-line"}"></i><span>${esc(renameLocked ? t("life.interactions.family.rename_locked") : t("life.interactions.family.rename"))}</span></button>`
      : "";
    const nameForm = name
      ? ""
      : `<form class="interaction-child-name-form" data-child-name-form data-child-id="${esc(child.id)}"><label><span>${esc(t("life.interactions.family.name_label"))}</span><input type="text" name="child_name" maxlength="${Number(state.data?.children_rules?.name_max_length || 40)}" placeholder="${esc(t("life.interactions.family.name_placeholder"))}" required></label><label><span>${esc(t("life.interactions.family.position_label"))}</span><select name="child_position"><option value="">${esc(t("life.interactions.family.position_any"))}</option>${(state.data?.children_rules?.positions || []).map((row) => `<option value="${esc(row)}">${esc(row)}</option>`).join("")}</select></label><button type="submit" class="interaction-gold-button" ${busy ? "disabled" : ""}><i data-lucide="check"></i>${esc(t("life.interactions.family.name_save"))}</button></form>`;
    const elixirs = Array.isArray(state.data?.children_rules?.elixirs) ? state.data.children_rules.elixirs : [];
    const elixirButtons = name && age < adultAge
      ? `<div class="interaction-child-elixirs">${elixirs.map((tier) => `<button type="button" class="interaction-elixir" data-interaction-action="child-elixir" data-child-id="${esc(child.id)}" data-tier="${esc(tier.id)}" ${busy ? "disabled" : ""}><i data-lucide="flask-conical"></i><span>${esc(elixirName(tier))}</span><small>${esc(t("life.interactions.family.elixir_target", { current: age, target: Math.min(adultAge, age + Math.floor(Number(tier.days || 0) / 365)) }))}</small><b>${esc(familyMoney(Number(tier.price || 0)))}</b></button>`).join("")}</div>`
      : "";
    const clubs = recommendableClubs();
    const clubOptions = clubs.map((club) => `<option value="${Number(club.team_id || 0)}" data-club-level="${Number(club.level || 3)}" data-club-name="${esc(club.name || "")}">${esc(String(club.name || club.team_id || ""))}${club.league_name ? ` · ${esc(club.league_name)}` : ""}</option>`).join("");
    const trialPicker = `<label class="interaction-child-club-picker"><span>${esc(t("life.interactions.family.trial_club"))}</span><select data-child-trial-club="${esc(child.id)}" ${busy ? "disabled" : ""}>${clubOptions}</select></label>`;
    const avatar = child.avatar || {};
    const avatarPanel = age >= adultAge
      ? `<div class="interaction-child-avatar-panel"><div class="interaction-child-avatar-preview">${avatar.preview ? `<img src="${esc(avatar.preview)}" alt="">` : `<i data-lucide="image-plus"></i>`}</div><div class="interaction-child-avatar-copy"><strong>${esc(t("life.interactions.family.avatar_title"))}</strong><small>${esc(avatar.synced_uid ? t("life.interactions.family.avatar_synced", { uid: Number(avatar.synced_uid) }) : avatar.error ? avatar.error : t("life.interactions.family.avatar_note"))}</small></div><label class="interaction-secondary interaction-child-avatar-pick"><i data-lucide="upload"></i><span>${esc(t("life.interactions.family.avatar_choose"))}</span><input type="file" accept="image/png,image/jpeg,image/webp" data-child-avatar="${esc(child.id)}" ${busy ? "disabled" : ""}></label></div>`
      : "";
    const trialAction = child.trial_available
      ? `<div class="interaction-child-trial"><div class="interaction-child-trial-copy"><strong>${esc(t("life.interactions.family.trial_title"))}</strong><small>${esc(t("life.interactions.family.trial_note", { age: adultAge }))}</small></div>${trialPicker}<button type="button" class="interaction-button" data-interaction-action="child-trial" data-child-id="${esc(child.id)}" ${busy ? "disabled" : ""}><i data-lucide="clipboard-check"></i>${esc(t("life.interactions.family.trial_start"))}</button></div>`
      : status.tone === "trial"
        ? `<div class="interaction-child-trial is-final"><div class="interaction-child-trial-copy"><strong>${esc(t("life.interactions.family.finalize_title"))}</strong><small>${esc(t("life.interactions.family.finalize_note"))}</small></div><button type="button" class="interaction-button interaction-child-finalize" data-interaction-action="child-finalize" data-child-id="${esc(child.id)}" ${busy ? "disabled" : ""}><i data-lucide="shield-plus"></i>${esc(t("life.interactions.family.finalize_start"))}</button></div>`
        : "";
    const childView = ["profile", "growth", "academy"].includes(state.familyChildView)
      ? state.familyChildView : "profile";
    const childViewTabs = `<div class="interaction-child-view-bar"><nav class="interaction-child-view-tabs" aria-label="${esc(t("life.interactions.family.detail_open"))}">${[
      ["profile", "life.interactions.family.child_view.profile", "user-round"],
      ["growth", "life.interactions.family.child_view.growth", "sprout"],
      ["academy", "life.interactions.family.child_view.academy", "graduation-cap"],
    ].map(([key, label, icon]) => `<button type="button" class="${key === childView ? "active" : ""}" data-family-child-view="${key}" aria-pressed="${key === childView}"><i data-lucide="${icon}"></i>${esc(t(label))}</button>`).join("")}</nav><button type="button" class="interaction-secondary interaction-child-refresh" data-interaction-action="refresh-family-academy" ${state.requestBusy ? "disabled" : ""}><i data-lucide="refresh-cw"></i><span>${esc(t("life.interactions.family.academy_refresh"))}</span></button></div>`;
    const metaStrip = `<div class="interaction-child-meta">
      <span><i data-lucide="calendar-days"></i>${esc(t("life.interactions.family.born_on", { date: child.born_day ? formatGameDay(child.born_day) : t("life.interactions.family.unknown") }))}</span>
      <span><i data-lucide="venus-and-mars"></i>${child.gender === "female" ? "♀" : "♂"}</span>
      <span><i data-lucide="flask-conical"></i>${esc(t("life.interactions.family.elixirs_used", { count: Number(child.elixirs_used || 0) }))}</span>
      <span><i data-lucide="map-pin"></i>${esc(t("life.interactions.family.detail_position", { position: child.football_position || t("life.interactions.family.position_any") }))}</span>
    </div>`;
    const football = Number(child.ca || 0) > 0
      ? `<div class="interaction-child-football"><span>CA <b>${Number(child.ca || 0)}</b></span><span>PA <b>${Number(child.pa || 0)}</b></span>${child.preferred_position ? `<span>${esc(child.preferred_position)}</span>` : ""}</div>`
      : `<div class="interaction-child-football"><span>${esc(t("life.interactions.family.no_football_data"))}</span></div>`;
    const profileAside = avatarPanel || `<aside class="interaction-child-side-card"><header><small>${esc(t("life.interactions.family.stat_next"))}</small><strong>${next ? `${Number(next.age)} ${esc(t("life.interactions.family.overview_age_suffix"))}` : "—"}</strong></header><p>${esc(next ? childMilestoneLabel(next) : t("life.interactions.family.grown_note"))}</p><div class="interaction-child-side-meta">${relationBadge(child.parent_person_id)}<span>${esc(child.parent_name || t("life.interactions.family.unknown_parent"))}</span></div></aside>`;
    const profileBody = `<div class="interaction-child-detail-body">${nameForm}<div class="interaction-child-profile-grid"><div class="interaction-child-profile-facts">${metaStrip}${football}<p class="interaction-child-note">${esc(next ? t("life.interactions.family.next_milestone", { age: next.age }) : t("life.interactions.family.grown_note"))}</p></div>${profileAside}</div><div class="interaction-child-profile-extra"><section><header><h4>${esc(t("life.interactions.family.growth_nodes"))}</h4><span>${esc(t("life.interactions.family.growth_note"))}</span></header>${milestoneSteps(child)}</section><section><header><h4>${esc(t("life.interactions.family.rail.recent"))}</h4><span>${esc(t("life.interactions.family.training_history", { count: (child.training_history || []).length }))}</span></header>${history || `<p class="interaction-child-note">${esc(t("life.interactions.family.no_history"))}</p>`}</section></div></div>`;
    const growthBody = `<div class="interaction-child-detail-body">${growthEventCta}${milestoneSteps(child)}<div class="interaction-child-history">${history ? `<div class="interaction-child-history-head"><span>${esc(t("life.interactions.family.training_history", { count: (child.training_history || []).length }))}</span></div>${history}` : `<p>${esc(t("life.interactions.family.no_history"))}</p>`}</div>${elixirButtons ? `<details class="interaction-child-tools" open><summary>${esc(t("life.interactions.family.tools_open"))}</summary>${elixirButtons}</details>` : ""}</div>`;
    const placementLabel = String(status.label || "");
    const placementTeam = placementTeamName(placement);
    const placementUid = Number(placement.player_id || 0);
    const placementCa = Number(placement.ca || child.ca || 0);
    const placementPa = Number(placement.pa || child.pa || 0);
    const placementPosition = String(placement.position || child.football_position || "");
    const academyState = `<div class="interaction-child-academy-state is-${status.tone}"><span class="interaction-child-academy-mark"><i data-lucide="${status.tone === "playing" || status.tone === "queued" ? "badge-check" : status.tone === "trial" ? "clipboard-check" : "graduation-cap"}"></i></span><div><strong>${esc(placementLabel)}</strong><small>${esc(placementTeam || t("life.interactions.family.academy_note"))}</small>${placementUid > 0 ? `<small class="interaction-child-academy-uid">FM UID ${placementUid}${placementCa > 0 ? ` · CA ${placementCa}` : ""}${placementPa > 0 ? ` · PA ${placementPa}` : ""}${placementPosition ? ` · ${esc(placementPosition)}` : ""}</small>` : ""}${placement.message ? `<small class="interaction-child-academy-uid">${esc(placement.message)}</small>` : ""}</div></div>`;
    const directAction = age >= adultAge && status.tone === "ready"
      ? `<div class="interaction-child-trial is-final"><div class="interaction-child-trial-copy"><strong>${esc(t("life.interactions.family.place_own"))}</strong><small>${esc(t("life.interactions.family.finalize_note"))}</small></div><button type="button" class="interaction-button interaction-child-finalize" data-interaction-action="child-place" data-mode="own" data-child-id="${esc(child.id)}" ${busy ? "disabled" : ""}><i data-lucide="shield-plus"></i>${esc(t("life.interactions.family.place_own"))}</button></div>`
      : "";
    const academyFallback = ["playing", "queued", "trial", "rejected"].includes(status.tone)
      ? ""
      : `<p class="interaction-child-note">${esc(t("life.interactions.family.academy_waiting"))}</p>`;
    const academyActions = `${trialAction}${directAction}`;
    const academyBody = `<div class="interaction-child-detail-body interaction-child-academy-body${academyActions ? "" : " is-single"}"><div class="interaction-child-academy-main">${academyState}${academyFallback}</div>${academyActions ? `<div class="interaction-child-academy-actions">${academyActions}</div>` : ""}</div>`;
    return `<article class="interaction-child-card" data-child-card="${esc(child.id)}">
      <header class="interaction-child-hero">
        <span class="interaction-child-avatar">${avatar.preview ? `<img src="${esc(avatar.preview)}" alt="">` : `<i data-lucide="baby"></i>`}</span>
        <div class="interaction-child-identity">
          <span class="interaction-child-kicker">${esc(t("life.interactions.family.parent", { name: String(child.parent_name || "") }))}${relationBadge(child.parent_person_id)}</span>
          <div class="interaction-child-name-row"><h3>${esc(name || t("life.interactions.family.unnamed"))}</h3>${renameButton}</div>
          <div class="interaction-child-chips"><span class="interaction-child-status is-${status.tone}">${esc(status.label)}</span></div>
        </div>
        <div class="interaction-child-hero-side">
          <div class="interaction-child-hero-stats">
            <span><small>CA</small><b>${displayCa}</b></span>
            <span><small>PA</small><b>${displayPa}</b></span>
            ${displayPosition ? `<span class="is-position">${esc(displayPosition)}</span>` : ""}
          </div>
          <span class="interaction-child-age">${esc(t("life.interactions.family.age", { age }))}</span>
        </div>
      </header>
      <div class="interaction-child-progress-row"><span class="interaction-child-progress"><span style="width:${Math.max(0, Math.min(100, (age / adultAge) * 100)).toFixed(1)}%"></span></span><b>${age} / ${adultAge}</b></div>
      ${childViewTabs}
      <section class="interaction-child-view">${childView === "profile" ? profileBody : childView === "growth" ? growthBody : academyBody}</section>
    </article>`;
  }

  function familySectionTabs(active) {
    const sections = [
      ["overview", "life.interactions.family.section.overview", "layout-dashboard"],
      ["children", "life.interactions.family.section.children", "users-round"],
      ["growth", "life.interactions.family.section.growth", "sprout"],
      ["academy", "life.interactions.family.section.academy", "graduation-cap"],
    ];
    return `<nav class="interaction-family-sections" aria-label="${esc(t("life.interactions.family.section_label"))}">${sections.map(([key, label, icon]) => `<button type="button" class="${key === active ? "active" : ""}" data-family-section="${key}" aria-pressed="${key === active}"><i data-lucide="${icon}"></i><span>${esc(t(label))}</span></button>`).join("")}</nav>`;
  }

  function familyOverview(children, parentRows, adultAge) {
    const pending = children.filter((child) => {
      const status = String(child.placement?.status || "");
      return child.trial_available || ["training", "trial_passed", "armed", "pending", "applied"].includes(status);
    });
    const nextChild = children
      .map((child) => ({ child, next: childMilestoneRows(child).find((row) => row.status === "due") || childMilestoneRows(child).find((row) => row.status === "upcoming") }))
      .filter((row) => row.next)
      .sort((left, right) => Number(left.next.age) - Number(right.next.age))[0];
    const parentCards = parentRows.map((parent) => `<button type="button" class="interaction-family-overview-parent" data-family-section="children" data-family-parent="${parent.id}">${portraitMarkup({ id: parent.id, name: parent.name }, { small: true })}<span class="interaction-family-overview-parent-copy"><strong>${esc(parent.name)}</strong><span>${relationBadge(parent.id)}<small>${esc(t("life.interactions.family.parent_children", { count: parent.children.length }))}</small></span></span><i data-lucide="chevron-right"></i></button>`).join("");
    return `<section class="interaction-family-overview">
      <div class="interaction-family-callout"><span class="interaction-family-callout-icon"><i data-lucide="house-heart"></i></span><div><strong>${esc(t("life.interactions.family.overview_title"))}</strong><p>${esc(t("life.interactions.family.overview_note"))}</p></div></div>
      <div class="interaction-family-overview-grid">
        <article class="interaction-family-overview-card"><small>${esc(t("life.interactions.family.overview_next"))}</small><strong>${nextChild ? `${esc(nextChild.child.name || t("life.interactions.family.unnamed"))} · ${Number(nextChild.next.age)} ${esc(t("life.interactions.family.overview_age_suffix"))}` : "—"}</strong><span>${esc(nextChild ? childMilestoneLabel(nextChild.next) : t("life.interactions.family.overview_none"))}</span></article>
        <article class="interaction-family-overview-card"><small>${esc(t("life.interactions.family.overview_academy"))}</small><strong>${pending.length}</strong><span>${esc(t("life.interactions.family.overview_academy_note", { age: adultAge }))}</span></article>
        <article class="interaction-family-overview-card"><small>${esc(t("life.interactions.family.overview_parents"))}</small><strong>${parentRows.length}</strong><span>${esc(t("life.interactions.family.overview_parents_note"))}</span></article>
      </div>
      <section class="interaction-family-overview-panel"><header><div><h3>${esc(t("life.interactions.family.parents_title"))}</h3><p>${esc(t("life.interactions.family.overview_parent_hint"))}</p></div><button type="button" class="interaction-secondary" data-family-section="children"><i data-lucide="users-round"></i>${esc(t("life.interactions.family.open_children"))}</button></header><div class="interaction-family-overview-parents">${parentCards}</div></section>
    </section>`;
  }

  function familyGrowth(children) {
    const rows = children.map((child) => `<article class="interaction-family-growth-card"><header><div><strong>${esc(child.name || t("life.interactions.family.unnamed"))}</strong><small>${esc(t("life.interactions.family.age", { age: Number(child.age || 0) }))}</small></div><span>${esc(t("life.interactions.family.training_history", { count: (child.training_history || []).length }))}</span></header>${milestoneSteps(child)}</article>`).join("");
    return `<section class="interaction-family-growth"><header class="interaction-family-subsection-head"><div><h3>${esc(t("life.interactions.family.growth_title"))}</h3><p>${esc(t("life.interactions.family.growth_note"))}</p></div><span class="interaction-badge">${children.length}</span></header><div class="interaction-family-growth-grid">${rows}</div></section>`;
  }

  function familyAcademyRow(child, adultAge) {
    const placement = child.placement || {};
    const acadName = String(child.name || placement.player_name || t("life.interactions.family.unnamed"));
    const clubs = recommendableClubs();
    const status = childStatusMeta(child);
    const action = child.trial_available
      ? `<div class="interaction-family-academy-action"><select data-child-trial-club="${esc(child.id)}">${clubs.map((club) => `<option value="${Number(club.team_id || 0)}" data-club-level="${Number(club.level || 3)}" data-club-name="${esc(club.name || "")}">${esc(club.name || club.team_id || "")}</option>`).join("")}</select><button type="button" class="interaction-button" data-interaction-action="child-trial" data-child-id="${esc(child.id)}"><i data-lucide="clipboard-check"></i>${esc(t("life.interactions.family.trial_start"))}</button></div>`
      : status.tone === "trial"
        ? `<button type="button" class="interaction-button" data-interaction-action="child-finalize" data-child-id="${esc(child.id)}"><i data-lucide="shield-plus"></i>${esc(t("life.interactions.family.finalize_start"))}</button>`
        : "";
    const uid = Number(placement.player_id || 0);
    return `<article class="interaction-family-academy-card"><div class="interaction-family-academy-icon"><i data-lucide="${status.tone === "playing" || status.tone === "queued" ? "badge-check" : "graduation-cap"}"></i></div><div class="interaction-family-academy-main"><header><strong>${esc(acadName)}</strong><span>${esc(t("life.interactions.family.age", { age: Number(child.age || 0) }))}</span></header><p>${esc(status.label || (Number(child.age || 0) >= adultAge ? t("life.interactions.family.academy_ready") : t("life.interactions.family.grow_note", { years: Math.max(0, adultAge - Number(child.age || 0)) })))}</p><small class="interaction-family-academy-team"><i data-lucide="shield"></i>${esc(placementTeamName(placement))}</small>${uid > 0 ? `<small class="interaction-family-academy-uid">FM UID ${uid}</small>` : ""}</div><div class="interaction-family-academy-side">${action || `<span class="interaction-badge ${status.tone === "playing" ? "friend" : status.tone === "rejected" ? "secret" : ""}">${esc(status.label)}</span>`}</div></article>`;
  }

  function familyAcademy(children, adultAge) {
    return `<section class="interaction-family-academy"><header class="interaction-family-subsection-head"><div><h3>${esc(t("life.interactions.family.academy_title"))}</h3><p>${esc(t("life.interactions.family.academy_note"))}</p></div><button type="button" class="interaction-secondary" data-interaction-action="refresh-family-academy" ${state.requestBusy ? "disabled" : ""}><i data-lucide="refresh-cw"></i>${esc(t("life.interactions.family.academy_refresh"))}</button></header><div class="interaction-family-academy-list">${children.map((child) => familyAcademyRow(child, adultAge)).join("")}</div></section>`;
  }

  function familyChildRail(child, allChildren) {
    const placement = child?.placement || {};
    const status = childStatusMeta(child || {});
    const age = Number(child?.age || 0);
    const adultAge = Number(child?.adult_age || 15);
    const uid = Number(placement.player_id || 0);
    const team = placementTeamName(placement);
    const playerName = String(placement.player_name || child?.name || "");
    const ca = Number(placement.ca || child?.ca || 0);
    const pa = Number(placement.pa || child?.pa || 0);
    const position = String(placement.position || child?.football_position || child?.preferred_position || "");
    const history = (child?.training_history || []).slice().reverse().slice(0, 3);
    const siblings = (allChildren || []).filter((row) => (
      String(row.parent_person_id || "") === String(child?.parent_person_id || "")
      && String(row.id || "") !== String(child?.id || "")
    ));
    const steps = [
      {
        key: "trial", title: t("life.interactions.family.rail.trial"),
        note: age >= adultAge
          ? t("life.interactions.family.rail.trial_done")
          : t("life.interactions.family.rail.trial_wait", { age: adultAge }),
        state: age >= adultAge ? "done" : "current",
      },
      {
        key: "plan", title: t("life.interactions.family.rail.plan"),
        note: placement.status
          ? t("life.interactions.family.rail.plan_active", { team })
          : t("life.interactions.family.rail.plan_wait"),
        state: placement.status ? "done" : (age >= adultAge ? "current" : ""),
      },
      {
        key: "list", title: t("life.interactions.family.rail.list"),
        note: uid > 0
          ? t("life.interactions.family.rail.list_done", { name: playerName || team })
          : placement.status === "armed" || placement.status === "pending"
            ? t("life.interactions.family.rail.list_wait")
            : t("life.interactions.family.rail.list_todo"),
        state: uid > 0 ? "done" : (placement.status === "armed" || placement.status === "pending" ? "current" : ""),
      },
      {
        key: "register", title: t("life.interactions.family.rail.register"),
        note: uid > 0
          ? t("life.interactions.family.rail.register_done", { team })
          : t("life.interactions.family.rail.register_wait"),
        state: uid > 0 ? "current" : "",
      },
    ];
    const stepMarkup = steps.map((step) => `<div class="interaction-family-rail-step ${step.state ? `is-${step.state}` : ""}"><span class="interaction-family-rail-dot"></span><div><b>${esc(step.title)}</b><small>${esc(step.note)}</small></div></div>`).join("");
    const historyMarkup = history.length
      ? history.map((row) => `<div class="interaction-family-rail-event"><span></span><div><b>${esc(eventOptionLabel("child_football", String(row.option || "")))}</b><small>${esc(t("life.interactions.family.training_age", { age: Number(row.age || 0) }))} · CA ${Number(row.ca || 0)} / PA ${Number(row.pa || 0)}</small></div></div>`).join("")
      : `<p class="interaction-family-rail-empty">${esc(t("life.interactions.family.no_history"))}</p>`;
    return `<aside class="interaction-family-rail">
      <section class="interaction-family-rail-card">
        <header><h3>${esc(t("life.interactions.family.rail.title"))}</h3><span class="interaction-badge ${uid > 0 ? "partner" : status.tone === "queued" ? "friend" : "secret"}">${esc(status.label)}</span></header>
        <div class="interaction-family-rail-steps">${stepMarkup}</div>
        <button type="button" class="interaction-secondary interaction-family-rail-refresh" data-interaction-action="refresh-family-academy" ${state.requestBusy ? "disabled" : ""}><i data-lucide="refresh-cw"></i>${esc(t("life.interactions.family.academy_refresh"))}</button>
      </section>
      <section class="interaction-family-rail-card">
        <header><h3>${esc(t("life.interactions.family.rail.ability"))}</h3><span class="interaction-badge">${esc(position || "—")}</span></header>
        <div class="interaction-family-rail-ability"><span>CA</span><div><i style="width:${Math.max(0, Math.min(100, (ca / 200) * 100)).toFixed(1)}%"></i></div><b>${ca}</b></div>
        <div class="interaction-family-rail-ability is-pa"><span>PA</span><div><i style="width:${Math.max(0, Math.min(100, (pa / 200) * 100)).toFixed(1)}%"></i></div><b>${pa}</b></div>
        <div class="interaction-family-rail-meta"><span>${esc(t("life.interactions.family.rail.fm_uid"))}</span><b>${uid > 0 ? uid : "—"}</b></div>
        <div class="interaction-family-rail-meta"><span>${esc(t("life.interactions.family.rail.club"))}</span><b>${esc(uid > 0 ? team : t("life.interactions.family.rail.club_wait"))}</b></div>
      </section>
      <section class="interaction-family-rail-card">
        <header><h3>${esc(t("life.interactions.family.rail.family"))}</h3></header>
        <div class="interaction-family-rail-meta"><span>${esc(t("life.interactions.family.rail.parent"))}</span><b>${esc(child?.parent_name || "—")}</b></div>
        <div class="interaction-family-rail-meta"><span>${esc(t("life.interactions.family.rail.siblings"))}</span><b>${siblings.length}</b></div>
        <div class="interaction-family-rail-meta"><span>${esc(t("life.interactions.family.rail.born"))}</span><b>${esc(child?.born_day ? formatGameDay(child.born_day) : "—")}</b></div>
      </section>
      <section class="interaction-family-rail-card">
        <header><h3>${esc(t("life.interactions.family.rail.recent"))}</h3></header>
        <div class="interaction-family-rail-events">${historyMarkup}</div>
      </section>
    </aside>`;
  }

  function renderFamily(data) {
    const listed = data && data.children;
    state.familyDebug = { hasData: Boolean(data), type: typeof listed, count: Array.isArray(listed) ? listed.length : -1 };
    const children = Array.isArray(listed) ? listed : [];
    const rules = data?.children_rules || {};
    if (!children.length) {
      return `<div class="interaction-section-head"><div><h2>${esc(t("life.interactions.family.title"))}</h2><p>${esc(t("life.interactions.family.subtitle"))}</p></div></div><div class="interaction-empty"><i data-lucide="baby"></i><span>${esc(t("life.interactions.family.empty"))}</span></div>`;
    }
    const parents = new Map();
    for (const child of children) {
      const id = Number(child.parent_person_id || 0);
      if (!parents.has(id)) parents.set(id, {
        id, name: String(child.parent_name || t("life.interactions.family.unknown_parent")),
        children: [],
      });
      parents.get(id).children.push(child);
    }
    const parentRows = [...parents.values()].sort((a, b) => String(a.name).localeCompare(String(b.name)));
    const selectedId = parents.has(Number(state.familyParentId || 0))
      ? Number(state.familyParentId) : parentRows[0].id;
    state.familyParentId = selectedId;
    const selected = parents.get(selectedId);
    const selectedChild = selected.children.find(
      (child) => String(child.id || "") === String(state.familyChildId || ""),
    ) || selected.children[0];
    state.familyChildId = String(selectedChild?.id || "");
    const adultAge = Number(rules.adult_age || 15);
    const academyCount = children.filter((row) => (
      Number(row.placement?.player_id || 0) > 0
      || ["armed", "pending", "applied", "playing", "trial_passed"].includes(String(row.placement?.status || ""))
    )).length;
    const nextAge = children
      .map((row) => Number(row.age || 0))
      .map((age) => [3, 6, 9, 12].find((milestone) => milestone > age) || adultAge)
      .sort((left, right) => left - right)[0] || adultAge;
    const section = ["overview", "children", "growth", "academy"].includes(state.familySection)
      ? state.familySection : "children";
    const parentChips = parentRows.map((parent) => `<button type="button" class="interaction-family-parent-chip ${parent.id === selectedId ? "active" : ""}" data-family-parent="${parent.id}" aria-pressed="${parent.id === selectedId}">${portraitMarkup({ id: parent.id, name: parent.name }, { small: true })}<span><b>${esc(parent.name)}</b><small>${relationBadge(parent.id)} ${esc(t("life.interactions.family.parent_children", { count: parent.children.length }))}</small></span></button>`).join("");
    const childChips = selected.children.map((child) => `<button type="button" class="interaction-family-child-chip ${String(child.id) === String(selectedChild?.id) ? "active" : ""}" data-family-child="${esc(child.id)}" aria-pressed="${String(child.id) === String(selectedChild?.id)}"><span class="interaction-family-child-chip-avatar">${child.avatar?.preview ? `<img src="${esc(child.avatar.preview)}" alt="">` : `<i data-lucide="user-round"></i>`}</span><span><b>${esc(child.name || t("life.interactions.family.unnamed"))}</b><small>${esc(t("life.interactions.family.age", { age: Number(child.age || 0) }))}</small></span>${Number(child.placement?.player_id || 0) > 0 ? `<span class="interaction-badge partner">U18</span>` : ""}</button>`).join("");
    let body = familyOverview(children, parentRows, adultAge);
    if (section === "children") {
      body = `<div class="interaction-family-workspace"><div class="interaction-family-main">${selectedChild ? familyChild(selectedChild) : ""}</div>${selectedChild ? familyChildRail(selectedChild, children) : ""}</div>`;
    } else if (section === "growth") {
      body = familyGrowth(children);
    } else if (section === "academy") {
      body = familyAcademy(children, adultAge);
    }
    return `<div class="interaction-section-head"><div><h2>${esc(t("life.interactions.family.title"))}</h2><p>${esc(t("life.interactions.family.subtitle"))}</p></div><span class="interaction-badge partner">${esc(t("life.interactions.family.summary_v3", { total: children.length, academy: academyCount }))}</span></div>
      <div class="interaction-family-summary-grid">
        <article class="interaction-family-summary-card"><small>${esc(t("life.interactions.family.stat_children"))}</small><strong>${children.length}</strong><span>${esc(t("life.interactions.family.stat_children_note"))}</span></article>
        <article class="interaction-family-summary-card"><small>${esc(t("life.interactions.family.stat_next"))}</small><strong>${nextAge}</strong><span>${esc(t("life.interactions.family.stat_next_note", { age: nextAge }))}</span></article>
        <article class="interaction-family-summary-card"><small>${esc(t("life.interactions.family.stat_academy"))}</small><strong>${academyCount}</strong><span>${esc(t("life.interactions.family.stat_academy_note"))}</span></article>
        <article class="interaction-family-summary-card"><small>${esc(t("life.interactions.family.stat_parents"))}</small><strong>${parentRows.length}</strong><span>${esc(t("life.interactions.family.stat_parents_note"))}</span></article>
      </div>
      <section class="interaction-family-selector"><div class="interaction-family-selector-row"><span>${esc(t("life.interactions.family.parents_title"))}</span>${parentChips}</div><div class="interaction-family-selector-row"><span>${esc(t("life.interactions.family.children_label"))}</span>${childChips}</div></section>
      ${familySectionTabs(section)}
      ${body}`;
  }

  function str(row, key) {
    const locale = String(bridge()?.getState?.()?.settings?.ui_locale || "").toLowerCase();
    const zh = locale.startsWith("zh");
    return String(row?.[zh ? `${key}_zh` : `${key}_en`] || row?.[key] || "");
  }

  function applyLifeView(response) {
    const view = response?.life && Array.isArray(response.life.children)
      ? response.life
      : Array.isArray(response?.children) ? response : null;
    if (!view) return false;
    applyData(view, state.selectedId);
    return true;
  }

  async function renameChild(childId) {
    if (!childId || state.childBusy) return;
    const child = (state.data?.children || []).find((row) => String(row.id) === String(childId));
    if (!child) return;
    if (Number(child.age || 0) >= Number(child.adult_age || 15)) {
      bridge()?.toast(t("life.interactions.family.rename_locked"));
      return;
    }
    const oldName = String(child.name || "");
    const accepted = await bridge()?.fmoddConfirm?.(
      t("life.interactions.family.rename_confirm", {name: oldName}),
      t("life.interactions.family.rename"),
      t("life.interactions.family.rename_title"),
    );
    if (!accepted) return;
    const value = window.prompt(t("life.interactions.family.rename_prompt"), oldName);
    const next = String(value || "").trim();
    if (!next || next === oldName) return;
    state.childBusy = childId;
    paintWorkspace();
    try {
      const response = await postJson("/api/life/interactions/children/name", {
        child_id: childId, name: next, preferred_position: String(child.preferred_position || ""),
      });
      applyLifeView(response);
      bridge()?.toast(t("life.interactions.family.rename_done", {name: next}));
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.childBusy = "";
      paintWorkspace();
    }
  }

  async function submitChildName(form) {
    const childId = String(form?.dataset.childId || "");
    const name = String(form?.querySelector("[name=child_name]")?.value || "").trim();
    const position = String(form?.querySelector("[name=child_position]")?.value || "");
    if (!childId || !name) return;
    state.childBusy = childId;
    try {
      const response = await postJson("/api/life/interactions/children/name", {
        child_id: childId, name, preferred_position: position,
      });
      if (applyLifeView(response)) {
        paintWorkspace();
      }
      bridge()?.toast(t("life.interactions.family.name_saved", {name}));
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.childBusy = "";
    }
  }

  async function feedChildElixir(childId, tier) {
    if (!childId || !tier || state.childBusy) return;
    const child = (state.data?.children || []).find((row) => String(row.id) === String(childId));
    const label = String(child?.name || "");
    const accepted = await bridge()?.fmoddConfirm?.(
      t("life.interactions.family.elixir_confirm", {name: label, tier}),
      t("life.interactions.family.elixir_open"),
      t("life.interactions.family.title"),
    );
    if (!accepted) return;
    state.childBusy = childId;
    try {
      const response = await postJson("/api/life/interactions/children/elixir", {
        child_id: childId, tier,
      });
      if (applyLifeView(response)) {
        paintWorkspace();
      }
      bridge()?.toast(t("life.interactions.family.elixir_done", {
        name: String(response?.child?.name || label),
        age: Number(response?.quote?.target_age || 0),
      }));
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.childBusy = "";
    }
  }

  async function uploadChildAvatar(childId, file) {
    if (!childId || !file || state.childBusy) return;
    if (Number(file.size || 0) > 2 * 1024 * 1024) {
      bridge()?.toast(t("life.interactions.family.avatar_too_large"));
      return;
    }
    const extension = String(file.type || "image/png").split("/").pop() || "png";
    state.childBusy = childId;
    paintWorkspace();
    try {
      const image = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(new Error(t("life.interactions.family.avatar_failed")));
        reader.readAsDataURL(file);
      });
      const response = await postJson("/api/life/interactions/children/avatar", {
        child_id: childId, image, extension,
      });
      applyLifeView(response);
      bridge()?.toast(t("life.interactions.family.avatar_saved"));
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.childBusy = "";
      paintWorkspace();
    }
  }

  async function finalizeChildTraining(childId) {
    if (!childId || state.childBusy) return;
    const child = (state.data?.children || []).find((row) => String(row.id) === String(childId));
    const placement = child?.placement || {};
    const teamId = Number(placement.team_id || 0);
    if (!child || teamId <= 0) {
      bridge()?.toast(t("life.interactions.family.finalize_no_team"));
      return;
    }
    const managerTeamId = Number(state.data?.manager_identity?.team_id || 0);
    const mode = managerTeamId === teamId ? "own" : "recommend";
    state.childBusy = childId;
    paintWorkspace();
    try {
      const response = await postJson("/api/life/interactions/children/academy", {
        child_id: childId, mode, team_id: teamId,
      });
      applyLifeView(response);
      paintWorkspace();
      bridge()?.toast(String(response?.warning || t("life.interactions.family.finalize_done")));
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.childBusy = "";
      paintWorkspace();
    }
  }

  async function startChildTrial(childId) {
    if (!childId || state.childBusy) return;
    const picker = [...document.querySelectorAll("[data-child-trial-club]")]
      .find((node) => String(node.dataset.childTrialClub || "") === String(childId));
    const option = picker?.selectedOptions?.[0];
    const teamId = Number(option?.value || 0);
    const teamName = String(option?.dataset?.clubName || option?.textContent || "").trim();
    const clubLevel = Number(option?.dataset?.clubLevel || 3);
    if (teamId <= 0) {
      bridge()?.toast(t("life.interactions.family.trial_no_club"));
      return;
    }
    state.childBusy = childId;
    paintWorkspace();
    try {
      const response = await postJson("/api/life/interactions/children/trial", {
        child_id: childId, team_id: teamId, team_name: teamName, club_level: clubLevel,
      });
      applyLifeView(response);
      paintWorkspace();
      bridge()?.toast(String(response?.placement?.message || t("life.interactions.family.trial_done")));
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.childBusy = "";
      paintWorkspace();
    }
  }

  async function placeChild(childId, mode) {
    if (!childId || state.childBusy) return;
    const child = (state.data?.children || []).find((row) => String(row.id) === String(childId));
    const clubs = mode === "recommend" ? recommendableClubs() : [];
    if (mode === "recommend" && !clubs.length) {
      bridge()?.toast(t("life.interactions.family.no_clubs"));
      return;
    }
    const picker = [...document.querySelectorAll("[data-child-club]")].find(
      (node) => String(node.dataset.childClub || "") === String(childId),
    );
    const teamId = mode === "own"
      ? Number(state.data?.manager_identity?.team_id || 0)
      : Number(picker?.value || 0);
    if (!teamId) {
      bridge()?.toast(t("life.interactions.family.no_own_club"));
      return;
    }
    state.childBusy = childId;
    try {
      const response = await postJson("/api/life/interactions/children/academy", {
        child_id: childId, mode, team_id: teamId,
      });
      if (applyLifeView(response)) {
        paintWorkspace();
      }
      bridge()?.toast(String(response?.warning || t("life.interactions.family.place_done", {
        name: String(child?.name || ""),
        team: String(response?.team_name || ""),
      })));
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.childBusy = "";
    }
  }

  function recommendableClubs() {
    const owned = state.data?.recommendable_clubs;
    if (Array.isArray(owned) && owned.length) return owned;
    const manager = state.data?.manager_identity || {};
    return Number(manager.team_id || 0) ? [{"team_id": Number(manager.team_id), "name": String(manager.team_name || "")}] : [];
  }

  function renderTabs(data, type = "main") {
    let definitions = type === "main"
      ? TABS
      : type === "people"
        ? [
          ["dossier", "life.interactions.people_tabs.dossier", "id-card"],
          ["interaction", "life.interactions.people_tabs.interaction", "message-circle-more"],
          ["owned", "life.interactions.people_tabs.owned", "gem"],
        ]
        : type === "interaction"
          ? [
            ["home", "life.interactions.interaction_tabs.home", "sparkles"],
            ["progress", "life.interactions.interaction_tabs.progress", "route"],
          ]
          : [["residence", "life.interactions.asset_tabs.residence", "house"], ["gift", "life.interactions.asset_tabs.gift", "gift"]];
    if (type === "interaction" && state.data?.adult_content_enabled
      && isIntimateRelationship(selectedRow()?.relationship)) {
      definitions = [...definitions, ["intimacy", "life.interactions.interaction_tabs.intimacy", "heart-handshake"]];
    }
    let current = type === "main"
      ? state.tab
      : type === "people"
        ? state.peopleTab
        : type === "interaction"
          ? state.interactionTab
          : state.assetsTab;
    if (type === "interaction" && !definitions.some(([key]) => key === current)) {
      current = "home";
      state.interactionTab = "home";
    }
    const counts = tabCounts(data);
    const attribute = type === "main"
      ? "data-interaction-tab"
      : type === "people"
        ? "data-interaction-people-tab"
        : type === "interaction"
          ? "data-interaction-mode-tab"
          : "data-interaction-assets-tab";
    return `<nav class="interaction-tabs ${type === "main" ? "is-main" : "is-sub"} ${type === "interaction" ? "is-inline" : ""}" role="tablist"${type === "interaction" ? ` aria-label="${esc(t("life.interactions.interaction_tabs.label"))}"` : ""}>${definitions.map(([key, labelKey, icon]) => {
      const active = current === key;
      return `<button type="button" class="interaction-tab ${active ? "active" : ""}" ${attribute}="${key}" role="tab" aria-selected="${active}"><i data-lucide="${icon}"></i><span>${esc(t(labelKey))}</span>${type === "main" && counts[key] ? `<b>${counts[key]}</b>` : ""}</button>`;
    }).join("")}</nav>`;
  }

  function eventKindLabel(kind) {
    return t(`life.interactions.event.kind.${String(kind || "relationship_crisis")}`);
  }

  function eventKindIcon(kind) {
    if (kind === "pregnancy") return "sprout";
    if (kind === "secret_exposure") return "eye";
    if (kind === "child_football") return "graduation-cap";
    return "heart-crack";
  }

  function eventDescription(event) {
    const kind = String(event?.kind || "relationship_crisis");
    const data = event?.data || {};
    if (kind === "pregnancy") {
      return t("life.interactions.event.pregnancy.body", {
        name: event?.person_name || "",
        days: Number(data.due_day || 0),
        early: data.due_early ? formatGameDay(data.due_early) : "",
        late: data.due_late ? formatGameDay(data.due_late) : "",
      });
    }
    if (kind === "secret_exposure") {
      return t("life.interactions.event.secret_exposure.body", {
        name: event?.person_name || "",
        public: data.public_person_name || t("life.interactions.event.secret_exposure.no_public"),
      });
    }
    if (kind === "child_football") {
      return t("life.interactions.event.child_football.body", {
        name: data.child_name || "",
        age: Number(data.age || 0),
      });
    }
    return t("life.interactions.event.relationship_crisis.body", {
      name: event?.person_name || "",
      value: Number(data.intimacy || 0).toFixed(1),
    });
  }

  function eventOptionLabel(kind, option) {
    return t(`life.interactions.event.${kind}.option.${option}.title`);
  }

  function eventOptionDetail(kind, option) {
    if (kind === "child_football") {
      return t("life.interactions.event.child_football.option_detail");
    }
    return t(`life.interactions.event.${kind}.option.${option}.detail`);
  }

  function eventOptionIcon(option) {
    if (["keep_child", "repair"].includes(option)) return "heart-handshake";
    if (option === "end_secret") return "shield-check";
    if (option === "end_public_relationship") return "heart-off";
    if (option === "finisher") return "target";
    if (option === "creator") return "brain";
    if (option === "winger") return "wind";
    if (option === "defender") return "shield";
    if (option === "goalkeeper") return "hand";
    if (option === "balanced") return "sprout";
    if (option === "street") return "goal";
    if (option === "athletic") return "dumbbell";
    if (option === "risky") return "flame";
    if (option === "rest") return "moon";
    if (option === "mentor") return "users-round";
    if (option === "late") return "hourglass";
    if (option === "team") return "shield-check";
    return "circle-slash";
  }

  function eventResolutionText(result, kind) {
    if (kind === "child_football") {
      return t("life.interactions.event.child_football.result", {
        name: result?.detail?.child?.name || "",
        ca: Number(result?.detail?.training?.ca || 0),
        pa: Number(result?.detail?.training?.pa || 0),
      });
    }
    const option = String(result?.option || "");
    const detail = result?.detail || {};
    const suffix = result?.success === false ? "result_fail" : "result";
    const key = `life.interactions.event.${kind}.option.${option}.${suffix}`;
    return translated(key, {
      name: result?.person_name || "",
      child: detail.child?.name || "",
    }) || t(`life.interactions.event.${kind}.option.${option}.result`) || t("life.interactions.result.recorded");
  }

  function renderPendingEvents(data) {
    const events = Array.isArray(data?.pending_events) ? data.pending_events : [];
    if (!events.length) return "";
    return `<section class="interaction-pending-events"><header class="interaction-pending-events-head"><div><h2>${esc(t("life.interactions.event.pending_title"))}</h2><p>${esc(t("life.interactions.event.pending_detail", {count: events.length}))}</p></div><span class="interaction-badge secret">${Number(events.length)}</span></header><div class="interaction-pending-event-list">${events.map((event) => `<button type="button" class="interaction-pending-event" data-interaction-event="${esc(event.id)}"><span class="interaction-pending-event-icon"><i data-lucide="${eventKindIcon(event.kind)}"></i></span><span class="interaction-pending-event-copy"><strong>${esc(eventKindLabel(event.kind))}</strong><small>${esc(event.person_name || "")}</small></span><i data-lucide="chevron-right"></i></button>`).join("")}</div></section>`;
  }

  function assetPassCarArt(level) {
    const vehicle = level.vehicle || {};
    if (!vehicle.image) {
      return `<span class="interaction-asset-pass-car-art is-empty"><i data-lucide="car-front"></i></span>`;
    }
    return `<span class="interaction-asset-pass-car-art"><i data-lucide="car-front"></i><img src="${esc(vehicle.image)}" alt="${esc(vehicle.name || vehicle.catalog_id || "")}" loading="lazy" draggable="false"></span>`;
  }

  function renderAssetLevelTimeline(data) {
    const snapshot = data?.asset_level || {};
    const levels = Array.isArray(snapshot.levels) ? snapshot.levels : [];
    if (!levels.length) return "";
    const currentLevel = Number(snapshot.current_level || 1);
    const nextCopy = snapshot.next_threshold
      ? t("life.interactions.asset_level.next", {
        value: compactMoney(snapshot.next_threshold),
        level: Number(snapshot.next_level || 0),
      })
      : t("life.interactions.asset_level.max");
    const cards = levels.map((level) => {
      const number = Number(level.level || 0);
      const unlocked = Boolean(level.unlocked);
      const current = number === currentLevel;
      const pending = Boolean(level.vehicle_pending);
      const statusKey = current
        ? "current_badge"
        : pending ? "pending" : unlocked ? "unlocked" : "locked";
      const points = Number(level.points || 0);
      const pointsMarkup = points > 0
        ? `<span class="interaction-asset-pass-points ${level.claimed ? "is-claimed" : ""}"><i data-lucide="${level.claimed ? "badge-check" : "sparkles"}"></i>${esc(t("life.interactions.asset_level.points", {count: points}))}</span>`
        : `<span class="interaction-asset-pass-points is-empty"><i data-lucide="flag"></i>${esc(t("life.interactions.asset_level.start"))}</span>`;
      const vehicle = level.vehicle || null;
      const claimable = Boolean(vehicle && unlocked && !level.vehicle_claimed);
      const carStatus = vehicle
        ? level.vehicle_claimed
          ? `<span class="interaction-asset-pass-car-status is-claimed"><i data-lucide="badge-check"></i>${esc(t("life.interactions.asset_level.claimed"))}</span>`
          : claimable
            ? `<span class="interaction-asset-pass-car-status is-pending"><i data-lucide="gift"></i>${esc(t("life.interactions.asset_level.pending"))}</span>`
            : `<span class="interaction-asset-pass-car-status"><i data-lucide="lock-keyhole"></i>${esc(t("life.interactions.asset_level.car_reward"))}</span>`
        : "";
      const claimButton = claimable
        ? `<button type="button" class="interaction-asset-pass-claim" data-interaction-action="claim-asset-level" data-level="${number}" ${state.requestBusy ? "disabled" : ""}><i data-lucide="${state.claimLevel === number ? "loader-circle" : "hand-coins"}"></i>${esc(state.claimLevel === number ? t("life.interactions.asset_level.claiming") : t("life.interactions.asset_level.claim_vehicle"))}</button>`
        : "";
      return `<article class="interaction-asset-pass-card ${unlocked ? "is-unlocked" : "is-locked"} ${current ? "is-current" : ""} ${pending ? "is-pending" : ""}" data-asset-level="${number}">
        <header class="interaction-asset-pass-card-head"><span class="interaction-asset-pass-level"><small>LV</small><b>${String(number).padStart(2, "0")}</b></span><span class="interaction-asset-pass-state state-${statusKey}">${esc(t(`life.interactions.asset_level.${statusKey}`))}</span></header>
        <small class="interaction-asset-pass-threshold">${esc(t("life.interactions.asset_level.threshold", {value: compactMoney(level.threshold || 0)}))}</small>
        ${pointsMarkup}
        <div class="interaction-asset-pass-reward ${vehicle ? "has-car" : ""}">
          ${vehicle ? `${assetPassCarArt(level)}<div class="interaction-asset-pass-car-copy"><small>${esc(t("life.interactions.asset_level.car_reward"))}</small><strong>${esc(vehicle.name || vehicle.catalog_id || "")}</strong><em>${esc([vehicle.manufacturer, vehicle.class].filter(Boolean).join(" · "))}</em>${carStatus}${claimButton}</div>` : `<div class="interaction-asset-pass-no-car"><i data-lucide="sparkles"></i><span>${esc(t("life.interactions.asset_level.points_only"))}</span></div>`}
        </div>
      </article>`;
    }).join("");
    return `<section class="interaction-asset-pass" aria-label="${esc(t("life.interactions.asset_level.title"))}">
      <div class="interaction-asset-pass-hero">
        <div class="interaction-asset-pass-emblem"><small>LV</small><strong>${String(currentLevel).padStart(2, "0")}</strong></div>
        <div class="interaction-asset-pass-hero-copy"><span class="interaction-kicker">${esc(t("life.interactions.asset_level.eyebrow"))}</span><h2>${esc(t("life.interactions.asset_level.current", {level: currentLevel}))}</h2><p>${esc(nextCopy)}</p></div>
        <div class="interaction-asset-pass-summary"><span>${esc(t("life.interactions.asset_level.total"))}<strong>${esc(compactMoney(snapshot.total_value || 0))}</strong></span><span>${esc(t("life.interactions.asset_level.property"))}<strong>${esc(compactMoney(snapshot.property_value || 0))}</strong></span><span>${esc(t("life.interactions.asset_level.vehicle"))}<strong>${esc(compactMoney(snapshot.vehicle_value || 0))}</strong></span></div>
      </div>
      <div class="interaction-asset-pass-progress"><div><span>${esc(t("life.interactions.asset_level.progress", {percent: Math.round(Number(snapshot.progress || 0) * 100)}))}</span><strong>${esc(nextCopy)}</strong></div><div class="interaction-asset-pass-track"><span style="width:${(Math.max(0, Math.min(1, Number(snapshot.progress || 0))) * 100).toFixed(1)}%"></span></div></div>
      <div class="interaction-asset-pass-rail-wrap">
        <button type="button" class="interaction-asset-pass-nav" data-asset-pass-nav="-1" aria-label="${esc(t("life.interactions.asset_level.scroll_prev"))}"><i data-lucide="chevron-left"></i></button>
        <div class="interaction-asset-level-scroll interaction-asset-pass-rail" data-asset-pass-rail tabindex="0" aria-label="${esc(t("life.interactions.asset_level.pass_hint"))}">
          <div class="interaction-asset-pass-rail-track">${cards}</div>
        </div>
        <button type="button" class="interaction-asset-pass-nav" data-asset-pass-nav="1" aria-label="${esc(t("life.interactions.asset_level.scroll_next"))}"><i data-lucide="chevron-right"></i></button>
      </div>
      <p class="interaction-asset-pass-hint"><i data-lucide="hand"></i>${esc(t("life.interactions.asset_level.pass_hint"))}</p>
      ${state.claimError ? `<p class="interaction-asset-pass-error" role="alert"><i data-lucide="circle-alert"></i>${esc(state.claimError)}</p>` : ""}
    </section>`;
  }

  function bindAssetPass(content) {
    const rail = content.querySelector("[data-asset-pass-rail]");
    if (!rail) return;
    let drag = null;
    rail.addEventListener("pointerdown", (event) => {
      if (event.pointerType !== "mouse" || event.button !== 0) return;
      if (event.target.closest("button, a, input, select, textarea, [role='button']")) return;
      drag = { x: event.clientX, left: rail.scrollLeft };
      rail.classList.add("is-dragging");
      rail.setPointerCapture?.(event.pointerId);
      event.preventDefault();
    });
    rail.addEventListener("pointermove", (event) => {
      if (!drag) return;
      rail.scrollLeft = drag.left - (event.clientX - drag.x);
    });
    const endDrag = (event) => {
      if (!drag) return;
      drag = null;
      rail.classList.remove("is-dragging");
      try { rail.releasePointerCapture?.(event.pointerId); } catch (_error) {}
    };
    rail.addEventListener("pointerup", endDrag);
    rail.addEventListener("pointercancel", endDrag);
    rail.addEventListener("wheel", (event) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
      rail.scrollLeft += event.deltaY;
      event.preventDefault();
    }, { passive: false });
    rail.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      rail.scrollBy({ left: (event.key === "ArrowLeft" ? -1 : 1) * rail.clientWidth * 0.8, behavior: "smooth" });
      event.preventDefault();
    });
    content.querySelectorAll("[data-asset-pass-nav]").forEach((button) => {
      button.addEventListener("click", () => {
        rail.scrollBy({
          left: Number(button.dataset.assetPassNav || 1) * rail.clientWidth * 0.8,
          behavior: "smooth",
        });
      });
    });
    const centerCurrent = () => {
      const current = rail.querySelector(".is-current");
      if (!current) return;
      const target = Math.max(
        0,
        current.offsetLeft - (rail.clientWidth - current.offsetWidth) / 2,
      );
      const previous = rail.style.scrollBehavior;
      rail.style.scrollBehavior = "auto";
      rail.scrollLeft = target;
      rail.style.scrollBehavior = previous;
    };
    centerCurrent();
    requestAnimationFrame(centerCurrent);
    window.setTimeout(centerCurrent, 120);
  }

  function renderAssetLevelDialog() {
    const content = document.getElementById("life-interactions-asset-level-content");
    if (!content) return;
    content.innerHTML = renderAssetLevelTimeline(state.data);
    bridge()?.renderIcons(content);
    bindAssetPass(content);
  }

  function openAssetLevelDialog() {
    const dialog = assetLevelDialog();
    if (!dialog) return;
    state.claimError = "";
    renderAssetLevelDialog();
    if (!dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    requestAnimationFrame(() => {
      dialog.querySelector(".interaction-asset-level-scroll")?.focus?.();
    });
  }

  async function claimAssetLevel(level) {
    if (!Number(level) || state.requestBusy) return;
    state.requestBusy = true;
    state.claimLevel = Number(level);
    state.claimError = "";
    if (assetLevelDialog()?.open) renderAssetLevelDialog();
    try {
      const response = await postJson("/api/life/interactions/asset-level/claim", {
        level: Number(level),
      });
      if (applyLifeView(response)) {
        paintWorkspace();
      } else {
        await loadInteractions({ announce: false });
      }
      bridge()?.toast(t("life.interactions.asset_level.claim_success", {
        name: String(response?.vehicle?.name || t("life.interactions.asset_level.car_reward")),
      }));
    } catch (error) {
      const detail = String(error?.message || "");
      state.claimError = /空位|车位|space|garage|platz|vaga|lugar|место/i.test(detail)
        ? t("life.interactions.asset_level.claim_no_space")
        : localizedError(error);
      bridge()?.toast(state.claimError);
    } finally {
      state.requestBusy = false;
      state.claimLevel = 0;
      if (assetLevelDialog()?.open) renderAssetLevelDialog();
    }
  }

  function closeAssetLevelDialog() {
    const dialog = assetLevelDialog();
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  function renderOverview(data) {
    const profile = data.profile || {};
    const points = data.action_points || {};
    const summary = data.summary || {};
    const profileName = String(profile.name || t("life.interactions.profile.unnamed"));
    const gender = ["male", "female", "nonbinary"].includes(String(profile.gender || "male"))
      ? String(profile.gender || "male") : "male";
    const attributes = profileAttributeSource(profile);
    const progress = Math.max(0, Math.min(100, Number(points.current || 0) / Math.max(1, Number(points.maximum || 12)) * 100));
    const apCosts = points.costs || {};
    const apCostItems = [
      ["life.interactions.ap.cost.chat", apCosts.chat ?? 1],
      ["life.interactions.ap.cost.gift", apCosts.gift ?? 1],
      ["life.interactions.ap.cost.asset_gift", apCosts.asset_gift ?? 1],
      ["life.interactions.ap.cost.date", `${Number(apCosts.date_min ?? 2)}-${Number(apCosts.date_max ?? 4)}`],
      ["life.interactions.ap.cost.relationship", apCosts.relationship ?? 3],
    ];
    const recoveryCopy = points.is_full
      ? t("life.interactions.ap.full")
      : t("life.interactions.ap.next_gain", {
        days: Number(points.days_until_recovery || 7),
        gain: Number(points.next_recovery_gain || 0),
      });
    const fullCopy = points.is_full
      ? ""
      : t("life.interactions.ap.full_in", {days: Number(points.days_until_full || 0)});
    const selected = selectedRow();
    const quick = [
      ["people", "life.interactions.tabs.people", "heart-handshake", summary.relationships || 0],
      ["search", "life.interactions.tabs.search", "user-round-search", summary.people || 0],
      ["assets", "life.interactions.tabs.assets", "landmark", Number(data.assets?.properties?.length || 0) + Number(data.assets?.vehicles?.length || 0)],
      ["timeline", "life.interactions.tabs.timeline", "history", data.timeline?.length || 0],
    ];
    return `${profile.completed ? "" : `<div class="interaction-setup-banner"><div><strong>${esc(t("life.interactions.profile.setup_title"))}</strong><span>${esc(t("life.interactions.profile.setup_body"))}</span></div><button type="button" class="interaction-gold-button" data-interaction-action="edit-profile">${esc(t("life.interactions.profile.create"))}</button></div>`}
      <div class="interaction-summary-grid">
        <article class="interaction-profile-card">
          <span class="interaction-avatar">${esc(initials(profileName))}</span>
          <div class="interaction-profile-copy"><span class="interaction-kicker">${esc(t("life.interactions.profile.dossier"))}</span><div class="interaction-profile-name-row"><h2>${esc(profileName)}</h2><button type="button" class="interaction-asset-level-entry" data-interaction-action="open-asset-level" aria-haspopup="dialog" aria-controls="life-interactions-asset-level-dialog"><i data-lucide="chart-no-axes-column-increasing"></i><span>${esc(t("life.interactions.asset_level.entry", {level: Number(data.asset_level?.current_level || 1)}))}</span></button></div><div class="interaction-profile-meta"><span>${esc(t("life.interactions.profile.age_value", {age: profile.age || 18}))}</span><span>${esc(t(`life.interactions.gender.${gender}`))}</span><span>${esc(t("life.interactions.profile.height_value", {height: profile.height_cm || 180}))}</span><span>${esc(`${t("life.interactions.traits.weight")} ${Number(profile.weight_kg || 75)} kg`)}</span></div><div class="interaction-profile-attribute-strip">${[["appearance", "life.interactions.profile.appearance"], ["ability", "life.interactions.profile.ability"], ["charisma", "life.interactions.profile.charisma"], ["eq", "life.interactions.profile.eq"], ["reputation", "life.interactions.profile.reputation"]].map(([key, labelKey]) => `<span class="${key === "reputation" ? "is-reputation" : ""}" title="${esc(t("life.interactions.profile.reputation_cost", {cost: profileAttributeWeight(key)}))}"><small>${key === "reputation" ? '<i data-lucide="award"></i>' : ""}${esc(t(labelKey))}</small><strong>${Number(attributes[key] || 0)}</strong></span>`).join("")}</div><div class="interaction-profile-points"><span>${esc(t("life.interactions.profile.points_available"))}</span><strong>${Number(profile.points_available || 0)}</strong><small>/ ${Number((profile.points_base || 200) + (profile.points_earned || 0))}</small></div></div>
          <button type="button" class="interaction-gold-button interaction-profile-edit-button" data-interaction-action="edit-profile"><i data-lucide="file-pen-line"></i><span>${esc(t("life.interactions.profile.edit"))}</span></button>
        </article>
        <article class="interaction-energy-card"><div class="interaction-energy-head"><span class="interaction-card-label">${esc(t("life.interactions.ap.title"))}</span><span class="interaction-ap-state ${points.is_full ? "is-full" : ""}">${esc(t(points.is_full ? "life.interactions.ap.full_badge" : "life.interactions.ap.recovering_badge"))}</span></div><div class="interaction-energy-main"><div class="interaction-energy-ring" style="--progress:${progress.toFixed(1)}%"><span>${Number(points.current || 0)}<small>/${Number(points.maximum || 12)}</small></span></div><div class="interaction-energy-copy"><strong>${esc(t("life.interactions.ap.current", {current: Number(points.current || 0), maximum: Number(points.maximum || 12)}))}</strong><span>${esc(recoveryCopy)}</span>${fullCopy ? `<span>${esc(fullCopy)}</span>` : ""}</div></div><div class="interaction-ap-costs"><span class="interaction-card-label">${esc(t("life.interactions.ap.cost_title"))}</span><div class="interaction-ap-cost-grid">${apCostItems.map(([labelKey, value]) => `<span><small>${esc(t(labelKey))}</small><b>${esc(value)} ${esc(AP())}</b></span>`).join("")}</div></div><div class="interaction-ap-actions"><button type="button" class="interaction-secondary interaction-ap-ledger-button" data-interaction-action="open-ap-ledger"><i data-lucide="receipt-text"></i><span>${esc(t("life.interactions.ap.ledger_button"))}</span></button><button type="button" class="interaction-gold-button" data-interaction-action="open-ap-purchase" ${Number(points.purchase_available || 0) > 0 ? "" : "disabled"}><i data-lucide="wallet"></i><span>${esc(t("life.interactions.ap.purchase_button", {price: compactMoney(Number(points.purchase_price || 0))}))}</span></button></div></article>
        <article class="interaction-overview-card"><span class="interaction-card-label">${esc(t("life.interactions.summary.title"))}</span><div class="interaction-stat-grid">${[["people", summary.people], ["friends", summary.friends], ["partners", summary.partners], ["secret_lovers", summary.secret_lovers], ["residents", summary.residents], ["gifted_assets", summary.gifted_assets]].map(([key, value]) => `<div class="interaction-stat"><strong>${Number(value || 0)}</strong><span>${esc(t(`life.interactions.summary.${key}`))}</span></div>`).join("")}</div></article>
      </div>
      ${renderPendingEvents(data)}
      <div class="interaction-overview-grid">
        <section class="interaction-panel"><header class="interaction-panel-head"><div><h2>${esc(t("life.interactions.overview.quick"))}</h2></div></header><div class="interaction-quick-grid">${quick.map(([tab, labelKey, icon, count]) => `<button type="button" class="interaction-quick-card" data-interaction-tab="${tab}"><i data-lucide="${icon}"></i><strong>${esc(t(labelKey))}</strong><span>${Number(count || 0)}</span></button>`).join("")}</div></section>
        <section class="interaction-panel"><header class="interaction-panel-head"><div><h2>${esc(t("life.interactions.overview.current"))}</h2></div></header><div class="interaction-panel-body">${selected ? `<button type="button" class="interaction-current-person" data-interaction-person-select="${Number(selected.person.id || 0)}">${portraitMarkup(selected.person, {small: true})}<span><strong>${esc(selected.person.name || "")}</strong><small>${esc(personAffiliation(selected.person))}</small></span>${stageBadge(selected.relationship)}</button>` : `<div class="interaction-empty compact"><i data-lucide="user-round-search"></i><span>${esc(t("life.interactions.relationship.select_person"))}</span></div>`}</div></section>
      </div>
      ${renderRelationshipNetwork(data)}`;
  }

  function renderDimensions(relationship) {
    return `<div class="interaction-dimension-grid">${DIMENSIONS.map(([key, labelKey]) => {
      const value = Math.max(0, Math.min(100, Number(relationship?.[key] || relationship?.dimensions?.[key] || 0)));
      return `<div class="interaction-dimension"><div class="interaction-dimension-head"><span>${esc(t(labelKey))}</span><strong>${value.toFixed(0)}</strong></div><div class="interaction-meter"><span style="width:${value.toFixed(1)}%"></span></div></div>`;
    }).join("")}</div>`;
  }

  function optionLabel(prefix, value) {
    const key = `${prefix}.${String(value || "")}`;
    return translated(key) || String(value || "");
  }

  function traitChips(items, prefix) {
    return (items || []).map((value) => `<span>${esc(optionLabel(prefix, value))}</span>`).join("");
  }

  function renderPersonTraits(person) {
    const traits = person?.traits || {};
    const likes = traits.likes || {};
    const dislikes = traits.dislikes || {};
    const disclosure = traits.disclosure || {};
    const level = Math.max(0, Math.min(3, Number(disclosure.level || 0)));
    const measurements = traits.measurements || {};
    const ranges = traits.measurement_ranges || {};
    const exactMeasurementRows = [["bust_cm", "bust"], ["waist_cm", "waist"], ["hips_cm", "hips"]]
      .filter(([key]) => measurements[key]);
    const rangeRows = [["bust_cm", "bust"], ["waist_cm", "waist"], ["hips_cm", "hips"]]
      .filter(([key]) => ranges[key]);
    const measurementMarkup = exactMeasurementRows.length
      ? `<div class="interaction-trait-block is-measurement"><small>${esc(t("life.interactions.traits.measurements"))}<b>${esc(t("life.interactions.traits.measurements_exact"))}</b></small><div class="interaction-chip-row">${exactMeasurementRows.map(([key, label]) => `<span>${esc(t(`life.interactions.traits.${label}`))} ${Number(measurements[key])} cm</span>`).join("")}</div></div>`
      : rangeRows.length
        ? `<div class="interaction-trait-block is-measurement"><small>${esc(t("life.interactions.traits.measurements"))}<b>${esc(t("life.interactions.traits.measurements_range"))}</b></small><div class="interaction-chip-row">${rangeRows.map(([key, label]) => `<span>${esc(t(`life.interactions.traits.${label}`))} ${Number(ranges[key].minimum)}–${Number(ranges[key].maximum)} cm</span>`).join("")}</div><p class="interaction-trait-hint">${esc(t("life.interactions.traits.measurement_hint", {cm: Number(traits.measurement_precision_cm || 0)}))}</p></div>`
        : "";
    const personalityVisible = Number(disclosure.personality_visible ?? (traits.personality || []).length);
    const personalityTotal = Number(disclosure.personality_total ?? personalityVisible);
    const valuesVisible = Number(disclosure.values_visible ?? (traits.values || []).length);
    const valuesTotal = Number(disclosure.values_total ?? valuesVisible);
    const likesVisible = Number(disclosure.likes_visible_per_group ?? 3);
    const likesTotal = Number(disclosure.likes_total_per_group ?? 3);
    const locked = (count) => count > 0
      ? `<span class="interaction-locked-chip"><i data-lucide="lock-keyhole"></i>${esc(t("life.interactions.traits.locked_remaining", {count}))}</span>` : "";
    return `<section class="interaction-trait-panel">
      <header><div><span class="interaction-kicker">${esc(t("life.interactions.traits.title"))}</span><h3>${esc(t("life.interactions.traits.disclosure_title"))}</h3></div><span class="interaction-disclosure-badge level-${level}">${esc(t(`life.interactions.traits.disclosure_level.${level}`))}</span></header>
      <div class="interaction-disclosure-meter" aria-hidden="true">${[0, 1, 2, 3].map((step) => `<span class="${step <= level ? "active" : ""}"></span>`).join("")}</div>
      <div class="interaction-trait-fact-grid"><div><small>${esc(t("life.interactions.traits.height"))}</small><strong>${Number(person?.height_cm || traits.height_cm || 0)} cm</strong></div><div><small>${esc(t("life.interactions.traits.weight"))}</small><strong>${Number(person?.weight_kg || traits.weight_kg || 0)} kg</strong></div><div><small>${esc(t("life.interactions.traits.personality"))}</small><strong>${personalityVisible}/${personalityTotal}</strong></div><div><small>${esc(t("life.interactions.traits.values"))}</small><strong>${valuesVisible}/${valuesTotal}</strong></div></div>
      <div class="interaction-trait-block"><small>${esc(t("life.interactions.traits.personality"))}</small><div class="interaction-chip-row">${traitChips(traits.personality, "life.interactions.personality")}${locked(personalityTotal - personalityVisible)}</div></div>
      <div class="interaction-trait-block"><small>${esc(t("life.interactions.traits.values"))}</small><div class="interaction-chip-row">${valuesVisible ? traitChips(traits.values, "life.interactions.value") : `<span class="interaction-locked-chip"><i data-lucide="lock-keyhole"></i>${esc(t("life.interactions.traits.values_locked"))}</span>`}${locked(valuesTotal - valuesVisible)}</div></div>
      <div class="interaction-trait-block"><small>${esc(t("life.interactions.traits.likes"))}</small><div class="interaction-like-groups"><span><b>${esc(t("life.interactions.traits.topics"))}</b>${traitChips(likes.topics, "life.interactions.topic")}</span><span><b>${esc(t("life.interactions.traits.activities"))}</b>${traitChips(likes.activities, "life.interactions.activity")}</span><span><b>${esc(t("life.interactions.traits.gifts"))}</b>${traitChips(likes.gifts, "life.interactions.gift_category")}</span></div>${likesVisible < likesTotal ? `<p class="interaction-trait-hint">${esc(t("life.interactions.traits.likes_hint", {count: likesVisible, total: likesTotal}))}</p>` : ""}</div>
      <div class="interaction-trait-block"><small>${esc(t("life.interactions.traits.dislikes"))}</small><div class="interaction-like-groups"><span>${traitChips(dislikes.activities, "life.interactions.activity")}</span><span>${traitChips(dislikes.gifts, "life.interactions.gift_category")}</span></div>${disclosure.dislikes_visible ? "" : `<p class="interaction-trait-hint">${esc(t("life.interactions.traits.dislikes_locked"))}</p>`}</div>
      ${measurementMarkup}
    </section>`;
  }

  function renderDossier(data, row) {
    if (!row) return `<div class="interaction-empty"><i data-lucide="user-round-search"></i><span>${esc(t("life.interactions.relationship.select_person"))}</span></div>`;
    const person = row.person || {};
    const relationship = row.relationship || {};
    const positions = Array.isArray(person.positions) ? person.positions.slice(0, 5).join(" · ") : "";
    const encounterPerson = isEncounterPerson(person);
    const chips = [
      t("life.interactions.age_short", {age: person.age || 0}),
      personAffiliation(person),
      personNationality(person),
      positions,
      !encounterPerson && person.ca != null ? `CA ${person.ca}` : "",
      !encounterPerson && person.pa != null ? `PA ${person.pa}` : "",
      !encounterPerson ? `${t("life.interactions.reputation_short")} ${person.world_reputation ?? 0}` : "",
    ].filter(Boolean);
    return `<article class="interaction-dossier-card"><header class="interaction-dossier-hero">${portraitMarkup(person)}<div class="interaction-dossier-copy"><span class="interaction-kicker">${esc(t("life.interactions.dossier.title"))}</span><h2>${esc(person.name || person.id || "")}${person.id ? `<span class="interaction-person-uid">UID ${Number(person.id)}</span>` : ""}</h2><p>${esc(personAffiliation(person))}</p><div class="interaction-dossier-chips">${chips.map((chip) => `<span>${esc(chip)}</span>`).join("")}</div></div><div class="interaction-dossier-hero-actions">${stageBadge(relationship)}<button type="button" class="interaction-secondary" data-interaction-refresh-person="${Number(person.id || 0)}"><i data-lucide="refresh-cw"></i><span>${esc(t("life.interactions.refresh_person"))}</span></button></div></header><div class="interaction-dossier-grid"><section class="interaction-dossier-main">${renderPersonTraits(person)}<div class="interaction-preference-box"><strong>${esc(t("life.interactions.preference.title"))}</strong><div class="interaction-chip-row">${preferenceChips(relationship)}</div></div></section><aside class="interaction-dossier-side"><section class="interaction-relationship-panel"><h3>${esc(t("life.interactions.relationship.stage_title"))}</h3><p>${esc(t("life.interactions.relationship.stage_detail"))}</p>${renderDimensions(relationship)}</section></aside></div></article>`;
  }

  function renderRelationshipList(data) {
    const rows = data.relationships || [];
    return `<section class="interaction-panel interaction-people-panel"><header class="interaction-panel-head"><div><h2>${esc(t("life.interactions.relationship.title"))}</h2><p>${esc(t("life.interactions.relationship.count", {count: rows.length}))}</p></div></header><div class="interaction-panel-body"><div class="interaction-relation-list">${rows.length ? rows.map((row) => {
      const person = row.person || {};
      const relationship = row.relationship || {};
      const id = Number(person.id || 0);
      const affection = Math.round(Number(relationship.affection || 0));
      return `<div class="interaction-relation-row ${id === state.selectedId ? "selected" : ""}"><button type="button" class="interaction-relation-main" data-interaction-person-select="${id}">${portraitMarkup(person, {small: true})}<span class="interaction-relation-copy"><strong>${esc(person.name || id)}</strong><span>${esc(personAffiliation(person))}</span><span class="interaction-relation-stage">${stageBadge(relationship)}</span></span><span class="interaction-relation-affection tone-${affectionTone(affection)}">${affection}<small>${esc(t("life.interactions.dimension.affection_short"))}</small></span></button><button type="button" class="interaction-relation-delete" data-interaction-remove="${id}" aria-label="${esc(t("life.interactions.relationship.delete_contact_for", {name: person.name || id}))}" title="${esc(t("life.interactions.relationship.delete_contact"))}"><i data-lucide="user-round-x"></i></button></div>`;
    }).join("") : `<div class="interaction-empty compact"><i data-lucide="heart-handshake"></i><span>${esc(t("life.interactions.relationship.empty"))}</span></div>`}</div></div></section>`;
  }

  function renderPeople(data) {
    const row = selectedRow();
    const detail = state.peopleTab === "interaction"
      ? renderInteractionPanel(data, row)
      : state.peopleTab === "owned"
        ? renderOwnedAssets(data, row)
        : renderDossier(data, row);
    return `<div class="interaction-people-layout">${renderRelationshipList(data)}<section class="interaction-panel interaction-people-detail">${renderTabs(data, "people")}<div class="interaction-people-content">${detail}</div></section></div>`;
  }

  function requirementLabel(requirement) {
    const key = String(requirement?.key || "");
    if (key === "social_stage") return t("life.interactions.requirement.social_stage");
    if (key === "bond_stage") return t("life.interactions.requirement.bond_stage");
    if (key === "romance_stage") return t("life.interactions.requirement.romance_stage");
    return translated(`life.interactions.dimension.${key}`) || key;
  }

  function stageLabel(stage) {
    return stage ? t(`life.interactions.social.${SOCIAL_KEYS[stage] || stage}`) : "";
  }

  function levelLabel(level) {
    const key = `life.interactions.level.${String(level || "")}`;
    const value = t(key);
    return value === key ? stageLabel(String(level || "")) : value;
  }

  function bondStageLabel(stage) {
    const key = `life.interactions.level.${String(stage || "")}`;
    const value = t(key);
    return value === key ? String(stage || "") : value;
  }

  function toneLabel(key) {
    const lookup = `life.interactions.tone.${String(key || "")}`;
    const value = t(lookup);
    return value === lookup ? String(key || "") : value;
  }

  function branchLineLabel(line) {
    const key = `life.interactions.branch.line.${String(line || "")}`;
    const value = t(key);
    return value === key ? String(line || "") : value;
  }

  function romanceStageLabel(stage) {
    if (stage === "secret_lover") return t("life.interactions.romance.secret_lover");
    return stage ? t(`life.interactions.romance.${ROMANCE_KEYS[stage] || stage}`) : "";
  }

  function requirementValue(requirement) {
    if (String(requirement?.key || "") === "social_stage") {
      return `${stageLabel(String(requirement.current || "acquaintance"))} → ${stageLabel(String(requirement.required || "friend"))}`;
    }
    if (String(requirement?.key || "") === "bond_stage") {
      return `${bondStageLabel(String(requirement.current || "none"))} → ${bondStageLabel(String(requirement.required || "partner"))}`;
    }
    if (String(requirement?.key || "") === "romance_stage") {
      return `${romanceStageLabel(String(requirement.current || "none"))} → ${romanceStageLabel(String(requirement.required || "ambiguous"))}`;
    }
    return t("life.interactions.requirement.progress_label", {
      current: Number(requirement?.current || 0).toFixed(1),
      required: Number(requirement?.required || 0).toFixed(1),
    });
  }

  function requirementPercent(requirement) {
    if (String(requirement?.key || "") === "social_stage") return requirement?.met ? 100 : 0;
    return Math.max(0, Math.min(100, Number(requirement?.current || 0) / Math.max(1, Number(requirement?.required || 0)) * 100));
  }

  function renderProgressBlock(block, titleKey, icon, stageType) {
    const requirements = Array.isArray(block?.requirements) ? block.requirements : [];
    const met = requirements.filter((row) => row.met).length;
    const target = block?.next
      ? stageType === "romance" ? romanceStageLabel(String(block.next))
        : stageType === "bond" ? bondStageLabel(String(block.next))
          : stageLabel(String(block.next))
      : "";
    return `<article class="interaction-progress-block ${block?.ready ? "is-ready" : ""}">
      <header><span><i data-lucide="${icon}"></i><strong>${esc(t(titleKey))}</strong></span><span class="interaction-badge ${block?.ready ? "friend" : ""}">${esc(t(block?.maxed ? "life.interactions.relationship.max_stage" : block?.ready ? "life.interactions.relationship.ready_badge" : "life.interactions.relationship.locked_badge"))}</span></header>
      ${block?.maxed ? `<div class="interaction-progress-complete"><i data-lucide="badge-check"></i><span>${esc(t("life.interactions.relationship.max_stage"))}</span></div>` : `<div class="interaction-progress-target"><span><small>${esc(t("life.interactions.relationship.next_stage", {stage: target}))}</small><strong>${esc(target)}</strong></span><b>${esc(t("life.interactions.relationship.requirements_progress", {met, total: requirements.length}))}</b></div><div class="interaction-progress-meter" aria-hidden="true"><span style="width:${(requirements.length ? met / requirements.length * 100 : 0).toFixed(1)}%"></span></div><ul class="interaction-progress-requirements">${requirements.map((requirement) => `<li class="${requirement.met ? "met" : ""}"><div><span>${esc(requirementLabel(requirement))}</span><small>${esc(requirementValue(requirement))}</small></div><span class="interaction-progress-bar"><i style="width:${requirementPercent(requirement).toFixed(1)}%"></i></span><b><i data-lucide="${requirement.met ? "check" : "lock-keyhole"}"></i>${esc(t(requirement.met ? "life.interactions.requirement.met" : "life.interactions.requirement.unmet"))}</b></li>`).join("")}</ul>`}
    </article>`;
  }

  function relationshipActions(data, row, {destructive = false} = {}) {
    const relationship = row?.relationship || {};
    const options = (Array.isArray(relationship.options) ? relationship.options : [])
      .filter((option) => {
        const target = String(option.target || "");
        const isDestructive = target === "breakup" || target === "divorce";
        if (!destructive && option.branch) return false;
        return destructive ? isDestructive : !isDestructive;
      });
    return `<div class="interaction-action-row interaction-relationship-actions">${options.map((option) => {
      const target = String(option.target || "");
      const danger = target === "breakup" || target === "divorce";
      const unavailable = !option.available || !actionPointsReady(data, option.cost || 0);
      const ringNote = target === "spouse"
        ? `<em class="${state.data?.proposal_ring?.ready ? "is-ring-ready" : "is-ring-missing"}">${esc(t(state.data?.proposal_ring?.ready ? "life.interactions.relationship.ring_ready" : "life.interactions.relationship.ring_missing"))}</em>`
        : "";
      return `<button type="button" class="${danger ? "interaction-danger" : "interaction-secondary"}" data-interaction-relationship="${esc(target)}" data-interaction-person="${Number(row.person?.id || 0)}" ${unavailable ? "disabled" : ""}><span>${esc(t(`life.interactions.relationship.action.${target}`))}</span><small>${Number(option.cost || 0)} ${esc(AP())}</small>${!option.available ? `<em>${esc(t("life.interactions.relationship.option_unavailable"))}</em>` : ""}${ringNote}</button>`;
    }).join("") || (destructive ? "" : `<span class="interaction-inline-note">${esc(t("life.interactions.relationship.no_actions"))}</span>`)}</div>`;
  }

  function giftGroups(data) {
    const grouped = new Map();
    for (const item of Array.isArray(data?.items) ? data.items : []) {
      const id = String(item?.id || "");
      if (!id) continue;
      const key = [item.sku || item.name || id, item.category || "", Number(item.value || 0)].join("|");
      const existing = grouped.get(key);
      if (existing) {
        existing.count += 1;
      } else {
        grouped.set(key, {...item, id, count: 1});
      }
    }
    return Array.from(grouped.values());
  }

  const DATE_ICONS = Object.freeze({
    cafe: "coffee", walk: "trees", cinema: "clapperboard", museum: "landmark",
    dinner: "utensils", sports: "trophy", concert: "music", trip: "plane",
  });
  const GIFT_ICONS = Object.freeze({
    book: "book-open", fashion: "shirt", technology: "cpu", food: "utensils",
    sport: "trophy", music: "music", art: "palette", luxury: "gem",
  });

  function canInviteToDate(relationship) {
    const key = String(relationship?.level || relationship?.social_stage || relationship?.romance_stage || "acquaintance");
    return [
      "friend", "close_friend", "confidant", "partner", "kindred",
      "best_friend", "brother", "sworn_brother",
      // A committed romance or marriage should always allow a date even when
      // the social stage has not been refreshed yet.
      "ambiguous", "couple", "secret_lover", "spouse",
    ].includes(key);
  }

  function renderInteractionHome(data, row) {
    const person = row.person || {};
    const relationship = row.relationship || {};
    const gifts = giftGroups(data);
    const giftCount = gifts.reduce((sum, item) => sum + item.count, 0);
    const activities = Array.isArray(data.options?.date_activities) ? data.options.date_activities : [];
    const dateUnlocked = canInviteToDate(relationship);
    const dateCosts = activities.map((activity) => Number(activity.cost || 0));
    const dateCost = dateCosts.length ? Math.min(...dateCosts) : 0;
    const dateReady = dateUnlocked && activities.length > 0 && actionPointsReady(data, dateCost);
    return `<section class="interaction-relationship-panel interaction-home-summary"><header><div><h3>${esc(t("life.interactions.interaction_home.title"))}</h3><p>${esc(t("life.interactions.relationship.home_detail"))}</p></div><span class="interaction-ap-note"><i data-lucide="zap"></i><span>${esc(t("life.interactions.interaction_home.ap", {current: Number(data.action_points?.current || 0), maximum: Number(data.action_points?.maximum || 12)}))}</span></span></header>${renderDimensions(relationship)}</section>
      <div class="interaction-action-grid interaction-action-grid--three">
        <article class="interaction-action-card"><div class="interaction-action-card-head"><span class="interaction-action-icon"><i data-lucide="message-circle-more"></i></span><h3>${esc(t("life.interactions.chat.title"))}</h3></div><p>${esc(t("life.interactions.chat.detail"))}</p><button type="button" class="interaction-choice-launch interaction-chat-launch" data-interaction-action="open-chat" ${actionPointsReady(data, 1) ? "" : "disabled"}><span><i data-lucide="messages-square"></i><strong>${esc(t("life.interactions.chat.open"))}</strong><small>${esc(t("life.interactions.chat.open_detail"))}</small></span><i data-lucide="chevron-right"></i></button></article>
        <article class="interaction-action-card"><div class="interaction-action-card-head"><span class="interaction-action-icon"><i data-lucide="gift"></i></span><h3>${esc(t("life.interactions.gift.title"))}</h3></div><p>${esc(t("life.interactions.gift.detail"))}</p><button type="button" class="interaction-choice-launch" data-interaction-action="open-gift-picker" ${gifts.length && actionPointsReady(data, 1) ? "" : "disabled"}><span><i data-lucide="package-open"></i><strong>${esc(gifts.length ? t("life.interactions.gift.choose") : t("life.interactions.gift.empty"))}</strong><small>${esc(gifts.length ? t("life.interactions.gift.stock_summary", {count: giftCount}) : t("life.interactions.interaction_home.gift_empty"))}</small></span><i data-lucide="chevron-right"></i></button><button type="button" class="interaction-secondary interaction-gift-shop-link" data-interaction-action="open-gift-shop"><i data-lucide="shopping-bag"></i><span>${esc(t("life.interactions.interaction_home.gift_shop"))}</span></button></article>
        <article class="interaction-action-card"><div class="interaction-action-card-head"><span class="interaction-action-icon"><i data-lucide="calendar-heart"></i></span><h3>${esc(t("life.interactions.date.title"))}</h3></div><p>${esc(t("life.interactions.date.detail"))}</p><button type="button" class="interaction-choice-launch" data-interaction-action="open-date-picker" ${dateReady ? "" : "disabled"}><span><i data-lucide="sparkles"></i><strong>${esc(dateUnlocked ? t("life.interactions.date.choose") : t("life.interactions.date.requires_friend"))}</strong><small>${esc(dateUnlocked ? t("life.interactions.date.activity_summary", {count: activities.length, min: dateCost, max: dateCosts.length ? Math.max(...dateCosts) : 0}) : t("life.interactions.date.requires_friend_detail"))}</small></span><i data-lucide="chevron-right"></i></button></article>
      </div>
      <button type="button" class="interaction-money-entry" data-interaction-action="open-money-gift"><span class="interaction-money-entry-icon"><i data-lucide="banknote"></i></span><span><strong>${esc(t("life.interactions.money_gift.title"))}</strong><small>${esc(t("life.interactions.money_gift.detail"))}</small></span><i data-lucide="chevron-right"></i></button>
      <button type="button" class="interaction-progress-cta" data-interaction-mode-tab="progress"><span><i data-lucide="route"></i><span><strong>${esc(t("life.interactions.interaction_home.progress_cta"))}</strong><small>${esc(t("life.interactions.interaction_home.progress_cta_detail"))}</small></span></span><i data-lucide="chevron-right"></i></button>`;
  }

  function renderBranchPanel(data, relationship) {
    const progress = relationship?.social_progress || {};
    const branch = progress.branch || {};
    const options = Array.isArray(branch.options) ? branch.options : [];
    if (!options.length && (!branch.path || branch.path === "none")) return "";
    const chosen = branch.path && branch.path !== "none"
      ? `<span class="interaction-branch-chosen">${esc(levelLabel(String(progress.level || branch.level || "")))}${branch.line ? ` · ${esc(branchLineLabel(String(branch.line)))}` : ""}</span>`
      : `<span class="interaction-branch-chosen">${esc(t("life.interactions.branch.unselected"))}</span>`;
    const cards = options.map((option) => {
      const target = String(option.target || "");
      const requirements = Array.isArray(option.requirements) ? option.requirements : [];
      const met = requirements.filter((item) => item.met).length;
      const label = translated(`life.interactions.relationship.action.${target}`) || target;
      const detailTarget = (
        target === "bond_partner_brotherhood"
        && String(option.variant || "") === "brotherhood_kindred"
      ) ? `${target}_kindred` : target;
      const detail = translated(`life.interactions.branch.option.${detailTarget}`)
        || t("life.interactions.branch.requirements", {met, total: requirements.length});
      const disabled = !option.available || !option.ready || !actionPointsReady(data, option.cost || 3);
      return `<button type="button" class="interaction-branch-option ${option.ready ? "is-ready" : ""}" data-interaction-relationship="${esc(target)}" data-interaction-person="${Number(relationship?.person_id || 0)}" ${disabled ? "disabled" : ""}><span><strong>${esc(label)}</strong><small>${esc(detail)}</small></span><em>${Number(option.cost || 3)} ${esc(AP())}</em></button>`;
    }).join("");
    return `<section class="interaction-branch-panel"><header><div><h3>${esc(t("life.interactions.branch.title"))}</h3><p>${esc(t("life.interactions.branch.detail"))}</p></div>${chosen}</header>${cards ? `<div class="interaction-branch-grid">${cards}</div>` : ""}</section>`;
  }

  function renderRelationshipProgress(data, row) {
    const relationship = row.relationship || {};
    const progress = relationship.social_progress || {};
    const relationshipOptions = Array.isArray(relationship.options) ? relationship.options : [];
    const hasDanger = relationshipOptions.some((option) => ["breakup", "divorce"].includes(String(option.target || "")));
    const showRomance = progress.romance && (
      String(progress.romance.current || "none") !== "none"
      || (progress.branch?.path !== "bond" && progress.romance.available)
    );
    const showBond = progress.bond && (
      String(progress.bond.current || "none") !== "none"
      || (progress.branch?.path !== "romance" && progress.bond.available)
    );
    return `<div class="interaction-progress-layout">${renderBranchPanel(data, relationship)}${renderProgressBlock(progress.social, "life.interactions.relationship.social_heading", "users-round", "social")}${showRomance ? renderProgressBlock(progress.romance, "life.interactions.relationship.romance_heading", "heart", "romance") : ""}${showBond ? renderProgressBlock(progress.bond, "life.interactions.relationship.bond_heading", "handshake", "bond") : ""}</div>
      <section class="interaction-relationship-panel interaction-relationship-progress-actions"><header><div><h3>${esc(t("life.interactions.relationship.progress_route"))}</h3><p>${esc(t("life.interactions.relationship.progress_detail"))}</p></div></header>${relationshipActions(data, row)}${hasDanger ? `<details class="interaction-more-actions"><summary><i data-lucide="ellipsis"></i><span>${esc(t("life.interactions.relationship.more_actions"))}</span></summary><div class="interaction-danger-drawer"><strong>${esc(t("life.interactions.relationship.danger_zone"))}</strong>${relationshipActions(data, row, {destructive: true})}</div></details>` : ""}</section>`;
  }

  function gameDayMonth(day) {
    const ordinal = Number(day || 0);
    if (!ordinal) return "—";
    const date = new Date(Date.UTC(1970, 0, 1) + (ordinal - 719163) * 86400000);
    return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
  }

  function intimacyHistoryMarkup(history) {
    if (!history.length) {
      return `<span class="interaction-inline-note">${esc(t("life.interactions.intimacy.history_empty"))}</span>`;
    }
    const months = new Map();
    for (const item of history) {
      const month = gameDayMonth(item.day);
      if (!months.has(month)) months.set(month, []);
      months.get(month).push(item);
    }
    return [...months.entries()].map(([month, rows]) => {
      const records = rows.map((item) => {
        const result = item.result || {};
        const before = Number(result.intimacy_before || 0);
        const after = Number(result.intimacy_after || 0);
        const chance = Number(result.pregnancy_chance || 0);
        const dims = DIMENSIONS.map(([key, labelKey]) => {
          const delta = Number(result.deltas?.[key] || 0);
          return delta > 0 ? `<span>${esc(t(labelKey))} +${delta.toFixed(1)}</span>` : "";
        }).filter(Boolean).join("");
        return `<details class="interaction-intimacy-record"><summary><span class="interaction-intimacy-record-icon"><i data-lucide="heart"></i></span><span><strong>${esc(intimacyActionLabel(item.action))}</strong><small>${esc(t("life.interactions.intimacy.history_cost", {value: Number(result.intimacy_cost || 0)}))}</small></span><span class="interaction-intimacy-record-day">${esc(formatGameDay(item.day))}</span></summary><div class="interaction-intimacy-record-body"><dl><div><dt>${esc(t("life.interactions.intimacy.history_before"))}</dt><dd>${before.toFixed(1)}</dd></div><div><dt>${esc(t("life.interactions.intimacy.history_after"))}</dt><dd>${after.toFixed(1)}</dd></div>${chance > 0 ? `<div><dt>${esc(t("life.interactions.intimacy.history_chance"))}</dt><dd>${esc(percent(chance, 1))}</dd></div>` : ""}</dl>${dims ? `<div class="interaction-intimacy-record-deltas">${dims}</div>` : ""}</div></details>`;
      }).join("");
      return `<details class="interaction-intimacy-month" open><summary><span><i data-lucide="calendar-days"></i><strong>${esc(month)}</strong></span><small>${esc(t("life.interactions.intimacy.history_month", {count: rows.length}))}</small></summary><div class="interaction-intimacy-month-body">${records}</div></details>`;
    }).join("");
  }

  function renderIntimacyPanel(data, row) {
    if (!data?.adult_content_enabled) return "";
    const relationship = row.relationship || {};
    if (!isIntimateRelationship(relationship)) {
      return `<div class="interaction-empty"><i data-lucide="heart-off"></i><span>${esc(t("life.interactions.intimacy.requires_commitment"))}</span></div>`;
    }
    const person = row.person || {};
    const value = Math.max(-100, Math.min(100, Number(relationship.intimacy || 0)));
    const magnitude = Math.abs(value);
    const barLeft = value >= 0 ? 50 : 50 - magnitude / 2;
    const barWidth = magnitude / 2;
    const band = String(relationship.intimacy_band || "new");
    const options = Array.isArray(relationship.intimacy_options) ? relationship.intimacy_options : [];
    const stage = String(relationship.effective_romance_stage || relationship.romance_stage || "");
    const history = (data.timeline || []).filter((item) => (
      String(item?.kind || "") === "intimacy"
      && Number(item?.person_id || 0) === Number(person.id || 0)
    ));
    const tab = state.intimacyTab === "history" ? "history" : "actions";
    const itemCounts = {};
    for (const item of (data.items || [])) {
      const sku = String(item?.sku || "");
      if (sku) itemCounts[sku] = (itemCounts[sku] || 0) + 1;
    }
    const cards = options.map((action) => {
      const id = String(action.id || "");
      const blocked = String(action.blocked_reason || "");
      const allowedStages = Array.isArray(action.stages) ? action.stages : [];
      const requiredStage = allowedStages.length === 1 ? allowedStages[0] : "partner";
      const requiredItem = String(action.requires_item || "");
      const hasItem = !requiredItem || Number(itemCounts[requiredItem] || 0) > 0;
      const disabled = !action.available || state.requestBusy || !hasItem;
      const dims = DIMENSIONS.map(([key, labelKey]) => {
        const delta = Number(action.delta_preview?.[key] || 0);
        return delta > 0 ? `<span>${esc(t(labelKey))} +${delta.toFixed(1)}</span>` : "";
      }).filter(Boolean).join("");
      const stageNote = !hasItem
        ? t("life.interactions.intimacy.requires_item", { item: t(`life.interactions.item.${requiredItem}`) })
        : action.available ? "" : blocked === "stage"
        ? t("life.interactions.intimacy.requires_stage", {stage: t(`life.interactions.romance.${ROMANCE_KEYS[requiredStage] || "partner"}`)})
        : t(`life.interactions.intimacy.blocked.${blocked || "unavailable"}`);
      return `<button type="button" class="interaction-intimacy-action" data-interaction-intimate-action="${esc(id)}" data-intimate-action="${esc(id)}" ${disabled ? "disabled" : ""}>
        <span class="interaction-intimacy-action-top"><span class="interaction-intimacy-icon"><i data-lucide="${esc(action.icon || "heart")}"></i></span><span class="interaction-intimacy-action-copy"><strong>${esc(t(`life.interactions.intimacy.action.${id}.title`))}</strong><small>${esc(t(`life.interactions.intimacy.action.${id}.detail`))}</small></span>${action.family_planning ? `<span class="interaction-intimacy-future"><i data-lucide="sprout"></i>${esc(t("life.interactions.intimacy.future_tag"))}</span>` : ""}</span>
        <span class="interaction-intimacy-action-meta"><span class="interaction-intimacy-cost"><i data-lucide="zap"></i>${Number(action.ap_cost || 0)} ${esc(AP())}</span>${requiredItem ? `<span class="interaction-intimacy-cost"><i data-lucide="package"></i>${esc(t("life.interactions.intimacy.item_count", { item: t(`life.interactions.item.${requiredItem}`), count: Number(itemCounts[requiredItem] || 0) }))}</span>` : ""}${Number(action.obedience_gain || 0) > 0 ? `<span class="interaction-intimacy-cost is-obedience"><i data-lucide="crown"></i>+${Number(action.obedience_gain).toFixed(0)} ${esc(t("life.interactions.intimacy.obedience_short"))}</span>` : ""}<span class="interaction-intimacy-cost"><i data-lucide="heart"></i>${Number(action.intimacy_cost || 0)} ${esc(t("life.interactions.intimacy.points_short"))}</span>${Number(action.pregnancy_chance || 0) > 0 ? `<span class="interaction-intimacy-cost is-pregnancy"><i data-lucide="sprout"></i>${esc(t("life.interactions.intimacy.pregnancy_chance", {chance: percent(action.pregnancy_chance, 1)}))}</span>` : ""}</span>
        <span class="interaction-intimacy-deltas">${dims}</span>
        ${stageNote ? `<span class="interaction-intimacy-blocked">${esc(stageNote)}</span>` : `<span class="interaction-intimacy-ready">${esc(t("life.interactions.intimacy.ready", {value: Math.round(Number(action.intimacy_after || 0))}))}</span>`}
      </button>`;
    }).join("");
    const subTabs = `<nav class="interaction-intimacy-subtabs" role="tablist"><button type="button" class="${tab === "actions" ? "active" : ""}" data-interaction-intimacy-tab="actions" role="tab" aria-selected="${tab === "actions"}"><i data-lucide="heart-handshake"></i>${esc(t("life.interactions.intimacy.tabs.actions"))}</button><button type="button" class="${tab === "history" ? "active" : ""}" data-interaction-intimacy-tab="history" role="tab" aria-selected="${tab === "history"}"><i data-lucide="history"></i>${esc(t("life.interactions.intimacy.tabs.history"))}<span class="interaction-badge">${history.length}</span></button></nav>`;
    const protection = `<div class="interaction-intimacy-protection"><label><span>${esc(t("life.interactions.intimacy.protection"))}</span><select data-intimacy-protection><option value="">${esc(t("life.interactions.intimacy.protection_none"))}</option><option value="condom">${esc(t("life.interactions.intimacy.protection_condom", { count: Number(itemCounts.intimate_condoms || 0) }))}</option><option value="pill">${esc(t("life.interactions.intimacy.protection_pill", { count: Number(itemCounts.intimate_pills || 0) }))}</option></select></label><small>${esc(t("life.interactions.intimacy.protection_hint"))}</small></div>`;
    const actionsPanel = `<section class="interaction-relationship-panel interaction-intimacy-actions"><header><div><h3>${esc(t("life.interactions.intimacy.actions_title"))}</h3><p>${esc(t("life.interactions.intimacy.actions_detail"))}</p></div></header>${protection}<div class="interaction-intimacy-grid">${cards || `<div class="interaction-empty compact"><i data-lucide="heart-off"></i><span>${esc(t("life.interactions.intimacy.empty"))}</span></div>`}</div></section>`;
    const historyPanel = `<section class="interaction-relationship-panel interaction-intimacy-history"><header><div><h3>${esc(t("life.interactions.intimacy.history_title"))}</h3><p>${esc(t("life.interactions.intimacy.history_detail"))}</p></div><span class="interaction-badge">${history.length}</span></header><div class="interaction-intimacy-month-list">${intimacyHistoryMarkup(history)}</div></section>`;
    return `<div class="interaction-intimacy-layout">
      <section class="interaction-intimacy-hero">
        <div class="interaction-intimacy-hero-head">${portraitMarkup(person, {small: true})}<div><span class="interaction-kicker">${esc(t("life.interactions.intimacy.eyebrow"))}</span><h3>${esc(t("life.interactions.intimacy.title", {name: person.name || ""}))}</h3><p>${esc(t("life.interactions.intimacy.subtitle"))}</p></div><span class="interaction-badge partner">${esc(stage === "secret_lover" ? t("life.interactions.romance.secret_lover") : t(`life.interactions.romance.${ROMANCE_KEYS[stage] || "partner"}`))}</span></div>
        <div class="interaction-intimacy-meter"><div class="interaction-intimacy-meter-head"><span><i data-lucide="heart"></i><strong>${esc(t("life.interactions.intimacy.current", {value: `${value > 0 ? "+" : ""}${value.toFixed(1)}`, maximum: 100}))}</strong></span><span class="interaction-intimacy-band">${esc(intimacyBandLabel(band))}</span></div><div class="interaction-intimacy-meter-track is-signed" role="progressbar" aria-valuemin="-100" aria-valuemax="100" aria-valuenow="${value.toFixed(1)}"><span class="${value < 0 ? "is-negative" : ""}" style="left:${barLeft.toFixed(1)}%;width:${barWidth.toFixed(1)}%"></span></div><div class="interaction-intimacy-meter-foot"><span>${esc(t("life.interactions.intimacy.gain_hint"))}</span><span>${esc(t("life.interactions.intimacy.band_hint"))}</span></div><div class="interaction-dossier-chips">${relationshipStatusChips(relationship)}</div><div class="interaction-obedience-meter"><div><span>${esc(t("life.interactions.intimacy.obedience"))}</span><b>${Math.round(Number(relationship.obedience || 0))} / 100</b></div><div class="interaction-obedience-track"><span style="width:${Math.max(0, Math.min(100, Number(relationship.obedience || 0))).toFixed(1)}%"></span></div></div></div>
      </section>
      ${subTabs}
      ${tab === "history" ? historyPanel : actionsPanel}
    </div>`;
  }

  function renderInteractionPanel(data, row) {
    if (!row) return `<div class="interaction-empty"><i data-lucide="message-circle-more"></i><span>${esc(t("life.interactions.relationship.select_person"))}</span></div>`;
    const person = row.person || {};
    const relationship = row.relationship || {};
    const exclusiveNotice = data.exclusive_partner && !relationship.is_exclusive && String(relationship.romance_stage || "none") !== "none"
      ? `<div class="interaction-warning"><i data-lucide="shield-alert"></i><span>${esc(t("life.interactions.relationship.exclusive_notice", {name: data.exclusive_partner.person_name || ""}))}</span></div>` : "";
    return `<div class="interaction-interaction-view"><div class="interaction-interaction-head"><div>${portraitMarkup(person, {small: true})}<span><strong>${esc(person.name || "")}</strong><small>${esc(personAffiliation(person))}</small></span></div><div class="interaction-dossier-chips">${stageBadge(relationship)}${relationshipStatusChips(relationship)}</div></div>
      ${exclusiveNotice}
      ${renderTabs(data, "interaction")}
      <div class="interaction-mode-content">${state.interactionTab === "progress" ? renderRelationshipProgress(data, row) : state.interactionTab === "intimacy" && isIntimateRelationship(relationship) ? renderIntimacyPanel(data, row) : renderInteractionHome(data, row)}</div></div>`;
  }

  function renderSearch(data) {
    const cached = new Set((data.relationships || []).map((row) => Number(row.person?.id || 0)));
    let results = "";
    if (state.searchBusy) {
      results = `<div class="interaction-empty"><span class="interaction-spinner"></span><span>${esc(t("life.interactions.search.searching"))}</span></div>`;
    } else if (state.searchResults === null) {
      results = `<div class="interaction-empty"><i data-lucide="search"></i><span>${esc(t("life.interactions.search.idle"))}</span></div>`;
    } else if (!state.searchResults.length) {
      results = `<div class="interaction-empty"><i data-lucide="user-round-x"></i><span>${esc(t("life.interactions.search.empty"))}</span></div>`;
    } else {
      results = state.searchResults.map((player) => {
        const id = Number(player.id || 0);
        const isCached = cached.has(id);
        const positions = Array.isArray(player.positions) ? player.positions.slice(0, 3).join(" · ") : "";
        return `<div class="interaction-search-row">${portraitMarkup(player, {small: true})}<div class="interaction-search-copy"><strong>${esc(player.name || id)}</strong><span>${esc([player.team_name || t("life.interactions.free_agent"), player.nationality, t("life.interactions.age_short", {age: player.age || 0}), positions].filter(Boolean).join(" · "))}</span><span>${esc(`CA ${player.ca ?? "-"} · PA ${player.pa ?? "-"} · ${t("life.interactions.reputation_short")} ${player.world_reputation ?? 0}`)}</span></div><button type="button" class="interaction-secondary" data-interaction-add="${id}" ${isCached ? "disabled" : ""}>${esc(isCached ? t("life.interactions.search.added") : t("life.interactions.search.add"))}</button></div>`;
      }).join("");
    }
    const nationalityOptions = (state.searchNationalities || []).map((nation) => {
      const id = Number(nation.id || 0);
      return `<option value="${id}" ${Number(state.searchNationalityId || 0) === id ? "selected" : ""}>${esc(nation.name || id)}</option>`;
    }).join("");
    const clubOptions = state.searchClubOptions.map((club) => {
      const id = Number(club.id || 0);
      const context = [club.nation, club.competition].filter(Boolean).join(" · ");
      return `<button type="button" class="interaction-search-club-option" data-interaction-search-club-select="${id}"><span><strong>${esc(club.name || club.short_name || id)}</strong>${context ? `<small>${esc(context)}</small>` : ""}</span><i data-lucide="chevron-right"></i></button>`;
    }).join("");
    const selectedClub = state.searchClubId
      ? `<div class="interaction-search-club-selected"><span><small>${esc(t("life.interactions.search.selected_club"))}</small><strong>${esc(state.searchClubName)}</strong></span><button type="button" data-interaction-search-club-clear aria-label="${esc(t("life.interactions.search.club_clear"))}"><i data-lucide="x"></i></button></div>`
      : "";
    const clubPanel = state.searchClubBusy
      ? `<div class="interaction-search-club-note"><span class="interaction-spinner"></span>${esc(t("life.interactions.search.club_finding"))}</div>`
      : selectedClub || (state.searchClubOptions.length
        ? `<div class="interaction-search-club-options">${clubOptions}</div>`
        : state.searchClubQuery
          ? `<div class="interaction-search-club-note">${esc(t("life.interactions.search.club_no_results"))}</div>`
          : `<div class="interaction-search-club-note">${esc(t("life.interactions.search.club_hint"))}</div>`);
    const total = Number(state.searchTotal);
    const resultSummary = state.searchResults !== null && Number.isFinite(total)
      ? `<p class="interaction-search-summary">${esc(t("life.interactions.search.total", {count: total}))}</p>` : "";
    const page = Math.max(1, Number(state.searchPage || 1));
    const pageCount = Math.max(0, Number(state.searchPageCount || 0));
    let pagination = "";
    if (!state.searchBusy && state.searchResults !== null && pageCount > 1) {
      const previous = t("life.interactions.search.previous");
      const next = t("life.interactions.search.next");
      pagination = `<nav class="interaction-search-pagination" aria-label="${esc(t("life.interactions.search.pagination_label"))}"><button type="button" class="interaction-secondary" data-interaction-search-page="${Math.max(1, page - 1)}" ${page <= 1 ? "disabled" : ""} aria-label="${esc(previous)}"><i data-lucide="chevron-left"></i>${esc(previous)}</button><span class="interaction-search-page-status">${esc(t("life.interactions.search.page_status", {page, pages: pageCount}))}</span><button type="button" class="interaction-secondary" data-interaction-search-page="${Math.min(pageCount, page + 1)}" ${page >= pageCount ? "disabled" : ""} aria-label="${esc(next)}">${esc(next)}<i data-lucide="chevron-right"></i></button></nav>`;
    }
    return `<form class="interaction-search-layout" data-interaction-form="search"><section class="interaction-panel interaction-search-results-panel"><header class="interaction-panel-head"><div><h2>${esc(t("life.interactions.search.title"))}</h2><p>${esc(t("life.interactions.search.subtitle"))}</p></div><span class="interaction-badge">${esc(t("life.interactions.player_only"))}</span></header><div class="interaction-panel-body"><div class="interaction-search-query"><input class="interaction-input" name="query" value="${esc(state.searchQuery)}" placeholder="${esc(t("life.interactions.search.placeholder"))}" autocomplete="off"><button type="submit" class="interaction-button" ${state.searchBusy ? "disabled" : ""}><i data-lucide="search"></i>${esc(t("life.interactions.search.button"))}</button></div>${resultSummary}<div class="interaction-search-results">${results}</div>${pagination}</div></section><aside class="interaction-panel interaction-search-filter-panel"><header class="interaction-panel-head"><div><h2>${esc(t("life.interactions.search.filters_title"))}</h2><p>${esc(t("life.interactions.search.filters_subtitle"))}</p></div><i data-lucide="sliders-horizontal"></i></header><div class="interaction-panel-body"><label class="interaction-search-field"><span>${esc(t("life.interactions.search.nationality"))}</span><select class="interaction-select" name="nationality_id"><option value="0">${esc(t("life.interactions.search.nationality_all"))}</option>${nationalityOptions}</select></label><label class="interaction-search-field"><span>${esc(t("life.interactions.search.gender"))}</span><select class="interaction-select" name="gender"><option value="all" ${state.searchGender === "all" ? "selected" : ""}>${esc(t("life.interactions.search.all"))}</option><option value="men" ${state.searchGender === "men" ? "selected" : ""}>${esc(t("life.interactions.search.men"))}</option><option value="women" ${state.searchGender === "women" ? "selected" : ""}>${esc(t("life.interactions.search.women"))}</option></select></label><div class="interaction-search-field"><span>${esc(t("life.interactions.search.age"))}</span><div class="interaction-search-age-range"><input class="interaction-input" type="number" min="18" name="min_age" value="${esc(state.searchMinAge)}" placeholder="${esc(t("life.interactions.search.age_min"))}" inputmode="numeric"><em>—</em><input class="interaction-input" type="number" min="18" name="max_age" value="${esc(state.searchMaxAge)}" placeholder="${esc(t("life.interactions.search.age_max"))}" inputmode="numeric"></div></div><div class="interaction-search-field"><span>${esc(t("life.interactions.search.club"))}</span><div class="interaction-search-club-row"><input class="interaction-input" data-interaction-search-club-input value="${esc(state.searchClubQuery)}" placeholder="${esc(t("life.interactions.search.club_placeholder"))}" autocomplete="off"><button type="button" class="interaction-secondary" data-interaction-search-clubs ${state.searchClubBusy ? "disabled" : ""}>${esc(t("life.interactions.search.club_find"))}</button></div>${clubPanel}</div><div class="interaction-search-filter-actions"><button type="button" class="interaction-secondary" data-interaction-search-reset><i data-lucide="rotate-ccw"></i>${esc(t("life.interactions.search.reset"))}</button><button type="submit" class="interaction-button" ${state.searchBusy ? "disabled" : ""}><i data-lucide="search-check"></i>${esc(t("life.interactions.search.button"))}</button></div></div></aside></form>`;
  }

  function personSelector(data, attribute) {
    const rows = data.relationships || [];
    return `<label class="interaction-person-select"><span>${esc(t("life.interactions.overview.current"))}</span><select class="interaction-select" ${attribute}>${rows.map((row) => {
      const person = row.person || {};
      return `<option value="${Number(person.id || 0)}" ${Number(person.id || 0) === Number(state.selectedId || 0) ? "selected" : ""}>${esc([person.name || "", person.team_name || ""].filter(Boolean).join(" · "))}</option>`;
    }).join("")}</select></label>`;
  }

  function residenceLabel(residence) {
    const city = placeName(residence, "city_name_zh", "city_name_en");
    const name = placeName(residence) || residence.asset_id;
    const kind = t(`life.kind.${residence.kind || "residential"}`);
    return [city, name, kind].filter(Boolean).join(" · ");
  }

  function residenceSelectionFor(personId, currentId) {
    return Number(state.residenceSelectionPerson || 0) === Number(personId || 0)
      ? String(state.residenceSelectionId || "")
      : String(currentId || "");
  }

  function residenceOccupantsMarkup(residence) {
    const occupants = Array.isArray(residence?.occupants) ? residence.occupants : [];
    if (!occupants.length) {
      return `<span class="interaction-residence-occupants is-empty"><span class="interaction-residence-occupant-label">${esc(t("life.interactions.residence.occupants"))}</span><span class="interaction-residence-none">${esc(t("life.interactions.residence.no_occupants"))}</span></span>`;
    }
    return `<span class="interaction-residence-occupants"><span class="interaction-residence-occupant-label">${esc(t("life.interactions.residence.occupants"))}</span><span class="interaction-residence-occupant-list">${occupants.map((occupant) => {
      const person = occupant.person || {};
      return `<span class="interaction-residence-occupant">${portraitMarkup(person, {small: true})}<span class="interaction-residence-occupant-copy"><strong>${esc(person.name || person.id || "")}</strong><small>${esc(personAffiliation(person))}</small></span><span class="interaction-residence-occupant-stage">${stageBadge(occupant.relationship || {})}</span></span>`;
    }).join("")}</span></span>`;
  }

  function renderResidencePanel(data, row) {
    if (!row) return `<div class="interaction-empty"><i data-lucide="house"></i><span>${esc(t("life.interactions.relationship.select_person"))}</span></div>`;
    const person = row.person || {};
    const relationship = row.relationship || {};
    const currentId = String(relationship.residence_asset_id || "");
    const residences = Array.isArray(data.residences) ? data.residences : [];
    const selectedId = residenceSelectionFor(person.id, currentId);
    const selected = residences.find((residence) => String(residence.asset_id || "") === selectedId) || null;
    const selectedAvailable = selected && (String(selected.asset_id || "") === currentId || Number(selected.free || 0) > 0);
    const canMoveIn = Boolean(
      selected && selectedAvailable && !selected.construction
      && String(selected.asset_id || "") !== currentId && !state.requestBusy
    );
    const cards = residences.map((residence) => {
      const id = String(residence.asset_id || "");
      const isCurrent = id === currentId;
      const isSelected = id === selectedId;
      const available = isCurrent || Number(residence.free || 0) > 0;
      const disabled = !available || Boolean(residence.construction);
      const availability = isCurrent
        ? t("life.interactions.residence.current")
        : available ? t("life.interactions.residence.available") : t("life.interactions.residence.full");
      return `<button type="button" class="interaction-residence-card ${isCurrent ? "is-current" : ""} ${isSelected ? "is-selected" : ""}" data-interaction-residence-select="${esc(id)}" aria-pressed="${isSelected}" ${disabled ? "disabled" : ""}>
        <span class="interaction-residence-card-head"><span class="interaction-residence-icon"><i data-lucide="house"></i></span><span class="interaction-residence-title"><strong>${esc(placeName(residence) || residence.asset_id)}</strong><small>${esc([placeName(residence, "city_name_zh", "city_name_en"), `${Number(residence.area_sqm || 0)} m²`, `Lv.${Number(residence.level || 1)}`].filter(Boolean).join(" · "))}</small></span><span class="interaction-badge ${isCurrent ? "friend" : available ? "" : "secret"}">${esc(availability)}</span></span>
        <span class="interaction-residence-card-meta"><span><i data-lucide="users"></i>${esc(t("life.interactions.residence.capacity", {occupied: residence.occupied || 0, capacity: residence.capacity || 0}))}</span><span><i data-lucide="banknote"></i>${esc(compactMoney(residence.market_value || 0))}</span>${isSelected ? `<span class="is-selected-label"><i data-lucide="check"></i>${esc(t("life.interactions.residence.selected"))}</span>` : ""}</span>
        ${residenceOccupantsMarkup(residence)}
      </button>`;
    }).join("");
    return `<div class="interaction-assets-toolbar">${personSelector(data, "data-interaction-person-select")}</div><section class="interaction-panel interaction-residence-panel"><header class="interaction-panel-head"><div><h2>${esc(t("life.interactions.residence.title"))}</h2><p>${esc(t("life.interactions.residence.detail"))}</p></div><span class="interaction-badge">${currentId ? esc(t("life.interactions.residence.living")) : esc(t("life.interactions.residence.not_living"))}</span></header><div class="interaction-panel-body"><p class="interaction-residence-hint"><i data-lucide="mouse-pointer-click"></i>${esc(t("life.interactions.residence.select_hint"))}</p><div class="interaction-residence-grid">${residences.length ? cards : `<div class="interaction-empty compact"><i data-lucide="house"></i><span>${esc(t("life.interactions.residence.empty"))}</span></div>`}</div>${residences.length ? `<div class="interaction-residence-footer"><span class="interaction-residence-selection"><small>${esc(t("life.interactions.residence.selected_label"))}</small><strong>${esc(selected ? residenceLabel(selected) : t("life.interactions.residence.select_hint_short"))}</strong></span><span class="interaction-residence-actions">${currentId ? `<button type="button" class="interaction-secondary" data-interaction-residence-move-out ${state.requestBusy ? "disabled" : ""}><i data-lucide="log-out"></i>${esc(t("life.interactions.residence.move_out_button"))}</button>` : ""}<button type="button" class="interaction-button" data-interaction-residence-move-in ${canMoveIn ? "" : "disabled"}><i data-lucide="key-round"></i>${esc(t("life.interactions.residence.apply_selected"))}</button></span></div>` : ""}</div></section>`;
  }

  function rarityLabel(value) {
    return optionLabel("life.rarity", String(value || "").toLowerCase());
  }

  function giftFilterOptions(rows, getter) {
    const values = new Set();
    for (const row of rows || []) {
      const value = String(getter(row) || "").trim();
      if (value) values.add(value);
    }
    return [...values].sort((left, right) => left.localeCompare(right));
  }

  function giftFilterLabel(field, value) {
    if (field === "kind") return t(`life.kind.${value}`);
    if (field === "rarity") return optionLabel("life.rarity", String(value || "").toLowerCase());
    if (field === "class") return `${t("life.class")} ${value}`;
    return value;
  }

  function giftFilterSelect(kind, field, value, options, labelKey) {
    const choices = options.map((option) => `<option value="${esc(option)}" ${String(option) === String(value) ? "selected" : ""}>${esc(giftFilterLabel(field, option))}</option>`).join("");
    return `<label class="interaction-gift-filter"><span>${esc(t(labelKey))}</span><select data-interaction-gift-filter="${esc(kind)}" data-gift-field="${esc(field)}"><option value="">${esc(t("life.interactions.asset.filter_all"))}</option>${choices}</select></label>`;
  }

  function giftGroupState(kind, key, many) {
    const all = kind === "property" ? state.giftPropertyExpandAll : state.giftVehicleExpandAll;
    if (all === true) return true;
    if (all === false) return false;
    const store = kind === "property" ? state.giftPropertyExpanded : state.giftVehicleExpanded;
    if (store.has(`closed:${key}`)) return false;
    if (store.has(`open:${key}`)) return true;
    return !many;
  }

  function giftGroupToggleButton(kind, key, open, title, meta) {
    return `<button type="button" class="interaction-gift-group-head" data-interaction-gift-toggle="${esc(kind)}" data-group-key="${esc(key)}" aria-expanded="${open ? "true" : "false"}"><i data-lucide="${open ? "chevron-down" : "chevron-right"}"></i><span><strong>${esc(title)}</strong><small>${esc(meta)}</small></span></button>`;
  }

  function giftPropertyGroups(properties, relationship) {
    const cityOptions = giftFilterOptions(properties, (row) => placeName(row, "city_name_zh", "city_name_en") || row.city_id);
    const cityRows = state.giftPropertyCity
      ? properties.filter((row) => String(placeName(row, "city_name_zh", "city_name_en") || row.city_id) === state.giftPropertyCity)
      : properties;
    const districtOptions = giftFilterOptions(cityRows, (row) => placeName(row, "district_name_zh", "district_name_en") || row.district_id);
    const kindOptions = giftFilterOptions(cityRows, (row) => row.kind);
    const filtered = cityRows.filter((row) => {
      const district = String(placeName(row, "district_name_zh", "district_name_en") || row.district_id || "");
      return (!state.giftPropertyDistrict || district === state.giftPropertyDistrict)
        && (!state.giftPropertyKind || String(row.kind || "") === state.giftPropertyKind);
    });
    const cities = new Map();
    for (const row of filtered) {
      const city = String(placeName(row, "city_name_zh", "city_name_en") || row.city_id || "—");
      const district = String(placeName(row, "district_name_zh", "district_name_en") || row.district_id || "—");
      if (!cities.has(city)) cities.set(city, new Map());
      const districts = cities.get(city);
      if (!districts.has(district)) districts.set(district, []);
      districts.get(district).push(row);
    }
    const many = filtered.length > 12;
    const groups = [...cities.entries()].map(([city, districts]) => {
      const cityRowsAll = [...districts.values()].flat();
      const cityKey = `city:${city}`;
      const cityOpen = giftGroupState("property", cityKey, many);
      const value = cityRowsAll.reduce((sum, row) => sum + Number(row.market_value || 0), 0);
      const districtMarkup = [...districts.entries()].map(([district, rows]) => {
        const districtKey = `district:${city}:${district}`;
        const districtOpen = giftGroupState("property", districtKey, many);
        return `<div class="interaction-gift-district"><button type="button" class="interaction-gift-district-head" data-interaction-gift-toggle="property" data-group-key="${esc(districtKey)}" aria-expanded="${districtOpen ? "true" : "false"}"><i data-lucide="${districtOpen ? "chevron-down" : "chevron-right"}"></i><span>${esc(district)}</span><small>${esc(t("life.interactions.asset.group_count", {count: rows.length, value: compactMoney(rows.reduce((sum, row) => sum + Number(row.market_value || 0), 0))}))}</small></button>${districtOpen ? `<div class="interaction-asset-grid interaction-gift-grid">${rows.map((row) => propertyCard(row, relationship)).join("")}</div>` : ""}</div>`;
      }).join("");
      return `<section class="interaction-gift-group"><button type="button" class="interaction-gift-group-head" data-interaction-gift-toggle="property" data-group-key="${esc(cityKey)}" aria-expanded="${cityOpen ? "true" : "false"}"><i data-lucide="${cityOpen ? "chevron-down" : "chevron-right"}"></i><span><strong>${esc(city)}</strong><small>${esc(t("life.interactions.asset.group_count", {count: cityRowsAll.length, value: compactMoney(value)}))}</small></span><span class="interaction-badge">${esc(t("life.city"))}</span></button>${cityOpen ? `<div class="interaction-gift-districts">${districtMarkup}</div>` : ""}</section>`;
    }).join("");
    return `<div class="interaction-gift-toolbar"><div class="interaction-gift-filters">${giftFilterSelect("property", "city", state.giftPropertyCity, cityOptions, "life.interactions.asset.filter_city")}${giftFilterSelect("property", "district", state.giftPropertyDistrict, districtOptions, "life.interactions.asset.filter_district")}${giftFilterSelect("property", "kind", state.giftPropertyKind, kindOptions, "life.interactions.asset.filter_kind")}</div><button type="button" class="interaction-secondary" data-interaction-gift-expand="property">${esc(t(state.giftPropertyExpandAll === true ? "life.interactions.asset.collapse_all" : "life.interactions.asset.expand_all"))}</button></div><div class="interaction-gift-groups">${groups || `<div class="interaction-empty compact"><span>${esc(t("life.interactions.asset.filter_empty"))}</span></div>`}</div>`;
  }

  function giftGarageLabel(asset) {
    return placeName(asset, "garage_name_zh", "garage_name_en") || String(asset.garage_id || "");
  }

  function giftVehicleGroups(vehicles, relationship) {
    const brandOptions = giftFilterOptions(vehicles, (row) => row.manufacturer);
    const classOptions = giftFilterOptions(vehicles, (row) => row.class);
    const rarityOptions = giftFilterOptions(vehicles, (row) => row.rarity);
    const filtered = vehicles.filter((row) => (
      (!state.giftVehicleBrand || String(row.manufacturer || "") === state.giftVehicleBrand)
      && (!state.giftVehicleClass || String(row.class || "") === state.giftVehicleClass)
      && (!state.giftVehicleRarity || String(row.rarity || "") === state.giftVehicleRarity)
    ));
    const brands = new Map();
    for (const row of filtered) {
      const brand = String(row.manufacturer || "—");
      if (!brands.has(brand)) brands.set(brand, []);
      brands.get(brand).push(row);
    }
    const many = filtered.length > 12;
    const groups = [...brands.entries()].map(([brand, rows]) => {
      const key = `brand:${brand}`;
      const open = giftGroupState("vehicle", key, many);
      return `<section class="interaction-gift-group"><button type="button" class="interaction-gift-group-head" data-interaction-gift-toggle="vehicle" data-group-key="${esc(key)}" aria-expanded="${open ? "true" : "false"}"><i data-lucide="${open ? "chevron-down" : "chevron-right"}"></i><span><strong>${esc(brand)}</strong><small>${esc(t("life.interactions.asset.group_count", {count: rows.length, value: compactMoney(rows.reduce((sum, row) => sum + Number(row.market_value || 0), 0))}))}</small></span><span class="interaction-badge">${esc(t("life.brand"))}</span></button>${open ? `<div class="interaction-asset-grid interaction-gift-grid">${rows.map((row) => vehicleCard(row, relationship)).join("")}</div>` : ""}</section>`;
    }).join("");
    return `<div class="interaction-gift-toolbar"><div class="interaction-gift-filters">${giftFilterSelect("vehicle", "brand", state.giftVehicleBrand, brandOptions, "life.brand")}${giftFilterSelect("vehicle", "class", state.giftVehicleClass, classOptions, "life.class")}${giftFilterSelect("vehicle", "rarity", state.giftVehicleRarity, rarityOptions, "life.rarity")}</div><button type="button" class="interaction-secondary" data-interaction-gift-expand="vehicle">${esc(t(state.giftVehicleExpandAll === true ? "life.interactions.asset.collapse_all" : "life.interactions.asset.expand_all"))}</button></div><div class="interaction-gift-groups">${groups || `<div class="interaction-empty compact"><span>${esc(t("life.interactions.asset.filter_empty"))}</span></div>`}</div>`;
  }

  function assetGiftPreview(relationship, assetType, asset) {
    const preview = relationship?.asset_gift_previews?.[`${assetType}:${asset.id}`];
    if (!preview) return "";
    const stageKey = String(preview.social_stage_after || "acquaintance");
    const stageCopy = preview.may_upgrade
      ? t("life.interactions.asset.stage_after", {stage: t(`life.interactions.social.${stageKey}`)})
      : t("life.interactions.asset.stage_hold");
    return `<div class="interaction-gift-preview"><span><i data-lucide="heart"></i>${esc(t("life.interactions.asset.gift_affection", {gain: Number(preview.affection_gain || 0).toFixed(1)}))}</span><span class="${preview.may_upgrade ? "is-upgrade" : ""}"><i data-lucide="${preview.may_upgrade ? "trending-up" : "minus"}"></i>${esc(stageCopy)}</span></div>`;
  }

  function propertyCard(asset, relationship) {
    const city = placeName(asset, "city_name_zh", "city_name_en");
    const name = placeName(asset) || asset.id;
    const kind = t(`life.kind.${asset.kind || "residential"}`);
    const cost = Number(asset.action_cost || 1);
    const reason = asset.blocked_reason_key
      ? translated(`life.interactions.asset.blocked.${asset.blocked_reason_key}`) || asset.blocked_reason || ""
      : "";
    const district = placeName(asset, "district_name_zh", "district_name_en");
    return `<article class="interaction-asset-card ${asset.giftable ? "" : "is-blocked"}"><header><span class="interaction-asset-type"><i data-lucide="building-2"></i>${esc(kind)}</span><span class="interaction-badge">${esc(compactMoney(asset.market_value || 0))}</span></header><h3>${esc(name)}</h3><p>${esc([city, district, `${Number(asset.area_sqm || 0)} m²`, `Lv.${Number(asset.level || 1)}`].filter(Boolean).join(" · "))}</p>${reason ? `<small class="interaction-blocked-reason">${esc(reason)}</small>` : `${assetGiftPreview(relationship, "property", asset)}<button type="button" class="interaction-secondary" data-interaction-gift-asset="property:${esc(asset.id)}"><i data-lucide="gift"></i>${esc(t("life.interactions.asset.give"))} · ${cost} ${esc(AP())}</button>`}</article>`;
  }

  function vehicleCard(asset, relationship) {
    const cost = Number(asset.action_cost || 1);
    const reason = asset.blocked_reason_key
      ? translated(`life.interactions.asset.blocked.${asset.blocked_reason_key}`) || asset.blocked_reason || ""
      : "";
    const garage = giftGarageLabel(asset) || t("life.interactions.asset.unknown_garage");
    const image = String(asset.image || "");
    const thumb = image
      ? `<span class="interaction-asset-thumb"><img src="${esc(image)}" alt="${esc(asset.name || "")}" loading="lazy" decoding="async"></span>`
      : `<span class="interaction-asset-thumb is-empty"><i data-lucide="car-front"></i></span>`;
    return `<article class="interaction-asset-card interaction-vehicle-gift-card ${asset.giftable ? "" : "is-blocked"}"><header><span class="interaction-asset-type"><i data-lucide="car-front"></i>${esc(asset.manufacturer || t("life.vehicle"))}</span><span class="interaction-badge">${esc(compactMoney(asset.market_value || 0))}</span></header><div class="interaction-asset-vehicle-main">${thumb}<div><h3>${esc(asset.name || asset.id)}</h3><p>${esc([asset.class ? `${t("life.class")} ${asset.class}` : "", asset.rarity ? rarityLabel(asset.rarity) : "", garage].filter(Boolean).join(" · "))}</p></div></div>${reason ? `<small class="interaction-blocked-reason">${esc(reason)}</small>` : `${assetGiftPreview(relationship, "vehicle", asset)}<button type="button" class="interaction-secondary" data-interaction-gift-asset="vehicle:${esc(asset.id)}"><i data-lucide="gift"></i>${esc(t("life.interactions.asset.give"))} · ${cost} ${esc(AP())}</button>`}</article>`;
  }

  function renderAssetGiftPanel(data, row) {
    if (!row) return `<div class="interaction-empty"><i data-lucide="gift"></i><span>${esc(t("life.interactions.relationship.select_person"))}</span></div>`;
    const person = row.person || {};
    const properties = data.assets?.properties || [];
    const vehicles = data.assets?.vehicles || [];
    const history = (data.gifted_assets || []).filter((gift) => Number(gift.person_id || 0) === Number(person.id || 0)).slice(0, 10);
    return `<div class="interaction-assets-toolbar">${personSelector(data, "data-interaction-person-select")}</div><section class="interaction-panel"><header class="interaction-panel-head"><div><h2>${esc(t("life.interactions.asset.title"))}</h2><p>${esc(t("life.interactions.asset.detail"))}</p></div><span class="interaction-badge secret">${esc(t("life.interactions.asset.permanent_badge"))}</span></header><div class="interaction-panel-body"><div class="interaction-warning"><i data-lucide="triangle-alert"></i><span>${esc(t("life.interactions.asset.warning"))}</span></div><section class="interaction-asset-section"><h3>${esc(t("life.interactions.asset.property_group"))}</h3>${properties.length ? giftPropertyGroups(properties, row.relationship) : `<div class="interaction-empty compact"><span>${esc(t("life.interactions.asset.empty"))}</span></div>`}</section><section class="interaction-asset-section"><h3>${esc(t("life.interactions.asset.vehicle_group"))}</h3>${vehicles.length ? giftVehicleGroups(vehicles, row.relationship) : `<div class="interaction-empty compact"><span>${esc(t("life.interactions.asset.empty"))}</span></div>`}</section><div class="interaction-gift-history"><strong>${esc(t("life.interactions.asset.history"))}</strong>${history.length ? history.map((gift) => `<div class="interaction-residence-row"><div><strong>${esc(assetGiftName(gift, gift.asset_id))}</strong><span>${esc(t("life.interactions.asset.history_row", {date: formatGameDay(gift.day), value: compactMoney(gift.value || 0)}))}</span></div><span class="interaction-badge secret">${esc(t("life.interactions.asset.permanent_badge"))}</span></div>`).join("") : `<span class="interaction-inline-note">${esc(t("life.interactions.asset.history_empty"))}</span>`}</div></div></section>`;
  }

  function renderOwnedAssets(data, row) {
    if (!row) return `<div class="interaction-empty"><i data-lucide="gem"></i><span>${esc(t("life.interactions.relationship.select_person"))}</span></div>`;
    const person = row.person || {};
    const relationship = row.relationship || {};
    const owned = relationship.owned_assets || {};
    const properties = Array.isArray(owned.properties) ? owned.properties : [];
    const vehicles = Array.isArray(owned.vehicles) ? owned.vehicles : [];
    const rowMarkup = (asset, type) => {
      const date = formatGameDay(asset.day);
      return `<div class="interaction-owned-row"><span class="interaction-owned-icon"><i data-lucide="${type === "vehicle" ? "car-front" : "building-2"}"></i></span><div><strong>${esc(assetGiftName(asset, asset.asset_id || ""))}</strong><span>${esc([date ? t("life.interactions.owned.gift_date", {date}) : "", compactMoney(asset.value || 0)].filter(Boolean).join(" · "))}</span></div><span class="interaction-badge secret">${esc(t("life.interactions.owned.permanent"))}</span></div>`;
    };
    const section = (titleKey, icon, rows, type) => `<article class="interaction-owned-section"><header><span><i data-lucide="${icon}"></i><strong>${esc(t(titleKey))}</strong></span><b>${rows.length}</b></header><div>${rows.length ? rows.map((asset) => rowMarkup(asset, type)).join("") : `<div class="interaction-owned-none">${esc(t("life.interactions.owned.empty"))}</div>`}</div></article>`;
    return `<div class="interaction-interaction-view"><div class="interaction-interaction-head"><div>${portraitMarkup(person, {small: true})}<span><strong>${esc(person.name || "")}</strong><small>${esc(personAffiliation(person))}</small></span></div><div class="interaction-dossier-chips">${stageBadge(relationship)}</div></div>
      <section class="interaction-owned-summary"><div><small>${esc(t("life.interactions.owned.total_value"))}</small><strong>${esc(compactMoney(owned.total_value || 0))}</strong><span>${esc(t("life.interactions.owned.count", {count: Number(owned.count || 0)}))}</span></div><span class="interaction-badge secret"><i data-lucide="lock-keyhole"></i>${esc(t("life.interactions.owned.permanent"))}</span></section>
      <div class="interaction-owned-groups">${section("life.interactions.owned.properties", "building-2", properties, "property")}${section("life.interactions.owned.vehicles", "car-front", vehicles, "vehicle")}</div>
      <p class="interaction-owned-hint"><i data-lucide="info"></i>${esc(t("life.interactions.owned.hint"))}</p></div>`;
  }

  function renderAssets(data) {
    return `${renderTabs(data, "assets")}${state.assetsTab === "gift" ? renderAssetGiftPanel(data, selectedRow()) : renderResidencePanel(data, selectedRow())}`;
  }

  function timelineTitle(item) {
    const result = item?.result || {};
    const action = String(item?.action || "");
    if (item?.kind === "chat") return t("life.interactions.timeline.chat_title", {topic: t(`life.interactions.topic.${result.topic || "life"}`)});
    if (item?.kind === "gift") return t("life.interactions.timeline.gift_title", {item: result.item_name || ""});
    if (item?.kind === "date") return t("life.interactions.timeline.date_title", {activity: t(`life.interactions.activity.${action}`)});
    if (item?.kind === "relationship") return t(`life.interactions.relationship.action.${action}`);
    if (item?.kind === "intimacy") return t("life.interactions.timeline.intimacy_title", {action: intimacyActionLabel(action)});
    if (item?.kind === "residence") return action === "move_out" ? t("life.interactions.timeline.move_out_title") : t("life.interactions.timeline.move_in_title");
    if (item?.kind === "asset_gift") return t("life.interactions.timeline.asset_title", {asset: assetGiftName(result)});
    if (item?.kind === "event") return eventKindLabel(action);
    return t(`life.interactions.timeline.kind.${TIMELINE_KEYS[item?.kind] || "chat"}`);
  }

  function timelineDetail(item) {
    const result = item?.result || {};
    if (item?.kind === "chat") return result.preference_match ? t("life.interactions.timeline.preference_hit") : t("life.interactions.timeline.chat_detail");
    if (item?.kind === "gift") return t("life.interactions.timeline.gift_detail", {value: fullMoney(result.value || 0)});
    if (item?.kind === "date") return t("life.interactions.timeline.date_detail", {activity: t(`life.interactions.activity.${item.action || "walk"}`), match: result.preference_match ? t("life.interactions.timeline.preference_hit_short") : ""});
    if (item?.kind === "relationship") return result.chance !== undefined
      ? t(result.success ? "life.interactions.timeline.relationship_success" : "life.interactions.timeline.relationship_fail", {chance: percent(result.chance, 1)})
      : t("life.interactions.timeline.relationship_detail");
    if (item?.kind === "intimacy") return t("life.interactions.timeline.intimacy_detail", {
      cost: Number(result.intimacy_cost || 0),
      remaining: Number(result.intimacy_after || 0).toFixed(1),
    });
    if (item?.kind === "residence") return t(item.action === "move_out" ? "life.interactions.timeline.move_out_detail" : "life.interactions.timeline.move_in_detail");
    if (item?.kind === "asset_gift") return t("life.interactions.timeline.asset_detail", {value: compactMoney(result.value || 0)});
    if (item?.kind === "event") return eventOptionLabel(String(item.action || "relationship_crisis"), String(result.option || ""));
    return "";
  }

  function deltaMarkup(deltas) {
    const rows = DIMENSIONS.map(([key, labelKey]) => {
      const value = Number(deltas?.[key] || 0);
      if (!value) return "";
      return `<span class="${value < 0 ? "negative" : ""}">${esc(t(labelKey))} ${value > 0 ? "+" : ""}${value.toFixed(2)}</span>`;
    }).filter(Boolean);
    return rows.length ? `<div class="interaction-delta-row">${rows.join("")}</div>` : "";
  }

  function renderTimeline(data) {
    const selected = selectedRow();
    const items = (data.timeline || []).filter((item) => state.timelineAll || Number(item.person_id || 0) === Number(selected?.person?.id || 0)).slice(0, 120);
    return `<div class="interaction-timeline-toolbar"><label class="interaction-check"><input type="checkbox" data-interaction-timeline-all ${state.timelineAll ? "checked" : ""}><span>${esc(t("life.interactions.timeline.all"))}</span></label>${state.timelineAll ? "" : personSelector(data, "data-interaction-person-select")}</div><section class="interaction-panel"><header class="interaction-panel-head"><div><h2>${esc(t("life.interactions.timeline.title"))}</h2><p>${esc(t("life.interactions.timeline.detail"))}</p></div><span class="interaction-badge">${Number(items.length)}</span></header><div class="interaction-panel-body"><div class="interaction-timeline">${items.length ? items.map((item) => `<div class="interaction-timeline-row"><span class="interaction-timeline-dot"></span><div class="interaction-timeline-copy"><strong>${esc(timelineTitle(item))}</strong><span>${esc(timelineDetail(item))}</span>${deltaMarkup(item.result?.deltas || {})}</div><span class="interaction-timeline-date">${esc(formatGameDay(item.day))}</span></div>`).join("") : `<div class="interaction-empty"><i data-lucide="history"></i><span>${esc(t("life.interactions.timeline.empty"))}</span></div>`}</div></div></section>`;
  }

  function dialogueText(result) {
    const dialogue = result?.dialogue || {};
    const kind = ["chat", "gift", "date", "relationship", "intimacy"].includes(String(dialogue.kind))
      ? String(dialogue.kind) : "chat";
    const reaction = ["preferred", "neutral", "disliked", "success", "failure"].includes(String(dialogue.reaction))
      ? String(dialogue.reaction) : "neutral";
    const parameters = {};
    if (kind === "chat") {
      parameters.topic = t(`life.interactions.topic.${String(dialogue.topic || "life")}`);
    } else if (kind === "gift") {
      parameters.category = t(`life.interactions.gift_category.${GIFT_CATEGORY_KEYS[String(dialogue.category || "luxury")] || "luxury"}`);
    } else if (kind === "date") {
      parameters.activity = t(`life.interactions.activity.${String(dialogue.activity || "cafe")}`);
    } else if (kind === "relationship") {
      parameters.action = t(`life.interactions.relationship.action.${String(dialogue.target || "partner")}`);
    } else {
      parameters.action = intimacyActionLabel(String(dialogue.action || "embrace"));
    }
    const base = `life.interactions.dialogue.${kind}.${reaction}`;
    const candidates = [];
    if (dialogue.variant) candidates.push(`${base}.${Number(dialogue.variant)}`);
    if (dialogue.tone) candidates.push(`${base}.${String(dialogue.tone)}`);
    if (dialogue.second_tone) candidates.push(`${base}.${String(dialogue.second_tone)}`);
    if (dialogue.value) candidates.push(`${base}.${String(dialogue.value)}`);
    if (dialogue.stage) candidates.push(`${base}.${String(dialogue.stage)}`);
    if (dialogue.bond) candidates.push(`${base}.${String(dialogue.bond)}`);
    if (dialogue.romance_stage && dialogue.romance_stage !== "none") {
      candidates.push(`${base}.${String(dialogue.romance_stage)}`);
    }
    candidates.push(base);
    for (const key of candidates) {
      const text = translated(key, parameters);
      if (text) return text;
    }
    return parameters.topic || parameters.category || parameters.activity || parameters.action || "";
  }

  function localizedError(error) {
    const source = String(error?.message || error || t("life.interactions.error"));
    const known = {
      "行动力不足，请等待每周恢复": "ap_missing",
      "球员 ID 无效": "person_invalid",
      "互动系统首版仅支持球员，不支持职员": "player_only_error",
      "无法确认该球员年龄，暂不能加入互动": "age_unknown",
      "仅可添加年满 18 岁的成年球员": "adult_only",
      "请先将该球员加入互动列表": "person_missing",
      "请选择要赠送的物品": "item_missing",
      "成为朋友后才可邀请约会": "friend_required",
      "约会活动无效": "date_invalid",
      "今天已经与该球员约会过": "date_daily",
      "当前关系已经越过暧昧阶段": "romance_passed",
      "至少要先成为朋友": "friend_required",
      "好感或吸引尚未达到表白条件": "ambiguous_score",
      "请先进入暧昧阶段": "ambiguous_required",
      "已有情侣或配偶，只能发展为情人保密关系": "exclusive_secret_only",
      "吸引或好感尚未达到情侣条件": "partner_score",
      "只有公开情侣可以结婚": "spouse_public_partner",
      "已有情侣或配偶，无法结婚": "exclusive_spouse",
      "好感或信任尚未达到结婚条件": "spouse_score",
      "当前关系不能成为情人": "secret_invalid",
      "没有其他情侣或配偶时，请公开发展为情侣": "secret_public",
      "吸引或信任尚未达到保密关系条件": "secret_score",
      "当前没有可分手的关系": "breakup_missing",
      "婚姻关系请使用离婚": "breakup_use_divorce",
      "当前没有婚姻关系": "divorce_missing",
      "关系操作无效": "relationship_invalid",
      "至少要先成为好友": "friend_required",
      "已经选择朋友线，无法再进入暧昧": "relationship_invalid",
      "已经选择朋友线，无法成为情侣": "relationship_invalid",
      "已经选择朋友线，无法结婚": "relationship_invalid",
      "已经选择朋友线，无法成为保密情人": "relationship_invalid",
      "当前性别组合不能进入夫妻线": "relationship_invalid",
      "当前性别组合不能选择这条朋友线": "relationship_invalid",
      "已经选择夫妻线，无法再进入朋友线": "relationship_invalid",
      "朋友线已经开始": "relationship_invalid",
      "请先成为搭档": "relationship_invalid",
      "当前朋友线不能进入这个阶段": "relationship_invalid",
      "只有兄弟线可以成为生死兄弟": "relationship_invalid",
      "熟悉、信任或尊重尚未达到搭档条件": "relationship_invalid",
      "好感、熟悉或尊重尚未达到同好条件": "relationship_invalid",
      "关系条件尚未达到下一阶段": "relationship_invalid",
      "信任、尊重或好感尚未达到生死兄弟条件": "relationship_invalid",
      "成为朋友后才可邀请入住": "residence_friend_required",
      "只能选择本人持有并设为自住的住宅": "residence_owned_self_only",
      "住宅正在建设中，暂时不能入住": "residence_construction",
      "该住宅入住容量已满": "residence_full",
      "成为朋友后才可赠送地产或车辆": "asset_friend_required",
      "资产不存在": "asset_missing",
      "车辆不存在": "vehicle_missing",
      "赠送资产类型无效": "asset_type_invalid",
      "请填写玩家名称": "profile_name_required",
      "请填写玩家姓氏或名字": "profile_name_required",
      "玩家性别无效": "profile_gender_invalid",
      "玩家必须年满 18 岁": "profile_adult_only",
      "颜值、能力、魅力与情商只能增加，不能降低": "profile_attribute_locked",
      "颜值、能力与魅力只能增加，不能降低": "profile_attribute_locked",
      "请选择要加入互动的球员": "search_person_required",
      "未找到该球员，或该球员不属于可互动球员范围": "search_person_missing",
      "请选择互动球员": "person_required",
      "该物品已经使用或不存在": "item_used",
      "该物品暂不支持赠送": "item_unsupported",
      "调整已分配属性需要重置档案并支付重置费用": "profile_reset_required",
      "调整已分配属性需要重置档案": "profile_reset_required_short",
      "可用属性点不足": "profile_points_insufficient",
      "住宅或资产不存在": "asset_missing",
      "租赁资产不可赠送": "asset_lease_blocked",
      "资产正在建设中，不可赠送": "asset_construction_blocked",
      "请选择要处理的事件": "event_required",
      "事件不存在": "event_missing",
      "该事件已经处理": "event_resolved",
      "该事件尚未到发生时间": "event_not_due",
      "事件选项无效": "event_option_invalid",
      "未知事件类型": "event_kind_invalid",
      "该人物关系已不存在": "event_relationship_missing",
      "资产内仍有 NPC 居住，请先迁出": "asset_occupied_blocked",
      "资产车库内仍有车辆，请先移走车辆": "asset_garage_blocked",
      "成为情侣、情人或夫妻后才可以进行亲密行为": "intimacy_requires_commitment",
      "当前关系阶段不支持该亲密行为": "intimacy_stage_blocked",
      "亲密度不足": "intimacy_insufficient",
      "亲密行为无效": "intimacy_invalid",
    };
    const key = known[source] || (source.startsWith("可用属性点不足") ? "profile_points_insufficient" : "");
    return key ? t(`life.interactions.error.${key}`) : source;
  }

  function showActionResult(result, row) {
    const dialog = resultDialog();
    const content = document.getElementById("life-interactions-result-content");
    if (!dialog || !content || !result) return;
    const person = row?.person || {};
    const relationship = row?.relationship || {};
    const headingKey = `life.interactions.result.${result.kind || "chat"}.title`;
    const failed = (result.kind === "relationship" || result.kind === "event") && !result.success;
    const tone = failed ? "warning" : result.kind === "intimacy" ? "intimate" : "success";
    const eventKind = String(result.event?.kind || result.event_kind || "relationship_crisis");
    const outcome = result.kind === "relationship"
      ? t(result.success
        ? "life.interactions.result.relationship_success"
        : "life.interactions.result.relationship_failure", {
        chance: percent(result.chance || 0, 1),
      })
      : result.kind === "intimacy"
        ? t("life.interactions.result.intimacy_complete", {action: intimacyActionLabel(result.action)})
        : result.kind === "event"
          ? t(result.success ? "life.interactions.result.event_success" : "life.interactions.result.event_partial")
        : t("life.interactions.result.recorded");
    const activity = result.kind === "gift"
      ? (result.consumed_item?.name || t(`life.interactions.gift_category.${GIFT_CATEGORY_KEYS[String(result.dialogue?.category || "luxury")] || "luxury"}`))
      : result.kind === "date"
        ? t(`life.interactions.activity.${String(result.activity || "cafe")}`)
        : result.kind === "asset_gift"
          ? `${assetGiftName(result)} · ${compactMoney(result.value || 0)}`
          : result.kind === "intimacy"
            ? intimacyActionLabel(result.action)
            : result.kind === "event"
              ? eventKindLabel(eventKind)
            : result.kind === "relationship"
              ? t(`life.interactions.relationship.action.${String(result.target || "")}`)
              : t(`life.interactions.topic.${String(result.dialogue?.topic || "life")}`);
    const bond = String(result.dialogue?.bond || relationship.effective_romance_stage || relationship.romance_stage || "");
    const bondNote = bond && bond !== "none" && result.kind !== "intimacy" && result.kind !== "event"
      ? t(`life.interactions.dialogue.${bond}_note`)
      : "";
    const intimacyMarkup = result.kind === "intimacy"
      ? `<div class="interaction-result-metric is-intimate"><small>${esc(t("life.interactions.result.intimacy_cost"))}</small><strong>-${Number(result.intimacy_cost || 0).toFixed(1)}</strong><span>${esc(t("life.interactions.result.intimacy_remaining", {value: Number(result.intimacy_after || 0).toFixed(1)}))}</span></div>`
      : Number(result.intimacy_gain || 0) > 0
        ? `<div class="interaction-result-metric is-intimate"><small>${esc(t("life.interactions.result.intimacy_gain"))}</small><strong>+${Number(result.intimacy_gain).toFixed(1)}</strong><span>${esc(t("life.interactions.result.intimacy_remaining", {value: Number(result.intimacy_after || 0).toFixed(1)}))}</span></div>`
        : "";
    const chanceMarkup = result.kind === "relationship"
      ? `<div class="interaction-result-metric"><small>${esc(t("life.interactions.result.chance_label"))}</small><strong>${esc(percent(result.chance || 0, 1))}</strong><span>${esc(t("life.interactions.result.roll_label", {roll: Number(result.roll || 0).toFixed(3)}))}</span></div>`
      : result.kind === "event"
        ? `<div class="interaction-result-metric"><small>${esc(t("life.interactions.result.event_choice"))}</small><strong>${esc(eventOptionLabel(eventKind, String(result.option || "")))}</strong><span>${esc(t("life.interactions.result.recorded_short"))}</span></div>`
      : `<div class="interaction-result-metric"><small>${esc(t("life.interactions.result.action_cost"))}</small><strong>${Number(result.action_cost || result.dialogue?.action_cost || 0)} ${esc(AP())}</strong><span>${esc(t("life.interactions.result.recorded_short"))}</span></div>`;
    const upgradeMarkup = result.upgraded_stage
      ? `<div class="interaction-result-upgrade"><i data-lucide="sparkles"></i><span>${esc(t("life.interactions.chat.stage_upgraded", {stage: t(`life.interactions.social.${SOCIAL_KEYS[String(result.upgraded_stage)] || "friend"}`)}))}</span></div>`
      : "";
    const familyMarkup = result.family_planning
      ? `<div class="interaction-result-family"><i data-lucide="sprout"></i><span>${esc(t("life.interactions.result.family_planning"))}</span></div>`
      : "";
    const quoteText = result.kind === "event"
      ? eventResolutionText(result, eventKind)
      : dialogueText(result);
    content.innerHTML = `<div class="interaction-result-hero">${portraitMarkup(person, {small: true})}<div class="interaction-result-person-copy"><small>${esc(t("life.interactions.result.speaker"))}</small><strong>${esc(person.name || t("life.interactions.dossier.title"))}</strong><span>${esc(personAffiliation(person))}</span><div class="interaction-result-badges">${stageBadge(relationship)}</div></div><span class="interaction-result-status tone-${tone}"><i data-lucide="${failed ? "circle-alert" : result.kind === "intimacy" ? "heart-handshake" : "check"}"></i>${esc(outcome)}</span></div>
      <blockquote class="interaction-result-quote">${esc(quoteText)}</blockquote>
      ${bondNote ? `<p class="interaction-result-intimacy-note"><i data-lucide="heart"></i><span>${esc(bondNote)}</span></p>` : ""}
      <div class="interaction-result-context"><span><small>${esc(t("life.interactions.result.context"))}</small><strong>${esc(activity)}</strong></span>${chanceMarkup}${intimacyMarkup}</div>
      ${upgradeMarkup}${familyMarkup}
      ${result.deltas && Object.keys(result.deltas).length ? `<div class="interaction-result-rewards"><span>${esc(t("life.interactions.result.progress_gain"))}</span>${deltaMarkup(result.deltas)}</div>` : ""}
      <footer class="interaction-result-footer"><span><i data-lucide="history"></i>${esc(t("life.interactions.result.saved"))}</span><button type="button" class="interaction-button interaction-result-close" data-interaction-action="close-result">${esc(t("life.interactions.result.done"))}</button></footer>`;
    dialog.dataset.resultTone = tone;
    dialog.querySelector("[data-interaction-result-title]").textContent = t(headingKey);
    bridge()?.renderIcons(dialog);
    if (!dialog.open) dialog.showModal();
  }

  function closeResultDialog() {
    const dialog = resultDialog();
    if (dialog?.open) dialog.close();
    window.setTimeout(maybeOpenPendingEvent, 0);
  }

  function chatReplyText(result) {
    const direct = String(result?.reply_text || "").trim();
    if (direct) return direct;
    if (!result?.dialogue) return "";
    return dialogueText({dialogue: result.dialogue});
  }

  function chatThreadRows(personId) {
    const rows = (state.data?.timeline || []).filter((item) => (
      String(item?.kind || "") === "chat"
      && Number(item?.person_id || 0) === Number(personId || 0)
    )).slice(0, 60).reverse();
    return rows.sort((left, right) => {
      const dayDelta = Number(left?.day || 0) - Number(right?.day || 0);
      if (dayDelta) return dayDelta;
      return String(left?.id || "").localeCompare(String(right?.id || ""));
    });
  }

  function chatThreadMarkup(rows, person, latestTimelineId = "") {
    if (!rows.length) {
      return `<div class="interaction-chat-empty"><span class="interaction-chat-empty-icon"><i data-lucide="messages-square"></i></span><strong>${esc(t("life.interactions.chat.history_empty_title"))}</strong><span>${esc(t("life.interactions.chat.history_empty"))}</span></div>`;
    }
    let currentDay = 0;
    return rows.map((entry) => {
      const result = entry?.result || {};
      const day = Number(entry?.day || 0);
      const daySeparator = day && day !== currentDay
        ? `<div class="interaction-chat-day"><span>${esc(formatGameDay(day))}</span></div>` : "";
      currentDay = day || currentDay;
      const topicKey = String(result.topic || "life");
      const playerText = String(result.message || "").trim()
        || t("life.interactions.chat.topic_message", {topic: t(`life.interactions.topic.${topicKey}`)});
      const reply = chatReplyText(result)
        || t("life.interactions.chat.history_reply", {topic: t(`life.interactions.topic.${topicKey}`)});
      const upgraded = result.upgraded_stage
        ? `<div class="interaction-chat-system"><i data-lucide="sparkles"></i>${esc(t("life.interactions.chat.stage_upgraded", {stage: t(`life.interactions.social.${SOCIAL_KEYS[String(result.upgraded_stage)] || "friend"}`)}))}</div>` : "";
      const deltas = deltaMarkup(result.deltas || {});
      const intimacyGain = Number(result.intimacy_gain || 0) > 0
        ? `<span class="interaction-chat-intimacy"><i data-lucide="heart"></i>${esc(t("life.interactions.chat.intimacy_gain", {gain: Number(result.intimacy_gain).toFixed(1), value: Number(result.intimacy_after || 0).toFixed(1)}))}</span>`
        : "";
      const reward = deltas
        ? `<div class="interaction-chat-reward"><span><i data-lucide="sparkles"></i>${esc(t("life.interactions.result.recorded"))}</span>${deltas}${intimacyGain}</div>` : "";
      return `${daySeparator}
        <div class="interaction-chat-exchange ${String(entry.id || "") === String(latestTimelineId || "") ? "is-latest" : ""}">
          <div class="interaction-chat-message is-player"><div class="interaction-chat-bubble">${esc(playerText)}</div><span class="interaction-chat-meta">${esc(t("life.interactions.chat.you"))}</span></div>
          <div class="interaction-chat-message is-contact">${portraitMarkup(person, {small: true})}<div><div class="interaction-chat-bubble">${esc(reply)}</div><span class="interaction-chat-meta">${esc(person.name || "")}</span></div></div>
          ${reward}${upgraded}
        </div>`;
    }).join("");
  }

  function renderChatDialog(lastResult = null) {
    const dialog = chatDialog();
    const content = document.getElementById("life-interactions-chat-content");
    const row = selectedRow();
    if (!dialog || !content || !row) return;
    const person = row.person || {};
    const topicOptions = state.data?.options?.topics || ["life"];
    if (!topicOptions.includes(state.chatTopic)) state.chatTopic = String(topicOptions[0] || "life");
    const topics = topicOptions.map((topic) => (
      `<option value="${esc(topic)}" ${String(topic) === String(state.chatTopic) ? "selected" : ""}>${esc(t(`life.interactions.topic.${topic}`))}</option>`
    )).join("");
    const rows = chatThreadRows(person.id);
    const canSend = actionPointsReady(state.data, 1) && !state.requestBusy;
    content.innerHTML = `<div class="interaction-chat-app">
      <header class="interaction-chat-contact">${portraitMarkup(person, {small: true})}<div class="interaction-chat-contact-copy"><strong>${esc(person.name || "")}</strong><span>${esc(personAffiliation(person))}</span></div><div class="interaction-chat-contact-badges">${stageBadge(row.relationship || {})}</div><span class="interaction-chat-mode"><i data-lucide="bot"></i>${esc(t("life.interactions.chat.template_mode"))}</span></header>
      <div class="interaction-chat-history" id="life-interactions-chat-history" role="log" aria-live="polite" aria-label="${esc(t("life.interactions.chat.history_label"))}">${chatThreadMarkup(rows, person, lastResult?.timeline?.id)}</div>
      <form class="interaction-chat-composer" data-interaction-form="chat">
        <input type="hidden" name="person_id" value="${Number(person.id || 0)}">
        <div class="interaction-chat-toolbar"><label><i data-lucide="hash"></i><span>${esc(t("life.interactions.chat.topic_label"))}</span><select class="interaction-select" name="topic">${topics}</select></label><span class="interaction-chat-ap"><i data-lucide="zap"></i>${Number(state.data?.action_points?.current || 0)}/${Number(state.data?.action_points?.maximum || 12)} ${esc(AP())}</span></div>
        <div class="interaction-chat-input-row"><textarea class="interaction-textarea" name="message" maxlength="500" rows="2" placeholder="${esc(t("life.interactions.chat.input_placeholder"))}"></textarea><button type="submit" class="interaction-button interaction-chat-send" ${canSend ? "" : "disabled"}><i data-lucide="send"></i><span>${esc(t("life.interactions.chat.send"))}</span><b>1 ${esc(AP())}</b></button></div>
        <small class="interaction-chat-disclaimer"><i data-lucide="lock-keyhole"></i>${esc(t("life.interactions.chat.template_notice"))}</small>
      </form>
    </div>`;
    bridge()?.renderIcons(content);
    requestAnimationFrame(() => {
      const history = document.getElementById("life-interactions-chat-history");
      if (history) history.scrollTop = history.scrollHeight;
      if (lastResult) content.querySelector("[name=message]")?.focus({preventScroll: true});
    });
  }

  function openChatDialog() {
    const dialog = chatDialog();
    if (!dialog) return;
    renderChatDialog();
    if (!dialog.open) dialog.showModal();
  }

  function closeChatDialog() {
    const dialog = chatDialog();
    if (dialog?.open) dialog.close();
  }

  function apLedgerDialog() { return document.getElementById("life-interactions-ap-ledger-dialog"); }

  function ledgerReasonLabel(reason) {
    const known = ["chat", "gift", "asset_gift", "date", "relationship", "weekly_recovery", "cdk_action_points"];
    return t(`life.interactions.ap.ledger.reason.${known.includes(reason) ? reason : "other"}`);
  }

  function renderApLedger() {
    const dialog = apLedgerDialog();
    const content = document.getElementById("life-interactions-ap-ledger-content");
    if (!dialog || !content) return;
    const points = state.data?.action_points || {};
    const ledger = Array.isArray(points.ledger) ? points.ledger : [];
    content.innerHTML = `<div class="interaction-ap-ledger-summary"><div><small>${esc(t("life.interactions.ap.title"))}</small><strong>${Number(points.current || 0)}<span> / ${Number(points.maximum || 12)}</span></strong></div><div><small>${esc(t("life.interactions.ap.ledger_total", {count: Number(points.ledger_total || ledger.length)}))}</small><span>${esc(t("life.interactions.ap.ledger_balance", {value: Number(points.current || 0)}))}</span></div></div>
      <div class="interaction-ap-ledger-list">${ledger.length ? ledger.map((row) => {
        const amount = Number(row.amount || 0);
        const date = formatGameDay(row.day);
        const detail = row.person_name
          ? t("life.interactions.ap.ledger.person", {name: row.person_name})
          : row.reason === "weekly_recovery" ? "" : String(row.detail || "");
        return `<div class="interaction-ap-ledger-row"><span class="interaction-ap-ledger-amount ${amount < 0 ? "negative" : "positive"}">${amount > 0 ? "+" : ""}${amount}</span><div><strong>${esc(ledgerReasonLabel(String(row.reason || "other")))}</strong><small>${esc([date, detail].filter(Boolean).join(" · "))}</small></div><b>${esc(t("life.interactions.ap.ledger_balance", {value: Number(row.balance_after || 0)}))}</b></div>`;
      }).join("") : `<div class="interaction-empty compact"><i data-lucide="receipt-text"></i><span>${esc(t("life.interactions.ap.ledger_empty"))}</span></div>`}</div>`;
    bridge()?.renderIcons(content);
  }

  function openApLedgerDialog() {
    const dialog = apLedgerDialog();
    if (!dialog) return;
    renderApLedger();
    if (!dialog.open) dialog.showModal();
  }

  function closeApLedgerDialog() {
    const dialog = apLedgerDialog();
    if (dialog?.open) dialog.close();
  }

  function moneyGiftDialog() {
    let dialog = document.getElementById("life-interactions-money-dialog");
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "life-interactions-money-dialog";
    dialog.className = "life-collection-dialog interaction-money-dialog";
    dialog.setAttribute("aria-labelledby", "life-interactions-money-title");
    dialog.innerHTML = `<div class="life-collection-dialog-shell"><header class="life-collection-dialog-head"><div><small class="interaction-kicker">${esc(t("life.interactions.money_gift.kicker"))}</small><h2 id="life-interactions-money-title">${esc(t("life.interactions.money_gift.title"))}</h2></div><button type="button" class="life-icon-button" data-interaction-action="close-money-gift" aria-label="${esc(t("life.interactions.close"))}" title="${esc(t("life.interactions.close"))}">×</button></header><div class="life-collection-dialog-content"><form id="life-money-form" class="interaction-dialog-form"><p class="interaction-dialog-lead" id="life-money-person"></p><label class="interaction-dialog-field"><span>${esc(t("life.interactions.money_gift.amount"))}</span><input id="life-money-amount" name="amount" type="number" min="100000" max="1000000000" step="100000" value="1000000" inputmode="numeric" required></label><p class="interaction-dialog-note">${esc(t("life.interactions.money_gift.note"))}</p><div class="interaction-dialog-actions"><button type="button" class="interaction-secondary" data-interaction-action="close-money-gift">${esc(t("life.interactions.cancel"))}</button><button type="submit" class="interaction-button" id="life-money-submit">${esc(t("life.interactions.money_gift.send"))}</button></div></form></div></div>`;
    (document.getElementById("page-life-interactions") || document.body).append(dialog);
    bridge()?.renderIcons(dialog);
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.querySelector("#life-money-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const row = selectedRow();
      const personId = Number(row?.person?.id || 0);
      const amount = Number(document.getElementById("life-money-amount")?.value || 0);
      if (!personId || !Number.isFinite(amount) || amount < 100000) {
        bridge()?.toast(t("life.interactions.money_gift.invalid"));
        return;
      }
      const button = document.getElementById("life-money-submit");
      if (button) button.disabled = true;
      try {
        const response = await performAction("/api/life/interactions/money-gift", {
          person_id: personId, amount,
        });
        closeMoneyGiftDialog();
        if (response?.result) actionToast(response.result);
      } catch (error) {
        bridge()?.toast(localizedError(error));
      } finally {
        if (button) button.disabled = false;
      }
    });
    return dialog;
  }

  function openMoneyGiftDialog() {
    const row = selectedRow();
    if (!row) return;
    const dialog = moneyGiftDialog();
    const person = row.person || {};
    const line = document.getElementById("life-money-person");
    if (line) line.textContent = t("life.interactions.money_gift.to_person", {
      name: person.name || String(person.id || ""),
    });
    const input = document.getElementById("life-money-amount");
    if (input) input.value = String(Math.max(100000, Number(input.value || 1000000)));
    if (!dialog.open) dialog.showModal();
  }

  function closeMoneyGiftDialog() {
    const dialog = document.getElementById("life-interactions-money-dialog");
    if (dialog?.open) dialog.close();
  }

  function apPurchaseDialog() {
    let dialog = document.getElementById("life-interactions-ap-dialog");
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "life-interactions-ap-dialog";
    dialog.className = "life-collection-dialog interaction-ap-dialog";
    dialog.setAttribute("aria-labelledby", "life-interactions-ap-title");
    dialog.innerHTML = `<div class="life-collection-dialog-shell"><header class="life-collection-dialog-head"><div><small class="interaction-kicker">${esc(t("life.interactions.ap.purchase_kicker"))}</small><h2 id="life-interactions-ap-title">${esc(t("life.interactions.ap.purchase_title"))}</h2></div><button type="button" class="life-icon-button" data-interaction-action="close-ap-purchase" aria-label="${esc(t("life.interactions.close"))}" title="${esc(t("life.interactions.close"))}">×</button></header><div class="life-collection-dialog-content"><form id="life-ap-form" class="interaction-dialog-form"><label class="interaction-dialog-field"><span>${esc(t("life.interactions.ap.purchase_points"))}</span><input id="life-ap-points" name="points" type="number" min="1" step="1" value="1" inputmode="numeric" required></label><p class="interaction-dialog-note" id="life-ap-quote"></p><div class="interaction-dialog-actions"><button type="button" class="interaction-secondary" data-interaction-action="close-ap-purchase">${esc(t("life.interactions.cancel"))}</button><button type="submit" class="interaction-button" id="life-ap-submit">${esc(t("life.interactions.ap.purchase_confirm"))}</button></div></form></div></div>`;
    (document.getElementById("page-life-interactions") || document.body).append(dialog);
    bridge()?.renderIcons(dialog);
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    const input = dialog.querySelector("#life-ap-points");
    input.addEventListener("input", () => renderApPurchaseQuote());
    dialog.querySelector("#life-ap-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const points = Number(input.value || 0);
      const available = Number(state.data?.action_points?.purchase_available || 0);
      if (!points || points < 1 || points > available) {
        bridge()?.toast(t("life.interactions.ap.purchase_invalid"));
        return;
      }
      const button = document.getElementById("life-ap-submit");
      if (button) button.disabled = true;
      try {
        const response = await performAction("/api/life/interactions/action-points/purchase", {points});
        closeApPurchaseDialog();
        if (response?.result) actionToast(response.result);
      } catch (error) {
        bridge()?.toast(localizedError(error));
      } finally {
        if (button) button.disabled = false;
      }
    });
    return dialog;
  }

  function renderApPurchaseQuote() {
    const points = state.data?.action_points || {};
    const input = document.getElementById("life-ap-points");
    const quote = document.getElementById("life-ap-quote");
    if (!input || !quote) return;
    const available = Math.max(0, Number(points.purchase_available || 0));
    input.max = String(available);
    const quantity = Math.max(0, Math.min(available, Number(input.value || 0)));
    const unit = Number(points.purchase_price || 0);
    quote.textContent = t("life.interactions.ap.purchase_quote", {
      points: quantity, price: fullMoney(quantity * unit), unit: fullMoney(unit),
    });
  }

  function openApPurchaseDialog() {
    const points = state.data?.action_points || {};
    if (Number(points.purchase_available || 0) <= 0) {
      bridge()?.toast(t("life.interactions.ap.purchase_full"));
      return;
    }
    const dialog = apPurchaseDialog();
    const input = document.getElementById("life-ap-points");
    if (input) input.value = "1";
    renderApPurchaseQuote();
    if (!dialog.open) dialog.showModal();
  }

  function closeApPurchaseDialog() {
    const dialog = document.getElementById("life-interactions-ap-dialog");
    if (dialog?.open) dialog.close();
  }

  function choicePersonMarkup(row) {
    const person = row?.person || {};
    return `<div class="interaction-choice-person">${portraitMarkup(person, {small: true})}<span><strong>${esc(person.name || "")}</strong><small>${esc(personAffiliation(person))}</small></span>${stageBadge(row?.relationship || {})}</div>`;
  }

  function renderGiftPicker() {
    const dialog = giftDialog();
    const content = document.getElementById("life-interactions-gift-content");
    const row = selectedRow();
    if (!dialog || !content || !row) return;
    const items = giftGroups(state.data);
    if (!items.some((item) => String(item.id) === String(state.giftItemId || ""))) {
      state.giftItemId = String(items[0]?.id || "");
    }
    const selected = items.find((item) => String(item.id) === String(state.giftItemId || "")) || null;
    const preferences = row.relationship?.preferences || {};
    const cards = items.map((item) => {
      const active = String(item.id) === String(state.giftItemId || "");
      const preferred = Boolean(preferences.gift_known && preferences.gift === String(item.category || ""));
      const category = String(item.category || "luxury");
      return `<button type="button" class="interaction-choice-card interaction-gift-choice ${active ? "is-selected" : ""} ${preferred ? "is-preferred" : ""}" data-interaction-gift-choice="${esc(item.id)}" data-gift-category="${esc(category)}" aria-pressed="${active}">
        <span class="interaction-choice-card-top"><span class="interaction-choice-icon"><i data-lucide="${GIFT_ICONS[category] || "gift"}"></i></span><span class="interaction-choice-stock">×${Number(item.count || 1)}</span></span>
        <strong>${esc(item.name || item.sku || item.id)}</strong>
        <small>${esc(t(`life.interactions.gift_category.${GIFT_CATEGORY_KEYS[String(item.category || "luxury")] || "luxury"}`))}</small>
        <span class="interaction-choice-card-bottom"><b>${esc(compactMoney(item.value || 0))}</b>${preferred ? `<em>${esc(t("life.interactions.gift.preferred"))}</em>` : ""}${active ? `<i data-lucide="check-circle-2"></i>` : ""}</span>
      </button>`;
    }).join("");
    const canGive = Boolean(selected) && actionPointsReady(state.data, 1) && !state.requestBusy;
    content.innerHTML = `${choicePersonMarkup(row)}<div class="interaction-choice-summary"><span><strong>${esc(t("life.interactions.gift.picker_title"))}</strong><small>${esc(t("life.interactions.gift.picker_detail"))}</small></span><span class="interaction-choice-ap"><i data-lucide="zap"></i>${Number(state.data?.action_points?.current || 0)}/${Number(state.data?.action_points?.maximum || 12)} ${esc(AP())}</span></div>
      ${items.length ? `<div class="interaction-choice-grid">${cards}</div>` : `<div class="interaction-empty compact"><i data-lucide="gift"></i><span>${esc(t("life.interactions.interaction_home.gift_empty"))}</span></div>`}
      <div class="interaction-choice-footer"><span class="interaction-choice-selected"><small>${esc(t("life.interactions.gift.selected"))}</small><strong>${esc(selected ? selected.name : t("life.interactions.gift.none_selected"))}</strong></span><span class="interaction-choice-actions"><button type="button" class="interaction-secondary" data-interaction-action="open-gift-shop"><i data-lucide="shopping-bag"></i>${esc(t("life.interactions.interaction_home.gift_shop"))}</button><button type="button" class="interaction-button" data-interaction-action="confirm-gift" ${canGive ? "" : "disabled"}><i data-lucide="hand-heart"></i>${esc(selected ? t("life.interactions.gift.confirm", {name: selected.name}) : t("life.interactions.gift.none_selected"))} · 1 ${esc(AP())}</button></span></div>`;
    bridge()?.renderIcons(content);
  }

  function openGiftDialog() {
    const dialog = giftDialog();
    if (!dialog) return;
    renderGiftPicker();
    if (!dialog.open) dialog.showModal();
  }

  function closeGiftDialog() {
    const dialog = giftDialog();
    if (dialog?.open) dialog.close();
  }

  function renderDatePicker() {
    const dialog = dateDialog();
    const content = document.getElementById("life-interactions-date-content");
    const row = selectedRow();
    if (!dialog || !content || !row) return;
    const activities = Array.isArray(state.data?.options?.date_activities) ? state.data.options.date_activities : [];
    const unlocked = canInviteToDate(row.relationship || {});
    if (!activities.some((activity) => String(activity.id) === String(state.dateActivityId || ""))) {
      state.dateActivityId = String(activities[0]?.id || "");
    }
    const selected = activities.find((activity) => String(activity.id) === String(state.dateActivityId || "")) || null;
    const preferences = row.relationship?.preferences || {};
    const cards = activities.map((activity) => {
      const active = String(activity.id) === String(state.dateActivityId || "");
      const cost = Number(activity.cost || 0);
      const available = unlocked && actionPointsReady(state.data, cost);
      const preferred = Boolean(preferences.activity_known && preferences.activity === String(activity.id));
      return `<button type="button" class="interaction-choice-card interaction-date-choice ${active ? "is-selected" : ""} ${preferred ? "is-preferred" : ""}" data-interaction-date-choice="${esc(activity.id)}" data-date-activity="${esc(activity.id)}" aria-pressed="${active}" ${available ? "" : "disabled"}>
        <span class="interaction-choice-card-top"><span class="interaction-choice-icon"><i data-lucide="${DATE_ICONS[String(activity.id)] || "sparkles"}"></i></span><span class="interaction-choice-stock interaction-date-cost"><i data-lucide="zap"></i><b>${cost}</b></span></span>
        <strong>${esc(t(`life.interactions.activity.${activity.id}`))}</strong>
        <small>${esc(t("life.interactions.date.picker_activity"))}</small>
        <span class="interaction-choice-card-bottom">${preferred ? `<em>${esc(t("life.interactions.date.preferred"))}</em>` : ""}${active ? `<i data-lucide="check-circle-2"></i>` : ""}</span>
      </button>`;
    }).join("");
    const canDate = Boolean(selected) && unlocked && actionPointsReady(state.data, selected.cost || 0) && !state.requestBusy;
    content.innerHTML = `${choicePersonMarkup(row)}<div class="interaction-choice-summary"><span><strong>${esc(t("life.interactions.date.picker_title"))}</strong><small>${esc(unlocked ? t("life.interactions.date.picker_detail") : t("life.interactions.date.requires_friend_detail"))}</small></span><span class="interaction-choice-ap"><i data-lucide="zap"></i>${Number(state.data?.action_points?.current || 0)}/${Number(state.data?.action_points?.maximum || 12)} ${esc(AP())}</span></div>
      ${unlocked ? `<div class="interaction-choice-grid">${cards}</div>` : `<div class="interaction-warning"><i data-lucide="lock-keyhole"></i><span>${esc(t("life.interactions.date.requires_friend"))}</span></div>`}
      <div class="interaction-choice-footer"><span class="interaction-choice-selected"><small>${esc(t("life.interactions.date.selected"))}</small><strong>${esc(selected ? t(`life.interactions.activity.${selected.id}`) : t("life.interactions.date.none_selected"))}</strong></span><span class="interaction-choice-actions"><button type="button" class="interaction-button" data-interaction-action="confirm-date" ${canDate ? "" : "disabled"}><i data-lucide="sparkles"></i>${esc(selected ? t("life.interactions.date.confirm", {name: t(`life.interactions.activity.${selected.id}`)}) : t("life.interactions.date.none_selected"))} · ${Number(selected?.cost || 0)} ${esc(AP())}</button></span></div>`;
    bridge()?.renderIcons(content);
  }

  function openDateDialog() {
    const dialog = dateDialog();
    if (!dialog) return;
    renderDatePicker();
    if (!dialog.open) dialog.showModal();
  }

  function closeDateDialog() {
    const dialog = dateDialog();
    if (dialog?.open) dialog.close();
  }
  async function removeContact(personId) {
    const id = Number(personId || 0);
    const row = rowFor(id);
    if (!id || !row) return;
    const name = String(row.person?.name || id);
    const gifted = Number(row.relationship?.owned_assets?.count || 0);
    const warning = [
      t("life.interactions.relationship.delete_confirm_body", {name}),
      gifted ? t("life.interactions.relationship.delete_gift_warning", {count: gifted}) : "",
    ].filter(Boolean).join("\n\n");
    const accepted = await bridge()?.fmoddConfirm?.(
      warning,
      t("life.interactions.relationship.delete_confirm_button"),
      t("life.interactions.relationship.delete_confirm_title"),
    );
    if (!accepted) return;
    state.requestBusy = true;
    paintWorkspace();
    try {
      const response = await postJson("/api/life/interactions/remove", {person_id: id});
      applyData(response);
      bridge()?.toast(t("life.interactions.relationship.delete_success", {name}));
    } finally {
      state.requestBusy = false;
      paintWorkspace();
    }
  }

  function profileAttributeSource(profile) {
    return Object.fromEntries(
      ["appearance", "ability", "charisma", "eq", "reputation"].map((key) => [
        key, Math.max(1, Math.floor(Number(profile?.[key] || 1))),
      ]),
    );
  }

  function profileAttributeWeight(key) {
    if (String(key) === "reputation") {
      return Math.max(1, Number(state.data?.profile_rules?.reputation_cost || 5));
    }
    return 1;
  }

  function profileIdentityCost(age, height, weight) {
    const rules = state.data?.profile_rules?.identity || {};
    const anchorAge = Number(rules.anchor_age || 30);
    const anchorHeight = Number(rules.anchor_height_cm || 180);
    const anchorWeight = Number(rules.anchor_weight_kg || 75);
    const ageGap = Math.max(0, anchorAge - Math.max(18, Number(age || anchorAge)));
    const ageCost = Math.round(Math.pow(ageGap, Number(rules.age_exponent || 1.4)) * Number(rules.age_rate || 2.2));
    const heightCost = Math.round(Math.max(0, Number(height || anchorHeight) - anchorHeight) * Number(rules.height_rate || 1.15));
    const weightCost = Math.round(Math.max(0, anchorWeight - Number(weight || anchorWeight)) * Number(rules.weight_rate || 0.9));
    return {age: ageCost, height: heightCost, weight: weightCost, total: ageCost + heightCost + weightCost};
  }

  function profileDisplayName(surname, givenName) {
    const family = String(surname || "").trim();
    const given = String(givenName || "").trim();
    if (!family) return given;
    if (!given) return family;
    return /[\u3400-\u9fff\uf900-\ufaff]/.test(family + given)
      ? `${family}${given}` : `${given} ${family}`;
  }

  function profilePointState(profile) {
    const base = Math.max(0, Number(profile?.points_base || 200));
    const earned = Math.max(0, Number(profile?.points_earned || 0));
    const attributes = profileAttributeSource(profile);
    const identity = profileIdentityCost(profile?.age, profile?.height_cm, profile?.weight_kg);
    const spent = Object.entries(attributes).reduce(
      (total, [key, value]) => total + value * profileAttributeWeight(key), 0,
    ) + identity.total;
    const total = base + earned;
    return {base, earned, spent, total, available: Math.max(0, total - spent), identity};
  }

  function ledgerRow(row) {
    const source = String(row?.source || "manual");
    const sourceKey = `life.interactions.profile.ledger_source.${source}`;
    const sourceLabel = translated(sourceKey)
      || (source === "legacy" || source.endsWith("_migration")
        ? t("life.interactions.profile.ledger_source.migration") : source);
    const reference = String(row?.reference || "").trim();
    const levelMatch = /^asset-level:(\d+)$/.exec(reference);
    let detail = "";
    if (source === "asset_level" && levelMatch) {
      detail = t("life.interactions.profile.ledger_reference.asset_level", {
        level: Number(levelMatch[1] || 0),
      });
    } else if (source === "vehicle") {
      detail = t("life.interactions.profile.ledger_reference.vehicle");
    } else if (source === "legacy" || source.endsWith("_migration")) {
      detail = t("life.interactions.profile.ledger_reference.migration");
    } else if (reference && !/^[a-z_]+-\d+$/i.test(reference) && !reference.startsWith("pre-")) {
      detail = reference;
    }
    if (!detail) detail = formatGameDay(row?.day) || "—";
    return `<div class="interaction-ledger-row"><div><strong>${esc(sourceLabel)}</strong><span>${esc(detail)}</span></div><b>+${Number(row?.points || 0)}</b></div>`;
  }

  function renderProfileForm(profile) {
    const current = profileAttributeSource(profile);
    const points = profilePointState(profile);
    const rules = state.data?.profile_rules || {};
    const minimum = Number(rules.attribute_minimum || 1);
    const completed = Boolean(profile?.completed);
    const ledger = Array.isArray(profile?.point_ledger) ? profile.point_ledger.slice(-6).reverse() : [];
    const attributes = [
      ["appearance", "life.interactions.profile.appearance", "sparkles"],
      ["ability", "life.interactions.profile.ability", "brain-circuit"],
      ["charisma", "life.interactions.profile.charisma", "message-heart"],
      ["eq", "life.interactions.profile.eq", "heart-pulse"],
      ["reputation", "life.interactions.profile.reputation", "award"],
    ];
    return `<form class="interaction-profile-form" data-interaction-form="profile" data-completed="${completed ? "true" : "false"}">
      <div class="interaction-profile-dialog-intro"><div><span class="interaction-kicker">${esc(t("life.interactions.profile.points_eyebrow"))}</span><h3>${esc(t("life.interactions.profile.points_title"))}</h3><p>${esc(t("life.interactions.profile.points_detail"))}</p></div><div class="interaction-profile-budget" data-profile-budget><span>${esc(t("life.interactions.profile.points_available"))}</span><strong data-profile-available>${points.available}</strong><small><span data-profile-spent>${points.spent}</span> / <span data-profile-total>${points.total}</span></small></div></div>
      <section class="interaction-profile-identity">
        <header><div><h3>${esc(t("life.interactions.profile.identity_title"))}</h3><p>${esc(t("life.interactions.profile.identity_detail"))}</p></div><span class="interaction-badge">${esc(t("life.interactions.profile.identity_cost_badge", {count: points.identity.total}))}</span></header>
        <div class="interaction-profile-form-grid">
          <label><span>${esc(t("life.interactions.profile.surname"))}</span><input class="interaction-input" name="surname" maxlength="40" value="${esc(profile?.surname || "")}" placeholder="${esc(t("life.interactions.profile.surname_placeholder"))}"></label>
          <label><span>${esc(t("life.interactions.profile.given_name"))}</span><input class="interaction-input" name="given_name" maxlength="40" required value="${esc(profile?.given_name || "")}" placeholder="${esc(t("life.interactions.profile.given_name_placeholder"))}"></label>
          <label><span>${esc(t("life.interactions.profile.gender"))}</span><select class="interaction-select" name="gender"><option value="male" ${String(profile?.gender || "male") === "male" ? "selected" : ""}>${esc(t("life.interactions.gender.male"))}</option><option value="female" ${String(profile?.gender || "") === "female" ? "selected" : ""}>${esc(t("life.interactions.gender.female"))}</option><option value="nonbinary" ${String(profile?.gender || "") === "nonbinary" ? "selected" : ""}>${esc(t("life.interactions.gender.nonbinary"))}</option></select></label>
          <label><span>${esc(t("life.interactions.profile.age"))}</span><input class="interaction-input" name="age" type="number" min="18" max="99" value="${Number(profile?.age || 30)}" data-profile-identity="age"></label>
          <label><span>${esc(t("life.interactions.profile.height"))}</span><input class="interaction-input" name="height_cm" type="number" min="120" max="230" value="${Number(profile?.height_cm || 180)}" data-profile-identity="height"></label>
          <label><span>${esc(t("life.interactions.profile.weight"))}</span><input class="interaction-input" name="weight_kg" type="number" min="35" max="200" value="${Number(profile?.weight_kg || 75)}" data-profile-identity="weight"></label>
          <label class="span-2"><span>${esc(t("life.interactions.profile.bio"))}</span><textarea class="interaction-textarea" name="bio" maxlength="500">${esc(profile?.bio || "")}</textarea></label>
        </div>
        <div class="interaction-profile-identity-costs" data-profile-identity-costs><span><b>${esc(t("life.interactions.profile.identity_cost_total"))}</b><strong data-profile-identity-total>${points.identity.total}</strong></span><span data-profile-identity-breakdown>${esc(t("life.interactions.profile.identity_cost_breakdown", {age: points.identity.age, height: points.identity.height, weight: points.identity.weight}))}</span><small data-profile-name-preview>${esc(t("life.interactions.profile.name_preview", {name: profile?.name || t("life.interactions.profile.unnamed")}))}</small></div>
      </section>
      <section class="interaction-profile-allocation"><header><div><h3>${esc(t("life.interactions.profile.allocation_title"))}</h3><p>${esc(t("life.interactions.profile.allocation_detail_unbounded", {min: minimum}))}</p></div><span class="interaction-badge">${esc(t("life.interactions.profile.points_total", {count: points.total}))}</span></header><div class="interaction-profile-stat-grid">${attributes.map(([key, labelKey, icon]) => {
        const floor = completed ? current[key] : minimum;
        const rangeMax = Math.max(floor, current[key], points.total);
        const weight = profileAttributeWeight(key);
        const costTag = weight > 1
          ? `<em class="interaction-profile-stat-cost">${esc(t("life.interactions.profile.reputation_cost", {cost: weight}))}</em>` : "";
        return `<article class="interaction-profile-stat ${key === "reputation" ? "is-reputation" : ""}" data-profile-stat="${key}"><header><span><i data-lucide="${icon}"></i>${esc(t(labelKey))}${costTag}</span><strong data-profile-stat-value="${key}">${current[key]}</strong></header><input type="range" min="${floor}" max="${rangeMax}" step="1" value="${current[key]}" data-profile-range="${key}" aria-label="${esc(t(labelKey))}"><input class="interaction-profile-number" type="number" name="${key}" min="${floor}" step="1" value="${current[key]}" data-profile-number="${key}" data-profile-weight="${weight}"></article>`;
      }).join("")}</div><div class="interaction-profile-allocation-foot"><span data-profile-status role="status"></span><span>${esc(t("life.interactions.profile.points_ledger_note"))}</span></div></section>
      <section class="interaction-profile-ledger"><div><h3>${esc(t("life.interactions.profile.ledger_title"))}</h3><p>${esc(t("life.interactions.profile.ledger_detail"))}</p></div><div class="interaction-ledger-list">${ledger.length ? ledger.map(ledgerRow).join("") : `<span class="interaction-inline-note">${esc(t("life.interactions.profile.ledger_empty"))}</span>`}</div></section>
      <p class="interaction-inline-note interaction-profile-attribute-rule">${esc(t(completed ? "life.interactions.profile.attribute_only_increase" : "life.interactions.profile.save_note"))}</p>
      <div class="interaction-profile-savebar"><span>${esc(t("life.interactions.profile.savebar_available"))} <b data-profile-save-available>${points.available}</b></span><button type="submit" class="interaction-button interaction-profile-save"><i data-lucide="save"></i>${esc(t("life.interactions.profile.save"))}</button></div>
    </form>`;
  }

  function updateProfileBudget(form) {
    if (!form) return;
    const profile = state.data?.profile || {};
    const current = profileAttributeSource(profile);
    const completed = Boolean(profile?.completed);
    const base = Number(profile.points_base || 200);
    const total = base + Number(profile.points_earned || 0);
    let attributeSpent = 0;
    let attributeReduced = false;
    form.querySelectorAll("[data-profile-number]").forEach((input) => {
      const key = String(input.dataset.profileNumber || "");
      const value = Math.max(1, Math.floor(Number(input.value || 1)));
      const weight = Math.max(1, Number(input.dataset.profileWeight || profileAttributeWeight(key)));
      attributeSpent += value * weight;
      if (completed && key && value < Number(current[key] || 0)) attributeReduced = true;
    });
    const age = form.querySelector('input[name="age"]')?.value;
    const height = form.querySelector('input[name="height_cm"]')?.value;
    const weight = form.querySelector('input[name="weight_kg"]')?.value;
    const identity = profileIdentityCost(age, height, weight);
    const spent = attributeSpent + identity.total;
    const available = total - spent;
    const availableNode = form.querySelector("[data-profile-available]");
    const spentNode = form.querySelector("[data-profile-spent]");
    const totalNode = form.querySelector("[data-profile-total]");
    const saveAvailable = form.querySelector("[data-profile-save-available]");
    const identityTotal = form.querySelector("[data-profile-identity-total]");
    const identityBreakdown = form.querySelector("[data-profile-identity-breakdown]");
    const namePreview = form.querySelector("[data-profile-name-preview]");
    const status = form.querySelector("[data-profile-status]");
    const save = form.querySelector('button[type="submit"]');
    if (availableNode) availableNode.textContent = String(Math.max(0, available));
    if (spentNode) spentNode.textContent = String(Math.max(0, spent));
    if (totalNode) totalNode.textContent = String(total);
    if (saveAvailable) saveAvailable.textContent = String(Math.max(0, available));
    if (identityTotal) identityTotal.textContent = String(identity.total);
    if (identityBreakdown) identityBreakdown.textContent = t("life.interactions.profile.identity_cost_breakdown", {
      age: identity.age, height: identity.height, weight: identity.weight,
    });
    if (namePreview) namePreview.textContent = t("life.interactions.profile.name_preview", {
      name: profileDisplayName(form.querySelector('input[name="surname"]')?.value, form.querySelector('input[name="given_name"]')?.value)
        || t("life.interactions.profile.unnamed"),
    });
    const overBudget = available < 0;
    const valid = !overBudget && !attributeReduced;
    if (status) {
      status.textContent = attributeReduced
        ? t("life.interactions.profile.attribute_only_increase")
        : overBudget
          ? t("life.interactions.profile.points_over", {count: Math.abs(available)})
          : t("life.interactions.profile.points_remaining", {count: Math.max(0, available)});
      status.classList.toggle("is-over", overBudget || attributeReduced);
    }
    form.classList.toggle("is-over-budget", overBudget);
    form.classList.toggle("is-attribute-reduced", attributeReduced);
    if (save) save.disabled = !valid || state.requestBusy;
  }

  function syncProfileStat(form, key, value, source) {
    if (!form || !key) return;
    const current = profileAttributeSource(state.data?.profile || {});
    const completed = Boolean(state.data?.profile?.completed);
    const floor = completed ? Number(current[key] || 1) : Number(state.data?.profile_rules?.attribute_minimum || 1);
    const numeric = Math.max(floor, Math.floor(Number(value) || floor));
    form.querySelectorAll(`[data-profile-stat="${key}"]`).forEach((card) => {
      card.querySelectorAll("[data-profile-range], [data-profile-number]").forEach((input) => {
        if (input !== source) input.value = String(numeric);
      });
      const output = card.querySelector(`[data-profile-stat-value="${key}"]`);
      if (output) output.textContent = String(numeric);
    });
    updateProfileBudget(form);
  }

  function syncProfileIdentity(form, key, value, source) {
    if (!form || !key) return;
    const limits = key === "age" ? [18, 99] : key === "height" ? [120, 230] : [35, 200];
    const numeric = Math.max(limits[0], Math.min(limits[1], Math.floor(Number(value) || limits[0])));
    if (source && source.value !== String(numeric)) source.value = String(numeric);
    form.querySelectorAll(`[data-profile-identity="${key}"]`).forEach((input) => {
      if (input !== source) input.value = String(numeric);
    });
    updateProfileBudget(form);
  }

  function openProfileDialog() {
    const dialog = profileDialog();
    const content = document.getElementById("life-interactions-profile-content");
    if (!dialog || !content) return;
    content.innerHTML = renderProfileForm(state.data?.profile || {});
    updateProfileBudget(content.querySelector("[data-interaction-form=profile]"));
    bridge()?.renderIcons(dialog);
    if (!dialog.open) dialog.showModal();
  }

  function closeProfileDialog() {
    const dialog = profileDialog();
    if (dialog?.open) dialog.close();
  }

  function pendingEventById(eventId) {
    return (state.data?.pending_events || []).find(
      (event) => String(event.id || "") === String(eventId || ""),
    ) || null;
  }

  function renderEventDialog(event) {
    const content = document.getElementById("life-interactions-event-content");
    if (!content || !event) return;
    const kind = String(event.kind || "relationship_crisis");
    const data = event.data || {};
    const options = (event.options || []).map((option) => {
      const irreversible = ["end_pregnancy", "end_public_relationship", "accept_separation"].includes(option);
      return `<button type="button" class="interaction-event-option ${irreversible ? "is-irreversible" : ""}" data-interaction-event-option="${esc(option)}" data-interaction-event-person="${Number(event.person_id || 0)}" ${state.requestBusy ? "disabled" : ""}><span class="interaction-event-option-icon"><i data-lucide="${eventOptionIcon(option)}"></i></span><span class="interaction-event-option-copy"><strong>${esc(eventOptionLabel(kind, option))}</strong><small>${esc(eventOptionDetail(kind, option))}</small>${irreversible ? `<span class="interaction-event-option-warning">${esc(t("life.interactions.event.irreversible"))}</span>` : ""}</span></button>`;
    }).join("");
    const facts = [];
    if (kind === "pregnancy") {
      facts.push(`${esc(t("life.interactions.event.pregnancy.conceived"))}<strong>${esc(formatGameDay(data.conceived_day))}</strong>`);
      const dueEarly = Number(data.due_early || data.due_day || 0);
      const dueLate = Number(data.due_late || data.due_day || 0);
      const dueText = dueEarly && dueLate && dueEarly !== dueLate
        ? `${formatGameDay(dueEarly)} – ${formatGameDay(dueLate)}`
        : formatGameDay(data.due_day);
      facts.push(`${esc(t("life.interactions.event.pregnancy.due"))}<strong>${esc(dueText)}</strong>`);
    } else if (kind === "secret_exposure") {
      facts.push(`${esc(t("life.interactions.event.secret_exposure.risk"))}<strong>${Number(data.risk || 0).toFixed(1)}</strong>`);
      facts.push(`${esc(t("life.interactions.event.secret_exposure.chance"))}<strong>${percent(data.chance || 0, 1)}</strong>`);
    } else if (kind === "child_football") {
      facts.push(`${esc(t("life.interactions.event.child_football.age"))}<strong>${Number(data.age || 0)}</strong>`);
      facts.push(`${esc(t("life.interactions.event.child_football.ca"))}<strong>${Number(data.ca || 0)}</strong>`);
      facts.push(`${esc(t("life.interactions.event.child_football.pa"))}<strong>${Number(data.pa || 0)}</strong>`);
    } else {
      facts.push(`${esc(t("life.interactions.event.relationship_crisis.intimacy"))}<strong>${Number(data.intimacy || 0).toFixed(1)}</strong>`);
    }
    content.innerHTML = `<div class="interaction-event-hero"><span class="interaction-event-option-icon"><i data-lucide="${eventKindIcon(kind)}"></i></span><div class="interaction-event-hero-copy"><strong>${esc(event.person_name || "")}</strong><span>${esc(t("life.interactions.event.kind." + kind))}</span></div><span class="interaction-event-kind"><i data-lucide="${eventKindIcon(kind)}"></i>${esc(eventKindLabel(kind))}</span></div><div class="interaction-event-body"><p>${esc(eventDescription(event))}</p><div class="interaction-event-facts">${facts.map((fact) => `<span>${fact}</span>`).join("")}</div></div><div class="interaction-event-options">${options}</div>`;
    bridge()?.renderIcons(content);
  }

  function openEventDialog(eventId) {
    const dialog = eventDialog();
    const event = pendingEventById(eventId);
    if (!dialog || !event) return;
    state.eventId = String(event.id || "");
    renderEventDialog(event);
    if (!dialog.open) dialog.showModal();
  }

  function closeEventDialog(dismiss = true) {
    const dialog = eventDialog();
    if (dismiss && state.eventId) state.dismissedEventIds.add(String(state.eventId));
    state.eventId = "";
    if (dialog?.open) dialog.close();
  }

  function maybeOpenPendingEvent() {
    const dialog = eventDialog();
    if (!dialog || dialog.open || !state.data || state.requestBusy) return;
    if ([profileDialog(), resultDialog(), chatDialog(), giftDialog(), dateDialog()].some((other) => other?.open)) return;
    const event = (state.data.pending_events || []).find(
      (row) => !state.dismissedEventIds.has(String(row.id || "")),
    );
    if (event) openEventDialog(event.id);
  }

  function paintHeader() {
    const node = document.getElementById("life-interactions-action-points");
    if (!node) return;
    const points = state.data?.action_points || {};
    node.innerHTML = `<i data-lucide="zap"></i><span>${esc(t("life.interactions.ap.short"))}</span><strong>${Number(points.current || 0)}/${Number(points.maximum || 12)}</strong>`;
  }

  function travelLocaleName(row) {
    const locale = String(
      bridge()?.getState?.()?.settings?.ui_locale
      || document.documentElement.lang || "en",
    ).toLowerCase();
    return String(
      locale.startsWith("zh") ? row?.name_zh : row?.name_en
    ) || String(row?.name_zh || row?.name_en || row?.id || "");
  }

  function travelCityName(countryCode, cityId) {
    const target = String(cityId || "").trim();
    if (!target) return "";
    const country = travelCountries().find(
      (row) => String(row.code) === String(countryCode || ""),
    ) || travelCountries().find(
      (row) => (row.cities || []).some((city) => String(city.id) === target),
    );
    const city = (country?.cities || []).find((row) => String(row.id) === target);
    return city ? travelLocaleName(city) : target;
  }

  function travelCountries() {
    return Array.isArray(state.travelCatalog?.countries) ? state.travelCatalog.countries : [];
  }

  function travelSelectedCountry() {
    const rows = travelCountries();
    return rows.find((row) => String(row.code) === String(state.travelCountry))
      || rows[0] || null;
  }

  function travelSelectedCity(country) {
    const rows = Array.isArray(country?.cities) ? country.cities : [];
    return rows.find((row) => String(row.id) === String(state.travelCity))
      || rows[0] || null;
  }

  function travelSelectedPlace(city) {
    const rows = Array.isArray(city?.places) ? city.places : [];
    return String(state.travelPlace || rows[0] || "");
  }

  function travelCountryLabel(code) {
    const row = travelCountries().find((item) => String(item.code) === String(code));
    return row ? travelLocaleName(row) : String(code || "");
  }

  function travelPersonaLabel(person) {
    const key = String(person?.occupation_key || person?.persona_key || "");
    if (key) {
      const value = translated(`life.interactions.travel.persona.${key}`);
      if (value) return value;
    }
    return String(person?.persona || key || t("life.interactions.travel.persona.traveler"));
  }

  function travelSourceLabel(source) {
    return String(source) === "encounter"
      ? t("life.interactions.travel.source_encounter")
      : t("life.interactions.travel.source_fm");
  }

  async function loadTravelCatalog() {
    if (state.travelCatalog || state.travelLoading) return;
    state.travelLoading = true;
    paintWorkspace();
    try {
      const response = await requestJson("/api/life/interactions/travel");
      state.travelCatalog = response?.catalog || { countries: [] };
      if (response?.travel && state.data) state.data.travel = response.travel;
      if (response?.asset_level && state.data) state.data.asset_level = response.asset_level;
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.travelLoading = false;
      paintWorkspace();
    }
  }

  async function travelGoOut(cityId, place) {
    if (state.travelBusy) return;
    const country = travelSelectedCountry();
    const city = travelSelectedCity(country);
    const targetCity = String(cityId || city?.id || "");
    if (!country || !targetCity) return;
    const targetPlace = String(place || travelSelectedPlace(city) || "");
    state.travelBusy = true;
    state.travelCity = targetCity;
    state.travelPlace = targetPlace;
    paintWorkspace();
    try {
      const response = await postJson("/api/life/interactions/travel/go-out", {
        country: country.code, city: targetCity, place: targetPlace,
      });
      applyLifeView(response);
      bridge()?.toast(response?.travel_missed
        ? t("life.interactions.travel.missed", { city: travelLocaleName(city) })
        : t("life.interactions.travel.met"));
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.travelBusy = false;
      paintWorkspace();
    }
  }

  async function travelEncounterAction(action) {
    if (state.travelBusy) return;
    state.travelBusy = true;
    paintWorkspace();
    try {
      const response = await postJson("/api/life/interactions/travel/encounter", {
        action: String(action),
      });
      applyLifeView(response);
      const result = response?.travel_result || {};
      if (action === "ask") {
        bridge()?.toast(String(result.message || t("life.interactions.travel.ask_done")));
      } else if (action === "goodbye") {
        bridge()?.toast(t("life.interactions.travel.goodbye_done"));
      } else {
        bridge()?.toast(t("life.interactions.travel.chat_done"));
      }
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.travelBusy = false;
      paintWorkspace();
    }
  }

  function isEncounterPerson(person) {
    return Boolean(person && (person.source === "encounter" || person.npc === true));
  }

  function personAffiliation(person) {
    if (!person) return t("life.interactions.free_agent");
    if (isEncounterPerson(person)) {
      const persona = travelPersonaLabel(person);
      return persona || t("life.interactions.travel.source_encounter");
    }
    return String(person.team_name || t("life.interactions.free_agent"));
  }

  function personNationality(person) {
    if (!person) return "";
    if (isEncounterPerson(person)) {
      const code = String(person.nationality_code || person.nationality || "");
      return code ? travelCountryLabel(code) : "";
    }
    return String(person.nationality || "");
  }

  function renderTravelStage(pending) {
    if (!pending) return "";
    const person = pending.person || {};
    const relation = pending.relationship || {};
    const name = String(person.name || t("life.interactions.travel.unknown_person"));
    const known = Boolean(relation.contact_known);
    const place = String(pending.place || "");
    const city = travelLocaleName({
      name_zh: pending.city_name_zh, name_en: pending.city_name_en, id: pending.city,
    });
    return `<section class="interaction-travel-stage">
      <div class="interaction-travel-stage-person">
        ${portraitMarkup(person, { small: false })}
        <div>
          <span class="interaction-kicker">${esc(travelSourceLabel(pending.source))}</span>
          <h3>${esc(name)}</h3>
          <p>${esc(travelPersonaLabel(person))}${person.age ? ` · ${Number(person.age)}` : ""}</p>
          <div class="interaction-travel-tags">
            <span class="interaction-badge">${esc(t("life.interactions.travel.met_at", { city, place }))}</span>
            ${known ? `<span class="interaction-badge partner">${esc(t("life.interactions.travel.known"))}</span>` : ""}
          </div>
        </div>
      </div>
      <div class="interaction-travel-stage-copy">
        <p>${esc(t("life.interactions.travel.stage_copy", { city, place }))}</p>
        <div class="interaction-travel-stage-stats">
          <span><small>${esc(t("life.interactions.travel.affection"))}</small><b>${Number(relation.affection || 0).toFixed(0)}</b></span>
          <span><small>${esc(t("life.interactions.travel.chat_count"))}</small><b>${Number(relation.chat_count || 0)}</b></span>
          <span><small>${esc(t("life.interactions.travel.source"))}</small><b>${esc(travelSourceLabel(pending.source))}</b></span>
        </div>
        <div class="interaction-travel-stage-actions">
          <button type="button" class="interaction-button" data-travel-encounter="chat" ${state.travelBusy ? "disabled" : ""}><i data-lucide="message-circle"></i>${esc(t("life.interactions.travel.chat"))}</button>
          ${known ? "" : `<button type="button" class="interaction-secondary" data-travel-encounter="ask" ${state.travelBusy ? "disabled" : ""}><i data-lucide="phone"></i>${esc(t("life.interactions.travel.ask"))}</button>`}
          <button type="button" class="interaction-secondary" data-travel-encounter="goodbye" ${state.travelBusy ? "disabled" : ""}><i data-lucide="log-out"></i>${esc(t("life.interactions.travel.goodbye"))}</button>
        </div>
      </div>
    </section>`;
  }

  function renderTravel(data) {
    const catalog = state.travelCatalog;
    if (!catalog) {
      return `<div class="interaction-section-head"><div><h2>${esc(t("life.interactions.travel.title"))}</h2><p>${esc(t("life.interactions.travel.subtitle"))}</p></div></div><div class="interaction-empty"><i data-lucide="map"></i><span>${esc(state.travelLoading ? t("life.interactions.travel.loading") : t("life.interactions.travel.empty_catalog"))}</span>${state.travelLoading ? "" : `<button type="button" class="interaction-button" data-travel-reload><i data-lucide="refresh-cw"></i>${esc(t("life.interactions.travel.reload"))}</button>`}</div>`;
    }
    const countries = travelCountries();
    if (!state.travelCountry && countries.length) state.travelCountry = String(countries[0].code);
    const country = travelSelectedCountry();
    const city = travelSelectedCity(country);
    if (country && !state.travelCity && city) state.travelCity = String(city.id);
    if (city && !state.travelPlace) state.travelPlace = String(city.places?.[0] || "");
    const travel = data?.travel || {};
    const pending = travel.pending || null;
    const assetLevel = Number(data?.asset_level?.current_level || data?.asset_level?.level || 0);
    const adult = Boolean(data?.adult_content_enabled);
    const chance = Number(travel.encounter_chance || 0);
    const currentName = city ? travelLocaleName(city) : t("life.interactions.travel.no_city");
    const contacts = (data?.relationships || []).filter((row) => (
      row?.relationship?.met_city || row?.person?.source === "encounter"
    )).slice(0, 4);
    const countryChips = countries.map((row) => `<button type="button" class="interaction-travel-country ${String(row.code) === String(country?.code) ? "active" : ""}" data-travel-country="${esc(row.code)}"><i data-lucide="globe-2"></i><span>${esc(travelLocaleName(row))}</span><b>${(row.cities || []).length}</b></button>`).join("");
    const shownCities = (country?.cities || []).slice(0, Math.max(3, Number(state.travelCityLimit || 9)));
    const remainingCities = Math.max(0, (country?.cities || []).length - shownCities.length);
    const cityCards = shownCities.map((row) => `<article class="interaction-travel-city ${String(row.id) === String(city?.id) ? "active" : ""}">
      <button type="button" class="interaction-travel-city-head" data-travel-city="${esc(row.id)}"><span class="interaction-travel-postcard"><i data-lucide="landmark"></i></span><span><strong>${esc(travelLocaleName(row))}</strong><small>${esc(t("life.interactions.travel.place_count", { count: (row.places || []).length }))}</small></span><i data-lucide="chevron-right"></i></button>
      <div class="interaction-travel-places">${(row.places || []).slice(0, 5).map((place) => `<button type="button" class="interaction-travel-place ${String(row.id) === String(city?.id) && String(place) === String(state.travelPlace) ? "active" : ""}" data-travel-place="${esc(place)}" data-travel-city-id="${esc(row.id)}">${esc(place)}</button>`).join("")}</div>
    </article>`).join("");
    const contactCards = contacts.length ? `<div class="interaction-travel-contact-grid">${contacts.map((row) => `<button type="button" class="interaction-travel-contact" data-interaction-person-select="${Number(row.person?.id || 0)}"><span class="interaction-travel-contact-avatar">${row.person?.portrait_uid ? `<img src="/api/portrait/${Number(row.person.portrait_uid)}" alt="">` : `<i data-lucide="user-round"></i>`}</span><span><strong>${esc(row.person?.name || "")}</strong><small>${esc([personAffiliation(row.person), travelCityName(row.person?.met_country || row.relationship?.met_country, row.relationship?.met_city || row.person?.met_city)].filter(Boolean).join(" · "))}</small></span><i data-lucide="chevron-right"></i></button>`).join("")}</div>` : `<div class="interaction-empty compact"><i data-lucide="users-round"></i><span>${esc(t("life.interactions.travel.no_contacts"))}</span></div>`;
    return `<div class="interaction-section-head"><div><h2>${esc(t("life.interactions.travel.title"))}</h2><p>${esc(t("life.interactions.travel.subtitle"))}</p></div><span class="interaction-badge">${esc(t("life.interactions.travel.chance", { chance: percent(chance, 0) }))}</span></div>
      <section class="interaction-travel-hero">
        <div><span class="interaction-kicker">${esc(t("life.interactions.travel.eyebrow"))}</span><h3>${esc(t("life.interactions.travel.hero_title", { city: currentName }))}</h3><p>${esc(t("life.interactions.travel.hero_copy"))}</p></div>
        <div class="interaction-travel-hero-side">
          <div class="interaction-travel-stat"><small>${esc(t("life.interactions.travel.ap"))}</small><b>${Number(data?.action_points?.current || 0)} / ${Number(data?.action_points?.maximum || 0)}</b></div>
          <div class="interaction-travel-stat"><small>${esc(t("life.interactions.travel.asset_level"))}</small><b>Lv.${assetLevel}</b></div>
          <div class="interaction-travel-stat"><small>${esc(t("life.interactions.travel.chance_label"))}</small><b>${percent(chance, 0)}</b></div>
          <span class="interaction-badge ${adult ? "partner" : "secret"}">${esc(adult ? t("life.interactions.travel.adult_on") : t("life.interactions.travel.adult_off"))}</span>
        </div>
      </section>
      ${pending ? renderTravelStage(pending) : ""}
      <div class="interaction-travel-layout">
        <div class="interaction-travel-main">
          <section class="interaction-travel-panel"><header><h3>${esc(t("life.interactions.travel.countries"))}</h3><span>${esc(t("life.interactions.travel.country_note"))}</span></header><div class="interaction-travel-countries">${countryChips}</div></section>
          <section class="interaction-travel-panel"><header><h3>${esc(country ? travelLocaleName(country) : "")}</h3><span>${esc(t("life.interactions.travel.city_note"))}</span><button type="button" class="interaction-secondary" data-travel-go ${state.travelBusy ? "disabled" : ""}><i data-lucide="footprints"></i>${esc(t("life.interactions.travel.go_out"))}</button></header><div class="interaction-travel-city-grid">${cityCards}</div>${remainingCities > 0 ? `<button type="button" class="interaction-secondary interaction-travel-more" data-travel-more-cities><i data-lucide="chevron-down"></i>${esc(t("life.interactions.travel.more_cities", { count: remainingCities }))}</button>` : ""}</section>
          <section class="interaction-travel-panel"><header><h3>${esc(t("life.interactions.travel.recent"))}</h3><span>${esc(t("life.interactions.travel.recent_note"))}</span></header>${contactCards}</section>
        </div>
        <aside class="interaction-travel-side">
          <section class="interaction-travel-panel"><header><h3>${esc(t("life.interactions.travel.current"))}</h3></header><div class="interaction-travel-facts"><span><small>${esc(t("life.interactions.travel.city"))}</small><b>${esc(currentName)}</b></span><span><small>${esc(t("life.interactions.travel.place"))}</small><b>${esc(state.travelPlace || "—")}</b></span><span><small>${esc(t("life.interactions.travel.asset_bonus"))}</small><b>+${percent(Number(travel.asset_bonus || 0), 0)}</b></span><span><small>${esc(t("life.interactions.travel.adult_state"))}</small><b>${esc(adult ? t("life.interactions.travel.adult_on") : t("life.interactions.travel.adult_off"))}</b></span></div></section>
          <section class="interaction-travel-panel"><header><h3>${esc(t("life.interactions.travel.visits"))}</h3><span>${esc(t("life.interactions.travel.visits_note"))}</span></header>${(travel.visits || []).length ? `<div class="interaction-travel-visits">${(travel.visits || []).slice(-4).reverse().map((row) => `<span><i data-lucide="map-pin"></i><b>${esc(travelCountryLabel(row.country))}</b><small>${esc(row.place || row.city || "")}</small></span>`).join("")}</div>` : `<p class="interaction-travel-note">${esc(t("life.interactions.travel.no_visits"))}</p>`}</section>
          <section class="interaction-travel-panel"><header><h3>${esc(t("life.interactions.travel.rules"))}</h3></header><p class="interaction-travel-note">${esc(t("life.interactions.travel.rules_copy"))}</p></section>
          ${adult ? "" : `<section class="interaction-travel-panel interaction-travel-adult-lock"><i data-lucide="lock"></i><p>${esc(t("life.interactions.travel.adult_locked"))}</p><button type="button" class="interaction-secondary" data-travel-adult-settings>${esc(t("life.interactions.travel.open_settings"))}</button></section>`}
        </aside>
      </div>`;
  }

  function renderWorkspace(data) {
    if (state.tab === "people") return renderPeople(data);
    if (state.tab === "travel") return renderTravel(data);
    if (state.tab === "search") return renderSearch(data);
    if (state.tab === "assets") return renderAssets(data);
    if (state.tab === "family") return renderFamily(data);
    if (state.tab === "timeline") return renderTimeline(data);
    return renderOverview(data);
  }

  function paintWorkspace() {
    const root = pageRoot();
    const content = document.getElementById("life-interactions-content");
    if (!root || !content) return;
    let markup = "";
    if (state.loading && !state.data) {
      markup = `<div class="interaction-loading"><span class="interaction-spinner"></span><span>${esc(t("life.interactions.loading"))}</span></div>`;
    } else if (state.error && !state.data) {
      markup = `<div class="interaction-error"><i data-lucide="circle-alert"></i><span>${esc(localizedError(state.error))}</span><button type="button" class="interaction-secondary" data-interaction-action="reload">${esc(t("life.interactions.retry"))}</button></div>`;
    } else if (!state.data) {
      markup = `<div class="interaction-empty"><i data-lucide="heart-handshake"></i><span>${esc(t("life.interactions.empty"))}</span></div>`;
    } else {
      markup = `${renderTabs(state.data, "main")}<div class="interaction-workspace-view">${renderWorkspace(state.data)}</div>`;
    }
    content.innerHTML = markup;
    updateProfileBudget(document.querySelector("[data-interaction-form=profile]"));
    paintHeader();
    root.setAttribute("aria-busy", state.loading || state.requestBusy ? "true" : "false");
    root.classList.toggle("interaction-busy", state.requestBusy);
    bridge()?.renderIcons(root);
    window.setTimeout(maybeOpenPendingEvent, 0);
  }

  function formValues(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  function actionToast(result) {
    if (!result) return;
    if (result.kind === "relationship") {
      bridge()?.toast(t(result.success
        ? "life.interactions.toast.relationship_success"
        : "life.interactions.toast.relationship_fail", {
        action: t(`life.interactions.relationship.action.${result.target || ""}`),
        chance: percent(result.chance || 0, 1),
      }));
    } else if (result.kind === "chat") {
      bridge()?.toast(t(result.preference_match
        ? "life.interactions.toast.chat_preferred"
        : "life.interactions.toast.chat_done"));
    } else if (result.kind === "gift") {
      bridge()?.toast(t(result.preference_match
        ? "life.interactions.toast.gift_preferred"
        : "life.interactions.toast.gift_done"));
    } else if (result.kind === "date") {
      bridge()?.toast(t(result.preference_match
        ? "life.interactions.toast.date_preferred"
        : "life.interactions.toast.date_done"));
    } else if (result.kind === "intimacy") {
      bridge()?.toast(t("life.interactions.toast.intimacy_done", {
        action: intimacyActionLabel(result.action),
      }));
    } else if (result.kind === "money_gift") {
      bridge()?.toast(t("life.interactions.toast.money_gift_done", {
        amount: fullMoney(result.amount || 0),
      }));
    } else if (result.kind === "action_points") {
      bridge()?.toast(t("life.interactions.toast.action_points_done", {
        points: Number(result.points || 0), price: fullMoney(result.cost || 0),
      }));
    }
  }

  async function performAction(path, body) {
    state.requestBusy = true;
    paintWorkspace();
    try {
      const response = await postJson(path, body);
      applyData(response, body.person_id || 0);
      return response;
    } finally {
      state.requestBusy = false;
      paintWorkspace();
    }
  }

  async function submitChat(form) {
    const values = formValues(form);
    state.chatTopic = String(values.topic || "");
    const response = await performAction("/api/life/interactions/chat", {
      person_id: Number(values.person_id || 0), topic: String(values.topic || ""),
      message: String(values.message || "").trim().slice(0, 500),
    });
    renderChatDialog(response.result);
  }

  async function submitGift(form) {
    const values = form instanceof HTMLFormElement ? formValues(form) : (form || {});
    const response = await performAction("/api/life/interactions/gift", {
      person_id: Number(values.person_id || 0), item_id: String(values.item_id || ""),
    });
    closeGiftDialog();
    actionToast(response.result);
    showActionResult(response.result, selectedRow());
  }

  async function submitDate(form) {
    const values = form instanceof HTMLFormElement ? formValues(form) : (form || {});
    const response = await performAction("/api/life/interactions/date", {
      person_id: Number(values.person_id || 0), activity: String(values.activity || ""),
    });
    closeDateDialog();
    actionToast(response.result);
    showActionResult(response.result, selectedRow());
  }

  async function submitIntimacy(actionId) {
    const personId = Number(selectedRow()?.person?.id || 0);
    if (!personId || !actionId) return;
    const protection = String(
      document.querySelector("[data-intimacy-protection]")?.value || "",
    );
    const response = await performAction("/api/life/interactions/intimacy", {
      person_id: personId, action: String(actionId), protection,
    });
    actionToast(response.result);
    showActionResult(response.result, selectedRow());
  }

  async function submitEvent(eventId, option, personId) {
    if (!eventId || !option) return;
    const event = pendingEventById(eventId);
    const label = event ? eventOptionLabel(event.kind, option) : option;
    const destructive = ["end_pregnancy", "end_public_relationship", "accept_separation"].includes(option);
    if (destructive) {
      const accepted = await bridge().fmoddConfirm(
        t("life.interactions.event.confirm_body", {
          name: event?.person_name || "",
          option: label,
        }),
        label,
        t("life.interactions.event.confirm_title"),
      );
      if (!accepted) return;
    }
    const response = await performAction("/api/life/interactions/event", {
      event_id: String(eventId),
      option: String(option),
      person_id: Number(personId || event?.person_id || 0),
    });
    state.dismissedEventIds.delete(String(eventId));
    closeEventDialog(false);
    bridge()?.toast(t("life.interactions.toast.event_resolved"));
    showActionResult(response.result, selectedRow());
  }

  async function submitResidence(personId, assetId) {
    const response = await performAction("/api/life/interactions/residence", {
      person_id: Number(personId || 0), asset_id: String(assetId || ""),
    });
    state.residenceSelectionPerson = 0;
    state.residenceSelectionId = "";
    paintWorkspace();
    bridge()?.toast(t(response.result?.asset_id
      ? "life.interactions.toast.residence_in"
      : "life.interactions.toast.residence_out"));
  }

  async function submitAssetGift(assetType, assetId) {
    const row = selectedRow();
    const personId = Number(row?.person?.id || 0);
    if (!personId || !assetType || !assetId) return;
    const preview = await postJson("/api/life/interactions/gift-asset", {
      person_id: personId, asset_type: assetType, asset_id: assetId, confirm: false,
    });
    const plan = preview.plan || {};
    const stageCopy = plan.may_upgrade
      ? t("life.interactions.asset.stage_after", {
        stage: t(`life.interactions.social.${String(plan.social_stage_after || "acquaintance")}`),
      })
      : t("life.interactions.asset.stage_hold");
    const warning = [
      t("life.interactions.asset.confirm_title"),
      `${assetGiftName(plan, assetId)} · ${compactMoney(plan.value || 0)}`,
      `${t("life.interactions.asset.gift_affection", {gain: Number(plan.affection_gain || 0).toFixed(1)})} · ${stageCopy}`,
      t("life.interactions.asset.confirm_body"),
      t("life.interactions.asset.warning"),
    ].join("\n\n");
    const accepted = await bridge().fmoddConfirm(
      warning,
      t("life.interactions.asset.confirm_button"),
      t("life.interactions.asset.confirm_heading"),
    );
    if (!accepted) return;
    state.requestBusy = true;
    paintWorkspace();
    try {
      const response = await postJson("/api/life/interactions/gift-asset", {
        person_id: personId, asset_type: assetType, asset_id: assetId, confirm: true,
      });
      applyData(response, personId);
      document.dispatchEvent(new CustomEvent("fmodd:life-assets-changed"));
      bridge()?.toast(t("life.interactions.toast.asset_gifted", {asset: assetGiftName(plan, assetId)}));
      showActionResult(response.result, selectedRow());
    } finally {
      state.requestBusy = false;
      paintWorkspace();
    }
  }

  async function loadSearchClubs() {
    const form = pageRoot()?.querySelector('[data-interaction-form="search"]');
    const input = form?.querySelector("[data-interaction-search-club-input]");
    if (form) {
      const values = formValues(form);
      state.searchQuery = String(values.query || "").trim();
      state.searchGender = String(values.gender || "all");
      state.searchNationalityId = Number(values.nationality_id || 0);
      state.searchMinAge = String(values.min_age || "").trim();
      state.searchMaxAge = String(values.max_age || "").trim();
    }
    const query = String(input?.value || state.searchClubQuery || "").trim();
    state.searchClubQuery = query;
    if (!query || state.searchClubBusy) return;
    state.searchClubBusy = true;
    state.searchClubOptions = [];
    paintWorkspace();
    try {
      const parameters = new URLSearchParams({
        search: query, page: "1", page_size: "15", gender: "all",
      });
      const response = await requestJson(`/api/world-clubs?${parameters}`);
      if (response.ready === false) throw new Error(response.error || t("life.interactions.search.club_no_results"));
      state.searchClubOptions = (Array.isArray(response.clubs) ? response.clubs : [])
        .slice(0, 15)
        .map((club) => ({
          id: Number(club.id || 0), name: String(club.name || club.short_name || ""),
          nation: String(club.nation || ""), competition: String(club.competition || ""),
        }))
        .filter((club) => club.id > 0);
    } catch (error) {
      state.searchClubOptions = [];
      bridge()?.toast(localizedError(error));
    } finally {
      state.searchClubBusy = false;
      paintWorkspace();
    }
  }

  function resetSearchFilters() {
    state.searchResults = null;
    state.searchTotal = null;
    state.searchPage = 1;
    state.searchPageCount = 0;
    state.searchQuery = "";
    state.searchGender = "all";
    state.searchNationalityId = 0;
    state.searchMinAge = "";
    state.searchMaxAge = "";
    state.searchClubId = 0;
    state.searchClubName = "";
    state.searchClubQuery = "";
    state.searchClubOptions = [];
    paintWorkspace();
  }

  function searchQueryForPage(page) {
    const query = new URLSearchParams({
      query: state.searchQuery, gender: state.searchGender,
      page: String(Math.max(1, Number(page || 1))),
      page_size: String(state.searchPageSize),
    });
    if (state.searchNationalityId) query.set("nationality_id", String(state.searchNationalityId));
    if (state.searchMinAge) query.set("min_age", state.searchMinAge);
    if (state.searchMaxAge) query.set("max_age", state.searchMaxAge);
    if (state.searchClubId) query.set("club_id", String(state.searchClubId));
    return `/api/life/interactions/search?${query}`;
  }

  async function loadSearchPage(page = 1) {
    const requestedPage = Math.max(1, Number(page || 1));
    if (state.searchBusy && requestedPage === state.searchPage) return;
    state.searchPage = requestedPage;
    state.searchBusy = true;
    state.error = "";
    paintWorkspace();
    try {
      const response = await requestJson(searchQueryForPage(state.searchPage));
      if (response.ready === false) throw new Error(response.error || t("life.interactions.search.empty"));
      state.searchResults = Array.isArray(response.players) ? response.players : [];
      const pagination = response.pagination || {};
      state.searchPage = Math.max(1, Number(pagination.page || state.searchPage));
      state.searchPageCount = Math.max(0, Number(pagination.page_count || 0));
      state.searchPageSize = Math.max(1, Number(pagination.page_size || state.searchPageSize));
      state.searchTotal = Number(pagination.total ?? state.searchResults.length);
      const nationalities = response.filter_options?.nationalities;
      if (Array.isArray(nationalities)) {
        state.searchNationalities = nationalities
          .map((nation) => ({id: Number(nation.id || 0), name: String(nation.name || "")}))
          .filter((nation) => nation.id > 0)
          .sort((left, right) => left.name.localeCompare(right.name));
      }
    } catch (error) {
      state.searchResults = [];
      state.searchTotal = 0;
      state.searchPageCount = 0;
      bridge()?.toast(localizedError(error));
    } finally {
      state.searchBusy = false;
      paintWorkspace();
      pageRoot()?.querySelector(".interaction-search-results")?.scrollTo({top: 0});
    }
  }

  async function submitSearch(form) {
    const values = formValues(form);
    state.searchQuery = String(values.query || "").trim();
    state.searchGender = String(values.gender || "all");
    state.searchNationalityId = Number(values.nationality_id || 0);
    state.searchMinAge = String(values.min_age || "").trim();
    state.searchMaxAge = String(values.max_age || "").trim();
    await loadSearchPage(1);
  }

  async function addPerson(playerId) {
    state.requestBusy = true;
    paintWorkspace();
    try {
      const response = await postJson("/api/life/interactions/person", {player_id: Number(playerId || 0)});
      applyData(response, playerId);
      state.tab = "people";
      state.peopleTab = "dossier";
      bridge()?.toast(t("life.interactions.toast.person_added"));
    } finally {
      state.requestBusy = false;
      paintWorkspace();
    }
  }

  async function submitProfile(form) {
    const values = formValues(form);
    const payload = {...values};
    state.requestBusy = true;
    paintWorkspace();
    updateProfileBudget(form);
    try {
      const response = await postJson("/api/life/interactions/profile", payload);
      applyData(response, state.selectedId);
      closeProfileDialog();
      bridge()?.toast(t("life.interactions.toast.profile_saved"));
    } finally {
      state.requestBusy = false;
      paintWorkspace();
    }
  }

  async function submitRelationship(personId, target) {
    const row = selectedRow();
    const personName = row?.person?.name || t("life.interactions.dossier.title");
    const actionLabel = t(`life.interactions.relationship.action.${target}`);
    const destructive = target === "breakup" || target === "divorce";
    const accepted = await bridge().fmoddConfirm(
      t(destructive ? "life.interactions.relationship.confirm_destructive" : "life.interactions.relationship.confirm_action", {
        name: personName, action: actionLabel,
      }),
      actionLabel,
      t("life.interactions.relationship.confirm_heading"),
    );
    if (!accepted) return;
    const response = await performAction("/api/life/interactions/relationship", {
      person_id: Number(personId || 0), target: String(target || ""),
    });
    actionToast(response.result);
    showActionResult(response.result, selectedRow());
  }

  async function refreshSnapshots(personId = 0) {
    state.requestBusy = true;
    paintWorkspace();
    try {
      const response = await postJson("/api/life/interactions/refresh", personId ? {person_id: Number(personId)} : {});
      applyData(response, state.selectedId);
      const refresh = response.refresh || {};
      bridge()?.toast(t("life.interactions.toast.refreshed", {
        checked: Number(refresh.checked || 0), updated: Number(refresh.updated || 0),
      }));
    } finally {
      state.requestBusy = false;
      paintWorkspace();
    }
  }

  async function refreshFamilyAcademy() {
    if (state.requestBusy) return;
    state.requestBusy = true;
    paintWorkspace();
    try {
      const response = await postJson("/api/life/interactions/children/academy/refresh", {});
      applyLifeView(response);
      const rows = Array.isArray(response?.academy_refresh) ? response.academy_refresh : [];
      const finalized = rows.find((row) => row?.finalized);
      const failure = rows.find((row) => row?.reason);
      bridge()?.toast(String(
        finalized
          ? t("life.interactions.family.finalize_done")
          : failure?.reason || t("life.interactions.family.academy_refreshed"),
      ));
    } catch (error) {
      bridge()?.toast(localizedError(error));
    } finally {
      state.requestBusy = false;
      paintWorkspace();
    }
  }

  async function handleSubmit(event) {
    const form = event.target.closest?.("[data-interaction-form]");
    if (!form) return;
    if (
      !pageRoot()?.contains(form)
      && !profileDialog()?.contains(form)
      && !chatDialog()?.contains(form)
    ) return;
    event.preventDefault();
    if (state.requestBusy && form.dataset.interactionForm !== "search") return;
    try {
      if (form.dataset.interactionForm === "search") await submitSearch(form);
      else if (form.dataset.interactionForm === "profile") await submitProfile(form);
      else if (form.dataset.interactionForm === "chat") await submitChat(form);
    } catch (error) {
      bridge()?.toast(localizedError(error));
    }
  }

  async function handleClick(event) {
    const target = event.target;
    const familyParent = target.closest?.("[data-family-parent]");
    if (familyParent) {
      state.familyParentId = Number(familyParent.dataset.familyParent || 0);
      state.familyChildId = "";
      if (familyParent.dataset.familySection) {
        state.familySection = String(familyParent.dataset.familySection);
      }
      paintWorkspace();
      return;
    }
    const familyChild = target.closest?.("[data-family-child]");
    if (familyChild) {
      state.familyChildId = String(familyChild.dataset.familyChild || "");
      state.familyChildView = "profile";
      paintWorkspace();
      return;
    }
    const familyChildView = target.closest?.("[data-family-child-view]");
    if (familyChildView) {
      state.familyChildView = String(familyChildView.dataset.familyChildView || "profile");
      paintWorkspace();
      return;
    }
    const familySection = target.closest?.("[data-family-section]");
    if (familySection) {
      state.familySection = String(familySection.dataset.familySection || "overview");
      paintWorkspace();
      return;
    }
    const milestone = target.closest?.("[data-child-milestone]");
    if (milestone) {
      const card = milestone.closest("[data-child-card]");
      const detail = card?.querySelector(".interaction-child-detail");
      if (detail) {
        detail.open = true;
        detail.scrollIntoView({block: "nearest", behavior: "smooth"});
      }
      return;
    }
    if (
      !pageRoot()?.contains(target)
      && !profileDialog()?.contains(target)
      && !resultDialog()?.contains(target)
        && !chatDialog()?.contains(target)
      && !giftDialog()?.contains(target)
      && !dateDialog()?.contains(target)
      && !eventDialog()?.contains(target)
    ) return;
    const searchPageButton = target.closest("[data-interaction-search-page]");
    if (searchPageButton && !searchPageButton.disabled) {
      try {
        await loadSearchPage(Number(searchPageButton.dataset.interactionSearchPage || 1));
      } catch (error) {
        bridge()?.toast(localizedError(error));
      }
      return;
    }
    const searchClubs = target.closest("[data-interaction-search-clubs]");
    if (searchClubs) {
      try { await loadSearchClubs(); }
      catch (error) { bridge()?.toast(localizedError(error)); }
      return;
    }
    const searchClubSelect = target.closest("[data-interaction-search-club-select]");
    if (searchClubSelect) {
      const clubId = Number(searchClubSelect.dataset.interactionSearchClubSelect || 0);
      const club = state.searchClubOptions.find((row) => Number(row.id || 0) === clubId);
      if (club) {
        state.searchClubId = club.id;
        state.searchClubName = club.name;
        state.searchClubQuery = club.name;
        state.searchClubOptions = [];
        paintWorkspace();
      }
      return;
    }
    if (target.closest("[data-interaction-search-club-clear]")) {
      state.searchClubId = 0;
      state.searchClubName = "";
      state.searchClubQuery = "";
      state.searchClubOptions = [];
      paintWorkspace();
      return;
    }
    if (target.closest("[data-interaction-search-reset]")) {
      resetSearchFilters();
      return;
    }
    if (target.closest("#life-interactions-refresh-cache")) {
      try { await refreshSnapshots(); } catch (error) { bridge()?.toast(localizedError(error)); }
      return;
    }
    const action = target.closest("[data-interaction-action]");
    if (action) {
      const name = action.dataset.interactionAction;
      if (name === "edit-profile") openProfileDialog();
      else if (name === "close-profile") closeProfileDialog();
      else if (name === "close-event") closeEventDialog();
      else if (name === "close-result") closeResultDialog();
      else if (name === "open-chat") openChatDialog();
      else if (name === "close-chat") closeChatDialog();
      else if (name === "open-ap-ledger") openApLedgerDialog();
      else if (name === "open-ap-purchase") openApPurchaseDialog();
      else if (name === "close-ap-purchase") closeApPurchaseDialog();
      else if (name === "open-money-gift") openMoneyGiftDialog();
      else if (name === "close-money-gift") closeMoneyGiftDialog();
      else if (name === "close-ap-ledger") closeApLedgerDialog();
      else if (name === "open-asset-level") openAssetLevelDialog();
      else if (name === "close-asset-level") closeAssetLevelDialog();
      else if (name === "claim-asset-level") await claimAssetLevel(Number(action.dataset.level || 0));
      else if (name === "rename-child") await renameChild(String(action.dataset.childId || ""));
      else if (name === "child-elixir") await feedChildElixir(String(action.dataset.childId || ""), String(action.dataset.tier || ""));
      else if (name === "child-place") await placeChild(String(action.dataset.childId || ""), String(action.dataset.mode || "own"));
      else if (name === "child-trial") await startChildTrial(String(action.dataset.childId || ""));
      else if (name === "child-finalize") await finalizeChildTraining(String(action.dataset.childId || ""));
      else if (name === "refresh-family-academy") await refreshFamilyAcademy();
      else if (name === "open-gift-picker") openGiftDialog();
      else if (name === "close-gift") closeGiftDialog();
      else if (name === "open-date-picker") openDateDialog();
      else if (name === "close-date") closeDateDialog();
      else if (name === "confirm-gift") {
        const personId = Number(selectedRow()?.person?.id || 0);
        if (personId && state.giftItemId) {
          try { await submitGift({person_id: personId, item_id: state.giftItemId}); }
          catch (error) { bridge()?.toast(localizedError(error)); }
        }
      } else if (name === "confirm-date") {
        const personId = Number(selectedRow()?.person?.id || 0);
        if (personId && state.dateActivityId) {
          try { await submitDate({person_id: personId, activity: state.dateActivityId}); }
          catch (error) { bridge()?.toast(localizedError(error)); }
        }
      } else if (name === "open-gift-shop") {
        closeGiftDialog();
        closeDateDialog();
        document.querySelector('.main-sidebar [data-page="gift-shop"]')?.click();
      }
      else if (name === "reload") {
        try { await loadInteractions(); } catch (error) { bridge()?.toast(localizedError(error)); }
      }
      return;
    }
    const eventChoice = target.closest("[data-interaction-event]");
    if (eventChoice) {
      openEventDialog(String(eventChoice.dataset.interactionEvent || ""));
      return;
    }
    const eventOption = target.closest("[data-interaction-event-option]");
    if (eventOption && !eventOption.disabled) {
      try {
        await submitEvent(
          state.eventId,
          String(eventOption.dataset.interactionEventOption || ""),
          Number(eventOption.dataset.interactionEventPerson || 0),
        );
      } catch (error) {
        bridge()?.toast(localizedError(error));
      }
      return;
    }
    const travelCountry = target.closest("[data-travel-country]");
    if (travelCountry) {
      state.travelCountry = String(travelCountry.dataset.travelCountry || "");
      state.travelCityLimit = 9;
      const country = travelSelectedCountry();
      state.travelCity = String(country?.cities?.[0]?.id || "");
      state.travelPlace = String(country?.cities?.[0]?.places?.[0] || "");
      paintWorkspace();
      return;
    }
    const travelCity = target.closest("[data-travel-city]");
    if (travelCity) {
      state.travelCity = String(travelCity.dataset.travelCity || "");
      const country = travelSelectedCountry();
      const city = travelSelectedCity(country);
      state.travelPlace = String(city?.places?.[0] || "");
      paintWorkspace();
      return;
    }
    const travelPlace = target.closest("[data-travel-place]");
    if (travelPlace) {
      state.travelCity = String(travelPlace.dataset.travelCityId || state.travelCity);
      state.travelPlace = String(travelPlace.dataset.travelPlace || "");
      travelGoOut(state.travelCity, state.travelPlace);
      return;
    }
    const travelGo = target.closest("[data-travel-go]");
    if (travelGo && !travelGo.disabled) {
      travelGoOut(state.travelCity, state.travelPlace);
      return;
    }
    const travelEncounter = target.closest("[data-travel-encounter]");
    if (travelEncounter && !travelEncounter.disabled) {
      travelEncounterAction(String(travelEncounter.dataset.travelEncounter || ""));
      return;
    }
    if (target.closest("[data-travel-more-cities]")) {
      state.travelCityLimit = Number(state.travelCityLimit || 9) + 12;
      paintWorkspace();
      return;
    }
    if (target.closest("[data-travel-reload]")) {
      state.travelCatalog = null;
      loadTravelCatalog();
      return;
    }
    if (target.closest("[data-travel-adult-settings]")) {
      bridge()?.showPage?.("settings");
      return;
    }
    const mainTab = target.closest("[data-interaction-tab]");
    if (mainTab) {
      const next = String(mainTab.dataset.interactionTab || "overview");
      if (TABS.some(([key]) => key === next)) state.tab = next;
      if (next === "travel") loadTravelCatalog();
      paintWorkspace();
      return;
    }
    const peopleTab = target.closest("[data-interaction-people-tab]");
    if (peopleTab) {
      state.peopleTab = String(peopleTab.dataset.interactionPeopleTab || "dossier");
      paintWorkspace();
      return;
    }
    const modeTab = target.closest("[data-interaction-mode-tab]");
    if (modeTab) {
      state.interactionTab = String(modeTab.dataset.interactionModeTab || "home");
      paintWorkspace();
      return;
    }
    const intimacyTab = target.closest("[data-interaction-intimacy-tab]");
    if (intimacyTab) {
      state.intimacyTab = String(intimacyTab.dataset.interactionIntimacyTab || "actions");
      paintWorkspace();
      return;
    }
    const assetsTab = target.closest("[data-interaction-assets-tab]");
    if (assetsTab) {
      state.assetsTab = String(assetsTab.dataset.interactionAssetsTab || "residence");
      paintWorkspace();
      return;
    }
    const giftToggle = target.closest("[data-interaction-gift-toggle]");
    if (giftToggle) {
      const kind = String(giftToggle.dataset.interactionGiftToggle || "");
      const key = String(giftToggle.dataset.groupKey || "");
      if (kind && key) {
        const store = kind === "property" ? state.giftPropertyExpanded : state.giftVehicleExpanded;
        const open = giftToggle.getAttribute("aria-expanded") === "true";
        const groups = [...document.querySelectorAll("[data-interaction-gift-toggle]")]
          .filter((node) => String(node.dataset.interactionGiftToggle || "") === kind)
          .map((node) => String(node.dataset.groupKey || ""));
        store.delete(`open:${key}`);
        store.delete(`closed:${key}`);
        store.add(`${open ? "closed" : "open"}:${key}`);
        if (!open && kind === "property") {
          const cityPrefix = key.startsWith("district:") ? "" : `district:${key.slice(5)}:`;
          const districtPrefix = key.startsWith("district:")
            ? key.split(":").slice(0, 2).join(":") + ":" : "";
          for (const groupKey of groups) {
            if (groupKey === key) continue;
            if (cityPrefix && groupKey.startsWith(cityPrefix)) {
              store.delete(`open:${groupKey}`);
              store.add(`closed:${groupKey}`);
            } else if (districtPrefix && groupKey.startsWith(districtPrefix)) {
              store.delete(`open:${groupKey}`);
              store.add(`closed:${groupKey}`);
            }
          }
        }
        if (kind === "property") state.giftPropertyExpandAll = null;
        else state.giftVehicleExpandAll = null;
        paintWorkspace();
      }
      return;
    }
    const giftExpand = target.closest("[data-interaction-gift-expand]");
    if (giftExpand) {
      const kind = String(giftExpand.dataset.interactionGiftExpand || "");
      if (kind === "property") {
        state.giftPropertyExpandAll = state.giftPropertyExpandAll === true ? false : true;
        state.giftPropertyExpanded.clear();
      } else if (kind === "vehicle") {
        state.giftVehicleExpandAll = state.giftVehicleExpandAll === true ? false : true;
        state.giftVehicleExpanded.clear();
      }
      paintWorkspace();
      return;
    }
    const intimateAction = target.closest("[data-interaction-intimate-action]");
    if (intimateAction && !intimateAction.disabled) {
      try {
        await submitIntimacy(String(intimateAction.dataset.interactionIntimateAction || ""));
      } catch (error) {
        bridge()?.toast(localizedError(error));
      }
      return;
    }
    const selected = target.closest("[data-interaction-person-select]");
    if (selected && !["SELECT", "OPTION"].includes(selected.tagName)) {
      state.selectedId = Number(selected.dataset.interactionPersonSelect || 0);
      state.residenceSelectionPerson = 0;
      state.residenceSelectionId = "";
      state.tab = "people";
      if (selected.hasAttribute("data-interaction-open-dossier")) state.peopleTab = "dossier";
      paintWorkspace();
      return;
    }
    const gentity = target.closest("[data-interaction-gift-choice]");
    if (gentity && !gentity.disabled) {
      state.giftItemId = String(gentity.dataset.interactionGiftChoice || "");
      renderGiftPicker();
      return;
    }
    const dactivity = target.closest("[data-interaction-date-choice]");
    if (dactivity && !dactivity.disabled) {
      state.dateActivityId = String(dactivity.dataset.interactionDateChoice || "");
      renderDatePicker();
      return;
    }
    const residenceCard = target.closest("[data-interaction-residence-select]");
    if (residenceCard && !residenceCard.disabled) {
      state.residenceSelectionPerson = Number(selectedRow()?.person?.id || 0);
      state.residenceSelectionId = String(residenceCard.dataset.interactionResidenceSelect || "");
      paintWorkspace();
      return;
    }
    const residenceMoveIn = target.closest("[data-interaction-residence-move-in]");
    if (residenceMoveIn && !residenceMoveIn.disabled) {
      const personId = Number(selectedRow()?.person?.id || 0);
      if (personId && state.residenceSelectionId) {
        try { await submitResidence(personId, state.residenceSelectionId); }
        catch (error) { bridge()?.toast(localizedError(error)); }
      }
      return;
    }
    const residenceMoveOut = target.closest("[data-interaction-residence-move-out]");
    if (residenceMoveOut && !residenceMoveOut.disabled) {
      const personId = Number(selectedRow()?.person?.id || 0);
      if (personId) {
        try { await submitResidence(personId, ""); }
        catch (error) { bridge()?.toast(localizedError(error)); }
      }
      return;
    }
    const remove = target.closest("[data-interaction-remove]");
    if (remove) {
      try { await removeContact(Number(remove.dataset.interactionRemove || 0)); }
      catch (error) { bridge()?.toast(localizedError(error)); }
      return;
    }
    const gift = target.closest("[data-interaction-gift-asset]");
    if (gift) {
      try {
        const [assetType, ...identifier] = String(gift.dataset.interactionGiftAsset || "").split(":");
        await submitAssetGift(assetType, identifier.join(":"));
      } catch (error) {
        bridge()?.toast(localizedError(error));
      }
      return;
    }
    const add = target.closest("[data-interaction-add]");
    if (add) {
      try { await addPerson(Number(add.dataset.interactionAdd || 0)); }
      catch (error) { bridge()?.toast(localizedError(error)); }
      return;
    }
    const personRefresh = target.closest("[data-interaction-refresh-person]");
    if (personRefresh) {
      try { await refreshSnapshots(Number(personRefresh.dataset.interactionRefreshPerson || 0)); }
      catch (error) { bridge()?.toast(localizedError(error)); }
      return;
    }
    const relationship = target.closest("[data-interaction-relationship]");
    if (relationship) {
      try {
        await submitRelationship(
          Number(relationship.dataset.interactionPerson || 0),
          String(relationship.dataset.interactionRelationship || ""),
        );
      } catch (error) {
        bridge()?.toast(localizedError(error));
      }
    }
  }

  function ensureEvents() {
    if (state.bound) return;
    state.bound = true;
    document.addEventListener("submit", handleSubmit);
    document.addEventListener("click", handleClick);
  document.addEventListener("submit", (event) => {
    const form = event.target.closest?.("[data-child-name-form]");
    if (!form) return;
    event.preventDefault();
    void submitChildName(form);
  });
    document.addEventListener("keydown", (event) => {
      const clubInput = event.target.closest?.("[data-interaction-search-club-input]");
      if (!clubInput || event.key !== "Enter" || event.isComposing) return;
      event.preventDefault();
      void loadSearchClubs().catch((error) => bridge()?.toast(localizedError(error)));
    });
    document.addEventListener("change", (event) => {
      const avatarInput = event.target.closest?.("[data-child-avatar]");
      if (avatarInput) {
        const file = avatarInput.files?.[0];
        if (file) void uploadChildAvatar(String(avatarInput.dataset.childAvatar || ""), file);
        return;
      }
      const personSelect = event.target.closest?.("[data-interaction-person-select]");
      if (personSelect && ["SELECT", "OPTION"].includes(personSelect.tagName)) {
        state.selectedId = Number(personSelect.value || 0);
        state.residenceSelectionPerson = 0;
        state.residenceSelectionId = "";
        paintWorkspace();
        return;
      }
      const giftFilter = event.target.closest?.("[data-interaction-gift-filter]");
      if (giftFilter) {
        const kind = String(giftFilter.dataset.interactionGiftFilter || "");
        const field = String(giftFilter.dataset.giftField || "");
        const value = String(giftFilter.value || "");
        if (kind === "property") {
          if (field === "city") {
            state.giftPropertyCity = value;
            state.giftPropertyDistrict = "";
          } else if (field === "district") {
            state.giftPropertyDistrict = value;
          } else if (field === "kind") {
            state.giftPropertyKind = value;
          }
          state.giftPropertyExpandAll = null;
        } else if (kind === "vehicle") {
          if (field === "brand") state.giftVehicleBrand = value;
          else if (field === "class") state.giftVehicleClass = value;
          else if (field === "rarity") state.giftVehicleRarity = value;
          state.giftVehicleExpandAll = null;
        }
        paintWorkspace();
        return;
      }
      if (event.target.matches?.("[data-interaction-timeline-all]")) {
        state.timelineAll = Boolean(event.target.checked);
        paintWorkspace();
        return;
      }
    });
    document.addEventListener("input", (event) => {
      const identity = event.target.closest?.("[data-profile-identity]");
      const identityForm = identity?.closest("[data-interaction-form=profile]");
      if (identity && identityForm) {
        syncProfileIdentity(
          identityForm,
          identity.dataset.profileIdentity,
          identity.value,
          identity,
        );
        return;
      }
      const range = event.target.closest?.("[data-profile-range]");
      const number = event.target.closest?.("[data-profile-number]");
      const control = range || number;
      if (!control) return;
      const key = range?.dataset.profileRange || number?.dataset.profileNumber || "";
      const form = control.closest("[data-interaction-form=profile]");
      syncProfileStat(form, key, control.value, control);
    });
    const dialog = profileDialog();
    dialog?.addEventListener("click", (event) => {
      if (event.target === dialog) closeProfileDialog();
    });
    const result = resultDialog();
    result?.addEventListener("click", (event) => {
      if (event.target === result) closeResultDialog();
    });
    const chat = chatDialog();
    chat?.addEventListener("click", (event) => {
      if (event.target === chat) closeChatDialog();
    });
    const ledger = apLedgerDialog();
    ledger?.addEventListener("click", (event) => {
      if (event.target === ledger) closeApLedgerDialog();
    });
    const assetLevel = assetLevelDialog();
    assetLevel?.addEventListener("click", (event) => {
      if (event.target === assetLevel) closeAssetLevelDialog();
    });
    const gift = giftDialog();
    gift?.addEventListener("click", (event) => {
      if (event.target === gift) closeGiftDialog();
    });
    const date = dateDialog();
    date?.addEventListener("click", (event) => {
      if (event.target === date) closeDateDialog();
    });
    const evt = eventDialog();
    evt?.addEventListener("click", (event) => {
      if (event.target === evt) closeEventDialog();
    });
    document.addEventListener("fmodd:localechange", () => {
      paintWorkspace();
      if (dialog?.open) openProfileDialog();
      if (ledger?.open) renderApLedger();
      if (assetLevel?.open) renderAssetLevelDialog();
      if (gift?.open) renderGiftPicker();
      if (date?.open) renderDatePicker();
      if (chat?.open) renderChatDialog();
      if (evt?.open && state.eventId) renderEventDialog(pendingEventById(state.eventId));
      closeResultDialog();
    });
    document.addEventListener("fmodd:settings-changed", () => paintWorkspace());
    document.addEventListener("fmodd:interaction-entitlements-changed", () => {
      if (state.data) void loadInteractions();
    });
    document.addEventListener("fmodd:game-clock-changed", (event) => {
      if (!state.data || !event?.detail?.dateChanged) return;
      // Age, pregnancies and children events all advance with the game date.
      void loadInteractions();
    });

    document.addEventListener("fmodd:life-assets-changed", () => {
      if (!pageRoot()?.hidden && bridge()?.isSaveConnected?.()) void loadInteractions();
    });
  }

  function currentScope() {
    return String(bridge()?.getState?.()?.data_scope_id || "");
  }

  function currentGameDate() {
    return String(bridge()?.getState?.()?.game_clock?.date || "");
  }

  function syncSaveScope() {
    const scope = currentScope();
    if (scope === state.scope) return false;
    state.scope = scope;
    state.data = null;
    state.error = "";
    state.selectedId = 0;
    state.searchResults = null;
    state.searchQuery = "";
    state.searchGender = "all";
    state.searchNationalityId = 0;
    state.searchMinAge = "";
    state.searchMaxAge = "";
    state.searchClubId = 0;
    state.searchClubName = "";
    state.searchClubQuery = "";
    state.searchClubOptions = [];
    state.searchNationalities = [];
    state.searchTotal = null;
    state.searchPage = 1;
    state.searchPageCount = 0;
    state.tab = "overview";
    state.peopleTab = "dossier";
    state.interactionTab = "home";
    state.assetsTab = "residence";
    state.familySection = "children";
    state.timelineAll = false;
    state.giftItemId = "";
    state.dateActivityId = "";
    state.residenceSelectionPerson = 0;
    state.residenceSelectionId = "";
    state.eventId = "";
    state.dismissedEventIds.clear();
    closeProfileDialog();
    closeResultDialog();
    closeChatDialog();
    closeGiftDialog();
    closeDateDialog();
    closeEventDialog(false);
    return true;
  }

  function render(page = "life-interactions") {
    if (page !== "life-interactions") return;
    ensureEvents();
    const scopeChanged = syncSaveScope();
    paintWorkspace();
    const gameDate = currentGameDate();
    const stale = scopeChanged || !state.data
      || (gameDate && String(state.data.game_date || "") !== gameDate);
    if (stale && !state.loading) void loadInteractions();
  }

  window.FMSDDInteractions = Object.freeze({render, paint: () => paintWorkspace(), debug: () => ({state: {tab: state.tab, family: state.familyDebug}})});
})();
