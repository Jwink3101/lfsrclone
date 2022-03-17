# git-lfs rclone based custom transfer angent

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

***

# BETA

This software is still beta. A *non-exhaustive* and only *roughly* ordered list of priorities are:

- [ ] Test (and fix?) on windows
- [ ] Improve tests to handle/verify other edge cases
    - subdirectories (work but not tested)
    - conflicting rclone flags
    - test for line coverage
    - committed rclone config (similar chicken-and-egg as noted before)
    - tests for additional error capture from rclone
- [ ] Document migrations (if possible)
- [ ] PyPI (or do we just distribute via `pip install git+https://...`?)
    - [ ] Better distribution and `setup.py` format
- [ ] type annotations
- [ ] Better parallel working so more than one thing can upload at the same time and make `--transfers` more correct.
- [ ] real-world production testing

## Open Questions

- **Remote Filename Format**: Rather than `53/a0/53a079ad5d55c455b3d617a60117fd7f87ac8c0097454c63c3e5c91fdca9d1af` we can cut this down. One idea is to keep the first two hex bytes `53/a0` and then base32 (for case insensitivity) encode the rest (without those bytes for even more space savings). 

    ```
    import binascii, base64
    hexhash = "53a079ad5d55c455b3d617a60117fd7f87ac8c0097454c63c3e5c91fdca9d1af"
    filename = f"{hexhash[:2]}/{hexhash[2:4]}/{base64.b32encode(binascii.unhexlify(hexhash[4:])).decode()}"
    ```
    
    This ends up being 54 characters with no loss of information.
    
    Do I make this an option? Or default. Is it worth it?
    
- **Content-based chunking**: Much further down the line (and maybe a totally new tool) but can apply content based chunking to split files before upload. Adds a whole level of complexity but also pretty useful for small changes to large binaries.



***
***


Implements a pretty simple [custom-transfer agent][cta] for [git-lfs][lfs].

[cta]:https://github.com/git-lfs/git-lfs/blob/main/docs/custom-transfers.md
[lfs]:https://git-lfs.github.com/

This is **BETA**. See Known Issues and Roadmap for more details.

This project is heavily inspired by [lfs-folderstore][folder] and [git-lfs-swift-transfer-agent][swift] (The idea mostly came from the former but the latter, being that it is in Python, was useful). [git-lfs-rsync-agent][rsync] also proved to be valuable in development.

[folder]:https://github.com/sinbad/lfs-folderstore
[swift]:https://github.com/cbartz/git-lfs-swift-transfer-agent
[rsync]:https://github.com/aleb/git-lfs-rsync-agent

## Install



## Configure LFS

TODO: INSTALL

The following are optional flags that can be specified below:

```
usage: lfsrclone [-h] [--log-file LOG_FILE]
                  [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL,NONE}]
                  [--rclone-exe RCLONE_EXE] [--temp-dir TEMP_DIR]
                  remote

positional arguments:
  remote                Specify rclone remote

optional arguments:
  -h, --help            show this help message and exit
  --log-file LOG_FILE   [.git/lfsrclone.log] Specify alternative log file
                        destination
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL,NONE}
                        Logging levels. Set to None to (effectivly) disable
                        logging (i.e. set to 9999)
  --rclone-exe RCLONE_EXE
                        ['rclone'] Specify rclone executable.
  --temp-dir TEMP_DIR   [.git/lfsrclone-tmp] Specify a temporary download
                        directory

All additional arguments are passed to rclone
```




This section is based on a similar one from [lfs-folderstore][folder].

Download and install [git-lfs][lfs]. Make sure you have followed the directions to begin such as `git lfs install` (globally) and `git lfs track *.ext` (locally), and `git add .gitattributes`

### Starting a new repo

This assumes you have already set up LFS as noted above.

Set the following:

    $ git config --add lfs.customtransfer.lfsrclone.path lfsrclone

Or, if you did not install lfsrclone, you can specify the full path to the Python file

Then,

    $ git config --add lfs.standalonetransferagent lfsrclone
    
And finally,

    $ git config --add lfs.customtransfer.lfsrclone.args "remote: <lfsrclone-options> <additional rclone flags>"
    
Note in the above that all arguments must be escaped properly so it is passed to `git-config` as just one. Alternatively, do something like:

    $ git config --add lfs.customtransfer.lfsrclone.args TMP

then open `.git/config` and you will see lines like:

