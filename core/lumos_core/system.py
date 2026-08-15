from __future__ import annotations

import ctypes
import json
import logging
import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from .config import settings

logger = logging.getLogger("uvicorn.error")
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
BASE_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = BASE_DIR / "models"
ALLOWLIST_PATH = BASE_DIR / "docs" / "security" / "model-allowlist.json"
LICENSES_DIR = BASE_DIR / "docs" / "licenses"
LICENSES_DIR.mkdir(parents=True, exist_ok=True)
SBOM_PATH = LICENSES_DIR / "sbom.json"

router = APIRouter(prefix="/api/v1/system", tags=["system"])


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class HardwareInfoResponse(BaseModel):
    os_name: str
    os_version: str
    cpu_cores_logical: int
    memory_total_gb: float
    memory_available_gb: float
    gpu_name: str | None
    gpu_acceleration: str
    recommended_profile: str
    status: str


class ModelItem(BaseModel):
    name: str
    filename: str
    path: str
    size_mb: float
    allowlist_status: str


class ModelScanResponse(BaseModel):
    models_dir: str
    installed_models: list[ModelItem]
    count: int


class SbomComponent(BaseModel):
    name: str
    version: str
    license: str
    purpose: str
    status: str


class SbomResponse(BaseModel):
    app_name: str
    version: str
    updated_at: str
    components: list[SbomComponent]


def get_windows_memory_gb() -> tuple[float, float]:
    if platform.system() == "Windows":
        try:
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total = round(stat.ullTotalPhys / (1024**3), 1)
                avail = round(stat.ullAvailPhys / (1024**3), 1)
                return total, avail
        except Exception as exc:  # noqa: BLE001
            logger.debug("Memory check fallback triggered: %s", exc)
    return 16.0, 8.0


def get_gpu_name() -> str | None:
    if platform.system() == "Windows":
        try:
            cmd = "powershell -Command \"Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name\""
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3, check=False)
            if res.returncode == 0 and res.stdout.strip():
                lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                return lines[0] if lines else None
        except Exception as exc:  # noqa: BLE001
            logger.debug("GPU check fallback triggered: %s", exc)
    return None


def get_allowlist_map() -> dict[str, str]:
    if ALLOWLIST_PATH.exists():
        try:
            data = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
            result = {}
            for item in data.get("allowed_models", []):
                repo = item.get("exact_repository", "")
                status = item.get("status", "candidate")
                if repo:
                    result[repo.lower()] = status
                    result[repo.split("/")[-1].lower()] = status
            return result
        except Exception as exc:  # noqa: BLE001
            logger.debug("Allowlist read fallback triggered: %s", exc)
    return {"qwen2.5-7b-instruct-gguf": "candidate"}


@router.get("/hardware", response_model=HardwareInfoResponse, name="get_hardware_info")
async def get_hardware_info() -> HardwareInfoResponse:
    os_sys = platform.system()
    os_ver = platform.platform()
    cpu_cores = os.cpu_count() or 4
    total_ram, avail_ram = get_windows_memory_gb()
    gpu = get_gpu_name()

    gpu_accel = "CPU Fallback"
    if gpu:
        gpu_low = gpu.lower()
        if "nvidia" in gpu_low or "geforce" in gpu_low or "rtx" in gpu_low or "gtx" in gpu_low:
            gpu_accel = "CUDA (NVIDIA Acceleration)"
        elif "amd" in gpu_low or "radeon" in gpu_low or "intel" in gpu_low or "arc" in gpu_low:
            gpu_accel = "DirectML / Vulkan Acceleration"

    recommended = "Q4_K_M (7B)" if total_ram >= 12 else "Q4_K_S (3B/7B)"

    return HardwareInfoResponse(
        os_name=f"{os_sys} {platform.release()}",
        os_version=os_ver,
        cpu_cores_logical=cpu_cores,
        memory_total_gb=total_ram,
        memory_available_gb=avail_ram,
        gpu_name=gpu,
        gpu_acceleration=gpu_accel,
        recommended_profile=recommended,
        status="ok",
    )


@router.get("/models", response_model=ModelScanResponse, name="scan_installed_models")
async def scan_installed_models() -> ModelScanResponse:
    allow_map = get_allowlist_map()
    items: list[ModelItem] = []

    if MODELS_DIR.exists():
        for path in MODELS_DIR.rglob("*.gguf"):
            try:
                size_mb = round(path.stat().st_size / (1024 * 1024), 1)
            except OSError:
                size_mb = 0.0

            fn_low = path.name.lower()
            status = "unreviewed"
            for key, val in allow_map.items():
                if key in fn_low or key in str(path).lower():
                    status = val
                    break

            items.append(
                ModelItem(
                    name=path.stem,
                    filename=path.name,
                    path=str(path),
                    size_mb=size_mb,
                    allowlist_status=status,
                )
            )

    return ModelScanResponse(
        models_dir=str(MODELS_DIR),
        installed_models=items,
        count=len(items),
    )


@router.get("/sbom", response_model=SbomResponse, name="get_sbom")
async def get_sbom() -> SbomResponse:
    components = [
        SbomComponent(
            name="LumOS Core (FastAPI)",
            version=settings.version,
            license="MIT / Commercial Open-Source",
            purpose="Office Core Backend & Security Supervisor",
            status="approved",
        ),
        SbomComponent(
            name="Svelte + Vite Desktop UI",
            version="5.0.0",
            license="MIT",
            purpose="Floating AI Desktop User Interface",
            status="approved",
        ),
        SbomComponent(
            name="llama-server (llama.cpp)",
            version="b10375",
            license="MIT",
            purpose="Lokale GGUF LLM Inference Engine",
            status="quarantine",
        ),
        SbomComponent(
            name="Qwen2.5-7B-Instruct-GGUF",
            version="Q4_K_M",
            license="Qwen Research / Apache 2.0",
            purpose="Beleggestützte lokale Textgenerierung",
            status="candidate",
        ),
        SbomComponent(
            name="python-docx & reportlab",
            version="1.1 / 4.5",
            license="MIT / BSD",
            purpose="DIN 5008 Geschäftsbrief DOCX & PDF Export",
            status="approved",
        ),
        SbomComponent(
            name="SQLite Database",
            version="3.x",
            license="Public Domain",
            purpose="Autoritative lokale Daten- und Dokumentspeicherung",
            status="approved",
        ),
    ]

    response = SbomResponse(
        app_name=settings.app_name,
        version=settings.version,
        updated_at=datetime.now(UTC).strftime("%Y-%m-%d"),
        components=components,
    )

    # Save to docs/licenses/sbom.json
    try:
        SBOM_PATH.write_text(
            json.dumps(response.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("SBOM save fallback triggered: %s", exc)

    return response
