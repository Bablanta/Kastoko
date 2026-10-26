import ctypes
from ctypes import wintypes
import os
import sys
import threading
import time
import webbrowser
import atexit
import signal

# Inisialisasi Win32 API hanya jika berjalan di sistem Windows
IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32

    # Konfigurasi tipe 64-bit yang aman untuk fungsi Win32
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = ctypes.c_longlong

    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT, wintypes.LPCWSTR]
    user32.AppendMenuW.restype = wintypes.BOOL
    user32.TrackPopupMenuEx.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
    user32.TrackPopupMenuEx.restype = wintypes.BOOL
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.DestroyMenu.restype = wintypes.BOOL

    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL

    user32.PostQuitMessage.argtypes = [ctypes.c_int]
    user32.PostQuitMessage.restype = None
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL

    user32.LoadImageW.restype = wintypes.HICON
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.LoadIconW.restype = wintypes.HICON
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]

    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ('cbSize', wintypes.UINT),
            ('style', wintypes.UINT),
            ('lpfnWndProc', WNDPROC),
            ('cbClsExtra', ctypes.c_int),
            ('cbWndExtra', ctypes.c_int),
            ('hInstance', wintypes.HINSTANCE),
            ('hIcon', wintypes.HICON),
            ('hCursor', wintypes.HANDLE),
            ('hbrBackground', wintypes.HBRUSH),
            ('lpszMenuName', wintypes.LPCWSTR),
            ('lpszClassName', wintypes.LPCWSTR),
            ('hIconSm', wintypes.HICON)
        ]

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [
            ('cbSize', wintypes.DWORD),
            ('hWnd', wintypes.HWND),
            ('uID', wintypes.UINT),
            ('uFlags', wintypes.UINT),
            ('uCallbackMessage', wintypes.UINT),
            ('hIcon', wintypes.HICON),
            ('szTip', wintypes.WCHAR * 128),
            ('dwState', wintypes.DWORD),
            ('dwStateMask', wintypes.DWORD),
            ('szInfo', wintypes.WCHAR * 256),
            ('uTimeoutOrVersion', wintypes.UINT),
            ('szInfoTitle', wintypes.WCHAR * 64),
            ('dwInfoFlags', wintypes.DWORD),
            ('guidItem', ctypes.c_byte * 16),
            ('hBalloonIcon', wintypes.HICON)
        ]

# Konstanta Win32
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20
WM_RBUTTONUP = 0x0205
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203

NIF_MESSAGE = 0x0001
NIF_ICON = 0x0002
NIF_TIP = 0x0004
NIF_INFO = 0x0010

NIM_ADD = 0x0000
NIM_MODIFY = 0x0001
NIM_DELETE = 0x0002

IDM_OPEN = 1001
IDM_TOGGLE_CONSOLE = 1002
IDM_QUIT = 1003

TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
SW_HIDE = 0
SW_RESTORE = 9

