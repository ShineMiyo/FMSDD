from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_family_page_uses_fixed_parent_portrait_column() -> None:
    css = _read("src/web/interactions.css")
    assert ".interaction-family-overview-parent > .interaction-avatar" in css
    assert "width: 44px" in css
    # The 58px shared "small" avatar must not be able to overlap the parent name.
    assert ".interaction-family-parent > .interaction-avatar.small" in css


def test_family_page_shows_parent_relationship_badge() -> None:
    js = _read("src/web/interactions_page.js")
    assert "function parentRelationMeta" in js
    assert "interaction-relation-badge" in js
    assert 'relationship.secret_lover' in js
    assert 'relationship.effective_romance_stage' in js


def test_family_child_card_has_cohesive_sections_and_actions() -> None:
    js = _read("src/web/interactions_page.js")
    css = _read("src/web/interactions.css")
    assert "interaction-child-hero" in js
    assert "interaction-child-steps" in js
    assert "interaction-child-academy-state" in js
    assert "data-interaction-action=\"child-place\"" in js
    assert ".interaction-child-step-copy span" in css
    # The old generic class had no styling and produced browser-default buttons.
    assert "interaction-primary" not in js


def test_family_child_mutations_apply_direct_life_view() -> None:
    js = _read("src/web/interactions_page.js")
    assert "function applyLifeView" in js
    assert "Array.isArray(response?.children)" in js
    assert "applyLifeView(response)" in js


def test_family_child_card_surfaces_native_generated_identity() -> None:
    js = _read("src/web/interactions_page.js")
    assert "placement.player_id" in js
    assert "placement.ca" in js
    assert "placement.pa" in js
    assert "FM UID" in js


def test_managed_club_youth_plan_and_explicit_refresh_contract() -> None:
    api = _read("src/fm_odds_web.py")
    assert "def _youth_plan_club_target" in api
    assert "managed_team_id = self._life_manager_team_id()" in api
    assert "self._youth_plan_club_target(team_id)" in api
    assert '"refresh_life_child_academy"' in api
    assert '"/api/life/interactions/children/academy/refresh": "refresh_life_child_academy"' in api
    assert "finalize_academy_son_attributes(\n" in api


def test_family_child_card_uses_full_width_summary_rail() -> None:
    js = _read("src/web/interactions_page.js")
    css = _read("src/web/interactions.css")
    assert "interaction-child-hero-stats" in js
    assert "interaction-child-view-bar" in js
    assert "interaction-child-side-card" in js
    assert "interaction-child-academy-body" in js
    assert "V2.9.5.1: use the full family workspace width" in css
    assert ".interaction-family-children .interaction-child-card { max-width: none" in css


def test_family_academy_rows_resolve_club_name_before_showing_fm_uid() -> None:
    js = _read("src/web/interactions_page.js")
    css = _read("src/web/interactions.css")
    assert "function placementTeamName(placement)" in js
    assert "club.name" in js
    assert "placementTeamName(placement)" in js
    assert "interaction-family-academy-team" in js
    assert ".interaction-family-academy-team" in css
    assert "placement.team_id || placement.player_id" not in js


def test_adult_content_toggle_is_localized_and_server_backed() -> None:
    html = _read("src/web/index.html")
    js = _read("src/web/app.js")
    api = _read("src/fm_odds_web.py")
    catalog = _read("src/web/i18n.family.v294.js")
    assert 'id="adult-content-enabled"' in html
    assert '"/api/settings/adult-content"' in js
    assert '"/api/settings/adult-content"' in api
    for locale in (
        "en-GB", "zh-CN", "zh-TW", "ko-KR", "de-DE", "es-ES",
        "fr-FR", "ru-RU", "ja-JP", "pt-BR", "pt-PT",
    ):
        assert f'"{locale}"' in catalog
    assert 'settings.adult_content_enabled === true' in js
