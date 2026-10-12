#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

"""
Build script for Promise Minimap Mover.

Works with Python 2.7 or Python 3 as the builder.

The WoT runtime module is ALWAYS compiled with the Python 2.7
executable passed via --python27.

Example:

    python build.py --clean --game-version 2.4.0.0 --python27 "C:\\Python27\\python.exe"
"""

import argparse
import os
import re
import shutil
import subprocess
import zipfile


ROOT = os.path.dirname(os.path.abspath(__file__))

PROJECT = "promise_minimap_mover"

MODULE_NAME = "mod_promise_minimap_mover.py"

SOURCE_FILE = os.path.join(
    ROOT,
    "src",
    "scripts",
    "client",
    "gui",
    "mods",
    MODULE_NAME
)

DIST_DIR = os.path.join(ROOT, "dist")
BUILD_DIR = os.path.join(ROOT, ".build")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_text(value):

    if isinstance(value, bytes):
        return value.decode("ascii", "replace")

    return value


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

def read_version():

    if not os.path.isfile(SOURCE_FILE):
        raise RuntimeError(
            "Runtime source not found: %s" % SOURCE_FILE
        )

    f = open(SOURCE_FILE, "r")

    try:
        data = f.read()

    finally:
        f.close()

    # Preferred conventional version declaration:
    #
    #     __version__ = '1.0.0'
    #
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        data,
        re.MULTILINE
    )

    # Backward compatibility with older mods:
    #
    #     MOD_VERSION = '1.0.0'
    #
    if not match:

        match = re.search(
            r'^MOD_VERSION\s*=\s*["\']([^"\']+)["\']',
            data,
            re.MULTILINE
        )

    if not match:
        raise RuntimeError(
            "__version__ or literal MOD_VERSION not found in: %s"
            % SOURCE_FILE
        )

    return match.group(1)

    if not os.path.isfile(SOURCE_FILE):

        raise RuntimeError(
            "Runtime source not found: %s" % SOURCE_FILE
        )

    f = open(SOURCE_FILE, "r")

    try:
        data = f.read()

    finally:
        f.close()

    match = re.search(
        r'^MOD_VERSION\s*=\s*["\']([^"\']+)["\']',
        data,
        re.MULTILINE
    )

    if not match:

        raise RuntimeError(
            "MOD_VERSION not found in: %s" % SOURCE_FILE
        )

    return match.group(1)


# ---------------------------------------------------------------------------
# Build directories
# ---------------------------------------------------------------------------

def clean():

    if os.path.isdir(DIST_DIR):
        shutil.rmtree(DIST_DIR)

    if os.path.isdir(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)

    os.makedirs(DIST_DIR)


def ensure_directories():

    if not os.path.isdir(DIST_DIR):
        os.makedirs(DIST_DIR)

    if not os.path.isdir(BUILD_DIR):
        os.makedirs(BUILD_DIR)


# ---------------------------------------------------------------------------
# Python 2.7 compiler
# ---------------------------------------------------------------------------

def verify_python27(python27):

    if not python27:

        raise RuntimeError(
            "Python 2.7 is required. "
            "Use --python27 \"C:\\Python27\\python.exe\""
        )

    if not os.path.isfile(python27):

        raise RuntimeError(
            "Python 2.7 executable not found: %s" % python27
        )

    command = [
        python27,
        "-c",
        "import sys; print('%d.%d' % sys.version_info[:2])"
    ]

    version = subprocess.check_output(command)

    version = to_text(version).strip()

    if version != "2.7":

        raise RuntimeError(
            "Wrong compiler: expected Python 2.7, got %s"
            % version
        )

    return version


# ---------------------------------------------------------------------------
# Compile WoT runtime
# ---------------------------------------------------------------------------

def compile_python27(python27):

    verify_python27(python27)

    ensure_directories()

    temp_py = os.path.join(
        BUILD_DIR,
        MODULE_NAME
    )

    shutil.copy2(
        SOURCE_FILE,
        temp_py
    )

    subprocess.check_call(
        [
            python27,
            "-m",
            "py_compile",
            temp_py
        ]
    )

    pyc_file = temp_py + "c"

    if not os.path.isfile(pyc_file):

        raise RuntimeError(
            "Python 2.7 did not create bytecode file: %s"
            % pyc_file
        )

    return pyc_file


