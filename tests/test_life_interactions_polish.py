from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "src"
LOCALES = (
    "en-GB", "zh-CN", "zh-TW", "ko-KR", "de-DE", "es-ES",
    "fr-FR", "ru-RU", "ja-JP", "pt-BR", "pt-PT",
)
DIALOGUE_PATHS = (
    "chat.preferred", "chat.neutral",
    "gift.preferred", "gift.neutral", "gift.disliked",
    "date.preferred", "date.neutral", "date.disliked",
    "relationship.success", "relationship.failure",
)
PROFILE_KEYS = (
    "life.interactions.profile.identity_title",
    "life.interactions.profile.identity_detail",
    "life.interactions.profile.identity_cost_badge",
    "life.interactions.profile.identity_cost_total",
    "life.interactions.profile.identity_cost_breakdown",
    "life.interactions.profile.name_preview",
    "life.interactions.profile.surname",
    "life.interactions.profile.given_name",
    "life.interactions.profile.surname_placeholder",
    "life.interactions.profile.given_name_placeholder",
    "life.interactions.profile.allocation_detail_unbounded",
    "life.interactions.profile.attribute_only_increase",
    "life.interactions.error.profile_attribute_locked",
    "life.interactions.traits.disclosure_title",
    "life.interactions.traits.disclosure_level.0",
    "life.interactions.traits.disclosure_level.1",
    "life.interactions.traits.disclosure_level.2",
    "life.interactions.traits.disclosure_level.3",
    "life.interactions.traits.locked_remaining",
    "life.interactions.traits.values_locked",
    "life.interactions.traits.likes_hint",
    "life.interactions.traits.dislikes_locked",
    "life.interactions.traits.measurements_exact",
    "life.interactions.traits.measurements_range",
    "life.interactions.traits.measurement_hint",
)
ACTION_GIFT_KEYS = (
    "settings.portraits.help",
    "settings.interaction_portraits.note",
    "life.interactions.ap.current",
    "life.interactions.ap.next_gain",
    "life.interactions.ap.full_in",
    "life.interactions.ap.full",
    "life.interactions.ap.full_badge",
    "life.interactions.ap.recovering_badge",
    "life.interactions.ap.cost_title",
    "life.interactions.ap.cost.chat",
    "life.interactions.ap.cost.gift",
    "life.interactions.ap.cost.asset_gift",
    "life.interactions.ap.cost.date",
    "life.interactions.ap.cost.relationship",
    "life.interactions.asset.gift_affection",
    "life.interactions.asset.stage_after",
    "life.interactions.asset.stage_hold",
)
FEATURE_KEYS = (
    "life.interactions.search.filters_title",
    "life.interactions.search.filters_subtitle",
    "life.interactions.search.nationality",
    "life.interactions.search.nationality_all",
    "life.interactions.search.gender",
    "life.interactions.search.club",
    "life.interactions.search.club_placeholder",
    "life.interactions.search.club_find",
    "life.interactions.search.club_finding",
    "life.interactions.search.club_hint",
    "life.interactions.search.club_clear",
    "life.interactions.search.club_no_results",
    "life.interactions.search.selected_club",
    "life.interactions.search.age",
    "life.interactions.search.age_min",
    "life.interactions.search.age_max",
    "life.interactions.search.reset",
    "life.interactions.search.total",
    "life.interactions.search.previous",
    "life.interactions.search.next",
    "life.interactions.search.page_status",
    "life.interactions.search.pagination_label",
    "settings.portraits.eyebrow",
    "settings.portraits.status_label",
    "settings.portraits.status_default",
    "settings.portraits.xml_count",
    "settings.portraits.xml_none",
    "settings.portraits.step_graphics",
    "settings.portraits.step_xml",
    "settings.portraits.step_reuse",
    "settings.portraits.fallback",
    "settings.portraits.offset_title",
    "settings.portraits.offset_note",
    "settings.portraits.offset_apply",
    "settings.portraits.offset_saved",
    "settings.portraits.offset_invalid",
    "settings.cdk.note",
    "settings.cdk.success.action_points",
    "settings.cdk.success.relationship_gain",
    "settings.cdk.success.generic",
)
CHAT_KEYS = (
    "life.interactions.chat.open",
    "life.interactions.chat.open_detail",
    "life.interactions.chat.eyebrow",
    "life.interactions.chat.dialog_title",
    "life.interactions.chat.template_mode",
    "life.interactions.chat.history_label",
    "life.interactions.chat.history_empty_title",
    "life.interactions.chat.history_empty",
    "life.interactions.chat.history_reply",
    "life.interactions.chat.stage_upgraded",
    "life.interactions.chat.you",
    "life.interactions.chat.topic_message",
    "life.interactions.chat.topic_label",
    "life.interactions.chat.input_placeholder",
    "life.interactions.chat.send",
    "life.interactions.chat.template_notice",
)
MANAGER_REPUTATION_KEYS = (
    "life.interactions.profile.manager_reputation_title",
    "life.interactions.profile.manager_reputation_detail",
    "life.interactions.profile.manager_reputation_unavailable",
    "life.interactions.profile.manager_reputation_scale",
    "life.interactions.profile.manager_reputation_domestic",
    "life.interactions.profile.manager_reputation_world",
    "life.interactions.profile.manager_reputation_linked",
    "life.interactions.profile.manager_reputation_missing",
)


