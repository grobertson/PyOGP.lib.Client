
"""
Contributors can be viewed at:
http://svn.secondlife.com/svn/linden/projects/2008/pyogp/lib/client/trunk/CONTRIBUTORS.txt 

$LicenseInfo:firstyear=2008&license=apachev2$

Copyright 2009, Linden Research, Inc.

Licensed under the Apache License, Version 2.0.
You may obtain a copy of the License at:
    http://www.apache.org/licenses/LICENSE-2.0
or in 
    http://svn.secondlife.com/svn/linden/projects/2008/pyogp/lib/client/LICENSE.txt

$/LicenseInfo$
"""

import os, sys
import re
import pyclbr
import subprocess

module_file_ext = ".rst"

def main():

    source_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'source'))
    html_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'html'))
    conf_dir = os.path.join(source_dir, 'configure')
    modules_dir = os.path.abspath(os.path.join(source_dir, 'modules'))
    unit_test_dir = os.path.abspath(os.path.join(source_dir, 'unittest'))
    eggs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../eggs/'))
    lib_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    modules_root_dir = os.path.abspath(os.path.join(lib_dir, 'pyogp', 'lib', 'client'))

    path_additions = []

    path_additions.append(lib_dir)

    try:
        import pyogp.lib.base
        print "pyogp.lib.base is in the path, continuing..."
        base_dir = None
    except ImportError:
        print "pyogp.lib.base is required and is not in the path, checking for the package in buildout"

        base_dir = os.path.abspath(os.path.join(lib_dir, '../pyogp.lib.base'))

        if os.path.isdir(base_dir):
            path_additions.append(base_dir)
        else:
            raise ImportError("cannot find pyogp.lib.base")

    if not os.path.isdir(lib_dir):
        print "pyogp.lib.client is not found in src/ as expected, stopping"
        sys.exit()

    # skip files in processing docs
    skipfiles = ['build_packet_templates.py']

    if not os.path.isdir(modules_dir):
        print "Creating modules directory: %s" % (modules_dir)
        os.mkdir(modules_dir)

    if not os.path.isdir(unit_test_dir):
        print "Creating unit test modules directory: %s" % (unit_test_dir)
        os.mkdir(unit_test_dir)

    if os.path.isdir(eggs_dir):

        for directory in os.listdir(eggs_dir):
            path_additions.append(os.path.join(eggs_dir + directory))

    else:
        print 'All dependencies required to be in system path...'

    sys.path[0:0] = path_additions

    mock = 0

    def remove(mock, dirname, fnames):

        if not re.search("/.svn", dirname):

            for fname in fnames:
                if not re.search(".svn", fname):
                    #print "  Removing " + os.path.join(dirname, fname)
                    os.remove(os.path.join(dirname, fname))

                    mock += 1

    print "Cleaning the sources/modules/ dir..."

    # remove .rst files in source/modules
    os.path.walk(modules_dir, remove, mock)

    print "Cleaning the sources/unittest/ dir..."

    # remove .rst files in source/unittest
    os.path.walk(unit_test_dir, remove, mock)

    # ToDO: purge the html/ dir
    # print "Cleaning the html/ dir..."

    store = {}

    def callback(store, dirname, fnames):

        keepers = []

        if not re.search("/.svn", dirname):

            for f in fnames:
                if (re.search(".py$", f) or re.search(".txt$", f)) and not re.search("__init_", f) and not f in skipfiles:
                    keepers.append(f)

            store[dirname] = keepers

    # look for .py files in pyogp.lib.client
    print "Parsing package for docs: %s" % (modules_root_dir)
    os.path.walk(modules_root_dir, callback, store)

    def get_handle(_dir, fname):

        f = open(os.path.join(_dir, fname), 'w')

        #print "  Writing %s" % (fname)

        return f

    def close_handle(handle):

        handle.close()

    def write_rst(handle, params, header = ''):

        package_root = params[0]    # is the root path + directory
        module = params[1]          # is the full package path
        mod_name = params[2]        # is the name of the directory within pyogp.lib.client
        fname = params[3]           # is the root name of the .py file
        mod_ext = params[4]         # extension of the source file
        

        if header != '':
            handle.write(header + "\n")

        if mod_ext == "txt":

            title = mod_name

            handle.write(title + "\n")
            handle.write("=" * len(title) + "\n")
            handle.write("\n")

            handle.write("\n")
            handle.write(".. module:: " + module + "\n")
            handle.write("\n")

            handle.write("This is a doctest, the content here is verbatim from the source file at %s.\n" % (module + "." + mod_ext))
            handle.write("\n")

            source_handle = open(os.path.join(lib_dir, "/".join(module.split(".")) + "." + mod_ext))

            # skip the 17 line license comment
            counter = 0
            
            for line in source_handle.readlines():
                if counter <17:
                    counter+=1
                else:
                    handle.write(line)

            # this is a doctest
        else:

            title = ":mod:`" + mod_name + "`"

            handle.write(title + "\n")
            handle.write("=" * len(title) + "\n")

            handle.write("\n")
            handle.write(".. automodule:: " + module + "\n")
            handle.write("\n")

            for k in pyclbr.readmodule(module):

                # hack to workaround something i cant reckon
                if module == 'pyogp.lib.client.groups' and k in ['UUID', 'Vector3', 'Quaternion']:
                    continue

                #print "    adding %s" % (k)

                handle.write(".. autoclass:: " + module + "." + k + "\n")
                handle.write("  :members:" + "\n")
                handle.write("  :undoc-members:" + "\n")
                if not re.search("test_", mod_name):
                    handle.write("  :inherited-members:" + "\n")
                handle.write("" + "\n")

    print "Building modules sphinx files..."

    unit_tests = []

    for k in store:

        offset = len(k.split("/")) - (len(k.split("/")) - len(lib_dir.split("/")))

        package_root = '.'.join(k.split("/")[offset:])

        for fname in store[k]:

            mod_name = fname.split(".")[0]
            mod_ext = fname.split(".")[1]

            if package_root == "pyogp.lib.client.":
                module = package_root + mod_name
            else:
                module = package_root + "." + mod_name

            fname = mod_name + module_file_ext

            # skip the sample implementation scripts
            if re.search("sample", mod_name) and re.search("pyogp.lib.client.examples", package_root):
                continue

            # handle unit tests separately
            if re.search("test", mod_name) or re.search("test", package_root):
                unit_tests.append((package_root, module, mod_name, fname, mod_ext))
                continue

            handle = get_handle(modules_dir, fname)

            write_rst(handle, (package_root, module, mod_name, fname, mod_ext))

            close_handle(handle)

    print "Building unit test sphinx files..."

    for params in unit_tests:

        handle = get_handle(unit_test_dir, params[3])

        write_rst(handle, params)

        close_handle(handle)

    if base_dir != None:
        cmd = os.path.abspath(os.path.join(os.path.dirname(__file__), 'refresh.sh'))
        builder = subprocess.Popen([cmd, base_dir]).wait()
    else:
        builder = subprocess.Popen(['sphinx-build', '-a', '-c', conf_dir, source_dir, html_dir]).wait()


if __name__ == '__main__':
    main()