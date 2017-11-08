#!/usr/bin/env python

import sys


def main():
    python_version = sys.version_info
    if python_version[0] < 3 or python_version[1] < 6:
        sys.stderr.write("Unsupported Python version: %s\n" % sys.version)
        sys.stderr.flush()
        exit(1)

    from deployster_impl import main_impl
    main_impl()


if __name__ == "__main__":
    main()
