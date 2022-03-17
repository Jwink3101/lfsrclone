#!/usr/bin/env python
"""
Apply various features to ensure it works properly.
"""
import sys, os
import subprocess
import shutil
import shlex
import hashlib
from pathlib import Path


print(f'git: {subprocess.check_output(["git", "version"]).decode().strip()}')
print(f'git-lfs: {subprocess.check_output(["git","lfs", "version"]).decode().strip()}')
lfsrc = os.path.abspath("lfsrclone.py")


def verify_contents(hh):
    hh = str(hh)
    dpath = Path("testdir/data/") / hh[:2] / hh[2:4] / hh
    assert dpath.exists()
    h2 = hashlib.sha256(dpath.read_bytes()).hexdigest()
    assert str(h2) == hh


call = subprocess.check_call

################## cleanup
os.chdir(os.path.dirname(__file__))
try:
    shutil.rmtree("testdir")
except OSError:
    pass
os.makedirs("testdir")

with open("testdir/cfg", "wt") as fout:
    fout.write(
        f"""\
[remote]
type = alias
remote = {os.path.abspath('testdir/data')}
"""
    )

################# New Repo
call(["git", "init", "--bare", "host"], cwd="testdir")
hostpath = os.path.abspath("testdir/host")

call(["git", "clone", hostpath, "repo"], cwd="testdir")
repopath = os.path.abspath("testdir/repo")

# Config
call(
    ["git", "config", "--add", "lfs.customtransfer.lfsrclone.path", lfsrc],
    cwd=repopath,
)
call(
    ["git", "config", "--add", "lfs.standalonetransferagent", "lfsrclone"],
    cwd=repopath,
)

cmd = [
    "remote:",
    "--stats",  # rclone
    "100ms",
    "--config",
    "../cfg",  # Test that the path is maintained
    "--log-level",  # lfsrclone
    "DEBUG",
    "--log-file",
    os.path.abspath("testdir/log"),
]
call(
    ["git", "config", "--add", "lfs.customtransfer.lfsrclone.args", shlex.join(cmd)],
    cwd=repopath,
)

call(["git", "lfs", "track", "*.ext"], cwd=repopath)

call(["git", "add", ".gitattributes"], cwd=repopath)

with open("testdir/repo/file1.ext", "wt") as fout:
    print("line 1", file=fout)

call(["git", "add", "file1.ext"], cwd=repopath)
call(["git", "commit", "-m", "file1"], cwd=repopath)
call(["git", "push"], cwd=repopath)

# verify it got pushed where it should
with open("testdir/repo/file1.ext", "rb") as f:
    hh0 = hh = str(hashlib.sha256(f.read()).hexdigest())
verify_contents(hh)

# add to it, clean up, and make sure we can get it back
with open("testdir/repo/file1.ext", "at") as fout:
    print("line 2", file=fout)

call(["git", "add", "file1.ext"], cwd=repopath)
call(["git", "commit", "-m", "file1 line2"], cwd=repopath)
call(["git", "push"], cwd=repopath)

# verify it got pushed where it should
with open("testdir/repo/file1.ext", "rb") as f:
    hh1 = hh = str(hashlib.sha256(f.read()).hexdigest())
verify_contents(hh)

# Clean up and make sure we can get everything back. ALso check with verify
call(["git", "lfs", "prune", "--verify-remote", "--force"], cwd=repopath)
assert [p for p in (Path(repopath) / ".git" / "lfs").rglob("*") if p.is_file()] == []

call(["git", "tag", "tmp"], cwd=repopath)

call(["git", "checkout", "HEAD~1"], cwd=repopath)
with open("testdir/repo/file1.ext", "rb") as f:
    hh = str(hashlib.sha256(f.read()).hexdigest())
assert hh == hh0

call(["git", "checkout", "tmp"], cwd=repopath)
with open("testdir/repo/file1.ext", "rb") as f:
    hh = str(hashlib.sha256(f.read()).hexdigest())
assert hh == hh1


## New checkout with settings
env = os.environ.copy()
env["GIT_LFS_SKIP_SMUDGE"] = "1"

call(["git", "clone", hostpath, "repo2"], cwd="testdir", env=env)
repopath2 = os.path.abspath("testdir/repo2")

f = Path(repopath2) / "file1.ext"
assert hashlib.sha256(f.read_bytes()).hexdigest() != hh1
assert hh1 in f.read_text()  # the oid should be in the file

# Setup
call(
    ["git", "config", "--add", "lfs.customtransfer.lfsrclone.path", lfsrc],
    cwd=repopath2,
)
call(
    ["git", "config", "--add", "lfs.standalonetransferagent", "lfsrclone"],
    cwd=repopath2,
)

cmd = [
    "remote:",
    "--stats",  # rclone
    "100ms",
    "--config",
    "../cfg",  # Test that the path is maintained
    "--log-level",  # lfsrclone
    "DEBUG",
    "--log-file",
    os.path.abspath("testdir/log"),
]
call(
    ["git", "config", "--add", "lfs.customtransfer.lfsrclone.args", shlex.join(cmd)],
    cwd=repopath2,
)
# Update and verify
call(["git", "lfs", "pull"], cwd=repopath2)
assert hashlib.sha256(f.read_bytes()).hexdigest() == hh1
assert hh1 not in f.read_text()  # the oid should be in the file

call(["git", "checkout", "HEAD~1"], cwd=repopath2)
with open("testdir/repo2/file1.ext", "rb") as f:
    hh = str(hashlib.sha256(f.read()).hexdigest())
assert hh == hh0
