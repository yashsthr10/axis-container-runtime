from __future__ import annotations

import argparse
import selectors
import socket
import threading


BUFFER_SIZE = 65536


def main() -> int:
    parser = argparse.ArgumentParser(prog="axis-proxy")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--target-host", required=True)
    parser.add_argument("--target-port", type=int, required=True)
    args = parser.parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.listen_host, args.listen_port))
        server.listen()

        while True:
            client, _ = server.accept()
            try:
                target = socket.create_connection((args.target_host, args.target_port))
            except OSError:
                client.close()
                continue

            threading.Thread(target=proxy_connection, args=(client, target), daemon=True).start()


def proxy_connection(left: socket.socket, right: socket.socket) -> None:
    selector = selectors.DefaultSelector()
    left.setblocking(False)
    right.setblocking(False)

    with left, right, selector:
        selector.register(left, selectors.EVENT_READ, right)
        selector.register(right, selectors.EVENT_READ, left)

        while True:
            events = selector.select()
            for key, _ in events:
                source = key.fileobj
                destination = key.data
                try:
                    data = source.recv(BUFFER_SIZE)
                except OSError:
                    return

                if not data:
                    return

                try:
                    destination.sendall(data)
                except OSError:
                    return


if __name__ == "__main__":
    raise SystemExit(main())
