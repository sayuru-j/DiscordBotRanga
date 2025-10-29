#!/usr/bin/env python3
"""
Simple hot reload script for Discord bot development
"""
import subprocess
import sys
import time
import os
from pathlib import Path

def main():
    print("🔥 Discord Bot Hot Reload")
    print("📁 Watching bot.py for changes...")
    print("⏹️  Press Ctrl+C to stop")
    print()
    
    bot_process = None
    last_modified = 0
    
    try:
        while True:
            # Check if bot.py was modified
            bot_file = Path("bot.py")
            if bot_file.exists():
                current_modified = bot_file.stat().st_mtime
                
                if current_modified > last_modified:
                    last_modified = current_modified
                    
                    # Restart bot if it's running
                    if bot_process:
                        print("🔄 Restarting bot...")
                        bot_process.terminate()
                        bot_process.wait()
                    
                    # Start bot
                    print("🚀 Starting bot...")
                    bot_process = subprocess.Popen([sys.executable, "bot.py"])
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot...")
        if bot_process:
            bot_process.terminate()
            bot_process.wait()
        print("✅ Stopped successfully")

if __name__ == "__main__":
    main()
