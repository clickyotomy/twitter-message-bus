#! /usr/bin/env python2.7

'''
Reads messages from the 'in' queue, decrypts the contents.
'''

import time
import json
from argparse import ArgumentParser
from logging import (NullHandler, getLogger, StreamHandler, Formatter, DEBUG,
                     INFO)

from pydisque.client import Client

from gist import get
from auth import status, verify, decrypt


# Formatting for logger output.
getLogger(__name__).addHandler(NullHandler())
LOGGER = getLogger()
HANDLER = StreamHandler()
FORMATTER = Formatter(
    ('%(asctime)s; log: %(name)s, %(levelname)s, %(levelno)s; '
     'process: %(process)s - %(processName)s; path: %(pathname)s '
     'L%(lineno)s - module: %(module)s, method: %(funcName)s; '
     'error: %(exc_info)s; message: %(message)s')
)
HANDLER.setFormatter(FORMATTER)


# Check daemon.py for more information.
VAULT_PATH = 'vault/keys.json'


def load_credentials(path=VAULT_PATH):
    '''
    Load credentials from vault.
    '''
    gist = None
    with open(path, 'r') as vault_file:
        try:
            vault = json.loads(vault_file.read())
            gist = vault['github']
        except IOError:
            print 'Unable to read vault-file: {0}.'.format(path)
        except (KeyError, ValueError):
            print 'Unable to parse the vault-file.'

    return gist


def receive(token, queue, retry, debug=False):
    '''
    Get the message from the queue, display the decrypted text.
    '''
    if status(debug):
        LOGGER.info('[keybase-status] client-up; signed-in')
    else:
        LOGGER.error('[keybase-status] client-down/sigend-out')
        return

    try:
        while True:
            job = queue.get_job(['in'], count=1, nohang=False)
            if len(job) > 0:
                queue.ack_job(job[0][1])
                LOGGER.info('[received-job]: %s', repr(job[0]))
                signed = get(job[0][2].strip(), token, debug)
                if signed is None:
                    LOGGER.error('[gist-fetch] %s not found!', job[0][2])
                    continue
                flag, who, encrypted = verify(signed, debug)
                if flag:
                    LOGGER.info('[keybase-verify] message signed by %s',
                                who)
                    who, text = decrypt(encrypted, debug)
                    if who is not None:
                        LOGGER.info(('[keybase-decrypt] message encrypted'
                                     ' by %s'), who)
                        LOGGER.info(('[keybase-decrypt] plain-text content: '
                                     '\n%s'), text)
                    else:
                        LOGGER.error('[keybase-decrypt] un-trusted encryption')
                        continue
                else:
                    LOGGER.error('[keybase-verify] unable to verify')
                    continue
            time.sleep(retry)

    except Exception:
        LOGGER.error('[queue] unable to fetch jobs from \'in\'')


def main():
    '''
    Validate arguments, load credentials and read from the queue.
    '''
    message = 'Read messages from the message bus.'
    socket_help = ('a list containing the host, port numbers to listen to; '
                   'defaults to localhost:7711 (for disque)')
    retry_help = 'queue check frequncy (in seconds); defaults to 8'

    parser = ArgumentParser(description=message)
    parser.add_argument('-s', '--sockets', help=socket_help,
                        default=['localhost:7711'], dest='sockets',
                        metavar=('HOST:PORT'), nargs='+')
    parser.add_argument('-d', '--debug', help='enable debugging',
                        action='store_true', default=False)
    parser.add_argument('-r', '--retry', help=retry_help, default=8,
                        type=int, metavar=('DELAY'))

    args = vars(parser.parse_args())

    if args['debug']:
        LOGGER.setLevel(DEBUG)
        LOGGER.addHandler(HANDLER)
    else:
        LOGGER.setLevel(INFO)
        LOGGER.addHandler(HANDLER)

    token = load_credentials()

    if not token:
        LOGGER.error('[load_credentials] unable to load credentials!')
        return

    try:
        # Connect to the redis-queue.
        queue = Client(args['sockets'])
        queue.connect()
        LOGGER.info('[start-daemon]')
        queue_info = json.dumps(queue.info(), indent=4)
        LOGGER.info('[queue-init]\n%s', queue_info)
        receive(token, queue, args['retry'], args['debug'])

    except Exception:
        LOGGER.error('[error] unable to connect to the redis-queue (disque)!')

    except KeyboardInterrupt:
        LOGGER.critical('[stop-daemon]')


if __name__ == '__main__':
    main()
