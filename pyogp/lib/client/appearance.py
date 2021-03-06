
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

# standard python libs
from logging import getLogger
import uuid

#related
import eventlet

# pyogp
from pyogp.lib.client.datamanager import DataManager
# pyogp messaging
from pyogp.lib.base.message.message_handler import MessageHandler
from pyogp.lib.base.message.message import Message, Block

from pyogp.lib.base.helpers import Helpers
from pyogp.lib.client.exc import NotImplemented
from pyogp.lib.client.objects import Object
from pyogp.lib.client.visualparams import VisualParams
from pyogp.lib.base.datatypes import UUID, Vector3
from pyogp.lib.client.enums import BakedIndex, TextureIndex, \
     WearableMap, AssetType, WearablesIndex
from pyogp.lib.client.assets import AssetWearable

# initialize logging
logger = getLogger('pyogp.lib.client.appearance')

class AppearanceManager(DataManager):
    """The AppearanceManager class handles appearance of an Agent() instance

    Sample implementations: 
    Tests: 
    """

    def __init__(self, agent, settings = None):
        """
        initialize the appearance manager
        """
        super(AppearanceManager, self).__init__(agent, settings)
        self.AgentSetSerialNum = 1
        self.AgentCachedSerialNum = 1
        self.wearables = {} #indexed by WearableType
        for i in range(TextureIndex.TEX_COUNT):
            self.wearables[i] = Wearable(i)
        self.helpers = Helpers()
        self.bakedTextures = {} #indexed by TextureIndex
        for i in range(BakedIndex.BAKED_COUNT):
            self.bakedTextures[i] = BakedTexture(i)
        self.visualParams = VisualParams().params
        self.visualParams[32].value = 1.0
        self.TextureEntry = ""
        self.requests = []

    def enable_callbacks(self):
        """
        enables the calback handlers for this AppearanceManager
        """
        onAgentWearablesUpdate_received = self.agent.region.message_handler.register('AgentWearablesUpdate')
        onAgentWearablesUpdate_received.subscribe(self.onAgentWearablesUpdate)
        onAgentCachedTextureResponse_received = self.agent.region.message_handler.register('AgentCachedTextureResponse')
        onAgentCachedTextureResponse_received.subscribe(self.onAgentCachedTextureResponse)
        #onAvatarAppearance_received = self.agent.region.message_handler.register('AvatarAppearance')
        #onAvatarAppearance_received.subscribe(self.onAvatarAppearance)
        self.request_agent_wearables()
        '''
        onAgentDataUpdate_received = self.agent.region.message_handler.register('AgentDataUpdate')
        onAgentDataUpdate_received.subscribe(self.helpers.log_packet, self)
        '''

    def wear_item(self, item, wearable_type):
        self.wearables[wearable_type].ItemID = item.ItemID
        self.wearables[wearable_type].AssetID = item.AssetID
        self.send_AgentSetAppearance(self.agent.agent_id,
                                     self.agent.session_id,
                                     self.get_size(),
                                     self.bakedTextures,
                                     self.TextureEntry,
                                     self.visualParams)
        self.send_AgentIsNowWearing(self.agent.agent_id,
                                    self.agent.session_id,
                                    self.wearables)

    
    def request_agent_wearables(self):
        """
        Asks the simulator what the avatar is wearing
        #TODO create a one--shot callback
        """
        if self.agent.agent_id == None or self.agent.session_id == None or \
              str(self.agent.agent_id) == str(UUID()) or \
              str(self.agent.session_id) == str(UUID()):
           logger.warning("Agent has either no agent_id or session_id, message not sent")
           return

        self.send_AgentWearablesRequest(self.agent.agent_id,
                                        self.agent.session_id)

    def get_size(self):
        """
        Computes the size of the avatar, bases off of libomv's implementation for now.
        """
        height = 1.706 + (self.visualParams[692].value*0.1918) + (self.visualParams[842].value*0.0375) + \
                 (self.visualParams[33].value*0.12022) + (self.visualParams[682].value*0.01117) + \
                 (self.visualParams[756].value*0.038) + (self.visualParams[198].value*0.08) + \
                 (self.visualParams[503].value*0.07)
        return Vector3(X = 0.45, Y = 0.60, Z = height )
        
    def wearableArrived(self, assetID, isSuccess):
        """
        callback for wearables request
        """


        self.requests.remove(str(assetID))
        if isSuccess:
            base_asset = self.agent.asset_manager.get_asset(assetID)
            asset = AssetWearable(base_asset.assetID, base_asset.assetType, base_asset.data)
            asset.parse_data()
            logger.debug("Received wearable data for %s" % (asset.Name))
            for paramID in asset.params.keys():
                self.visualParams[paramID].value = asset.params[paramID]
            if len(self.requests) == 0:
                logger.info("YAY!! Got all requested assets")
            self.send_AgentCachedTexture(self.agent.agent_id,
                                         self.agent.session_id,
                                         self.bakedTextures,
                                         self.wearables)
            #self.send_AgentIsNowWearing(self.agent.agent_id,
            #                        self.agent.session_id,
            #                        self.wearables)

    def onAgentWearablesUpdate(self, packet):
        """
        Automatically tells simulator avatar is wearing the wearables from
        the AgentWearables update packet.
        This message should only be received once.

        Error Checking: make sure agent and session id are correct
        make sure this method is only called once.

        """

        #self.verifyAgentData(packet)
        #logger.debug("AgentWearablesUpdate: %s" % packet)
        shape = packet['WearableData'][0]
        if shape['WearableType'] != WearablesIndex.WT_SHAPE:
            raise TypeError("Wrong wearable types")
        if str(shape['AssetID']) == '00000000-0000-0000-0000-000000000000':
            #sim has no wearable data on this avatar set defaults
            #self.create_default_wearables()

            #send avatar is now wearing
            #self.send_AgentIsNowWearing(self.agent.agent_id,
            #                        self.agent.session_id,
            #                        self.wearables)
            return
        
        for wearableData in packet['WearableData']:
            wearableType = wearableData['WearableType']
            itemID = wearableData['ItemID']
            assetID = wearableData['AssetID']
            wearable = self.wearables[wearableType]
            wearable.ItemID = itemID
            wearable.AssetID = assetID                
            if str(assetID) != '00000000-0000-0000-0000-000000000000':
                self.agent.asset_manager.request_asset(assetID, wearable.getAssetType(),
                                                       True, self.wearableArrived)
                self.requests.append(str(assetID))

    def onAvatarTextureUpdate(self, packet):
        raise NotImplemented("onAvatarTextureUpdate")

    def onAvatarAppearance(self, packet):
        """
        Informs viewer how other avatars look
        """
        raise NotImplemented("onAvatarAppearance")

    def onAgentCachedTextureResponse(self, packet):
        """
        Update the bakedTextures with their TextureIDs and HostNames and call
        send_AgentSetAppearance
        """
        #logger.debug("AgentCachedTextureRespose received: %s" % packet)
        for bakedTexture in packet['WearableData']:
            bakedIndex = bakedTexture['TextureIndex']
            self.bakedTextures[bakedIndex].TextureID = bakedTexture['TextureID']
            self.bakedTextures[bakedIndex].HostName = bakedTexture['HostName']
        self.send_AgentSetAppearance(self.agent.agent_id,
                                     self.agent.session_id,
                                     self.get_size(),
                                     self.bakedTextures,
                                     self.TextureEntry,
                                     self.visualParams)

    def verifyAgentData(self, packet):
        """
        verifies that packet refers to this agent
        """
        pAgentID = packet['AgentData'][0]["AgentID"]
        pSessionID = packet['AgentData'][0]["SessionID"]
        if  str(pAgentID) != str(self.agent.agent_id):
            logger.warning("%s packet does not have an AgentID", packet.name)
        if str(pSessionID) != str(self.agent.session_id):
            logger.warning("%s packet does not have a SessionID" % packet.name)

    def send_AgentWearablesRequest(self, AgentID, SessionID):
        """
        sends and AgentWearablesRequest message.
        """
        packet = Message('AgentWearablesRequest',
                         Block('AgentData',
                               AgentID = AgentID,
                               SessionID = SessionID))

        self.agent.region.enqueue_message(packet)

    def send_AgentIsNowWearing(self, AgentID, SessionID, wearables):
        """
        Tell the simulator that avatar is wearing initial items
        """
        args = [Block('AgentData',
                      AgentID = AgentID,
                      SessionID = SessionID)]
        args += [Block('WearableData',
                       ItemID = wearables[key].ItemID,
                       WearableType = wearables[key].WearableType) \
                 for key in wearables.keys()]

        packet = Message('AgentIsNowWearing', *args)

        self.agent.region.enqueue_message(packet, True)

    def send_AgentCachedTexture(self, AgentID, SessionID, bakedTextures,
                                wearables):
        """
        Ask the simulator what baked textures it has cached.
        TODO Create a one-shot callback?
        """
        args = [Block('AgentData',
                      AgentID = AgentID,
                      SessionID = SessionID,
                      SerialNum = self.AgentCachedSerialNum)]

        args += [Block('WearableData',
                       ID = bakedTextures[i].get_hash(wearables),
                       TextureIndex = i) \
                 for i in range(BakedIndex.BAKED_COUNT)]

        packet = Message('AgentCachedTexture', *args)



        self.AgentCachedSerialNum += 1
        self.agent.region.enqueue_message(packet, True)


    def send_AgentSetAppearance(self, AgentID, SessionID, Size, bakedTextures,
                                TextureEntry, visualParams):
        """
        Informs simulator how avatar looks
        """
        args = [Block('AgentData',
                      AgentID = AgentID,
                      SessionID = SessionID,
                      SerialNum = self.AgentSetSerialNum, 
                      Size = Size)]

        args += [Block('WearableData',
                       CacheID = bakedTextures[i].TextureID,
                       TextureIndex = bakedTextures[i].bakedIndex) \
                 for i in range(BakedIndex.BAKED_COUNT)]

        args += [Block('ObjectData',
                      TextureEntry = TextureEntry)]

        paramkeys = visualParams.keys()
        paramkeys.sort()
        args += [Block('VisualParam',
                       ParamValue = visualParams[key].floatToByte()) \
                 for key in paramkeys if visualParams[key].group is 0]

        packet =  Message('AgentSetAppearance', *args)

        self.AgentSetSerialNum += 1
        self.agent.region.enqueue_message(packet)

    def create_default_wearables(self):
        create = [True, True, True, True, True, True, True, True, False, False, \
                  True, True, False]
        for i in range(WearablesIndex.WT_COUNT):
            if create[i]:
                asset_id == UUID()
                asset_id.random()
                self.wearables[i] = Wearable(i, AssetID=asset_id)


