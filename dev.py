#!/usr/bin/env python3
"""
Development server with hot reload for Discord bot
"""
import subprocess
import sys
import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class BotReloadHandler(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.restart_bot()
    
    def restart_bot(self):
        """Restart the bot process"""
        if self.process:
            print("🔄 Restarting bot...")
            self.process.terminate()
            self.process.wait()
        
        print("🚀 Starting bot...")
        self.process = subprocess.Popen([sys.executable, "bot.py"])
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        # Only restart for Python files
        if event.src_path.endswith('.py'):
            print(f"📝 File changed: {event.src_path}")
            self.restart_bot()
    
    def stop(self):
        """Stop the bot process"""
        if self.process:
            self.process.terminate()
            self.process.wait()

def main():
    print("🔥 Starting Discord Bot with Hot Reload")
    print("📁 Watching for changes in Python files...")
    print("⏹️  Press Ctrl+C to stop")
    
    # Create event handler
    event_handler = BotReloadHandler()
    
    # Create observer
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot and hot reload...")
        event_handler.stop()
        observer.stop()
    
    observer.join()
    print("✅ Stopped successfully")

if __name__ == "__main__":
    main()
