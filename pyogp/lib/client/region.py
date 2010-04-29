
"""
Contributors can be viewed at:
http://svn.secondlife.com/svn/linden/projects/2008/pyogp/lib/base/trunk/CONTRIBUTORS.txt 

$LicenseInfo:firstyear=2008&license=apachev2$

Copyright 2009, Linden Research, Inc.

Licensed under the Apache License, Version 2.0.
You may obtain a copy of the License at:
    http://www.apache.org/licenses/LICENSE-2.0
or in 
    http://svn.secondlife.com/svn/linden/projects/2008/pyogp/lib/base/LICENSE.txt

$/LicenseInfo$
"""

# std lib
from logging import getLogger
import time

# related
from llbase import llsd

# pyogp
from pyogp.lib.base.caps import Capability
from pyogp.lib.base.network.stdlib_client import StdLibClient, HTTPError
from pyogp.lib.client.exc import ResourceNotFound, ResourceError, RegionSeedCapNotAvailable, \
     RegionMessageError
from pyogp.lib.client.settings import Settings
from pyogp.lib.base.helpers import Helpers
from pyogp.lib.client.objects import ObjectManager
from pyogp.lib.client.event_system import AppEventsHandler
from pyogp.lib.client.parcel import ParcelManager

# messaging
from pyogp.lib.base.message.message import Message, Block
from pyogp.lib.base.message.message_handler import MessageHandler
from pyogp.lib.base.message_manager import MessageManager
from pyogp.lib.base.message.circuit import Host

# utilities
from pyogp.lib.base.helpers import Wait

# initialize logging
logger = getLogger('pyogp.lib.client.region')

