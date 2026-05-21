#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────────────────────
# Service Control  |  Tools / Git  |  github_sync.py
# Sincronizacao com GitHub. Usa apenas biblioteca padrao do Python.
#
# Uso:
#   python tools/git/github_sync.py
#   python tools/git/github_sync.py --no-push | --rebuild-git | --dry-run
#
# Configuracao: tools/git/github_sync.ini
#   Copie github_sync.ini.example para github_sync.ini e ajuste os valores.
#
# © Quallit — Projeto proprietário. Todos os direitos reservados.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import configparser
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent
# Raiz do repositório (tools/git/ → dois níveis acima)
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CONFIG_FILE  = SCRIPT_DIR / "github_sync.ini"

# ---------------------------------------------------------------------------
# Leitura de configuração
# ---------------------------------------------------------------------------
_cfg = configparser.ConfigParser()
_cfg.read(CONFIG_FILE, encoding="utf-8")


def _c(key: str, fallback: str = "") -> str:
    return _cfg.get("git", key, fallback=fallback).strip()


def _project_from_remote(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"github\.com/[^/\s]+/([^/\s]+?)(?:\.git)?$", url, re.I)
    return m.group(1) if m else ""


REMOTE                 = _c("remote")
BRANCH                 = _c("branch")  or "main"
USER_NAME              = _c("username")
USER_EMAIL             = _c("email")
PROJECT_LABEL          = _c("project") or _project_from_remote(REMOTE) or PROJECT_ROOT.name
DEFAULT_COMMIT_MESSAGE = _c("default_commit_message")

# ---------------------------------------------------------------------------
# Versao do projeto (lida de version_info.txt)
# ---------------------------------------------------------------------------

def _read_project_version() -> str:
    ver_file = PROJECT_ROOT / "version_info.txt"
    if not ver_file.is_file():
        return ""
    try:
        # utf-8-sig descarta o BOM (EF BB BF) se presente — necessário quando
        # o arquivo foi gravado por ferramentas .NET/PowerShell com Encoding.UTF8
        for line in ver_file.read_text(encoding="utf-8-sig").splitlines():
            m = re.match(r"Versao:\s*(.+)", line.strip())
            if m:
                return m.group(1).strip()
    except OSError:
        pass
    return ""

APP_VERSION = _read_project_version()

# Ambiente limpo para git
_GIT_ENV = os.environ.copy()
for _k in ("GIT_TRACE", "GIT_TRACE_PERFORMANCE", "GIT_TRACE_SETUP"):
    _GIT_ENV.setdefault(_k, "0")

# ---------------------------------------------------------------------------
# Helpers de log e cor
# ---------------------------------------------------------------------------
_IS_WIN = sys.platform == "win32"
if _IS_WIN:
    os.system("")  # habilita ANSI no Windows


