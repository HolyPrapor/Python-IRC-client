import curses


class CursesInterface:
    def __init__(self, irc):
        self.debug_enabled = False
        self.irc = irc
        self.buffer = ""
        curses.setupterm()
        self.colors = curses.tigetnum("colors")
        self.screen = curses.initscr()
        curses.cbreak()
        curses.noecho()
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            self.status_color_pair = curses.color_pair(7)
            self.debug_color_pair = curses.color_pair(7)
            self.border_color_pair = curses.color_pair(7)
            self.have_color = True
        else:
            self.have_color = False
        if self.have_color:
            self.init_colors()
        self.update_geometry()
        self.make_windows()
        self.update()
        self.clear_input_window()

    def run(self):
        while True:
            self.irc.poll()
            yield self.poll_kb()

    def poll_kb(self):
        keycode = self.input_window.getch()
        kb_input = None
        if keycode >= 0:
            if keycode == 10:  # Enter
                if self.buffer != "":
                    kb_input = self.buffer
                    self.buffer = ""
                    self.clear_input_window()
            elif keycode == 127:  # Backspace
                if self.buffer != "":
                    self.buffer = self.buffer[:-1]
                    y, x = self.input_window.getyx()
                    self.input_window.delch(y, x - 1)
            elif (keycode >= 32) and (keycode < 127):
                self.buffer = self.buffer + chr(keycode)
                self.input_window.addch(keycode)
        return kb_input

    def make_windows(self):
        self.input_window = curses.newwin(
            self.input_window_height, self.screen_width, self.nick_window_height + self.border_size, 0
        )
        self.chat_window = curses.newwin(self.chat_window_height, self.chat_window_width, 0, 0)
        self.nick_window = curses.newwin(
            self.nick_window_height, self.nick_window_width, 0, self.chat_window_width + self.border_size
        )
        self.debug_border = curses.newwin(
            self.debug_window_height, self.debug_window_width, self.debug_window_y, self.debug_window_x
        )
        self.debug_window = curses.newwin(
            self.debug_window_height - 2,
            self.debug_window_width - 2,
            self.debug_window_y + 1,
            self.debug_window_x + 1,
        )
        self.chat_window.move(self.chat_window_height - 1, 0)
        self.chat_window.scrollok(1)
        self.nick_window.scrollok(1)
        self.input_window.scrollok(1)
        self.input_window.nodelay(1)
        self.debug_window.scrollok(1)

    def update_geometry(self):
        self.chat_to_window_ratio = 85
        self.input_window_height = 1
        self.border_size = 1
        self.screen_height, self.screen_width = self.screen.getmaxyx()
        self.chat_window_width = int(self.screen_width * self.chat_to_window_ratio / 100)
        self.chat_window_height = self.screen_height - self.input_window_height - self.border_size
        self.nick_window_width = self.screen_width - self.chat_window_width - 1
        self.nick_window_height = self.screen_height - self.input_window_height - self.border_size
        self.debug_window_width = int(self.screen_width - 6)
        self.debug_window_height = int(self.screen_height / 2)
        self.debug_window_x = 3
        self.debug_window_y = int(self.screen_height / 8)

    def resize_window(self):
        self.update_geometry()
        self.make_windows()
        self.update()

    def update(self):
        height, width = self.screen.getmaxyx()
        if width != self.screen_width or height != self.screen_height:
            self.resize_window()
        self.screen.attron(self.border_color_pair)
        self.screen.hline(self.chat_window_height, 0, curses.ACS_HLINE, self.screen_width)
        self.screen.vline(0, self.chat_window_width, curses.ACS_VLINE, self.chat_window_height)
        self.screen.addch(self.chat_window_height, self.chat_window_width, curses.ACS_BTEE)
        self.screen.refresh()
        self.chat_window.refresh()
        self.nick_window.refresh()
        self.input_window.refresh()
        if self.debug_enabled:
            self.debug_border.attron(self.border_color_pair)
            self.debug_border.border(0)
            self.debug_border.refresh()
            self.debug_window.redrawwin()
            self.debug_window.refresh()
        curses.doupdate()

    def clear_input_window(self):
        self.input_window.move(0, 0)
        self.input_window.deleteln()
        self.input_window.addstr(
            self.irc.nick
            + "@"
            + self.irc.get_channel()
            + "> "
        )

    def add_message(self, message, color):
        pair = curses.color_pair(color)
        self.chat_window.addstr("\n" + message, pair)
        self.update()

    def add_debug_message(self, message):
        if self.have_color:
            self.debug_window.addstr("\n" + message, self.debug_color_pair)
        else:
            self.debug_window.addstr("\n" + message)
        if self.debug_enabled:
            self.update()

    def set_nicknames(self, nicknames):
        self.nick_window.clear()
        nicks = sorted(nicknames)[: self.nick_window_height]
        for i, nick in enumerate(nicks):
            self.nick_window.move(i, 0)
            self.nick_window.addstr(self.truncate_name(nick))
        self.update()

    def init_colors(self):
        for i in range(self.colors):
            curses.init_pair(i, i, -1)

    def shutdown(self):
        curses.nocbreak()
        curses.endwin()

    def toggle_debug(self):
        self.debug_enabled = not self.debug_enabled
        self.chat_window.touchwin()
        self.nick_window.touchwin()
        self.debug_window.touchwin()
        self.update()

    def truncate_name(self, s):
        if len(s) < self.nick_window_width:
            return s
        else:
            return s[: self.nick_window_width - 1] + "+"
