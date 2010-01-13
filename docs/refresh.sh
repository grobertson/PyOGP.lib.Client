#!/bin/bash

conf_dir='source/configure/'
source_dir='source/'
html_dir='html/'

export PYTHONPATH=$1
echo $PYTHONPATH
sphinx-build -a -c $conf_dir $source_dir $html_dir