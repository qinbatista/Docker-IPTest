#!/usr/bin/env python3
import sys
from iptest_runtime import IPTestRuntimeClient


if __name__ == "__main__":
    sys.exit(IPTestRuntimeClient().run())
