#!/usr/bin/env python3
"""Hermetic regression tests for staged bundle permission branding."""

import codecs
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()
