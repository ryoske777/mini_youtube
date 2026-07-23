"""194x110 항상 위 YouTube 미니 플레이어 (프레임리스).

유튜브 시청 페이지를 그대로 초소형 창에 띄운다. 별도 재생목록 없이
유튜브 자동재생(내 계정 알고리즘)에 따라 다음 영상이 실시간으로 이어진다.

설치:
    pip install pywebview

실행:
    python youtube_mini.py
    (더블클릭 실행 시 콘솔 창은 자동으로 숨겨짐.
     아예 콘솔 없이 띄우려면: pythonw youtube_mini.py,
     또는 파일을 youtube_mini.pyw 로 복사해 더블클릭)

배포용 빌드 (파이썬 없는 PC 에서도 실행):
    build_exe.bat 더블클릭 → dist\\YTMini\\ 폴더 생성 (+ dist\\YTMini.zip).
    폴더째 복사(또는 zip 배포)해 YTMini.exe 실행. 콘솔 창 없이 뜬다.
    (onedir 방식 — 임시폴더 삭제 실패 경고가 없고 시작이 빠르다. 코드
     업데이트는 앱 내장 자동 업데이트가 처리하므로 배포는 한 번만.)
    대상 PC 에는 WebView2 런타임만 필요 (Win10/11 대부분 기본 탑재).

조작법:
  - 우클릭: 커서 위치에 별도 팝업 메뉴 창 (미니 창 크기에 갇히지 않음)
      재생/일시정지, 음소거, 다음/이전 영상, URL 열기,
      YT 홈/구독, 항상 위, 크기, 전체화면, 최소화, 종료, 불투명도 슬라이더
  - 다음 영상: 유튜브 자동재생 알고리즘 그대로 (영상 끝나면 자동 진행)
  - 스틸컷 재생: 화면을 N초(1~10, 메뉴 슬라이더)마다 갱신되는
    정지화면으로 표시 — 소리/재생은 계속 진행 (설정 저장됨)
  - 좌클릭 드래그: 창 이동 (화면 아무 곳이나; 투명 실드가 오동작 차단)
  - 유튜브 자체 컨트롤은 우클릭 메뉴/키보드 단축키(스페이스, m 등)로 조작
  - 크기 조절: 우측 하단 손잡이 드래그 (메뉴 '기본 크기'로 복원)
  - 홈/구독 창에서 영상 클릭: 그 창은 닫히고 미니 플레이어에서 재생
  - 트레이로 보내기: 창을 숨기고 우측 하단 트레이 아이콘으로 —
    재생(소리)은 계속, 아이콘 좌클릭으로 복원, 우클릭 열기/종료
  - 카멜레온 모드: 다른 창(브라우저 등) 위에 올려두고 켜면 그 창과
    현재 탭(창 제목)을 호스트로 기억. 미니 자리가 실제로 다른 창에
    '가려졌을 때'만 같이 숨는다 — 다른 창이 활성화만 되고 호스트가
    안 가려졌으면 계속 떠 있음. 브라우저 탭이 바뀌거나 호스트가
    최소화되면 숨고, 돌아오면 다시 나타난다. 호스트 창을 옮기면
    상대 위치를 유지하며 따라간다 (Windows 전용)

저장:
  창 크기/위치, 항상 위, 불투명도, 마지막 시청 영상이
  ~/.yt_mini_profile/config.json 에 저장되어 재실행 후에도 이어서 사용.

로그인:
  크롬 로그인과는 별개(WebView2 자체 프로필 사용). YT 홈/구독 창에서
  한 번 로그인하면 유지되며, 추천 알고리즘도 계정 기준으로 적용된다.
"""
import ctypes
import json
import os
import re
import sys
import threading
import time
from ctypes import wintypes

# 배포 버전. 새 코드를 main 브랜치에 올릴 때마다 반드시 올려야(증가) 자동
# 업데이트가 인식한다. 형식은 자유지만 숫자가 커지는 방향으로.
VERSION = "2026.07.21.4"

# 자동 업데이트 소스 — main 브랜치의 youtube_mini.py (raw, 공개 접근).
# 사용자에게 배포하려면 변경사항을 main 에 병합/푸시하고 VERSION 을 올린다.
UPDATE_BRANCH = "main"
UPDATE_RAW_URL = (
    "https://raw.githubusercontent.com/ryoske777/mini_youtube/"
    + UPDATE_BRANCH + "/youtube_mini.py"
)


def _upd_log(msg):
    try:
        d = os.path.join(os.path.expanduser("~"), ".yt_mini_profile")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "mini.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S") + " [update] " + str(msg) + "\n")
    except Exception:
        pass


def _upd_version_of(src):
    m = re.search(r'(?m)^VERSION\s*=\s*["\']([^"\']+)["\']', src or "")
    return m.group(1) if m else None


def _upd_key(v):
    try:
        return tuple(int(x) for x in re.findall(r"\d+", v or ""))
    except Exception:
        return ()


def _upd_compiles(src):
    try:
        compile(src, "<yt_mini_update>", "exec")
        return True
    except Exception as e:
        _upd_log("downloaded source did not compile: %r" % (e,))
        return False


def _update_disabled():
    if not getattr(sys, "frozen", False):
        return True
    if os.environ.get("YTMINI_NOUPDATE"):
        return True
    try:
        prof = os.path.join(os.path.expanduser("~"), ".yt_mini_profile")
        with open(os.path.join(prof, "config.json"), encoding="utf-8") as f:
            if json.load(f).get("autoUpdate") is False:
                return True
    except Exception:
        pass
    return False


def _update_cache_py():
    return os.path.join(os.path.expanduser("~"), ".yt_mini_profile",
                        "update", "youtube_mini.py")


def _run_cached_update_if_any():
    """캐시에 받아둔 최신 버전이 번들보다 최신이면 '그것'을 실행한다.

    네트워크를 쓰지 않아 시작이 지연되지 않는다(최신본 다운로드는
    _background_update_fetch 가 백그라운드에서 하고 '다음 실행'에 적용된다).
    반드시 'import webview' 보다 먼저 호출 — 업데이트 코드가 자체 아키텍처
    패치 후 webview 를 임포트할 수 있게. frozen 아니면/끄면/캐시 없으면 통과.
    - 컴파일 안 되거나 버전이 더 낮으면 무시(다운그레이드 방지).
    - 실행 중 크래시하면 캐시 폐기 후 번들 버전으로 재시작.
    끄는 법: 환경변수 YTMINI_NOUPDATE=1 또는 config.json "autoUpdate": false.
    """
    if _update_disabled() or os.environ.get("YTMINI_RUNNING_UPDATE"):
        return
    cache_py = _update_cache_py()
    try:
        if not os.path.exists(cache_py):
            return
        with open(cache_py, encoding="utf-8") as f:
            csrc = f.read()
        cv = _upd_version_of(csrc)
        if not (cv and _upd_key(cv) > _upd_key(VERSION) and _upd_compiles(csrc)):
            return
        _upd_log("running cached update %s (bundled %s)" % (cv, VERSION))
        os.environ["YTMINI_RUNNING_UPDATE"] = "1"
        g = {"__name__": "__main__", "__file__": cache_py}
        try:
            exec(compile(csrc, cache_py, "exec"), g)
            sys.exit(0)
        except SystemExit:
            raise
        except BaseException as e:
            _upd_log("cached update crashed, reverting to bundled: %r" % (e,))
            try:
                os.remove(cache_py)
            except Exception:
                pass
            try:
                import subprocess
                env = dict(os.environ)
                env["YTMINI_NOUPDATE"] = "1"
                env.pop("YTMINI_RUNNING_UPDATE", None)
                subprocess.Popen([sys.executable], env=env)
            except Exception:
                pass
            os._exit(1)
    except SystemExit:
        raise
    except Exception as e:
        _upd_log("run cached update failed: %r" % (e,))


def _background_update_fetch():
    """원격 최신 소스를 받아 캐시에 저장 — '다음 실행'에 적용된다.

    백그라운드 데몬 스레드에서 돌아 시작 시간에 영향을 주지 않는다.
    즉시 최신으로 바꾸고 싶으면 우클릭 메뉴의 '버전'을 쓰면 된다.
    """
    if _update_disabled() or os.environ.get("YTMINI_RUNNING_UPDATE"):
        return
    try:
        import urllib.request
        req = urllib.request.Request(
            UPDATE_RAW_URL, headers={"User-Agent": "YTMini-updater"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            remote = resp.read().decode("utf-8", "replace")
        rv = _upd_version_of(remote)
        if rv and _upd_key(rv) > _upd_key(VERSION) and _upd_compiles(remote):
            cache_py = _update_cache_py()
            os.makedirs(os.path.dirname(cache_py), exist_ok=True)
            tmp = cache_py + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(remote)
            os.replace(tmp, cache_py)
            _upd_log("background: cached update %s for next launch (bundled %s)"
                     % (rv, VERSION))
    except Exception as e:
        _upd_log("background update fetch failed: %r" % (e,))


_run_cached_update_if_any()


def _force_x64_arch_on_arm():
    """Windows on ARM 대응 — 반드시 'import webview' 보다 먼저 실행.

    pywebview 는 webview.util 을 임포트하는 순간 아키텍처로 인터롭 DLL 경로
    (win-x64 / win-arm64 …)를 정한다. x64 로 빌드한 exe 를 ARM Windows 에서
    에뮬레이션 실행하면 platform.machine()/uname().machine 이 ARM64 라
    win-arm64(번들에 없음)를 찾다가 'Cannot find win-arm64' 로 죽는다.
    실제로는 x64 에뮬레이션이므로 프로세스 아키텍처(PROCESSOR_ARCHITECTURE)가
    AMD64 일 때만, 아키텍처를 AMD64 로 보이게 해서 번들된 win-x64 DLL 을 쓴다.
    """
    try:
        if os.environ.get("PROCESSOR_ARCHITECTURE", "").upper() != "AMD64":
            return   # 네이티브 arm64/x86 등은 건드리지 않음
        # platform 이 ARM64 로 읽는 원천 두 가지를 모두 무력화한다:
        #  1) 환경변수(PROCESSOR_ARCHITEW6432) — uname().machine 이 이걸 본다
        #  2) platform.machine / platform.uname 캐시
        os.environ.pop("PROCESSOR_ARCHITEW6432", None)
        import platform as _pf
        try:
            _pf._uname_cache = None
        except Exception:
            pass
        _orig_machine = _pf.machine

        def _machine_amd64():
            m = _orig_machine()
            return "AMD64" if (m or "").upper() == "ARM64" else m

        _pf.machine = _machine_amd64
    except Exception:
        pass


_force_x64_arch_on_arm()

import webview

BASE_W, BASE_H = 226, 126   # 최초 실행 기본 크기 (이후엔 저장된 크기 사용)
# 크기 조절 하한 — 가로/세로 모두 극한까지. 우측 하단 손잡이(16px)를
# 다시 잡아 되돌릴 수 있는 최소한의 크기만 남긴다.
MIN_W, MIN_H = 24, 20
MENU_W, MENU_H = 240, 480
# 라이브 스트림은 종료되면 '실시간 스트림 녹화를 볼 수 없습니다' 오류가
# 나므로 기본 시작 영상은 항상 재생 가능한 일반 영상으로 둔다.
DEFAULT_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

PROFILE_DIR = os.path.join(os.path.expanduser("~"), ".yt_mini_profile")
CONFIG_PATH = os.path.join(PROFILE_DIR, "config.json")

YT_ID_RE = re.compile(r"(?:youtu\.be/|[?&]v=|shorts/|live/)([A-Za-z0-9_-]{11})")

BROWSER_URLS = {
    "home": "https://www.youtube.com/",
    "subs": "https://www.youtube.com/feed/subscriptions",
    "music": "https://music.youtube.com/",
    "mlib": "https://music.youtube.com/library/playlists",
}


_USER32 = None


def _user32():
    """우리 전용 user32 인스턴스. Windows 가 아니면 None.

    주의: ctypes.windll.user32 는 프로세스 전체가 공유하는 객체라
    여기에 argtypes 를 설정하면 pywebview 내부의 SetWindowPos 호출까지
    깨져 ctypes.ArgumentError 가 쏟아진다. 반드시 별도 WinDLL 인스턴스를
    만들어 우리 시그니처가 밖으로 새지 않게 한다.
    """
    global _USER32
    if _USER32 is not None:
        return _USER32
    if not hasattr(ctypes, "WinDLL"):
        return None
    try:
        u = ctypes.WinDLL("user32")
    except Exception:
        return None
    u.WindowFromPoint.restype = ctypes.c_void_p
    u.WindowFromPoint.argtypes = [wintypes.POINT]
    u.GetAncestor.restype = ctypes.c_void_p
    u.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    u.GetForegroundWindow.restype = ctypes.c_void_p
    u.IsWindow.argtypes = [ctypes.c_void_p]
    u.IsIconic.argtypes = [ctypes.c_void_p]
    u.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    u.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
    u.IsWindowVisible.argtypes = [ctypes.c_void_p]
    u.SetWindowPos.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
    ]
    u.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    u.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    u.MonitorFromPoint.restype = ctypes.c_void_p
    u.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    u.GetTopWindow.restype = ctypes.c_void_p
    u.GetTopWindow.argtypes = [ctypes.c_void_p]
    u.GetWindow.restype = ctypes.c_void_p
    u.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
    u.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    u.FindWindowW.restype = ctypes.c_void_p
    u.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    u.MessageBoxW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    u.GetAsyncKeyState.restype = ctypes.c_short
    u.GetAsyncKeyState.argtypes = [ctypes.c_int]
    u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    _USER32 = u
    return u


VK_LBUTTON, VK_RBUTTON = 1, 2


WM_NCLBUTTONDOWN, HTCAPTION = 0x00A1, 2


GW_HWNDNEXT = 2
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x20, 0x80, 0x08000000
# 화면을 항상 덮고 있지만 '가림'으로 치지 않는 셸 창들
_SHELL_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW"}


def _ex_style(u, hwnd):
    try:
        return int(u.GetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_EXSTYLE))
    except Exception:
        try:
            return int(u.GetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE))
        except Exception:
            return 0


def _is_cloaked(hwnd):
    """DWM 이 감춘(cloaked) UWP 유령 창인지 — z순서 최상단에 남아 있어 무시 필요."""
    try:
        dwm = ctypes.windll.dwmapi
        val = wintypes.DWORD(0)
        dwm.DwmGetWindowAttribute(ctypes.c_void_p(hwnd), 14,
                                  ctypes.byref(val), ctypes.sizeof(val))
        return val.value != 0
    except Exception:
        return False


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


MONITOR_DEFAULTTONEAREST = 2


def _strip_window_chrome(hwnd):
    """Windows(특히 11)가 프레임리스 창에 기본으로 붙이는
    DWM 그림자와 둥근 모서리를 제거한다."""
    try:
        dwm = ctypes.windll.dwmapi
    except AttributeError:
        return
    try:
        # DWMWA_NCRENDERING_POLICY(2) = DWMNCRP_DISABLED(1): 그림자 제거
        val = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 2,
                                  ctypes.byref(val), ctypes.sizeof(val))
        # DWMWA_WINDOW_CORNER_PREFERENCE(33) = DWMWCP_DONOTROUND(1)
        val2 = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 33,
                                  ctypes.byref(val2), ctypes.sizeof(val2))
    except Exception:
        pass


def _work_area_at(x, y):
    """(x, y)가 속한 모니터의 작업영역 (물리 px). 실패 시 None."""
    u = _user32()
    if u is None:
        return None
    try:
        hmon = u.MonitorFromPoint(wintypes.POINT(int(x), int(y)), MONITOR_DEFAULTTONEAREST)
        if not hmon:
            return None
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)
        if not u.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return None
        r = mi.rcWork
        return (r.left, r.top, r.right, r.bottom)
    except Exception:
        return None


def _win_title(u, hwnd):
    try:
        n = u.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 2)
        u.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value or ""
    except Exception:
        return ""


