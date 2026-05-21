#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────────────────────
# Service Control  |  Tools  |  build_release.py
# Pipeline de build PyInstaller — gera o executavel ServiceControl.exe.
#
# © Quallit — Projeto proprietário. Todos os direitos reservados.
# ─────────────────────────────────────────────────────────────────────────────
#
# Etapas:
#   0. Verificação de encoding (.ps1 com não-ASCII sem UTF-8 BOM → aviso)
#   1. Bump de versão (Minor + MM/YY) + sync em README.md e docs/
#   2. Compilação PyInstaller (onefile, windowed, scripts embarcados via --add-data)
#   3. ZIP RELEASE → C:\DESENV\PROJECT_RELEASE\ServiceControl_RELEASE-{ver}-{data}.zip
#      ZIP BACKUP  → C:\DESENV\PROJECT_BACKUP\ServiceControl_BACKUP-{ver}-{data}.zip
#
# Uso:
#   python tools/build_release.py
#   (ou via build_release.bat)
# ─────────────────────────────────────────────────────────────────────────────

import datetime
import re
import subprocess
import sys
import zipfile
from pathlib import Path

# ─── Caminhos ────────────────────────────────────────────────────────────────
_TOOLS_DIR   = Path(__file__).resolve().parent   # Service-Control/tools/
_ROOT_DIR    = _TOOLS_DIR.parent                 # Service-Control/
_GUI_DIR     = _ROOT_DIR / "GUI"                 # Service-Control/GUI/
_MAIN_PY     = _GUI_DIR / "main.py"
_VERSION_TXT = _GUI_DIR / "version_info.txt"
_DIST_DIR    = _GUI_DIR / "dist"
_BUILD_DIR   = _GUI_DIR / "build"

APP_NAME = "ServiceControl"

# Pastas de serviço a embarcar no executável via --add-data.
# Cada pasta é extraída em sys._MEIPASS/<nome> em tempo de execução.
_SERVICE_DIRS = ["VMWARE", "FORTINET", "VIRTUALBOX", "OPENVPN"]

# ─── Constantes de ZIP ───────────────────────────────────────────────────────
_PROJ_NAME   = "ServiceControl"
_RELEASE_DIR = Path(r"C:\DESENV\PROJECT_RELEASE")
_BACKUP_DIR  = Path(r"C:\DESENV\PROJECT_BACKUP")

_BACKUP_EXCLUDE_DIRS  = {
    "dist", "build", "__pycache__", ".specstory", ".git",
    ".vs", ".idea", "temp", "logs",
}
_BACKUP_EXCLUDE_EXTS  = {".pyc", ".pyo", ".spec", ".log", ".tmp", ".pfx", ".p12", ".cer"}
_BACKUP_EXCLUDE_FILES = {"tools\\git\\github_sync.ini"}


# ─── Encoding check ─────────────────────────────────────────────────────────
def _check_encoding() -> None:
    """Etapa 0 — Avisa sobre .ps1 com não-ASCII sem UTF-8 BOM (PS 5.1 leria errado)."""
    UTF8_BOM = b"\xef\xbb\xbf"
    issues: list[str] = []
    for ps1 in _ROOT_DIR.rglob("*.ps1"):
        raw = ps1.read_bytes()
        if any(b > 0x7F for b in raw) and not raw.startswith(UTF8_BOM):
            issues.append(str(ps1.relative_to(_ROOT_DIR)))
    if issues:
        _warn("Arquivo(s) .ps1 com não-ASCII sem UTF-8 BOM — PS 5.1 pode ler errado:")
        for f in issues:
            _warn(f"  {f}")
        _warn("  Corrija: VS Code → botão de encoding (rodapé) → 'Save with Encoding' → UTF-8 with BOM")
    else:
        _ok("Encoding .ps1: OK")


# ─── Versionamento ───────────────────────────────────────────────────────────
def _read_version() -> str:
    if not _VERSION_TXT.exists():
        return "1.00.05.26"
    for line in _VERSION_TXT.read_text(encoding="utf-8").splitlines():
        if line.startswith("Versao:"):
            return line.split(":", 1)[1].strip()
    return "1.00.05.26"


