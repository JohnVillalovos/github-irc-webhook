from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys
import threading
from typing import Optional

import config
import events
from irc import IrcConnection

irc: Optional[IrcConnection] = None

# handle POST events from github server
# We should also make sure to ignore requests from the IRC, which can clutter
# the output with errors
CONTENT_TYPE = "content-type"
CONTENT_LEN = "content-length"
EVENT_TYPE = "x-github-event"


class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        pass

    def do_CONNECT(self) -> None:
        pass

    def do_POST(self) -> None:
        if not all(x in self.headers for x in [CONTENT_TYPE, CONTENT_LEN, EVENT_TYPE]):
            return
        content_type = self.headers["content-type"]
        content_len = int(self.headers["content-length"])
        event_type = self.headers["x-github-event"]

        if content_type != "application/json":
            self.send_error(400, "Bad Request", "Expected a JSON request")
            return

        data = self.rfile.read(content_len)
        if sys.version_info < (3, 6):
            data = data.decode()

        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("OK", "utf-8"))

        if irc is not None:
            events.handle_event(irc, event_type, json.loads(data))


# Just run IRC connection event loop
def worker() -> None:
    if irc is not None:
        irc.loop()


irc = IrcConnection(
    server=config.IRC_SERVER,
    channel=config.IRC_CHANNEL,
    nick=config.IRC_NICK,
    passw=config.IRC_PASS,
    port=config.IRC_PORT,
)

t = threading.Thread(target=worker)
t.start()

# Run Github webhook handling server
try:
    server = HTTPServer((config.SERVER_HOST, config.SERVER_PORT), MyHandler)
    server.serve_forever()
except KeyboardInterrupt:
    print("Exiting")
    server.socket.close()
    irc.stop_loop()