def _norm_title(title):
    """탭 식별용 제목 정규화: 알림 카운트 '(3) ' 같은 접두어는 무시."""
    return re.sub(r"^\(\d+\)\s*", "", title or "").strip()


SW_HIDE, SW_SHOWNOACTIVATE, GA_ROOT = 0, 4, 2
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER = 0x0001, 0x0002, 0x0004
SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0010, 0x0040
MENU_PARK = (-10000, -10000)   # 메뉴 창 '주차' 위치 (화면 밖)


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        _log_file("load_config failed (설정 초기화됨): %r" % (e,))
        return {}


def save_config(cfg):
    # 임시 파일에 쓰고 교체(원자적) — 저장 도중 종료돼도 설정이 깨지지 않음
    try:
        os.makedirs(PROFILE_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except Exception as e:
        _log_file("save_config failed: %r" % (e,))


def _icon_path():
    """앱 아이콘(icon.ico) 경로 — exe 에 번들된 경우(_MEIPASS)도 지원."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(base, "icon.ico")
    return p if os.path.exists(p) else None


def _log_file(msg):
    """콘솔이 숨겨져 있어도 확인할 수 있는 진단 로그 (~/.yt_mini_profile/mini.log)."""
    try:
        os.makedirs(PROFILE_DIR, exist_ok=True)
        with open(os.path.join(PROFILE_DIR, "mini.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S") + " " + str(msg) + "\n")
    except Exception:
        pass


# 홈/구독 창에 주입: 영상 링크 클릭을 가로채 미니 플레이어로 넘긴다.
BROWSER_HOOK_JS = r"""
(function(){
  if (window.__miniHooked) return; window.__miniHooked = true;
  function idFrom(href){
    var m = (href||'').match(/(?:youtu\.be\/|[?&]v=|shorts\/|live\/)([A-Za-z0-9_-]{11})/);
    return m ? m[1] : null;
  }
  document.addEventListener('click', function(e){
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    var id = idFrom(a.href);
    if (!id) return;
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    if (window.pywebview && window.pywebview.api)
      window.pywebview.api.play_in_mini(a.href);
  }, true);
  // 클릭 가로채기를 빠져나간 내비게이션(키보드 이동 등) 대비 감시
  setInterval(function(){
    var id = idFrom(location.href);
    if (id && !window.__miniSent){
      window.__miniSent = true;
      if (window.pywebview && window.pywebview.api)
        window.pywebview.api.play_in_mini(location.href);
    }
  }, 500);
})();
"""


# 미니 창(유튜브 시청 페이지)에 주입: 영상만 보이게 하고 실드/손잡이를 얹는다.
# 주의: 유튜브는 Trusted Types(CSP)를 강제하므로 innerHTML 사용 금지,
# DOM API 로만 구성할 것. 문자는 BMP 범위만 사용.
MINI_HOOK_JS = r"""
(function(){
 try {
  if (window.__miniHooked) return; window.__miniHooked = true;
  var api = function(){ return (window.pywebview && window.pywebview.api) || null; };

  // ---- 영상만 꽉 차게 보이도록 CSS ----
  var st = document.createElement('style');
  st.textContent = [
    'ytd-masthead, #masthead-container, #secondary, #below, #comments,',
    '#guide, tp-yt-app-drawer, ytd-mini-guide-renderer,',
    '#cinematics, #cinematics-container { display:none !important; }',  // 앰비언트 모드 빛번짐 제거
    '/* 채널 브랜딩 워터마크(우하단 로고 오버레이) 숨김.',
    '   영상 픽셀 자체에 새겨진 방송사 로고는 CSS 로 제거 불가 */',
    '.ytp-watermark { display:none !important; }',
    'body { overflow:hidden !important; }',
    '#page-manager { margin:0 !important; }',
    '#movie_player { position:fixed !important; left:0 !important; top:0 !important;',
    '  width:100vw !important; height:100vh !important; z-index:9000 !important; background:#000; }',
    '#__mini_shield { position:fixed; left:0; top:0; right:0; bottom:0; z-index:9500; }',
    '#__mini_still { position:fixed; left:0; top:0; width:100%; height:100%;',
    '  z-index:9400; display:none; background:#000; }',
    '/* YouTube Music: 내비/플레이어바 숨기고 플레이어만 꽉 차게 */',
    'ytmusic-nav-bar, ytmusic-player-bar, #side-panel { display:none !important; }',
    'ytmusic-app-layout { --ytmusic-nav-bar-height: 0px !important; }',
    'ytmusic-player-page { padding:0 !important; margin:0 !important; top:0 !important; }',
    '#main-panel { padding:0 !important; margin:0 !important; }',
    'ytmusic-player, #player.ytmusic-player { width:100vw !important; height:100vh !important;',
    '  max-width:none !important; min-width:0 !important; margin:0 !important; }',
    '/* 영상 위에 뜨는 뮤직 자체 UI(셔플/이전/다음/반복, 노래/동영상 탭 등)',
    '   전부 숨김 — 실드에 가려 클릭도 안 되므로 시각적 소음만 됨 */',
    'ytmusic-av-toggle, ytmusic-player-expanding-menu,',
    'ytmusic-player .song-media-controls, #song-media-window .song-media-controls,',
    'ytmusic-player #song-media-controls, ytmusic-player-page .player-controls-wrapper',
    '{ display:none !important; }',
    '/* 자체 앨범아트 오버레이 (뮤직 DOM 과 무관하게 동작) */',
    '#__mini_album { position:fixed; left:0; top:0; width:100%; height:100%;',
    '  z-index:9450; display:none; background-color:#000;',
    '  background-position:center; background-repeat:no-repeat;',
    '  background-size:contain; }',
    '#__mini_grip { position:fixed; right:0; bottom:0; width:16px; height:16px;',
    '  z-index:10001; cursor:nwse-resize; opacity:0.45; }',
    '#__mini_grip:hover { opacity:1; }',
    '#__mini_grip::before { content:""; position:absolute; right:2px; bottom:2px;',
    '  width:9px; height:9px; border-right:2px solid #ddd; border-bottom:2px solid #ddd; }',
    '#__mini_url { position:fixed; z-index:10003; display:none; top:50%; left:50%;',
    '  transform:translate(-50%,-50%); width:calc(100vw - 16px);',
    '  background:#1e1e1e; border:1px solid #555; border-radius:4px; padding:5px; }',
    '#__mini_url input { width:100%; background:#111; color:#fff; border:1px solid #444;',
    '  border-radius:3px; font-size:10px; padding:4px 6px; outline:none; }',
    '#__mini_toast { position:fixed; z-index:10004; bottom:6px; left:50%;',
    '  transform:translateX(-50%); background:rgba(0,0,0,0.85); color:#fff;',
    '  font-size:9px; padding:3px 10px; border-radius:10px; opacity:0;',
    '  transition:opacity 0.25s; pointer-events:none; white-space:nowrap; }'
  ].join('\n');
  document.documentElement.appendChild(st);

  // ---- 자체 UI 요소 ----
  // 투명 실드: 유튜브 플레이어가 마우스 이벤트를 삼키지 못하게 막고
  // 좌클릭 드래그(창 이동)/우클릭(메뉴)을 안정적으로 받는다.
  var shield = document.createElement('div'); shield.id = '__mini_shield';
  var urlbox = document.createElement('div'); urlbox.id = '__mini_url';
  var urlinput = document.createElement('input');
  urlinput.placeholder = '검색어 / YouTube URL · Enter';
  urlbox.appendChild(urlinput);
  var toastEl = document.createElement('div'); toastEl.id = '__mini_toast';
  var grip = document.createElement('div'); grip.id = '__mini_grip';
  var still = document.createElement('canvas'); still.id = '__mini_still';
  var albumEl = document.createElement('div'); albumEl.id = '__mini_album';
  document.documentElement.appendChild(still);
  document.documentElement.appendChild(albumEl);
  document.documentElement.appendChild(shield);
  document.documentElement.appendChild(urlbox);
  document.documentElement.appendChild(toastEl);
  document.documentElement.appendChild(grip);

  var toastTimer = null;
  function toast(m){
    toastEl.textContent = m; toastEl.style.opacity = '1';
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function(){ toastEl.style.opacity = '0'; }, 1800);
  }

  function vid(){ return document.querySelector('video'); }
  function urlVisible(){ return urlbox.style.display === 'block'; }

  function togglePlay(){ var v = vid(); if (!v) return; v.paused ? v.play() : v.pause(); }
  function toggleMute(){
    var v = vid(); if (!v) return;
    v.muted = !v.muted;
    toast(v.muted ? '음소거' : '소리 켜짐');
  }
  function setVolume(p){
    var v = vid(); if (!v) return;
    p = Math.max(0, Math.min(100, p | 0));
    v.volume = p / 100;
    if (p > 0 && v.muted) v.muted = false;   // 볼륨을 올리면 음소거 해제
  }
  function nextVideo(){
    var b = document.querySelector('.ytp-next-button')
         || document.querySelector('ytmusic-player-bar .next-button');
    if (b) b.click();
  }
  function prevVideo(){
    var b = document.querySelector('ytmusic-player-bar .previous-button');
    if (b){ b.click(); return; }
    history.back();
  }
  // 뮤직 전용 컨트롤 — 플레이어바는 CSS 로 숨겨져 있지만
  // JS click() 은 숨겨진 요소에도 동작한다.
  function shuffleMusic(){
    var b = document.querySelector('ytmusic-player-bar .shuffle');
    if (b){ b.click(); toast('셔플'); return; }
    toast('셔플은 유튜브 뮤직에서만 돼요');
  }
  function repeatMusic(){
    var b = document.querySelector('ytmusic-player-bar .repeat');
    if (b){ b.click(); toast('반복 모드 전환'); return; }
    toast('반복은 유튜브 뮤직에서만 돼요');
  }
  // 앨범아트 보기 — 뮤직의 노래 모드 대신 우리가 직접 오버레이로 그린다.
  // (뮤직 자체 노래 모드는 주입 레이아웃과 충돌해 이미지가 깨짐)
  var albumOn = false;
  function albumArtUrl(){
    var img = document.querySelector('ytmusic-player-bar img');
    var src = img && img.src ? img.src : '';
    if (!src){
      var v = vid();
      if (v && v.poster) src = v.poster;
    }
    // 플레이어바 썸네일(저해상도)을 고해상도로 승급
    return src ? src.replace(/=w\d+-h\d+/, '=w544-h544') : '';
  }
  function refreshAlbum(){
    if (!albumOn) return;
    var u2 = albumArtUrl();
    if (u2) albumEl.style.backgroundImage = "url('" + u2 + "')";
  }
  function toggleAvMode(){
    if (location.host.indexOf('music.youtube.com') < 0){
      toast('앨범 보기는 유튜브 뮤직에서만 돼요'); return;
    }
    albumOn = !albumOn;
    if (albumOn){ refreshAlbum(); albumEl.style.display = 'block'; toast('앨범 보기'); }
    else { albumEl.style.display = 'none'; toast('영상 보기'); }
  }

  function toWatchUrl(s){
    s = (s || '').trim();
    if (/^[A-Za-z0-9_-]{11}$/.test(s)) return 'https://www.youtube.com/watch?v=' + s;
    var m = s.match(/(?:youtu\.be\/|[?&]v=|shorts\/|live\/)([A-Za-z0-9_-]{11})/);
    if (m) return 'https://www.youtube.com/watch?v=' + m[1];
    if (/^https?:\/\/(www\.|m\.)?youtube\.com\//.test(s)) return s;
    return null;
  }

  function openUrl(){
    urlbox.style.display = 'block'; urlinput.value = '';
    setTimeout(function(){ urlinput.focus(); }, 50);
  }
  function closeUrl(){ urlbox.style.display = 'none'; }

  // ---- 스틸컷 재생: N초마다 현재 프레임을 캔버스에 캡처해 정지화면처럼 표시.
  //      영상(소리 포함)은 뒤에서 계속 재생된다.
  var stillTimer = null, stillOn = false, stillSec = 10;
  function drawStill(){
    var v = vid();
    if (!v || !v.videoWidth) return;
    var w = innerWidth, h = innerHeight;
    if (still.width !== w) still.width = w;
    if (still.height !== h) still.height = h;
    var ctx = still.getContext('2d');
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, w, h);
    var s = Math.min(w / v.videoWidth, h / v.videoHeight);
    var dw = v.videoWidth * s, dh = v.videoHeight * s;
    try { ctx.drawImage(v, (w - dw) / 2, (h - dh) / 2, dw, dh); } catch (err) {}
  }
  function setStill(on, sec){
    stillOn = !!on;
    if (sec) stillSec = Math.max(1, Math.min(10, sec | 0));
    clearInterval(stillTimer); stillTimer = null;
    if (stillOn){
      still.style.display = 'block';
      drawStill();
      stillTimer = setInterval(drawStill, stillSec * 1000);
      toast('스틸컷 재생: ' + stillSec + '초 간격');
    } else {
      still.style.display = 'none';
      toast('스틸컷 재생: 꺼짐');
    }
  }

  // 파이썬(팝업 메뉴 창)에서 호출할 수 있게 노출
  window.__mini = {
    togglePlay: togglePlay, toggleMute: toggleMute, setVolume: setVolume,
    nextVideo: nextVideo, prevVideo: prevVideo,
    shuffleMusic: shuffleMusic, repeatMusic: repeatMusic, toggleAvMode: toggleAvMode,
    isAlbum: function(){ return albumOn; },
    openUrl: openUrl, toast: toast, setStill: setStill
  };

  // 저장된 스틸컷 설정 복원
  var stillCfg = __STILL__;
  if (stillCfg && stillCfg.on) setStill(true, stillCfg.sec);

  // 우클릭 → 커서 위치(물리 좌표)에 별도 팝업 메뉴 창
  document.addEventListener('contextmenu', function(e){
    e.preventDefault(); e.stopPropagation();
    closeUrl();
    var dpr = window.devicePixelRatio || 1;
    var a = api();
    if (a) a.show_menu(Math.round(e.screenX * dpr), Math.round(e.screenY * dpr));
  }, true);

  // 실드 좌클릭 드래그 = 창 이동.
  // start_drag(네이티브 이동 루프)가 성공하면 OS 가 마우스를 가져가
  // 아래 pointermove 폴백은 자연히 조용해진다 — 프레임 단위로 부드럽게.
  var dragging = false, dgX = 0, dgY = 0, dgLast = 0;
  shield.addEventListener('pointerdown', function(e){
    if (e.button !== 0) return;
    e.preventDefault();
    var a = api(); if (a) a.hide_menu();
    dragging = true; dgX = e.screenX; dgY = e.screenY; dgLast = 0;
    if (a){ a.begin_move(); a.start_drag(); }
    shield.setPointerCapture(e.pointerId);
  });
  shield.addEventListener('pointermove', function(e){
    if (!dragging) return;
    if (e.buttons === 0){ dragging = false; return; }   // 네이티브 드래그 후 잔여 상태 정리
    var now = Date.now();
    if (now - dgLast < 16) return;
    dgLast = now;
    var a = api(); if (a) a.move_delta(e.screenX - dgX, e.screenY - dgY);
  });
  shield.addEventListener('pointerup', function(){ dragging = false; });
  shield.addEventListener('pointercancel', function(){ dragging = false; });

  // 좌우 방향키 = 5초 뒤로/앞으로 (포커스 위치와 무관하게 동작)
  document.addEventListener('keydown', function(e){
    if (urlVisible()) return;
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    var v = vid(); if (!v) return;
    e.preventDefault(); e.stopImmediatePropagation();   // 유튜브 자체 처리와 중복 방지
    var d = (e.key === 'ArrowRight') ? 5 : -5;
    try { v.currentTime = Math.max(0, v.currentTime + d); } catch (err) {}
    toast(d > 0 ? '+5초' : '-5초');
  }, true);

  document.addEventListener('click', function(e){
    if (urlVisible() && !urlbox.contains(e.target)) closeUrl();
  });

  urlinput.addEventListener('keydown', function(e){
    e.stopPropagation();
    if (e.key === 'Escape'){ closeUrl(); return; }
    if (e.key !== 'Enter') return;
    var raw = urlinput.value.trim();
    if (!raw) return;
    var u = toWatchUrl(raw);
    closeUrl();
    if (u){ location.href = u; return; }         // URL/영상 ID → 바로 재생
    var a = api(); if (a) a.open_search(raw);    // 그 외 → 검색 (탐색 창)
  });

  // 우측 하단 손잡이 드래그로 창 크기 조절
  var resizing = false, rsX = 0, rsY = 0, rsW = 0, rsH = 0, rsLast = 0;
  grip.addEventListener('mousedown', function(e){
    e.preventDefault(); e.stopPropagation();
  });
  grip.addEventListener('pointerdown', function(e){
    if (e.button !== 0) return;
    e.preventDefault(); e.stopPropagation();
    resizing = true;
    rsX = e.screenX; rsY = e.screenY;
    rsW = innerWidth; rsH = innerHeight;
    grip.setPointerCapture(e.pointerId);
  });
  grip.addEventListener('pointermove', function(e){
    if (!resizing) return;
    var now = Date.now();
    if (now - rsLast < 33) return;
    rsLast = now;
    var a = api(); if (a) a.resize_to(rsW + (e.screenX - rsX), rsH + (e.screenY - rsY));
  });
  grip.addEventListener('pointerup', function(){ resizing = false; });
  grip.addEventListener('pointercancel', function(){ resizing = false; });

  // ---- 광고 자동 건너뛰기 ----
  // 확인 결과, 현재 유튜브의 '건너뛰기' 버튼은 스크립트 클릭(합성 이벤트)을
  // 무시한다(사람의 실제 클릭만 인식). 실드 때문에 사람 클릭도 불가하므로,
  // 실질적으로 광고를 넘기는 유일한 방법은 '광고 재생 중'에 광고 영상을
  // 끝으로 보내는 것이다. '#movie_player.ad-showing' 일 때만 동작하므로 본
  // 영상은 절대 건드리지 않는다. 네트워크 차단(애드블록)이 아니라서
  // '광고 차단기 감지' 팝업 대상도 아니다. (config.json 의 "adFastSkip":false
  // 로 끌 수 있음. 기본 켜짐)
  var AD_FF = __ADFF__;
  function isSkipEl(el){
    var s = ((el.textContent || '') + ' '
             + (el.getAttribute('aria-label') || '')).trim();
    if (/자세히|learn\s*more/i.test(s)) return false;  // '자세히보기'(Learn more) 제외
    if (/건너뛰기/.test(s)) return true;
    if (/\bskip\b/i.test(s)) return true;
    return false;
  }
  function handleAds(){
    try {
      var player = document.querySelector('#movie_player')
                || document.querySelector('.html5-video-player');
      var adShowing = !!(player && player.classList
                         && player.classList.contains('ad-showing'));
      // 1) 진짜 '건너뛰기' 버튼은 눌러도 본다(사람 클릭이 먹는 환경 대비).
      //    '자세히보기(Learn more)'는 제외 — 잘못 누르면 광고 링크가 열린다.
      var scope = player || document;
      var cands = scope.querySelectorAll('button, [role="button"]');
      for (var i = 0; i < cands.length; i++){
        if (isSkipEl(cands[i])){
          var el = cands[i];
          var b = (el.tagName === 'BUTTON') ? el
                : (el.querySelector && el.querySelector('button'))
                || (el.closest && el.closest('button')) || el;
          try { b.click(); } catch(e){}
        }
      }
      // 2) 광고 재생 중이면 광고 영상을 끝으로 보내 즉시 종료 (본 영상 불변)
      if (adShowing && AD_FF){
        var v = document.querySelector('video');
        if (v && isFinite(v.duration) && v.duration > 0
            && v.currentTime < v.duration - 0.3){
          try { v.currentTime = v.duration; } catch(e){}
        }
      }
      // 3) 하단 배너 오버레이 광고의 닫기(X)
      var close = document.querySelector('.ytp-ad-overlay-close-button');
      if (close){ try { close.click(); } catch(e){} }
    } catch(e){}
  }
  setInterval(handleAds, 300);

  // 주기 작업: 자동재생(알고리즘 다음 영상) 켜기, 마지막 영상 저장,
  // 재생 불가 감지, 플레이어 리사이즈.
  setInterval(function(){
    var b = document.querySelector('.ytp-autonav-toggle-button');
    if (b && b.getAttribute('aria-checked') === 'false') b.click();

    var errEl = document.querySelector('#movie_player .ytp-error');
    if (errEl && !window.__miniErrToasted){
      window.__miniErrToasted = true;
      toast('재생 불가 영상 — 우클릭 메뉴에서 URL/홈으로 이동');
    }

    // (마지막 영상 저장은 파이썬 쪽에서 get_current_url 로 처리 —
    //  내비게이션 도중 JS→파이썬 호출의 반환 콜백이 사라지며
    //  pywebview 내부 스레드가 예외를 뱉는 문제를 피한다)
    refreshAlbum();   // 곡이 바뀌면 앨범아트 갱신
    window.dispatchEvent(new Event('resize'));   // 플레이어 크기 갱신
  }, 2000);
 } catch (err) {
  // 실패 시 가드를 풀어 파이썬 쪽 재주입 루프가 다시 시도하게 한다
  window.__miniHooked = false;
  try {
    if (window.pywebview && window.pywebview.api)
      window.pywebview.api.log('mini hook error: ' + ((err && err.stack) || err));
  } catch (e) {}
 }
})();
"""


# 팝업 메뉴 창(자체 페이지 — 유튜브 CSP 제약 없음)
MENU_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #1e1e1e; color: #fff;
    font: 12px -apple-system, "Segoe UI", "Malgun Gothic", sans-serif;
    border: 1px solid #444; border-radius: 6px;
    overflow: hidden; user-select: none;
    width: 240px;   /* CSS 기준 고정폭 — 창 크기는 배율 곱해서 맞춘다 */
  }
  #g { padding: 5px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2px; }
  .mi { padding: 6px 9px; border-radius: 4px; cursor: pointer; white-space: nowrap;
        overflow: hidden; text-overflow: ellipsis; }
  .mi:hover { background: #ff5252; }
  .mi.quit { text-align: center; }
  .sep { height: 1px; background: #3a3a3a; margin: 5px 4px; }
  .op { padding: 5px 9px 6px; }
  .op label { font-size: 11px; opacity: 0.8; display: block; margin-bottom: 3px; }
  /* 슬라이더: 파란 기본 스타일 대신 얇은 옅은 회색 선 + 회색 손잡이 */
  input[type=range] {
    -webkit-appearance: none; appearance: none;
    width: 100%; height: 12px; background: transparent; margin: 0;
  }
  input[type=range]::-webkit-slider-runnable-track {
    height: 2px; background: #555; border-radius: 2px;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none; appearance: none;
    width: 10px; height: 10px; margin-top: -4px;
    background: #cfcfcf; border-radius: 50%; border: none;
  }
</style>
</head>
<body>
<div id="g"></div>
<script>
  var api = function(){ return (window.pywebview && window.pywebview.api) || null; };
  var st = { playing: false, muted: false, onTop: true, opacity: 100,
             cham: false, still: false, stillSec: 10, volume: 100, av: 'n' };
  // 화면 오른쪽 정리안대로 3그룹 + 하단 종료. 각 배열이 한 그룹(2열 그리드).
  var groups = [
    [   // 탐색 / 창
      ['home',     function(){ return '유튜브 홈'; }],
      ['url',      function(){ return '검색'; }],
      ['still',    function(){ return (st.still ? '✓ ' : '') + '스틸컷 재생'; }],
      ['cham',     function(){ return (st.cham ? '✓ ' : '') + '카멜레온모드'; }],
      ['ontop',    function(){ return (st.onTop ? '✓ ' : '') + '항상 위'; }],
      ['scale1',   function(){ return '기본 크기'; }],
      ['minimize', function(){ return '최소화'; }],
      ['tray',     function(){ return '트레이'; }],
      ['logs',     function(){ return '로그 보기'; }],
      ['version',  function(){ return '버전'; }]
    ],
    [   // 뮤직
      ['music',    function(){ return '유튜브 뮤직'; }],
      ['mlib',     function(){ return '뮤직 재생 목록'; }],
      ['repeat',   function(){ return '반복'; }],
      ['shuffle',  function(){ return '셔플'; }],
      ['avmode',   function(){
                     if (st.av === 'v') return '앨범 보기';
                     if (st.av === 's') return '영상 보기';
                     return '앨범/영상 전환';
                   }]
    ],
    [   // 재생
      ['play',     function(){ return st.playing ? '일시정지' : '재생'; }],
      ['mute',     function(){ return st.muted ? '소리 켜기' : '음소거'; }],
      ['prev',     function(){ return '이전 영상'; }],
      ['next',     function(){ return '다음영상'; }]
    ]
  ];
  var g = document.getElementById('g');
  var allItems = [];
  function addItem(parent, it, cls){
    allItems.push(it);
    var d = document.createElement('div');
    d.className = 'mi' + (cls ? ' ' + cls : ''); d.id = 'mi_' + it[0];
    d.onclick = function(){ var a = api(); if (a) a.menu_action(it[0]); };
    parent.appendChild(d);
  }
  groups.forEach(function(grp, gi){
    if (gi > 0){
      var sep = document.createElement('div'); sep.className = 'sep';
      g.appendChild(sep);
    }
    var grid = document.createElement('div'); grid.className = 'grid';
    grp.forEach(function(it){ addItem(grid, it); });
    g.appendChild(grid);
  });
  // 하단: 종료 (전체폭)
  var qsep = document.createElement('div'); qsep.className = 'sep'; g.appendChild(qsep);
  addItem(g, ['quit', function(){ return '종료'; }], 'quit');

  // 슬라이더 (볼륨 / 불투명도 / 스틸컷 간격)
  function addSlider(min, max, onInput){
    var wrap = document.createElement('div'); wrap.className = 'op';
    var lb = document.createElement('label');
    var rg = document.createElement('input');
    rg.type = 'range'; rg.min = min; rg.max = max; rg.value = max;
    rg.addEventListener('input', function(){ onInput(lb, rg); });
    wrap.appendChild(lb); wrap.appendChild(rg); g.appendChild(wrap);
    return { lb: lb, rg: rg };
  }
  var vol = addSlider(0, 100, function(lb, rg){
    lb.textContent = '볼륨 ' + rg.value + '%';
    var a = api(); if (a) a.set_volume(parseInt(rg.value, 10));
  });
  var opa = addSlider(20, 100, function(lb, rg){
    lb.textContent = '불투명도 ' + rg.value + '%';
    var a = api(); if (a) a.set_opacity(parseInt(rg.value, 10));
  });
  var sti = addSlider(1, 10, function(lb, rg){
    lb.textContent = '스틸컷 간격 ' + rg.value + '초';
    var a = api(); if (a) a.set_still_sec(parseInt(rg.value, 10));
  });

  function refresh(){
    allItems.forEach(function(it){
      var el = document.getElementById('mi_' + it[0]);
      if (el) el.textContent = it[1]();
    });
    opa.rg.value = st.opacity;   opa.lb.textContent = '불투명도 ' + st.opacity + '%';
    sti.rg.value = st.stillSec;  sti.lb.textContent = '스틸컷 간격 ' + st.stillSec + '초';
    vol.rg.value = st.volume;    vol.lb.textContent = '볼륨 ' + st.volume + '%';
  }
  function setState(s){ st = Object.assign(st, s || {}); refresh(); }
  window.setState = setState;
  refresh();

  // Windows 디스플레이 배율(DPI) 때문에 창 물리 크기와 CSS 크기가 달라
  // 메뉴가 잘릴 수 있다 → 콘텐츠 크기 x 배율로 창 크기를 맞춘다.
  function reportSize(){
    var a = api(); if (!a) return false;
    var dpr = window.devicePixelRatio || 1;
    var h = g.offsetHeight + 4;
    a.menu_resize(Math.ceil(242 * dpr), Math.ceil(h * dpr));
    return true;
  }
  var sizeTimer = setInterval(function(){
    if (reportSize()) clearInterval(sizeTimer);
  }, 200);

  // 마우스가 벗어나도 닫지 않는다 — 닫기는 바깥 클릭(파이썬 쪽 전역 감시),
  // 메뉴 위 우클릭, 항목 선택, Esc 로만.
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape'){ var a = api(); if (a) a.hide_menu(); }
  });
  document.addEventListener('contextmenu', function(e){
    e.preventDefault();
    var a = api(); if (a) a.hide_menu();
  });
</script>
</body>
</html>
"""


