import datetime


class ConsoleUI:
    def __init__(self, interface):
        self.current_nicknames = []
        self.active = False
        self.interface = interface

    def run(self):
        print("Started")
        print("Type /help to see available command list")
        self.active = True
        while self.active:
            self.interface.parse_input(input())

    def set_nicknames(self, new_nicknames):
        self.current_nicknames = new_nicknames

    def handle_message(self, nick, message):
        print(nick + " " + message)

    def handle_private_message(self, nick, message):
        self.handle_message(nick, message)

    def show_info(self, info):
        print(str(datetime.datetime.now()) + "| " + info)

    def shutdown(self):
        print("Quitting...")
        self.active = False

    def refresh(self):
        print("______________")

    def handle_action_message(self, nick, message):
        self.handle_message(nick, message)