def _dialogue_probe() -> dict[str, dict[str, str]]:
    script = r'''
const fs = require("fs"), vm = require("vm");
const context = {window:{FMODDI18nModules:[]}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), context);
console.log(JSON.stringify(context.window.FMODDI18nModules[0].messages));
'''
    result = subprocess.run(
        ["node", "-e", script, str(ROOT / "web" / "i18n.interactions.polish.js")],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    return json.loads(result.stdout)


def test_dialogue_variants_cover_every_locale_and_keep_placeholders() -> None:
    messages = _dialogue_probe()
    assert set(messages) == set(LOCALES)
    for locale in LOCALES:
        catalog = messages[locale]
        assert catalog["settings.interaction_portraits.title"]
        assert catalog["settings.interaction_portraits.note"]
        assert catalog["settings.interaction_portraits.enabled"]
        assert catalog["settings.interaction_portraits.disabled"]
        for path in DIALOGUE_PATHS:
            values = [
                catalog[f"life.interactions.dialogue.{path}.{index}"]
                for index in (1, 2, 3)
            ]
            assert len(set(values)) == 3, (locale, path)
            for index in (1, 2, 3):
                key = f"life.interactions.dialogue.{path}.{index}"
                placeholder_sets = {
                    frozenset(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", messages[item][key]))
                    for item in LOCALES
                }
                assert len(placeholder_sets) == 1, (path, index, placeholder_sets)


def test_profile_copy_covers_every_locale_and_keeps_placeholders() -> None:
    messages = _dialogue_probe()
    for locale in LOCALES:
        catalog = messages[locale]
        for key in PROFILE_KEYS:
            assert catalog.get(key), (locale, key)
        for key in PROFILE_KEYS:
            placeholder_sets = {
                frozenset(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", messages[item][key]))
                for item in LOCALES
            }
            assert len(placeholder_sets) == 1, (key, placeholder_sets)


def test_action_and_asset_gift_copy_covers_every_locale_and_keeps_placeholders() -> None:
    messages = _dialogue_probe()
    for locale in LOCALES:
        catalog = messages[locale]
        for key in ACTION_GIFT_KEYS:
            assert catalog.get(key), (locale, key)
        for key in ACTION_GIFT_KEYS:
            placeholder_sets = {
                frozenset(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", messages[item][key]))
                for item in LOCALES
            }
            assert len(placeholder_sets) == 1, (key, placeholder_sets)


def test_people_search_and_portrait_settings_copy_cover_every_locale() -> None:
    messages = _dialogue_probe()
    for locale in LOCALES:
        catalog = messages[locale]
        for key in FEATURE_KEYS:
            assert catalog.get(key), (locale, key)
        for key in FEATURE_KEYS:
            placeholder_sets = {
                frozenset(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", messages[item][key]))
                for item in LOCALES
            }
            assert len(placeholder_sets) == 1, (key, placeholder_sets)


def test_chat_workspace_and_manager_reputation_copy_cover_every_locale() -> None:
    messages = _dialogue_probe()
    keys = CHAT_KEYS + MANAGER_REPUTATION_KEYS
    for locale in LOCALES:
        catalog = messages[locale]
        for key in keys:
            assert catalog.get(key), (locale, key)
        for key in keys:
            placeholder_sets = {
                frozenset(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", messages[item][key]))
                for item in LOCALES
            }
            assert len(placeholder_sets) == 1, (key, placeholder_sets)


def test_chat_workspace_has_a_live_composer_and_submit_gate() -> None:
    page = (ROOT / "web" / "interactions_page.js").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "web" / "interactions.css").read_text(encoding="utf-8")
    assert 'id="life-interactions-chat-dialog"' in html
    assert 'data-interaction-form="chat"' in page
    assert 'name="message" maxlength="500"' in page
    assert 'data-interaction-action="open-chat"' in page
    assert '!chatDialog()?.contains(form)' in page
    assert 'renderChatDialog(response.result)' in page
    assert 'interaction-chat-reward' in page
    assert '.interaction-chat-app { display: grid; grid-template-rows: auto minmax(0, 1fr) auto;' in css
    assert '.interaction-chat-history {' in css
    assert '.interaction-chat-composer {' in css
    assert '.interaction-chat-message.is-player .interaction-chat-bubble {' in css
    assert '.interaction-chat-reward {' in css


def test_people_search_and_portrait_layout_contract() -> None:
    page = (ROOT / "web" / "interactions_page.js").read_text(encoding="utf-8")
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "web" / "interactions.css").read_text(encoding="utf-8")
    settings_css = (ROOT / "web" / "app.css").read_text(encoding="utf-8")

    assert 'class="interaction-search-layout"' in page
    assert 'name="nationality_id"' in page
    assert 'name="min_age"' in page
    assert 'name="max_age"' in page
    assert 'query.set("club_id", String(state.searchClubId))' in page
    assert '/api/world-clubs?' in page
    assert 'data-interaction-search-club-select' in page
    assert 'data-interaction-search-reset' in page
    assert 'searchPageSize: 30' in page
    assert 'data-interaction-search-page=' in page
    assert 'loadSearchPage(Number(searchPageButton.dataset.interactionSearchPage || 1))' in page

    assert '.portfolio-source-setting' not in css
    assert 'width: 90px; height: 90px;' in css
    assert 'width: 58px; height: 58px;' in css
    assert 'font-family: inherit; font-size: 25px;' in css
    assert 'grid-template-columns: minmax(310px, 350px) minmax(0, 1fr)' in css
    assert '.interaction-search-layout {' in css
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr))' in css
    assert '.interaction-search-pagination {' in css

    assert '".portrait-source-setting", ".interaction-portrait-setting"' in app
    assert 'row.className = "setting-toggle interaction-portrait-setting"' in app
    assert 'class="interaction-portrait-slot"' in app
    assert 'id="portrait-source-status"' in app
    assert 'settings.portraits.step_graphics' in app
    assert '#settings-panel-general,#settings-panel-markets,#settings-panel-display,#settings-panel-cheats' in settings_css


def test_polish_copy_is_loaded_before_the_i18n_runtime() -> None:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert html.index('/i18n.interactions.js') < html.index(
        '/i18n.interactions.polish.js'
    )
    assert html.index('/i18n.interactions.polish.js') < html.index('/i18n.js')


def test_interaction_portrait_setting_round_trip_contract() -> None:
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    signature = app.split("function settingsRenderStateSignature", 1)[1].split(
        "function playerNameLocalizationAvailable", 1,
    )[0]
    renderer = app.split("function renderSettingsControls", 1)[1].split(
        "function shellDomIndex", 1,
    )[0]
    control = app.split("function ensureInteractionPortraitControl", 1)[1].split(
        "function ensureUpdateCheckControl", 1,
    )[0]
    handler = app.split('$("#interaction-portraits")?.addEventListener', 1)[1].split(
        '$("#god-mode")?.addEventListener', 1,
    )[0]

    assert "settings.interaction_portraits_enabled !== false" in signature
    assert 'if ($("#interaction-portraits"))' in renderer
    assert 'id="interaction-portraits"' in control
    assert 'row.className = "setting-toggle interaction-portrait-setting"' in control
    assert "/api/settings/interaction-portraits" in handler
    assert 'document.dispatchEvent(new CustomEvent("fmodd:settings-changed"))' in handler
    assert "ensureInteractionPortraitControl();" in app
    assert "settings.interaction_portraits.save_failed" in handler


def test_people_workspace_is_split_into_main_and_sub_tabs() -> None:
    page = (ROOT / "web" / "interactions_page.js").read_text(encoding="utf-8")
    assert '["overview", "life.interactions.tabs.overview"' in page
    assert '["people", "life.interactions.tabs.people"' in page
    assert '["search", "life.interactions.tabs.search"' in page
    assert '["assets", "life.interactions.tabs.assets"' in page
    assert '["timeline", "life.interactions.tabs.timeline"' in page
    assert 'renderTabs(data, "people")' in page
    assert 'renderTabs(data, "assets")' in page


def test_asset_names_follow_the_saved_locale_and_bilingual_ledger_fields() -> None:
    page = (ROOT / "web" / "interactions_page.js").read_text(encoding="utf-8")
    locale = page.split("function currentThemeLocale", 1)[1].split(
        "function placeName", 1,
    )[0]
    gift_name = page.split("function assetGiftName", 1)[1].split(
        "function formatGameDay", 1,
    )[0]
    assert "bridge()?.getState?.()?.settings?.ui_locale" in locale
    assert 'placeName(record, "asset_name_zh", "asset_name_en")' in gift_name
    css = (ROOT / "web" / "interactions.css").read_text(encoding="utf-8")
    page = (ROOT / "web" / "interactions_page.js").read_text(encoding="utf-8")
    assert ".interaction-profile-dialog .life-collection-dialog-shell {\n  width: 100%;" in css
    assert ".interaction-profile-edit-button" in css
    assert "min-height: 46px;" in css
    assert ".interaction-profile-attribute-strip" in css
    assert ".interaction-profile-identity" in css
    assert ".interaction-disclosure-badge" in css
    assert ".interaction-trait-block.is-measurement" in css
    assert ".interaction-reset-notice" not in css
    assert ".interaction-profile-save { grid-column: 1 / -1;" in css
    assert 'name="surname"' in page
    assert 'name="given_name"' in page
    assert "profileDisplayName(" in page
    assert "attribute_only_increase" in page
    assert "data-interaction-select" not in page
    assert 'data-interaction-person-select="${id}"' in page
    assert 'target.closest("[data-interaction-person-select]")' in page


def test_action_gift_and_asset_layout_contract() -> None:
    page = (ROOT / "web" / "interactions_page.js").read_text(encoding="utf-8")
    css = (ROOT / "web" / "interactions.css").read_text(encoding="utf-8")
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "life.interactions.ap.cost_title" in page
    assert "asset_gift_previews" in page
    assert 'class="interaction-person-uid"' in page
    assert "compactMoney(asset.market_value" in page
    assert "giftPropertyGroups(properties, row.relationship)" in page
    assert "giftVehicleGroups(vehicles, row.relationship)" in page
    assert ".interaction-asset-grid { display: grid; grid-template-columns: repeat(4" in css
    assert "white-space: nowrap;" in css[css.index(".interaction-person-select"):css.index(".interaction-interaction-head")]
    assert ".interaction-gift-preview" in css
    assert "settings.portraits.help" in app
    assert "formatCompactMoney, formatFullMoney" in app


def test_action_results_use_a_self_contained_single_column_card() -> None:
    page = (ROOT / "web" / "interactions_page.js").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "web" / "interactions.css").read_text(encoding="utf-8")
    result_dialog = html.split('id="life-interactions-result-dialog"', 1)[1].split(
        "</dialog>", 1,
    )[0]

    assert 'class="interaction-result-dialog"' in result_dialog
    assert 'class="interaction-result-card"' in result_dialog
    assert "life-collection-dialog-shell" not in result_dialog
    assert "interaction-result-hero" in page
    assert "interaction-result-context" in page
    assert "interaction-result-rewards" in page
    assert "interaction-result-footer" in page
    assert ".interaction-result-card { display: grid; grid-template-rows: auto minmax(0, 1fr);" in css
    assert ".interaction-result-content { display: grid; align-content: start;" in css
    assert ".interaction-result-context { display: grid; grid-template-columns: minmax(0, 1.4fr) repeat(2, minmax(0, .8fr));" in css


def test_intimacy_tab_is_conditional_and_exposes_costs_and_preview() -> None:
    page = (ROOT / "web" / "interactions_page.js").read_text(encoding="utf-8")
    css = (ROOT / "web" / "interactions.css").read_text(encoding="utf-8")

    assert 'if (type === "interaction" && state.data?.adult_content_enabled' in page
    assert 'isIntimateRelationship(selectedRow()?.relationship)' in page
    assert '["intimacy", "life.interactions.interaction_tabs.intimacy", "heart-handshake"]' in page
    assert 'data-interaction-intimate-action="${esc(id)}"' in page
    assert "interaction-intimacy-cost" in page
    assert "action.ap_cost" in page
    assert "action.intimacy_cost" in page
    assert "action.intimacy_after" in page
    assert ".interaction-intimacy-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert '.interaction-intimacy-action[data-intimate-action="kiss"]' in css
    assert ".interaction-intimacy-meter-track > span" in css