class Wearable(object):
    """
    Represents 1 of the 13 wearables an avatar can wear
    """
    def __init__(self, WearableType = None, ItemID = UUID(), AssetID = UUID()):
        self.WearableType = WearableType
        self.ItemID = ItemID
        self.AssetID = AssetID

    def getAssetType(self):
        if self.WearableType == WearablesIndex.WT_SHAPE or \
           self.WearableType == WearablesIndex.WT_SKIN or \
           self.WearableType == WearablesIndex.WT_HAIR or \
           self.WearableType == WearablesIndex.WT_EYES:
            return AssetType.BodyPart
        elif self.WearableType == WearablesIndex.WT_SHIRT or \
             self.WearableType == WearablesIndex.WT_PANTS or \
             self.WearableType == WearablesIndex.WT_SHOES or \
             self.WearableType == WearablesIndex.WT_SOCKS or \
             self.WearableType == WearablesIndex.WT_JACKET or \
             self.WearableType == WearablesIndex.WT_GLOVES or \
             self.WearableType == WearablesIndex.WT_UNDERSHIRT or \
             self.WearableType == WearablesIndex.WT_UNDERPANTS or \
             self.WearableType == WearablesIndex.WT_SKIRT:
            return AssetType.Clothing
        else:
            return AssetType.NONE


