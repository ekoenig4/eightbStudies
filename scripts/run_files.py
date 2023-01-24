#!/bin/env python

# %%
import os
os.environ['KMP_WARNINGS'] = 'off'
import sys
import git

import matplotlib as mpl
mpl.use('Agg')

import uproot as ut
import awkward as ak
import numpy as np
import math
import vector
import sympy as sp

import re
from tqdm import tqdm
import timeit
import re

sys.path.append( git.Repo('.', search_parent_directories=True).working_tree_dir )
from utils import *

# %%
from argparse import ArgumentParser, RawTextHelpFormatter

templates = { subclass.__name__:subclass() for subclass in Analysis.__subclasses__() }

driver = ArgumentParser(
    description='General Analysis Driver',
    formatter_class=RawTextHelpFormatter
)

subparser = driver.add_subparsers()

for name, template in templates.items():
    parser = subparser.add_parser(
        name=name,
        description=str(repr(template)),
        formatter_class=RawTextHelpFormatter    
    )
    method_list = template.methods.keys
    parser.add_argument('--ignore-error', default=False, action='store_true')
    parser.add_argument(f'--module', default='fc.eightb.preselection.t8btag_minmass', help='specify the file collection module to use for all samples')
    parser.add_argument('--template', default=template, dest='_class_template_')
    parser.add_argument(f'--only', nargs="*", help=f'Disable all other methods from run list', default=method_list)
    parser.add_argument(f'--disable', nargs="*", help=f'Disable method from run list', default=[])
    parser.add_argument(f'--debug', default=False, action='store_true', help='disable running analysis for debug')
    template._add_parser(parser)

args, unk = driver.parse_known_args()

print("---Arguments---")
for key, value in vars(args).items():
    if key.startswith('_'): continue
    print(f"{key} = {value}")
if any(unk):
    print(f"uknown = {unk}")
print()

template = args._class_template_
method_list = template.methods.keys

def _module(mod):
    local = dict()
    exec(f"module = {mod}", globals(), local)
    return local['module']
module = _module(args.module)

def _file(f):
    if fc.exists(f): return f
    local = dict()
    exec(f"f = module.{f}", globals(), local)
    return local['f']

files = [ _file(f) for f in unk ]

def iter_files(fs):
    if isinstance(fs, list): return fs
    else: return [fs]

altfile = getattr(args, 'altfile', '{base}')

files = [ f for fs in files for f in iter_files(fs) ]
signal, bkg, data = ObjIter([]), ObjIter([]), ObjIter([])

if not args.debug:
    trees = [ Tree(f, altfile=altfile, report=False) for f in tqdm(files) ]
    signal = ObjIter([ tree for tree in trees if tree.is_signal ])
    bkg = ObjIter([ tree for tree in trees if (not tree.is_data and not tree.is_signal) ])
    data = ObjIter([ tree for tree in trees if tree.is_data ])
else:
    print(files)

# %%
def add_to_list(i, method):
    import re 

    for disable in args.disable:
        if disable.isdigit() and int(disable) == i: return False
        if re.match(f'^{disable}$', method): return False 

    for only in args.only:
        if only.isdigit() and int(only) == i: return True
        if re.match(f'^{only}$', method): return True 

    return False
    
runlist = [method for i, method in enumerate(method_list) if add_to_list(i, method)]

analysis = template.__class__(
    signal=signal, bkg=bkg, data=data,
    runlist=runlist,
    **vars(args)
)

print( repr(analysis) )

if args.debug: exit()

analysis.run()