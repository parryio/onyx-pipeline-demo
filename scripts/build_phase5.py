#!/usr/bin/env python3
import subprocess, sys, os

def main():
  py = sys.executable
  # Generate UI catalog + assets from Phase 4 kits
  rc = subprocess.call([py, os.path.join('ritual_player','ui_data_generator.py')])
  if rc != 0:
    sys.exit(rc)

if __name__ == '__main__':
  main()
