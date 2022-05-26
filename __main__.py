import asyncio
import logging
import sys
import functools
from hashlib import sha1

logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s: %(message)s',
    stream=sys.stderr,
)
log = logging.getLogger('main')


class PeerServe(asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport
        self.address = transport.get_extra_info('peername')
        self.log = logging.getLogger(
            'EchoServer_{}_{}'.format(*self.address)
        )
        self.log.debug('connection accepted')

    def data_received(self, data):
        self.log.debug('received {!r}'.format(data))
        self.transport.write(data)
        self.log.debug('sent {!r}'.format(data))

    def eof_received(self):
        self.log.debug('received EOF')
        if self.transport.can_write_eof():
            self.transport.write_eof()

    def connection_lost(self, error):
        if error:
            self.log.error('ERROR: {}'.format(error))
        else:
            self.log.debug('closing')
        super().connection_lost(error)


class PeerConnection(asyncio.Protocol):
    def __init__(self, messages, future):
        super().__init__()
        self.messages = messages
        self.log = logging.getLogger('EchoClient')
        self.f = future

    def connection_made(self, transport):
        self.transport = transport
        self.address = transport.get_extra_info('peername')
        self.log.debug(
            'connecting to {} port {}'.format(*self.address)
        )

        for msg in self.messages:
            transport.write(msg)
            self.log.debug('sending {!r}'.format(msg))
        if transport.can_write_eof():
            transport.write_eof()

    def data_received(self, data):
        self.log.debug('received {!r}'.format(data))

    def eof_received(self):
        self.log.debug('received EOF')
        self.transport.close()
        if not self.f.done():
            self.f.set_result(True)

    def connection_lost(self, exc):
        self.log.debug('server closed connection')
        self.transport.close()
        if not self.f.done():
            self.f.set_result(True)
        super().connection_lost(exc)


class Peer:
    def __init__(self, loop, port=8888):
        self.loop = loop
        self.peername = ('localhost', port)
        self.me = loop.create_server(PeerServe, *self.peername)
        self.me = loop.run_until_complete(self.me)

        self.peers = dict()

    def new_peer(self, ip, port):
        client_completed = asyncio.Future()

        client_factory = functools.partial(
            PeerConnection,
            messages=MESSAGES,
            future=client_completed,
        )
        factory_coroutine = loop.create_connection(
            client_factory,
            *self.peername,
        )

        peername = f'{ip}:{port}'
        hash = sha1(peername.encode()).hexdigest()
        self.peers[hash] = (peername, factory_coroutine)
        self.loop.run_until_complete(factory_coroutine)

    def _hash_peername(self, peername):
        pass



MESSAGES = [
    b'This is the message. ',
    b'It will be sent ',
    b'in parts.',
]


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    peers = []

    for port in range(8888, 8908):
        peers.append(Peer(loop, port))

    for port in range(8889, 8908):
        peers[0].new_peer('localhost', port)

    try:
        print(peers[0].peers)
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for p in peers:
            p.me.close()
            loop.run_until_complete(p.me.wait_closed())

        loop.close()