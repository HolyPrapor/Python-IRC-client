import unittest
from unittest.mock import Mock
from queue import Queue
import threading
import sys
import os

sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.pardir)
)

from irc_client import SocketThread, IRC


def socket_iterator(*args):
    for argument in args:
        yield argument
    while True:
        yield ""


class ParsePacketTests(unittest.TestCase):
    event = None
    queue = None
    socket = None
    socket_thread = None

    def setUp(self):
        self.event = threading.Event()
        self.queue = Queue()
        self.socket = Mock()
        self.socket_thread = SocketThread(self.event, self.queue, self.socket)

    def tearDown(self):
        self.event.set()
        self.queue = None
        self.socket = None
        self.socket_thread = None
        self.event = None

    def test_socket_thread_work(self):
        self.socket.recv(1024).decode = Mock()
        self.socket.recv(1024).decode.side_effect = socket_iterator(
            "weber.freenode.net NOTICE * :*** Looking up your hostname...\n",
            "weber.freenode.net NOTICE * :*** Checking Ident\n",
        )

        self.socket_thread.start()

        first_queued = self.queue.get(True, 0.01)
        second_queued = self.queue.get(True, 0.01)

        self.assertEqual(
            first_queued,
            "weber.freenode.net NOTICE * :*** Looking up your hostname...",
        )
        self.assertEqual(
            second_queued, "weber.freenode.net NOTICE * :*** Checking Ident"
        )

    def test_NOTICE_parse(self):
        message = (
            "weber.freenode.net NOTICE * :*** Looking up your hostname..."
        )
        expected = (
            "",
            "weber.freenode.net",
            ["NOTICE", "*", "*** Looking up your hostname..."],
        )
        self.assertEqual(expected, IRC.parse_message(message))

    def test_MODE_parse(self):
        message = "ChanServ!ChanServ@services. MODE #test +v Zeliboba"
        expected = (
            "",
            "ChanServ!ChanServ@services.",
            ["MODE", "#test", "+v", "Zeliboba"],
        )
        self.assertEqual(expected, IRC.parse_message(message))
