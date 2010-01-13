
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
import os
# standard python libs
from logging import getLogger
import uuid

#related
from eventlet import api

# pyogp
from pyogp.lib.client.datamanager import DataManager
from pyogp.lib.client.enums import TransferChannelType, TransferSourceType, \
     TransferTargetType, TransferStatus

# pyogp messaging
from pyogp.lib.base.message.message_handler import MessageHandler
from pyogp.lib.base.message.message import Message, Block
from pyogp.lib.base.helpers import Helpers
from pyogp.lib.client.exc import NotImplemented, ResourceError, ResourceNotFound
from pyogp.lib.client.objects import Object
from pyogp.lib.base.datatypes import Vector3, UUID
from pyogp.lib.base.caps import Capability
from pyogp.lib.client.enums import AssetType

# initialize logging
logger = getLogger('pyogp.lib.client.assets')

class AssetManager(DataManager):
    """
    The AssetManager class handles the assets of an Agent() instance

    Sample implementations: 
    Tests: test_assets.py 
    """

    def __init__(self, agent, settings = None):
        super(AssetManager, self).__init__(agent, settings)
        #indexed by assetID
        self.assets = {} 

    def enable_callbacks(self):
        pass


    def request_asset(self, assetID, assetType, isPriority, callback=None, itemID=None):
        """
        Sends a TransferRequest to the sim for asset assetID with type assetType,
        will call callback with the assetID and True with the asset received or False
        if request failed.  On successful request the asset is store in
        self.assets 
        TODO add a timeout
        """
        transferID = UUID()  #associate the assetID with the transferID
        transferID.random()
        transferInfoHandler = self.agent.region.message_handler.register('TransferInfo')
        transferPacketHandler = self.agent.region.message_handler.register('TransferPacket')
        def onTransferPacket(packet):
            """
            TransferPacket of a successful TransferRequest
            """
            # fill in data for Asset in the requests queue and pop it off and story in assets dict
            if str(transferID) == str(packet['TransferData'][0]['TransferID']):
                
                
                                                              
                # insert packet
                self.assets[str(assetID)].store_packet(packet['TransferData'][0]['Packet'],
                                                       packet['TransferData'][0]['Data'],
                                                       packet['TransferData'][0]['Status'])
                if self.assets[str(assetID)].is_downloaded():
                    self.assets[str(assetID)].assemble_data()
                    if callback != None:
                        callback(assetID, True)
                    transferPacketHandler.unsubscribe(onTransferPacket)
                else:
                    pass
                    # wait for more packets

        def onTransferInfo(packet):
            """
            Status of TransferRequest
            Account for size and multiple packets
            """
            if not self.assets.has_key(str(assetID)):
                    self.assets[str(assetID)] = Asset(assetID, assetType)
                    
            if str(transferID) == str(packet['TransferInfo'][0]['TransferID']):
                status = packet['TransferInfo'][0]["Status"]
                if status != TransferStatus.OK:
                    logger.warning("Request for asset %s failed with status %s" \
                        % (assetID, status))
                    if callback != None:
                        callback(assetID, False)
                    transferPacketHandler.unsubscribe(onTransferPacket)
                else:
                    self.assets[str(assetID)].size = packet['TransferInfo'][0]['Size']
                transferInfoHandler.unsubscribe(onTransferInfo)

        transferInfoHandler.subscribe(onTransferInfo)
        transferPacketHandler.subscribe(onTransferPacket)

        if isPriority:
            priority = 1.0
        else:
            priority = 0.0

        params = ''
        if itemID != None:
            params += self.agent.agent_id.get_bytes() + \
                      self.agent.session_id.get_bytes() + \
                      self.agent.agent_id.get_bytes() + \
                      UUID().get_bytes() + \
                      itemID.get_bytes()
        params += assetID.get_bytes() + \
                  Helpers().int_to_bytes(assetType) 

        self.send_TransferRequest(transferID,
                                  TransferChannelType.Asset,
                                  TransferSourceType.Asset,
                                  priority,
                                  params)

    def request_sound_asset(self, assetID):
        """
        requests a sound asset from the simulator 
        """
        self.request_asset(assetID, AssetType.Sound, False, self.on_sound_transfer)

    def on_sound_transfer(self, assetID, is_success):
        """
        on the sucessful retrieval of asset date a sound file is created
        and the download buffer is cleared.  asset.dataq is set to the
        filname.
        """

        mod_path = os.path.dirname(__file__)
        
        if not is_success:
            return
        temp_path = mod_path + "/temp/"
        temp_filename = temp_path + str(assetID) + ".dsf"
        if not os.path.exists(temp_path):
            os.mkdir(temp_path)
        sound = self.get_asset(assetID)
        sound_file = open(temp_filename, 'wb') 
        sound_file.write(sound.data)        
        sound_file.close()
        sound.data = temp_filename
                          
    """
    def upload_asset(self, transaction_id, type_, tempfile, store_local,
                     asset_data=None):

        assetUploadCompleteHandler = self.agent.region.message_handler.register('AssetUploadComplete')
        def onAssetUploadComplete(packet):
            logger.info("AssetUploadComplete: %s" % packet)

        assetUploadCompleteHandler.subscribe(onAssetUploadComplete)

        self.send_AssetUploadRequest(transaction_id, type_, tempfile,
                                     store_local)
    """

    def upload_script_via_caps(self, item_id, script):
        """
        uploads a plaintext LSL file via UploadScriptAgent capability
        """
        custom_post_body = {'item_id' : str(item_id), 'target': 'lsl2'}
        self.upload_via_caps("UpdateScriptAgent", item_id, script, custom_post_body)
        
        
    def upload_notecard_via_caps(self, item_id, note_text):
        """
        uploads a note via UploadNotecard capability
        """
        note = "Linden text version 2\n{\nLLEmbeddedItems version 1\n" + \
                          "{\ncount 0\n}\nText length " + str(len(note_text)) + "\n" + note_text + \
                          "}\n"
        self.upload_via_caps("UpdateNotecardAgentInventory", item_id, note)
        
    def upload_via_caps(self, cap_name, item_id, item, custom_post_body={}):
        """
        Uploads payload via cap_name Capability
        """
        if cap_name not in self.agent.region.capabilities.keys():
            logger.error("Capability %s not found")
            return
        cap = self.agent.region.capabilities[cap_name]
        if custom_post_body == {}:
            post_body = {"item_id" : str(item_id)}
        else:
            post_body = custom_post_body

        try:
            response = cap.POST(post_body)
        except ResourceError, error:
            logger.error(error)
            return
        except ResourceNotFound, error:
            logger.error("404 calling: %s" % (error))
            return
        if response.has_key('uploader'):
            self.upload_via_caps_responder(response['uploader'], item)                                            
        else:
            logger.warning("Upload via %s failed"  % cap_name)
                           
    def upload_via_caps_responder(self, url, payload):
        """
        Creates a Capability instance for the given url and POSTS the payload.
        """
        cap = Capability("uploader", url)
        headers = {"Content-type" : "application/octet-stream",
                           "Expect" : "100-continue",
                           "Connection" : "close" }
        try:
            response = cap.POST_CUSTOM(headers, payload)
        except ResourceError, error:
            logger.error(error)
            return
        except ResourceNotFound, error:
            logger.error("404 calling: %s" % (error))
            return
        if response["state"] == "complete":
            logger.debug("Successful upload to: %s" % url)
        else:
            logger.warning("Failed upload to: %s" % url)
    
    def get_asset(self, assetID):
        """
        returns an asset from the asset store given an assetID
        """
        return self.assets[str(assetID)]

    def send_AssetUploadRequest(self, TransactionID, Type, Tempfile, \
                                StoreLocal, AssetData=None):
        """
        Sends an AssetUploadRequest packet to request that an asset be
        uploaded to the to the sim
        """
        packet = Message('AssetUploadRequest',
                         Block('AssetBlock',
                               TransactionID = TransactionID,
                               Type = Type,
                               Tempfile = Tempfile,
                               StoreLocal = StoreLocal,
                               AssetData = AssetData))
        self.agent.region.enqueue_message(packet)


    def send_TransferRequest(self, TransferID, ChannelType, SourceType,
                             Priority, Params):
        """
        sends a TransferRequest packet to request an asset to download, the
        assetID and assetType of the request are stored in the Params variable
        see assets.request_asset for example.
        """
        packet = Message('TransferRequest',
                         Block('TransferInfo',
                               TransferID = TransferID,
                               ChannelType = ChannelType,
                               SourceType = SourceType,
                               Priority = Priority,
                               Params = Params))
        self.agent.region.enqueue_message(packet)

