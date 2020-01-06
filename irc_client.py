#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from queue import Queue
from datetime import datetime
import hashlib
import socket
import threading
import argparse

from curses_interface import CursesInterface


class IRC:
    nick = "Zeliboba"
    host = "localhost"
    server = ""
    topic = ""
    user = "Zeliboba"
    name = "Zeliboba"
    quit_message = "I'm quitting!"
    version = "1.0"
    channel = ""
    nicknames = []
    connected = False
    joined = False
    stop_thread_request = threading.Event()
    rx_queue = Queue()

    def __init__(self, nick="", connect_info=None):
        if nick:
            self.nick = nick
        self.ui = UserInterface(self)
        self.keyboard = KeyboardHandler(self)
        if connect_info:
            self.connect(*connect_info)

    def start_thread(self):
        self.socketThread = SocketThread(
            self.stop_thread_request, self.rx_queue, self.sock,
        )
        self.stop_thread_request.clear()
        self.socketThread.start()

    def stop_thread(self):
        self.stop_thread_request.set()

    def connect(self, server, port):
        if not self.connected:
            self.server = server
            self.port = port
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.sock.connect((server, port))
                self.connected = True
            except socket.error:
                self.ui.add_status_message(
                    f"Unable to connect to {server}:{str(port)}"
                )
            if self.connected:
                self.start_thread()
                self.ui.add_status_message(
                    f"Connecting to {server}:{str(port)}"
                )
                self.login(self.nick, self.user, self.name, self.host, server)
        else:
            self.ui.add_status_message("Already connected")

    def send(self, command):
        if self.connected:
            bytes_sent = 0
            bytes_to_sent = bytes(command + "\n", "UTF-8")
            while bytes_sent < len(bytes_to_sent):
                current_sent = self.sock.send(bytes_to_sent[bytes_sent:])
                if current_sent == 0:
                    self.ui.add_status_message("Connection lost")
                    self.disconnect()
                bytes_sent += current_sent
            self.ui.add_debug_message("-> " + command)

    def send_message(self, message):
        if self.joined:
            self.ui.add_nick_message(self.nick, message)
            self.send(f"PRIVMSG {self.channel} :{message}")
        else:
            self.ui.add_status_message("Not in a channel")

    def send_private_message(self, nick, message):
        if self.connected:
            self.send(f"PRIVMSG {nick} :{message}")
            self.ui.add_nick_message(self.nick, f"[{nick}] {message}")
        else:
            self.ui.add_status_message("Not connected")

    def get_status(self):
        return self.nick, self.server, self.channel, self.topic

    def disconnect(self):
        if self.connected:
            self.send(f"QUIT :{self.quit_message}")
            self.stop_thread()
            self.connected = False
            self.server = ""
            self.ui.add_status_message("Disconnected")
            self.ui.update_status()
        else:
            self.ui.add_status_message("Not connected")

    def login(self, nick, user, name, host, server):
        self.send(f"USER {user} {host} {server} {name}")
        self.send(f"NICK {nick}")
        self.ui.add_status_message(f"Using nickname {nick}")

    def join(self, channel):
        if self.connected:
            if not self.joined:
                self.send(f"JOIN {channel}")
            else:
                self.ui.add_status_message("Already in a channel")
        else:
            self.ui.add_status_message("Not connected")

    def part(self):
        if self.joined:
            self.send(f"PART {self.channel}")
            self.set_nicknames([])
            self.ui.add_status_message(f"Left channel {self.channel}")
            self.joined = False
            self.channel = ""
            self.ui.update_status()
        else:
            self.ui.add_status_message("Not in a channel")

    def add_nick(self, nick):
        self.nicknames.append(nick)
        self.nicknames.sort()
        self.ui.set_nicknames(self.nicknames)

    def delete_nick(self, nick):
        if nick in self.nicknames:
            self.nicknames.remove(nick)
            self.ui.set_nicknames(self.nicknames)

    def replace_nick(self, old_nick, new_nick):
        self.delete_nick(old_nick)
        self.add_nick(new_nick)
        self.ui.set_nicknames(self.nicknames)
        self.ui.add_status_message(f"{old_nick} is now known as {new_nick}")

    def request_nicknames(self):
        if self.joined:
            self.send(f"NAMES {self.channel}")

    def set_nicknames(self, nicknames):
        self.nicknames = nicknames
        self.ui.set_nicknames(self.nicknames)

    def set_nick(self, nick):
        if self.connected:
            self.send(f":{self.nick}!{self.user}@{self.host} NICK {nick}")

    def get_channel(self):
        if self.joined:
            return self.channel
        else:
            return "~"

    def handle_ctcp(self, command, message):
        self.ui.add_status_message("Got CTCP message: " + command)
        if command == "VERSION":
            self.send("VERSION Zeliboba-IRC %s" % self.version)
        if command == "ACTION":
            self.ui.add_emote_message(self.nick, message)

    def poll(self):
        rx = ""
        try:
            rx = self.rx_queue.get(True, 0.01)
        except BaseException:
            pass
        if rx != "":
            self.ui.add_debug_message("<- " + rx)
            self.handle_message(self.parse_message(rx))

    @staticmethod
    def parse_message(message):
        prefix = ""
        if message[0] == ":":
            prefix, message = message[1:].split(" ", 1)
        if message.find(" :") != -1:
            message, trail = message.split(" :", 1)
            args = message.split()
            args.append(trail)
        else:
            args = message.split()
        command = args.pop(0)
        return prefix, command, args

    def handle_message(self, message):
        prefix, command, args = message
        if command == "PING":
            self.send(f"PONG {args[0]}")
        if command == "PRIVMSG":
            message = " ".join(args[1:])
            nick = prefix[: prefix.find("!")]
            if args[1].startswith(chr(1)):
                ctcp = message.replace(chr(1), "").split()
                ctcp_command = ctcp[0]
                ctcp_message = " ".join(ctcp[1:])
                self.handle_ctcp(ctcp_command, ctcp_message)
            elif args[0] == self.channel:
                self.ui.add_nick_message(nick, message)
            else:
                self.ui.add_private_message(nick, message)
        if command == "JOIN":
            nick = prefix[: prefix.find("!")]
            if not self.joined:
                self.joined = True
                self.channel = args[0]
                self.ui.update_status()
                self.ui.add_status_message(f"Joined channel {self.channel}")
            elif nick != self.nick:
                self.add_nick(prefix[: prefix.find("!")])
                self.ui.add_status_message(f"{nick} joined the channel")
        if command == "PART" and args[0] == self.channel:
            nick = prefix[: prefix.find("!")]
            self.delete_nick(nick)
            self.ui.add_status_message(f"{nick} left the channel")
        if command == "353":  # NAMEREPLY
            nicknames = " ".join(args[3:]).split()
            self.set_nicknames(nicknames)
        if command == "376":  # MOTD
            self.ui.add_status_message("MOTD received, ready for action")
            self.ui.update_status()
        if command == "NICK":
            old_nick = prefix[: prefix.find("!")]
            new_nick = args[0]
            if old_nick == self.nick:
                self.nick = new_nick
            self.replace_nick(old_nick, new_nick)
            self.ui.update_status()

    def run(self):
        for kb_input in self.ui.run():
            self.keyboard.parse_input(kb_input)


