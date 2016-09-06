#! /usr/bin/env python2.7

'''
Wrapper around the Keybase client.
'''

import re
import json
import distutils.spawn
from subprocess import Popen, PIPE


def clean(text):
    '''
    Remove ANSI escape sequences.
    '''
    escape = re.compile(r'\x1b[^m]*m', re.UNICODE)
    return escape.sub('', text)


def status(debug=False):
    '''
    Check the status of the client.
    '''
    keybase = distutils.spawn.find_executable('keybase')

    if keybase is not None:
        keybase_status = [keybase, 'status', '--json']
        execute = Popen(keybase_status, stdout=PIPE, stderr=PIPE,
                        close_fds=True)
        stdout, stderr = execute.communicate()

        if execute.returncode != 0:
            if debug:
                print '[stderr] status()'
                print '{0}'.format(stderr.strip())
                print '{0} (exit code: {1})'.format(' '.join(keybase_status),
                                                    execute.returncode)
        else:
            try:
                payload = json.loads(stdout.strip())
                if debug:
                    print '[stdout] status()'
                    print json.dumps(payload, indent=4, sort_keys=True)
                return payload['LoggedIn']
            except (KeyError, ValueError):
                if debug:
                    print 'Unable to parse response from the Keybase Client.'


def lookup(username, debug=False):
    '''
    Check if a user exists on Keybase.
    '''
    keybase = distutils.spawn.find_executable('keybase')

    if keybase is not None:
        keybase_lookup = [keybase, 'id', username.strip()]
        execute = Popen(keybase_lookup, stdout=PIPE, stderr=PIPE,
                        close_fds=True)
        stdout, stderr = execute.communicate()

        if execute.returncode != 0:
            if debug:
                print '[stderr] lookup()'
                print '{0}'.format(stderr.strip())
                print '{0} (exit code: {1})'.format(' '.join(keybase_lookup),
                                                    execute.returncode)
            if re.search(r'.*Not found.*', clean(stderr.strip())):
                return False
        else:
            if debug:
                print '[stdout] lookup()'
                print stdout.strip()
            return True


def encrypt(plaintext, recipient, debug=False):
    '''
    Encrypt the plain-text (into keybase-saltpack).
    '''
    keybase = distutils.spawn.find_executable('keybase')

    if keybase is not None:
        keybase_encrypt = [keybase, 'encrypt', '-m', plaintext, recipient]
        execute = Popen(keybase_encrypt, stdout=PIPE, stderr=PIPE,
                        close_fds=True)
        stdout, stderr = execute.communicate()

        if execute.returncode != 0:
            if debug:
                print '[stderr] encrypt()'
                print '{0}'.format(stderr.strip())
                print '{0} (exit code: {1})'.format(' '.join(keybase_encrypt),
                                                    execute.returncode)
        else:
            if debug:
                print '[stdout] encrypt()'
                print stdout.strip()
            return stdout.strip()


def sign(plaintext, debug=False):
    '''
    Sign the plain-text (into keybase-saltpack).
    '''
    keybase = distutils.spawn.find_executable('keybase')

    if keybase is not None:
        keybase_sign = [keybase, 'sign', '-m', plaintext]
        execute = Popen(keybase_sign, stdout=PIPE, stderr=PIPE,
                        close_fds=True)
        stdout, stderr = execute.communicate()

        if execute.returncode != 0:
            if debug:
                print '[stderr] sign()'
                print '{0}'.format(stderr.strip())
                print '{0} (exit code: {1})'.format(' '.join(keybase_sign),
                                                    execute.returncode)
        else:
            if debug:
                print '[stdout] sign()'
                print stdout.strip()
            return stdout.strip()


def verify(signed_saltpack, debug=False):
    '''
    Verify the signed-text (from keybase-saltpack).
    '''
    keybase = distutils.spawn.find_executable('keybase')
    flag, username, text = None, None, None

    if keybase is not None:
        keybase_verify = [keybase, 'verify', '-m', signed_saltpack]
        execute = Popen(keybase_verify, stdout=PIPE, stderr=PIPE,
                        close_fds=True)
        stdout, stderr = execute.communicate()

        signed = re.compile(r'.*Signed\sby\s(?P<username>\w+).*')
        username = signed.search(clean(stderr.strip()))
        who = None if username is None else username.group('username').strip()

        if execute.returncode != 0:
            if debug:
                print '[stderr] verify()'
                print '{0}'.format(stderr.strip())
                print '{0} (exit code: {1})'.format(' '.join(keybase_verify),
                                                    execute.returncode)
                if re.search(r'.*bad signature.*', clean(stderr.strip())):
                    flag = False
        else:
            if debug:
                print '[stdout] verify()'
                print stderr.strip()
                print stdout.strip()
            flag = True
            text = stdout.strip()

    return flag, who, text


def decrypt(encrypted_saltpack, debug=False):
    '''
    Decrypt the encrypted message (from keybase-saltpack).
    '''
    keybase = distutils.spawn.find_executable('keybase')
    who, plaintext = None, None

    if keybase is not None:
        keybase_encrypt = [keybase, 'decrypt', '-m', encrypted_saltpack]
        execute = Popen(keybase_encrypt, stdout=PIPE, stderr=PIPE,
                        close_fds=True)
        stdout, stderr = execute.communicate()

        authored = re.compile(r'.*authored\sby\s(?P<username>\w+).*')
        username = authored.search(clean(stderr.strip()))
        who = None if username is None else username.group('username').strip()

        if execute.returncode != 0:
            if debug:
                print '[stderr] decrypt()'
                print '{0}'.format(stderr.strip())
                print '{0} (exit code: {1})'.format(' '.join(keybase_encrypt),
                                                    execute.returncode)

        else:
            if debug:
                print '[stdout] verify()'
                print stderr.strip()
                print stdout.strip()
            plaintext = stdout.strip()

    return who, plaintext
