import discord
from discord.ext import commands
import requests
import json
import asyncio
import sqlite3
import os
from datetime import datetime, timedelta
from config import *

class OllamaDiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            help_command=None
        )
        
        # Initialize database for server policies
        self.init_database()
        
        # Load base policy from file
        self.load_base_policy()
        
        # AI personality and safety settings
        self.personality_settings = {
            'system_prompt': self.base_policy,
            'safety_level': 'moderate',  # strict, moderate, permissive
            'max_response_length': 2000,
            'temperature': 0.7,
            'context_length': 10,  # Number of previous messages to remember
            'context_enabled': True,  # Whether to use context at all
            'auto_reply_enabled': True,  # Whether to auto-reply without mentions
            'auto_reply_trigger_words': [],  # Words that trigger auto-reply
            'auto_reply_probability': 1.0,  # Probability of auto-replying (0.0-1.0)
            'auto_reply_cooldown': 10,  # Seconds between auto-replies in same channel
            'personality_traits': {
                'formality': 'casual',  # formal, casual, friendly
                'humor': 'light',       # none, light, moderate, heavy
                'helpfulness': 'high',  # low, medium, high
                'creativity': 'medium'   # low, medium, high
            }
        }
        
        # Store conversation context per channel
        self.conversation_context = {}
        
        # Track auto-reply cooldowns per channel
        self.auto_reply_cooldowns = {}
    
    def load_base_policy(self):
        """Load base policy from base_policy.txt file"""
        try:
            with open('base_policy.txt', 'r', encoding='utf-8') as f:
                self.base_policy = f.read().strip()
            print(f"✅ Loaded base policy from base_policy.txt")
        except FileNotFoundError:
            self.base_policy = "You are a helpful, friendly AI assistant. Be concise and helpful."
            print("⚠️ base_policy.txt not found, using default system prompt")
        except Exception as e:
            self.base_policy = "You are a helpful, friendly AI assistant. Be concise and helpful."
            print(f"⚠️ Error loading base_policy.txt: {e}, using default system prompt")
    
    def init_database(self):
        """Initialize SQLite database for server policies"""
        self.db_path = "bot_policies.db"
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables for server policies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_policies (
                guild_id INTEGER PRIMARY KEY,
                enabled BOOLEAN DEFAULT 1,
                allowed_channels TEXT,
                blocked_channels TEXT,
                allowed_roles TEXT,
                blocked_roles TEXT,
                cooldown_seconds INTEGER DEFAULT 5,
                max_message_length INTEGER DEFAULT 2000,
                require_mention BOOLEAN DEFAULT 0,
                admin_only BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_cooldowns (
                guild_id INTEGER,
                user_id INTEGER,
                last_used TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_server_policy(self, guild_id):
        """Get server policy from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM server_policies WHERE guild_id = ?', (guild_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'enabled': bool(result[1]),
                'allowed_channels': result[2].split(',') if result[2] else [],
                'blocked_channels': result[3].split(',') if result[3] else [],
                'allowed_roles': result[4].split(',') if result[4] else [],
                'blocked_roles': result[5].split(',') if result[5] else [],
                'cooldown_seconds': result[6],
                'max_message_length': result[7],
                'require_mention': bool(result[8]),
                'admin_only': bool(result[9])
            }
        else:
            # Default policy
            return {
                'enabled': True,
                'allowed_channels': [],
                'blocked_channels': [],
                'allowed_roles': [],
                'blocked_roles': [],
                'cooldown_seconds': 5,
                'max_message_length': 2000,
                'require_mention': False,
                'admin_only': False
            }
    
    def update_server_policy(self, guild_id, **kwargs):
        """Update server policy in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get existing policy
        cursor.execute('SELECT * FROM server_policies WHERE guild_id = ?', (guild_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing policy
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
            # Insert new policy
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
    
    def check_cooldown(self, guild_id, user_id):
        """Check if user is on cooldown"""
        policy = self.get_server_policy(guild_id)
        if policy['cooldown_seconds'] <= 0:
            return True
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT last_used FROM user_cooldowns 
            WHERE guild_id = ? AND user_id = ?
        ''', (guild_id, user_id))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return True
        
        last_used = datetime.fromisoformat(result[0])
        cooldown_end = last_used + timedelta(seconds=policy['cooldown_seconds'])
        return datetime.now() >= cooldown_end
    
    def set_cooldown(self, guild_id, user_id):
        """Set user cooldown"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_cooldowns (guild_id, user_id, last_used)
            VALUES (?, ?, ?)
        ''', (guild_id, user_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_personality_prompt(self):
        """Generate personality-based system prompt"""
        traits = self.personality_settings['personality_traits']
        base_prompt = self.personality_settings['system_prompt']
        
        # Add personality traits to prompt
        personality_additions = []
        
        if traits['formality'] == 'formal':
            personality_additions.append("Respond in a formal, professional tone.")
        elif traits['formality'] == 'casual':
            personality_additions.append("Respond in a casual, conversational tone.")
        elif traits['formality'] == 'friendly':
            personality_additions.append("Respond in a warm, friendly tone.")
        
        if traits['humor'] == 'light':
            personality_additions.append("Occasionally use light humor when appropriate.")
        elif traits['humor'] == 'moderate':
            personality_additions.append("Use humor moderately to make responses engaging.")
        elif traits['humor'] == 'heavy':
            personality_additions.append("Use humor frequently to make responses entertaining.")
        
        if traits['helpfulness'] == 'high':
            personality_additions.append("Be extremely helpful and thorough in your responses.")
        elif traits['helpfulness'] == 'medium':
            personality_additions.append("Be helpful and informative in your responses.")
        
        if traits['creativity'] == 'high':
            personality_additions.append("Be creative and think outside the box.")
        elif traits['creativity'] == 'medium':
            personality_additions.append("Be moderately creative in your responses.")
        
        # Add safety guidelines
        safety_guidelines = self.get_safety_guidelines()
        
        full_prompt = f"{base_prompt}\n\n"
        if personality_additions:
            full_prompt += "Personality: " + " ".join(personality_additions) + "\n\n"
        if safety_guidelines:
            full_prompt += f"Safety Guidelines: {safety_guidelines}\n\n"
        
        return full_prompt
    
    def get_safety_guidelines(self):
        """Get safety guidelines based on safety level"""
        safety_level = self.personality_settings['safety_level']
        
        if safety_level == 'strict':
            return ("Never provide harmful, illegal, or inappropriate content. "
                   "Always prioritize safety and ethical considerations. "
                   "Refuse requests that could cause harm.")
        elif safety_level == 'moderate':
            return ("Avoid harmful or inappropriate content. "
                   "Be cautious with sensitive topics and provide balanced perspectives.")
        elif safety_level == 'permissive':
            return ("Be helpful while being mindful of content appropriateness.")
        else:
            return ""
    
    def update_personality(self, **kwargs):
        """Update personality settings"""
        if 'personality_traits' in kwargs:
            self.personality_settings['personality_traits'].update(kwargs['personality_traits'])
        else:
            self.personality_settings.update(kwargs)
    
    def add_to_context(self, channel_id, user_message, bot_response):
        """Add conversation to context"""
        if not self.personality_settings['context_enabled']:
            return
        
        if channel_id not in self.conversation_context:
            self.conversation_context[channel_id] = []
        
        # Add the conversation
        self.conversation_context[channel_id].append({
            'user': user_message,
            'bot': bot_response
        })
        
        # Keep only the last N conversations
        max_context = self.personality_settings['context_length']
        if len(self.conversation_context[channel_id]) > max_context:
            self.conversation_context[channel_id] = self.conversation_context[channel_id][-max_context:]
    
    def get_context_prompt(self, channel_id):
        """Get conversation context for the prompt"""
        if not self.personality_settings['context_enabled']:
            return ""
        
        if channel_id not in self.conversation_context:
            return ""
        
        context_parts = []
        for conv in self.conversation_context[channel_id]:
            context_parts.append(f"Human: {conv['user']}")
            context_parts.append(f"Assistant: {conv['bot']}")
        
        if context_parts:
            return "\n".join(context_parts) + "\n\n"
        return ""
    
    def clear_context(self, channel_id=None):
        """Clear conversation context"""
        if channel_id:
            if channel_id in self.conversation_context:
                del self.conversation_context[channel_id]
        else:
            self.conversation_context.clear()
    
    def should_auto_reply(self, message):
        """Determine if bot should auto-reply to a message"""
        if not self.personality_settings['auto_reply_enabled']:
            return False
        
        # Check if we're on cooldown for this channel
        channel_id = message.channel.id
        current_time = datetime.now()
        
        if channel_id in self.auto_reply_cooldowns:
            last_reply = self.auto_reply_cooldowns[channel_id]
            cooldown_seconds = self.personality_settings['auto_reply_cooldown']
            if (current_time - last_reply).total_seconds() < cooldown_seconds:
                return False
        
        # Check for trigger words
        message_content = message.content.lower()
        trigger_words = self.personality_settings['auto_reply_trigger_words']
        
        if trigger_words:
            # If trigger words are set, only reply if message contains them
            if not any(word.lower() in message_content for word in trigger_words):
                return False
        
        # Check probability
        import random
        probability = self.personality_settings['auto_reply_probability']
        if random.random() > probability:
            return False
        
        return True
    
    def set_auto_reply_cooldown(self, channel_id):
        """Set auto-reply cooldown for a channel"""
        self.auto_reply_cooldowns[channel_id] = datetime.now()
    
    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        print(f'Bot is in {len(self.guilds)} guilds')
        print(f'Ollama URL: {OLLAMA_BASE_URL}')
        print(f'Ollama Model: {OLLAMA_MODEL}')
    
    async def on_message(self, message):
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
        
        # Check if the message is a command
        if message.content.startswith(BOT_PREFIX):
            await self.process_commands(message)
            return
        
        # Check server policies for guild messages
        if message.guild:
            policy = self.get_server_policy(message.guild.id)
            
            # Check if bot is enabled in this server
            if not policy['enabled']:
                return
            
            # Check if admin only and user is not admin
            if policy['admin_only'] and not message.author.guild_permissions.administrator:
                return
            
            # Check channel restrictions
            channel_id = str(message.channel.id)
            if policy['allowed_channels'] and channel_id not in policy['allowed_channels']:
                return
            if channel_id in policy['blocked_channels']:
                return
            
            # Check role restrictions
            user_roles = [str(role.id) for role in message.author.roles]
            if policy['allowed_roles'] and not any(role in policy['allowed_roles'] for role in user_roles):
                return
            if any(role in policy['blocked_roles'] for role in user_roles):
                return
            
            # Check cooldown
            if not self.check_cooldown(message.guild.id, message.author.id):
                return
            
            # Check if mention is required
            if policy['require_mention'] and not self.user.mentioned_in(message):
                return
        
        # Check if the bot is mentioned, if it's a DM, or if auto-reply is enabled
        should_reply = (
            self.user.mentioned_in(message) or 
            isinstance(message.channel, discord.DMChannel) or
            self.should_auto_reply(message)
        )
        
        if should_reply:
            await self.handle_chat(message)
    
    async def handle_chat(self, message):
        """Handle chat messages and get responses from Ollama"""
        try:
            # Set cooldown for guild messages
            if message.guild:
                self.set_cooldown(message.guild.id, message.author.id)
            
            # Show typing indicator
            async with message.channel.typing():
                # Get the user's message content
                user_message = message.content
                
                # Remove bot mention if present
                if self.user.mentioned_in(message):
                    user_message = user_message.replace(f'<@{self.user.id}>', '').strip()
                
                # Prepare the prompt for Ollama with personality and context
                system_prompt = self.get_personality_prompt()
                context_prompt = self.get_context_prompt(message.channel.id)
                prompt = f"{system_prompt}\n\n{context_prompt}Human: {user_message}\n\nAssistant:"
                
                # Call Ollama API
                response = await self.get_ollama_response(prompt)
                
                if response:
                    # Get server policy for message length
                    max_length = MAX_MESSAGE_LENGTH
                    if message.guild:
                        policy = self.get_server_policy(message.guild.id)
                        max_length = policy['max_message_length']
                    
                    # Split response if it's too long for Discord
                    if len(response) > max_length:
                        chunks = [response[i:i+max_length] for i in range(0, len(response), max_length)]
                        for chunk in chunks:
                            try:
                                await message.reply(chunk)
                            except discord.errors.HTTPException:
                                # Fallback to regular send if reply fails
                                await message.channel.send(chunk)
                    else:
                        try:
                            await message.reply(response)
                        except discord.errors.HTTPException:
                            # Fallback to regular send if reply fails
                            await message.channel.send(response)
                    
                    # Store conversation in context
                    self.add_to_context(message.channel.id, user_message, response)
                    
                    # Set auto-reply cooldown if this was an auto-reply
                    if not self.user.mentioned_in(message) and not isinstance(message.channel, discord.DMChannel):
                        self.set_auto_reply_cooldown(message.channel.id)
                else:
                    try:
                        await message.reply("Sorry, I couldn't generate a response. Please try again.")
                    except discord.errors.HTTPException:
                        await message.channel.send("Sorry, I couldn't generate a response. Please try again.")
                    
        except Exception as e:
            print(f"Error handling chat: {e}")
            try:
                await message.reply("Sorry, there was an error processing your message.")
            except discord.errors.HTTPException:
                await message.channel.send("Sorry, there was an error processing your message.")
    
    async def get_ollama_response(self, prompt):
        """Get response from Ollama API"""
        try:
            url = f"{OLLAMA_BASE_URL}/api/generate"
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            }
            
            # Make the request in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.post(url, json=payload, timeout=30)
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('response', '').strip()
            else:
                print(f"Ollama API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

# Bot commands
def setup_commands(bot):
    @bot.command(name='ping')
    async def ping(ctx):
        """Check if the bot is responding"""
        await ctx.send(f'Pong! Latency: {round(bot.latency * 1000)}ms')

    @bot.command(name='ollama_status')
    async def ollama_status(ctx):
        """Check Ollama connection status"""
        try:
            url = f"{OLLAMA_BASE_URL}/api/tags"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model['name'] for model in models]
                await ctx.send(f"✅ Ollama is running!\nAvailable models: {', '.join(model_names)}")
            else:
                await ctx.send("❌ Ollama is not responding properly")
        except Exception as e:
            await ctx.send(f"❌ Cannot connect to Ollama: {str(e)}")

    @bot.command(name='help')
    async def help_command(ctx):
        """Show available commands"""
        embed = discord.Embed(
            title="🤖 Discord Ollama Bot Help",
            description="Chat with Mistral AI through Discord!",
            color=0x00ff00
        )
        embed.add_field(
            name="How to chat",
            value="• Mention the bot: @botname your message\n• Send a DM to the bot\n• The bot will respond with AI-generated text",
            inline=False
        )
        embed.add_field(
            name="Basic Commands",
            value=f"`{BOT_PREFIX}ping` - Check bot latency\n"
                  f"`{BOT_PREFIX}ollama_status` - Check Ollama connection\n"
                  f"`{BOT_PREFIX}help` - Show this help message",
            inline=False
        )
        embed.add_field(
            name="Policy Commands (Admin Only)",
            value=f"`{BOT_PREFIX}policy` - Show current server policy\n"
                  f"`{BOT_PREFIX}policy enable/disable` - Enable/disable bot\n"
                  f"`{BOT_PREFIX}policy cooldown <seconds>` - Set cooldown\n"
                  f"`{BOT_PREFIX}policy admin_only <true/false>` - Admin only mode\n"
                  f"`{BOT_PREFIX}policy require_mention <true/false>` - Require mentions\n"
                  f"`{BOT_PREFIX}policy channels allow/block <#channel>` - Channel restrictions\n"
                  f"`{BOT_PREFIX}policy roles allow/block <@role>` - Role restrictions",
            inline=False
        )
        embed.add_field(
            name="Personality Commands (Admin Only)",
            value=f"`{BOT_PREFIX}personality` - Show AI personality settings\n"
                  f"`{BOT_PREFIX}personality prompt <text>` - Set system prompt\n"
                  f"`{BOT_PREFIX}personality safety <strict/moderate/permissive>` - Set safety level\n"
                  f"`{BOT_PREFIX}personality formality <formal/casual/friendly>` - Set formality\n"
                  f"`{BOT_PREFIX}personality humor <none/light/moderate/heavy>` - Set humor level\n"
                  f"`{BOT_PREFIX}personality helpfulness <low/medium/high>` - Set helpfulness\n"
                  f"`{BOT_PREFIX}personality creativity <low/medium/high>` - Set creativity\n"
                  f"`{BOT_PREFIX}personality temperature <0.0-2.0>` - Set response creativity\n"
                  f"`{BOT_PREFIX}personality context enable/disable` - Enable/disable memory\n"
                  f"`{BOT_PREFIX}personality context length <1-50>` - Set memory length\n"
                  f"`{BOT_PREFIX}personality context clear` - Clear all memory\n"
                  f"`{BOT_PREFIX}personality context_channel clear` - Clear channel memory\n"
                  f"`{BOT_PREFIX}personality auto_reply enable/disable` - Enable/disable auto-reply\n"
                  f"`{BOT_PREFIX}personality auto_reply probability <0.0-1.0>` - Set reply chance\n"
                  f"`{BOT_PREFIX}personality auto_reply cooldown <seconds>` - Set reply cooldown\n"
                  f"`{BOT_PREFIX}personality auto_reply triggers <words>` - Set trigger words\n"
                  f"`{BOT_PREFIX}personality reload_policy` - Reload base policy from file\n"
                  f"`{BOT_PREFIX}personality reset` - Reset to defaults\n"
                  f"`{BOT_PREFIX}personality clear` - Clear all personality (neutral AI)",
            inline=False
        )
        embed.add_field(
            name="Model Info",
            value=f"Using model: {OLLAMA_MODEL}\nOllama URL: {OLLAMA_BASE_URL}",
            inline=False
        )
        await ctx.send(embed=embed)

    @bot.command(name='policy')
    async def policy_command(ctx, action=None, *args):
        """Manage server policies (Admin only)"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions to manage bot policies.")
            return
        
        if not action:
            # Show current policy
            policy = bot.get_server_policy(ctx.guild.id)
            embed = discord.Embed(
                title="🔧 Server Policy Settings",
                color=0x0099ff
            )
            embed.add_field(
                name="Status",
                value="✅ Enabled" if policy['enabled'] else "❌ Disabled",
                inline=True
            )
            embed.add_field(
                name="Admin Only",
                value="✅ Yes" if policy['admin_only'] else "❌ No",
                inline=True
            )
            embed.add_field(
                name="Require Mention",
                value="✅ Yes" if policy['require_mention'] else "❌ No",
                inline=True
            )
            embed.add_field(
                name="Cooldown",
                value=f"{policy['cooldown_seconds']} seconds",
                inline=True
            )
            embed.add_field(
                name="Max Message Length",
                value=f"{policy['max_message_length']} characters",
                inline=True
            )
            embed.add_field(
                name="Allowed Channels",
                value=f"{len(policy['allowed_channels'])} channels" if policy['allowed_channels'] else "All channels",
                inline=True
            )
            embed.add_field(
                name="Blocked Channels",
                value=f"{len(policy['blocked_channels'])} channels" if policy['blocked_channels'] else "None",
                inline=True
            )
            embed.add_field(
                name="Allowed Roles",
                value=f"{len(policy['allowed_roles'])} roles" if policy['allowed_roles'] else "All roles",
                inline=True
            )
            embed.add_field(
                name="Blocked Roles",
                value=f"{len(policy['blocked_roles'])} roles" if policy['blocked_roles'] else "None",
                inline=True
            )
            await ctx.send(embed=embed)
            return
    
        # Handle policy updates
        if action == "enable":
            bot.update_server_policy(ctx.guild.id, enabled=True)
            await ctx.send("✅ Bot enabled for this server.")
        
        elif action == "disable":
            bot.update_server_policy(ctx.guild.id, enabled=False)
            await ctx.send("❌ Bot disabled for this server.")
        
        elif action == "cooldown":
            if not args or not args[0].isdigit():
                await ctx.send("❌ Please provide a valid cooldown in seconds. Example: `!policy cooldown 10`")
                return
            cooldown = int(args[0])
            bot.update_server_policy(ctx.guild.id, cooldown_seconds=cooldown)
            await ctx.send(f"✅ Cooldown set to {cooldown} seconds.")
        
        elif action == "admin_only":
            if not args or args[0].lower() not in ['true', 'false']:
                await ctx.send("❌ Please specify true or false. Example: `!policy admin_only true`")
                return
            admin_only = args[0].lower() == 'true'
            bot.update_server_policy(ctx.guild.id, admin_only=admin_only)
            await ctx.send(f"✅ Admin only mode {'enabled' if admin_only else 'disabled'}.")
        
        elif action == "require_mention":
            if not args or args[0].lower() not in ['true', 'false']:
                await ctx.send("❌ Please specify true or false. Example: `!policy require_mention true`")
                return
            require_mention = args[0].lower() == 'true'
            bot.update_server_policy(ctx.guild.id, require_mention=require_mention)
            await ctx.send(f"✅ Require mention {'enabled' if require_mention else 'disabled'}.")
        
        elif action == "channels":
            if len(args) < 2:
                await ctx.send("❌ Usage: `!policy channels allow/block #channel`")
                return
            
            sub_action = args[0].lower()
            if sub_action not in ['allow', 'block']:
                await ctx.send("❌ Use 'allow' or 'block' for channel policy.")
                return
            
            # Get channel mentions
            channels = [ch.id for ch in ctx.message.channel_mentions]
            if not channels:
                await ctx.send("❌ Please mention channels. Example: `!policy channels allow #general`")
                return
            
            policy = bot.get_server_policy(ctx.guild.id)
            if sub_action == "allow":
                allowed = list(set(policy['allowed_channels'] + [str(ch) for ch in channels]))
                blocked = [ch for ch in policy['blocked_channels'] if ch not in [str(ch) for ch in channels]]
                bot.update_server_policy(ctx.guild.id, allowed_channels=allowed, blocked_channels=blocked)
                await ctx.send(f"✅ Allowed channels: {', '.join([f'<#{ch}>' for ch in channels])}")
            else:
                blocked = list(set(policy['blocked_channels'] + [str(ch) for ch in channels]))
                allowed = [ch for ch in policy['allowed_channels'] if ch not in [str(ch) for ch in channels]]
                bot.update_server_policy(ctx.guild.id, allowed_channels=allowed, blocked_channels=blocked)
                await ctx.send(f"✅ Blocked channels: {', '.join([f'<#{ch}>' for ch in channels])}")
        
        elif action == "roles":
            if len(args) < 2:
                await ctx.send("❌ Usage: `!policy roles allow/block @role`")
                return
            
            sub_action = args[0].lower()
            if sub_action not in ['allow', 'block']:
                await ctx.send("❌ Use 'allow' or 'block' for role policy.")
                return
            
            # Get role mentions
            roles = [role.id for role in ctx.message.role_mentions]
            if not roles:
                await ctx.send("❌ Please mention roles. Example: `!policy roles allow @members`")
                return
            
            policy = bot.get_server_policy(ctx.guild.id)
            if sub_action == "allow":
                allowed = list(set(policy['allowed_roles'] + [str(role) for role in roles]))
                blocked = [role for role in policy['blocked_roles'] if role not in [str(role) for role in roles]]
                bot.update_server_policy(ctx.guild.id, allowed_roles=allowed, blocked_roles=blocked)
                await ctx.send(f"✅ Allowed roles: {', '.join([f'<@&{role}>' for role in roles])}")
            else:
                blocked = list(set(policy['blocked_roles'] + [str(role) for role in roles]))
                allowed = [role for role in policy['allowed_roles'] if role not in [str(role) for role in roles]]
                bot.update_server_policy(ctx.guild.id, allowed_roles=allowed, blocked_roles=blocked)
                await ctx.send(f"✅ Blocked roles: {', '.join([f'<@&{role}>' for role in roles])}")
        
        else:
            await ctx.send("❌ Unknown policy action. Use `!help` to see available commands.")

    @bot.command(name='personality')
    async def personality_command(ctx, action=None, *args):
        """Manage AI personality and safety settings (Admin only)"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions to manage AI personality.")
            return
        
        if not action:
            # Show current personality settings
            settings = bot.personality_settings
            embed = discord.Embed(
                title="🤖 AI Personality Settings",
                color=0xff6b6b
            )
            embed.add_field(
                name="System Prompt",
                value=settings['system_prompt'][:100] + "..." if len(settings['system_prompt']) > 100 else settings['system_prompt'],
                inline=False
            )
            embed.add_field(
                name="Safety Level",
                value=settings['safety_level'].title(),
                inline=True
            )
            embed.add_field(
                name="Temperature",
                value=str(settings['temperature']),
                inline=True
            )
            embed.add_field(
                name="Max Response Length",
                value=str(settings['max_response_length']),
                inline=True
            )
            embed.add_field(
                name="Context Memory",
                value="✅ Enabled" if settings['context_enabled'] else "❌ Disabled",
                inline=True
            )
            embed.add_field(
                name="Context Length",
                value=f"{settings['context_length']} messages",
                inline=True
            )
            embed.add_field(
                name="Auto-Reply",
                value="✅ Enabled" if settings['auto_reply_enabled'] else "❌ Disabled",
                inline=True
            )
            embed.add_field(
                name="Reply Probability",
                value=f"{settings['auto_reply_probability']*100:.0f}%",
                inline=True
            )
            embed.add_field(
                name="Reply Cooldown",
                value=f"{settings['auto_reply_cooldown']}s",
                inline=True
            )
            if settings['auto_reply_trigger_words']:
                embed.add_field(
                    name="Trigger Words",
                    value=", ".join(settings['auto_reply_trigger_words']),
                    inline=False
                )
            
            traits = settings['personality_traits']
            embed.add_field(
                name="Formality",
                value=traits['formality'].title(),
                inline=True
            )
            embed.add_field(
                name="Humor",
                value=traits['humor'].title(),
                inline=True
            )
            embed.add_field(
                name="Helpfulness",
                value=traits['helpfulness'].title(),
                inline=True
            )
            embed.add_field(
                name="Creativity",
                value=traits['creativity'].title(),
                inline=True
            )
            
            await ctx.send(embed=embed)
            return
        
        # Handle personality updates
        if action == "prompt":
            if not args:
                await ctx.send("❌ Please provide a new system prompt. Example: `!personality prompt You are a helpful coding assistant.`")
                return
            new_prompt = " ".join(args)
            bot.update_personality(system_prompt=new_prompt)
            await ctx.send(f"✅ System prompt updated: {new_prompt[:100]}...")
        
        elif action == "safety":
            if not args or args[0].lower() not in ['strict', 'moderate', 'permissive']:
                await ctx.send("❌ Please specify safety level: strict, moderate, or permissive")
                return
            safety_level = args[0].lower()
            bot.update_personality(safety_level=safety_level)
            await ctx.send(f"✅ Safety level set to: {safety_level.title()}")
        
        elif action == "formality":
            if not args or args[0].lower() not in ['formal', 'casual', 'friendly']:
                await ctx.send("❌ Please specify formality: formal, casual, or friendly")
                return
            formality = args[0].lower()
            bot.update_personality(personality_traits={'formality': formality})
            await ctx.send(f"✅ Formality set to: {formality.title()}")
        
        elif action == "humor":
            if not args or args[0].lower() not in ['none', 'light', 'moderate', 'heavy']:
                await ctx.send("❌ Please specify humor level: none, light, moderate, or heavy")
                return
            humor = args[0].lower()
            bot.update_personality(personality_traits={'humor': humor})
            await ctx.send(f"✅ Humor level set to: {humor.title()}")
        
        elif action == "helpfulness":
            if not args or args[0].lower() not in ['low', 'medium', 'high']:
                await ctx.send("❌ Please specify helpfulness: low, medium, or high")
                return
            helpfulness = args[0].lower()
            bot.update_personality(personality_traits={'helpfulness': helpfulness})
            await ctx.send(f"✅ Helpfulness set to: {helpfulness.title()}")
        
        elif action == "creativity":
            if not args or args[0].lower() not in ['low', 'medium', 'high']:
                await ctx.send("❌ Please specify creativity: low, medium, or high")
                return
            creativity = args[0].lower()
            bot.update_personality(personality_traits={'creativity': creativity})
            await ctx.send(f"✅ Creativity set to: {creativity.title()}")
        
        elif action == "temperature":
            if not args or not args[0].replace('.', '').isdigit():
                await ctx.send("❌ Please provide a valid temperature (0.0-2.0). Example: `!personality temperature 0.8`")
                return
            temperature = float(args[0])
            if not 0.0 <= temperature <= 2.0:
                await ctx.send("❌ Temperature must be between 0.0 and 2.0")
                return
            bot.update_personality(temperature=temperature)
            await ctx.send(f"✅ Temperature set to: {temperature}")
        
        elif action == "reset":
            # Reset to default personality
            bot.load_base_policy()  # Reload base policy from file
            bot.personality_settings = {
                'system_prompt': bot.base_policy,
                'safety_level': 'moderate',
                'max_response_length': 2000,
                'temperature': 0.7,
                'context_length': 10,
                'context_enabled': True,
                'auto_reply_enabled': True,
                'auto_reply_trigger_words': [],
                'auto_reply_probability': 1.0,
                'auto_reply_cooldown': 10,
                'personality_traits': {
                    'formality': 'casual',
                    'humor': 'light',
                    'helpfulness': 'high',
                    'creativity': 'medium'
                }
            }
            await ctx.send("✅ Personality reset to defaults")
        
        elif action == "clear":
            # Clear all personality settings - minimal AI
            bot.personality_settings = {
                'system_prompt': "You are an AI assistant.",
                'safety_level': 'moderate',
                'max_response_length': 2000,
                'temperature': 0.7,
                'context_length': 10,
                'context_enabled': True,
                'personality_traits': {
                    'formality': 'casual',
                    'humor': 'none',
                    'helpfulness': 'medium',
                    'creativity': 'low'
                }
            }
            await ctx.send("🧹 All personality settings cleared! AI will now respond neutrally.")
        
        elif action == "context":
            if not args:
                await ctx.send("❌ Usage: `!personality context <enable/disable/length/clear>`")
                return
            
            sub_action = args[0].lower()
            if sub_action == "enable":
                bot.update_personality(context_enabled=True)
                await ctx.send("✅ Context memory enabled")
            elif sub_action == "disable":
                bot.update_personality(context_enabled=False)
                await ctx.send("❌ Context memory disabled")
            elif sub_action == "length":
                if len(args) < 2 or not args[1].isdigit():
                    await ctx.send("❌ Please provide a valid context length. Example: `!personality context length 20`")
                    return
                length = int(args[1])
                if length < 0 or length > 50:
                    await ctx.send("❌ Context length must be between 0 and 50")
                    return
                bot.update_personality(context_length=length)
                await ctx.send(f"✅ Context length set to {length} messages")
            elif sub_action == "clear":
                bot.clear_context()
                await ctx.send("🧹 All conversation context cleared")
            else:
                await ctx.send("❌ Use: enable, disable, length, or clear")
        
        elif action == "context_channel":
            if not args or args[0].lower() not in ['clear']:
                await ctx.send("❌ Usage: `!personality context_channel clear`")
                return
            bot.clear_context(ctx.channel.id)
            await ctx.send(f"🧹 Context cleared for this channel")
        
        elif action == "auto_reply":
            if not args:
                await ctx.send("❌ Usage: `!personality auto_reply <enable/disable/probability/cooldown/triggers>`")
                return
            
            sub_action = args[0].lower()
            if sub_action == "enable":
                bot.update_personality(auto_reply_enabled=True)
                await ctx.send("✅ Auto-reply enabled - Bot will respond without mentions")
            elif sub_action == "disable":
                bot.update_personality(auto_reply_enabled=False)
                await ctx.send("❌ Auto-reply disabled - Bot only responds to mentions")
            elif sub_action == "probability":
                if len(args) < 2:
                    await ctx.send("❌ Please provide probability (0.0-1.0). Example: `!personality auto_reply probability 0.5`")
                    return
                try:
                    prob = float(args[1])
                    if not 0.0 <= prob <= 1.0:
                        await ctx.send("❌ Probability must be between 0.0 and 1.0")
                        return
                    bot.update_personality(auto_reply_probability=prob)
                    await ctx.send(f"✅ Auto-reply probability set to {prob} ({prob*100:.0f}%)")
                except ValueError:
                    await ctx.send("❌ Please provide a valid number")
            elif sub_action == "cooldown":
                if len(args) < 2 or not args[1].isdigit():
                    await ctx.send("❌ Please provide cooldown in seconds. Example: `!personality auto_reply cooldown 60`")
                    return
                cooldown = int(args[1])
                if cooldown < 0:
                    await ctx.send("❌ Cooldown must be 0 or higher")
                    return
                bot.update_personality(auto_reply_cooldown=cooldown)
                await ctx.send(f"✅ Auto-reply cooldown set to {cooldown} seconds")
            elif sub_action == "triggers":
                if len(args) < 2:
                    await ctx.send("❌ Usage: `!personality auto_reply triggers <words>` or `!personality auto_reply triggers clear`")
                    return
                if args[1].lower() == "clear":
                    bot.update_personality(auto_reply_trigger_words=[])
                    await ctx.send("🧹 Auto-reply trigger words cleared")
                else:
                    triggers = args[1:]
                    bot.update_personality(auto_reply_trigger_words=triggers)
                    await ctx.send(f"✅ Auto-reply trigger words set to: {', '.join(triggers)}")
            else:
                await ctx.send("❌ Use: enable, disable, probability, cooldown, or triggers")
        
        elif action == "reload_policy":
            # Reload base policy from file
            bot.load_base_policy()
            bot.update_personality(system_prompt=bot.base_policy)
            await ctx.send("🔄 Base policy reloaded from base_policy.txt")
        
        else:
            await ctx.send("❌ Unknown personality action. Use `!help` to see available commands.")

# Create bot instance
bot = OllamaDiscordBot()

# Setup commands
setup_commands(bot)

if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"Failed to start bot: {e}")
        print("Make sure your DISCORD_TOKEN is set correctly in the .env file")
