"""
==============================================================================
TESIS UNI - INTERFAZ DE CONFIGURACIÓN DE RED Y ENLACE DE VUELO (DJI AIR 2S)
Módulo gráfico interactivo para gestión y persistencia de direcciones IP:
- Recuerda y guarda automáticamente la ÚLTIMA IP utilizada en cada sesión.
- Muestra claramente la IP de la Tablet y de la Laptop de la sesión anterior.
- Permite continuar con un solo clic/Enter con las IPs ya guardadas.
- Permite modificar las IPs y guardarlas de forma permanente en config_red.json.
- Incluye auto-detección de la IP de la laptop en la red local y prueba de ping.
==============================================================================
"""

import os
import sys
import json
import socket
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

CONFIG_FILENAME = "config_red.json"
DEFAULT_CONFIG = {
    "laptop_ip": "10.11.8.47",
    "tablet_ip": "10.11.8.59",
    "mavlink_port": 19980,
    "video_port": 5600,
    "use_drone_video": True,
    "real_flight": False
}

def get_config_paths():
    """Retorna las rutas candidatas donde se almacena el archivo config_red.json."""
    paths = [
        os.path.join(os.getcwd(), CONFIG_FILENAME),
        os.path.join(os.getcwd(), "Air2S_MAVSDK", CONFIG_FILENAME),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILENAME)
    ]
    unique_paths = []
    for p in paths:
        norm = os.path.normpath(p)
        if norm not in unique_paths:
            unique_paths.append(norm)
    return unique_paths

def load_network_config():
    """Carga la configuración de red guardada en la última sesión o valores por defecto."""
    cfg = dict(DEFAULT_CONFIG)
    for p in get_config_paths():
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cfg.update(data)
                        break
            except Exception:
                pass
    return cfg

def save_network_config(cfg):
    """Guarda la configuración de red en disco de forma persistente en todas las rutas."""
    for p in get_config_paths():
        try:
            folder = os.path.dirname(p)
            if folder and os.path.exists(folder):
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=4)
        except Exception:
            pass

