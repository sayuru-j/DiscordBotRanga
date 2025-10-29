#!/usr/bin/env python3
"""
Policy Manager - Read and edit bot policies directly
"""
import sqlite3
import json
from datetime import datetime

class PolicyManager:
    def __init__(self, db_path="bot_policies.db"):
        self.db_path = db_path
    
    def get_all_policies(self):
        """Get all server policies"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM server_policies')
        results = cursor.fetchall()
        conn.close()
        
        policies = []
        for row in results:
            policies.append({
                'guild_id': row[0],
                'enabled': bool(row[1]),
                'allowed_channels': row[2].split(',') if row[2] else [],
                'blocked_channels': row[3].split(',') if row[3] else [],
                'allowed_roles': row[4].split(',') if row[4] else [],
                'blocked_roles': row[5].split(',') if row[5] else [],
                'cooldown_seconds': row[6],
                'max_message_length': row[7],
                'require_mention': bool(row[8]),
                'admin_only': bool(row[9]),
                'created_at': row[10]
            })
        
        return policies
    
    def get_server_policy(self, guild_id):
        """Get policy for specific server"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM server_policies WHERE guild_id = ?', (guild_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'guild_id': result[0],
                'enabled': bool(result[1]),
                'allowed_channels': result[2].split(',') if result[2] else [],
                'blocked_channels': result[3].split(',') if result[3] else [],
                'allowed_roles': result[4].split(',') if result[4] else [],
                'blocked_roles': result[5].split(',') if result[5] else [],
                'cooldown_seconds': result[6],
                'max_message_length': result[7],
                'require_mention': bool(result[8]),
                'admin_only': bool(result[9]),
                'created_at': result[10]
            }
        return None
    
    def update_server_policy(self, guild_id, **kwargs):
        """Update server policy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get existing policy
        cursor.execute('SELECT * FROM server_policies WHERE guild_id = ?', (guild_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            cursor.execute('''
                UPDATE server_policies SET 
                enabled = ?, allowed_channels = ?, blocked_channels = ?, 
                allowed_roles = ?, blocked_roles = ?, cooldown_seconds = ?, 
                max_message_length = ?, require_mention = ?, admin_only = ?
                WHERE guild_id = ?
            ''', (
                kwargs.get('enabled', existing[1]),
                ','.join(kwargs.get('allowed_channels', [])),
                ','.join(kwargs.get('blocked_channels', [])),
                ','.join(kwargs.get('allowed_roles', [])),
                ','.join(kwargs.get('blocked_roles', [])),
                kwargs.get('cooldown_seconds', existing[6]),
                kwargs.get('max_message_length', existing[7]),
                kwargs.get('require_mention', existing[8]),
                kwargs.get('admin_only', existing[9]),
                guild_id
            ))
        else:
            # Insert new
            cursor.execute('''
                INSERT INTO server_policies 
                (guild_id, enabled, allowed_channels, blocked_channels, 
                 allowed_roles, blocked_roles, cooldown_seconds, 
                 max_message_length, require_mention, admin_only)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                guild_id,
                kwargs.get('enabled', True),
                ','.join(kwargs.get('allowed_channels', [])),
                ','.join(kwargs.get('blocked_channels', [])),
                ','.join(kwargs.get('allowed_roles', [])),
                ','.join(kwargs.get('blocked_roles', [])),
                kwargs.get('cooldown_seconds', 5),
                kwargs.get('max_message_length', 2000),
                kwargs.get('require_mention', False),
                kwargs.get('admin_only', False)
            ))
        
        conn.commit()
        conn.close()
        print(f"✅ Updated policy for server {guild_id}")
    
    def delete_server_policy(self, guild_id):
        """Delete server policy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM server_policies WHERE guild_id = ?', (guild_id,))
        cursor.execute('DELETE FROM user_cooldowns WHERE guild_id = ?', (guild_id,))
        
        conn.commit()
        conn.close()
        print(f"✅ Deleted policy for server {guild_id}")
    
    def export_policies(self, filename="policies_backup.json"):
        """Export all policies to JSON"""
        policies = self.get_all_policies()
        
        with open(filename, 'w') as f:
            json.dump(policies, f, indent=2, default=str)
        
        print(f"✅ Exported {len(policies)} policies to {filename}")
    
    def import_policies(self, filename="policies_backup.json"):
        """Import policies from JSON"""
        with open(filename, 'r') as f:
            policies = json.load(f)
        
        for policy in policies:
            self.update_server_policy(policy['guild_id'], **policy)
        
        print(f"✅ Imported {len(policies)} policies from {filename}")

def main():
    """Interactive policy manager"""
    pm = PolicyManager()
    
    while True:
        print("\n🔧 Policy Manager")
        print("1. View all policies")
        print("2. View specific server policy")
        print("3. Update server policy")
        print("4. Delete server policy")
        print("5. Export policies")
        print("6. Import policies")
        print("7. Exit")
        
        choice = input("\nChoose an option (1-7): ").strip()
        
        if choice == "1":
            policies = pm.get_all_policies()
            if policies:
                print(f"\n📋 Found {len(policies)} server policies:")
                for policy in policies:
                    print(f"Server {policy['guild_id']}: {'✅ Enabled' if policy['enabled'] else '❌ Disabled'}")
            else:
                print("No policies found.")
        
        elif choice == "2":
            guild_id = input("Enter server ID: ").strip()
            try:
                guild_id = int(guild_id)
                policy = pm.get_server_policy(guild_id)
                if policy:
                    print(f"\n📋 Policy for server {guild_id}:")
                    print(json.dumps(policy, indent=2, default=str))
                else:
                    print("No policy found for this server.")
            except ValueError:
                print("Invalid server ID.")
        
        elif choice == "3":
            guild_id = input("Enter server ID: ").strip()
            try:
                guild_id = int(guild_id)
                print("Enter new policy values (press Enter to keep current):")
                
                enabled = input("Enabled (true/false): ").strip().lower()
                enabled = enabled == 'true' if enabled else None
                
                cooldown = input("Cooldown (seconds): ").strip()
                cooldown = int(cooldown) if cooldown.isdigit() else None
                
                admin_only = input("Admin only (true/false): ").strip().lower()
                admin_only = admin_only == 'true' if admin_only else None
                
                require_mention = input("Require mention (true/false): ").strip().lower()
                require_mention = require_mention == 'true' if require_mention else None
                
                # Filter out None values
                updates = {k: v for k, v in {
                    'enabled': enabled,
                    'cooldown_seconds': cooldown,
                    'admin_only': admin_only,
                    'require_mention': require_mention
                }.items() if v is not None}
                
                pm.update_server_policy(guild_id, **updates)
                
            except ValueError:
                print("Invalid server ID.")
        
        elif choice == "4":
            guild_id = input("Enter server ID to delete: ").strip()
            try:
                guild_id = int(guild_id)
                confirm = input(f"Are you sure you want to delete policy for server {guild_id}? (y/N): ").strip().lower()
                if confirm == 'y':
                    pm.delete_server_policy(guild_id)
                else:
                    print("Cancelled.")
            except ValueError:
                print("Invalid server ID.")
        
        elif choice == "5":
            filename = input("Export filename (default: policies_backup.json): ").strip()
            if not filename:
                filename = "policies_backup.json"
            pm.export_policies(filename)
        
        elif choice == "6":
            filename = input("Import filename (default: policies_backup.json): ").strip()
            if not filename:
                filename = "policies_backup.json"
            try:
                pm.import_policies(filename)
            except FileNotFoundError:
                print(f"File {filename} not found.")
        
        elif choice == "7":
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