class Region(object):
    """ a region container

    The Region class is a container for region specific data.
    It is also a nice place for convenience code.

    Sample implementations: examples/sample_region_connect.py
    Tests: tests/region.txt, tests/test_region.py        

    """

    WIDTH = 256

    def __init__(self, global_x = 0, global_y = 0, seed_capability_url = None,
                 udp_blacklist = None, sim_ip = None, sim_port = None,
                 circuit_code = None, agent = None, settings = None,
                 message_handler = None, handle = None, events_handler = None):
        """ initialize a region """

        # allow the settings to be passed in
        # otherwise, grab the defaults
        if settings != None:
            self.settings = settings
        else:
            self.settings = Settings()

        # allow the packet_handler to be passed in
        # otherwise, grab the defaults
        if message_handler != None:
            self.message_handler = message_handler
        else:
            self.message_handler = MessageHandler()

        # allow the eventhandler to be passed in
        # so that applications running multiple avatars
        # may use the same eventhandler

        # otherwise, let's just use our own
        if events_handler != None:
            self.events_handler = events_handler
        else:
            self.events_handler = AppEventsHandler()

        # initialize the init params
        self.global_x = int(global_x)
        self.global_y = int(global_y)
        self.grid_x = int(self.global_x/Region.WIDTH)
        self.grid_y = int(self.global_y/Region.WIDTH)
        self.seed_capability_url = seed_capability_url
        self.udp_blacklist = udp_blacklist
        self.sim_ip = sim_ip
        self.sim_port = sim_port
        self.circuit_code = circuit_code
        self.agent = agent   # an agent object
        self.handle = handle
        self.is_host_region = False
        self.message_manager = None
        self.last_ping = 0
        
        # other attributes
        self.RegionHandle = None    # from AgentMovementComplete
        self.SimName = None
        self.seed_capability = None
        self.capabilities = {}
        self.connected = False
        self.helpers = Helpers()

        # data storage containers
        
        self.objects = ObjectManager(agent = self.agent, region = self,
                                     settings = self.settings,
                                     message_handler = self.message_handler,
                                     events_handler = self.events_handler)

        self.parcel_manager = ParcelManager(agent = self.agent, region = self,
                                            settings = self.settings,
                                            message_handler = self.message_handler,
                                            events_handler = self.events_handler)



        # data we need
        self.region_caps_list = ['ChatSessionRequest',
                                 'CopyInventoryFromNotecard',
                                 'DispatchRegionInfo',
                                 'EstateChangeInfo',
                                 'EventQueueGet',
                                 'FetchInventory',
                                 'WebFetchInventoryDescendents',
                                 'FetchLib',
                                 'FetchLibDescendents',
                                 'GroupProposalBallot',
                                 'HomeLocation',
                                 'MapLayer',
                                 'MapLayerGod',
                                 'NewFileAgentInventory',
                                 'ParcelPropertiesUpdate',
                                 'ParcelVoiceInfoRequest',
                                 'ProvisionVoiceAccountRequest',
                                 'RemoteParcelRequest',
                                 'RequestTextureDownload',
                                 'SearchStatRequest',
                                 'SearchStatTracking',
                                 'SendPostcard',
                                 'SendUserReport',
                                 'SendUserReportWithScreenshot',
                                 'ServerReleaseNotes',
                                 'StartGroupProposal',
                                 'UpdateAgentLanguage',
                                 'UpdateGestureAgentInventory',
                                 'UpdateNotecardAgentInventory',
                                 'UpdateScriptAgent',
                                 'UpdateGestureTaskInventory',
                                 'UpdateNotecardTaskInventory',
                                 'UpdateScriptTask',
                                 'ViewerStartAuction',
                                 'UntrustedSimulatorMessage',
                                 'ViewerStats'
                                 ]
        if self.settings.LOG_VERBOSE:
            logger.debug('initializing region domain: %s' %self)

    def enable_callbacks(self):
        '''enables the callback handles for this Region'''
        # required packet handlers
        onPacketAck_received = self.message_handler.register('PacketAck')
        onPacketAck_received.subscribe(self.helpers.null_packet_handler, self)
        
        # the RegionHandshake packet requires a response
        onRegionHandshake_received = self.message_handler.register('RegionHandshake')
        onRegionHandshake_received.subscribe(self.onRegionHandshake)

        # the StartPingCheck packet requires a response
        onStartPingCheck_received = self.message_handler.register('StartPingCheck')
        onStartPingCheck_received.subscribe(self.onStartPingCheck)
        
        if self.settings.ENABLE_OBJECT_TRACKING:
            self.objects.enable_callbacks()

        if self.settings.ENABLE_PARCEL_TRACKING:
            self.parcel_manager.enable_callbacks()

    def enable_child_simulator(self, IP, Port, Handle):

        logger.info("Would enable a simulator at %s:%s with a handle of %s" % (IP, Port, Handle))

    def enqueue_message(self, packet, reliable = False):
        """ queues packets for the messaging system to send """

        if self.message_manager:
            self.message_manager.outgoing_queue.append((packet, reliable))
        else:
            logger.warn("Failed to enqueue a message - no message manager!")

    def _set_seed_capability(self, url = None):
        """ sets the seed_cap attribute as a RegionSeedCapability instance """

        if url != None:
            self.seed_capability_url = url
        self.seed_cap = RegionSeedCapability('seed_cap', self.seed_capability_url, settings = self.settings)

        if self.settings.LOG_VERBOSE:
            logger.debug('setting region domain seed cap: %s' % (self.seed_capability_url))

    def _get_region_public_seed(self, custom_headers={'Accept' : 'application/llsd+xml'}):
        """ call this capability, return the parsed result """

        if self.settings.ENABLE_CAPS_LOGGING:
            logger.debug('Getting region public_seed %s' %(self.region_uri))

        try:
            restclient = StdLibClient()
            response = restclient.GET(self.region_uri, custom_headers)
        except HTTPError, e:
            if e.code == 404:
                raise ResourceNotFound(self.region_uri)
            else:
                raise ResourceError(self.region_uri, e.code, e.msg, e.fp.read(), method="GET")

        data = llsd.parse(response.body)

        if self.settings.ENABLE_CAPS_LOGGING:
            logger.debug('Get of cap %s response is: %s' % (self.region_uri, data))        

        return data

    def _get_region_capabilities(self):
        """ queries the region seed cap for capabilities """

        if (self.seed_cap == None):
            raise RegionSeedCapNotAvailable("querying for agent capabilities")
        else:

            if self.settings.ENABLE_CAPS_LOGGING:
                logger.info('Getting caps from region seed cap %s' % (self.seed_cap))

            # use self.region_caps.keys() to pass a list to be parsed into LLSD            
            self.capabilities = self.seed_cap.get(self.region_caps_list, self.settings)

    def connect(self):
        """ connect to the udp circuit code and event queue"""
        if (self.sim_ip == None) or (self.sim_port == None):
            logger.error("sim_ip or sim_port is None")
            return
        
        
        # if this is the agent's host region, spawn the event queue
        # spawn an eventlet api instance that runs the event queue connection
        if self.seed_capability_url != None:

            # set up the seed capability
            self._set_seed_capability()

            # grab the agent's capabilities from the sim
            self._get_region_capabilities()

            
        self.message_manager = MessageManager(Host((self.sim_ip, self.sim_port)),
                                              self.message_handler,
                                              self.capabilities,  self.settings)
        self.enable_callbacks()
        self._init_agent_in_region()
        self.message_manager.start_monitors()
        
                
        logger.debug("Spawned region data connections")

    def connect_child(self):
        """ connect to the a child region udp circuit code """

        # send the UseCircuitCode packet
        self.sendUseCircuitCode(self.circuit_code, self.agent.session_id, self.agent.agent_id)
        self.message_manager.start_monitors()

    def logout(self):
        """ send a logout packet """

        logger.info("Disconnecting from region %s" % (self.SimName))

        try:

            self.send_LogoutRequest(self.agent.agent_id, self.agent.session_id)

            # ToDo: We should parse a response packet prior to really disconnecting
            Wait(1)

            self.message_manager.stop_monitors()
            return True
        except Exception, error:
            logger.error("Error logging out from region.")
            return False

    def send_LogoutRequest(self, agent_id, session_id):
        """ send a LogoutRequest message to the host simulator """

        packet = Message('LogoutRequest',
                        Block('AgentData',
                                AgentID = agent_id,
                                SessionID = session_id))

        self.message_manager.send_udp_message(packet)

    def kill_coroutines(self):
        """ trigger to end processes spawned by the child regions """

        self.message_manager.stop_monitors()
        
    def _init_agent_in_region(self):
        """ send a few packets to set things up """

        # send the UseCircuitCode packet
        self.sendUseCircuitCode(self.circuit_code, self.agent.session_id, self.agent.agent_id)

        # wait a sec, then send the rest
        time.sleep(1)

        # send the CompleteAgentMovement packet
        self.sendCompleteAgentMovement(self.agent.agent_id, self.agent.session_id, self.circuit_code)

        # send a UUIDNameRequest packet
        #self.sendUUIDNameRequest()

        # send an AgentUpdate packet to complete the loop
        self.sendAgentUpdate(self.agent.agent_id, self.agent.session_id)

    def sendUseCircuitCode(self, circuit_code, session_id, agent_id):
        """ initializing on a simulator requires announcing the circuit code an agent will use """

        packet = Message('UseCircuitCode',
                        Block('CircuitCode',
                                Code = circuit_code,
                                SessionID = session_id,
                                ID = agent_id))

        self.message_manager.send_udp_message(packet, reliable=True)

    def sendCompleteAgentMovement(self, agent_id, session_id, circuit_code):
        """ initializing on a simulator requires sending CompleteAgentMovement, also required on teleport """

        packet = Message('CompleteAgentMovement',
                        Block('AgentData',
                                AgentID = agent_id,
                                SessionID = session_id,
                                CircuitCode = circuit_code))

        self.message_manager.send_udp_message(packet, reliable=True)

    def sendUUIDNameRequest(self, agent_ids = []):
        """ sends a packet requesting the name corresponding to a UUID """

        packet = Message('UUIDNameRequest',
                        *[Block('UUIDNameBlock',
                                ID = agent_id) for agent_id in agent_ids])

        self.message_manager.send_udp_message(packet)

    def sendAgentUpdate(self,
                        AgentID,
                        SessionID,
                        BodyRotation = (0.0,0.0,0.0,1.0),
                        HeadRotation = (0.0,0.0,0.0,1.0),
                        State = 0x00,
                        CameraCenter = (0.0,0.0,0.0),
                        CameraAtAxis = (0.0,0.0,0.0),
                        CameraLeftAxis = (0.0,0.0,0.0),
                        CameraUpAxis = (0.0,0.0,0.0),
                        Far = 0,
                        ControlFlags = 0x00,
                        Flags = 0x00):
        """ sends an AgentUpdate packet to *this* simulator"""

        packet = Message('AgentUpdate',
                        Block('AgentData',
                                AgentID = AgentID,
                                SessionID = SessionID,
                                BodyRotation = BodyRotation,
                                HeadRotation = HeadRotation,
                                State = State,
                                CameraCenter = CameraCenter,
                                CameraAtAxis = CameraAtAxis,
                                CameraLeftAxis = CameraLeftAxis,
                                CameraUpAxis = CameraUpAxis,
                                Far = Far,
                                ControlFlags = ControlFlags,
                                Flags = Flags))

        self.enqueue_message(packet)

    def sendRegionHandshakeReply(self, AgentID, SessionID, Flags = 00):
        """ sends a RegionHandshake packet """

        packet = Message('RegionHandshakeReply',
                        Block('AgentData',
                                AgentID = AgentID,
                                SessionID = SessionID),
                        Block('RegionInfo',
                                Flags = Flags))

        self.message_manager.send_udp_message(packet, reliable=True)

    def sendCompletePingCheck(self, PingID):
        """ sends a CompletePingCheck packet """

        packet = Message('CompletePingCheck',
                        Block('PingID',
                                PingID = PingID))

        self.message_manager.send_udp_message(packet)

        # we need to increment the last ping id
        self.last_ping += 1
    

    def onRegionHandshake(self, packet):
        """ handles the response to receiving a RegionHandshake packet """

        # send the reply
        self.sendRegionHandshakeReply(self.agent.agent_id, self.agent.session_id)

        # propagate the incoming data
        self.SimName = packet['RegionInfo'][0]['SimName']
        self.SimAccess = packet['RegionInfo'][0]['SimAccess']
        self.SimOwner = packet['RegionInfo'][0]['SimOwner']
        self.IsEstateManager = packet['RegionInfo'][0]['IsEstateManager']
        self.WaterHeight = packet['RegionInfo'][0]['WaterHeight']
        self.BillableFactor = packet['RegionInfo'][0]['BillableFactor']
        self.TerrainBase0 = packet['RegionInfo'][0]['TerrainBase0']
        self.TerrainBase1 = packet['RegionInfo'][0]['TerrainBase1']
        self.TerrainBase2 = packet['RegionInfo'][0]['TerrainBase2']
        self.TerrainStartHeight00 = packet['RegionInfo'][0]['TerrainStartHeight00']
        self.TerrainStartHeight01 = packet['RegionInfo'][0]['TerrainStartHeight01']
        self.TerrainStartHeight10 = packet['RegionInfo'][0]['TerrainStartHeight10']
        self.TerrainStartHeight11 = packet['RegionInfo'][0]['TerrainStartHeight11']
        self.TerrainHeightRange00 = packet['RegionInfo'][0]['TerrainHeightRange00']
        self.TerrainHeightRange01 = packet['RegionInfo'][0]['TerrainHeightRange01']
        self.TerrainHeightRange10 = packet['RegionInfo'][0]['TerrainHeightRange10']
        self.TerrainHeightRange11 = packet['RegionInfo'][0]['TerrainHeightRange11']
        self.CPUClassID = packet['RegionInfo3'][0]['CPUClassID']
        self.CPURatio = packet['RegionInfo3'][0]['CPURatio']
        self.ColoName = packet['RegionInfo3'][0]['ColoName']
        self.ProductSKU = packet['RegionInfo3'][0]['ProductSKU']
        self.ProductName = packet['RegionInfo3'][0]['ProductName']
        self.RegionID = packet['RegionInfo2'][0]['RegionID']

        # we are connected
        self.connected = True

        logger.info("Connected agent \'%s %s\' to region %s" % (self.agent.firstname, self.agent.lastname, self.SimName))

    def onStartPingCheck(self, packet):
        """ sends the CompletePingCheck packet """

        self.sendCompletePingCheck(self.last_ping)

    @staticmethod
    def globalxy_to_handle(x, y):
        """Convert a global x, y location into a 64-bit region handle"""
        x, y = int(x), int(y)
        x -= x % 256
        y -= y % 256
        handle = x << 32 | y
        return handle

    @staticmethod
    def handle_to_globalxy(handle):
        """Convert a region handle into a global x,y location. Handle can be an int or binary string."""
        import struct
        if isinstance(handle, str):
            handle =  struct.unpack('>Q', handle)[0]

        x = handle >> 32
        y = handle & 0xffffffff

        return x, y

    @staticmethod
    def gridxy_to_handle(x, y):
        """Convert an x, y region grid location into a 64-bit handle"""

        return Region.globalxy_to_handle(x * Region.WIDTH, y * Region.WIDTH)

    @staticmethod
    def handle_to_gridxy(handle):
        """Convert a handle into an x,y region grid location. Handle can be an int or binary string."""

        x, y = Region.handle_to_globalxy(handle)

        return x / Region.WIDTH, y / Region.WIDTH


class RegionSeedCapability(Capability):
    """ a seed capability which is able to retrieve other capabilities """

    def get(self, names=[], settings = None):
        """if this is a seed cap we can retrieve other caps here"""

        # allow the settings to be passed in
        # otherwise, grab the defaults
        if settings != None:
            self.settings = settings
        else:
            from pyogp.lib.client.settings import Settings
            self.settings = Settings()

        #logger.info('requesting from the region domain the following caps: %s' % (names))

        payload = names
        parsed_result = self.POST(payload)  #['caps']
        if self.settings.ENABLE_CAPS_LOGGING:
            logger.info('Request for caps returned: %s' % (parsed_result.keys()))

        caps = {}
        for name in names:
            # TODO: some caps might be seed caps, how do we know? 
            if parsed_result.has_key(name):
                caps[name] = Capability(name, parsed_result[name], settings = self.settings)
            else:
                if self.settings.ENABLE_CAPS_LOGGING:
                    logger.debug('Requested capability \'%s\' is not available' %  (name))
            #logger.info('got cap: %s' % (name))

        return caps

    def __repr__(self):
        return "<RegionSeedCapability for %s>" % (self.public_url)



