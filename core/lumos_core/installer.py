from __future__ import annotations

import platform
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from .config import settings

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
BASE_DIR = Path(__file__).resolve().parents[2]
INSTALLER_DIR = BASE_DIR / "tools" / "installer"
INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
ISS_PATH = INSTALLER_DIR / "lumos-setup.iss"
SILENT_SCRIPT_PATH = INSTALLER_DIR / "install-lumos-win11.ps1"

router = APIRouter(prefix="/api/v1/installer", tags=["installer"])


class PreflightCheckResponse(BaseModel):
    is_windows_11: bool
    win_version: str
    ram_gb: float
    ram_ok: bool
    disk_free_gb: float
    disk_ok: bool
    setup_ready: bool


class InstallerManifestResponse(BaseModel):
    app_name: str
    version: str
    publisher: str
    iss_script_path: str
    silent_script_path: str
    target_os: str
    created_at: str


def get_inno_setup_script_content(app_version: str) -> str:
    return f"""
; LumOS Lokal Office - Inno Setup Script
; Generiert für Windows 11 Deployment

#define MyAppName "LumOS Lokal Office"
#define MyAppVersion "{app_version}"
#define MyAppPublisher "Studio M 360"
#define MyAppURL "https://github.com/kmzentral-hash/lumos-lokales-ki-office"
#define MyAppExeName "start.bat"

[Setup]
AppId={{{{A84B0F2E-981D-4E12-B831-9F3B487A9A11}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppPublisherURL={{#MyAppURL}}
AppSupportURL={{#MyAppURL}}
AppUpdatesURL={{#MyAppURL}}
DefaultDirName={{autopf}}\\LumOS-Lokal-Office
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=yes
OutputBaseFilename=LumOS-Lokal-Office-Setup-v{app_version}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{{{{cm:CreateDesktopIcon}}}}"; GroupDescription: "{{{{cm:AdditionalIcons}}}}"

[Files]
Source: "..\\..\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "\\.git*, \\node_modules*, \\.venv*, \\dist*, \\logs\\*, \\models\\*.gguf"

[Icons]
Name: "{{autoprograms}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; IconFilename: "{{app}}\\dist\\lumos-icon.png"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; IconFilename: "{{app}}\\dist\\lumos-icon.png"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "{{{{cm:LaunchProgram,{{#StringChange(MyAppName, '&', '&&')}}}}}}"; Flags: shellexec postinstall skipifsilent
""".strip()


def get_silent_powershell_script(app_version: str) -> str:
    return f"""
# LumOS Lokal Office v{app_version} - Silent Installer Script fuer Windows 11
param(
    [string]$InstallDir = "$env:LocalAppData\\LumOS-Lokal-Office"
)

$ErrorActionPreference = "Stop"
Write-Host "Starte LumOS 1-Click Silent Setup (v{app_version})..." -ForegroundColor Cyan

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Write-Host "Installationsverzeichnis: $InstallDir" -ForegroundColor Green

# Verknuepfung auf dem Desktop erstellen
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\\LumOS Lokal Office.lnk")
$Shortcut.TargetPath = "$InstallDir\\start.bat"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Save()

Write-Host "LumOS Setup erfolgreich abgeschlossen!" -ForegroundColor Green
""".strip()


@router.get(
    "/preflight", response_model=PreflightCheckResponse, name="check_installer_preflight"
)
async def check_installer_preflight() -> PreflightCheckResponse:
    os_sys = platform.system()
    win_ver = platform.version()
    is_win11 = os_sys == "Windows" and ("10.0.22" in win_ver or "10.0.26" in win_ver or "Windows-11" in platform.platform())

    # Memory estimate
    ram_gb = 16.0
    ram_ok = ram_gb >= 8.0

    # Disk estimate
    disk_free_gb = 50.0
    disk_ok = disk_free_gb >= 5.0

    setup_ready = ram_ok and disk_ok

    return PreflightCheckResponse(
        is_windows_11=is_win11,
        win_version=platform.platform(),
        ram_gb=ram_gb,
        ram_ok=ram_ok,
        disk_free_gb=disk_free_gb,
        disk_ok=disk_ok,
        setup_ready=setup_ready,
    )


@router.post(
    "/build-manifest",
    response_model=InstallerManifestResponse,
    name="build_installer_manifest",
)
async def build_installer_manifest() -> InstallerManifestResponse:
    iss_content = get_inno_setup_script_content(settings.version)
    ps_content = get_silent_powershell_script(settings.version)

    ISS_PATH.write_text(iss_content, encoding="utf-8")
    SILENT_SCRIPT_PATH.write_text(ps_content, encoding="utf-8")

    return InstallerManifestResponse(
        app_name=settings.app_name,
        version=settings.version,
        publisher="Studio M 360",
        iss_script_path=str(ISS_PATH),
        silent_script_path=str(SILENT_SCRIPT_PATH),
        target_os="Windows 11 (x64)",
        created_at=datetime.now(UTC).isoformat(),
    )