def detect_local_ip(target_hint=None):
    """Detecta automáticamente la IP activa de la laptop en la red WiFi/Hotspot."""
    candidates = []
    if target_hint:
        candidates.append(target_hint)
    candidates.extend(['10.11.8.59', '10.11.8.29', '10.11.8.1', '192.168.43.1', '192.168.1.1', '8.8.8.8'])
    for target in candidates:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect((target, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith('127.'):
                return ip
        except Exception:
            pass
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith('127.'):
                return ip
    except Exception:
        pass
    return "127.0.0.1"

def ping_host_sync(ip, timeout_ms=800):
    """Prueba si un host responde a ping en Windows sin abrir ventanas de consola."""
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        res = subprocess.run(
            ['ping', '-n', '1', '-w', str(timeout_ms), ip],
            capture_output=True,
            encoding='cp850',
            errors='ignore',
            creationflags=flags
        )
        out = res.stdout.upper()
        if 'TTL=' in out:
            latency = "OK"
            for part in out.split():
                if part.startswith('TIEMPO=') or part.startswith('TIME='):
                    latency = part.split('=')[-1]
            return True, latency
        return False, "Sin respuesta"
    except Exception as e:
        return False, str(e)


class NetworkConfigDialog:
    """Ventana interactiva de configuración de red para el prototipo de vuelo."""
    def __init__(self, current_args=None):
        self.result = None
        # 1. Cargar la configuración guardada de la última sesión
        self.saved_cfg = load_network_config()

        # 2. Solo sobreescribir si el usuario pasó explícitamente parámetros por terminal
        if current_args:
            cli_tab = getattr(current_args, 'tablet_ip', None)
            if cli_tab is not None:
                self.saved_cfg['tablet_ip'] = cli_tab
            if getattr(current_args, 'fly', False):
                self.saved_cfg['real_flight'] = True

        # 3. Detectar la IP activa de la laptop en la red local
        self.detected_laptop_ip = detect_local_ip(self.saved_cfg.get("tablet_ip", "10.11.8.59"))

        # Si no había IP guardada de laptop, usar la detectada
        if not self.saved_cfg.get("laptop_ip") or self.saved_cfg.get("laptop_ip") == "127.0.0.1":
            self.saved_cfg["laptop_ip"] = self.detected_laptop_ip

        self.root = tk.Tk()
        self.root.title("Tesis UNI - Configuración de Red (DJI Air 2S)")
        self.root.geometry("580x610")
        self.root.resizable(False, False)
        self.root.configure(bg="#181825")

        # Centrar en pantalla
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"+{(sw - w)//2}+{(sh - h)//2}")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.root.bind("<Escape>", lambda e: self._on_cancel())
        self.root.bind("<Return>", lambda e: self._on_continue_saved())

    def _build_ui(self):
        # 1. Encabezado institucional
        hdr_frame = tk.Frame(self.root, bg="#11111b", height=75)
        hdr_frame.pack(fill="x", side="top")

        lbl_icon = tk.Label(hdr_frame, text="🚁", font=("Segoe UI Emoji", 26), bg="#11111b", fg="#89b4fa")
        lbl_icon.pack(side="left", padx=16, pady=10)

        txt_frame = tk.Frame(hdr_frame, bg="#11111b")
        txt_frame.pack(side="left", fill="both", expand=True, pady=8)

        lbl_title = tk.Label(txt_frame, text="SISTEMA DE ENLACE DE VUELO - TESIS UNI",
                             font=("Segoe UI", 12, "bold"), bg="#11111b", fg="#cdd6f4")
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(txt_frame, text="Gestión de Direcciones IP (Laptop IA <---> Tablet RosettaDrone)",
                           font=("Segoe UI", 9), bg="#11111b", fg="#a6adc8")
        lbl_sub.pack(anchor="w")

        # Contenedor principal
        main_frame = tk.Frame(self.root, bg="#181825", padx=20, pady=12)
        main_frame.pack(fill="both", expand=True)

        # 2. Panel de Resumen de IPs Guardadas (Última Sesión)
        box_saved = tk.LabelFrame(main_frame, text=" 📌 IPs Guardadas de la Última Sesión ",
                                  font=("Segoe UI", 9, "bold"), bg="#1e1e2e", fg="#fab387",
                                  padx=12, pady=8, bd=1, relief="groove")
        box_saved.pack(fill="x", pady=(0, 12))

        saved_lap = self.saved_cfg.get("laptop_ip", self.detected_laptop_ip)
        saved_tab = self.saved_cfg.get("tablet_ip", "10.11.8.59")

        row_s1 = tk.Frame(box_saved, bg="#1e1e2e")
        row_s1.pack(fill="x", pady=2)
        tk.Label(row_s1, text="• IP Laptop (Última usada):", font=("Segoe UI", 9), bg="#1e1e2e", fg="#bac2de").pack(side="left")
        self.lbl_s_lap = tk.Label(row_s1, text=f"{saved_lap}", font=("Segoe UI", 9, "bold"), bg="#1e1e2e", fg="#a6e3a1")
        self.lbl_s_lap.pack(side="left", padx=8)

        row_s2 = tk.Frame(box_saved, bg="#1e1e2e")
        row_s2.pack(fill="x", pady=2)
        tk.Label(row_s2, text="• IP Tablet (Última usada):", font=("Segoe UI", 9), bg="#1e1e2e", fg="#bac2de").pack(side="left")
        self.lbl_s_tab = tk.Label(row_s2, text=f"{saved_tab}", font=("Segoe UI", 9, "bold"), bg="#1e1e2e", fg="#89b4fa")
        self.lbl_s_tab.pack(side="left", padx=8)

        # 3. Formulario de Configuración / Modificación de IPs
        box_form = tk.LabelFrame(main_frame, text=" ⚙️ IPs a Utilizar en Este Vuelo ",
                                 font=("Segoe UI", 9, "bold"), bg="#1e1e2e", fg="#cdd6f4",
                                 padx=12, pady=10, bd=1, relief="groove")
        box_form.pack(fill="x", pady=(0, 10))

        # Fila Tablet IP
        tk.Label(box_form, text="IP de la Tablet (RosettaDrone):", font=("Segoe UI", 9, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4").pack(anchor="w")
        row_tab = tk.Frame(box_form, bg="#1e1e2e")
        row_tab.pack(fill="x", pady=(2, 6))

        self.ent_tablet = tk.Entry(row_tab, font=("Consolas", 11), bg="#313244", fg="#ffffff",
                                   insertbackground="#ffffff", bd=2, relief="flat")
        self.ent_tablet.insert(0, saved_tab)
        self.ent_tablet.pack(side="left", fill="x", expand=True, ipady=3)

        btn_ping = tk.Button(row_tab, text="🔍 Probar Ping", font=("Segoe UI", 9, "bold"),
                             bg="#f9e2af", fg="#11111b", activebackground="#f5c2e7",
                             bd=0, padx=10, cursor="hand2", command=self._on_test_ping)
        btn_ping.pack(side="left", padx=(8, 0))

        self.lbl_ping_status = tk.Label(box_form, text="Estado: No probado",
                                        font=("Segoe UI", 8), bg="#1e1e2e", fg="#6c7086")
        self.lbl_ping_status.pack(anchor="w", pady=(0, 6))

        # Fila Laptop IP
        tk.Label(box_form, text="IP de esta Laptop:", font=("Segoe UI", 9, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4").pack(anchor="w")
        row_lap = tk.Frame(box_form, bg="#1e1e2e")
        row_lap.pack(fill="x", pady=(2, 2))

        self.ent_laptop = tk.Entry(row_lap, font=("Consolas", 11), bg="#313244", fg="#ffffff",
                                   insertbackground="#ffffff", bd=2, relief="flat")
        self.ent_laptop.insert(0, saved_lap)
        self.ent_laptop.pack(side="left", fill="x", expand=True, ipady=3)
        self.ent_laptop.bind("<KeyRelease>", self._update_guide_banner)

        btn_detect = tk.Button(row_lap, text="⚡ Auto-Detectar", font=("Segoe UI", 9, "bold"),
                               bg="#89dceb", fg="#11111b", activebackground="#74c7ec",
                               bd=0, padx=10, cursor="hand2", command=self._on_auto_detect)
        btn_detect.pack(side="left", padx=(8, 0))

        self.lbl_detect_info = tk.Label(box_form, text=f"IP activa en adaptador WiFi: {self.detected_laptop_ip}",
                                        font=("Segoe UI", 8), bg="#1e1e2e", fg="#a6adc8")
        self.lbl_detect_info.pack(anchor="w", pady=(2, 2))

        # 4. Banner Guía para Configurar RosettaDrone en la Tablet
        box_guide = tk.Frame(main_frame, bg="#11111b", padx=10, pady=8, bd=1, relief="ridge")
        box_guide.pack(fill="x", pady=(0, 10))

        tk.Label(box_guide, text="📋 Configuración requerida en RosettaDrone (Tablet -> Settings):",
                 font=("Segoe UI", 8, "bold"), bg="#11111b", fg="#f38ba8").pack(anchor="w")

        self.lbl_guide_gcs = tk.Label(box_guide, text=f"  • GCS IP:       {saved_lap}",
                                      font=("Consolas", 8), bg="#11111b", fg="#cdd6f4")
        self.lbl_guide_gcs.pack(anchor="w")

        self.lbl_guide_vid = tk.Label(box_guide, text=f"  • Video IP:     {saved_lap} (Puerto 5600)",
                                      font=("Consolas", 8), bg="#11111b", fg="#cdd6f4")
        self.lbl_guide_vid.pack(anchor="w")

        # 5. Opciones de Vuelo (Checkboxes)
        row_chk = tk.Frame(main_frame, bg="#181825")
        row_chk.pack(fill="x", pady=(0, 12))

        self.var_video = tk.BooleanVar(value=self.saved_cfg.get("use_drone_video", True))
        chk_vid = tk.Checkbutton(row_chk, text="Video Dron DJI (UDP 5600)", variable=self.var_video,
                                 font=("Segoe UI", 9), bg="#181825", fg="#cdd6f4",
                                 selectcolor="#313244", activebackground="#181825", activeforeground="#ffffff")
        chk_vid.pack(side="left", padx=(0, 15))

        self.var_fly = tk.BooleanVar(value=self.saved_cfg.get("real_flight", False))
        chk_fly = tk.Checkbutton(row_chk, text="Modo Vuelo Real (--fly)", variable=self.var_fly,
                                 font=("Segoe UI", 9, "bold"), bg="#181825", fg="#f38ba8",
                                 selectcolor="#313244", activebackground="#181825", activeforeground="#f38ba8")
        chk_fly.pack(side="left")

        # 6. Botones de Acción
        btn_box = tk.Frame(self.root, bg="#11111b", padx=16, pady=12)
        btn_box.pack(fill="x", side="bottom")

        # BOTÓN 1: Continuar con IPs ya guardadas (Guarda y continúa)
        btn_saved = tk.Button(btn_box, text="▶ SEGUIR CON IPs GUARDADAS\n[Enter]",
                              font=("Segoe UI", 10, "bold"), bg="#a6e3a1", fg="#11111b",
                              activebackground="#94e2d5", bd=0, padx=12, pady=6,
                              cursor="hand2", command=self._on_continue_saved)
        btn_saved.pack(side="left", expand=True, fill="x", padx=(0, 8))

        # BOTÓN 2: Guardar las nuevas IPs y continuar
        btn_save = tk.Button(btn_box, text="💾 GUARDAR Y CONTINUAR\n(Nuevas IPs)",
                             font=("Segoe UI", 10, "bold"), bg="#89b4fa", fg="#11111b",
                             activebackground="#b4befe", bd=0, padx=12, pady=6,
                             cursor="hand2", command=self._on_save_and_continue)
        btn_save.pack(side="left", expand=True, fill="x", padx=(0, 8))

        # BOTÓN 3: Cancelar / Salir
        btn_cancel = tk.Button(btn_box, text="✕ Salir\n[Esc]",
                               font=("Segoe UI", 9), bg="#45475a", fg="#cdd6f4",
                               activebackground="#585b70", bd=0, padx=10, pady=6,
                               cursor="hand2", command=self._on_cancel)
        btn_cancel.pack(side="left")

    def _update_guide_banner(self, event=None):
        lap_ip = self.ent_laptop.get().strip() or "127.0.0.1"
        self.lbl_guide_gcs.config(text=f"  • GCS IP:       {lap_ip}")
        self.lbl_guide_vid.config(text=f"  • Video IP:     {lap_ip} (Puerto 5600)")

    def _on_auto_detect(self):
        detected = detect_local_ip(self.ent_tablet.get().strip())
        self.detected_laptop_ip = detected
        self.ent_laptop.delete(0, tk.END)
        self.ent_laptop.insert(0, detected)
        self.lbl_detect_info.config(text=f"IP activa en adaptador WiFi: {detected}")
        self._update_guide_banner()

    def _on_test_ping(self):
        target_ip = self.ent_tablet.get().strip()
        if not target_ip:
            messagebox.showwarning("Aviso", "Ingresa una dirección IP para la tablet antes de probar.", parent=self.root)
            return

        self.lbl_ping_status.config(text=f"Probando conexión con {target_ip}...", fg="#f9e2af")
        self.root.update()

        def _do_ping():
            ok, msg = ping_host_sync(target_ip, timeout_ms=800)
            if ok:
                status_txt = f"✅ Tablet CONECTADA y respondiendo (latencia: {msg})"
                color = "#a6e3a1"
            else:
                status_txt = f"❌ Sin respuesta en {target_ip} ({msg}). Verifique WiFi y RosettaDrone."
                color = "#f38ba8"

            def _update():
                self.lbl_ping_status.config(text=status_txt, fg=color)
            self.root.after(0, _update)

        threading.Thread(target=_do_ping, daemon=True).start()

    def _on_continue_saved(self):
        """Toma las IPs activas, las guarda automáticamente como últimas usadas y continúa."""
        active_tab = self.ent_tablet.get().strip() or self.saved_cfg.get("tablet_ip", "10.11.8.59")
        active_lap = self.ent_laptop.get().strip() or self.saved_cfg.get("laptop_ip", self.detected_laptop_ip)

        cfg = dict(self.saved_cfg)
        cfg["tablet_ip"] = active_tab
        cfg["laptop_ip"] = active_lap
        cfg["use_drone_video"] = self.var_video.get()
        cfg["real_flight"] = self.var_fly.get()

        # Guardar siempre para que en la siguiente sesión aparezca exactamente esta IP como última guardada
        save_network_config(cfg)
        self.result = cfg
        self.root.destroy()

    def _on_save_and_continue(self):
        """Valida, guarda las IPs ingresadas y continúa."""
        new_tab = self.ent_tablet.get().strip()
        new_lap = self.ent_laptop.get().strip()

        if not new_tab or not new_lap:
            messagebox.showerror("Error", "Debes ingresar tanto la IP de la tablet como la IP de la laptop.", parent=self.root)
            return

        cfg = dict(self.saved_cfg)
        cfg["tablet_ip"] = new_tab
        cfg["laptop_ip"] = new_lap
        cfg["use_drone_video"] = self.var_video.get()
        cfg["real_flight"] = self.var_fly.get()

        save_network_config(cfg)
        self.result = cfg
        self.root.destroy()

    def _on_cancel(self):
        self.result = None
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.result


def request_network_config_cli(saved_cfg):
    """Fallback en consola si no hay interfaz gráfica disponible."""
    saved_lap = saved_cfg.get("laptop_ip", "10.11.8.47")
    saved_tab = saved_cfg.get("tablet_ip", "10.11.8.59")
    detected = detect_local_ip(saved_tab)

    print("\n" + "=" * 65)
    print("  CONFIGURACIÓN DE RED (LAPTOP <-> TABLET ROSETTADRONE)")
    print("=" * 65)
    print(f"  [1] Seguir con IPs Guardadas (Última sesión):")
    print(f"      • Tablet IP: {saved_tab}")
    print(f"      • Laptop IP: {saved_lap}")
    print(f"  [2] Modificar IPs (Detectada actual de Laptop: {detected})")
    print(f"  [3] Cancelar y Salir")
    print("=" * 65)

    try:
        opt = input("  Seleccione opción [1 por defecto / Enter]: ").strip()
        if opt == "2":
            new_tab = input(f"  Ingresa IP de Tablet [{saved_tab}]: ").strip() or saved_tab
            new_lap = input(f"  Ingresa IP de Laptop [{detected}]: ").strip() or detected
            cfg = dict(saved_cfg)
            cfg["tablet_ip"] = new_tab
            cfg["laptop_ip"] = new_lap
            save_network_config(cfg)
            return cfg
        elif opt == "3":
            return None
        else:
            cfg = dict(saved_cfg)
            save_network_config(cfg)
            return cfg
    except (KeyboardInterrupt, EOFError):
        return None

def get_network_config_interactive(current_args=None, force_cli=False):
    """
    Punto de entrada principal:
    Lanza la pantalla gráfica interactiva. Si no hay display o se fuerza CLI,
    usa el menú de consola.
    """
    saved_cfg = load_network_config()
    if force_cli or (os.environ.get("DISPLAY") == "" and sys.platform != "win32"):
        return request_network_config_cli(saved_cfg)

    try:
        dialog = NetworkConfigDialog(current_args=current_args)
        return dialog.run()
    except Exception as e:
        print(f"[Aviso] No se pudo cargar interfaz gráfica ({e}). Usando modo consola...")
        return request_network_config_cli(saved_cfg)


if __name__ == "__main__":
    print("[*] Iniciando pantalla interactiva de configuración de red...")
    cfg = get_network_config_interactive()
    if cfg:
        print("\n✅ Configuración seleccionada exitosamente:")
        print(f"   • Laptop IP : {cfg.get('laptop_ip')}")
        print(f"   • Tablet IP : {cfg.get('tablet_ip')}")
        print(f"   • Video Dron: {cfg.get('use_drone_video')}")
        print(f"   • Vuelo Real: {cfg.get('real_flight')}")
    else:
        print("\n[Operación cancelada por el usuario].")
