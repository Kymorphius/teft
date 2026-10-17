#!/usr/bin/env python3
"""Create an ad-hoc signed development app with Teft’s product identity."""

import argparse
import codecs
import datetime
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from xml.parsers.expat import ExpatError


BRAND_KEYS = ("CFBundleName", "CFBundleDisplayName")
BUNDLE_IDENTIFIER = "com.teft.app"
EXECUTABLE_NAME = "Teft"
HELPER_DISPLAY_NAMES = {
    "com.teft.app.sandboxed-worker": "Teft Worker",
    "com.teft.app.pidinfo": "Teft PID Info",
    "com.teft.app.import-status": "Teft Import",
}
OWNED_HELPERS = (
    ("Contents/XPCServices/iTerm2SandboxedWorker.xpc",
     "com.iterm2.sandboxed-worker", "com.teft.app.sandboxed-worker",
     "TeftSandboxedWorkerServiceName"),
    ("Contents/XPCServices/pidinfo.xpc",
     "com.iterm2.pidinfo", "com.teft.app.pidinfo", "TeftProcessInfoServiceName"),
    ("Contents/MacOS/iTerm2ImportStatus.app",
     "com.googlecode.iterm2.iTerm2ImportStatus", "com.teft.app.import-status", None),
)
# Reviewed display strings only. Keys, selectors, URLs, compatibility names,
# upstream credits, and third-party product names keep their original identity.
UI_BRANDING_CATALOGS = {
    "xcstrings/Localizable.xcstrings": (
        "APIHelper.AllowConnectionMessage",
        "APIHelper.EnablePythonAPIMessage",
        "Appearance.ExcludeFromDockWarning",
        "GeneralPrefs.ModelUpdateDownloaded",
        "GeneralPrefs.RestartRequired",
        "GeneralPrefs.WindowRestorationDisabledMessage13",
        "GeneralPrefs.WindowRestorationDisabledMessageLegacy",
        "ImportExport.DryRunCompleteBody",
        "ImportExport.DryRunConfirmTitle",
        "ImportExport.ExportPanelTitle",
        "ImportExport.ImportConfirmBody",
        "InstanceLock.Heading",
        "InstanceLock.Message",
        "InstanceLock.SuiteMessage",
        "KeysPreferences.HotkeyPanelExplanation",
        "LaunchServices.NotDefaultHandlerTitle",
        "OpenLink.FileTitle",
        "OpenLink.Heading",
        "OpenLink.OpenIniTerm2",
        "OpenLink.WebTitle",
        "PTYSession.AIChatCouldNotOpen",
        "PTYSession.AlreadyAttachedTmux",
        "PTYSession.IT2AuthorizationPrompt",
        "PasswordManager.ResetConfigurationWarning",
        "PasswordManagerAuth.AppCancel",
        "PasswordManagerAuth.InvalidContext",
        "PasteboardReporter.ConfirmEnableBody",
        "PromptOnClose.ConfirmQuitEnabled",
        "PromptOnClose.ConfirmQuitWithoutWindows",
        "PseudoTerminal.RestartToEnableFeature",
        "QuitAlert.SessionsRestored",
        "QuitAlert.Title",
        "RemotePreferences.RemoteChangedOverwritePrompt",
        "RemotePreferences.SyncDataFilesPrompt",
        "RestorableState.RestoreWindowsMessage",
        "RestorableState.SlowRestoreBody",
        "SecureUserDefaults.CreateFolderPrompt",
        "SecureUserDefaults.ModifySettingsPrompt",
        "SecureUserDefaults.ModifySingleSettingPrompt",
        "StatusMenu.QuitiTerm2",
        "SuppressedAlerts.ShowRememberedTooltip",
        "Warning.RememberedSelectionExplanation",
    ),
    "sources/MainMenu/mul.lproj/MainMenu.xcstrings": (
        "56.title", "57.title", "111.title", "134.title", "136.title",
        "233.title", "1470.title", "it2-au-th0.title",
    ),
    "sources/Settings/mul.lproj/PreferencePanel.xcstrings": (
        "6Fq-pl-5nd.ibShadowedToolTip", "7dn-rM-ht2.title",
        "7pa-hD-WIi.ibExternalAccessibilityDescription", "4758.title",
        "Heb-gk-qk8.title", "iWk-HJ-EKg.ibShadowedToolTip",
        "mlk-a6-xcL.ibShadowedToolTip", "NtK-Fc-1Kb.ibShadowedToolTip",
        "OWt-qh-bb4.ibShadowedToolTip", "wjs-vG-qf2.ibShadowedToolTip",
        "zde-kb-c7t.ibShadowedToolTip",
    ),
    "sources/AboutWindow/mul.lproj/AboutWindow.xcstrings": (
        "U4n-GV-8aZ.title",
    ),
}
TOKEN = re.compile(
    r'(?P<space>\s+)|(?P<comment>//[^\r\n]*|/\*.*?\*/)|'
    r'(?P<quoted>"(?:\\.|[^"\\])*")|'
    r'(?P<bare>[A-Za-z0-9_./$:+-]+)|(?P<punct>[=;{}])',
    re.DOTALL,
)


