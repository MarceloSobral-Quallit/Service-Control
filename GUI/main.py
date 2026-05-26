# ─────────────────────────────────────────────────────────────────────────────
# Service Control  |  GUI  |  main.py
# Instalador grafico para gerenciamento dos controles de servico Windows.
#
# © Quallit — Projeto proprietário. Todos os direitos reservados.
# ─────────────────────────────────────────────────────────────────────────────

import ctypes
import datetime
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

# ─── Versão ──────────────────────────────────────────────────────────────────
APP_VERSION = "1.14.05.26"
APP_TITLE   = "Service Control — Instalador"

# ─── Caminhos base ────────────────────────────────────────────────────────────
# Quando compilado com PyInstaller --onefile, __file__ aponta para sys._MEIPASS
# (diretório de extração temporária), não para o .exe. Usar sys._MEIPASS garante
# que os scripts embarcados via --add-data sejam encontrados corretamente.
if getattr(sys, "frozen", False):
    _ROOT_DIR = Path(sys._MEIPASS)        # type: ignore[attr-defined]
    _EXE_DIR  = Path(sys.executable).resolve().parent
else:
    _ROOT_DIR = Path(__file__).resolve().parent.parent
    _EXE_DIR  = _ROOT_DIR
_PROG_DATA_BASE    = Path(r"C:\ProgramData\ServiceControl")
_START_MENU_FOLDER = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Service Control"
_GUI_LOG_FILE      = _EXE_DIR / "ServiceControl_log.txt"

# ─── Definição dos serviços ──────────────────────────────────────────────────
SERVICES = [
    {
        "label":       "VMware",
        "dir":         "VMWARE",
        "script":      "install-shortcuts.ps1",
        "toggle":      "vmware-toggle.ps1",
        "shortcuts":   ["VMware - Enable.lnk",
                        "VMware - Disable.lnk"],
    },
    {
        "label":       "Fortinet",
        "dir":         "FORTINET",
        "script":      "install-shortcuts.ps1",
        "toggle":      "fortinet-toggle.ps1",
        "shortcuts":   ["Fortinet - Enable.lnk",
                        "Fortinet - Disable.lnk"],
    },
    {
        "label":       "VirtualBox",
        "dir":         "VIRTUALBOX",
        "script":      "install-shortcuts.ps1",
        "toggle":      "virtualbox-toggle.ps1",
        "shortcuts":   ["VirtualBox - Enable.lnk",
                        "VirtualBox - Enable (sem abrir GUI).lnk",
                        "VirtualBox - Disable.lnk"],
    },
    {
        "label":       "OpenVPN",
        "dir":         "OPENVPN",
        "script":      "install-shortcuts.ps1",
        "toggle":      "openvpn-toggle.ps1",
        "shortcuts":   ["OpenVPN - Enable.lnk",
                        "OpenVPN - Disable.lnk"],
    },
]

