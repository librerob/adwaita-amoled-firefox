"""Exercise the packaged theme in an isolated Firefox profile via Marionette.

No browser driver or Python packages are needed. Never point this at a daily profile.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from contrast import over, ratio, rgba
from theme import THEME_ID, package


class Marionette:
    def __init__(self, port, process):
        deadline = time.monotonic() + 45
        while True:
            try:
                self.socket = socket.create_connection(("127.0.0.1", port), timeout=2)
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Firefox did not start Marionette")
                time.sleep(0.2)
        self.socket.settimeout(45)
        self.counter = 0
        self.receive()  # Server greeting precedes command frames.
        self.session = self.command("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {"browserName": "firefox"}}})
        self.command("Marionette:SetContext", {"value": "chrome"})

    def receive(self):
        length = bytearray()
        while True:
            char = self.socket.recv(1)
            if not char:
                raise EOFError("Marionette connection closed")
            if char == b":":
                break
            length.extend(char)
        remaining = int(length)
        data = bytearray()
        while remaining:
            chunk = self.socket.recv(remaining)
            if not chunk:
                raise EOFError("Incomplete Marionette frame")
            data.extend(chunk)
            remaining -= len(chunk)
        return json.loads(data)

    def command(self, name, parameters=None):
        self.counter += 1
        data = json.dumps([0, self.counter, name, parameters or {}]).encode()
        self.socket.sendall(str(len(data)).encode() + b":" + data)
        kind, identifier, error, result = self.receive()
        assert kind == 1 and identifier == self.counter
        if error:
            raise RuntimeError(f"{name}: {error}")
        return result

    def js(self, script, *args):
        result = self.command("WebDriver:ExecuteScript", {"script": script, "args": list(args), "newSandbox": True, "sandbox": "default"})
        return result.get("value") if isinstance(result, dict) and set(result) == {"value"} else result

    def wait(self, script, *args):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            result = self.js(script, *args)
            if result:
                return result
            time.sleep(0.1)
        raise AssertionError(f"Timed out: {script}")


WINDOW = "const win = Services.wm.getMostRecentWindow('navigator:browser'); const doc = win.document;"
SAMPLE = WINDOW + """
const style = selector => {
  const el = doc.querySelector(selector);
  if (!el || !el.getClientRects().length) throw new Error('Missing visible element: ' + selector);
  const s = win.getComputedStyle(el);
  return {selector, color:s.color, background:s.backgroundColor, border:s.borderColor,
          outline:s.outlineColor, opacity:s.opacity, width:el.getBoundingClientRect().width};
};
const root = win.getComputedStyle(doc.documentElement);
return {
  theme:doc.documentElement.getAttribute('lwtheme'),
  nova:Services.prefs.getBoolPref('browser.nova.enabled',false),
  vertical:Services.prefs.getBoolPref('sidebar.verticalTabs',false),
  density:Services.prefs.getIntPref('browser.uidensity',0),
  private:ChromeUtils.importESModule('resource://gre/modules/PrivateBrowsingUtils.sys.mjs').PrivateBrowsingUtils.isWindowPrivate(win),
  variables:Object.fromEntries(['--lwt-accent-color','--toolbar-background-color',
    '--toolbar-field-background-color','--toolbar-field-background-color-focus',
    '--lwt-tab-line-color','--tab-background-color-selected','--sidebar-background-color',
    '--urlbarview-background-color-selected','--urlbarview-text-color-selected'].map(k=>[k,root.getPropertyValue(k).trim()])),
  labels:[style('.tabbrowser-tab[selected] .tab-label'),style('#urlbar-input'),style('#nav-bar')],
  selectedTab:style('.tabbrowser-tab[selected] .tab-background')
};
"""


def screenshot(client, target, height=None):
    data = client.js(WINDOW + """
      const root=doc.documentElement;
      const restoreCue=arguments[1] && root.hasAttribute('remotecontrol');
      if(restoreCue) root.removeAttribute('remotecontrol');
      try {
        const canvas = doc.createElementNS('http://www.w3.org/1999/xhtml','canvas');
        canvas.width=win.innerWidth; canvas.height=Math.min(win.innerHeight,arguments[0] || win.innerHeight);
        canvas.getContext('2d').drawWindow(win,0,0,canvas.width,canvas.height,'rgb(0,0,0)');
        return canvas.toDataURL('image/png').split(',')[1];
      } finally {
        if(restoreCue) root.setAttribute('remotecontrol','true');
      }
    """, height, target.name.startswith("preview-"))
    target.write_bytes(base64.b64decode(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firefox", required=True)
    parser.add_argument("--output", default="artifacts/firefox")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    xpi = package()
    report = {"samples": [], "runtimePairs": [], "scope": "Native browser chrome, isolated profile; physical OLED and screen-reader behavior not measured."}
    with tempfile.TemporaryDirectory(prefix="amoled-firefox-") as temp:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        prefs = {
            "marionette.port": port,
            "browser.shell.checkDefaultBrowser": False,
            "browser.startup.page": 0,
            "browser.startup.homepage_override.mstone": "ignore",
            "browser.aboutwelcome.enabled": False,
            "browser.nova.enabled": True,
            "browser.newtabpage.activity-stream.feeds.section.topstories": False,
            "browser.newtabpage.activity-stream.showSponsored": False,
            "browser.newtabpage.activity-stream.showSponsoredTopSites": False,
            "datareporting.policy.dataSubmissionEnabled": False,
            "toolkit.telemetry.enabled": False,
            "browser.tabs.warnOnClose": False,
        }
        Path(temp, "user.js").write_text("".join(f"user_pref({json.dumps(k)}, {json.dumps(v)});\n" for k, v in prefs.items()))
        environment = dict(os.environ, MOZ_REMOTE_ALLOW_SYSTEM_ACCESS="1", MOZ_NO_REMOTE="1")
        log = open(output / "firefox.log", "w", encoding="utf-8")
        process = subprocess.Popen([args.firefox, "--headless", "--marionette", "--no-remote", "--profile", temp, "--width", "1360", "--height", "900", "about:blank"], env=environment, stdout=log, stderr=subprocess.STDOUT)
        client = None
        try:
            client = Marionette(port, process)
            report["session"] = client.session
            result = client.command("Addon:Install", {"path": str(xpi), "temporary": True})
            report["install"] = result
            client.js("return ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs').AddonManager.getAddonByID(arguments[0]).then(a=>a.enable());", THEME_ID)
            client.wait(WINDOW + "return doc.documentElement.hasAttribute('lwtheme');")
            client.js(WINDOW + """
              const principal=Services.scriptSecurityManager.getSystemPrincipal();
              const page = title => 'data:text/html,'+encodeURIComponent('<!doctype html><meta name="color-scheme" content="dark"><title>'+title+'</title><style>body{background:#000;color:#e6e6e6;font:18px system-ui;padding:70px}h1{font-size:32px;font-weight:500}p{color:#c0c0c0;line-height:1.7}a{color:#8ab4f8}</style><h1>'+title+'</h1><p>A quiet frame for the web.</p><p>Adwaita AMOLED for Firefox</p>');
              win.gBrowser.selectedBrowser.loadURI(Services.io.newURI('about:newtab'), {triggeringPrincipal:principal});
              for(const title of ['Reading list','Notes']) win.gBrowser.addTab(page(title),{triggeringPrincipal:principal});
              return true;
            """)
            client.wait(WINDOW + "return win.gBrowser.tabs.length >= 3 && win.gBrowser.selectedBrowser.currentURI.spec === 'about:newtab';")
            for system_mode in (1, 0):  # Firefox's ui.systemUsesDarkTheme override, confined to this profile.
                client.js("Services.prefs.setIntPref('ui.systemUsesDarkTheme',arguments[0]); return true;", system_mode)
                for vertical, compact in ((False, False), (True, False), (True, True)):
                    client.js("Services.prefs.setBoolPref('sidebar.verticalTabs',arguments[0]); Services.prefs.setIntPref('browser.uidensity',arguments[1]); return true;", vertical, int(compact))
                    client.wait(WINDOW + "return Services.prefs.getBoolPref('sidebar.verticalTabs',false) === arguments[0] && Services.prefs.getIntPref('browser.uidensity',0) === arguments[1];", vertical, int(compact))
                    time.sleep(0.5)
                    sample = client.js(SAMPLE)
                    sample["name"] = f"{'dark' if system_mode else 'light'}-{'vertical' if vertical else 'horizontal'}-{'compact' if compact else 'normal'}"
                    assert sample["nova"], "Nova must be enabled in the test profile"
                    assert sample["vertical"] == vertical
                    for variable in ("--lwt-accent-color", "--toolbar-background-color"):
                        assert rgba(sample["variables"][variable])[:3] == (0, 0, 0), sample
                    tab = sample["selectedTab"]
                    tab_bg = over(tab["background"], "#000000")
                    label = sample["labels"][0]
                    value = ratio(over(label["color"], tab_bg), tab_bg)
                    assert value >= 4.5, (sample["name"], value)
                    report["runtimePairs"].append({"state": sample["name"], "role": "selected tab label", "ratio": value})
                    report["samples"].append(sample)
                    screenshot(client, output / (sample["name"] + ".png"))
                    if system_mode == 1 and not compact:
                        screenshot(client, output / f"preview-{'vertical' if vertical else 'horizontal'}.png", 520 if vertical else 180)
            client.js(WINDOW + "win.gURLBar.focus(); win.gURLBar.inputField.select(); return true;")
            client.wait(WINDOW + "return doc.activeElement && (doc.activeElement.id === 'urlbar-input' || doc.activeElement.closest('#urlbar'));")
            screenshot(client, output / "address-focus.png")
            client.js(WINDOW + "win.gURLBar.blur(); win.PanelUI.show(); return true;")
            client.wait(WINDOW + "return doc.getElementById('appMenu-popup').state === 'open';")
            menu = client.js(WINDOW + "const el=doc.getElementById('appMenu-popup'); const s=win.getComputedStyle(el); return {color:s.color,background:s.backgroundColor};")
            report["menu"] = menu
            screenshot(client, output / "menu.png")
            client.js(WINDOW + "win.PanelUI.hide(); Services.prefs.setBoolPref('sidebar.verticalTabs',false); return true;")
            client.js(WINDOW + "win.OpenBrowserWindow({private:true}); return true;")
            client.wait(WINDOW + "return ChromeUtils.importESModule('resource://gre/modules/PrivateBrowsingUtils.sys.mjs').PrivateBrowsingUtils.isWindowPrivate(win) && doc.documentElement.hasAttribute('lwtheme');")
            report["private"] = client.js(SAMPLE)
            screenshot(client, output / "private.png")
            client.js(WINDOW + "win.close(); return true;")
            client.command("Addon:Uninstall", {"id": THEME_ID})
            client.wait(WINDOW + "return !doc.documentElement.hasAttribute('lwtheme');")
            report["uninstalled"] = True
            print(f"Firefox UI passed: {len(report['samples'])} layout/system combinations, address focus, menu, private window and removal.")
        except Exception as error:
            report["error"] = str(error)
            if client:
                try:
                    screenshot(client, output / "failure.png")
                except Exception:
                    pass
            raise
        finally:
            (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            if client:
                try:
                    client.command("Marionette:Quit", {"flags": ["eForceQuit"]})
                except (RuntimeError, EOFError, OSError):
                    pass
                client.socket.close()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                # End only this fixture's process tree if graceful shutdown stalls.
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
                else:
                    process.kill()
                process.wait()
            log.close()


if __name__ == "__main__":
    main()

