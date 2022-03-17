#!/usr/bin/env python
"""
lfsrclone: rclone-based transfer agent for git-lfs
"""
__version__ = "20220317.0.BETA"

import argparse
import sys, os
import json
import tempfile
import subprocess
import logging


def write(msg=None):
    if not msg:
        msg = {}
    print(json.dumps(msg), flush=True)
    logging.debug("write msg %s", msg)


def read():
    line = sys.stdin.readline()
    msg = json.loads(line)
    logging.debug("read msg %s", msg)
    return msg


class Main:
    def __init__(self, argv=None):
        if argv is None:
            argv = sys.argv[1:]

        parser = argparse.ArgumentParser(
            allow_abbrev=False,  # to avoid prefix matching
            epilog="""
                All additional arguments are passed to rclone
            """,
        )
        parser.add_argument("remote", help="Specify rclone remote")

        parser.add_argument(
            "--log-file",
            default=".git/lfsrclone.log",
            help="[%(default)s] Specify alternative log file destination",
        )
        parser.add_argument(
            "--log-level",
            help="Logging levels. Set to None to (effectivly) disable logging (i.e. set to 9999)",
            default="WARNING",  # Also the python default
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE"],
        )
        parser.add_argument(
            "--rclone-exe",
            default="rclone",
            help="['rclone'] Specify rclone executable.",
        )
        parser.add_argument(
            "--temp-dir",
            default=".git/lfsrclone-tmp",
            help="[%(default)s] Specify a temporary download directory",
        )

        args, rclone_args = parser.parse_known_args(argv)
        self.args = args
        self.rclone_args = rclone_args

        if args.log_level == "NONE":
            args.log_level = 9999

        logging.basicConfig(
            filename=args.log_file,
            encoding="utf-8",
            format="%(levelname)s:%(asctime)s: %(message)s",
            level=getattr(logging, args.log_level),
        )

        logging.debug("argv: %s", argv)
        logging.debug("args: %s", args)
        logging.debug("rclone: %s", rclone_args)

        self.init()
        self.loop()

    def init(self):
        msg = read()
        if msg["event"] != "init":
            logging.critical('Incorrect msg type. Expected "init". Got %s', msg)
            sys.exit(1)
        logging.info("Initiated in %s", os.getcwd())
        write()

    def loop(self):
        self.c = 0
        while True:
            logging.info("Loop %i", self.c)
            msg = read()
            if msg["event"] in {"upload", "download"}:
                self.action(msg)
            elif msg["event"] == "terminate":
                logging.info("Termination Called")
                sys.exit()
            else:
                logging.critical("Recieved incorrect event %s", msg["event"])
                sys.exit(1)
            self.c += 1

    def action(self, msg):
        oid, size = msg["oid"], msg["size"]

        cmd = [self.args.rclone_exe, "copy"]
        if msg["event"] == "upload":
            src = msg["path"]
            dst = pathjoin(self.args.remote, f"{oid[:2]}/{oid[2:4]}/")
        elif msg["event"] == "download":
            src = pathjoin(self.args.remote, f"{oid[:2]}/{oid[2:4]}/{oid}")
            dst = self.args.temp_dir
            if not dst:
                dst = tempfile.mkdtemp()
        else:
            logging.critical("Unrecognized event")
            sys.exit(1)

        cmd.extend([src, dst])
        # Do not need anything but do not use `--ignore existing` since it could be from a broken transfer
        cmd.append("--size-only")
        cmd.append("--no-traverse")  # Singly copy so this is faster.
        cmd.extend(["--use-json-log", "--log-level", "INFO"])  # Logging
        cmd.append("--ask-password=false")  # No password prompt
        cmd.extend(self.rclone_args)

        logging.debug("Calling %s", cmd)

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        errors = []
        prev = 0
        with proc.stderr:
            for line in iter(proc.stderr.readline, b""):
                # Allow for bad decoding not to crash it. Not common but has happened in
                # other projects.
                line = line.decode(errors="backslashreplace")
                try:
                    line = json.loads(line)
                except json.JSONDecodeError as E:
                    errors.append(f"JSONDecodeError: Exception {E}, line {line}")
                    # Errors will later get logged
                    continue

                if line.get("level", None) == "error":
                    errors.append(line.get("msg", ""))
                    continue

                stat = line.get("stats", {}).get("transferring", [{}])[0]
                if stat:
                    # rclone can sometimes report more than the size of the object.
                    # It seems to not affect lfs but if it does, we can handle that
                    # in the future as needed. Rclone may also given a stat we aren't
                    # prepared for. Again, lfs appears to not mind odd stats so handle it
                    # gracefully
                    stat_bytes = stat.get("bytes", 0)
                    progress = {
                        "event": "progress",
                        "oid": oid,
                        "bytesSoFar": stat_bytes,
                        "bytesSinceLast": stat_bytes - prev,
                    }
                    prev = stat_bytes
                    write(progress)

        # Now provide the last progress. May duplicate the 100% but it seems to be okay
        progress = {
            "event": "progress",
            "oid": oid,
            "bytesSoFar": size,
            "bytesSinceLast": size - prev,
        }
        write(progress)

        complete = {"event": "complete", "oid": oid}

        if msg["event"] == "download":
            complete["path"] = f"{dst}/{oid}"

        o = proc.poll()
        if o or errors:
            complete["error"] = {"code": max([o, 1]), "message": "\n".join(errors)}
            logging.debug("Error Lines %s", errors)
        write(complete)
        logging.debug("Action %s complete: %s", (self.c, msg))


def pathjoin(*args):
    """
    This is like os.path.join but does some rclone-specific things because there could be
    a ':' in the first part.
    
    The second argument could be '/file', or 'file' and the first could have a colon.
        pathjoin('a','b')   # a/b
        pathjoin('a:','b')  # a:b
        pathjoin('a:','/b') # a:/b
        pathjoin('a','/b')  # a/b  NOTE that this is different than os.path.join
    """
    if len(args) <= 1:
        return "".join(args)

    root, first, rest = args[0], args[1], args[2:]

    if root.endswith("/"):
        root = root[:-1]

    if root.endswith(":") or first.startswith("/"):
        path = root + first
    else:
        path = f"{root}/{first}"

    path = os.path.join(path, *rest)
    return path


if __name__ == "__main__":
    Main(sys.argv[1:])