class Api:
    # 주의: pywebview 는 js_api 의 공개 속성을 재귀 탐색해 JS 에 노출하므로
    # 창 객체는 반드시 밑줄(_) 접두사 속성에 보관해야 한다.
    # (공개 속성에 두면 window.native... 무한 재귀 오류 발생)
    def __init__(self, config=None):
        self._window = None
        self._browser = None
        self._menu = None
        self._menu_open = False
        self._menu_ok = False     # 메뉴 창 loaded 수신 = 메뉴 WebView2 정상
        self._logwin = None
        self._notify = None       # 트레이 아이콘 (WinForms NotifyIcon)
        self._in_tray = False
        self._tray_play_item = None
        self._tray_ontop_item = None
        self._playing = False     # 2초 주기 루프가 갱신하는 재생 상태 캐시
        self._engine_ok = False   # loaded 이벤트 수신 = WebView2 정상
        self._menu_w, self._menu_h = MENU_W, MENU_H
        self._config = config if isinstance(config, dict) else {}
        self._save_timer = None
        # 카멜레온 모드: 호스트 창을 따라 보이고/숨고/이동
        self._cham_host = None          # 호스트 창 HWND
        self._cham_title = None         # 켤 당시 호스트 창 제목(=탭 식별)
        self._cham_offset = (0, 0)      # 호스트 기준 상대 위치
        self._cham_visible = True
        self._cham_last_set = None      # 감시 스레드가 마지막으로 지정한 위치
        self._cham_thread = None
        # 로드중 스플래시 (네이티브 WinForms — WebView2 안 씀)
        self._splash = None
        self._splash_label = None
        self._splash_done = False

    def _persist_later(self, delay=0.5):
        if self._save_timer is not None:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(delay, save_config, args=(self._config,))
        self._save_timer.daemon = True
        self._save_timer.start()

    def save_ui_state(self, state):
        """JS 쪽 설정(마지막 영상 등) 저장."""
        if isinstance(state, dict):
            self._config.update(state)
            self._persist_later()

    def log(self, msg):
        """주입 스크립트의 오류를 콘솔·로그 파일에서 확인할 수 있게 출력."""
        try:
            print("[mini]", msg)   # --noconsole exe 에선 stdout 이 없어 실패할 수 있음
        except Exception:
            pass
        _log_file(msg)

    def on_geometry_change(self, *args):
        """창 크기/위치 변경 시 저장 (resized/moved 이벤트)."""
        try:
            self._config.update({
                "width": self._window.width,
                "height": self._window.height,
                "x": self._window.x,
                "y": self._window.y,
            })
            self._persist_later()
        except Exception:
            pass

    def _on_ui_thread(self, fn):
        """WinForms UI 스레드에서 실행 (창 속성은 UI 스레드 전용)."""
        try:
            native = getattr(self._window, "native", None)
            if native is not None and hasattr(native, "BeginInvoke"):
                import System  # pythonnet (Windows)
                native.BeginInvoke(System.Action(fn))
                return True
        except Exception:
            pass
        return False

    def set_on_top(self, flag):
        flag = bool(flag)
        self._config.update({"onTop": flag})
        self._persist_later()
        native = getattr(self._window, "native", None)
        applied = self._on_ui_thread(lambda: setattr(native, "TopMost", flag))
        if not applied:
            try:
                self._window.on_top = flag
            except Exception:
                pass
        # 켜는 즉시 작업표시줄 위까지 끌어올린다 (루프 대기 없이)
        if flag:
            try:
                u = _user32()
                mh = self._hwnd_of(self._window)
                if u and mh:
                    f = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                    u.SetWindowPos(mh, HWND_TOPMOST, 0, 0, 0, 0, f)
                    u.SetWindowPos(mh, None, 0, 0, 0, 0, f)
            except Exception:
                pass

    def set_volume(self, pct):
        """볼륨 슬라이더 (0~100%). 볼륨을 올리면 음소거도 해제."""
        try:
            pct = max(0, min(100, int(pct)))
        except Exception:
            return
        try:
            self._window.evaluate_js(
                "window.__mini && __mini.setVolume(%d)" % pct
            )
        except Exception:
            pass

    def set_still_sec(self, sec):
        """스틸컷 갱신 간격 (1~10초)."""
        try:
            sec = max(1, min(10, int(sec)))
        except Exception:
            return
        self._config.update({"stillSec": sec})
        self._persist_later()
        if self._config.get("stillOn", False):
            try:
                self._window.evaluate_js(
                    "window.__mini && __mini.setStill(true, %d)" % sec
                )
            except Exception:
                pass

    def set_opacity(self, pct):
        """불투명도 슬라이더 (20~100%)."""
        try:
            pct = max(20, min(100, int(pct)))
        except Exception:
            return
        self._config.update({"opacity": pct})
        self._persist_later()
        self._apply_opacity(pct)

    def _apply_opacity(self, pct):
        native = getattr(self._window, "native", None)
        if native is None:
            return
        self._on_ui_thread(lambda: setattr(native, "Opacity", pct / 100.0))

    def begin_move(self):
        """실드 드래그 시작: 창의 시작 위치를 기억."""
        try:
            self._drag_origin = (self._window.x, self._window.y)
        except Exception:
            self._drag_origin = (0, 0)

    def start_drag(self):
        """네이티브 창 드래그 시작 — OS 가 이동을 직접 처리해 프레임 단위로
        부드럽다. '타이틀바를 잡았다'(WM_NCLBUTTONDOWN+HTCAPTION)고 알리면
        이후 마우스 이동/놓기는 Windows 의 이동 루프가 담당한다.
        실패 환경에서는 JS 쪽 move_delta 폴백이 그대로 동작한다."""
        try:
            u = _user32()
            mh = self._hwnd_of(self._window)
            if u is not None and mh:
                u.ReleaseCapture()
                u.PostMessageW(mh, WM_NCLBUTTONDOWN, HTCAPTION, None)
        except Exception:
            pass

    def move_delta(self, dx, dy):
        """실드 드래그 중: 시작 위치 + 마우스 이동량으로 창 이동."""
        try:
            ox, oy = getattr(self, "_drag_origin", (self._window.x, self._window.y))
            nx, ny = int(ox + dx), int(oy + dy)
            # UI 스레드(Invoke)를 거치지 않는 SetWindowPos 로 이동 —
            # UI 스레드가 바빠도/꼬여도 드래그는 항상 동작한다.
            u = _user32()
            mh = self._hwnd_of(self._window)
            if u is not None and mh:
                u.SetWindowPos(mh, None, nx, ny, 0, 0,
                               SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
            else:
                self._window.move(nx, ny)
            self._config.update({"x": nx, "y": ny})
            self._persist_later()
        except Exception:
            pass

    def set_scale(self, scale):
        w, h = BASE_W * int(scale), BASE_H * int(scale)
        self._window.resize(w, h)
        self._config.update({"width": w, "height": h})
        self._persist_later()

    def resize_to(self, w, h):
        """우측 하단 손잡이 드래그로 크기 조절."""
        try:
            w, h = max(MIN_W, int(w)), max(MIN_H, int(h))
            u = _user32()
            mh = self._hwnd_of(self._window)
            if u is not None and mh:
                u.SetWindowPos(mh, None, 0, 0, w, h,
                               SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)
            else:
                self._window.resize(w, h)
            self._config.update({"width": w, "height": h})
            self._persist_later()
        except Exception:
            pass

    def fullscreen(self):
        self._window.toggle_fullscreen()

    def minimize(self):
        self._window.minimize()

    def quit(self):
        # 종료 직전 최종 크기/위치까지 즉시 저장 (디바운스 타이머 미대기)
        try:
            if self._save_timer is not None:
                self._save_timer.cancel()
            self.on_geometry_change()
            save_config(self._config)
        except Exception:
            pass
        # 트레이 아이콘이 잔류하지 않게 정리
        try:
            if self._notify is not None:
                self._notify.Visible = False
                self._notify.Dispose()
        except Exception:
            pass
        for w in (self._menu, self._browser, self._logwin):
            try:
                if w is not None and w in webview.windows:
                    w.destroy()
            except Exception:
                pass
        try:
            self._window.destroy()
        except Exception:
            pass

        # 창 파괴 후에도 백그라운드 스레드(주입 루프 등)가 프로세스를
        # 붙잡아 좀비로 남지 않게 — 잠시 후 무조건 프로세스 종료.
        # 종료 직전 WebView2 자식을 먼저 정리해 프로필/임시폴더 잠금을 풀어야
        # (1) PyInstaller 의 '_MEI 임시폴더 삭제 실패' 경고와
        # (2) 다음 실행의 프로필 잠금(엔진 초기화 실패)을 막을 수 있다.
        def _final_exit():
            _kill_descendants()
            # 자식이 _MEI 임시폴더 핸들을 놓을 시간을 준 뒤 종료 —
            # 곧바로 나가면 PyInstaller 부트로더가 삭제에 실패해 경고가 뜬다
            time.sleep(1.0)
            os._exit(0)

        t = threading.Timer(1.2, _final_exit)
        t.daemon = True
        t.start()

    # ---- 카멜레온 모드 ----

    def _hwnd_of(self, w):
        try:
            native = w.native
            # 주의: Handle 을 읽는 순간 핸들이 없으면 '현재 스레드에서'
            # 생성돼 버린다(WinForms). 백그라운드 스레드에서 그러면 창이
            # 잘못된 스레드에 묶여 아예 표시되지 않으므로, 이미 만들어진
            # 경우에만 읽는다.
            if native is None or not getattr(native, "IsHandleCreated", True):
                return None
            handle = native.Handle
            try:
                return int(handle.ToInt64())
            except Exception:
                return int(handle)
        except Exception:
            return None

    def _toast(self, msg):
        try:
            self._window.evaluate_js(
                "window.__mini && __mini.toast(%s)" % json.dumps(msg, ensure_ascii=False)
            )
        except Exception:
            pass

    def toggle_chameleon(self):
        u = _user32()
        if u is None:
            self._toast("카멜레온 모드는 Windows 전용이에요")
            return
        if self._cham_host:
            # 해제
            self._cham_host = None
            self._cham_title = None
            mini = self._hwnd_of(self._window)
            if mini:
                u.ShowWindow(mini, SW_SHOWNOACTIVATE)
            self._cham_visible = True
            self._toast("카멜레온 모드: 꺼짐")
            return
        # 미니 창 중심점 아래에 있는 최상위 창을 호스트로 지정
        try:
            mini = self._hwnd_of(self._window)
            cx = self._window.x + self._window.width // 2
            cy = self._window.y + self._window.height // 2
            u.ShowWindow(mini, SW_HIDE)   # 자기 자신이 잡히지 않게 잠깐 숨김
            try:
                hwnd = u.WindowFromPoint(wintypes.POINT(cx, cy))
                host = u.GetAncestor(hwnd, GA_ROOT) if hwnd else None
            finally:
                u.ShowWindow(mini, SW_SHOWNOACTIVATE)
            host = int(host) if host else 0
            ours = {self._hwnd_of(w) for w in (self._window, self._menu, self._browser) if w}
            if not host or host in ours:
                self._toast("아래에 붙을 창이 없어요 — 다른 창 위에 올려두고 켜주세요")
                return
            rect = wintypes.RECT()
            u.GetWindowRect(host, ctypes.byref(rect))
            self._cham_offset = (self._window.x - rect.left, self._window.y - rect.top)
            self._cham_last_set = None
            # 현재 창 제목(=브라우저 탭)을 기억 — 탭이 바뀌면 제목이 바뀐다
            self._cham_title = _norm_title(_win_title(u, host))
            self._cham_host = host
            self._cham_visible = True
            if self._cham_thread is None or not self._cham_thread.is_alive():
                self._cham_thread = threading.Thread(target=self._cham_loop, daemon=True)
                self._cham_thread.start()
            self._toast("카멜레온 모드: 켜짐 — 이 창/탭을 기억했어요")
        except Exception:
            self._cham_host = None
            self._toast("카멜레온 모드를 켤 수 없어요")

    def _host_region_covered(self, u, host, region):
        """미니가 앉을 영역(region)을 호스트보다 위 z순서의 다른 창이 덮는지.

        z순서를 위에서부터 훑어 호스트에 도달하기 전에, 우리 프로세스가
        아닌 보이는 창이 영역과 교차하면 '덮임'. 포커스와 무관하게
        실제 가림 여부만 본다.
        """
        try:
            left, top, right, bottom = region
            pid_self = os.getpid()
            hw = u.GetTopWindow(None)
            for _ in range(2000):        # 안전 상한
                if not hw:
                    break
                hw_i = int(hw)
                if hw_i == host:
                    return False         # 호스트 위에는 아무도 없음
                if u.IsWindowVisible(hw_i) and not _is_cloaked(hw_i):
                    pid = wintypes.DWORD(0)
                    u.GetWindowThreadProcessId(ctypes.c_void_p(hw_i), ctypes.byref(pid))
                    ex = _ex_style(u, hw_i)
                    # 툴팁/알림/클릭 통과 오버레이 같은 보조 창은 가림으로 안 침
                    if (pid.value != pid_self
                            and not (ex & (WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
                                           | WS_EX_NOACTIVATE))):
                        buf = ctypes.create_unicode_buffer(64)
                        u.GetClassNameW(ctypes.c_void_p(hw_i), buf, 64)
                        if buf.value not in _SHELL_CLASSES:
                            r = wintypes.RECT()
                            u.GetWindowRect(ctypes.c_void_p(hw_i), ctypes.byref(r))
                            # 실제로 미니 영역의 30% 이상을 덮을 때만 '가림'
                            ix = min(r.right, right) - max(r.left, left)
                            iy = min(r.bottom, bottom) - max(r.top, top)
                            if ix > 0 and iy > 0:
                                area = (right - left) * (bottom - top)
                                if area > 0 and (ix * iy) >= 0.3 * area:
                                    return True
                hw = u.GetWindow(ctypes.c_void_p(hw_i), GW_HWNDNEXT)
            return False
        except Exception:
            return False

    def _cham_loop(self):
        """호스트 창의 포커스/위치를 따라 미니 창을 보이고·숨기고·이동."""
        u = _user32()
        while True:
            time.sleep(0.25)
            host = self._cham_host
            if not host:
                continue
            if self._in_tray:      # 트레이 상태에선 표시/숨김 관리 중단
                continue
            try:
                mini = self._hwnd_of(self._window)
                if not mini:
                    continue
                # 호스트가 닫힘(X) 또는 파괴 직전(핸들만 남고 안 보임) →
                # 모드만 해제하고 미니는 그 자리에 계속 표시
                host_gone = not u.IsWindow(host)
                if not host_gone and (not u.IsWindowVisible(host)
                                      and not u.IsIconic(host)):
                    host_gone = True
                if host_gone:
                    self._cham_host = None
                    self._cham_title = None
                    u.ShowWindow(mini, SW_SHOWNOACTIVATE)
                    self._cham_visible = True
                    self._toast("호스트 창이 닫혀 카멜레온 모드를 껐어요 (미니는 유지)")
                    continue

                mini_shown = bool(u.IsWindowVisible(mini))
                rect = wintypes.RECT()
                u.GetWindowRect(host, ctypes.byref(rect))
                cur = (self._window.x, self._window.y)
                # 유저가 미니를 직접 옮겼으면 상대 위치 재계산
                if (mini_shown and self._cham_last_set is not None
                        and cur != self._cham_last_set):
                    self._cham_offset = (cur[0] - rect.left, cur[1] - rect.top)
                expect = (rect.left + self._cham_offset[0],
                          rect.top + self._cham_offset[1])

                # 표시 여부는 포커스가 아니라 '실제로 가려졌는가' 기준:
                # 다른 창이 활성화만 된 경우(호스트가 안 가려짐)엔 계속 떠 있고,
                # 미니 자리를 실제로 덮는 창이 호스트 위로 오면 같이 숨는다.
                visible = True
                cur_title = _norm_title(_win_title(u, host))
                if u.IsIconic(host):
                    visible = False
                elif self._cham_title and cur_title and cur_title != self._cham_title:
                    visible = False    # 브라우저 탭이 바뀜 (빈 제목은 판정 보류)
                else:
                    region = (expect[0], expect[1],
                              expect[0] + self._window.width,
                              expect[1] + self._window.height)
                    if self._host_region_covered(u, host, region):
                        visible = False

                # 플래그가 아니라 실제 표시 상태 기준으로 동기화 —
                # 한 번 어긋나도 다음 주기(0.25s)에 반드시 복구된다.
                if visible:
                    if not mini_shown or cur != expect:
                        # 표시 + 위치 + 최상위 z순서를 한 번에 복구 (포커스는 안 뺏음)
                        u.SetWindowPos(mini, HWND_TOPMOST, expect[0], expect[1], 0, 0,
                                       SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
                    self._cham_last_set = expect
                elif mini_shown:
                    self.hide_menu()
                    u.ShowWindow(mini, SW_HIDE)
                self._cham_visible = visible
            except Exception:
                pass

    # ---- 팝업 메뉴 창 ----

    def _ensure_menu(self):
        """메뉴 창 생성 — 반드시 webview.start 전(main)에 호출할 것.

        실행 중(runtime) 생성은 WebView2 초기화가 꼬여 UI 스레드가 멈추고
        드래그(창 이동)까지 죽는 사고가 있었다. 시작 전에 '숨김 없이'
        화면 밖 좌표에 만들어 두면 초기화가 정상 완료되고, 화면 밖이라
        보이지도 않는다. 이후 표시/숨김은 창을 커서 위치로 가져오거나
        다시 화면 밖으로 '주차'하는 이동으로만 처리한다.
        """
        if self._menu is not None and self._menu in webview.windows:
            return
        self._menu_ok = False
        try:
            kwargs = dict(
                html=MENU_HTML,
                js_api=self,
                width=MENU_W,
                height=MENU_H,
                x=MENU_PARK[0],
                y=MENU_PARK[1],
                frameless=True,
                on_top=True,
                resizable=False,
                # 프레임리스 기본값이 easy_drag=True 라 pywebview 내부
                # 이동 호출이 발생함 — 메뉴는 이동할 일이 없으니 끈다
                easy_drag=False,
            )
            try:
                self._menu = webview.create_window("menu", focus=False, **kwargs)
            except TypeError:   # 구버전: focus 파라미터 없음
                self._menu = webview.create_window("menu", **kwargs)
        except Exception as e:
            self._menu = None
            _log_file("menu create failed: %r" % (e,))
            return
        # loaded 수신 = 메뉴 WebView2 정상 신호. 이 신호가 없는 동안
        # 메뉴 창에 evaluate_js 를 하면 무기한 블로킹된다 (아래 show_menu 참고)
        try:
            self._menu.events.loaded += self._on_menu_loaded
        except AttributeError:
            try:
                self._menu.loaded += self._on_menu_loaded
            except Exception:
                pass
        # 작업표시줄에 'menu' 항목이 생기지 않게 (네이티브 준비 후 적용)
        for delay in (0.5, 2.0):
            t = threading.Timer(delay, self._menu_no_taskbar)
            t.daemon = True
            t.start()

    def _on_menu_loaded(self, window=None):
        self._menu_ok = True
        if self._config.get("menuResetCount"):
            self._config.update({"menuResetCount": 0})
            self._persist_later()

    def _menu_no_taskbar(self):
        try:
            native = getattr(self._menu, "native", None)
            if native is not None and hasattr(native, "BeginInvoke"):
                import System  # pythonnet (Windows)

                def _apply():
                    try:
                        native.ShowInTaskbar = False
                    except Exception:
                        pass
                    # WebView2 가 첫 페인트 전이라도 흰 배경 대신 메뉴와 같은
                    # 어두운 배경이 보이게 한다 (첫 실행 시 흰 화면 방지)
                    try:
                        from System.Drawing import Color
                        native.BackColor = Color.FromArgb(30, 30, 30)
                    except Exception:
                        pass

                native.BeginInvoke(System.Action(_apply))
        except Exception as e:
            _log_file("menu_no_taskbar failed: %r" % (e,))

    def menu_resize(self, w, h):
        """메뉴 페이지가 측정한 실제 필요 크기(물리 px)로 창 크기 보정."""
        # 메뉴 페이지 JS→파이썬 호출이 왔다 = 메뉴 창이 확실히 살아 있다
        # (구버전 pywebview 에서 loaded 이벤트 연결이 실패한 경우 대비)
        self._menu_ok = True
        try:
            self._menu_w, self._menu_h = int(w), int(h)
            if self._menu is not None and self._menu in webview.windows:
                self._menu.resize(self._menu_w, self._menu_h)
        except Exception:
            pass

    def _menu_pos(self, x, y):
        """커서 기준 메뉴 위치. 공간이 부족한 쪽은 네이티브 메뉴처럼
        커서 반대편(왼쪽/위쪽)으로 뒤집고, 모니터 작업영역 안으로 보정."""
        w, h = self._menu_w, self._menu_h
        area = _work_area_at(x, y)
        if area is None:
            # Windows API 를 못 쓰면 주 화면 크기로 근사
            try:
                s = webview.screens[0]
                area = (0, 0, s.width, s.height)
            except Exception:
                return x, y
        left, top, right, bottom = area
        if x + w > right:
            x = x - w          # 오른쪽 공간 부족 → 커서 왼쪽으로
        if y + h > bottom:
            y = y - h          # 아래 공간 부족 → 커서 위쪽으로
        x = max(left, min(x, right - w))
        y = max(top, min(y, bottom - h))
        return x, y

    def show_menu(self, sx, sy):
        """커서 위치(물리 좌표)에 팝업 메뉴 표시. 열려 있으면 닫기(토글)."""
        if self._menu_open:
            self.hide_menu()
            return
        try:
            self._ensure_menu()
        except Exception as e:
            _log_file("ensure_menu failed: %r" % (e,))
        if self._menu is None or self._menu not in webview.windows:
            _log_file("show_menu: menu window unavailable")
            return
        self._menu_open = True
        try:
            x, y = self._menu_pos(int(sx), int(sy))
        except Exception:
            x, y = int(sx), int(sy)

        def _reveal():
            # 메뉴 WebView2 가 아직 로드(첫 페인트) 전이면 화면 안으로 옮겨도
            # 내용이 안 그려진 '흰(빈) 창'이 뜬다. 첫 실행에서 이 증상이 잦아
            # loaded 신호(_menu_ok)를 잠깐 기다렸다가 표시한다. 이미 로드된
            # 뒤(두 번째부터)엔 대기 없이 즉시 뜬다.
            deadline = time.time() + 2.5
            while (not self._menu_ok and self._menu_open
                   and time.time() < deadline):
                time.sleep(0.05)
            if not self._menu_open:      # 대기 중 토글로 닫힘
                return
            if not self._menu_ok:
                _log_file("show_menu: menu page not loaded yet (WebView2 init?)")
            # 창은 항상 '표시' 상태 — 커서 위치로 이동시키는 것만으로 나타난다.
            # (위치+크기+최상위+표시를 SetWindowPos 한 번으로, 포커스 안 뺏음)
            try:
                u = _user32()
                mh = self._hwnd_of(self._menu)
                if u is not None and mh:
                    u.SetWindowPos(mh, HWND_TOPMOST, x, y,
                                   self._menu_w, self._menu_h,
                                   SWP_NOACTIVATE | SWP_SHOWWINDOW)
                else:
                    try:
                        self._menu.resize(self._menu_w, self._menu_h)
                    except Exception:
                        pass
                    self._menu.move(x, y)
            except Exception as e:
                _log_file("show_menu reveal failed: %r" % (e,))
            # 상태(재생/음소거 등) 갱신 + 바깥 클릭 감시는 별도 스레드로.
            # evaluate_js 는 대상 창 로드 전/내비게이션 중 블로킹될 수 있어
            # 표시 경로와 분리한다.
            threading.Thread(target=self._push_menu_state, daemon=True).start()
            threading.Thread(target=self._menu_outside_watch, daemon=True).start()

        threading.Thread(target=_reveal, daemon=True).start()

    def _push_menu_state(self):
        """현재 상태를 수집해 메뉴 페이지에 반영 (백그라운드 전용).

        미니/메뉴 어느 쪽 evaluate_js 가 블로킹돼도 우클릭 경로(show_menu)는
        영향을 받지 않도록 반드시 별도 스레드에서 호출한다.
        """
        state = {
            "onTop": bool(self._config.get("onTop", True)),
            "opacity": int(self._config.get("opacity", 100)),
            "cham": bool(self._cham_host),
            "still": bool(self._config.get("stillOn", False)),
            "stillSec": int(self._config.get("stillSec", 10)),
        }
        if self._engine_ok:      # 미니가 로드 전이면 질의 자체가 블로킹됨
            try:
                # 재생/음소거/볼륨 + 앨범 보기 상태(s=앨범, v=영상, n=뮤직 아님)
                r = self._window.evaluate_js(
                    "(function(){var v=document.querySelector('video');"
                    "if(!v) return '';"
                    "var av='n';"
                    "if(location.host.indexOf('music.youtube.com')>=0){"
                    "av=(window.__mini&&__mini.isAlbum&&__mini.isAlbum())?'s':'v';}"
                    "return (v.paused?'0':'1')+(v.muted?'1':'0')"
                    "+Math.round((v.volume||0)*100)+'|'+av;})()"
                )
                parts = (r or "").split("|", 1)
                s = parts[0]
                state["playing"] = bool(s and s[0] == "1")
                state["muted"] = bool(s and len(s) > 1 and s[1] == "1")
                if s and len(s) > 2:
                    state["volume"] = max(0, min(100, int(s[2:])))
                state["av"] = parts[1] if len(parts) > 1 else "n"
            except Exception:
                pass
        if not self._menu_ok or not self._menu_open:
            return
        try:
            if self._menu is not None and self._menu in webview.windows:
                self._menu.evaluate_js(
                    "window.setState && setState(%s)" % json.dumps(state, ensure_ascii=False)
                )
        except Exception:
            pass

    def _menu_outside_watch(self):
        """메뉴가 열려 있는 동안 바깥 클릭을 전역 감시해 닫는다.

        메뉴 창은 포커스를 받지 않아(NOACTIVATE) 블러 이벤트가 없으므로
        마우스 버튼 + 커서 위치를 폴링한다. 메뉴를 연 우클릭이 떼질
        때까지 기다린 뒤 감시를 시작한다.
        """
        u = _user32()
        if u is None:
            return
        try:
            def any_button():
                return ((u.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
                        or (u.GetAsyncKeyState(VK_RBUTTON) & 0x8000))

            while any_button():          # 메뉴를 연 클릭이 떼질 때까지
                time.sleep(0.03)
            while self._menu_open:
                time.sleep(0.08)
                if not any_button():
                    continue
                pt = wintypes.POINT()
                u.GetCursorPos(ctypes.byref(pt))
                mh = self._hwnd_of(self._menu)
                if not mh:
                    return
                r = wintypes.RECT()
                u.GetWindowRect(mh, ctypes.byref(r))
                if r.left <= pt.x < r.right and r.top <= pt.y < r.bottom:
                    # 메뉴 안 클릭(항목 선택 등) — 떼질 때까지 기다렸다 계속
                    while any_button():
                        time.sleep(0.03)
                    continue
                self.hide_menu()         # 바깥 클릭 → 닫기
                return
        except Exception:
            pass

    def hide_menu(self):
        self._menu_open = False
        try:
            if self._menu is not None and self._menu in webview.windows:
                # 숨기는 대신 화면 밖으로 '주차' — 표시 상태를 안 건드려
                # WinForms/WebView2 상태 꼬임이 없다.
                u = _user32()
                mh = self._hwnd_of(self._menu)
                if u is not None and mh:
                    u.SetWindowPos(mh, HWND_TOPMOST, MENU_PARK[0], MENU_PARK[1], 0, 0,
                                   SWP_NOSIZE | SWP_NOACTIVATE)
                else:
                    self._menu.move(MENU_PARK[0], MENU_PARK[1])
        except Exception:
            pass

    def menu_action(self, name):
        """팝업 메뉴 항목 실행."""
        self.hide_menu()
        page_calls = {
            "play": "window.__mini && __mini.togglePlay()",
            "mute": "window.__mini && __mini.toggleMute()",
            "next": "window.__mini && __mini.nextVideo()",
            "prev": "window.__mini && __mini.prevVideo()",
            "url": "window.__mini && __mini.openUrl()",
            "shuffle": "window.__mini && __mini.shuffleMusic()",
            "repeat": "window.__mini && __mini.repeatMusic()",
            "avmode": "window.__mini && __mini.toggleAvMode()",
        }
        try:
            if name in page_calls:
                self._window.evaluate_js(page_calls[name])
            elif name in ("home", "subs", "music", "mlib"):
                self.open_browser(name)
            elif name == "ontop":
                self.set_on_top(not self._config.get("onTop", True))
            elif name == "cham":
                self.toggle_chameleon()
            elif name == "logs":
                self.show_logs()
            elif name == "version":
                self.check_update()
            elif name == "tray":
                self.toggle_tray()
            elif name == "still":
                on = not self._config.get("stillOn", False)
                self._config.update({"stillOn": on})
                self._persist_later()
                sec = int(self._config.get("stillSec", 10))
                self._window.evaluate_js(
                    "window.__mini && __mini.setStill(%s, %d)"
                    % ("true" if on else "false", sec)
                )
            elif name == "scale2":
                self.set_scale(2)
            elif name == "scale1":
                self.set_scale(1)
            elif name == "fullscreen":
                self.fullscreen()
            elif name == "minimize":
                self.minimize()
            elif name == "quit":
                self.quit()
        except Exception:
            pass

    # ---- 트레이 ----

    def toggle_tray(self):
        """창을 숨기고 우측 하단 트레이 아이콘으로 보낸다 (재생은 계속)."""
        if self._in_tray:
            self._restore_from_tray()
            return
        u = _user32()
        mh = self._hwnd_of(self._window)
        if u is None or not mh:
            self._toast("트레이 기능은 Windows 전용이에요")
            return
        if not self._ensure_notify_icon():
            self._toast("트레이 아이콘을 만들 수 없어요")
            return
        self._in_tray = True
        self.hide_menu()
        u.ShowWindow(mh, SW_HIDE)   # 화면·작업표시줄에서 숨김

    def _ensure_notify_icon(self):
        """트레이 아이콘 생성/표시 — 반드시 UI 스레드에서 (WinForms)."""
        if self._notify is not None:
            try:
                self._notify.Visible = True
                return True
            except Exception:
                self._notify = None
        native = getattr(self._window, "native", None)
        if native is None or not hasattr(native, "BeginInvoke"):
            return False
        done = threading.Event()
        ok = [False]

        def _make():
            try:
                from System.Windows.Forms import (NotifyIcon, ContextMenuStrip,
                                                  ToolStripMenuItem)
                from System.Drawing import Icon, SystemIcons
                ni = NotifyIcon()
                ip = _icon_path()
                try:
                    if ip:
                        ni.Icon = Icon(ip)          # 전용 앱 아이콘
                    else:
                        ni.Icon = Icon.ExtractAssociatedIcon(sys.executable)
                except Exception:
                    ni.Icon = SystemIcons.Application
                ni.Text = "YT Mini"
                menu = ContextMenuStrip()
                mi_open = ToolStripMenuItem("열기")
                mi_play = ToolStripMenuItem("재생")
                mi_next = ToolStripMenuItem("다음")
                mi_prev = ToolStripMenuItem("이전")
                mi_top = ToolStripMenuItem("항상 위 끄기")
                mi_quit = ToolStripMenuItem("닫기")
                mi_open.Click += lambda s, e: self._tray_cmd("open")
                mi_play.Click += lambda s, e: self._tray_cmd("play")
                mi_next.Click += lambda s, e: self._tray_cmd("next")
                mi_prev.Click += lambda s, e: self._tray_cmd("prev")
                mi_top.Click += lambda s, e: self._tray_cmd("ontop")
                mi_quit.Click += lambda s, e: self._tray_cmd("quit")
                for it in (mi_open, mi_play, mi_next, mi_prev, mi_top, mi_quit):
                    menu.Items.Add(it)
                self._tray_play_item = mi_play
                self._tray_ontop_item = mi_top
                menu.Opening += self._on_tray_menu_opening
                ni.ContextMenuStrip = menu
                ni.MouseClick += self._on_tray_click
                ni.Visible = True
                self._notify = ni
                ok[0] = True
            except Exception as e:
                _log_file("notify icon create failed: %r" % (e,))
            finally:
                done.set()

        try:
            import System
            native.BeginInvoke(System.Action(_make))
        except Exception as e:
            _log_file("notify icon invoke failed: %r" % (e,))
            return False
        done.wait(3)
        return ok[0]

    def _on_tray_menu_opening(self, sender, e):
        """트레이 메뉴가 열릴 때 재생/멈춤·항상 위 라벨을 현재 상태로 갱신."""
        try:
            if self._tray_play_item is not None:
                self._tray_play_item.Text = "멈춤" if self._playing else "재생"
            if self._tray_ontop_item is not None:
                self._tray_ontop_item.Text = (
                    "항상 위 끄기" if self._config.get("onTop", True) else "항상 위 켜기"
                )
        except Exception:
            pass

    def _tray_cmd(self, name):
        """트레이 메뉴 클릭 처리.

        클릭 핸들러는 UI 스레드에서 실행되는데 거기서 evaluate_js 를
        동기 호출하면 결과 콜백이 같은 UI 스레드를 기다려 교착된다 —
        반드시 별도 스레드로 넘긴다.
        """
        def run():
            try:
                if name == "open":
                    self._restore_from_tray()
                elif name == "quit":
                    self.quit()
                elif name == "ontop":
                    self.set_on_top(not self._config.get("onTop", True))
                else:
                    if name == "play":
                        self._playing = not self._playing   # 라벨 즉시 반영
                    self.menu_action(name)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _on_tray_click(self, sender, e):
        try:
            from System.Windows.Forms import MouseButtons
            if e.Button != MouseButtons.Left:
                return   # 우클릭은 ContextMenuStrip(열기/종료)이 처리
        except Exception:
            pass
        self._restore_from_tray()

    def _restore_from_tray(self):
        self._in_tray = False
        # 트레이 아이콘은 상시 표시 유지 (창 찾기/항상 위 토글용) — 숨기지 않음
        # 창 복원 (표시 + 최상위, 포커스 안 뺏음)
        try:
            u = _user32()
            mh = self._hwnd_of(self._window)
            if u and mh:
                u.SetWindowPos(mh, HWND_TOPMOST, 0, 0, 0, 0,
                               SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                               | SWP_SHOWWINDOW)
        except Exception:
            pass

    def show_logs(self):
        """로그 파일(mini.log)을 보여주는 창. 오류 진단용 인터페이스."""
        import html as _html
        try:
            with open(os.path.join(PROFILE_DIR, "mini.log"), encoding="utf-8") as f:
                lines = f.readlines()[-400:]
            text = "".join(lines).strip() or "(로그가 비어 있어요)"
        except Exception:
            text = "(아직 로그 파일이 없어요)"
        page = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            "body{background:#111;color:#ddd;font:12px Consolas,monospace;"
            "padding:10px;white-space:pre-wrap;word-break:break-all;}"
            "h3{color:#fff;font:13px sans-serif;margin-bottom:8px;}"
            "</style></head><body><h3>YT Mini 로그 ("
            + _html.escape(os.path.join(PROFILE_DIR, "mini.log"))
            + ")</h3>" + _html.escape(text) + "</body></html>"
        )
        if self._logwin is not None and self._logwin in webview.windows:
            try:
                self._logwin.load_html(page)
                self._logwin.restore()
                self._logwin.show()
                return
            except Exception:
                pass
        try:
            self._logwin = webview.create_window(
                "YT Mini 로그", html=page, width=720, height=480, on_top=False)
        except Exception as e:
            _log_file("show_logs failed: %r" % (e,))

    # ---- 버전 확인 / 수동 업데이트 ----

    def check_update(self):
        """'버전' 메뉴: 최신 버전을 확인하고, 새 버전이 있으면 업데이트 여부를
        물어본 뒤 내려받아 재시작한다. 네트워크/메시지박스가 블로킹되므로
        반드시 별도 스레드에서 실행한다."""
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _check_update_worker(self):
        u = _user32()

        def box(text, icon=0x40):
            # icon: 0x40 정보, 0x30 경고, 0x20 물음
            try:
                if u is not None:
                    return u.MessageBoxW(None, text, "YT Mini 버전",
                                         icon | 0x00040000)  # MB_TOPMOST
            except Exception:
                pass
            return 0

        # 원격 최신 버전 확인
        try:
            import urllib.request
            req = urllib.request.Request(
                UPDATE_RAW_URL, headers={"User-Agent": "YTMini-updater"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                remote = resp.read().decode("utf-8", "replace")
            rv = _upd_version_of(remote)
        except Exception as e:
            _log_file("version check failed: %r" % (e,))
            box("업데이트 확인에 실패했어요.\n인터넷 연결을 확인해 주세요.\n\n"
                "현재 버전: %s" % VERSION, 0x30)
            return
        if not rv:
            box("최신 버전 정보를 읽지 못했어요.\n\n현재 버전: %s" % VERSION, 0x30)
            return
        if _upd_key(rv) <= _upd_key(VERSION):
            box("이미 최신 버전을 사용 중이에요.\n\n현재 버전: %s" % VERSION, 0x40)
            return
        # 새 버전 있음 → 업데이트할지 물어봄 (예/아니오)
        res = box("새 버전이 있어요.\n\n현재 버전: %s\n최신 버전: %s\n\n"
                  "지금 업데이트할까요?\n(업데이트 후 프로그램이 다시 시작됩니다)"
                  % (VERSION, rv), 0x24)   # MB_YESNO | MB_ICONQUESTION
        if res != 6:      # IDYES 아님
            return
        if not getattr(sys, "frozen", False):
            box("개발 모드(.py 직접 실행)에서는 자동 업데이트가 적용되지 않아요.\n"
                "git 으로 최신 코드를 받아 주세요.", 0x40)
            return
        if not _upd_compiles(remote):
            box("받은 최신 버전이 손상돼 적용할 수 없어요.\n"
                "잠시 후 다시 시도해 주세요.", 0x30)
            return
        # 캐시에 저장 → 재시작 (재시작 시 업데이터가 최신본을 실행)
        try:
            cache_dir = os.path.join(PROFILE_DIR, "update")
            os.makedirs(cache_dir, exist_ok=True)
            cache_py = os.path.join(cache_dir, "youtube_mini.py")
            tmp = cache_py + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(remote)
            os.replace(tmp, cache_py)
            _log_file("manual update downloaded %s → relaunch" % rv)
        except Exception as e:
            _log_file("manual update save failed: %r" % (e,))
            box("업데이트 저장에 실패했어요:\n%r" % (e,), 0x30)
            return
        # 재시작 시 업데이터가 캐시(최신본)를 실행하도록 억제 플래그 해제
        os.environ.pop("YTMINI_RUNNING_UPDATE", None)
        os.environ.pop("YTMINI_NOUPDATE", None)
        _relaunch()

    # ---- 홈/구독 브라우저 창 ----

    def _browser_geometry(self, bw=1000, bh=650):
        """미니 창 바로 아래(공간 없으면 위)에 붙는 위치 계산.

        화면 경계는 미니 창이 있는 모니터의 실제 작업영역(물리 px) 기준 —
        pywebview 의 논리 화면 크기와 물리 좌표를 섞으면 DPI 배율에서
        보정이 어긋난다.
        """
        try:
            mx, my = self._window.x, self._window.y
            mh = self._window.height
            x, y = mx, my + mh + 6
            area = _work_area_at(mx + 10, my + 10)
            if area:
                left, top, right, bottom = area
                x = max(left, min(x, right - bw))
                if y + bh > bottom:
                    y = my - bh - 6          # 아래 공간이 없으면 위로
                if y < top:
                    y = max(top, bottom - bh)
            return int(x), int(y)
        except Exception:
            return None, None

    def _place_browser(self, x, y, bw, bh):
        """브라우저 창을 미니 옆 계산 위치로 이동.

        pywebview move/생성 좌표는 런타임 창에 적용되지 않는 경우가 있어
        SetWindowPos 를 쓰고, 창 핸들이 준비될 때까지 재시도한다.
        """
        if x is None:
            return
        browser = self._browser

        def _worker():
            placed = 0
            for _ in range(20):          # 최대 ~5초
                try:
                    if browser is None or browser not in webview.windows:
                        return
                    u = _user32()
                    hw = self._hwnd_of(browser)
                    if u is not None and hw:
                        u.SetWindowPos(hw, None, int(x), int(y), int(bw), int(bh),
                                       SWP_NOZORDER)
                        placed += 1
                        # 초기화 과정에서 창이 스스로 위치를 되돌리는 경우가
                        # 있어 성공 후 한 번 더 못박는다.
                        if placed >= 2:
                            return
                except Exception as e:
                    _log_file("place_browser: %r" % (e,))
                    return
                time.sleep(0.3)
            # Windows API 를 못 쓰는 환경 폴백
            try:
                browser.move(int(x), int(y))
            except Exception:
                pass

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def open_search(self, query):
        """검색어를 탐색 창에서 검색 — 미니가 뮤직이면 뮤직 검색으로."""
        q = (query or "").strip()
        if not q:
            return
        import urllib.parse
        enc = urllib.parse.quote(q)
        cur = ""
        try:
            cur = self._window.get_current_url() or ""
        except Exception:
            pass
        if "music.youtube.com" in cur:
            url = "https://music.youtube.com/search?q=" + enc
        else:
            url = "https://www.youtube.com/results?search_query=" + enc
        self._open_browser_url(url)

    def open_browser(self, which):
        """YT 홈/구독/뮤직을 보는 일반 브라우저 창. 이미 열려 있으면 재사용."""
        self._open_browser_url(BROWSER_URLS.get(which, BROWSER_URLS["home"]))

    def _open_browser_url(self, url):
        bw, bh = 1000, 650
        x, y = self._browser_geometry(bw, bh)
        if self._browser is not None and self._browser in webview.windows:
            try:
                self._browser.load_url(url)
                self._browser.restore()
                self._browser.show()
                self._place_browser(x, y, bw, bh)
                return
            except Exception:
                pass
        self._browser = webview.create_window(
            "YouTube",
            url=url,
            js_api=self,
            width=bw,
            height=bh,
            x=x,
            y=y,
            on_top=False,
        )
        # 페이지가 로드될 때마다 클릭 가로채기 스크립트 주입
        try:
            self._browser.events.loaded += self._inject_browser_hook
        except AttributeError:
            self._browser.loaded += self._inject_browser_hook
        self._place_browser(x, y, bw, bh)

    def _inject_browser_hook(self, window=None):
        try:
            if self._browser is not None and self._browser in webview.windows:
                self._browser.evaluate_js(BROWSER_HOOK_JS)
        except Exception:
            pass

    # ---- 로드중 스플래시 (네이티브 WinForms 오버레이) ----
    # 미니 창이 유튜브를 로딩하는 동안(마스트헤드 깜빡임/작은 창 노출) 위에
    # '로드중' 오버레이를 덮어 가린다. 추가 WebView2 를 만들지 않아(느린 ARM
    # 에뮬레이션에서도) 엔진 초기화에 부담을 주지 않는다.

    def _make_or_move_splash(self, x, y, w, h):
        def fn():
            if self._splash_done:      # 이미 걷어내기로 결정됨
                return
            try:
                from System.Windows.Forms import (Form, Label, FormBorderStyle,
                                                   DockStyle)
                from System.Drawing import Color, Font, ContentAlignment
                first = self._splash is None
                if first:
                    f = Form()
                    f.FormBorderStyle = getattr(FormBorderStyle, "None")
                    f.ShowInTaskbar = False
                    f.TopMost = True
                    f.BackColor = Color.FromArgb(15, 15, 15)
                    lbl = Label()
                    lbl.Dock = DockStyle.Fill
                    lbl.TextAlign = ContentAlignment.MiddleCenter
                    lbl.ForeColor = Color.FromArgb(235, 235, 235)
                    try:
                        lbl.Font = Font("Malgun Gothic", 9.0)
                    except Exception:
                        pass
                    lbl.Text = "YouTube Mini\n로드중입니다..."
                    f.Controls.Add(lbl)
                    self._splash_label = lbl
                    self._splash = f
                f = self._splash
                try:
                    f.SetBounds(int(x), int(y), int(w), int(h))
                except Exception:
                    pass
                # 최초 1회는 Show() 로 확실히 그린다(라벨 렌더 보장). 이후엔
                # 포커스 뺏지 않고 위치/최상위만 갱신(SetWindowPos NOACTIVATE).
                if first:
                    try:
                        f.Show()
                    except Exception:
                        pass
                u = _user32()
                hs = None
                try:
                    hs = int(f.Handle.ToInt64())
                except Exception:
                    hs = None
                if u is not None and hs:
                    u.SetWindowPos(hs, HWND_TOPMOST, int(x), int(y), int(w), int(h),
                                   SWP_SHOWWINDOW | SWP_NOACTIVATE)
            except Exception as e:
                _log_file("splash make/move failed: %r" % (e,))
        self._on_ui_thread(fn)

    def _hide_splash(self):
        if self._splash_done:
            return
        self._splash_done = True

        def fn():
            try:
                if self._splash is not None:
                    self._splash.Hide()
                    self._splash.Dispose()
            except Exception:
                pass
            self._splash = None
            self._splash_label = None
        self._on_ui_thread(fn)

    def _splash_watch(self):
        """미니 창이 준비될 때까지 '로드중' 오버레이를 덮어둔다.

        준비 = WebView2 loaded + 주입 훅 적용(마스트헤드 숨김) + 영상 프레임
        확보(video.readyState>=2). 너무 오래 안 되면(45초) 안전하게 걷어내
        사용자가 조작할 수 있게 한다.
        """
        u = _user32()
        deadline = time.time() + 45
        last_query = 0.0
        last_rect = None
        while time.time() < deadline and not self._splash_done:
            try:
                if self._window not in webview.windows:
                    break
            except Exception:
                pass
            # 미니 창 위치/크기가 바뀔 때만 오버레이를 다시 맞춰 덮는다
            try:
                mh = self._hwnd_of(self._window)
                if mh and u is not None:
                    r = wintypes.RECT()
                    u.GetWindowRect(mh, ctypes.byref(r))
                    w, h = r.right - r.left, r.bottom - r.top
                    rect = (r.left, r.top, w, h)
                    if w > 0 and h > 0 and rect != last_rect:
                        last_rect = rect
                        self._make_or_move_splash(r.left, r.top, w, h)
            except Exception:
                pass
            # 준비 판정 (loaded 이후에만 질의, 과도한 호출 방지 위해 0.3s 간격)
            if self._engine_ok and (time.time() - last_query) >= 0.3:
                last_query = time.time()
                try:
                    rr = self._window.evaluate_js(
                        "(function(){try{var v=document.querySelector('video');"
                        "return (window.__miniHooked===true&&v&&v.readyState>=2)"
                        "?'1':'0';}catch(e){return '0';}})()")
                    if rr == "1":
                        break
                except Exception:
                    pass
            time.sleep(0.12)
        self._hide_splash()

    def _on_engine_loaded(self, window=None):
        """미니 창 loaded 이벤트: WebView2 정상 표시 + UI 주입."""
        self._engine_ok = True
        if self._config.get("udfResetCount"):
            self._config.update({"udfResetCount": 0})
            self._persist_later()
        self._inject_mini_hook()

    def _inject_mini_hook(self, window=None):
        try:
            js = MINI_HOOK_JS.replace("__STILL__", json.dumps({
                "on": bool(self._config.get("stillOn", False)),
                "sec": int(self._config.get("stillSec", 10)),
            }))
            # 광고 자동 건너뛰기(광고 영상 빨리감기) 사용 여부 — 기본 켜짐
            js = js.replace(
                "__ADFF__",
                "true" if self._config.get("adFastSkip", True) else "false")
            self._window.evaluate_js(js)
        except Exception:
            pass

    def play_in_mini(self, url, title=None):
        """브라우저 창에서 영상 클릭 시: 그 창을 숨기고 미니에서 재생.

        유튜브 뮤직에서 온 링크는 music.youtube.com 도메인을 유지해
        뮤직의 자동 재생목록(다음 곡)이 그대로 이어지게 한다.
        """
        m = YT_ID_RE.search(url or "")
        if m:
            host = ("music.youtube.com" if "music.youtube.com" in (url or "")
                    else "www.youtube.com")
            new = "https://%s/watch?v=%s" % (host, m.group(1))
            # 재생목록 컨텍스트 유지 — 다음 곡이 재생목록 순서로 이어진다
            lm = re.search(r"[?&]list=([A-Za-z0-9_-]+)", url or "")
            if lm:
                new += "&list=" + lm.group(1)
            url = new
        try:
            if self._browser is not None and self._browser in webview.windows:
                self._browser.hide()
        except Exception:
            pass
        try:
            self._window.restore()
            self._window.load_url(url)
            self._config.update({"lastUrl": url})
            self._persist_later()
        except Exception:
            pass


# ---- 자식 프로세스(WebView2) 정리 ----
# PyInstaller onefile 은 종료 시 _MEIxxxx 임시폴더를 지운다. 이때 살아 있는
# WebView2(msedgewebview2.exe) 자식이 그 폴더의 핸들을 쥐고 있으면 삭제가
# 실패해 'Failed to remove temporary directory' 경고가 뜬다. 또 이 자식들이
# WebView2 프로필(EBWebView)을 잠근 채 남으면 다음 실행이 엔진 초기화에
# 실패(0x8007139F 등)해 '복구 후 재시작' 루프에 빠진다. 종료·재시작 전에
# 반드시 정리해야 두 증상이 모두 사라진다.

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_TERMINATE = 0x0001


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


_K32 = None


def _kernel32_ex():
    """toolhelp/OpenProcess 전용 kernel32 인스턴스.

    _user32() 와 같은 이유로 프로세스 공유 windll.kernel32 에 시그니처를
    설정하면 다른 코드(pywebview 등)의 호출이 깨질 수 있어 별도 인스턴스에
    argtypes/restype 를 격리한다. Windows 가 아니면 None.
    """
    global _K32
    if _K32 is not None:
        return _K32
    if not hasattr(ctypes, "WinDLL"):
        return None
    try:
        k = ctypes.WinDLL("kernel32")
    except Exception:
        return None
    try:
        k.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PROCESSENTRY32W)]
        k.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PROCESSENTRY32W)]
        k.CloseHandle.argtypes = [ctypes.c_void_p]
        k.OpenProcess.restype = ctypes.c_void_p
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    except Exception:
        return None
    _K32 = k
    return k