class SocketThread(threading.Thread):
    def __init__(self, event, rx_queue, sock):
        super(SocketThread, self).__init__()
        self.stop_thread_request = event
        self.rx_queue = rx_queue
        self.socket = sock

    def run(self):
        rx = bytes()
        while not self.stop_thread_request.isSet():
            rx = rx + self.socket.recv(1024)
            if rx:
                buffer = rx.decode(encoding="utf-8", errors="ignore")
                decoded_bytes = len(bytes(buffer, "utf-8"))
                buffer = buffer.split("\n")
                rx = bytes(buffer.pop(), "utf-8") + rx[decoded_bytes:]
                for line in buffer:
                    line = line.rstrip()
                    self.rx_queue.put(line)
            else:
                self.stop_thread_request.set()
        return


class UserInterface:
    def __init__(self, irc):
        self.irc = irc
        self.curses_ui = CursesInterface(self.irc)
        self.draw_integral()
        self.add_status_message(
            "Welcome to Zeliboba-IRC version " + self.irc.version
        )
        self.add_status_message("Type /help for a list of commands")

    def run(self):
        for kb_input in self.curses_ui.run():
            if kb_input:
                yield kb_input

    def add_message(self, message, color):
        msg = self.get_time_stamp() + " " + message
        self.curses_ui.add_message(msg, color)

    def add_nick_message(self, nick, message):
        color = self.get_nick_color(nick)
        self.add_message("<" + nick + "> " + message, color)

    def add_emote_message(self, nick, message):
        color = self.get_nick_color(nick)
        self.add_message("* " + nick + " " + message, color)

    def add_private_message(self, nick, message):
        self.add_nick_message(nick, "[private] " + message)

    def add_status_message(self, message):
        self.add_message("== " + message, 7)

    def add_debug_message(self, message):
        self.curses_ui.add_debug_message(message)

    def set_nicknames(self, nicknames):
        self.curses_ui.set_nicknames(nicknames)

    def init_colors(self):
        self.curses_ui.init_colors()

    def get_nick_color(self, nick):
        return (
            int(hashlib.md5(nick.encode("utf-8")).hexdigest(), 16)
            % self.curses_ui.colors
        )

    def shutdown(self):
        self.curses_ui.shutdown()

    def toggle_debug(self):
        self.curses_ui.toggle_debug()

    def draw_integral(self):
        self.add_message("MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM", 2)
        self.add_message("MMMMMMMMMMMMMMMMMMMMMMWWWMMMMMMMMMMMMMMM", 3)
        self.add_message("MMMMMMMMMMMMMMMMMMMKkd:,:xXMMMMMMMMMMMMM", 2)
        self.add_message("MMMMMMMMMMMMMMMMMMK;  'c..oNMMMMMMMMMMMM", 3)
        self.add_message("MMMMMMMMMMMMMMMMMMx. .dWKx0WMMMMMMMMMMMM", 2)
        self.add_message("MMMMMMMMMMMMMMMMMWd  .xMMMMMMMMMMMMMMMMM", 3)
        self.add_message("MMMMMMMMMMMMMMMMMWo  .kMMMMMMMMMMMMMMMMM", 2)
        self.add_message("MMMMMMMMMMMMMMMMMNc  .OMMMMMMMMMMMMMMMMM", 3)
        self.add_message("MMMMMMMMMMMMMMMMMN:  '0MMMMMMMMMMMMMMMMM", 2)
        self.add_message("MMMMMMMMMMMMMMMMMX;  ,KMMMMMMMMMMMMMMMMM", 3)
        self.add_message("MMMMMMMMMMMMMMMMMK,  ;XMMMMMMMMMMMMMMMMM", 2)
        self.add_message("MMMMMMMMMMMMMMMMM0'  cNMMMMMMMMMMMMMMMMM", 3)
        self.add_message("MMMMMMMMMMMMMMMMMO.  lWMMMMMMMMMMMMMMMMM", 2)
        self.add_message("MMMMMMMMMMMMMMMMMk. .oWMMMMMMMMMMMMMMMMM", 3)
        self.add_message("MMMMMMMMMMMMMMWWMx...dWMMMMMMMMMMMMMMMMM", 2)
        self.add_message("MMMMMMMMMMMMNx:dKl .;kMMMMMMMMMMMMMMMMMM", 3)
        self.add_message("MMMMMMMMMMMMWk'....o0NMMMMMMMMMMMMMMMMMM", 2)
        self.add_message("MMMMMMMMMMMMMWXkdkKWMMMMMMMMMMMMMMMMMMMM", 3)
        self.add_message("MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM", 2)
        self.add_message("MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM", 3)

    def get_time_stamp(self):
        return datetime.now().strftime("[%H:%M]")

    def update_status(self):
        self.curses_ui.update()


