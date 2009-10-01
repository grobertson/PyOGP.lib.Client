
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
import unittest

# pyogp
from pyogp.lib.client.namevalue import *
from pyogp.lib.base.datatypes import Vector3

# pyogp tests
import pyogp.lib.base.tests.config 

class TestNameValues(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_parseserialize(self):

        test_types = [
            "Alpha STRING R S 'Twas brillig and the slighy toves/Did gyre and gimble in the wabe",
            "Beta F32 R S 3.14159",
            "Gamma S32 R S -12345",
            "Delta VEC3 R S <1.2, -3.4, 5.6>",
            "Epsilon U32 R S 12345",
            "Zeta ASSET R S 041a8591-6f30-42f8-b9f7-7f281351f375",
            "Eta U64 R S 9223372036854775807"
        ]

        for test in test_types:
            nv = NameValue(test)
            result = repr(nv)
            self.assertEquals(test, result)


    def test_enums(self):

        for enum in NameValueType, NameValueClass, NameValueSendTo:

            for name1 in enum.Strings:
                val1 = enum.parse(name1)
                name2 = enum.repr(val1)
                val2 = enum.parse(name2)
                
                self.assertEquals(name1, name2)
                self.assertEquals(val1, val2)
            

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestNameValues))
    return suite