def _descendant_procs(root_pid):
    """root_pid 의 모든 하위(자식·손자…) 프로세스를 (pid, exe소문자) 로 반환."""
    k = _kernel32_ex()
    if k is None:
        return []
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == ctypes.c_void_p(-1).value:
        return []
    procs = []   # (pid, ppid, name)
    try:
        pe = _PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        if not k.Process32FirstW(snap, ctypes.byref(pe)):
            return []
        while True:
            procs.append((pe.th32ProcessID, pe.th32ParentProcessID,
                          (pe.szExeFile or "").lower()))
            if not k.Process32NextW(snap, ctypes.byref(pe)):
                break
    except Exception:
        return []
    finally:
        try:
            k.CloseHandle(snap)
        except Exception:
            pass
    children = {}
    name_of = {}
    for pid, ppid, name in procs:
        children.setdefault(ppid, []).append(pid)
        name_of[pid] = name
    result, stack, seen = [], [root_pid], set()
    while stack:
        p = stack.pop()
        for c in children.get(p, ()):
            if c and c != root_pid and c not in seen:
                seen.add(c)
                result.append((c, name_of.get(c, "")))
                stack.append(c)
    return result


def _has_webview_children():
    """WebView2 자식이 살아 있는지 — 초기화가 '진행 중'인지 판별용."""
    try:
        return any(n == "msedgewebview2.exe"
                   for _pid, n in _descendant_procs(os.getpid()))
    except Exception:
        return False


