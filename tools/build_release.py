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
#   2. Compilação PyInstaller:
#      - Gera GUI/exe_version_info.txt (VSVersionInfo) → metadados em Propriedades → Detalhes
#      - Compila onefile/windowed com --version-file + --add-data (scripts embarcados)
#   2.5 README_TECNICO.md → metadados do build; incluído em todos os ZIPs; deletado após
#   3. ZIP RELEASE → C:\DESENV\PROJECT_RELEASE\ServiceControl_RELEASE-{ver}-{data}.zip
#      ZIP BACKUP  → C:\DESENV\PROJECT_BACKUP\ServiceControl_BACKUP-{ver}-{data}.zip
#
# Uso:
#   python tools/build_release.py
#   (ou via build_release.bat)
# ─────────────────────────────────────────────────────────────────────────────

import datetime
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# ─── Caminhos ────────────────────────────────────────────────────────────────
_TOOLS_DIR   = Path(__file__).resolve().parent   # Service-Control/tools/
_ROOT_DIR    = _TOOLS_DIR.parent                 # Service-Control/
_GUI_DIR     = _ROOT_DIR / "GUI"                 # Service-Control/GUI/
_MAIN_PY     = _GUI_DIR / "main.py"
_VERSION_TXT     = _GUI_DIR / "version_info.txt"
_EXE_VERSION_TXT = _GUI_DIR / "exe_version_info.txt"   # gerado pelo build — não versionar
_DIST_DIR        = _GUI_DIR / "dist"
_README_TECNICO  = _DIST_DIR / "README_TECNICO.md"    # temporário — incluído nos ZIPs, deletado após
_BUILD_DIR       = _GUI_DIR / "build"

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


# ─── README_TECNICO.md ─────────────────────────────────────────────────────────────────────
def _generate_readme_tecnico(version: str) -> None:
    """Gera README_TECNICO.md em dist/ com metadados do build.

    Obrigatório em todos os ZIPs (RELEASE e BACKUP) conforme padrão Quallit §8.
    Deletado na limpeza final junto com os demais artefatos temporários.
    """
    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    pv = sys.version_info
    py_ver = f"{pv.major}.{pv.minor}.{pv.micro}"

    pi_ver = "N/D"
    try:
        r = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True, text=True, timeout=10
        )
        raw = (r.stdout or r.stderr).strip()
        if raw:
            pi_ver = raw.splitlines()[-1].strip()
    except Exception:
        pass

    content = (
        "# Service Control — Informações Técnicas\n\n"
        "## Metadados do Build\n\n"
        "| Campo | Valor |\n"
        "|---|---|\n"
        "| **Aplicativo** | Service Control |\n"
        f"| **Versão** | {version} |\n"
        "| **Empresa** | Quallit |\n"
        f"| **Data do Build** | {now_str} |\n"
        f"| **Python** | {py_ver} |\n"
        f"| **PyInstaller** | {pi_ver} |\n"
        "| **Plataforma alvo** | Windows 10/11 x64 |\n\n"
        "## Assinatura Digital\n\n"
        "| Campo | Valor |\n"
        "|---|---|\n"
        "| **Status** | Não assinado |\n"
        "| **Certificado** | — |\n"
        "| **Thumbprint** | — |\n"
        "| **Timestamp** | — |\n\n"
        "---\n"
        f"*Gerado automaticamente em: {now_str}*\n"
    )

    _DIST_DIR.mkdir(parents=True, exist_ok=True)
    _README_TECNICO.write_text(content, encoding="utf-8")
    _ok(f"README_TECNICO.md gerado  ({_README_TECNICO.relative_to(_ROOT_DIR)})")


