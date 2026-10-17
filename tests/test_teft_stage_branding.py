#!/usr/bin/env python3
"""Hermetic regression tests for staged bundle permission and UI branding."""

import codecs
import importlib.util
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "stage_teft.py"
SPEC = importlib.util.spec_from_file_location("teft_stage_branding", SCRIPT)
stage_teft = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage_teft)


class PermissionBrandingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = Path(temporary.name).resolve() / "Teft.app"
        self.app.mkdir()

    def fixture(self):
        return {
            "CFBundleName": "iTerm2",
            "CFBundleDisplayName": "iTerm",
            "CFBundleIdentifier": "com.googlecode.iterm2",
            "CFBundleExecutable": "iTerm2",
            "CFBundleURLTypes": [{"CFBundleURLSchemes": ["iterm2"]}],
            "NSHumanReadableCopyright": "Copyright iTerm2 contributors",
            "NSCameraUsageDescription": "iTerm2 uses the camera for profile pictures.",
            "NSMicrophoneUsageDescription": "允许iTerm使用麦克风；保留中文。",
            "NSLocalNetworkUsageDescription": 'Allow iTerm2 to find “nearby” devices.\nNo uploads.',
            "NSBluetoothAlwaysUsageDescription": "Nearby device pairing only.",
            "NSAppleEventsUsageDescription": 'iTerm needs automation for \\"sessions\\".',
            "NSUnrelatedValue": "iTerm2 should remain here",
            "CustomUsageDescription": "iTerm should remain here too",
            "NSCameraUsageDescriptionSuffix": "iTerm2 should also remain here",
            "SUEnableAutomaticChecks": True,
        }

    def expected(self, original):
        result = dict(original)
        result.update({
            "CFBundleName": "Teft",
            "CFBundleDisplayName": "Teft",
            "NSCameraUsageDescription": "Teft uses the camera for profile pictures.",
            "NSMicrophoneUsageDescription": "允许Teft使用麦克风；保留中文。",
            "NSLocalNetworkUsageDescription": 'Allow Teft to find “nearby” devices.\nNo uploads.',
            "NSAppleEventsUsageDescription": 'Teft needs automation for \\"sessions\\".',
        })
        return result

    def check_plist(self, fmt, localized=False):
        original = self.fixture()
        path = self.app / ("InfoPlist.strings" if localized else "Info.plist")
        path.write_bytes(plistlib.dumps(original, fmt=fmt, sort_keys=False))
        function = stage_teft.brand_strings if localized else stage_teft.brand_plist
        function(path, self.app)
        actual = stage_teft.read_plist(path)
        self.assertEqual(actual, self.expected(original))
        self.assertEqual(set(actual), set(original), "No permission keys may be added")
        self.assertEqual(path.read_bytes().startswith(b"bplist"), fmt == plistlib.FMT_BINARY)
        first_pass = path.read_bytes()
        function(path, self.app)
        self.assertEqual(path.read_bytes(), first_pass, "Branding must be idempotent")

    def test_main_xml_plist(self):
        self.check_plist(plistlib.FMT_XML)

    def test_main_binary_plist(self):
        self.check_plist(plistlib.FMT_BINARY)

    def test_localized_xml_strings(self):
        self.check_plist(plistlib.FMT_XML, localized=True)

    def test_localized_binary_strings(self):
        self.check_plist(plistlib.FMT_BINARY, localized=True)

    def test_upstream_utf16_strings_with_utf8_xml_declaration(self):
        original = self.fixture()
        document = plistlib.dumps(original, sort_keys=False).decode("utf-8")
        self.assertIn('encoding="UTF-8"', document)
        path = self.app / "InfoPlist.strings"
        path.write_bytes(codecs.BOM_UTF16_LE + document.encode("utf-16-le"))
        stage_teft.brand_strings(path, self.app)
        actual = stage_teft.read_plist(path)
        self.assertEqual(actual, self.expected(original))
        self.assertEqual(set(actual), set(original))

    def test_openstep_preserves_comments_quotes_and_escapes(self):
        original = r'''{
/* iTerm2 comment remains untouched */
"CFBundleDisplayName" = "iTerm2";
CFBundleName = iTerm;
"NSCameraUsageDescription" = "Allow iTerm2 to use the camera for \"profile\" photos.\n保留。";
NSMicrophoneUsageDescription = "允许iTerm使用麦克风；iTerm2只用于会话。";
"NSBluetoothAlwaysUsageDescription" = "Pairing only: \U4f60\U597d.";
// iTerm comment remains untouched
"NSHumanReadableCopyright" = "Copyright iTerm2 contributors";
"CFBundleIdentifier" = "com.googlecode.iterm2";
"CFBundleURLSchemes" = "iterm2";
"Unrelated" = "iTerm2 \"keep\"";
"CustomUsageDescription" = "iTerm";
"NSCameraUsageDescriptionSuffix" = "iTerm2";
}
'''
        expected = original.replace('"CFBundleDisplayName" = "iTerm2"',
                                    '"CFBundleDisplayName" = "Teft"')
        expected = expected.replace('CFBundleName = iTerm;', 'CFBundleName = "Teft";')
        expected = expected.replace('Allow iTerm2 to use', 'Allow Teft to use')
        expected = expected.replace('允许iTerm使用麦克风；iTerm2只用于会话。',
                                    '允许Teft使用麦克风；Teft只用于会话。')
        path = self.app / "InfoPlist.strings"
        path.write_bytes(original.encode("utf-16"))
        stage_teft.brand_strings(path, self.app)
        self.assertEqual(path.read_bytes().decode("utf-16"), expected)
        first_pass = path.read_bytes()
        stage_teft.brand_strings(path, self.app)
        self.assertEqual(path.read_bytes(), first_pass)

    def test_permission_free_localization_does_not_gain_permission_keys(self):
        original = {"CFBundleDisplayName": "iTerm2", "Other": "iTerm2"}
        path = self.app / "InfoPlist.strings"
        path.write_bytes(plistlib.dumps(original))
        stage_teft.brand_strings(path, self.app)
        self.assertEqual(stage_teft.read_plist(path),
                         {"CFBundleDisplayName": "Teft", "Other": "iTerm2"})


class UIBrandingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.app = self.root / "Teft.app"
        self.resources = self.app / "Contents/Resources"
        self.resources.mkdir(parents=True)
        self.info = self.app / "Contents/Info.plist"
        self.info.write_bytes(plistlib.dumps({
            "CFBundleIdentifier": "com.teft.app",
            "CFBundleExecutable": "Teft",
            "CFBundleURLSchemes": ["iterm2"],
        }))
        self.catalogs = self.root / "catalogs"
        self.catalogs.mkdir()

    def entry(self, english, chinese=None):
        localizations = {"en": {"stringUnit": {"value": english, "state": "new"}}}
        if chinese is not None:
            localizations["zh-Hans"] = {
                "stringUnit": {"value": chinese, "state": "translated"},
            }
        return {"localizations": localizations}

    def catalog(self, relative_path, strings):
        path = self.catalogs / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"sourceLanguage": "en", "strings": strings},
                                   ensure_ascii=False), encoding="utf-8")
        return path

    def table(self, language, name="Localizable"):
        return self.resources / f"{language}.lproj" / f"{name}.strings"

    def snapshot(self, directory):
        return {str(path.relative_to(directory)): path.read_bytes()
                for path in directory.rglob("*") if path.is_file()}

    def test_creates_english_defaults_and_merges_localized_display_values(self):
        catalog = self.catalog("xcstrings/Localizable.xcstrings", {
            "QuitAlert.Title": self.entry("Quit iTerm2?", "退出 iTerm2？"),
            "StatusMenu.QuitiTerm2": self.entry("Quit iTerm2", "退出 iTerm2"),
            "Upstream.Sponsor": self.entry("Sponsor iTerm2 at https://iterm2.com"),
        })
        menu_catalog = self.catalog("sources/MainMenu/mul.lproj/MainMenu.xcstrings", {
            "57.title": self.entry("iTerm2", "iTerm2"),
        })
        original_catalogs = self.snapshot(self.catalogs)
        chinese = self.table("zh-Hans")
        chinese.parent.mkdir()
        preserved = {
            "Upstream.Sponsor": "Sponsor iTerm2 at https://iterm2.com",
            "Compatibility.URL": "iterm2://example.invalid",
            "Compatibility.Protocol": "iterm2-daemon-42.socket",
            "Compatibility.Identifier": "com.googlecode.iterm2",
            "Unrelated": "iTerm2Codec and ThirdParty",
        }
        chinese.write_bytes(plistlib.dumps({**preserved, "QuitAlert.Title": "旧值"},
                                          fmt=plistlib.FMT_BINARY))
        nib = self.resources / "MainMenu.nib"
        nib.write_bytes(b"\x00iTerm2\xffNib bytes must remain unchanged")
        third_party = self.resources / "ThirdParty.strings"
        third_party.write_bytes(b'"Sparkle.Credit" = "iTerm2 contributors";\n')
        unchanged_resources = {path: path.read_bytes()
                               for path in (self.info, nib, third_party)}
        self.assertFalse(self.table("en").exists(), "English relies on source defaults")

        allowlist = {
            str(catalog.relative_to(self.catalogs)):
                ("QuitAlert.Title", "StatusMenu.QuitiTerm2"),
            str(menu_catalog.relative_to(self.catalogs)): ("57.title",),
        }
        with mock.patch.object(stage_teft, "UI_BRANDING_CATALOGS", allowlist):
            self.assertEqual(stage_teft.brand_ui_strings(self.app, self.catalogs), 6)
            first_pass = self.snapshot(self.app)
            self.assertEqual(stage_teft.brand_ui_strings(self.app, self.catalogs), 6)
            self.assertEqual(self.snapshot(self.app), first_pass,
                             "Repeated staging must not rewrite or add resources")

        self.assertEqual(stage_teft.read_plist(self.table("en")), {
            "QuitAlert.Title": "Quit Teft?",
            "StatusMenu.QuitiTerm2": "Quit Teft",
        })
        self.assertEqual(stage_teft.read_plist(chinese), {
            **preserved,
            "QuitAlert.Title": "退出 Teft？",
            "StatusMenu.QuitiTerm2": "退出 Teft",
        })
        self.assertEqual(stage_teft.read_plist(self.table("en", "MainMenu")),
                         {"57.title": "Teft"})
        self.assertEqual(stage_teft.read_plist(self.table("zh-Hans", "MainMenu")),
                         {"57.title": "Teft"})
        self.assertEqual(self.snapshot(self.catalogs), original_catalogs,
                         "Canonical upstream catalogs must remain byte-identical")
        for path, original in unchanged_resources.items():
            self.assertEqual(path.read_bytes(), original, str(path))

    def test_preserves_format_placeholders_quotes_and_newlines(self):
        english = 'iTerm2 opened “%@” (%1$ld of %2$ld, 100%%).\nKeep \\"quoted\\" text.'
        chinese = 'iTerm为“%@”打开了 %ld 个会话。\n保留引号 “ ” 和路径 C:\\term。'
        self.catalog("xcstrings/Localizable.xcstrings", {
            "OpenLink.Heading": self.entry(english, chinese),
        })
        with mock.patch.object(stage_teft, "UI_BRANDING_CATALOGS", {
            "xcstrings/Localizable.xcstrings": ("OpenLink.Heading",),
        }):
            self.assertEqual(stage_teft.brand_ui_strings(self.app, self.catalogs), 2)
        self.assertEqual(stage_teft.read_plist(self.table("en"))["OpenLink.Heading"],
                         'Teft opened “%@” (%1$ld of %2$ld, 100%%).\nKeep \\"quoted\\" text.')
        self.assertEqual(stage_teft.read_plist(self.table("zh-Hans"))["OpenLink.Heading"],
                         'Teft为“%@”打开了 %ld 个会话。\n保留引号 “ ” 和路径 C:\\term。')

    def test_rejects_upstream_bundle_before_writing_resources(self):
        self.info.write_bytes(plistlib.dumps({"CFBundleIdentifier": "com.googlecode.iterm2"}))
        self.catalog("xcstrings/Localizable.xcstrings", {
            "QuitAlert.Title": self.entry("Quit iTerm2?"),
        })
        before = self.snapshot(self.app)
        with mock.patch.object(stage_teft, "UI_BRANDING_CATALOGS", {
            "xcstrings/Localizable.xcstrings": ("QuitAlert.Title",),
        }):
            with self.assertRaisesRegex(stage_teft.StageError, "Teft bundle identity"):
                stage_teft.brand_ui_strings(self.app, self.catalogs)
        self.assertEqual(self.snapshot(self.app), before)

    def test_missing_reviewed_key_fails_instead_of_silently_skipping(self):
        self.catalog("xcstrings/Localizable.xcstrings", {
            "Unrelated": self.entry("iTerm2"),
        })
        before = self.snapshot(self.app)
        with mock.patch.object(stage_teft, "UI_BRANDING_CATALOGS", {
            "xcstrings/Localizable.xcstrings": ("QuitAlert.Title",),
        }):
            with self.assertRaisesRegex(stage_teft.StageError, "Missing reviewed UI key QuitAlert.Title"):
                stage_teft.brand_ui_strings(self.app, self.catalogs)
        self.assertEqual(self.snapshot(self.app), before)

    def test_requires_english_default_and_flat_localizations(self):
        cases = (
            ({"localizations": {"zh-Hans": {"stringUnit": {"value": "退出 iTerm2？"}}}},
             "Missing English UI default"),
            ({"localizations": {"en": {"variations": {"plural": {}}}}},
             "Expected a flat UI string"),
        )
        for entry, message in cases:
            with self.subTest(message=message):
                self.catalog("xcstrings/Localizable.xcstrings", {"QuitAlert.Title": entry})
                before = self.snapshot(self.app)
                with mock.patch.object(stage_teft, "UI_BRANDING_CATALOGS", {
                    "xcstrings/Localizable.xcstrings": ("QuitAlert.Title",),
                }):
                    with self.assertRaisesRegex(stage_teft.StageError, message):
                        stage_teft.brand_ui_strings(self.app, self.catalogs)
                self.assertEqual(self.snapshot(self.app), before)

    def test_project_reviewed_catalogs_cover_quit_and_have_supported_localizations(self):
        project = SCRIPT.parents[1]
        # This alert mixes the product name with compatibility filesystem paths.
        # A display-name change must not invent a different data location.
        mixed_key = "ImportExport.EraseConfirmTitle"
        code_catalog = json.loads((project / "xcstrings/Localizable.xcstrings").read_text())
        mixed_value = code_catalog["strings"][mixed_key]["localizations"]["en"]["stringUnit"]["value"]
        self.assertIn("~/Library/Application Support/iTerm2", mixed_value)
        self.table("en").parent.mkdir()
        self.table("en").write_bytes(plistlib.dumps({mixed_key: mixed_value}))
        self.assertIn("QuitAlert.Title", stage_teft.UI_BRANDING_CATALOGS[
            "xcstrings/Localizable.xcstrings"])
        self.assertIn("StatusMenu.QuitiTerm2", stage_teft.UI_BRANDING_CATALOGS[
            "xcstrings/Localizable.xcstrings"])
        original_catalogs = {}
        expected_values = 0
        for relative_path, keys in stage_teft.UI_BRANDING_CATALOGS.items():
            path = project / relative_path
            original_catalogs[path] = path.read_bytes()
            catalog = json.loads(path.read_text(encoding="utf-8"))
            for key in keys:
                with self.subTest(catalog=relative_path, key=key):
                    self.assertIn(key, catalog["strings"])
                    localizations = catalog["strings"][key]["localizations"]
                    self.assertIn("en", localizations)
                    for language, localization in localizations.items():
                        self.assertRegex(language, r"^[A-Za-z0-9-]+$")
                        self.assertIsInstance(localization["stringUnit"]["value"], str)
                        self.assertNotIn("variations", localization)
                        expected_values += 1
        self.assertEqual(stage_teft.brand_ui_strings(self.app), expected_values)
        self.assertEqual(stage_teft.read_plist(self.table("en"))["QuitAlert.Title"], "Quit Teft?")
        self.assertEqual(stage_teft.read_plist(self.table("zh-Hans"))["QuitAlert.Title"], "退出 Teft？")
        self.assertEqual(stage_teft.read_plist(self.table("en"))[mixed_key], mixed_value)
        for path, original in original_catalogs.items():
            self.assertEqual(path.read_bytes(), original, str(path))


if __name__ == "__main__":
    unittest.main()