def _kill_descendants(names=("msedgewebview2.exe",)):
    """현재 프로세스의 WebView2 자식을 종료해 프로필/임시폴더 잠금을 푼다.

    names=None 이면 모든 하위 프로세스를 종료. 기본은 WebView2 만 골라
    다른 프로그램에 영향이 없게 한다.
    """
    k = _kernel32_ex()
    if k is None:
        return
    want = set(n.lower() for n in names) if names else None
    try:
        for pid, name in _descendant_procs(os.getpid()):
            if want is not None and name not in want:
                continue
            try:
                h = k.OpenProcess(PROCESS_TERMINATE, False, pid)
                if h:
                    k.TerminateProcess(h, 0)
                    k.CloseHandle(h)
            except Exception:
                pass
    except Exception:
        pass


def _kill_profile_lockers():
    """이전 실행이 비정상 종료돼 남은, 우리 프로필을 잠근 WebView2 프로세스 정리.

    이런 프로세스(msedgewebview2.exe)가 EBWebView 프로필을 물고 있으면 새
    실행의 엔진 초기화가 실패해 '프로필 복구 후 재시작'이 반복된다. 명령줄에
    우리 프로필 폴더명(.yt_mini_profile)이 든 것만 골라 종료하므로 다른 앱의
    WebView2 는 건드리지 않는다.

    주의: 반드시 우리 WebView2 가 뜨기 전(webview.start 이전)에 호출할 것 —
    안 그러면 자기 자신의 엔진 프로세스까지 죽인다.
    """
    if not sys.platform.startswith("win"):
        return
    name = os.path.basename(PROFILE_DIR)         # 예: .yt_mini_profile
    safe = name.replace("'", "''")
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe'\" "
        "| Where-Object { $_.CommandLine -like '*%s*' } "
        "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }"
    ) % safe
    try:
        import subprocess
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            creationflags=0x08000000, timeout=20, check=False)  # CREATE_NO_WINDOW
        _log_file("kill_profile_lockers: 남은 WebView2 잠금 프로세스 정리 시도 (%s)"
                  % name)
    except Exception as e:
        _log_file("kill_profile_lockers failed: %r" % (e,))


