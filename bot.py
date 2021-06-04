import json
import os
import random
from typing import DefaultDict

from twitchio.ext import commands


class Command:
    name = ""
    address = ""
    default_value = ""

    def as_dict(self):
        return {
            "name": self.name,
            "address": self.address,
            "default_value": self.default_value,
        }

    @staticmethod
    def create_from_json_entry(self, data):
        new_command = Command()
        new_command.name = data["name"]
        new_command.address = data["address"]
        new_command.default_value = data["default_value"]
        return new_command


class Manager:
    def __init__(self):
        self.commands = []
        self.load_from_disk()
    
    def execute_command(self, command, value=None):
        value = value if value is not None else command.default_value
        cmd = f"{command.address} {value}"
        print(cmd)

    def assign_command(self, command, name):
        command.name = name

    def load_from_disk(self):
        if os.path.exists("commands.json"):
            fp = open("commands.json", "r")
            data = json.load(fp)
            for command_data in data:
                new_command = Command.create_from_json_entry(command_data)
                self.commands.append(new_command)
            fp.close()

    def write_to_disk(self):
        json_data = []
        for c in self.commands:
            json_data.append(c.as_dict())
        fp = open("commands.json", "w")
        fp.write(json_data)
        fp.close()

    def get_unassigned_commands(self):
        return list(filter(lambda c: c.name == "", self.commands))

    def get_assigned_commands(self):
        return list(filter(lambda c: c.name != "", self.commands))

    def on_sub(self):
        pass


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(token='coxwfoge6t8mnd8f1xednqvo6c20un', prefix='!', initial_channels=['diffty'])
        self.manager = Manager()
        
    async def event_ready(self):
        # We are logged in and ready to chat and use commands...
        print(f'Logged in as | {self.nick}')

    @commands.command()
    async def hello(self, ctx: commands.Context):
        # Send a hello back!
        await ctx.send(f'Hello {ctx.author.name}!')
    
    @commands.command()
    async def register(self, ctx: commands.Context):
        unassigned_commands = self.manager.get_unassigned_commands()

        rand_idx = random.randint(range(len(unassigned_commands)))

        self.manager.assign_command(unassigned_commands[rand_idx], f"!{ctx.author.name}")
        
        # Send a hello back!
        await ctx.send(f'New command assigned : !{ctx.author.name} !')


bot = Bot()
bot.run()