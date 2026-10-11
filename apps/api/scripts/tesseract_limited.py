#!/usr/local/bin/python
"""Linux OCR child process cap, used only by the Docker runtime."""
import os
import resource
import sys

resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
os.environ["OMP_THREAD_LIMIT"] = "1"
os.execv("/usr/bin/tesseract", ["tesseract", *sys.argv[1:]])