_MUTEX = None


def _single_instance():
    """중복 실행 방지. 두 인스턴스가 같은 WebView2 프로필을 잡으면
    두 번째가 흰 창(엔진 초기화 실패)만 뜨므로, 이미 실행 중이면
    기존 창을 앞으로 가져오고 False 를 반환한다."""
    global _MUTEX
    try:
        k = ctypes.windll.kernel32
    except AttributeError:
        return True  # Windows 가 아님
    try:
        k.SetLastError(0)
        _MUTEX = k.CreateMutexW(None, False, "YTMini_SingleInstance")
        if k.GetLastError() != 183:      # ERROR_ALREADY_EXISTS
            return True
        # 이미 실행 중 → 종료 후 새로 시작할지 물어본다
        try:
            u = _user32()
            if u is None:
                return False
            hwnd = u.FindWindowW(None, "YT Mini")
            res = u.MessageBoxW(
                None,
                "YT Mini 가 이미 실행 중입니다.\n"
                "기존 실행을 종료하고 새로 시작할까요?",
                "YT Mini",
                0x24 | 0x40000,   # MB_YESNO | MB_ICONQUESTION | MB_TOPMOST
            )
            if res != 6:          # IDYES(6) 아님 → 기존 창만 앞으로 가져오고 종료
                if hwnd:
                    u.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
                    u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                   SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                                   | SWP_SHOWWINDOW)
                _log_file("already running - user kept old instance")
                return False
            # 예 → 기존 프로세스를 '트리째' 종료 후 계속 실행.
            # /T 로 자식(WebView2 msedgewebview2.exe)까지 함께 종료해야
            # 새 인스턴스가 프로필 잠금에 걸려 다시 흰 창이 되는 것을 막는다.
            import subprocess
            killed = False
            if hwnd:
                pid = wintypes.DWORD(0)
                u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value and pid.value != os.getpid():
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid.value)],
                        creationflags=0x08000000, check=False)  # CREATE_NO_WINDOW
                    killed = True
            if not killed and getattr(sys, "frozen", False):
                # 창 없는 좀비 exe 정리 (자기 자신 제외) — 트리째
                subprocess.run(
                    ["taskkill", "/F", "/T", "/FI", "IMAGENAME eq YTMini.exe",
                     "/FI", "PID ne %d" % os.getpid()],
                    creationflags=0x08000000, check=False)  # CREATE_NO_WINDOW
                killed = True
            _log_file("already running - killed old instance tree: %s" % killed)
            time.sleep(1.5)   # WebView2 자식 프로세스/프로필 잠금 정리 대기
            return True
        except Exception as e:
            _log_file("single_instance takeover failed: %r" % (e,))
            return False
    except Exception:
        return True


