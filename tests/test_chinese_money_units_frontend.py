"""Frontend contract for the V2.7.4beta Chinese money units."""

from __future__ import annotations

import unittest
from pathlib import Path

from frontend_source import read_frontend_source


ROOT = Path(__file__).resolve().parents[1] / "src"
LOCALE_FILES = (
    "i18n.settings.js", "i18n.tw.js", "i18n.de.js", "i18n.es.js", "i18n.fr.js",
    "i18n.ru.js", "i18n.ja.js", "i18n.pt-BR.js", "i18n.pt-PT.js",
)


class ChineseMoneyUnitsFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = read_frontend_source(ROOT / "web" / "app.js", mode="raw")
        cls.html = read_frontend_source(ROOT / "web" / "index.html", mode="raw")

    def test_the_ladder_climbs_by_ten_thousand_up_to_ten_to_the_48(self):
        units = self.script.split("const CHINESE_MONEY_UNITS = Object.freeze([", 1)[1].split("]);", 1)[0]
        for exponent, suffix in (
            (4, "万"), (8, "亿"), (12, "兆"), (16, "京"), (20, "垓"), (24, "秭"),
            (28, "穰"), (32, "沟"), (36, "涧"), (40, "正"), (44, "载"), (48, "极"),
        ):
            self.assertIn(f'[1e{exponent}, "{suffix}"]', units)
        # A ten-thousand based ladder keeps 兆 at 10^12, not the short-scale 10^6.
        self.assertNotIn('[1e6, "兆"]', units)

    def test_traditional_aliases_are_accepted(self):
        multipliers = self.script.split("const CHINESE_MONEY_MULTIPLIERS", 1)[1].split("});", 1)[0]
        for alias, threshold in (
            ("萬", "1e4"), ("億", "1e8"), ("極", "1e48"),
            ("載", "1e44"), ("溝", "1e32"), ("澗", "1e36"),
        ):
            self.assertIn(f'"{alias}": {threshold}', multipliers)

    def test_the_switch_defaults_by_language_and_persists_locally(self):
        stored = self.script.split("function storedChineseMoneyUnits()", 1)[1].split("\n}", 1)[0]
        self.assertIn('if (stored === "true") return true;', stored)
        self.assertIn('if (stored === "false") return false;', stored)
        self.assertIn('return activeUiLocale().startsWith("zh");', stored)
        toggle = self.script.split('$("#chinese-money-units").addEventListener("change"', 1)[1].split("});", 1)[0]
        self.assertIn("CHINESE_MONEY_UNITS_STORAGE_KEY", toggle)

    def test_both_unit_tables_drive_every_compact_money_helper(self):
        self.assertIn("const moneyUnitTable = () => (", self.script)
        self.assertIn(
            "app.chineseMoneyUnits ? CHINESE_MONEY_UNITS : MONEY_ABBREVIATION_UNITS",
            self.script,
        )
        self.assertIn(
            "moneyUnitTable().find(([threshold]) => Math.abs(Number(value)) >= threshold) || null",
            self.script,
        )
        limit = self.script.split("const formatBettingLimitInput = (value) => {", 1)[1].split("\n};", 1)[0]
        self.assertIn("moneyUnitTable().find(([threshold]) => (", limit)

    def test_the_betting_limit_input_reads_chinese_suffixes(self):
        parser = self.script.split("const parseBettingLimitInput = (value) => {", 1)[1].split("\n};", 1)[0]
        self.assertIn("(万|萬|亿|億|兆|京|垓|秭|穰|沟|溝|涧|澗|正|载|載|极|極)", parser)
        self.assertIn("CHINESE_MONEY_MULTIPLIERS[chinese[2]]", parser)

    def test_the_toggle_sits_in_the_display_tab_with_translated_copy(self):
        self.assertIn('id="chinese-money-units"', self.html)
        self.assertIn('data-i18n="settings.money_units_chinese"', self.html)
        self.assertIn('data-i18n="settings.money_units_chinese_note"', self.html)
        display = self.script.split('key:"display", labelKey:"settings.tabs.display"', 1)[1].split("},", 1)[0]
        self.assertIn(".chinese-money-setting", display)
        for name in LOCALE_FILES:
            catalog = read_frontend_source(ROOT / "web" / name, mode="raw")
            self.assertIn('"settings.money_units_chinese"', catalog, name)
            self.assertIn('"settings.money_units_chinese_note"', catalog, name)


if __name__ == "__main__":
    unittest.main()