def _bump_version(current: str) -> str:
    """Incrementa Minor e atualiza MM/YY para hoje."""
    now   = datetime.datetime.now()
    parts = current.split(".")
    while len(parts) < 4:
        parts.append("0")
    parts[1] = f"{int(parts[1]) + 1:02d}"
    parts[2] = f"{now.month:02d}"
    parts[3] = now.strftime("%y")
    return ".".join(parts)


def _sync_version_in_file(path: Path, pattern: str, replacement: str) -> None:
    """Aplica re.sub no arquivo e grava se houve alteração."""
    if not path.exists():
        _warn(f"  Sync: arquivo não encontrado — {path.name}")
        return
    src = path.read_text(encoding="utf-8")
    new = re.sub(pattern, replacement, src)
    if new != src:
        path.write_text(new, encoding="utf-8")
        _ok(f"  Sync: {path.relative_to(_ROOT_DIR)}")
    else:
        _info(f"  Sem alteração: {path.relative_to(_ROOT_DIR)}")


def _write_version(version: str):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    # Atualiza GUI/version_info.txt (fonte primária do build)
    _VERSION_TXT.write_text(
        f"Versao: {version}\nAtualizado em: {now}\n",
        encoding="utf-8"
    )
    # Mantém version_info.txt raiz em sincronia (lido pelo github_sync.py)
    (_ROOT_DIR / "version_info.txt").write_text(
        f"Versao: {version}\nAtualizado em: {now}\n",
        encoding="utf-8"
    )
    # APP_VERSION em main.py
    _sync_version_in_file(
        _MAIN_PY,
        r'APP_VERSION\s*=\s*"[^"]+"',
        f'APP_VERSION = "{version}"',
    )
    # Badge de versão no README.md da raiz
    _sync_version_in_file(
        _ROOT_DIR / "README.md",
        r"(badge/vers[aã]o-)[\d.]+(-blue)",
        f"\\g<1>{version}\\g<2>",
    )
    # Linha **Versão:** em todos os docs/
    _ver_doc_pattern = r"(?<=\*\*Versão:\*\* )[\d.]+"
    for doc in ("README.md", "DEV_PLAYBOOK.md", "INDEX.md"):
        _sync_version_in_file(_ROOT_DIR / "docs" / doc, _ver_doc_pattern, version)


# ─── Helpers de console ──────────────────────────────────────────────────────
_C_CYAN   = "\033[96m"
_C_GREEN  = "\033[92m"
_C_YELLOW = "\033[93m"
_C_RED    = "\033[91m"
_C_RESET  = "\033[0m"
_C_BOLD   = "\033[1m"


def _banner(msg: str):
    sep = "=" * 70
    print(f"\n{_C_CYAN}{_C_BOLD}{sep}")
    print(f"  {msg}")
    print(f"{sep}{_C_RESET}")


def _ok(msg: str):    print(f"  {_C_GREEN}[OK]{_C_RESET}  {msg}")
def _info(msg: str):  print(f"  {_C_CYAN}[..]{_C_RESET}  {msg}")
def _warn(msg: str):  print(f"  {_C_YELLOW}[!!]{_C_RESET}  {msg}")
def _err(msg: str):   print(f"  {_C_RED}[ERR]{_C_RESET} {msg}")


