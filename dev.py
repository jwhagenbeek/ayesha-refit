#!/usr/bin/env python3
"""Local dev server with auto reload: python3 dev.py [port]

Serves this folder like `python3 -m http.server`, but:
- every page reloads by itself when a file in this folder changes;
- nothing is cached, and the app's service worker is switched off,
  so you always see the files as they are on disk.
Only for localhost; the live site is not affected.
"""
import http.server, os, socketserver, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

SNIPPET = b"""<script>
/* dev.py: no service worker on localhost, and reload when files change */
(function () {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register = function () { return Promise.resolve(); };
    navigator.serviceWorker.getRegistrations().then(function (rs) {
      if (rs.length) Promise.all(rs.map(function (r) { return r.unregister(); }))
        .then(function () { return window.caches ? caches.keys().then(function (ks) { return Promise.all(ks.map(function (k) { return caches.delete(k); })); }) : 0; })
        .then(function () { location.reload(); });
    });
  }
  var last = null;
  setInterval(function () {
    fetch("/__changed", { cache: "no-store" }).then(function (r) { return r.text(); }).then(function (t) {
      if (last !== null && t !== last) location.reload();
      last = t;
    }).catch(function () {});
  }, 800);
})();
</script>
"""


def stamp():
    newest = 0.0
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for f in files:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(d, f)))
            except OSError:
                pass
    return str(newest)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_body(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/__changed":
            return self.send_body(stamp().encode(), "text/plain")
        if path in ("/", "/index.html"):
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                html = f.read()
            html = html.replace(b"<head>", b"<head>\n" + SNIPPET, 1)
            return self.send_body(html, "text/html; charset=utf-8")
        return super().do_GET()

    def log_message(self, fmt, *args):
        if "/__changed" not in (args[0] if args else ""):
            super().log_message(fmt, *args)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"Serving {ROOT} with auto reload on http://localhost:{PORT}/", flush=True)
    Server(("0.0.0.0", PORT), Handler).serve_forever()