```ini
[lfs "customtransfer.lfsrclone"]
	path = lfsrclone
	args = TMP
```
You can then set `TMP` to your full rclone command including `\` for line continuation, etc. `<lfsrclone-options>` are those noted above including the log file.

### Cloning an existing repo

Cloning an existing lfsrclone repo presents a "chicken and the egg" problem with how to configure.

To do this, you tell git-lfs not to download files.

    $ export GIT_LFS_SKIP_SMUDGE=1
    $ git clone <repo>
    $ unset GIT_LFS_SKIP_SMUDGE

    ##### OR #####
    
    $ GIT_LFS_SKIP_SMUDGE=1 git clone <repo>
    
(this assumes Bash but it is similar for other shells)
    
Then move into the repo and set up as per above:

    $ git config --add lfs.customtransfer.lfsrclone.path lfsrclone
    $ git config --add lfs.standalonetransferagent lfsrclone
    $ git config --add lfs.customtransfer.lfsrclone.args "remote: <flags>" # or TMP and replace
    
Finally:

    $ git lfs pull 

### Additional Notes

Since lfsrclone does not support file-locking, you may have to set

    $ git config lfs.locksverify false

inside the repo

## Concurrency and Transfers

git-lfs has its own way to set transfers and concurrency as does rclone. lfsrclone will not try to deduce that in any way. It will run on the number of transfers called. See [`lfs.concurrenttransfers`][concurrent] to set the number or [`lfs.customtransfer.<name>.concurrent`][custom concurrent] to disable. Alternatively or in addition, you can set `--transfers N` flag for rclone

[concurrent]:https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-config.5.ronn#upload-and-download-transfer-settings
[custom concurrent]: https://github.com/git-lfs/git-lfs/blob/main/docs/custom-transfers.md#defining-a-custom-transfer-type

## Rclone Flags

You can pass any flags to rclone by XYZ but note that some are automatically set and may not be compatible with what you set. It also uses `copy` instead of `copyto` since we do not want to upload if the dest is already there (and the right size).  Notable flags THISTOOL sets:

- [`--size-only`][so]: We do not need ModTime so no reason to get it and some remotes are very slow. We do *not* set [`--ignore-existing`][ie] because we want to overwrite incomplete uploads. And all remotes set size
- Progress reporting
    - [`--log-level INFO`][log] used to make it print output (note: same as `-v`)
    - [`--use-json-log`][json] makes the output easier to parse
- [`--no-traverse`][nt] Single transfers only so we can save listing
- [`--ask-password=false`][ap] No password prompts. Better to error

[ie]:https://rclone.org/docs/#ignore-existing
[so]:https://rclone.org/docs/#size-only
[log]: https://rclone.org/docs/#logging
[json]:https://rclone.org/docs/#use-json-log
[nt]:https://rclone.org/docs/#no-traverse
[ap]:https://rclone.org/docs/#configuration-encryption

### Tips

You can force rclone, and therefore LFS, to provide updates more often with `--stats`. For example: `--stats 100ms` will update 10 times a second.

### Rclone Setup

You can set up any rclone remote. However, if you use crypt, consider whether or not you need directory name encryption. Files are stored in a content-addressable manner of `<first hex byte>/<second hex byte>/<hex name>`. Encrypting the filenames make sense as they are the SHA256 and, while unlikely for most content, could leak the contents. However, unless the first two bytes of the SHA256 are critical, encrypting the leading directory names adds a lot of length to the file name. 

For example, the following encrypts 70 characters

    53/a0/53a079ad5d55c455b3d617a60117fd7f87ac8c0097454c63c3e5c91fdca9d1af

to 182 characters

    fi7dlav8hvdcpf6kjpth26q40o/kjj1o6gs49ee5pmmij57rb0a2k/d696m9fgemb461gv0gsqroqrkojb9pg15q1ito7idtigpc1itaskqbmqdmmes3g78dvgki4jb80tth36dmj6opum9kbbrblkig34hk8qkquodng9kc59pauesmbjfj2c
    
while disabling directory name  sets it to 134 characters

    53/a0/d696m9fgemb461gv0gsqroqrkojb9pg15q1ito7idtigpc1itaskqbmqdmmes3g78dvgki4jb80tth36dmj6opum9kbbrblkig34hk8qkquodng9kc59pauesmbjfj2c

### Incompatible Flags

This is **not exhaustive** but do not set the following:

- `--progress` since we parse it out
- `-v` or `--log-level` since we use it already

## Known Limitations

* Cannot perform locking. See [#4314](https://github.com/git-lfs/git-lfs/issues/4314#issuecomment-730434427)

## Contributing

All code should run through [black](https://github.com/psf/black)

## Background

I have always been disappointed that git-lfs required a special server. I don't care that it breaks the decentralized nature (though it does!) but it means that hosting requires more than just a simple ssh server. And portability becomes harders.

I've considered [git-fat][fat] but it is outdated. I've looked at [git-annex][annex] but it is (a) super (!!!) complicated, (b) not widely used, and (c) I don't like the symlink approach (even though smudge-filter approach also has its issues).

I've considered updating git-fat but decided it wasn't worth it. I ended up writing my own tool fully but found the edge-cases and testing to be more than I was willing to do (though it was a good learning experience!). So I left it alone.

But when I found [lfs-folderstore][folder], I learned about custom transfer agents. Suddenly, it became possible to let git-lfs handle the edge cases and the user interface and just let me handle the data! Win-win!

[fat]:https://github.com/jedbrown/git-fat
[annex]:https://git-annex.branchable.com/



