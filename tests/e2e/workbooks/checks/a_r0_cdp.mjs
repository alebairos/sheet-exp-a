// A headless browser for the a-r0-spreadsheet check, Node standard library only: the app served by web/io/serve.py
// and Chrome/Chromium driven over the DevTools protocol on a pipe (--remote-debugging-pipe, no WebSocket).
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import net from "node:net";

// $CHROME first, then the usual names on PATH.
export function findBrowser() {
  const names = [process.env.CHROME, "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"];
  for (const n of names.filter(Boolean)) {
    try { return execFileSync("sh", ["-c", 'command -v "$0"', n], { encoding: "utf8" }).trim() || null; } catch {}
  }
  return null;
}

const freePort = () => new Promise((ok) => { const s = net.createServer().listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => ok(p)); }); });

// python3 web/io/serve.py <port>; resolves once it prints its "Serving" line.
export async function serve() {
  const port = await freePort();
  const p = spawn("python3", ["web/io/serve.py", String(port)], { stdio: ["ignore", "pipe", "ignore"] });
  await new Promise((ok, no) => {
    p.stdout.on("data", (d) => { if (/Serving/.test(String(d))) ok(); });
    p.on("exit", (c) => no(new Error("serve.py exited " + c)));
  });
  return { url: `http://127.0.0.1:${port}`, close: () => p.kill() };
}

// Launches the browser and attaches to its page; send(method, params) -> result, on(event, fn).
export async function launch(browser) {
  const profile = mkdtempSync(join(tmpdir(), "a-r0-profile-"));
  const args = ["--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--no-first-run",
    "--remote-debugging-pipe", `--user-data-dir=${profile}`, "--window-size=1200,900", "about:blank"];
  const proc = spawn(browser, args, { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
  const out = proc.stdio[3], inp = proc.stdio[4];
  let id = 0, buf = "", sessionId;
  const waiting = new Map(), handlers = [];
  inp.on("data", (d) => {
    buf += d;
    let i;
    while ((i = buf.indexOf("\0")) >= 0) {
      const m = JSON.parse(buf.slice(0, i));
      buf = buf.slice(i + 1);
      if (m.id && waiting.has(m.id)) { const [ok, no] = waiting.get(m.id); waiting.delete(m.id); m.error ? no(new Error(JSON.stringify(m.error))) : ok(m.result); }
      else if (m.method) for (const [ev, fn] of handlers) if (ev === m.method) fn(m.params);
    }
  });
  const raw = (method, params = {}, sid) => new Promise((ok, no) => {
    const msg = { id: ++id, method, params };
    if (sid) msg.sessionId = sid;
    waiting.set(msg.id, [ok, no]);
    out.write(JSON.stringify(msg) + "\0");
  });
  let targets = [];
  for (let t = 0; t < 100 && !targets.length; t++) {
    targets = (await raw("Target.getTargets")).targetInfos.filter((x) => x.type === "page");
    if (!targets.length) await sleep(100);
  }
  if (!targets.length) throw new Error("the browser opened no page");
  sessionId = (await raw("Target.attachToTarget", { targetId: targets[0].targetId, flatten: true })).sessionId;
  return {
    send: (method, params) => raw(method, params, method.startsWith("Browser.") ? undefined : sessionId),
    on: (ev, fn) => handlers.push([ev, fn]),
    close: () => proc.kill(),
  };
}

export const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));