# ─── Elevação de privilégio ───────────────────────────────────────────────────
def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def _elevate_and_exit():
    """Re-lança o processo atual com privilégios de administrador."""
    script = str(Path(sys.executable).resolve())
    # sys.argv[0] é o próprio exe quando frozen — passa apenas os args reais
    args   = " ".join(f'"{a}"' for a in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", script, args, None, 1)
    sys.exit(0)

# ─── Status de instalação ─────────────────────────────────────────────────────
def get_status(svc: dict) -> str:
    """Retorna: 'Instalado', 'Parcial (sem atalhos)' ou 'Não instalado'."""
    prog_dir    = _PROG_DATA_BASE / svc["dir"]
    toggle_file = prog_dir / svc["toggle"]
    scripts_ok  = toggle_file.exists()

    if not scripts_ok:
        return "Não instalado"

    has_lnk = any(
        (_START_MENU_FOLDER / lnk).exists()
        for lnk in svc["shortcuts"]
    )
    return "Instalado" if has_lnk else "Parcial (sem atalhos)"


# ═════════════════════════════════════════════════════════════════════════════
# Janela principal
# ═════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE}  v{APP_VERSION}")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")

        self._checks:    dict[str, tk.BooleanVar] = {}
        self._statuses:  dict[str, tk.StringVar]  = {}
        self._disable_now = tk.BooleanVar(value=False)
        self._procs:     list[subprocess.Popen]   = []

        self._build_ui()
        self._refresh_status()
        self._center()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._log_to_file(f"{'='*60}")
        self._log_to_file(f"Sessão iniciada — v{APP_VERSION}")
        self._log_to_file(f"{'='*60}")
        self._log_write(f"Service Control  v{APP_VERSION}", "info")

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # Cabeçalho
        tk.Label(
            self, text="  Service Control — Instalador  ",
            font=("Segoe UI", 13, "bold"),
            fg="#cdd6f4", bg="#313244"
        ).pack(fill="x", pady=(0, 2))

        # Painel de serviços
        frame_svc = tk.LabelFrame(
            self, text=" Serviços ", font=("Segoe UI", 9),
            fg="#89b4fa", bg="#1e1e2e", bd=1
        )
        frame_svc.pack(fill="x", **pad)

        for svc in SERVICES:
            row = tk.Frame(frame_svc, bg="#1e1e2e")
            row.pack(fill="x", padx=8, pady=3)

            var = tk.BooleanVar(value=False)
            self._checks[svc["label"]] = var

            tk.Checkbutton(
                row, text=f"  {svc['label']:<12}", variable=var,
                font=("Segoe UI", 10), fg="#cdd6f4", bg="#1e1e2e",
                selectcolor="#313244", activebackground="#1e1e2e",
                activeforeground="#cdd6f4", width=14, anchor="w"
            ).pack(side="left")

            status_var = tk.StringVar(value="...")
            self._statuses[svc["label"]] = status_var

            tk.Label(
                row, textvariable=status_var,
                font=("Segoe UI", 9), width=26, anchor="w",
                bg="#1e1e2e"
            ).pack(side="left")

        # Opção de primeira execução
        frame_opt = tk.Frame(self, bg="#1e1e2e")
        frame_opt.pack(fill="x", padx=12, pady=(0, 4))

        tk.Checkbutton(
            frame_opt, text="Desativar serviços imediatamente após instalar (1ª execução)",
            variable=self._disable_now,
            font=("Segoe UI", 9), fg="#f9e2af", bg="#1e1e2e",
            selectcolor="#313244", activebackground="#1e1e2e",
            activeforeground="#f9e2af"
        ).pack(anchor="w")

        # Botões de ação
        frame_btn = tk.Frame(self, bg="#1e1e2e")
        frame_btn.pack(fill="x", padx=12, pady=4)

        self._btn_install = tk.Button(
            frame_btn, text="  Instalar Selecionados  ",
            command=self._on_install,
            font=("Segoe UI", 10, "bold"),
            fg="#1e1e2e", bg="#a6e3a1", activebackground="#94d9a1",
            relief="flat", padx=8, pady=4, cursor="hand2"
        )
        self._btn_install.pack(side="left", padx=(0, 6))

        self._btn_uninstall = tk.Button(
            frame_btn, text="  Desinstalar Selecionados  ",
            command=self._on_uninstall,
            font=("Segoe UI", 10),
            fg="#1e1e2e", bg="#f38ba8", activebackground="#e07898",
            relief="flat", padx=8, pady=4, cursor="hand2"
        )
        self._btn_uninstall.pack(side="left", padx=(0, 6))

        tk.Button(
            frame_btn, text="  Limpar Legado  ",
            command=self._on_cleanup,
            font=("Segoe UI", 10),
            fg="#1e1e2e", bg="#cba6f7", activebackground="#b896e7",
            relief="flat", padx=8, pady=4, cursor="hand2"
        ).pack(side="left")

        tk.Button(
            frame_btn, text="  ✕  Fechar  ",
            command=self._on_close,
            font=("Segoe UI", 10),
            fg="#1e1e2e", bg="#f38ba8", activebackground="#e07898",
            relief="flat", padx=8, pady=4, cursor="hand2"
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            frame_btn, text="↺",
            command=self._refresh_status,
            font=("Segoe UI", 11),
            fg="#89b4fa", bg="#313244", activebackground="#45475a",
            relief="flat", padx=6, pady=4, cursor="hand2"
        ).pack(side="right")

        # Log de saída
        frame_log = tk.LabelFrame(
            self, text=" Saída ", font=("Segoe UI", 9),
            fg="#89b4fa", bg="#1e1e2e", bd=1
        )
        frame_log.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        self._log = tk.Text(
            frame_log, height=14, width=74,
            font=("Consolas", 9), fg="#cdd6f4", bg="#181825",
            insertbackground="#cdd6f4", relief="flat",
            state="disabled", wrap="word"
        )
        scroll = ttk.Scrollbar(frame_log, command=self._log.yview)
        self._log.configure(yscrollcommand=scroll.set)
        self._log.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scroll.pack(side="right", fill="y", pady=4)

        # Tags de cor no log
        self._log.tag_configure("ok",    foreground="#a6e3a1")
        self._log.tag_configure("err",   foreground="#f38ba8")
        self._log.tag_configure("warn",  foreground="#f9e2af")
        self._log.tag_configure("info",  foreground="#89b4fa")
        self._log.tag_configure("plain", foreground="#cdd6f4")

    # ── Utilitários de log ────────────────────────────────────────────────────
    def _log_to_file(self, text: str):
        """Grava linha no arquivo de log persistente."""
        try:
            _GUI_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with _GUI_LOG_FILE.open("a", encoding="utf-8") as fh:
                fh.write(f"{ts}  {text}\n")
        except Exception:
            pass

    def _log_write(self, text: str, tag: str = "plain"):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")
        if text.strip():
            self._log_to_file(text)

    def _log_clear(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._log_write(f"Service Control  v{APP_VERSION}", "info")

    # ── Status ────────────────────────────────────────────────────────────────
    def _refresh_status(self):
        for svc in SERVICES:
            s = get_status(svc)
            var = self._statuses[svc["label"]]
            if s == "Instalado":
                var.set(f"● {s}")
            elif s.startswith("Parcial"):
                var.set(f"◐ {s}")
            else:
                var.set(f"○ {s}")

            # Atualiza cor do label de status
            for widget in self.winfo_children():
                self._update_status_label_color(widget, svc["label"], s)

    def _update_status_label_color(self, parent, label, status):
        for w in parent.winfo_children():
            if isinstance(w, tk.Label):
                try:
                    if w.cget("textvariable") and \
                       str(w.cget("textvariable")) == str(self._statuses.get(label, "")):
                        color = ("#a6e3a1" if status == "Instalado"
                                 else "#f9e2af" if "Parcial" in status
                                 else "#6c7086")
                        w.configure(fg=color)
                except Exception:
                    pass
            if hasattr(w, "winfo_children"):
                self._update_status_label_color(w, label, status)

    # ── Seleção rápida ────────────────────────────────────────────────────────
    def _selected_services(self) -> list[dict]:
        return [svc for svc in SERVICES if self._checks[svc["label"]].get()]

    # ── Executar script PS ────────────────────────────────────────────────────
    def _run_ps_script(self, script_path: Path, extra_args: list[str] | None = None):
        """Executa um script PowerShell e envia a saída para o log."""
        # Usa -Command com força de encoding UTF-8 para que mensagens do sistema
        # Windows (Stop-Service, etc.) não saiam garbled (CP1252 vs UTF-8).
        ps_call = f'[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; & "{script_path}"'
        if extra_args:
            ps_call += " " + " ".join(extra_args)
        cmd = [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-Command", ps_call
        ]

        self._log_write(f"▶ {script_path.name}", "info")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._procs.append(proc)
            try:
                for line in proc.stdout:
                    line = line.rstrip()
                    if not line:
                        continue
                    tag = ("ok"   if any(k in line for k in ("OK", "Copiado", "Atalho", "criado", "Instalado", "Habilitado", "Disabled")) else
                           "err"  if any(k in line for k in ("ERRO", "Falha", "Error")) else
                           "warn" if any(k in line for k in ("Aviso", "Warn", "nao encontrado")) else
                           "plain")
                    self._log_write(f"  {line}", tag)
                proc.wait()
                if proc.returncode == 0:
                    self._log_write(f"  Concluído (código {proc.returncode})", "ok")
                else:
                    self._log_write(f"  Encerrou com código {proc.returncode}", "err")
            finally:
                self._procs.remove(proc)
        except Exception as exc:
            self._log_write(f"  Erro ao executar script: {exc}", "err")

    # ── Ações dos botões ──────────────────────────────────────────────────────
    def _set_buttons_state(self, state: str):
        self._btn_install.configure(state=state)
        self._btn_uninstall.configure(state=state)

    def _on_close(self):
        """Encerra processos PowerShell ativos antes de fechar a janela."""
        if self._procs:
            self._log_to_file(f"Fechando: encerrando {len(self._procs)} processo(s) ativo(s).")
            for proc in list(self._procs):
                try:
                    proc.terminate()
                except Exception:
                    pass
        self._log_to_file("Sessão encerrada.")
        self.destroy()

    def _on_install(self):
        selected = self._selected_services()
        if not selected:
            messagebox.showwarning("Seleção vazia", "Selecione ao menos um serviço.")
            return
        disable_now = self._disable_now.get()
        self._log_clear()
        self._set_buttons_state("disabled")

        def _worker():
            for svc in selected:
                script = _ROOT_DIR / svc["dir"] / svc["script"]
                args   = ["-DisableAllNow"] if disable_now else []
                self._run_ps_script(script, args)
                self._log_write("", "plain")
            self.after(0, self._refresh_status)
            self.after(0, lambda: self._set_buttons_state("normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_uninstall(self):
        selected = self._selected_services()
        if not selected:
            messagebox.showwarning("Seleção vazia", "Selecione ao menos um serviço.")
            return
        labels = ", ".join(s["label"] for s in selected)
        if not messagebox.askyesno("Confirmar", f"Desinstalar atalhos de:\n{labels}?"):
            return
        self._log_clear()
        self._set_buttons_state("disabled")

        def _worker():
            for svc in selected:
                # Restaura o tipo de inicialização dos serviços para o padrão
                # (Manual) antes de remover os atalhos de gerenciamento.
                toggle = _PROG_DATA_BASE / svc["dir"] / svc["toggle"]
                if toggle.exists():
                    self._log_write(f"▶ Restaurando inicialização: {svc['label']}", "info")
                    self._run_ps_script(toggle, ["-Mode", "Enable"])
                else:
                    self._log_write(
                        f"  {svc['label']}: script não encontrado em ProgramData "
                        f"— serviços não serão restaurados.", "warn"
                    )
                self._log_write(f"▶ Removendo atalhos: {svc['label']}", "warn")
                self._remove_shortcuts_for(svc)
                self._remove_progdata_dir(svc)
                self._log_write("", "plain")
            # Remove o diretório base se ficou vazio
            self._remove_progdata_base_if_empty()
            self.after(0, self._refresh_status)
            self.after(0, lambda: self._set_buttons_state("normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _remove_shortcuts_for(self, svc: dict):
        """Remove os atalhos do Menu Iniciar para um serviço."""
        if not _START_MENU_FOLDER.exists():
            self._log_write(f"  Pasta Service Control não encontrada.", "warn")
            return
        removed = 0
        # Remove todos os .lnk que começam com o label do serviço
        pattern = f"{svc['label']} - "
        for f in _START_MENU_FOLDER.glob("*.lnk"):
            if f.name.startswith(pattern):
                try:
                    f.unlink()
                    self._log_write(f"  Removido: {f.name}", "ok")
                    removed += 1
                except Exception as exc:
                    self._log_write(f"  Erro: {f.name} — {exc}", "err")
        if removed == 0:
            self._log_write(f"  Nenhum atalho encontrado para {svc['label']}.", "warn")

    def _remove_progdata_dir(self, svc: dict):
        """Remove C:\\ProgramData\\ServiceControl\\<dir> do serviço."""
        prog_dir = _PROG_DATA_BASE / svc["dir"]
        if not prog_dir.exists():
            self._log_write(f"  ProgramData\\{svc['dir']}: não encontrado.", "warn")
            return
        try:
            shutil.rmtree(str(prog_dir))
            self._log_write(f"  Removido: ProgramData\\ServiceControl\\{svc['dir']}", "ok")
        except Exception as exc:
            self._log_write(f"  Erro ao remover ProgramData\\{svc['dir']}: {exc}", "err")

    def _remove_progdata_base_if_empty(self):
        """Remove C:\\ProgramData\\ServiceControl se não houver mais subpastas."""
        if not _PROG_DATA_BASE.exists():
            return
        remaining = [p for p in _PROG_DATA_BASE.iterdir() if p.is_dir()]
        if remaining:
            self._log_write(
                f"  ProgramData\\ServiceControl mantido "
                f"({len(remaining)} serviço(s) ainda instalado(s)).", "info"
            )
            return
        try:
            shutil.rmtree(str(_PROG_DATA_BASE))
            self._log_write("  Removido: ProgramData\\ServiceControl", "ok")
        except Exception as exc:
            self._log_write(f"  Erro ao remover ProgramData\\ServiceControl: {exc}", "err")

    def _on_cleanup(self):
        self._log_clear()
        self._log_write("▶ Verificando legado (MateWeb e caminhos antigos)...", "info")
        self._set_buttons_state("disabled")

        def _worker():
            self._check_mateweb()
            self._check_old_paths()
            self.after(0, self._refresh_status)
            self.after(0, lambda: self._set_buttons_state("normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _check_mateweb(self):
        appdata = os.environ.get("APPDATA", "")
        mw = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "MateWeb"
        if not mw.exists():
            self._log_write("  MateWeb: não encontrado.", "ok")
            return
        lnks = list(mw.rglob("*.lnk"))
        self._log_write(f"  MateWeb: {len(lnks)} atalho(s) encontrado(s) em {mw}", "warn")
        for f in lnks:
            self._log_write(f"    {f.name}", "plain")
        answer = messagebox.askyesno(
            "Remover MateWeb",
            f"Encontrados {len(lnks)} atalho(s) na pasta MateWeb (legado).\nRemover tudo?"
        )
        if answer:
            try:
                shutil.rmtree(str(mw))
                self._log_write("  MateWeb removido.", "ok")
            except Exception as exc:
                self._log_write(f"  Erro ao remover MateWeb: {exc}", "err")
        else:
            self._log_write("  MateWeb: operação cancelada.", "warn")

    def _check_old_paths(self):
        if not _START_MENU_FOLDER.exists():
            self._log_write("  Pasta Service Control não existe — nada a verificar.", "warn")
            return
        old_markers = [r"C:\DESENV\_SCRIPTS", r"C:\DESENV\PROJECT_DESENV"]
        broken: list[Path] = []
        for lnk in _START_MENU_FOLDER.glob("*.lnk"):
            content = lnk.read_bytes()
            for marker in old_markers:
                if marker.encode("utf-16-le") in content:
                    broken.append(lnk)
                    break
        if not broken:
            self._log_write("  Nenhum atalho com caminho antigo (DESENV).", "ok")
            return
        self._log_write(f"  {len(broken)} atalho(s) com caminho legado:", "warn")
        for f in broken:
            self._log_write(f"    {f.name}", "plain")
        answer = messagebox.askyesno(
            "Atalhos legados",
            f"{len(broken)} atalho(s) apontam para caminhos antigos (DESENV).\nRemover?"
        )
        if answer:
            for f in broken:
                try:
                    f.unlink()
                    self._log_write(f"  Removido: {f.name}", "ok")
                except Exception as exc:
                    self._log_write(f"  Erro: {f.name} — {exc}", "err")
        else:
            self._log_write("  Atalhos legados: operação cancelada.", "warn")

    # ── Centralizar janela ────────────────────────────────────────────────────
    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


# ═════════════════════════════════════════════════════════════════════════════
# Ponto de entrada
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not _is_admin():
        if messagebox.askyesno(
            "Privilégios necessários",
            "Este aplicativo precisa de privilégios de administrador.\n\nElevar agora?"
        ):
            _elevate_and_exit()
        else:
            sys.exit(0)

    app = App()
    app.mainloop()
