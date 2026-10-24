import subprocess
import sys
from pathlib import Path


child = Path(__file__).with_name("debuggee_break.py")
subprocess.run([sys.executable, "-B", str(child)], check=True)