class Asset(object):
    """
    Object which represents an asset downloaded from a sim.
    """
    def __init__(self, assetID, assetType):
        self.assetID = assetID
        self.assetType = assetType
        self.data = ""
        self.download_buffer = {}
        self.last_packet = -1
        self.size = 0
        
    def store_packet(self, packet_num, packet_data, status):
        """
        Stores a individual packet for this asset.
        """
        self.download_buffer[packet_num] = packet_data
        if status == 1:
            self.last_packet = packet_num

    def is_downloaded(self):
        """
        Tests whether all packets have been downloaded for this asset
        """
        if self.last_packet == -1 or \
               (self.last_packet + 1) != len(self.download_buffer):
            return False
        else:
            return True

    def assemble_data(self):
        """
        Takes each of the individual packets and assembles them into self.data
        """
        for i in range(self.last_packet + 1):
            self.data += self.download_buffer[i]
        self.download_buffer.clear()
        
        
class AssetWearable(Asset):

    def __init__(self, assetID, assetType, data = None):
        super(AssetWearable, self).__init__(assetID, assetType)
        self.Version = -1
        self.Name = ''
        self.Description = ''
        self.Type = -1
        self.Permissions = ''
        self.SaleInfo = ''
        self.params = {}
        self.textures = {}
        self.data = data
        self.parse_data()
        

    def parse_data(self):
        if not self.data:
            return
        tokens = self.data.split()
        i = iter(tokens)
        while True:
            try:
                token = i.next()
                if token.lower() == 'version':
                    self.Version = int(i.next())
                if token.lower() == 'type':
                    self.Type = int(i.next())
                if token.lower() == 'parameters':
                    count = int(i.next())
                    for num in range(count):
                        paramID = int(i.next())
                        paramVal = i.next()
                        #TODO Verify this is correct behavior this fix may be a hack
                        if paramVal == '.':
                            self.params[paramID] = 0.0
                        else:
                            self.params[paramID] = float(paramVal)
                if token.lower() == 'textures':
                    count = int(i.next())
                    for num in range(count):
                        textureID = int(i.next())
                        self.textures[textureID] = UUID(i.next())
            except StopIteration:
                break