class BakedTexture(object):
    """
    Represents 1 of the 6 baked textures of an avatar
    """
    def __init__(self, bakedIndex, TextureID = UUID()):
        self.bakedIndex = bakedIndex
        self.TextureID = TextureID
        self.HostName = None

        if bakedIndex == BakedIndex.BAKED_HEAD:
            self.secret_hash = UUID("18ded8d6-bcfc-e415-8539-944c0f5ea7a6")
        elif bakedIndex == BakedIndex.BAKED_UPPER:
            self.secret_hash = UUID("338c29e3-3024-4dbb-998d-7c04cf4fa88f")
        elif bakedIndex == BakedIndex.BAKED_LOWER:
            self.secret_hash = UUID("91b4a2c7-1b1a-ba16-9a16-1f8f8dcc1c3f")
        elif bakedIndex == BakedIndex.BAKED_EYES:
            self.secret_hash = UUID("b2cf28af-b840-1071-3c6a-78085d8128b5")
        elif bakedIndex == BakedIndex.BAKED_SKIRT:
            self.secret_hash = UUID("ea800387-ea1a-14e0-56cb-24f2022f969a")
        elif bakedIndex == BakedIndex.BAKED_HAIR:
            self.secret_hash = UUID("0af1ef7c-ad24-11dd-8790-001f5bf833e8")
        else:
            self.secret_hash = UUID()

    def get_hash(self, wearables):
        """
        Creates a hash using the assetIDs for each wearable in a baked layer
        """
        wearable_map = WearableMap().map
        hash = UUID()
        for wearable_index in wearable_map[self.bakedIndex]:
            hash ^= wearables[wearable_index].AssetID
        if str(hash) != '00000000-0000-0000-0000-000000000000':
            hash ^= self.secret_hash
        return hash

class AvatarTexture(object):
    """
    Represents 1 of the 21 baked and not baked textures of an avatar.
    """
    def __init__(self, TextureIndex, TextureID = None):
        self.TextureIndex = TextureIndex
        self.TextureID = TextureID