class KeyboardHandler:
    def __init__(self, irc):
        self.irc = irc

    def parse_input(self, keyboard_input):
        if keyboard_input.startswith("/"):
            if len(keyboard_input) > 1:
                self.handle_cmd(keyboard_input[1:])
        else:
            self.irc.send_message(keyboard_input)

    def handle_cmd(self, command_input):
        command = command_input.split()[0]
        args = command_input.split()[1:]
        if command == "connect":
            if len(args) == 1 and args[0].count(":") == 1:
                server, port = args[0].split(":")
                if port.isdigit():
                    self.irc.connect(server, int(port))
                else:
                    self.irc.ui.add_status_message(
                        "Port must be specified as an integer"
                    )
            else:
                self.irc.ui.add_status_message("Usage: connect <server:port>")
        elif command == "disconnect":
            self.irc.part()
            self.irc.disconnect()
        elif command == "join":
            if len(args) < 1:
                self.irc.ui.add_status_message("Usage: join <channel>")
            else:
                channel_name = args[0]
                if not channel_name.startswith("#"):
                    channel_name = "#" + channel_name
                self.irc.join(channel_name)
        elif command == "part":
            self.irc.part()
        elif command == "msg":
            if len(args) < 2:
                self.irc.ui.add_status_message("Usage: msg <nick> <message>")
            else:
                msg = " ".join(args[1:])
                self.irc.send_private_message(args[0], msg)
        elif command == "nick":
            if len(args) < 1:
                self.irc.ui.add_status_message("Usage: nick <new nick>")
            else:
                self.irc.set_nick(args[0])
        elif command == "debug":
            self.irc.ui.toggle_debug()
        elif command == "names":
            self.irc.request_nicknames()
        elif command == "help":
            self.irc.ui.add_status_message("available commands:")
            self.irc.ui.add_status_message("/connect <server:port>")
            self.irc.ui.add_status_message("/disconnect")
            self.irc.ui.add_status_message("/join <channel>")
            self.irc.ui.add_status_message("/part")
            self.irc.ui.add_status_message("/msg <nick> <message>")
            self.irc.ui.add_status_message("/nick <new nick>")
            self.irc.ui.add_status_message("/debug")
            self.irc.ui.add_status_message("/quit")
        elif command == "quit":
            self.irc.part()
            self.irc.disconnect()
            self.irc.ui.shutdown()
            exit()
        else:
            msg = "Unknown command: " + command
            self.irc.ui.add_status_message(msg)


def server_and_port(value):
    splitted_connect_info = value.split(":")
    if len(splitted_connect_info) == 2 and splitted_connect_info[-1].isdigit:
        server = "".join(splitted_connect_info[:-1])
        port = int(splitted_connect_info[-1])
        return server, port
    else:
        print("Wrong arguments!")
        raise argparse.ArgumentParser()


def parse_args():
    parser = argparse.ArgumentParser(description="Curses IRC client")
    parser.set_defaults(nick=None)
    parser.add_argument(
        "--connect", type=server_and_port, metavar="server:port"
    )
    parser.add_argument("--nick", help="Specify nickname")
    return parser.parse_args()


def main():
    args = parse_args()
    irc = IRC(nick=args.nick, connect_info=args.connect)
    irc.run()


if __name__ == "__main__":
    main()