class _C:
    R      = "\033[0m"
    GREEN  = "\033[92m"
    CYAN   = "\033[96m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    BOLD   = "\033[1m"


def _log(msg: str, level: str = "INFO") -> None:
    tag = {
        "INFO":  f"{_C.CYAN}[INFO ]{_C.R}",
        "OK":    f"{_C.GREEN}[OK   ]{_C.R}",
        "WARN":  f"{_C.YELLOW}[AVISO]{_C.R}",
        "ERROR": f"{_C.RED}[FALHA]{_C.R}",
    }.get(level, f"[{level}]")
    print(f"  {tag} {msg}")


def _short(url: str) -> str:
    if not url:
        return "(sem remote)"
    m = re.search(r"[:/]([^/\s]+/[^/\s]+?)(?:\.git)?$", url)
    return m.group(1) if m else url

# ---------------------------------------------------------------------------
# Wrappers git
# ---------------------------------------------------------------------------

def _git(args: list, *, capture: bool = False,
         check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(PROJECT_ROOT),
        capture_output=capture,
        text=True,
        env=_GIT_ENV,
        check=check,
    )

# ---------------------------------------------------------------------------
# Operações
# ---------------------------------------------------------------------------

def _ensure_repo() -> None:
    if not (PROJECT_ROOT / ".git").exists():
        _log("Inicializando repositorio git...", "INFO")
        _git(["init"], check=True)
        _git(["branch", "-M", BRANCH])

    if _IS_WIN:
        _git(["config", "credential.helper", "manager"])

    existing_name  = _git(["config", "--get", "user.name"],  capture=True).stdout.strip()
    existing_email = _git(["config", "--get", "user.email"], capture=True).stdout.strip()

    if not existing_name:
        if USER_NAME:
            _git(["config", "user.name", USER_NAME])
            _log(f"user.name = {USER_NAME}", "INFO")
        else:
            _log("user.name nao configurado em github_sync.ini → [git] username", "WARN")

    if not existing_email:
        if USER_EMAIL:
            _git(["config", "user.email", USER_EMAIL])
            _log(f"user.email = {USER_EMAIL}", "INFO")
        else:
            _log("user.email nao configurado em github_sync.ini → [git] email", "WARN")


def _ensure_remote() -> None:
    if not REMOTE:
        _log("Remote nao configurado em github_sync.ini → [git] remote", "WARN")
        return
    has = _git(["remote", "get-url", "origin"], capture=True).returncode == 0
    if not has:
        _log(f"Adicionando remote origin: {_short(REMOTE)}", "INFO")
        _git(["remote", "add", "origin", REMOTE])
    else:
        current = _git(["remote", "get-url", "origin"], capture=True).stdout.strip()
        if current != REMOTE:
            _log(f"Atualizando remote origin: {_short(REMOTE)}", "INFO")
            _git(["remote", "set-url", "origin", REMOTE])


def _has_changes() -> bool:
    return bool(_git(["status", "--porcelain"], capture=True).stdout.strip())


def _commit(message: str) -> bool:
    _git(["add", "-A"], check=True)
    r = _git(["commit", "-m", message], capture=True)
    if r.returncode == 0:
        _log("Commit criado.", "OK")
        return True
    out = (r.stdout + r.stderr).strip()
    if "nothing to commit" in out:
        _log("Nada para commitar.", "INFO")
    else:
        _log(f"git commit: {out}", "WARN")
    return False


def _push() -> bool:
    if not REMOTE:
        _log("Push ignorado: remote nao configurado.", "WARN")
        return False
    _log(f"Enviando para {_short(REMOTE)} ({BRANCH})...", "INFO")
    r = _git(["push", "-u", "origin", BRANCH], capture=True)
    if r.returncode == 0:
        _log(f"Push para {_short(REMOTE)} concluido.", "OK")
        return True
    _log(f"Push falhou: {(r.stdout + r.stderr).strip()}", "WARN")
    _log("Verifique credenciais (Git Credential Manager) e permissoes.", "WARN")
    return False

# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------

def sync(message: str, *, no_push: bool, dry_run: bool) -> None:
    _ensure_repo()
    _ensure_remote()

    if not _has_changes():
        _log("Nenhuma alteracao pendente. Tudo sincronizado.", "OK")
        return

    if dry_run:
        lines = _git(["status", "--short"], capture=True).stdout.strip().splitlines()
        _log("Arquivos que seriam commitados:", "INFO")
        for line in lines:
            print(f"        {line}")
        _log("Dry-run: nenhuma acao executada.", "WARN")
        return

    if not _commit(message):
        return

    if no_push:
        _log("Commit criado localmente. Push ignorado (--no-push).", "INFO")
    else:
        _push()


def rebuild_git(message: str, *, dry_run: bool) -> None:
    if dry_run:
        _log("Dry-run: --rebuild-git nao executado.", "WARN")
        return
    if not REMOTE:
        _log("--rebuild-git requer [git] remote configurado em github_sync.ini.", "ERROR")
        return

    _log("Zerando historico local e recriando repositorio...", "WARN")
    git_dir = PROJECT_ROOT / ".git"
    if git_dir.exists():
        try:
            shutil.rmtree(git_dir)
            _log(".git removido.", "INFO")
        except Exception as exc:
            _log(f"Falha ao remover .git: {exc}", "ERROR")
            return

    _git(["init"], check=True)
    _git(["branch", "-M", BRANCH])
    if _IS_WIN:
        _git(["config", "credential.helper", "manager"])
    if USER_NAME:
        _git(["config", "user.name",  USER_NAME])
    if USER_EMAIL:
        _git(["config", "user.email", USER_EMAIL])

    _git(["add", "-A"], check=True)
    r = _git(["commit", "-m", message], capture=True)
    if r.returncode != 0:
        _log(f"Falha no commit: {(r.stdout + r.stderr).strip()}", "ERROR")
        return
    _log("Commit inicial criado.", "OK")

    _git(["remote", "add", "origin", REMOTE])
    _log(f"Force-push para {_short(REMOTE)} ({BRANCH})...", "INFO")
    p = _git(["push", "-u", "origin", BRANCH, "--force"], capture=True)
    if p.returncode == 0:
        _log("Force-push concluido.", "OK")
    else:
        _log(f"Force-push falhou: {(p.stdout + p.stderr).strip()}", "WARN")

# ---------------------------------------------------------------------------
# Prompt interativo
# ---------------------------------------------------------------------------

def _default_message_if_blank() -> str:
    if DEFAULT_COMMIT_MESSAGE:
        return DEFAULT_COMMIT_MESSAGE
    ver  = APP_VERSION or "0.0.00.00"
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{PROJECT_LABEL} - Version {ver} - Build {ts}"


def _prompt_message():
    """Exibe prompt para descricao das alteracoes. Retorna None se cancelado."""
    print()
    print(f"  {_C.BOLD}Descricao das alteracoes{_C.R}")
    if DEFAULT_COMMIT_MESSAGE:
        hint = f"Enter para usar: {_C.BOLD}{DEFAULT_COMMIT_MESSAGE}{_C.R}"
    else:
        hint = f"Enter para timestamp automatico ({PROJECT_LABEL} - sync ...)"
    print(f"  {_C.CYAN}({hint} | 'q' para cancelar){_C.R}")
    print()
    try:
        answer = input("  > ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return None

    if answer.lower() in ("q", "quit", "exit", "cancelar"):
        return None

    if not answer:
        return _default_message_if_blank()

    return answer

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincronizacao com GitHub — Service Control."
    )
    parser.add_argument("--no-push",      action="store_true",
                        help="Commit local sem push.")
    parser.add_argument("--rebuild-git",  action="store_true",
                        help="Zera historico e faz force-push.")
    parser.add_argument("--dry-run",      action="store_true",
                        help="Mostra o que seria feito, sem executar.")
    args = parser.parse_args()

    if not CONFIG_FILE.exists():
        print(f"\n  {_C.RED}[FALHA]{_C.R} github_sync.ini nao encontrado em: {CONFIG_FILE}")
        print(f"  Copie github_sync.ini.example para github_sync.ini e ajuste os valores.")
        sys.exit(1)

    print()
    print("=" * 56)
    print(f"  {_C.BOLD}{PROJECT_LABEL}{_C.R} — sincronizacao GitHub")
    print("=" * 56)
    print(f"  Projeto : {PROJECT_ROOT}")
    print(f"  Remote  : {_short(REMOTE)}")
    print(f"  Branch  : {BRANCH}")
    if args.dry_run:
        print(f"  {_C.YELLOW}Modo    : DRY-RUN{_C.R}")
    elif args.rebuild_git:
        print(f"  {_C.YELLOW}Modo    : REBUILD-GIT (force-push){_C.R}")
    elif args.no_push:
        print(f"  Modo    : NO-PUSH (somente commit local)")

    if args.dry_run:
        message = _default_message_if_blank()
    else:
        message = _prompt_message()
        if message is None:
            print()
            _log("Operacao cancelada pelo usuario.", "WARN")
            print()
            return

    print()
    _log(f'Commit: "{message}"', "INFO")
    print()

    os.chdir(PROJECT_ROOT)

    if args.rebuild_git:
        rebuild_git(message, dry_run=args.dry_run)
    else:
        sync(message, no_push=args.no_push, dry_run=args.dry_run)

    print()
    print("=" * 56)
    print()


if __name__ == "__main__":
    main()
