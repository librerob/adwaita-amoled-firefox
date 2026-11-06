"""Exercise the packaged theme in an isolated Firefox profile via Marionette.

No browser driver or Python packages are needed. Never point this at a daily profile.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from contrast import over, ratio, rgba
from theme import THEME_ID, manifest, package


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
          outline:s.outlineColor, outlineWidth:s.outlineWidth, outlineStyle:s.outlineStyle,
          opacity:s.opacity, width:el.getBoundingClientRect().width};
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

TEXT_PAINT = """
const parentOf = node => node.assignedSlot || node.parentElement || node.getRootNode()?.host;
const textPaint = (el, pseudo=null, boundary=null, baseBackground='#000000') => {
  const s=win.getComputedStyle(el,pseudo);
  let opacity=Number(s.opacity), backgrounds=[];
  if(!pseudo) backgrounds.push(s.backgroundColor);
  for(let parent=pseudo ? el : parentOf(el);parent;parent=parentOf(parent)) {
    const ps=win.getComputedStyle(parent);
    opacity*=Number(ps.opacity);
    backgrounds.push(ps.backgroundColor);
    if(parent===boundary) break;
  }
  return {text:pseudo==='::placeholder' ? el.getAttribute('placeholder') : pseudo ? s.content : el.textContent || el.getAttribute('value') || '',
          selector:el.id || el.className?.baseVal || String(el.className), pseudo,
          color:s.color,opacity,backgrounds,baseBackground};
};
const deepElements = root => [...root.children,...(root.shadowRoot?.children || [])]
  .flatMap(el=>[el,...deepElements(el)]);
