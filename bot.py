import json
import os
import random
import functools
from typing import DefaultDict

from twitchio.ext import commands
from twitchio.ext.commands.core import Command

from pythonosc.udp_client import SimpleUDPClient


def convert_value(value, datatype):
    if datatype == "string":
        return str(value)
    elif datatype == "integer":
        return int(value)
    elif datatype == "float":
        return float(value)
    elif datatype == "bool":
        return bool(value)
    else:
        raise TypeError("<!!> Unknown datatype {datatype}")


class OscCommandData:
    name = ""
    address = ""
    datatype = ""
    default_value = ""

    def as_dict(self):
        return {
            "name": self.name,
            "address": self.address,
            "datatype": self.datatype,
            "default_value": self.default_value,
        }
    
    @staticmethod
    def create_from_json_entry(data):
        new_command = OscCommandData()
        new_command.name = data["name"]
        new_command.address = data["address"]
        new_command.datatype = data.get("datatype", "string")
        new_command.default_value = data.get("default_value", "")
        return new_command


class OscCommand(Command):
    def __init__(self, osc_command_data, name=None):
        if name is not None:
            osc_command_data.name = name
        elif name is None and osc_command_data.name == "":
            raise Exception("Can't register an unnamed OscCommandData.")

        self.osc_command_data = osc_command_data

        super().__init__(osc_command_data.name, self.receive_command)

    async def receive_command(self, ctx):
        args = ctx.message.content.split(" ")
        self.execute_command(value=args[1] if len(args) >= 2 else None)
    
    def execute_command(self, value=None):
        client = SimpleUDPClient("192.168.1.18", 7000)

        value = value if value is not None else self.osc_command_data.default_value
        client.send_message(self.osc_command_data.address,
                            convert_value(value, self.osc_command_data.datatype))


def mods_only(func):
    async def wrapper(*args, **kwargs):
        print(args, kwargs)
        return await func(*args, **kwargs)
    return wrapper


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(irc_token='oauth:twszee7twbiyiphmus1l43dt7gwgez',
                         prefix='!',
                         nick="DiFFtY",
                         initial_channels=['diffty'])
        
        self.unassigned_commands = []
        
        self.load_from_disk()
        
    async def event_ready(self):
        # We are logged in and ready to chat and use commands...
        print(f'Logged in as | {self.nick}')

    @commands.command()
    async def testregister(self, ctx):
        if not ctx.author.is_mod:
            raise Exception(f"User {ctx.author.name} executed unauthorized command {ctx.command.name}")
            
        unassigned_commands = self.get_unassigned_commands()
        rand_idx = random.randrange(0, len(unassigned_commands))
        self.register_command(unassigned_commands[rand_idx], ctx.author.name)

        self.write_to_disk()

        # Send a hello back!
        await ctx.send(f'New command assigned : !{ctx.author.name}')
    
    def register_command(self, command_data: OscCommandData, name: str=None):
        if name is None and command_data.name == "":
            self.unassigned_commands.append(command_data)
        else:
            self.assign_command(command_data, name)

    def assign_command(self, command_data: OscCommandData, name: str):
        command = OscCommand(command_data, name=name)
        self.add_command(command)
        if command_data in self.unassigned_commands:
            self.unassigned_commands.remove(command_data)

    def load_from_disk(self):
        if os.path.exists("commands.json"):
            fp = open("commands.json", "r")
            data = json.load(fp)
            for command_data in data:
                new_command = OscCommandData.create_from_json_entry(command_data)
                self.register_command(new_command)
            fp.close()

    def write_to_disk(self):
        json_data = []
        for c in self.get_all_commands():
            json_data.append(c.as_dict())
        fp = open("commands.json", "w")
        fp.write(json.dumps(json_data, indent=4))
        fp.close()

    def get_all_commands(self):
        return self.get_unassigned_commands() + self.get_assigned_commands()

    def get_unassigned_commands(self):
        return self.unassigned_commands

    def get_assigned_commands(self):
        return list(
            map(
                lambda cmd: cmd.osc_command_data,
                filter(lambda c: c.__class__ is OscCommand, self.commands.values())
            )
        )
    
    async def event_usernotice_subscription(self, metadata):
        unassigned_commands = self.get_unassigned_commands()
        rand_idx = random.randrange(0, len(unassigned_commands))
        self.register_command(unassigned_commands[rand_idx], metadata.user.name)
        self.write_to_disk()


if __name__ == "__main__":
    bot = Bot()
    bot.run()
