
"""
Contributors can be viewed at:
http://svn.secondlife.com/svn/linden/projects/2008/pyogp/lib/base/trunk/CONTRIBUTORS.txt 

$LicenseInfo:firstyear=2010&license=apachev2$

Copyright 2009, Linden Research, Inc.

Licensed under the Apache License, Version 2.0.
You may obtain a copy of the License at:
    http://www.apache.org/licenses/LICENSE-2.0
or in 
    http://svn.secondlife.com/svn/linden/projects/2008/pyogp/lib/base/LICENSE.txt

$/LicenseInfo$
"""

# standard python libs
from logging import getLogger


# pyogp
from pyogp.lib.base.datatypes import UUID
from pyogp.lib.client.exc import DataParsingError
from pyogp.lib.base.helpers import Wait
from pyogp.lib.client.datamanager import DataManager
from pyogp.lib.client.region import Region

# pyogp messaging
from pyogp.lib.base.message.message import Message, Block

# pyogp utilities
from pyogp.lib.client.enums import MapItem

# initialize logging
logger = getLogger('pyogp.lib.client.map')


class MapService(DataManager):
    """
    Wrapper for map services, such as looking up region names, telehubs,
    agent locations, etc.
    """




    def __init__(self, agent, settings = None):
        """ initialize the group manager """
        super(MapService, self).__init__(agent, settings)


        self.name_to_handle = {}

        
        if self.settings.LOG_VERBOSE:
            logger.debug("Initialized the Map Service")

    def enable_callbacks(self):
        """enables the callback handlers"""
        pass


    def request_handle(self, region_name, callback):
        """Given a region name, will call a callback function when the handle
        (which encodes the x/y location of the region) is looked up. A null handle
        (0, 0) denotes failure to find the region. Results are cached for
        subsequent calls."""
        region_name = region_name.lower()

        if region_name in self.name_to_handle:
            callback(self.name_to_handle[region_name])
            return
        
        handler = self.agent.region.message_handler.register('MapBlockReply')

        def onMapBlockReply(packet):
            """ handles the MapBlockReply message from a simulator """

            for data in packet['Data']:

                if data['Name'].lower() == region_name:

                    # Stop listening once we have the data we asked for
                    handler.unsubscribe(onMapBlockReply)

                    region_handle = Region.xy_to_handle(data['X'], data['Y'])

                    callback(region_handle)
                    return

            # Keep listening, as the event may come later

        # Register a handler for the response        
        handler.subscribe(onMapBlockReply)

        packet = Message('MapNameRequest', 
                        Block('AgentData', 
                            AgentID = self.agent.agent_id, 
                            SessionID = self.agent.session_id,
                            Flags = 0,
                            EstateID = 0, # filled in on server
                            Godlike = False), # filled in on server
                        Block('NameData',
                            Name = region_name))

        self.agent.region.enqueue_message(packet) 


    def search(self, query, callback):
        """Search for region info by region name. Returns a list of dicts.
        Results are NOT cached for subsequent calls."""
        handler = self.agent.region.message_handler.register('MapBlockReply')

        results = []

        # This is sent as the "Access" field to indicate the end of the
        # search results.
        END_OF_RESULTS = 255

        def onMapBlockReply(packet):
            """ handles the MapBlockReply message from a simulator """

            for data in packet['Data']:

                if data['Access'] == END_OF_RESULTS:
                    handler.unsubscribe(onMapBlockReply)
                    callback(results)
                    return

                else:
                    results.append({
                        'x': data['X'],
                        'y': data['Y'],
                        'name': data['Name']
                        })

        # Register a handler for the response        
        handler.subscribe(onMapBlockReply)

        packet = Message('MapNameRequest', 
                        Block('AgentData', 
                            AgentID = self.agent.agent_id, 
                            SessionID = self.agent.session_id,
                            Flags = 0,
                            EstateID = 0, # filled in on server
                            Godlike = False), # filled in on server
                        Block('NameData',
                            Name = query))

        self.agent.region.enqueue_message(packet) 



    def request_agent_locations(self, region_handle, callback):
        """For a given region (identified by handle), calls the callback
        function with a list of tuples (count, x, y) providing a rough
        distribution of agents within the region."""

        handler = self.agent.region.message_handler.register('MapItemReply')

        region_x, region_y = Region.handle_to_xy(region_handle)

        BLOCK_COUNT_PER_PACKET = 21

        cluster_list = []

        def onMapItemReply(packet):
            item_type = packet['RequestData'][0]['ItemType']
            if item_type == MapItem.AgentLocations:
                for data in packet['Data']:
                    count = data['Extra']
                    x = data['X']
                    y = data['Y']

                    if count and region_x == int(x/Region.WIDTH) and region_y == int(y/Region.WIDTH):
                        cluster_list.append((count, x % Region.WIDTH, y % Region.WIDTH))

            # This end condition is unreliable, and determined by inspecting
            # the simulator code. The viewer just receives the packets and
            # displays data as it appears, but has no completion indicator.
            if len(packet['Data']) < BLOCK_COUNT_PER_PACKET:
                handler.unsubscribe(onMapItemReply)
                callback(cluster_list)

        handler.subscribe(onMapItemReply)

        packet = Message('MapItemRequest', 
                         Block('AgentData', 
                               AgentID = self.agent.agent_id, 
                               SessionID = self.agent.session_id,
                               Flags = 0,
                               EstateID = 0, # filled in on server
                               Godlike = False), # filled in on server
                         Block('RequestData',
                            ItemType = MapItem.AgentLocations,
                               RegionHandle = region_handle))
        
        self.agent.region.enqueue_message(packet)