"""


def measure_text(samples, state, report):
    if not samples:
        raise AssertionError(f"No visible text sampled for {state}")
    for sample in samples:
        background = rgba(sample.get("baseBackground", "#000000"))
        for layer in reversed(sample["backgrounds"]):
            background = over(layer, background)
        foreground = rgba(sample["color"])
        foreground = foreground[:3] + (foreground[3] * sample["opacity"],)
        value = ratio(over(foreground, background), background)
        result = dict(sample, state=state, ratio=value)
        report["runtimePairs"].append(result)
        assert value >= 4.5, (state, sample["text"], value, sample)


def screenshot(client, target, height=None):
    if getattr(client, "desktop_captures", False) and not target.name.startswith("preview-"):
        # XUL popup widgets are absent from drawWindow's document-only capture.
        client.js(WINDOW + "return new Promise(resolve=>win.requestAnimationFrame(()=>win.requestAnimationFrame(()=>resolve(true))));")
        subprocess.run(["import", "-window", "root", str(target)], check=True, timeout=10)
        return
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
    parser.add_argument("--headed", action="store_true", help="Run with a display; Linux captures require ImageMagick's import command")
    args = parser.parse_args()
    if args.headed and (not os.environ.get("DISPLAY") or not shutil.which("import")):
        parser.error("--headed requires an isolated X11 display and ImageMagick import")
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
            "browser.search.suggest.enabled": False,
            "browser.urlbar.suggest.searches": False,
            "browser.urlbar.speculativeConnect.enabled": False,
        }
        Path(temp, "user.js").write_text("".join(f"user_pref({json.dumps(k)}, {json.dumps(v)});\n" for k, v in prefs.items()))
        environment = dict(os.environ, MOZ_REMOTE_ALLOW_SYSTEM_ACCESS="1", MOZ_NO_REMOTE="1")
        log = open(output / "firefox.log", "w", encoding="utf-8")
        command = [args.firefox] + ([] if args.headed else ["--headless"]) + ["--marionette", "--no-remote", "--profile", temp, "--width", "1360", "--height", "900", "about:blank"]
        process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
        client = None
        try:
            client = Marionette(port, process)
            client.desktop_captures = args.headed
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
                    assert tab["outlineStyle"] not in ("none", "hidden"), tab
                    assert float(tab["outlineWidth"].removesuffix("px")) >= 1, tab
                    assert ratio(over(tab["outline"], tab_bg), tab_bg) >= 3, tab
                    assert rgba(tab["outline"])[:3] == rgba(manifest()["theme"]["colors"]["tab_line"])[:3], tab
                    report["runtimePairs"].append({"state": sample["name"], "role": "selected tab label", "ratio": value})
                    report["samples"].append(sample)
                    screenshot(client, output / (sample["name"] + ".png"))
                    if system_mode == 1 and not compact:
                        screenshot(client, output / f"preview-{'vertical' if vertical else 'horizontal'}.png", 520 if vertical else 180)
            client.js(WINDOW + "win.gURLBar.focus(); win.gURLBar.inputField.select(); return true;")
            client.wait(WINDOW + "return doc.activeElement && (doc.activeElement.id === 'urlbar-input' || doc.activeElement.closest('#urlbar'));")
            screenshot(client, output / "address-focus.png")
            placeholder = client.js(WINDOW + TEXT_PAINT + "return textPaint(doc.getElementById('urlbar-input'),'::placeholder',doc.getElementById('urlbar'),win.getComputedStyle(doc.documentElement).getPropertyValue('--toolbar-field-background-color-focus').trim());")
            measure_text([placeholder], "address placeholder", report)
            client.js(WINDOW + """
              const {PlacesUtils}=ChromeUtils.importESModule('resource://gre/modules/PlacesUtils.sys.mjs');
              return PlacesUtils.history.insert({url:'https://example.test/amoled-reading',
                title:'AMOLED reading notes',visits:[{date:new Date()}]}).then(()=>{
                  win.gURLBar.value='amoled'; return win.gURLBar.startQuery();
                });
            """)
            client.wait(WINDOW + "return win.gURLBar.view.isOpen && [...doc.querySelectorAll('.urlbarView-row')].some(row=>row.getClientRects().length && row.textContent.includes('AMOLED reading notes'));")
            client.js(WINDOW + "const rows=[...doc.querySelectorAll('.urlbarView-row')].filter(row=>row.getClientRects().length); win.gURLBar.view.selectedRowIndex=rows.findIndex(row=>row.textContent.includes('AMOLED reading notes')); return true;")
            selected_result = client.js(WINDOW + TEXT_PAINT + """
              const row=doc.querySelector('.urlbarView-row[selected]');
              if(!row) throw new Error('Address result was not selected');
              return [...row.querySelectorAll('.urlbarView-title,.urlbarView-url,.urlbarView-action')]
                .filter(el=>el.getClientRects().length && el.textContent.trim()).map(el=>textPaint(el,null,row,
                  win.getComputedStyle(doc.documentElement).getPropertyValue('--toolbar-field-background-color-focus').trim()));
            """)
            measure_text(selected_result, "selected address result", report)
            screenshot(client, output / "selected-address-result.png", 520)
            client.js(WINDOW + "win.gURLBar.view.close(); return true;")
            client.js(WINDOW + "win.gURLBar.blur(); win.PanelUI.show(); return true;")
            client.wait(WINDOW + "return doc.getElementById('appMenu-popup').state === 'open';")
            menu = client.js(WINDOW + "const el=doc.getElementById('appMenu-popup'); const s=win.getComputedStyle(el); return {color:s.color,background:s.backgroundColor};")
            report["menu"] = menu
            screenshot(client, output / "menu.png")
            menu_text = client.js(WINDOW + TEXT_PAINT + """
              const panel=doc.getElementById('appMenu-popup');
              const row=[...panel.querySelectorAll('toolbarbutton.subviewbutton')].find(el=>
                el.getClientRects().length && !el.disabled && el.getAttribute('shortcut'));
              if(!row) throw new Error('No enabled menu row with a shortcut');
              win.InspectorUtils.addPseudoClassLock(row,':hover');
              const elements=deepElements(row).filter(el=>el.getClientRects().length &&
                (el.classList?.contains('toolbarbutton-text') || el.classList?.contains('toolbarbutton-accel')));
              const base=win.getComputedStyle(doc.documentElement).getPropertyValue('--panel-background-color').trim();
              let samples=elements.map(el=>textPaint(el,null,row,base));
              for(const pseudo of ['::before','::after']) {
                const s=win.getComputedStyle(row,pseudo);
                if(s.content && !['none','normal','""'].includes(s.content)) samples.push(textPaint(row,pseudo,row,base));
              }
              return {row:row.id,samples};
            """)
            report["selectedMenuRow"] = menu_text
            measure_text(menu_text["samples"], "hovered menu row and shortcut", report)
            screenshot(client, output / "selected-menu.png")
            client.js(WINDOW + "win.InspectorUtils.removePseudoClassLock(doc.getElementById(arguments[0]),':hover'); return true;", menu_text["row"])
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

