import asyncio
import logging
import random

from rpcudp.protocol import RPCProtocol

from kademlia.node import Node
from kademlia.routing import RoutingTable
from kademlia.utils import digest

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class KademliaProtocol(RPCProtocol):
    def __init__(self, source_node, storage, ksize):
        """Initialize the Kademlia protocol with the source node, storage, and k-bucket size.

        Parameters
        -----------
        source_node : Node
            The node representing the local peer in the network.
        storage : Storage
            The storage backend for storing key-value pairs.
        ksize : int
            The size of each k-bucket in the routing table.

        Returns
        -------
        None
        """

        RPCProtocol.__init__(self)
        self.router = RoutingTable(self, ksize, source_node)
        self.storage = storage
        self.source_node = source_node

    def get_refresh_ids(self):
        """Retrieve a list of node IDs to search for in order to refresh old buckets.

        Parameters
        -----------
        None

        Returns
        -------
        list of bytes
            A list of 20-byte node IDs to be used for refreshing the routing table.
        """

        ids = []
        for bucket in self.router.lonely_buckets():
            rid = random.randint(*bucket.range).to_bytes(20, byteorder="big")
            ids.append(rid)
        return ids

    def rpc_stun(self, sender):
        """Respond to a STUN RPC by returning the sender's address.

        Parameters
        -----------
        sender : tuple
            A tuple containing the sender's IP address and port.

        Returns
        -------
        tuple
            The sender's IP address and port.
        """

        return sender

    def rpc_ping(self, sender, nodeid):
        """Handle a PING RPC by adding the sender to the routing table and returning the local node ID.

        Parameters
        -----------
        sender : tuple
            A tuple containing the sender's IP address and port.
        nodeid : bytes
            The 20-byte ID of the sender node.

        Returns
        -------
        bytes
            The 20-byte ID of the local source node.
        """

        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        return self.source_node.id

    def rpc_store(self, sender, nodeid, key, value):
        """Handle a STORE RPC by adding the sender to the routing table and storing the key-value pair.

        Parameters
        -----------
        sender : tuple
            A tuple containing the sender's IP address and port.
        nodeid : bytes
            The 20-byte ID of the sender node.
        key : bytes
            The key to store in the DHT.
        value : bytes
            The value associated with the key.

        Returns
        -------
        bool
            True if the value was successfully stored.
        """

        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        log.debug(
            "got a store request from %s, storing '%s'='%s'", sender, key.hex(), value
        )
        self.storage.set(key, value)
        return True

    def rpc_find_node(self, sender, nodeid, key):
        """Handle a FIND_NODE RPC by returning a list of nearest neighbors to the given key.

        Parameters
        -----------
        sender : tuple
            A tuple containing the sender's IP address and port.
        nodeid : bytes
            The 20-byte ID of the sender node.
        key : bytes
            The 20-byte key to find neighbors for.

        Returns
        -------
        list of tuple
            A list of tuples, each containing the IP address and port of a neighbor node.
        """

        log.info("finding neighbors of %i in local table", int(nodeid.hex(), 16))
        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        node = Node(key)
        neighbors = self.router.find_neighbors(node, exclude=source)
        return list(map(tuple, neighbors))

    def rpc_find_value(self, sender, nodeid, key):
        """Handle a FIND_VALUE RPC by returning the value if it exists, otherwise return nearest neighbors.

        Parameters
        -----------
        sender : tuple
            A tuple containing the sender's IP address and port.
        nodeid : bytes
            The 20-byte ID of the sender node.
        key : bytes
            The 20-byte key to find the value for.

        Returns
        -------
        dict or list of tuple
            A dictionary containing the value if found, otherwise a list of neighbor nodes.
        """

        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        log.debug("RPC FIND VALUE: finding value of '%s'", key)
        value = self.storage.get(key, None)
        if value is None:
            log.debug("could not find value for %s", key.hex())
            dkey = digest(key)
            return self.rpc_find_node(sender, nodeid, dkey)
        return {"value": value}

    async def call_find_node(self, node_to_ask, node_to_find):
        """Asynchronously call the FIND_NODE RPC on a specified node.

        Parameters
        -----------
        node_to_ask : Node
            The node to send the FIND_NODE RPC to.
        node_to_find : Node
            The node ID to find neighbors for.

        Returns
        -------
        tuple
            The response from the RPC call and the node that was asked.
        """

        address = (node_to_ask.ip, node_to_ask.port)
        result = await self.find_node(address, self.source_node.id, node_to_find.id)
        return self.handle_call_response(result, node_to_ask)

    async def call_find_value(self, node_to_ask, node_to_find):
        """Asynchronously call the FIND_VALUE RPC on a specified node.

        Parameters
        -----------
        node_to_ask : Node
            The node to send the FIND_VALUE RPC to.
        node_to_find : Node
            The node ID to find the value for.

        Returns
        -------
        tuple
            The response from the RPC call and the node that was asked.
        """

        address = (node_to_ask.ip, node_to_ask.port)
        result = await self.find_value(address, self.source_node.id, node_to_find.custom_key)
        return self.handle_call_response(result, node_to_ask)

    async def call_ping(self, node_to_ask):
        """Asynchronously call the PING RPC on a specified node.

        Parameters
        -----------
        node_to_ask : Node
            The node to send the PING RPC to.

        Returns
        -------
        tuple
            The response from the RPC call and the node that was asked.
        """

        address = (node_to_ask.ip, node_to_ask.port)
        result = await self.ping(address, self.source_node.id)
        return self.handle_call_response(result, node_to_ask)

    async def call_store(self, node_to_ask, key, value):
        """Asynchronously call the STORE RPC on a specified node to store a key-value pair.

        Parameters
        -----------
        node_to_ask : Node
            The node to send the STORE RPC to.
        key : bytes
            The key to store.
        value : bytes
            The value associated with the key.

        Returns
        -------
        tuple
            The response from the RPC call and the node that was asked.
        """

        address = (node_to_ask.ip, node_to_ask.port)
        result = await self.store(address, self.source_node.id, key, value)
        return self.handle_call_response(result, node_to_ask)

    def welcome_if_new(self, node):
        """
        Send all relevant key-value pairs to a new node and add it to the routing table.

        Process
        -------
        For each key in storage, get k closest nodes.  If newnode is closer
        than the furtherst in that list, and the node for this server
        is closer than the closest in that list, then store the key/value
        on the new node (per section 2.5 of the paper)

        Parameters
        -----------
        node : Node
            A new node that just joined or that was discovered.

        Returns
        -------
        None
        """

        if not self.router.is_new_node(node):
            return

        log.info("never seen %s before, adding to router", node)
        for key, value in self.storage:
            keynode = Node(digest(key))
            neighbors = self.router.find_neighbors(keynode)
            if neighbors:
                last = neighbors[-1].distance_to(keynode)
                new_node_close = node.distance_to(keynode) < last
                first = neighbors[0].distance_to(keynode)
                this_closest = self.source_node.distance_to(keynode) < first
            if not neighbors or (new_node_close and this_closest):
                asyncio.ensure_future(self.call_store(node, key, value))
        self.router.add_contact(node)

    def handle_call_response(self, result, node):
        """Process the response from an RPC call by updating the routing table.

        Parameters
        -----------
        result : tuple
            The result of the RPC call, typically a success flag and additional data.
        node : Node
            The node that was contacted.

        Returns
        -------
        tuple
            The original result from the RPC call.
        """

        if not result[0]:
            log.warning("no response from %s, removing from router", node)
            self.router.remove_contact(node)
            return result

        log.info("got successful response from %s", node)
        self.welcome_if_new(node)
        return result
