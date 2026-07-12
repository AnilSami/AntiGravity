# -*- coding: utf-8 -*-
import re

with open(r"C:\Users\anils\.gemini\antigravity\brain\1b3acd38-6039-400c-975c-a12268af0711\.system_generated\tasks\task-7518.log", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "scout" in line.lower() or "curator" in line.lower() or "candidates" in line.lower() or "HTTP Request" in line:
        print(f"Line {idx+1}: {line.strip()}")