# ─── Metadados do executável (VSVersionInfo) ────────────────────────────────
def _generate_exe_version_file(version: str) -> None:
    """Gera exe_version_info.txt no formato VSVersionInfo do PyInstaller.

    O arquivo é lido por ``--version-file`` durante a compilação e embute os
    metadados visíveis em Propriedades → Detalhes do .exe no Windows Explorer.
    """
    parts = version.split(".")
    while len(parts) < 4:
        parts.append("0")
    v    = tuple(int(p) for p in parts[:4])
    year = datetime.datetime.now().year
    content = (
        "# -*- coding: utf-8 -*-\n"
        "# Gerado automaticamente por build_release.py — nao edite manualmente.\n"
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        f"    filevers=({v[0]}, {v[1]}, {v[2]}, {v[3]}),\n"
        f"    prodvers=({v[0]}, {v[1]}, {v[2]}, {v[3]}),\n"
        "    mask=0x3f,\n"
        "    flags=0x0,\n"
        "    OS=0x40004,\n"
        "    fileType=0x1,\n"
        "    subtype=0x0,\n"
        "    date=(0, 0)\n"
        "  ),\n"
        "  kids=[\n"
        "    StringFileInfo(\n"
        "      [StringTable(\n"
        "        u'041604B0',\n"
        "        [StringStruct(u'CompanyName', u'Quallit'),\n"
        "        StringStruct(u'FileDescription', u'Service Control'),\n"
        f"        StringStruct(u'FileVersion', u'{version}'),\n"
        "        StringStruct(u'InternalName', u'ServiceControl'),\n"
        f"        StringStruct(u'LegalCopyright', u'\\xa9 {year} Quallit. Todos os direitos reservados.'),\n"
        "        StringStruct(u'OriginalFilename', u'ServiceControl.exe'),\n"
        "        StringStruct(u'ProductName', u'Service Control'),\n"
        f"        StringStruct(u'ProductVersion', u'{version}')])]),\n"
        "    VarFileInfo([VarStruct(u'Translation', [0x0416, 1200])])\n"
        "  ]\n"
        ")\n"
    )
    _EXE_VERSION_TXT.write_text(content, encoding="utf-8")
    _ok(f"exe_version_info.txt gerado  ({version})")


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


# ─── Limpeza de artefatos ────────────────────────────────────────────────────
def _clean_artifacts() -> None:
    """Remove dist/ e build/ da pasta GUI para evitar artefatos de builds anteriores."""
    import time
    for target in (_DIST_DIR, _BUILD_DIR):
        if not target.exists():
            _info(f"Já limpo:  {target.relative_to(_ROOT_DIR)}")
            continue
        removed = False
        for attempt in range(1, 4):
            try:
                shutil.rmtree(target)
                _ok(f"Removido: {target.relative_to(_ROOT_DIR)}")
                removed = True
                break
            except PermissionError as exc:
                if attempt < 3:
                    _warn(f"Pasta em uso, aguardando... (tentativa {attempt}/3): {target.name}")
                    time.sleep(2)
                else:
                    raise SystemExit(
                        f"\n[ERR] Não foi possível remover '{target}'.\n"
                        f"      Feche o Explorer ou qualquer programa com essa pasta aberta e tente novamente.\n"
                        f"      Detalhe: {exc}"
                    ) from exc


# ─── Build ────────────────────────────────────────────────────────────────────
def _run_pyinstaller(version: str):
    _generate_exe_version_file(version)

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
        f"--version-file={_EXE_VERSION_TXT}",
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
    # Conteúdo: ServiceControl.exe + docs/README.md (manual) + README_TECNICO.md
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
            if _README_TECNICO.exists():
                zf.write(_README_TECNICO, "README_TECNICO.md")
                _ok("  + README_TECNICO.md")
            else:
                _warn("  README_TECNICO.md não encontrado — execute build completo")
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
            # README_TECNICO está em dist/ (excluído do rglob) — adiciona explicitamente
            if _README_TECNICO.exists():
                zf.write(_README_TECNICO, Path(_PROJ_NAME) / "README_TECNICO.md")
                _ok("  + README_TECNICO.md")
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

    # Limpeza inicial
    _banner("Limpeza inicial — artefatos anteriores")
    _clean_artifacts()

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

    # Etapa 2.5: README_TECNICO.md
    _banner("Etapa 2.5 — README_TECNICO.md")
    _generate_readme_tecnico(new_ver)

    # Etapa 3: ZIPs
    _banner("Etapa 3/3 — ZIPs Release e Backup")
    if not _generate_zips(new_ver):
        _warn("Um ou mais ZIPs não foram gerados. Verifique o log acima.")

    # Limpeza final
    _banner("Limpeza final — artefatos de build")
    if _BUILD_DIR.exists():
        shutil.rmtree(_BUILD_DIR)
        _ok(f"Removido: {_BUILD_DIR.relative_to(_ROOT_DIR)}")
    else:
        _info(f"Já limpo:  {_BUILD_DIR.relative_to(_ROOT_DIR)}")
    if _EXE_VERSION_TXT.exists():
        _EXE_VERSION_TXT.unlink()
        _ok(f"Removido: {_EXE_VERSION_TXT.relative_to(_ROOT_DIR)}")
    if _README_TECNICO.exists():
        _README_TECNICO.unlink()
        _ok(f"Removido: {_README_TECNICO.relative_to(_ROOT_DIR)}")

    _banner(f"Build concluído — v{new_ver}")


if __name__ == "__main__":
    main()