# ─── Build ────────────────────────────────────────────────────────────────────
def _run_pyinstaller(version: str):
    icon_arg = []
    icon_file = _GUI_DIR / "assets" / "icon.ico"
    if icon_file.exists():
        icon_arg = [f"--icon={icon_file}"]

    # Embarcar cada pasta de serviço no bundle.
    # PyInstaller 6.0+ aceita ':' como separador universal (inclusive no Windows
    # com drive letter — ex: C:\path\VMWARE:VMWARE — tratado corretamente).
    data_args: list[str] = []
    for svc_dir in _SERVICE_DIRS:
        src = _ROOT_DIR / svc_dir
        if src.exists():
            data_args += ["--add-data", f"{src}:{svc_dir}"]
            _info(f"  Embarcando: {svc_dir}/")
        else:
            _warn(f"  Pasta não encontrada — ignorada: {src}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        f"--distpath={_DIST_DIR}",
        f"--workpath={_BUILD_DIR}",
        "--noconfirm",
        "--clean",
        *icon_arg,
        *data_args,
        str(_MAIN_PY),
    ]
    _info(f"Comando: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(_GUI_DIR))
    return result.returncode == 0


# ─── ZIPs de Release e Backup ────────────────────────────────────────────────
def _generate_zips(version: str) -> bool:
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    success  = True

    for d in (_RELEASE_DIR, _BACKUP_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # ── ZIP RELEASE ──────────────────────────────────────────────────────────
    # Conteúdo: ServiceControl.exe + docs/README.md (manual entregue ao usuário)
    release_zip = _RELEASE_DIR / f"{_PROJ_NAME}_RELEASE-{version}-{date_str}.zip"
    _info(f"Destino RELEASE: {release_zip}")
    try:
        release_zip.unlink(missing_ok=True)
        with zipfile.ZipFile(release_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            exe_src = _DIST_DIR / f"{APP_NAME}.exe"
            if exe_src.exists():
                zf.write(exe_src, f"{APP_NAME}.exe")
                _ok(f"  + {APP_NAME}.exe")
            else:
                _warn(f"  Executável não encontrado: {exe_src.name}")
            manual_src = _ROOT_DIR / "docs" / "README.md"
            if manual_src.exists():
                zf.write(manual_src, "README.md")
                _ok("  + README.md  (Manual de Uso)")
            else:
                _warn(f"  Manual não encontrado: {manual_src}")
        sz = round(release_zip.stat().st_size / (1024 ** 2), 1)
        _ok(f"{release_zip.name}  ({sz} MB)")
    except Exception as exc:
        _err(f"Falha no RELEASE ZIP: {exc}")
        success = False

    # ── ZIP BACKUP ───────────────────────────────────────────────────────────
    # Conteúdo: código-fonte completo sem artefatos de build
    backup_zip = _BACKUP_DIR / f"{_PROJ_NAME}_BACKUP-{version}-{date_str}.zip"
    _info(f"Destino BACKUP:  {backup_zip}")
    try:
        backup_zip.unlink(missing_ok=True)
        count = 0
        with zipfile.ZipFile(backup_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in _ROOT_DIR.rglob("*"):
                if not file.is_file():
                    continue
                rel   = file.relative_to(_ROOT_DIR)
                parts = rel.parts
                if any(p.lower() in _BACKUP_EXCLUDE_DIRS for p in parts[:-1]):
                    continue
                if file.suffix.lower() in _BACKUP_EXCLUDE_EXTS:
                    continue
                if str(rel).replace("/", "\\") in _BACKUP_EXCLUDE_FILES:
                    continue
                zf.write(file, Path(_PROJ_NAME) / rel)
                count += 1
        sz = round(backup_zip.stat().st_size / (1024 ** 2), 1)
        _ok(f"{backup_zip.name}  ({sz} MB)  — {count} arquivo(s)")
    except Exception as exc:
        _err(f"Falha no BACKUP ZIP: {exc}")
        success = False

    return success


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    _banner("Service Control — Build Release")

    # Etapa 0: Verificação de encoding
    _banner("Etapa 0/3 — Encoding")
    _check_encoding()

    # Etapa 1: Bump versão + sync em README.md e docs/
    _banner("Etapa 1/3 — Versão")
    current = _read_version()
    new_ver = _bump_version(current)
    _write_version(new_ver)
    _ok(f"{current}  →  {new_ver}")

    # Etapa 2: Compilar
    _banner("Etapa 2/3 — PyInstaller")
    _info(f"Saída: {_DIST_DIR / APP_NAME}.exe")

    if not _run_pyinstaller(new_ver):
        _err("Build falhou.")
        sys.exit(1)

    exe = _DIST_DIR / f"{APP_NAME}.exe"
    if exe.exists():
        size_kb = exe.stat().st_size // 1024
        _ok(f"Executável gerado: {exe}  ({size_kb} KB)")
    else:
        _warn("Executável não encontrado no caminho esperado — verifique o log acima.")

    # Etapa 3: ZIPs
    _banner("Etapa 3/3 — ZIPs Release e Backup")
    if not _generate_zips(new_ver):
        _warn("Um ou mais ZIPs não foram gerados. Verifique o log acima.")

    _banner(f"Build concluído — v{new_ver}")


if __name__ == "__main__":
    main()