def _enable_dpi_awareness():
    """프로세스를 DPI 인식으로 설정 (창 생성 전에 호출).

    개발용 python.exe 는 매니페스트로 DPI 인식이 켜져 있지만
    PyInstaller exe 는 꺼져 있어 좌표가 가상화되고, WebView2 가 주는
    실제 픽셀 좌표와 어긋나 우클릭 메뉴가 화면 밖에 떠 버린다.
    """
    try:
        u = ctypes.windll.user32
    except AttributeError:
        return  # Windows 가 아님
    try:
        # Per-Monitor v2 (Windows 10 1703+)
        if u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
    except Exception:
        pass


def _hide_own_console():
    """더블클릭 실행으로 생긴 전용 콘솔 창만 숨긴다.

    기존 터미널(cmd/PowerShell)에서 실행한 경우에는 그 터미널까지 숨기면
    안 되므로, 이 콘솔을 쓰는 프로세스가 우리 하나뿐일 때만 숨긴다.
    (아예 콘솔 없이 실행하려면 pythonw youtube_mini.py 또는 .pyw 확장자 사용)
    """
    try:
        k = ctypes.windll.kernel32
    except AttributeError:
        return  # Windows 가 아님
    try:
        k.GetConsoleWindow.restype = ctypes.c_void_p
        hwnd = k.GetConsoleWindow()
        if not hwnd:
            return
        procs = (wintypes.DWORD * 4)()
        n = k.GetConsoleProcessList(procs, 4)
        if n == 1:
            ctypes.windll.user32.ShowWindow(ctypes.c_void_p(hwnd), SW_HIDE)
    except Exception:
        pass


def _relaunch():
    """뮤텍스를 풀고 자기 자신을 새 프로세스로 재실행."""
    global _MUTEX
    # 먼저 WebView2 자식을 정리한다 — 살아 있으면 EBWebView 프로필을 잠근
    # 채 남아 새 인스턴스의 엔진 초기화도 실패시켜 무한 재시작 루프가 된다
    # (스크린샷의 '이미 실행 중'+'임시폴더 삭제 실패' 연쇄 증상의 근본 원인).
    _kill_descendants()
    try:
        if _MUTEX:
            ctypes.windll.kernel32.CloseHandle(_MUTEX)
            _MUTEX = None
    except Exception:
        pass
    time.sleep(1.0)   # 자식 프로세스가 완전히 내려가 프로필 잠금이 풀릴 때까지
    import subprocess
    try:
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable])
        else:
            subprocess.Popen([sys.executable, os.path.abspath(__file__)])
    except Exception:
        pass
    os._exit(0)


def _engine_watchdog(api):
    """WebView2 초기화 실패(0x8007139F 등 → loaded 이벤트가 영영 안 옴)를
    감지해 엔진 프로필(EBWebView)을 초기화하고 자동 재시작한다."""
    # 콜드 스타트(첫 실행)/느린 PC(특히 ARM 에뮬레이션)는 30초를 넘길 수 있어
    # 우선 넉넉히 기다린다.
    for _ in range(30):
        time.sleep(1)
        if api._engine_ok:
            break
    # 아직이면: WebView2 자식이 살아 있으면 초기화가 '진행 중'이라는 뜻 —
    # 프로필을 지우고 재시작하는 대신, 자식이 살아 있는 한 최대 120초까지
    # 더 기다린다 (건강하지만 느린 실행을 오탐으로 날려 재시작 루프에 빠지는
    # 것을 막는다).
    waited = 30
    while not api._engine_ok and waited < 120 and _has_webview_children():
        time.sleep(2)
        waited += 2
    if api._engine_ok:
        # 미니(영상)는 정상인데 팝업 메뉴 창만 초기화에 실패한 경우 —
        # 우클릭해도 메뉴가 안 나오는 간헐 증상. 그대로 두면 재시작
        # 전까지 복구되지 않으므로 자동 재시작한다 (연속 2회 한도,
        # 메뉴가 정상 로드되면 카운터는 0 으로 복귀).
        if not api._menu_ok:
            count = int(api._config.get("menuResetCount", 0))
            api._config.update({"menuResetCount": count + 1})
            save_config(api._config)
            _log_file("engine watchdog: menu window not loaded in 20s"
                      " (relaunch %d/2)" % (count + 1,))
            if count < 2:
                _relaunch()
        return
    _log_file("engine watchdog: no loaded event in 20s (WebView2 init failure)")
    u = _user32()
    if u is None:
        return
    count = int(api._config.get("udfResetCount", 0))
    if count >= 2:
        try:
            u.MessageBoxW(
                None,
                "영상 엔진(WebView2) 초기화가 반복 실패했습니다.\n"
                "작업 관리자에서 msedgewebview2.exe 를 모두 종료하거나\n"
                "PC 를 재부팅한 뒤 다시 실행해 주세요.",
                "YT Mini", 0x30,
            )
        except Exception:
            pass
        return
    api._config.update({"resetUdf": True, "udfResetCount": count + 1})
    save_config(api._config)
    try:
        u.MessageBoxW(
            None,
            "영상 엔진(WebView2) 초기화에 실패해 프로필을 복구하고 "
            "다시 시작합니다.\n(유튜브 로그인은 다시 필요할 수 있어요)",
            "YT Mini", 0x40,
        )
    except Exception:
        pass
    _relaunch()


def _taskbar_above(u, mini):
    """작업표시줄이 미니와 겹친 채 z순서상 미니보다 위에 있는지."""
    try:
        rm = wintypes.RECT()
        u.GetWindowRect(mini, ctypes.byref(rm))
        hw = u.GetTopWindow(None)
        for _ in range(2000):
            if not hw:
                return False
            hw_i = int(hw)
            if hw_i == mini:
                return False
            buf = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(ctypes.c_void_p(hw_i), buf, 64)
            if (buf.value in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")
                    and u.IsWindowVisible(hw_i)):
                r = wintypes.RECT()
                u.GetWindowRect(ctypes.c_void_p(hw_i), ctypes.byref(r))
                if not (r.right <= rm.left or r.left >= rm.right
                        or r.bottom <= rm.top or r.top >= rm.bottom):
                    return True
            hw = u.GetWindow(ctypes.c_void_p(hw_i), GW_HWNDNEXT)
        return False
    except Exception:
        return False


def _keep_topmost(api):
    """'항상 위'가 켜져 있는 동안 작업표시줄 위 상태를 유지.

    작업표시줄도 최상위 창이라 클릭하면 그 위로 올라온다. 다만 매 주기
    무조건 z순서를 재배치하면 DWM 재합성으로 화면이 깜빡이므로,
    '작업표시줄이 실제로 미니를 덮고 있을 때만' 끌어올린다.
    """
    u = _user32()
    if u is None:
        return
    time.sleep(3)   # 창 핸들이 메인 스레드에서 만들어질 때까지 대기
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    while True:
        time.sleep(0.7)
        try:
            mh = api._hwnd_of(api._window)
            if not (mh and u.IsWindowVisible(mh)):
                continue
            if not api._config.get("onTop", True):
                # 항상 위가 꺼진 채 작업표시줄 뒤에 깔린 경우: 사용자가
                # 작업표시줄 아이콘으로 앱을 활성화하면 3초간 위로 꺼내줘
                # 잡아서 옮길 수 있게 한다
                fg = u.GetForegroundWindow()
                fg_root = int(u.GetAncestor(fg, GA_ROOT) or 0) if fg else 0
                if fg_root == mh and _taskbar_above(u, mh):
                    f = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                    u.SetWindowPos(mh, HWND_TOPMOST, 0, 0, 0, 0, f)
                    u.SetWindowPos(mh, None, 0, 0, 0, 0, f)
                    time.sleep(3)
                    if not api._config.get("onTop", True):   # 그 사이 안 켰으면 원복
                        u.SetWindowPos(mh, HWND_NOTOPMOST, 0, 0, 0, 0, f)
                continue
            if api._menu_open:      # 메뉴가 미니 위에 떠 있을 때 가리지 않게
                continue
            if not _taskbar_above(u, mh):
                continue            # 필요할 때만 재단언 → 깜빡임 없음
            # 1) 최상위 밴드 소속 보장  2) 밴드 '안'에서도 맨 위로.
            # (HWND_TOPMOST 만으로는 밴드 내 순서가 안 바뀜 — HWND_TOP 필요)
            u.SetWindowPos(mh, HWND_TOPMOST, 0, 0, 0, 0, flags)
            u.SetWindowPos(mh, None, 0, 0, 0, 0, flags)   # HWND_TOP
        except Exception:
            pass


def _keep_mini_injected(api):
    """미니 UI 주입 자가치유 루프.

    loaded 이벤트를 놓치거나 주입 스크립트가 실패해도 2초마다 재시도한다.
    스크립트 자체가 __miniHooked 가드로 멱등이라 중복 주입은 무해하다.
    """
    t = threading.Thread(target=_keep_topmost, args=(api,), daemon=True)
    t.start()
    t2 = threading.Thread(target=_engine_watchdog, args=(api,), daemon=True)
    t2.start()
    # 유튜브가 다 로드될 때까지 '로드중' 오버레이로 미니 창을 덮는다
    t3 = threading.Thread(target=api._splash_watch, daemon=True)
    t3.start()
    # 시작 시 저장된 불투명도 적용
    try:
        api._apply_opacity(int(api._config.get("opacity", 100)))
    except Exception as e:
        _log_file("apply_opacity failed: %r" % (e,))
    chrome_stripped = False
    tray_ready = False
    while True:
        # 미니 창이 닫혔으면 루프도 종료 — 프로세스가 좀비로 남지 않게
        try:
            if api._window not in webview.windows:
                return
        except Exception:
            pass
        try:
            api._inject_mini_hook()
        except Exception:
            pass
        # 창 핸들이 준비되면 한 번만: DWM 그림자/둥근 모서리 제거 + 앱 아이콘 적용
        if not chrome_stripped:
            try:
                mh = api._hwnd_of(api._window)
                if mh:
                    _strip_window_chrome(mh)
                    ip = _icon_path()
                    if ip:
                        native = getattr(api._window, "native", None)
                        if native is not None and hasattr(native, "BeginInvoke"):
                            import System

                            def _set_icon():
                                try:
                                    from System.Drawing import Icon
                                    native.Icon = Icon(ip)
                                except Exception:
                                    pass

                            native.BeginInvoke(System.Action(_set_icon))
                    chrome_stripped = True
            except Exception:
                chrome_stripped = True
        # 트레이 아이콘 상시 표시 — 창이 작업표시줄 뒤에 깔려도
        # 아이콘 우클릭 메뉴(항상 위 켜기/끄기 포함)로 항상 제어 가능
        if not tray_ready and chrome_stripped:
            try:
                tray_ready = api._ensure_notify_icon()
            except Exception:
                tray_ready = True
        # 마지막 시청 영상 + 재생 위치 저장 (파이썬 주도라 예외도 조용히 처리)
        try:
            url = api._window.get_current_url()
            if url and "/watch" in url:
                clean = re.sub(r"[&?]t=\d+s?", "", url)
                changed = False
                if clean != api._config.get("lastUrl"):
                    api._config.update({"lastUrl": clean, "lastTime": 0})
                    changed = True
                pv = api._window.evaluate_js(
                    "(function(){var v=document.querySelector('video');"
                    "return v ? ((v.paused?'1':'0')+'|'+Math.floor(v.currentTime||0)) : '';})()"
                )
                if pv and "|" in pv:
                    api._playing = pv[0] == "0"   # 트레이 메뉴 라벨용 캐시
                    t = int(pv.split("|", 1)[1])
                    if abs(t - int(api._config.get("lastTime", 0) or 0)) >= 5:
                        api._config.update({"lastTime": t})
                        changed = True
                if changed:
                    api._persist_later()
        except Exception:
            pass
        # 크기/위치 폴링 저장 — moved/resized 이벤트가 없는 환경이나
        # 네이티브 드래그(OS 가 직접 이동)에서도 확실히 저장되게 한다
        try:
            w = api._window
            geo = {"width": int(w.width), "height": int(w.height),
                   "x": int(w.x), "y": int(w.y)}
            if any(api._config.get(k) != v for k, v in geo.items()):
                api._config.update(geo)
                api._persist_later()
        except Exception:
            pass
        time.sleep(2)


