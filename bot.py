import json
import os
import random
import functools
import asyncio
from typing import DefaultDict

from twitchio.ext import commands
from twitchio.ext.commands.core import Command

from pythonosc.udp_client import SimpleUDPClient


OSC_IP = "192.168.1.18"
#OSC_IP = "127.0.0.1"
OSC_PASSWORD = 7000


def assert_user_is_mod(ctx):
    if not ctx.author.is_mod:
        raise Exception(f"User {ctx.author.name} executed unauthorized command {ctx.command.name}")

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
    def __init__(self):
        self.name = ""
        self.address = ""
        self.datatype = ""
        self.on_value = ""
        self.off_value = ""
        self.duration = ""

    def as_dict(self):
        return {
            "name": self.name,
            "address": self.address,
            "datatype": self.datatype,
            "off_value": self.off_value,
            "on_value": self.on_value,
            "duration": self.duration,
        }
    
    @staticmethod
    def create_from_json_entry(data):
        new_command_data = OscCommandData()
        new_command_data.name = data["name"]
        new_command_data.address = data["address"]
        new_command_data.duration = data.get("duration", -1)
        new_command_data.off_value = data.get("off_value", 0)
        new_command_data.on_value = data.get("on_value", 1)
        new_command_data.datatype = data.get("datatype", "string")
        return new_command_data


class OscCommand(Command):
    def __init__(self, osc_command_data: OscCommandData, name=None):
        if name is not None:
            osc_command_data.name = name
        elif name is None and osc_command_data.name == "":
            raise Exception("Can't register an unnamed OscCommandData.")

        self.osc_command_data = osc_command_data

        self.curr_value = None

        super().__init__(osc_command_data.name, self.receive_command)

    async def receive_command(self, ctx):
        args = ctx.message.content.split(" ")
        await self.execute_command(value=args[1] if len(args) >= 2 else None)
    
    async def execute_command(self, value=None):
        if value is None:
            if self.curr_value == self.osc_command_data.on_value:
                value = self.osc_command_data.off_value
            else:
                value = self.osc_command_data.on_value
        
        value = convert_value(value, self.osc_command_data.datatype)

        self.send_message(value)
        
        if self.osc_command_data.duration > 0:
            await self.disable_after_time(self.osc_command_data.duration)

    def send_message(self, value):
        client = SimpleUDPClient(OSC_IP, OSC_PASSWORD)
        client.send_message(self.osc_command_data.address, value)
        self.curr_value = value
                        
    async def disable_after_time(self, duration):
        await asyncio.sleep(duration)
        self.send_message(self.osc_command_data.off_value)


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(irc_token='oauth:twszee7twbiyiphmus1l43dt7gwgez',
                         prefix='!',
                         nick="DiFFtY",
                         initial_channels=['diffty'])
        
        self.unassigned_commands = []
        
        self.load_from_disk()
        
    async def event_ready(self):
        print(f'Logged in as | {self.nick}')

    @commands.command()
    async def register(self, ctx):
        assert_user_is_mod(ctx)

        args = ctx.message.content.split(" ")
        
        for a in args[1:]:
            unassigned_commands = self.get_unassigned_commands()

            if len(unassigned_commands) == 0:
                raise Exception("<!> No more unassigned commands!")

            rand_idx = random.randrange(0, len(unassigned_commands))
            self.register_command(unassigned_commands[rand_idx], a)
            
            await ctx.send(f'New command assigned : !{a}')

        self.write_to_disk()

    @commands.command()
    async def unregister(self, ctx):
        assert_user_is_mod(ctx)

        args = ctx.message.content.split(" ")
        
        for a in args[1:]:
            command = self.commands.get(a, None)

            if command is None:
                raise Exception(f"<!> Can't find command : {a}.")

            self.unregister_command(command)

            await ctx.send(f'Command unregistered : !{a}')

        self.write_to_disk()

    @commands.command()
    async def reload(self, ctx):
        assert_user_is_mod(ctx)
        
        for cmd in list(filter(lambda c: c.__class__ is OscCommand, self.commands.values())):
            self.remove_command(cmd)
        
        self.unassigned_commands = []
        
        self.load_from_disk()
        
    def register_command(self, command_data: OscCommandData, name: str=None):
        if name is None and command_data.name == "":
            self.unassigned_commands.append(command_data)
        else:
            self.assign_command(command_data, name)

    def unregister_command(self, command: OscCommand):
        if command not in self.commands.values():
            raise Exception(f"<!> Inexistant command {command.name}")
        
        if command.__class__ is not OscCommand:
            raise Exception(f"<!> Command {command.name} is not an OscCommand")

        self.remove_command(command)

        command.osc_command_data.name = ""
        
        self.unassigned_commands.append(command.osc_command_data)
        
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
