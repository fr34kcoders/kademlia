"""
General catchall for functions that don't make sense as methods.
"""

import asyncio
import hashlib
import operator
import random


async def gather_dict(dic):
    cors = list(dic.values())
    results = await asyncio.gather(*cors)
    return dict(zip(dic.keys(), results))


def generate_node_id():
    """Generates a 160-bit node ID for Kademlia using SHA-1.

    Returns
    -------
    bytes
        A 20-byte (160-bit) ID for the node.
    """

    # Generate a random 160-bit integer
    random_bits = random.getrandbits(160)
    # Hash the integer to ensure uniform distribution and create a 160-bit ID
    return hashlib.sha1(random_bits.to_bytes(20, byteorder="big")).digest()


def digest(string):
    if not isinstance(string, bytes):
        string = str(string).encode("utf8")
    key_namespace = string.split(b":", 1)[0]
    digest = hashlib.sha1(string).digest()
    if key_namespace == b"":
        return digest
    key = f"{key_namespace.decode('utf8')}:{digest}".encode("utf8")
    return key


def shared_prefix(args):
    """
    Find the shared prefix between the strings.

    For instance:

        sharedPrefix(['blahblah', 'blahwhat'])

    returns 'blah'.
    """
    i = 0
    while i < min(map(len, args)):
        if len(set(map(operator.itemgetter(i), args))) != 1:
            break
        i += 1
    return args[0][:i]


def bytes_to_bit_string(bites):
    bits = [bin(bite)[2:].rjust(8, "0") for bite in bites]
    return "".join(bits)
