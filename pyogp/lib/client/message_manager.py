
"""
message_manager.py
Implements the MessageManager class which faciliates the sending and receiving
of messages between a simulator through either the UDP or Capability message
paths.

Contributors: http://svn.secondlife.com/svn/linden/projects/2008/pyogp/CONTRIBUTORS.txt 

$LicenseInfo:firstyear=2008&license=apachev2$

Copyright (c) 2009, Linden Research, Inc.

Licensed under the Apache License, Version 2.0 (the "License").
You may obtain a copy of the License at:
    http://svn.secondlife.com/svn/linden/projects/2008/pyogp/LICENSE.txt
$/LicenseInfo$
"""

from pyogp.lib.base.message.udpdispatcher import UDPDispatcher
from pyogp.lib.base.message.circuit import Host
from pyogp.lib.base.message.message import Message, Block
from pyogp.lib.base.message.message_handler import MessageHandler
from pyogp.lib.client.event_queue import EventQueueClient

from eventlet import api

# initialize logging
logger = getLogger('pyogp.lib.client.message_manager')


class MessageManager(object):
    """ 
    This object serves as a consolidation point for all messaging related
    functionality in the base/message directory.
    """

    def __init__(self, region, message_handler = None, settings = None, 
                 start_monitors = True):
        """ 
        Initialize the MessageManager, applying custom settings and dedicated 
        message_handler if needed 
        """
        self.region = region
        # allow the settings to be passed in
        # otherwise, grab the defaults
        if settings != None:
            self.settings = settings
        else:
            self.settings = Settings()

        # allow the message_handler to be passed in
        # otherwise, grab the defaults
        if message_handler != None:
            self.message_handler = message_handler
        elif self.settings.HANDLE_PACKETS:
            self.message_handler = MessageHandler()

        log.debug("initializing the Message Manager")
        
        
        # initialize the manager's base attributes
        #self.builder = MessageBuilder()     # 
        #self.connections = {}               # a connection = {Host():
                                            #                       {'udp':UDPDispatcher(),
                                            #                       'event_queue_client':EventQueueClient()}}
        self.incoming_queue = []            # a list of incoming Message() instances
        self.outgoing_queue = []            # a list of (Message(), reliable) instances to be sent to an endpoint

        self._is_running = False
        #event queue-related attributes
        self.event_queue = EventQueueClient(self.capabilities['EventQueueGet'], 
                                            settings = self.settings, 
                                            message_handler = self.message_handler, 
                                            region = self.region)
        self.incoming_events_queue = []
        self.outgoing_events_queue = []
        
        #UDP-related attributes
        self.host = host
        self.incoming_udp_queue = []
        self.outgoing_udp_queue = []
        self.udp_dispatcher = UDPDispatcher(settings = self.settings, 
                                            message_handler = self.message_handler) 
                                            
        
        # if start parameter = True, kick off the queue monitors
        if start_monitors:
            self.start_monitors()

    def start_monitors(self):
        """ spawn queue monitoring coroutines """
        self._is_running = True
        api.spawn(self._udp_dispatcher)
        api.spawn(self._event_queue_dispatcher)
        #api.spawn(self.monitor_outgoing_queue)
        #api.spawn(self.monitor_incoming_queue)
        
    def stop_monitors(self):
        """ stops monitoring coroutines """
        #stops udp_dispatcher
        self._running = False
        #stops event_queue
        if self.event_queue._running:
            self.event_queue.stop()        

    def monitor_outgoing_queue(self):
        """  """

    def enqueue_message(self, message, endpoint, reliable = False, now = False):
        """ enqueues a Message() in the outgoing_queue """

        # ToDo: should a reliable flag parameter be required here?
        if now:
            self.outgoing_queue.insert(0, (packet, reliable))
        else:
            self.outgoing_queue.append((message, reliable))

    def send_message():
        """  """
        pass

    def new_message(self, name):
        pass
    
    def _udp_dispatcher(self):
        """
        Sends and receives UDP messages.
        """
        logger.debug('Spawning region UDP connection')
        while self._is_running:
            api.sleep(0)
            msg_buf, msg_size = self.udp_dispatcher.udp_client.receive_packet(self.udp_dispatcher.socket)
            recv_packet = self.udp_dispatcher.receive_check(self.udp_dispatcher.udp_client.get_sender(),
                                              msg_buf, 
                                              sg_size)
            #self.outgoing_udp_queue.append(recv_packet)
            if self.udp_dispatcher.has_unacked():
                self.udp_dispatcher.process_acks()
                
            for (packet, reliable) in self.outgoing_udp_queue:
                self.send_message(packet, reliable)
                self.outgoing_udp_queue.remove((packet, reliable))
                
        logger.debug("Stopped the UDP connection for %s" % (self.region.SimName))
    
    def _event_queue_dispatcher(self):
        if self.region.seed_capability_url != None:
            logger.debug('Spawning region event queue connection')
            self.event_queue.start
        