def _dll_search_roots():
    roots = []
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        roots.append(mp)
    try:
        roots.append(os.path.dirname(os.path.abspath(webview.__file__)))
    except Exception:
        pass
    try:
        roots.append(os.path.dirname(os.path.abspath(sys.executable)))
    except Exception:
        pass
    out, seen = [], set()
    for r in roots:
        if r and r not in seen and os.path.isdir(r):
            seen.add(r)
            out.append(r)
    return out


def _bundled_dll_candidates(dll_name):
    """번들/설치 트리에서 dll_name 을 모두 찾아 경로 목록으로 반환 (대소문자 무시)."""
    target = (dll_name or "").lower()
    found = []
    for root in _dll_search_roots():
        try:
            for dirpath, _dirs, files in os.walk(root):
                for fn in files:
                    if fn.lower() == target:
                        found.append(os.path.join(dirpath, fn))
        except Exception:
            pass
    return found


def _dump_bundle_webview_dlls():
    """번들에 실제로 들어 있는 WebView2 관련 DLL 목록을 로그에 남긴다.

    'Cannot find win-arm64' 같은 실패가 났을 때, 무엇이 번들됐는지 확인해
    빌드 문제인지 경로 문제인지 진단하기 위한 것.
    """
    n = 0
    for root in _dll_search_roots():
        _log_file("  [bundle root] " + root)
        try:
            for dirpath, _dirs, files in os.walk(root):
                for fn in files:
                    low = fn.lower()
                    if low.endswith(".dll") and (
                            "webview2" in low or "webview2loader" in low):
                        _log_file("    dll: " + os.path.join(dirpath, fn))
                        n += 1
        except Exception:
            pass
    if n == 0:
        _log_file("  (WebView2 DLL 이 번들에 하나도 없음 — 빌드에서 누락됨)")


def _patch_pywebview_arch():
    """Windows on ARM 대응.

    pywebview 는 platform.machine()==ARM64 이면 win-arm64 인터롭 DLL 을
    찾는데, x64 로 빌드한 exe 를 ARM Windows 에서 에뮬레이션 실행하면 그
    폴더가 없어 'Cannot find win-arm64' 로 임포트 단계에서 죽는다
    (webview.util.interop_dll_path). WebView2 는 x64 에뮬레이션에서 정상
    동작하므로 번들된 x64 DLL 을 대신 쓰게 한다. edgechromium 모듈이
    임포트되기 전(webview.start 전)에 호출해야 효과가 있다.
    """
    # 아키텍처 판정은 이미 import 전에 _force_x64_arch_on_arm() 으로 x64 로
    # 맞춰 두었다. 여기서는 그래도 DLL 을 못 찾는 경우를 대비해
    # interop_dll_path 에 번들 탐색 폴백을 건다.
    try:
        from webview import util as _wvutil
    except Exception:
        return
    orig = getattr(_wvutil, "interop_dll_path", None)
    if orig is None or getattr(orig, "_arch_patched", False):
        return

    def interop_dll_path(dll_name):
        try:
            p = orig(dll_name)
            if p and os.path.exists(p):
                return p
        except Exception as e:
            _log_file("interop_dll_path 원본 실패(%s): %r" % (dll_name, e))
        cands = _bundled_dll_candidates(dll_name)
        # 네이티브 로더(WebView2Loader.dll)는 아키텍처별이라 '실제 이 프로세스가
        # 도는 아키텍처'에 맞춰 고른다. ARM Windows 에서 x64 로 빌드된 exe 는
        # 에뮬레이션이라 PROCESSOR_ARCHITECTURE 가 AMD64 → x64 사본을 쓴다.
        # 관리형(.NET) 어셈블리는 AnyCPU 라 아무 사본이나 무방하다.
        pa = (os.environ.get("PROCESSOR_ARCHITECTURE") or "").lower()
        if "arm" in pa:
            prefer = ("arm64",)
        elif pa == "x86":
            prefer = ("x86",)
        else:
            prefer = ("x64", "amd64")
        for cand in cands:
            if any(k in cand.lower() for k in prefer):
                _log_file("interop_dll_path: %s -> %s 대체 %s"
                          % (dll_name, prefer[0], cand))
                return cand
        # 선호 아키텍처가 없으면 x64 를 마지막 후보로 (에뮬레이션 호환)
        for cand in cands:
            low = cand.lower()
            if "arm64" not in low and any(k in low for k in ("x64", "amd64")):
                _log_file("interop_dll_path: %s -> x64 대체 %s" % (dll_name, cand))
                return cand
        if cands:
            _log_file("interop_dll_path: %s -> 대체 %s" % (dll_name, cands[0]))
            return cands[0]
        # 번들에서 못 찾음 — 무엇이 들어 있는지 진단 로그를 남기고 원래 예외 전파
        _log_file("interop_dll_path: '%s' 을(를) 번들에서 찾지 못함. 번들 내용:"
                  % dll_name)
        _dump_bundle_webview_dlls()
        return orig(dll_name)   # 최후엔 원래 예외를 그대로 전파

    interop_dll_path._arch_patched = True
    try:
        _wvutil.interop_dll_path = interop_dll_path
    except Exception:
        pass


MONITOR_DEFAULTTONULL = 0


def _pos_on_screen(x, y, w, h):
    """창 좌표가 실제 모니터 위에 있는지(완전히 화면 밖이 아닌지).

    검증할 수 없으면(비-Windows 등) True 로 둬서 저장값을 그대로 쓴다.
    """
    u = _user32()
    if u is None:
        return True
    pts = ((x + 8, y + 8),
           (x + max(1, w // 2), y + max(1, h // 2)),
           (x + max(0, w - 8), y + 8))
    for px, py in pts:
        try:
            if u.MonitorFromPoint(wintypes.POINT(int(px), int(py)),
                                  MONITOR_DEFAULTTONULL):
                return True
        except Exception:
            return True
    return False


def _valid_geometry(cfg):
    """저장된 창 크기/위치를 검증해 (width, height, x|None, y|None) 반환.

    - 기본값은 '기본 크기' 메뉴와 동일한 BASE_W x BASE_H.
    - 사용자가 저장한 크기가 있으면 그대로 사용한다.
    - 값이 손상됐으면(정수 아님/0 이하/비현실적으로 큼) 기본 크기로 되돌린다.
      (손잡이로 줄인 작은 값 >=MIN 은 사용자의 선택이므로 존중한다.)
    - 위치가 완전히 화면 밖이면 폐기(None)해 자동 배치되게 한다.
    """
    try:
        w = int(cfg.get("width", BASE_W))
        h = int(cfg.get("height", BASE_H))
    except (TypeError, ValueError):
        w, h = BASE_W, BASE_H
    if not (MIN_W <= w <= 20000) or not (MIN_H <= h <= 20000):
        _log_file("저장된 창 크기가 이상해 기본 크기로 복원 (w=%r h=%r)"
                  % (cfg.get("width"), cfg.get("height")))
        w, h = BASE_W, BASE_H
    x, y = cfg.get("x"), cfg.get("y")
    try:
        x, y = int(x), int(y)
    except (TypeError, ValueError):
        return w, h, None, None
    if not _pos_on_screen(x, y, w, h):
        _log_file("저장된 창 위치가 화면 밖이라 자동 배치 (x=%d y=%d)" % (x, y))
        return w, h, None, None
    return w, h, x, y


def main():
    # 중복 실행이면 종료 — 두 인스턴스가 같은 WebView2 프로필을 잡으면
    # 두 번째가 0x8007139F(컨트롤러 생성 실패)로 흰 창만 뜬다.
    if not _single_instance():
        return
    # DPI 인식은 어떤 창보다 먼저 설정해야 한다 (exe 좌표 어긋남 방지)
    _enable_dpi_awareness()
    # 더블클릭 실행 시 뜨는 콘솔 창 숨김
    _hide_own_console()
    # pywebview 내부 오류도 로그 파일에 수집 — 콘솔 없는 exe 에서도
    # 우클릭 메뉴의 '로그 보기'로 확인할 수 있다
    try:
        import logging
        os.makedirs(PROFILE_DIR, exist_ok=True)
        handler = logging.FileHandler(
            os.path.join(PROFILE_DIR, "mini.log"), encoding="utf-8")
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                               datefmt="%H:%M:%S"))
        logging.getLogger("pywebview").addHandler(handler)
    except Exception:
        pass
    # 사용자 클릭 없이도 소리 있는 자동재생을 허용 (WebView2 전용 플래그)
    os.environ.setdefault(
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "--autoplay-policy=no-user-gesture-required",
    )
    _log_file("YT Mini 시작 — version %s (frozen=%s, updated=%s)"
              % (VERSION, getattr(sys, "frozen", False),
                 bool(os.environ.get("YTMINI_RUNNING_UPDATE"))))
    # 최신본은 백그라운드로 받아 '다음 실행'에 적용 — 시작이 느려지지 않게
    threading.Thread(target=_background_update_fetch, daemon=True).start()
    # ARM Windows(에뮬레이션 실행)에서 win-arm64 인터롭 DLL 을 못 찾아
    # webview.start 가 죽는 문제 방지 — 반드시 창 생성/start 전에 적용
    _patch_pywebview_arch()

    # 설정 파일 존재 여부로 '최초 실행'을 판정 (config 를 쓰기 전에 확인).
    first_run = not os.path.exists(CONFIG_PATH)
    cfg = load_config()
    # 이전 실행이 비정상 종료돼 우리 프로필을 잠근 채 남은 WebView2 프로세스를
    # 먼저 정리 — 이게 남아 있으면 이번 실행의 엔진 초기화도 실패해
    # '프로필 복구 후 재시작'이 반복된다. (우리 WebView2 가 뜨기 전에 호출)
    _kill_profile_lockers()
    # 지난 실행에서 엔진 초기화 실패로 프로필 복구가 예약된 경우:
    # 이전 프로세스(웹뷰 포함)가 완전히 내려간 뒤 엔진 데이터만 삭제.
    # 이전 인스턴스의 WebView2 자식이 늦게 내려가 프로필이 잠겨 있으면
    # 한 번의 rmtree 는 조용히 실패하므로(ignore_errors) 몇 번 재시도한다.
    if cfg.pop("resetUdf", False):
        import shutil
        target = os.path.join(PROFILE_DIR, "EBWebView")
        removed = False
        for _ in range(6):
            time.sleep(1.0)
            shutil.rmtree(target, ignore_errors=True)
            if not os.path.exists(target):
                removed = True
                break
        save_config(cfg)
        _log_file("EBWebView profile reset %s"
                  % ("done" if removed else "FAILED (프로필 잠금 지속)"))
    start_url = cfg.get("lastUrl") or DEFAULT_URL
    # 마지막 재생 위치에서 이어보기 (2초 여유를 두고 되감기)
    last_t = int(cfg.get("lastTime", 0) or 0)
    if cfg.get("lastUrl") and last_t > 5 and "t=" not in start_url:
        start_url += ("&" if "?" in start_url else "?") + "t=%ds" % max(0, last_t - 2)

    # 창 크기/위치 결정:
    #  - 최초 실행: 무조건 기본 크기(BASE)로 고정, 위치는 자동 배치.
    #  - 이후 실행: 저장된 사용자 크기 사용, 손상/화면밖이면 다시 기본으로.
    # 결정값을 설정에도 반영해 이후 저장/복원이 일관되게 한다.
    if first_run:
        win_w, win_h, win_x, win_y = BASE_W, BASE_H, None, None
        _log_file("최초 실행 — 창 크기를 기본 크기로 고정 (%dx%d)" % (BASE_W, BASE_H))
    else:
        win_w, win_h, win_x, win_y = _valid_geometry(cfg)
    cfg["width"], cfg["height"] = win_w, win_h
    if win_x is None:
        cfg.pop("x", None)
        cfg.pop("y", None)
    else:
        cfg["x"], cfg["y"] = win_x, win_y

    api = Api(cfg)
    window = webview.create_window(
        "YT Mini",
        url=start_url,
        js_api=api,
        width=win_w,
        height=win_h,
        x=win_x,
        y=win_y,
        on_top=bool(cfg.get("onTop", True)),
        resizable=True,
        min_size=(MIN_W, MIN_H),
        frameless=True,
        # 창 이동은 주입한 실드가 begin_move/move_delta 로 직접 처리
        # (유튜브 플레이어가 이벤트를 삼켜 easy_drag 는 동작하지 않음)
        easy_drag=False,
    )
    api._window = window
    # 팝업 메뉴 창은 반드시 시작 전에 생성 (화면 밖 좌표라 보이지 않음).
    # 실행 중 생성은 WebView2 초기화가 꼬여 드래그까지 죽는 사고가 있었다.
    api._ensure_menu()
    # 시청 페이지가 로드될 때마다 미니 UI(CSS/실드/손잡이) 주입
    # (+ loaded 수신 = WebView2 정상이라는 신호로 워치독에 사용)
    try:
        window.events.loaded += api._on_engine_loaded
    except AttributeError:
        window.loaded += api._on_engine_loaded
    # 창 크기/위치 변경을 저장 (구버전 pywebview 는 moved 이벤트가 없을 수 있음)
    for event_name in ("resized", "moved"):
        try:
            event = getattr(window.events, event_name)
            event += api.on_geometry_change
        except Exception:
            pass

    # 로그인 세션(쿠키)을 유지해 홈/구독 창에서 한 번 로그인하면 계속 사용.
    os.makedirs(PROFILE_DIR, exist_ok=True)
    webview.start(_keep_mini_injected, (api,), private_mode=False, storage_path=PROFILE_DIR)

    # GUI 루프 종료(모든 창 닫힘) 후: 남은 백그라운드 스레드와 무관하게
    # 프로세스를 확실히 종료해 좀비(뮤텍스 잔류 → '이미 실행 중' 팝업) 방지.
    # 종료 전 WebView2 자식을 정리해 _MEI 임시폴더 삭제 실패 경고를 막는다.
    try:
        save_config(api._config)
    except Exception:
        pass
    _kill_descendants()
    time.sleep(1.0)   # 자식이 _MEI 핸들을 놓을 시간 (임시폴더 삭제 실패 경고 방지)
    os._exit(0)


if __name__ == "__main__":
    main()
