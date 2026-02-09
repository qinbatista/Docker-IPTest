#!/usr/bin/env python
import os
import sys
if __name__ == "__main__":
	if len(sys.argv)>=2:
		os.system('curl http://www.cip.cc/'+sys.argv[1])
	else:
		os.system('curl http://www.cip.cc')