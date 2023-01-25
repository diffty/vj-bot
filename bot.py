import json
import os
import random
import functools
import asyncio
import requests

from typing import DefaultDict, List

from twitchio.ext import commands
from twitchio.ext.commands.core import Command

from pythonosc.udp_client import SimpleUDPClient

import config


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
        self.ip = ""
        self.port = ""
        self.name = ""
        self.address = ""
        self.datatype = ""
        self.on_value = ""
        self.off_value = ""
        self.off_address = ""
        self.duration = ""
        self.visible = ""

    def as_dict(self):
        return {
            "ip": self.ip,
            "port": self.port,
            "name": self.name,
            "address": self.address,
            "datatype": self.datatype,
            "off_address": self.off_address,
            "off_value": self.off_value,
            "on_value": self.on_value,
            "duration": self.duration,
            "visible": self.visible,
        }
    
    @staticmethod
    def create_from_json_entry(data):
        new_command_data = OscCommandData()
        new_command_data.ip = data.get("ip", None)
        new_command_data.port = data.get("port", None)
        new_command_data.name = data["name"]
        new_command_data.address = data["address"]
        new_command_data.duration = data.get("duration", -1)
        new_command_data.off_address = data.get("off_address", None)
        new_command_data.off_value = data.get("off_value", 0)
        new_command_data.on_value = data.get("on_value", 1)
        new_command_data.visible = data.get("visible", True)
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

    def send_message(self, value, address=None, ip=None, port=None):
        if address is None:
            address = self.osc_command_data.address

        if ip is None:
            ip = self.osc_command_data.ip

        if ip is None:
            ip = config.OSC_IP
        
        if port is None:
            port = self.osc_command_data.port
        
        if port is None:
            port = config.OSC_PORT

        client = SimpleUDPClient(ip, port)
        client.send_message(address, value)
        self.curr_value = value
                        
    async def disable_after_time(self, duration):
        await asyncio.sleep(duration)
        self.send_message(self.osc_command_data.off_value, self.osc_command_data.off_address)


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(token='',
                         prefix='!',
                         nick="DiFFtY",
                         initial_channels=['diffty'])
        
        self.unassigned_commands = []

        self.prev_donations = None
        
        self.load_from_disk()
        
    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        #await self.pubsub_subscribe(config.PUBSUB_TOKEN, "channel-points-channel-v1.27497503")

    @commands.command()
    async def register(self, ctx: commands.Context):
        assert_user_is_mod(ctx)

        args = ctx.message.content.split(" ")
        
        for arg in args[1:]:
            self.assign_random_command(arg)
            
            await ctx.send(f'New command assigned : !{arg}')

        self.write_to_disk()

    @commands.command()
    async def unregister(self, ctx: commands.Context):
        assert_user_is_mod(ctx)

        args = ctx.message.content.split(" ")
        
        for arg in args[1:]:
            command = self.commands.get(arg, None)

            if command is None:
                raise Exception(f"<!> Can't find command : {arg}.")

            self.unregister_command(command)

            await ctx.send(f'Command unregistered : !{arg}')

        self.write_to_disk()
    
    @commands.command()
    async def reveal(self, ctx: commands.Context):
        assert_user_is_mod(ctx)

        args = ctx.message.content.split(" ")
        
        if len(args) >= 2:
            command_list = map(lambda cmd_name: self.commands[cmd_name], args[1:])
        else:
            hidden_commands = self.get_commands_with_visibility(False)
            if hidden_commands:
                command_list = [random.choice(hidden_commands)]

        self.reveal_commands(command_list)

        for cmd in command_list:
            await ctx.send(f'Commande révélée : !{cmd.name}')

        self.write_to_disk()
    
    def reveal_commands(self, command_list: List[OscCommand]):
        for cmd in command_list:
            command = self.commands.get(cmd.name, None)

            if command is None:
                raise Exception(f"<!> Can't find command : {cmd.name}.")

            command.osc_command_data.visible = True

    @commands.command()
    async def reload(self, ctx: commands.Context):
        assert_user_is_mod(ctx)
        
        for name, cmd in list(filter(lambda c: c[1].__class__ is OscCommand, self.commands.items())):
            self.remove_command(name)
        
        self.unassigned_commands = []
        
        self.load_from_disk()
    
    @commands.command()
    async def commandes(self, ctx: commands.Context):
        await ctx.send(f'Commandes disponibles : {" ".join(map(lambda cmd: "!" + cmd.name, filter(lambda c: isinstance(c, OscCommand) and c.osc_command_data.visible, self.commands.values())))} ❤')

    @commands.command()
    async def koi(self, ctx: commands.Context):
        await ctx.send(f"feur {ctx.author.name}")
    
    @commands.command(aliases=["help", "aide"])
    async def aled(self, ctx: commands.Context):
        await ctx.send(f"Coucou {ctx.author.name} {self.get_random_heart()} Y a plein de commandes dispo ce soir pour péter le stream, utilisables à volonté. T'aurais la liste complète en utilisant la commande !commandes ✨")
        await ctx.send('Aussi, tu peux obtenir ta propre commande, portant ton pseudo, en récupérant la récompense de point de chaîne "👀", ou en subbant à la chaîne !')

    @staticmethod
    def get_random_heart():
        emotes = ["htyLuv", "moufroLove", "GayPride"]
        return emotes[random.randint(0, len(emotes)-1)]

    def assign_random_command(self, new_command_name: str):
        unassigned_commands = self.get_unassigned_commands()

        if len(unassigned_commands) == 0:
            raise Exception("<!> No more unassigned commands!")

        rand_idx = random.randrange(0, len(unassigned_commands))
        self.register_command(unassigned_commands[rand_idx], new_command_name)

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

        self.remove_command(command.name)

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
    
    def get_commands_with_visibility(self, visibility: bool = True) -> List[OscCommand]:
        return list(
            map(
                lambda cmd: cmd.osc_command_data,
                filter(lambda c: c.__class__ is OscCommand and c.osc_command_data.visible == visibility, self.commands.values())
            )
        )
    
    #async def event_usernotice_subscription(self, metadata):
    #    unassigned_commands = self.get_unassigned_commands()
    #    rand_idx = random.randrange(0, len(unassigned_commands))
    #    self.register_command(unassigned_commands[rand_idx], metadata.user.name)
    #    self.write_to_disk()
    
    #async def event_raw_pubsub(self, data):
    #    if 'data' in data:
    #        msg = data["data"]["message"]
    #        msg_dict = json.loads(msg)

    #        print(msg_dict)

    #        if 'data' in msg_dict and msg_dict['data']['redemption']['reward']['title'] == '👀':
    #            print(f"ON GENERE UNE COMMANDE POUR {msg_dict['data']['redemption']['user']['login']}")
    #        
    #        elif 'data' in msg_dict and msg_dict['data']['redemption']['reward']['title'] == '👄':
    #            print(f"ON GENERE UNE COMMANDE POUR {msg_dict['data']['redemption']['user_input']}")

    #            command_name = msg_dict['data']['redemption']['user_input'].split(" ")
    #            if command_name:
    #                self.assign_random_command(command_name[0])
    #                self.write_to_disk()

    #            #req = requests.patch(
    #            #    f"https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions?broadcaster_id={msg_dict['data']['redemption']['reward']['channel_id']}&reward_id={msg_dict['data']['redemption']['reward']['id']}&id={msg_dict['data']['redemption']['id']}",
    #            #    headers={
    #            #        "Client-Id": "",
    #            #        "Authorization": f"Bearer ",
    #            #        "Content-Type": "application/json"
    #            #    },
    #            #    data='{ "status": "CANCELED" }')
    #            #print(req.text)
    #        
    #        #rewards = await self.get_custom_rewards()
    #        #print(rewards)


if __name__ == "__main__":
    bot = Bot()
    bot.run()