class KasTokoTrayManager:
    def __init__(self, port=8080, on_quit=None):
        self.port = port
        self.on_quit = on_quit
        self.running = True
        self.console_hwnd = kernel32.GetConsoleWindow() if IS_WINDOWS else None
        self.msg_hwnd = None
        self.nid = None
        self.hicon = None
        self.thread = None
        self.monitor_thread = None
        self.balloon_shown = False
        self._wnd_proc_cb = None

        if not IS_WINDOWS:
            return

        # Muat logo bawaan default_logo.ico
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "default_logo.ico")

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        if os.path.exists(icon_path):
            self.hicon = user32.LoadImageW(
                None,
                icon_path,
                IMAGE_ICON,
                user32.GetSystemMetrics(49), # SM_CXSMICON
                user32.GetSystemMetrics(50), # SM_CYSMICON
                LR_LOADFROMFILE
            )

        if not self.hicon:
            # Fallback ke ikon aplikasi sistem
            self.hicon = user32.LoadIconW(None, ctypes.c_wchar_p(32512))

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON:
            if lparam in (WM_LBUTTONDBLCLK, WM_LBUTTONUP):
                self.action_open()
                return 0
            elif lparam == WM_RBUTTONUP:
                self.show_context_menu(hwnd)
                return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def show_context_menu(self, hwnd):
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))

        hmenu = user32.CreatePopupMenu()
        user32.AppendMenuW(hmenu, 0, IDM_OPEN, "🌐 Open (Buka KasToko)")
        user32.AppendMenuW(hmenu, 0, IDM_TOGGLE_CONSOLE, "🖥️ Tampilkan/Sembunyikan Jendela Server")
        user32.AppendMenuW(hmenu, 0x0800, 0, None) # Separator
        user32.AppendMenuW(hmenu, 0, IDM_QUIT, "❌ Quit (Keluar)")

        user32.SetForegroundWindow(hwnd)
        cmd = user32.TrackPopupMenuEx(hmenu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, hwnd, None)
        user32.PostMessageW(hwnd, 0, 0, 0)
        user32.DestroyMenu(hmenu)

        if cmd == IDM_OPEN:
            self.action_open()
        elif cmd == IDM_TOGGLE_CONSOLE:
            self.action_toggle_console()
        elif cmd == IDM_QUIT:
            self.action_quit()

    def action_open(self):
        """Buka dashboard di web browser dan pulihkan jendela konsol"""
        if self.console_hwnd:
            user32.ShowWindow(self.console_hwnd, SW_RESTORE)
            user32.SetForegroundWindow(self.console_hwnd)
        try:
            webbrowser.open(f"http://localhost:{self.port}")
        except Exception:
            pass

    def action_toggle_console(self):
        """Toggle antara sembunyikan atau tampilkan jendela konsol"""
        if not self.console_hwnd:
            return
        if user32.IsWindowVisible(self.console_hwnd) and not user32.IsIconic(self.console_hwnd):
            user32.ShowWindow(self.console_hwnd, SW_HIDE)
        else:
            user32.ShowWindow(self.console_hwnd, SW_RESTORE)
            user32.SetForegroundWindow(self.console_hwnd)

    def action_quit(self):
        """Keluar dari aplikasi dan hapus icon tray"""
        print("\n[INFO] Menghentikan server dari menu System Tray...")
        self.stop()
        if self.on_quit:
            self.on_quit()
        else:
            os._exit(0)

    def show_balloon(self, title, message):
        """Tampilkan notifikasi balon Windows di System Tray"""
        if not self.nid:
            return
        self.nid.uFlags |= NIF_INFO
        self.nid.szInfoTitle = title
        self.nid.szInfo = message
        self.nid.dwInfoFlags = 1 # NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self.nid))

    def _tray_thread_proc(self):
        """Loop pesan Windows untuk menangani interaksi tray icon"""
        self._wnd_proc_cb = WNDPROC(self._wnd_proc)
        hinst = kernel32.GetModuleHandleW(None)
        class_name = f"KasTokoTrayClass_{os.getpid()}"

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wnd_proc_cb
        wc.hInstance = hinst
        wc.lpszClassName = class_name
        user32.RegisterClassExW(ctypes.byref(wc))

        self.msg_hwnd = user32.CreateWindowExW(0, class_name, "KasTokoTrayWindow", 0, 0, 0, 0, 0, 0, 0, hinst, None)

        self.nid = NOTIFYICONDATAW()
        self.nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self.nid.hWnd = self.msg_hwnd
        self.nid.uID = 1
        self.nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self.nid.uCallbackMessage = WM_TRAYICON
        self.nid.hIcon = self.hicon
        self.nid.szTip = f"KasToko Server (Port {self.port})"

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self.nid))

        # Windows Message pump
        msg = wintypes.MSG()
        while self.running:
            b_ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if b_ret == 0 or b_ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self.nid:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.nid))
        if self.msg_hwnd:
            user32.DestroyWindow(self.msg_hwnd)
        user32.UnregisterClassW(class_name, hinst)

    def _monitor_minimize_loop(self):
        """Memantau tombol minimize pada jendela konsol.
        Jika diminimize, jendela konsol langsung disembunyikan ke background/tray.
        """
        while self.running:
            time.sleep(0.25)
            if self.console_hwnd:
                # Jika jendela terlihat dan sedang dalam status diminimize (IsIconic)
                if user32.IsWindowVisible(self.console_hwnd) and user32.IsIconic(self.console_hwnd):
                    # Sembunyikan sepenuhnya dari layar dan taskbar
                    user32.ShowWindow(self.console_hwnd, SW_HIDE)
                    if not self.balloon_shown:
                        self.show_balloon("KasToko Berjalan di Background", "Server tetap aktif. Klik kanan icon di Tray untuk Open atau Quit.")
                        self.balloon_shown = True

    def start(self):
        """Mulai thread tray icon dan monitor minimisasi"""
        if not IS_WINDOWS:
            return

        self.thread = threading.Thread(target=self._tray_thread_proc, daemon=True)
        self.thread.start()

        if self.console_hwnd:
            self.monitor_thread = threading.Thread(target=self._monitor_minimize_loop, daemon=True)
            self.monitor_thread.start()

    def stop(self):
        """Hentikan dan bersihkan tray icon secara tuntas"""
        if not self.running:
            return
        self.running = False
        if IS_WINDOWS:
            if self.nid and self.msg_hwnd:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.nid))
            if self.msg_hwnd:
                user32.PostMessageW(self.msg_hwnd, 0x0012, 0, 0) # WM_QUIT


def init_tray_manager(port=8080, on_quit=None):
    """Factory helper untuk memulai KasTokoTrayManager"""
    manager = KasTokoTrayManager(port=port, on_quit=on_quit)
    manager.start()

    # Pastikan dibersihkan saat python ditutup
    atexit.register(manager.stop)
    return manager
