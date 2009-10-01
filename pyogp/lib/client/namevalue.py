
"""
Contributors can be viewed at:
http://svn.secondlife.com/svn/linden/projects/2008/pyogp/lib/base/trunk/CONTRIBUTORS.txt 

$LicenseInfo:firstyear=2009&license=apachev2$

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
import re

# pyogp
from pyogp.lib.base.datatypes import Vector3


# initialize logging
logger = getLogger('pyogp.lib.client.namevalue')

class NameValueType(object):
    """Value types for NameValues"""

    Unknown = 0
    String = 1
    F32 = 2
    S32 = 3
    Vector3 = 4
    U32 = 5
    CAMERA = 6 # Obsolete
    Asset = 7
    U64 = 8

    Default = String
    Strings = ['NULL', 'STRING', 'F32', 'S32', 'VEC3', 'U32', 'CAMERA', 'ASSET', 'U64']

    @staticmethod
    def parse(name):
        """Return a 'enum' value given a string, or the default value
        if there is no match."""
        try:
            return NameValueType.Strings.index(name)
            
        except ValueError:
            return NameValueType.Default

    @staticmethod
    def repr(value):
        """Return the string representation of an 'enum' value."""
        return NameValueType.Strings[value]
                
class NameValueClass(object):
    """Class types for NameValues"""
    
    Null = 0
    ReadOnly = 1
    ReadWrite = 2

    Default = ReadOnly
    Strings = ['NULL', 'R', 'RW']

    @staticmethod
    def parse(name):
        """Return a 'enum' value given a string, or the default value
        if there is no match."""
        try:
            return NameValueClass.Strings.index(name)
            
        except ValueError:
            return NameValueClass.Default
                
    @staticmethod
    def repr(value):
        """Return the string representation of an 'enum' value."""
        return NameValueClass.Strings[value]
                

class NameValueSendTo(object):
    """Send To types for NameValues"""

    Null = 0
    Sim = 1
    DataSim = 2
    SimViewer = 3
    DataSimViewer = 4

    Default = Sim
    Strings = ['NULL', 'S', 'DS', 'SV', 'DSV']

    @staticmethod
    def parse(name):
        """Return a 'enum' value given a string, or the default value
        if there is no match."""
        try:
            return NameValueSendTo.Strings.index(name)
            
        except ValueError:
            return NameValueSendTo.Default
                
    @staticmethod
    def repr(value):
        """Return the string representation of an 'enum' value."""
        return NameValueSendTo.Strings[value]
                


class NameValue(object):
    """ represents a typed name-value pair as used in object updates

        Examples:
            namevalues = [NameValue(data=s) for s in rawdata.split('\n')]
            nv = NameValue(name='lastname', value='Linden')
            nv = NameValue(name='arc', value_type=NameValueType.U32, value=123)
    """
    _re_separators = re.compile('[ \n\t\r]')


    def __init__(self, data=None, name='', value_type=NameValueType.Default,
                 class_=NameValueClass.Default, send_to=NameValueSendTo.Default,
                 value=''):
        
        self.name = name
        self.value = value
        self.value_type = value_type
        self.class_ = class_
        self.send_to = send_to

        if data:
            chunks = NameValue._re_separators.split(data, 4)

            if len(chunks) > 1:
                self.name = chunks.pop(0)
                
            if len(chunks) > 1:
                self.value_type = NameValueType.parse(chunks.pop(0))
                
            if len(chunks) > 1:
                self.class_ = NameValueClass.parse(chunks.pop(0))
                
            if len(chunks) > 1:
                self.send_to = NameValueSendTo.parse(chunks.pop(0))

            self._set_value(chunks[0])

        
    def __repr__(self):
        return "%s %s %s %s %s" % (
            self.name,
            NameValueType.repr(self.value_type), 
            NameValueClass.repr(self.class_), 
            NameValueSendTo.repr(self.send_to),
            self.value
            )

    def __str__(self):
        return "Name='%s' Type='%s' Class='%s' SendTo='%s' Value='%s'" % (
            self.name,
            NameValueType.repr(self.value_type), 
            NameValueClass.repr(self.class_), 
            NameValueSendTo.repr(self.send_to),
            self.value
            )

    def _set_value(self, value):
        if self.value_type in (NameValueType.Asset, NameValueType.String):
            self.value = value

        elif self.value_type == NameValueType.F32:
            try:
                self.value = float(value)
            except ValueError:
                logger.warn("Unparsable float in NameValue: %s", value)
                self.value = 0

        elif self.value_type in (NameValueType.S32, NameValueType.U32, NameValueType.U64):
            try:
                self.value = int(value)
            except ValueError:
                logger.warn("Unparsable int in NameValue: %s", value)
                self.value = 0

        elif self.value_type == NameValueType.Vector3:
            try:
                self.value = Vector3.parse(value)
            except ValueError:
                self.value = Vector3(X=0, Y=0, Z=0)

        else:
            self.value = None
            logger.warn("Unknown value type in NameValue: %s", self.value_type)


class NameValueList(object):

    def __init__(self, data):

        if data:
            self.namevalues = [NameValue(line) for line in data.split('\n')]
        else:
            self.namevalues = []

        self._dict = dict([(nv.name, nv.value) for nv in self.namevalues])


    def __repr__(self):
        return self.namevalues.join('\n')

    def __getitem__(self, key):
        return self._dict[key]