# ---------------------------------------------------------------------------
# WOTMOD
# ---------------------------------------------------------------------------

def make_wotmod(version, python27):

    pyc_file = compile_python27(
        python27
    )

    ensure_directories()

    filename = "%s_%s.wotmod" % (
        PROJECT,
        version
    )

    output = os.path.join(
        DIST_DIR,
        filename
    )

    if os.path.isfile(output):
        os.remove(output)

    zf = zipfile.ZipFile(
        output,
        "w",
        zipfile.ZIP_STORED
    )

    try:

        zf.write(
            pyc_file,
            "res/scripts/client/gui/mods/"
            "mod_promise_minimap_mover.pyc"
        )

    finally:
        zf.close()

    return output


# ---------------------------------------------------------------------------
# Verify WOTMOD
# ---------------------------------------------------------------------------

def verify_wotmod(wotmod):

    zf = zipfile.ZipFile(
        wotmod,
        "r"
    )

    try:

        entries = zf.infolist()

        if len(entries) != 1:

            raise RuntimeError(
                "Unexpected number of files inside "
                ".wotmod: %d"
                % len(entries)
            )

        entry = entries[0]

        expected = (
            "res/scripts/client/gui/mods/"
            "mod_promise_minimap_mover.pyc"
        )

        if entry.filename != expected:

            raise RuntimeError(
                "Unexpected .wotmod path: %s"
                % entry.filename
            )

        if entry.compress_type != zipfile.ZIP_STORED:

            raise RuntimeError(
                ".wotmod entry is compressed. "
                "Expected ZIP_STORED."
            )

    finally:
        zf.close()


# ---------------------------------------------------------------------------
# Release ZIP
# ---------------------------------------------------------------------------

def make_release(version, game_version, wotmod):

    filename = "%s_%s.zip" % (
        PROJECT,
        version
    )

    output = os.path.join(
        DIST_DIR,
        filename
    )

    if os.path.isfile(output):
        os.remove(output)

    if game_version:

        wotmod_path = (
            "mods/%s/%s"
            % (
                game_version,
                os.path.basename(wotmod)
            )
        )

    else:

        wotmod_path = (
            "mods/PUT_WOT_VERSION_HERE/%s"
            % os.path.basename(wotmod)
        )

    zf = zipfile.ZipFile(
        output,
        "w",
        zipfile.ZIP_DEFLATED
    )

    try:

        zf.write(
            wotmod,
            wotmod_path
        )

    finally:
        zf.close()

    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Build Promise Minimap Mover"
    )

    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove old build output first"
    )

    parser.add_argument(
        "--game-version",
        help=(
            "World of Tanks mod folder version, "
            "e.g. 2.4.0.0"
        )
    )

    parser.add_argument(
        "--python27",
        required=True,
        help="Path to Python 2.7 executable"
    )

    args = parser.parse_args()

    if args.clean:
        clean()

    else:
        ensure_directories()

    version = read_version()

    print("Project : %s" % PROJECT)
    print("Version : %s" % version)

    python_version = verify_python27(
        args.python27
    )

    print(
        "Python  : %s (%s)"
        % (
            args.python27,
            python_version
        )
    )

    print("Compile : Python 2.7 bytecode")

    if args.game_version:
        print(
            "Game    : %s"
            % args.game_version
        )

    wotmod = make_wotmod(
        version,
        args.python27
    )

    verify_wotmod(
        wotmod
    )

    release = make_release(
        version,
        args.game_version,
        wotmod
    )

    print("")
    print("Built:")
    print("  %s" % wotmod)
    print("  %s" % release)

    print("")
    print("WOTMOD runtime:")
    print(
        "  scripts/client/gui/mods/"
        "mod_promise_minimap_mover.pyc"
    )

    print("")
    print("Compression:")
    print("  ZIP_STORED")

    if not args.game_version:

        print("")
        print(
            "WARNING: no --game-version "
            "was supplied."
        )

        print("Release ZIP uses:")
        print(
            "  mods/PUT_WOT_VERSION_HERE/"
        )


if __name__ == "__main__":
    main()