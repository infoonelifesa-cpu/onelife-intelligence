#!/usr/bin/env python3
"""Onelife Intelligence Dashboard V7 - Full Generator
Runs data crunching + HTML generation in sequence.
"""
import subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))

print("=" * 60)
print("  Onelife Intelligence Dashboard V7 Generator")
print("=" * 60)

# Step 1: Crunch data
print("\n[1/2] Crunching data...")
r1 = subprocess.run([sys.executable, os.path.join(DIR, "gen_v7_data.py")])
if r1.returncode != 0:
    print("ERROR: Data crunching failed!")
    sys.exit(1)

# Step 2: Generate HTML
print("\n[2/2] Building HTML dashboard...")
r2 = subprocess.run([sys.executable, os.path.join(DIR, "gen_v7_html.py")])
if r2.returncode != 0:
    print("ERROR: HTML generation failed!")
    sys.exit(1)

print("\n" + "=" * 60)
print("  Dashboard V7 ready: index.html")
print("=" * 60)
