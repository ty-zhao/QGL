'''
Original Author: Guilhem Ribeill

Copyright 2020 Raytheon BBN Technologies

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

from QGL.drivers.APS2Pattern import read_sequence_file
import numpy as np 
import os
import json

def convert(filename):
    """Converts .aps2 file `filename` to a CSV format"""
    basename, ext = os.path.splitext(filename)
    assert ext == ".aps2", "Unrecognized file type {0}!".format(ext)

    wfs = read_sequence_file(filename)

    for marker in ['m1', 'm2', 'm3', 'm4']:
        if not any(wfs[marker]):
            continue
        with open("{0}-{1}.csv".format(basename, marker), "w") as fid:
            for wf in wfs[marker]:
                if wf:
                    ta = np.hstack([np.repeat(value, count) for (count, value) in wf])
                else:
                    ta = np.array([0])
                ta.tofile(fid, ", ", "%d")
                fid.write('\n')

    for chan in ['ch1', 'ch2']:
        with open("{0}-{1}.csv".format(basename, chan), "w") as fid:
            for wf in wfs[chan]:
                ta = np.array([x[1] for x in wf])
                ta.tofile(fid, ", ", "%g")
                fid.write('\n')


def convert_batch(metafile):
    with open(metafile, 'r') as FID:
        meta_info = json.load(FID)
    fileNames = []
    for el in meta_info["instruments"].values():
        # Accomodate seq_file per instrument and per channel
        if isinstance(el, str):
            fileNames.append(el)
        elif isinstance(el, dict):
            for file in el.values():
                fileNames.append(file)
    for fn in fileNames:
        convert(fn)