#!/usr/bin/env python3
"""
janela_calendario.py
Janela flutuante de calendário (PyGTK3 — substitui yad --calendar/--paned).
Fecha ao perder foco ou pressionar Escape.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from collections import defaultdict

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Gdk  # noqa: E402

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PYTHON_BIN = str(SCRIPT_DIR / ".venv" / "bin" / "python")
if not pathlib.Path(PYTHON_BIN).exists():
    PYTHON_BIN = sys.executable
AGENDA_SCRIPT = str(SCRIPT_DIR / "google_agenda_polybar.py")

CSS = b"""
window {
    background-color: #1e1e2e;
}
.popup-box {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 8px;
}
.section {
    background-color: #313244;
    border-radius: 6px;
    margin: 4px 8px;
    padding: 4px 8px;
}
.section-title {
    color: #6c7086;
    font-size: 9pt;
    margin-bottom: 2px;
}
label {
    color: #cdd6f4;
}
button {
    background-color: #45475a;
    color: #cdd6f4;
    border: none;
    border-radius: 4px;
    padding: 2px 8px;
    min-height: 0;
}
button:hover { background-color: #585b70; }
button.close-btn {
    background-color: transparent;
    color: #6c7086;
    font-size: 9pt;
    margin: 2px 8px 6px 8px;
}
button.refresh-btn {
    background-color: #313244;
    color: #89b4fa;
    font-size: 9pt;
    margin: 2px 8px 0 8px;
}
.event-row {
    background-color: transparent;
    border-radius: 4px;
    padding: 2px 4px;
}
.event-row:hover { background-color: #45475a; }
.event-row label {
    color: #cdd6f4;
    font-size: 9pt;
}
.event-date {
    color: #89b4fa;
    font-size: 9pt;
    font-weight: bold;
}
calendar {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
calendar:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
}
"""


def _run_agenda(mode: str, extra: list[str] | None = None) -> str:
    cmd = [PYTHON_BIN, AGENDA_SCRIPT, "--mode", mode, "--cache-ttl", "1800"]
    if extra:
        cmd.extend(extra)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout
    except Exception:
        return ""


def _parse_details(raw: str) -> dict[str, list[str]]:
    """Formato: 'DD/MM/YYYY ev1 | ev2 | ...' → {YYYY-MM-DD: [ev1, ev2]}"""
    eventos: dict[str, list[str]] = defaultdict(list)
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        partes = line.split(" ", 1)
        if len(partes) < 2:
            continue
        data_str = partes[0]  # DD/MM/YYYY
        try:
            d, m, y = data_str.split("/")
            chave = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        except Exception:
            continue
        for ev in partes[1].split(" | "):
            ev = ev.strip()
            if ev:
                eventos[chave].append(ev)
    return dict(eventos)


def _parse_list7(raw: str) -> list[tuple[str, str]]:
    """Formato tab-sep: 'DD/MM \\t evento_curto \\t tooltip' → [(data, ev)]"""
    resultado = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            resultado.append((parts[0].strip(), parts[1].strip()))
    return resultado


class JanelaCalendario(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(type=Gtk.WindowType.POPUP)
        self._eventos: dict[str, list[str]] = {}
        self._vol_debounce_id: int | None = None

        self._apply_css()
        self._build()
        self._carregar_dados()
        self._posicionar()

        self.connect("key-press-event", self._on_key)
        self.connect("focus-out-event", self._on_focus_out)
        self.set_keep_above(True)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)

    def _apply_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build(self) -> None:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.get_style_context().add_class("popup-box")
        self.add(outer)

        title = Gtk.Label(label="  Calendário")
        title.set_xalign(0)
        title.set_margin_top(8)
        title.set_margin_start(8)
        title.get_style_context().add_class("section-title")
        outer.pack_start(title, False, False, 0)

        # Linha principal: calendário + eventos do dia
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer.pack_start(hbox, True, True, 0)

        # Calendário GTK
        cal_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        cal_section.get_style_context().add_class("section")
        hbox.pack_start(cal_section, False, False, 0)

        self._cal = Gtk.Calendar()
        self._cal.set_display_options(
            Gtk.CalendarDisplayOptions.SHOW_HEADING
            | Gtk.CalendarDisplayOptions.SHOW_DAY_NAMES
            | Gtk.CalendarDisplayOptions.SHOW_WEEK_NUMBERS
        )
        self._cal.connect("day-selected", self._on_day_selected)
        cal_section.pack_start(self._cal, False, False, 0)

        # Painel de eventos do dia selecionado
        day_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        day_section.get_style_context().add_class("section")
        day_section.set_size_request(260, -1)
        hbox.pack_start(day_section, True, True, 0)

        self._day_label = Gtk.Label(label="Selecione um dia")
        self._day_label.set_xalign(0)
        self._day_label.get_style_context().add_class("section-title")
        day_section.pack_start(self._day_label, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_size_request(-1, 200)
        day_section.pack_start(scroll, True, True, 0)

        self._day_list = Gtk.ListBox()
        self._day_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.add(self._day_list)

        # Lista de próximos 7 dias
        list7_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        list7_section.get_style_context().add_class("section")
        outer.pack_start(list7_section, False, False, 0)

        lbl7 = Gtk.Label(label="📅  Próximos eventos")
        lbl7.set_xalign(0)
        lbl7.get_style_context().add_class("section-title")
        list7_section.pack_start(lbl7, False, False, 0)

        scroll7 = Gtk.ScrolledWindow()
        scroll7.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll7.set_size_request(-1, 120)
        list7_section.pack_start(scroll7, False, False, 0)

        self._list7 = Gtk.ListBox()
        self._list7.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll7.add(self._list7)

        # Botões inferiores
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        outer.pack_start(btn_row, False, False, 0)

        refresh_btn = Gtk.Button(label="↻  Atualizar")
        refresh_btn.get_style_context().add_class("refresh-btn")
        refresh_btn.connect("clicked", lambda _: self._carregar_dados())
        btn_row.pack_start(refresh_btn, True, True, 0)

        close_btn = Gtk.Button(label="Fechar")
        close_btn.get_style_context().add_class("close-btn")
        close_btn.connect("clicked", lambda _: self.destroy())
        btn_row.pack_start(close_btn, False, False, 0)

    def _carregar_dados(self) -> None:
        raw_details = _run_agenda("details", ["--details-date-format", "%Y-%m-%d"])
        self._eventos = _parse_details(raw_details)

        # Marca dias com evento no calendário
        self._cal.clear_marks()
        ano, mes, _dia = self._cal.get_date()
        for chave in self._eventos:
            try:
                y, m, d = chave.split("-")
                if int(y) == ano and int(m) == mes + 1:
                    self._cal.mark_day(int(d))
            except Exception:
                pass

        # Popula lista de 7 dias
        raw_list7 = _run_agenda("list7", ["--list-max-len", "35"])
        eventos7 = _parse_list7(raw_list7)
        for child in self._list7.get_children():
            self._list7.remove(child)

        if not eventos7:
            row = Gtk.ListBoxRow()
            row.get_style_context().add_class("event-row")
            row.add(Gtk.Label(label="  Sem eventos nos próximos 7 dias"))
            self._list7.add(row)
        else:
            for data, evento in eventos7:
                row = Gtk.ListBoxRow()
                row.get_style_context().add_class("event-row")
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                lbl_data = Gtk.Label(label=data)
                lbl_data.get_style_context().add_class("event-date")
                lbl_data.set_size_request(40, -1)
                lbl_ev = Gtk.Label(label=evento)
                lbl_ev.set_xalign(0)
                hbox.pack_start(lbl_data, False, False, 0)
                hbox.pack_start(lbl_ev, True, True, 0)
                row.add(hbox)
                self._list7.add(row)

        self._list7.show_all()
        self._on_day_selected(self._cal)

    def _on_day_selected(self, cal: Gtk.Calendar) -> None:
        ano, mes, dia = cal.get_date()
        chave = f"{ano}-{str(mes + 1).zfill(2)}-{str(dia).zfill(2)}"
        self._day_label.set_text(f"📆  {dia:02d}/{mes + 1:02d}/{ano}")

        for child in self._day_list.get_children():
            self._day_list.remove(child)

        eventos_dia = self._eventos.get(chave, [])
        if not eventos_dia:
            row = Gtk.ListBoxRow()
            row.get_style_context().add_class("event-row")
            row.add(Gtk.Label(label="  Nenhum evento"))
            self._day_list.add(row)
        else:
            for ev in eventos_dia:
                row = Gtk.ListBoxRow()
                row.get_style_context().add_class("event-row")
                lbl = Gtk.Label(label=f"  • {ev}")
                lbl.set_xalign(0)
                row.add(lbl)
                self._day_list.add(row)

        self._day_list.show_all()

    def _on_key(self, _win, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def _on_focus_out(self, _win, _event) -> bool:
        self.destroy()
        return False

    def _posicionar(self) -> None:
        self.show_all()
        self.realize()

        display = Gdk.Display.get_default()
        seat = display.get_default_seat()
        pointer = seat.get_pointer()
        _screen, px, py = pointer.get_position()

        w, h = self.get_size()
        sw = display.get_default_screen().get_width()
        sh = display.get_default_screen().get_height()

        x = max(0, min(px - w // 2, sw - w - 4))
        y = py - h - 8
        if y < 0:
            y = py + 28

        self.move(x, y)


def main() -> None:
    import warnings
    warnings.filterwarnings("ignore")
    os.environ.setdefault("NO_AT_BRIDGE", "1")

    win = JanelaCalendario()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