class StageError(Exception):
    """An invalid input or failed staging operation."""


def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def load_plist(data):
    if not data.startswith(b"bplist"):
        content = data.decode(strings_encoding(data))
        if content.lstrip().startswith("<"):
            # Some upstream strings files are UTF-16 with a UTF-8 XML declaration.
            # Decode using the actual bytes and parse a consistent UTF-8 document.
            content = re.sub(
                r'(<\?xml\b[^?]*?)\s+encoding\s*=\s*([\"\']).*?\2',
                r'\1', content, count=1,
            )
            data = content.encode("utf-8")
    return plistlib.loads(data)


def read_plist(path):
    value = load_plist(path.read_bytes())
    if not isinstance(value, dict):
        raise StageError(f"Expected a property-list dictionary: {path}")
    return value


def check_staged_links(app_root):
    """Keep deep signing from reaching the source bundle or external files."""
    for directory, directories, files in os.walk(app_root, followlinks=False):
        for name in directories + files:
            path = Path(directory) / name
            if path.is_symlink() and not inside(path.resolve(), app_root):
                raise StageError(f"Staged symlink points outside the app: {path}")


def write_contents(path, data, app_root):
    """Replace only a staged file, including when the original is a symlink."""
    if not inside(path.parent.resolve(), app_root):
        raise StageError(f"Refusing to write outside the staged app: {path}")
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(prefix=".teft-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def is_permission_description(key):
    return key.startswith("NS") and key.endswith("UsageDescription")


def brand_permission_description(value):
    # ASCII boundaries also match the brand next to Chinese or Japanese text.
    return re.sub(r"(?<![A-Za-z0-9_])iTerm2?(?![A-Za-z0-9_])", "Teft", value)


def brand_ui_strings(app_root, catalog_root=None):
    """Overlay reviewed UI values, including English defaults embedded in code."""
    if read_plist(app_root / "Contents/Info.plist").get("CFBundleIdentifier") != BUNDLE_IDENTIFIER:
        raise StageError("UI branding requires the staged Teft bundle identity.")
    if catalog_root is None:
        catalog_root = Path(__file__).resolve().parents[1]
    resources = app_root / "Contents/Resources"
    count = 0
    for relative_path, keys in UI_BRANDING_CATALOGS.items():
        catalog_path = catalog_root / relative_path
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        entries = catalog["strings"]
        by_language = {}
        for key in keys:
            if key not in entries:
                raise StageError(f"Missing reviewed UI key {key}: {catalog_path}")
            localizations = entries[key].get("localizations", {})
            if "en" not in localizations:
                raise StageError(f"Missing English UI default for {key}: {catalog_path}")
            for language, localization in localizations.items():
                if not re.fullmatch(r"[A-Za-z0-9-]+", language):
                    raise StageError(f"Invalid UI localization name: {language}")
                value = localization.get("stringUnit", {}).get("value")
                if not isinstance(value, str):
                    raise StageError(f"Expected a flat UI string for {key}: {catalog_path}")
                by_language.setdefault(language, {})[key] = brand_permission_description(value)
        for language, overrides in by_language.items():
            path = resources / f"{language}.lproj" / f"{catalog_path.stem}.strings"
            if not inside(path.parent.resolve(), app_root):
                raise StageError(f"UI strings point outside the staged app: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            original = read_plist(path) if path.exists() else {}
            expected = {**original, **overrides}
            if expected != original:
                write_contents(path, plistlib.dumps(expected, sort_keys=False), app_root)
            if read_plist(path) != expected:
                raise StageError(f"UI string readback differs from allowed changes: {path}")
            count += len(overrides)
    return count


def brand_plist(path, app_root, disable_updates=False):
    data = path.read_bytes()
    value = read_plist(path)
    before = value.copy()
    for key in BRAND_KEYS:
        if disable_updates or key in value:
            value[key] = "Teft"
    for key, description in value.items():
        if is_permission_description(key) and isinstance(description, str):
            value[key] = brand_permission_description(description)
    if disable_updates:
        value["SUEnableAutomaticChecks"] = False
        print("Staged app: SUEnableAutomaticChecks set to false.", file=sys.stderr)
    if value != before:
        fmt = plistlib.FMT_BINARY if data.startswith(b"bplist") else plistlib.FMT_XML
        write_contents(path, plistlib.dumps(value, fmt=fmt, sort_keys=False), app_root)


def strings_encoding(data):
    for marker, encoding in (
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
        (codecs.BOM_UTF8, "utf-8-sig"),
    ):
        if data.startswith(marker):
            return encoding
    if b"\x00" in data:
        return "utf-16-be" if data.startswith(b"\x00") else "utf-16-le"
    return "utf-8"


def brand_strings(path, app_root):
    data = path.read_bytes()
    try:
        load_plist(data)
    except (plistlib.InvalidFileException, ValueError, ExpatError):
        if data.startswith(b"bplist") or data.lstrip().startswith(b"<"):
            raise StageError(f"Invalid property list: {path}")
    else:
        brand_plist(path, app_root)
        return

    encoding = strings_encoding(data)
    content = data.decode(encoding)
    tokens = []
    position = 0
    while position < len(content):
        match = TOKEN.match(content, position)
        if match is None:
            raise StageError(f"Unsupported strings syntax at offset {position}: {path}")
        if match.lastgroup not in ("space", "comment"):
            tokens.append(match)
        position = match.end()
    if tokens and tokens[0].group() == "{":
        if tokens[-1].group() != "}":
            raise StageError(f"Unclosed strings dictionary: {path}")
        tokens = tokens[1:-1]
    if len(tokens) % 4:
        raise StageError(f"Expected key = value; entries: {path}")
    replacements = []
    for index in range(0, len(tokens), 4):
        key, equals, value, semicolon = tokens[index:index + 4]
        if (
            key.lastgroup not in ("quoted", "bare")
            or equals.group() != "="
            or value.lastgroup not in ("quoted", "bare")
            or semicolon.group() != ";"
        ):
            raise StageError(f"Expected key = value; entry at offset {key.start()}: {path}")
        key_name = key.group().strip('"')
        if key_name in BRAND_KEYS:
            replacements.append((value.start(), value.end(), '"Teft"'))
        elif is_permission_description(key_name):
            branded = brand_permission_description(value.group())
            if branded != value.group():
                replacements.append((value.start(), value.end(), branded))
    for start, end, value in reversed(replacements):
        content = content[:start] + value + content[end:]
    if replacements:
        write_contents(path, content.encode(encoding), app_root)


def codesign(*arguments):
    result = subprocess.run(
        ["/usr/bin/codesign", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise StageError(f"codesign failed ({result.returncode}): {detail}")
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)


def stage(source_app, output_dir, suite):
    if not suite or suite in (".", "..") or Path(suite).name != suite:
        raise StageError("The defaults suite must be a nonempty directory name.")
    source = source_app.expanduser().resolve(strict=True)
    output = output_dir.expanduser().resolve()
    if not source.is_dir():
        raise StageError(f"Source app is not a directory: {source}")
    info_path = source / "Contents" / "Info.plist"
    if not info_path.is_file() or not inside(info_path.resolve(), source):
        raise StageError(f"Source app has no local Contents/Info.plist: {source}")
    original = read_plist(info_path)
    identifier = original.get("CFBundleIdentifier")
    executable_name = original.get("CFBundleExecutable")
    if not isinstance(identifier, str) or not identifier:
        raise StageError("Source app has no valid CFBundleIdentifier.")
    if identifier not in ("com.googlecode.iterm2", BUNDLE_IDENTIFIER):
        raise StageError(f"Unexpected source app identity: {identifier}")
    if (
        not isinstance(executable_name, str)
        or not executable_name
        or Path(executable_name).name != executable_name
    ):
        raise StageError("Source app has no valid CFBundleExecutable filename.")
    executable = source / "Contents" / "MacOS" / executable_name
    if (
        not executable.is_file()
        or not os.access(executable, os.X_OK)
        or not inside(executable.resolve(), source)
    ):
        raise StageError(f"Source executable is missing, external, or not executable: {executable}")
    if inside(output, source):
        raise StageError("Output directory must be outside the source app.")
    output.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    version_dir = Path(tempfile.mkdtemp(prefix=f"teft-{timestamp}-", dir=output))
    app = version_dir / "Teft.app"
    print(f"Staging directory (retained on failure): {version_dir}", file=sys.stderr)
    shutil.copytree(source, app, symlinks=True)
    check_staged_links(app)
    expected_plists = {path: read_plist(path) for path in app.rglob("Info.plist")}
    staged_info = app / "Contents" / "Info.plist"
    staged_executable = app / "Contents" / "MacOS" / EXECUTABLE_NAME
    if executable_name != EXECUTABLE_NAME:
        if staged_executable.exists() or staged_executable.is_symlink():
            raise StageError(f"Staged executable name is already in use: {staged_executable}")
        (app / "Contents" / "MacOS" / executable_name).rename(staged_executable)
    brand_plist(staged_info, app, disable_updates=True)
    staged_settings = read_plist(staged_info)
    staged_settings["TeftDefaultsSuite"] = suite
    staged_settings["SUDefaultsDomain"] = suite
    staged_settings["CFBundleIdentifier"] = BUNDLE_IDENTIFIER
    staged_settings["CFBundleExecutable"] = EXECUTABLE_NAME
    for relative_path, upstream_id, teft_id, service_key in OWNED_HELPERS:
        helper_info = app / relative_path / "Contents" / "Info.plist"
        helper_settings = expected_plists.get(helper_info)
        if not helper_settings or helper_settings.get("CFBundleIdentifier") not in (upstream_id, teft_id):
            raise StageError(f"Missing or unexpected owned helper: {relative_path}")
        helper_settings = helper_settings.copy()
        helper_settings["CFBundleIdentifier"] = teft_id
        for key in BRAND_KEYS:
            helper_settings[key] = HELPER_DISPLAY_NAMES[teft_id]
        expected_plists[helper_info] = helper_settings
        write_contents(helper_info, plistlib.dumps(helper_settings, sort_keys=False), app)
        if service_key:
            staged_settings[service_key] = teft_id
    write_contents(staged_info, plistlib.dumps(staged_settings, sort_keys=False), app)
    for strings_path in sorted((app / "Contents" / "Resources").glob("*.lproj/InfoPlist.strings")):
        if not inside(strings_path.resolve(), app):
            raise StageError(f"Localized strings point outside the staged app: {strings_path}")
        brand_strings(strings_path, app)
    ui_string_count = brand_ui_strings(app)
    codesign("--force", "--deep", "--sign", "-", str(app))
    # Apply explicit identifiers only to the owned bundles, never with --deep.
    # Passing --identifier together with --deep would also rename framework signatures.
    for relative_path, _, teft_id, _ in OWNED_HELPERS:
        codesign("--force", "--sign", "-", "--identifier", teft_id, str(app / relative_path))
    codesign("--force", "--sign", "-", "--identifier", BUNDLE_IDENTIFIER, str(app))
    codesign("--verify", "--deep", "--strict", str(app))
    readback = read_plist(staged_info)
    expected = original.copy()
    for key in BRAND_KEYS:
        expected[key] = "Teft"
    expected["TeftDefaultsSuite"] = suite
    expected["SUDefaultsDomain"] = suite
    expected["SUEnableAutomaticChecks"] = False
    expected["CFBundleIdentifier"] = BUNDLE_IDENTIFIER
    expected["CFBundleExecutable"] = EXECUTABLE_NAME
    for key, description in original.items():
        if is_permission_description(key) and isinstance(description, str):
            expected[key] = brand_permission_description(description)
    for _, _, teft_id, service_key in OWNED_HELPERS:
        if service_key:
            expected[service_key] = teft_id
    expected_plists[staged_info] = expected
    for path, expected_settings in expected_plists.items():
        if read_plist(path) != expected_settings:
            raise StageError(f"Signed property-list readback differs from allowed changes: {path}")
    if not staged_executable.is_file() or not os.access(staged_executable, os.X_OK):
        raise StageError(f"Staged executable is missing or not executable: {staged_executable}")
    return {
        "app_path": str(app),
        "executable_path": str(staged_executable),
        "bundle_identifier": readback["CFBundleIdentifier"],
        "display_name": readback["CFBundleDisplayName"],
        "defaults_suite": readback["TeftDefaultsSuite"],
        "branded_ui_strings": ui_string_count,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-app", type=Path, required=True, help="Compiled source .app bundle.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for versioned development artifacts.")
    parser.add_argument("--suite", required=True, help="Defaults suite for this checkout’s development app.")
    arguments = parser.parse_args()
    try:
        result = stage(arguments.source_app, arguments.output_dir, arguments.suite)
    except (StageError, OSError, ValueError, plistlib.InvalidFileException, ExpatError) as error:
        print(f"Teft staging failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
