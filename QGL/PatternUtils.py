'''
Copyright 2013 Raytheon BBN Technologies

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
import numpy as np
from warnings import warn
from math import pi
import hashlib, collections
import pickle
from copy import copy
from collections.abc import Iterable
from functools import reduce
import operator

from .PulseSequencer import Pulse, TAPulse, PulseBlock, CompositePulse, CompoundGate, align
from .PulsePrimitives import BLANK, X
from . import ControlFlow
from . import BlockLabel
from . import TdmInstructions
from . import ChannelLibraries
import QGL.drivers
from functools import reduce
import operator

def hash_pulse(shape):
    return hashlib.sha1(shape.tostring()).hexdigest()


TAZKey = hash_pulse(np.zeros(1, dtype=np.complex))


def delay(sequences, delay):
    '''
    Delays a sequence by the given amount.
    '''
    if delay <= 0:  # no need to inject zero delays
        return
    for seq in sequences:
        # loop through and look for WAIT instructions
        # use while loop because len(seq) will change as we inject delays
        ct = 0
        while ct < len(seq) - 1:
            if seq[ct] == ControlFlow.Wait() or seq[ct] == ControlFlow.Sync():
                seq.insert(ct + 1, TAPulse("Id", seq[ct + 1].channel, delay,
                                           0))
            ct += 1


def normalize_delays(delays):
    '''
    Normalizes a dictionary of channel delays. Postive delays shift right, negative delays shift left.
    Since we cannot delay by a negative amount in hardware, shift all delays until they are positive.
    Takes in a dict of channel:delay pairs and returns a normalized copy of the same.
    '''
    out = dict(delays)  # copy before modifying
    if not out or len(out) == 0:
        # Typically an error (empty sequence)
        import logging
        logging.error("normalize_delays() had no delays?")
        return out
    min_delay = min(delays.values())
    if min_delay < 0:
        for chan in delays.keys():
            out[chan] += -min_delay
    return out


def correct_mixers(wfLib, T):
    for k, v in wfLib.items():
        # To get the broadcast to work in numpy, need to do the multiplication one row at a time
        iqWF = np.vstack((np.real(v), np.imag(v)))
        wfLib[k] = T[0, :].dot(iqWF) + 1j * T[1, :].dot(iqWF)


def add_gate_pulses(seq):
    '''
    add gating pulses to Qubit pulses
    '''

    for ct in range(len(seq)):
        if isinstance(seq[ct], CompoundGate):
            add_gate_pulses(seq[ct].seq)
        elif isinstance(seq[ct], PulseBlock):
            pb = None
            for chan, pulse in seq[ct].pulses.items():
                if has_gate(chan) and not pulse.isZero and not (
                        chan.gate_chan in seq[ct].pulses.keys()):
                    if pb:
                        pb *= BLANK(chan, pulse.length)
                    else:
                        pb = BLANK(chan, pulse.length)
            if pb:
                seq[ct] *= pb
        elif hasattr(seq[ct], 'channel'):
            chan = seq[ct].channel
            if has_gate(chan) and not seq[ct].isZero:
                seq[ct] *= BLANK(chan, seq[ct].length)

def add_parametric_pulses(seq):
    '''
    add parametric pulses linked to predetermined channels, e.g. for parametric readout
    '''

    for ct in range(len(seq)):
        if isinstance(seq[ct], CompoundGate):
            add_parametric_pulses(seq[ct].seq)
        elif isinstance(seq[ct], PulseBlock):
            pb = None
            for chan, pulse in seq[ct].pulses.items():
                if has_parametric(chan) and not pulse.isZero and not (
                        chan.parametric_chan in seq[ct].pulses.keys()):
                    if pb:
                        pb *= X(chan.parametric_chan, length = pulse.length)
                    else:
                        pb = X(chan.parametric_chan, length = pulse.length)
            if pb:
                seq[ct] *= pb
        elif hasattr(seq[ct], 'channel'):
            chan = seq[ct].channel
            if has_parametric(chan) and not seq[ct].isZero:
                seq[ct] *= X(chan.parametric_chan, length = seq[ct].length)

def has_gate(channel):
    return hasattr(channel, 'gate_chan') and channel.gate_chan

def has_parametric(channel):
    return hasattr(channel, 'parametric_chan') and channel.parametric_chan

def update_pulse_length(pulse, new_length):
    """Return new Pulse with modified length"""
    assert new_length >= 0
    #copy shape parameter dictionary to avoid updating other copies
    new_params = copy(pulse.shapeParams)
    new_params["length"] = new_length
    return pulse._replace(shapeParams=new_params, length=new_length)

def apply_gating_constraints(chan, linkList):
    # get channel parameters in samples
    if not hasattr(chan, 'gate_buffer'):
        raise AttributeError("{0} does not have gate_buffer".format(chan.label))

    if not hasattr(chan, 'gate_min_width'):
        raise AttributeError("{0} does not have gate_min_width".format(
            chan.label))

    # get channel parameters
    gate_buffer = chan.gate_buffer
    gate_min_width = chan.gate_min_width

    #Initialize list of sequences to return
    gateSeqs = []

    for miniLL in linkList:
        gateSeq = []
        # first pass consolidates entries
        previousEntry = None
        for ct,entry in enumerate(miniLL):
            if isinstance(entry,
                    (ControlFlow.ControlInstruction, BlockLabel.BlockLabel,
                        TdmInstructions.CustomInstruction,
                        TdmInstructions.WriteAddrInstruction,
                        TdmInstructions.LoadCmpVramInstruction)):

                if previousEntry:
                    gateSeq.append(previousEntry)
                    previousEntry = None
                gateSeq.append(entry)
                continue

            if previousEntry is None:
                previousEntry = entry
                continue

            # matching entry types can be globbed together
            if previousEntry.isZero == entry.isZero:
                previousEntry = update_pulse_length(previousEntry, previousEntry.length + entry.length)
            else:
                gateSeq.append(previousEntry)
                previousEntry = entry

        # push on the last entry if necessary
        if previousEntry:
            gateSeq.append(previousEntry)

        # second pass expands non-zeros by gate_buffer
        for ct in range(len(gateSeq)):
            if isNonZeroWaveform(gateSeq[ct]):
                gateSeq[ct] = update_pulse_length(gateSeq[ct], gateSeq[ct].length + gate_buffer)

                # contract the next pulse by the same amount
                if ct + 1 < len(gateSeq) - 1 and isinstance(gateSeq[ct + 1], Pulse):
                    gateSeq[ct+1] = update_pulse_length(gateSeq[ct+1], gateSeq[ct+1].length - gate_buffer)

        # third pass ensures gate_min_width
        ct = 0
        while ct + 2 < len(gateSeq):
            # look for pulse, delay, pulse pattern and ensure delay is long enough
            if [isNonZeroWaveform(x) for x in gateSeq[ct:ct+3]] == [True, False, True] and \
                gateSeq[ct+1].length < gate_min_width and \
                [isinstance(x, Pulse) for x in gateSeq[ct:ct+3]] == [True, True, True]:
                gateSeq[ct] = update_pulse_length(gateSeq[ct], gateSeq[ct + 1].length + gateSeq[ct + 2].length)
                del gateSeq[ct + 1:ct + 3]
            else:
                ct += 1
        gateSeqs.append(gateSeq)

    return gateSeqs


def isNonZeroWaveform(entry):
    return isinstance(entry, Pulse) and not entry.isZero


def add_digitizer_trigger(seqs):
    '''
    Add a digitizer trigger to a logical LL (pulse blocks).
    '''
    # Attach a trigger to any pulse block containing a measurement. Each trigger is specific to each measurement
    for seq in seqs:
        for ct in range(len(seq)):
            if not contains_measurement(seq[ct]):
                continue
            #find corresponding digitizer trigger
            chanlist = list(flatten([seq[ct].channel]))
            for chan in chanlist:
                if hasattr(chan, 'trig_chan') and chan.trig_chan is not None:
                    trig_chan = chan.trig_chan
                    if not (hasattr(seq[ct], 'pulses') and
                            trig_chan in seq[ct].pulses.keys()):
                        seq[ct] = align('left', seq[ct], TAPulse("TRIG", trig_chan, trig_chan.pulse_params['length'], 1.0, 0.0, 0.0))


def contains_measurement(entry):
    """
    Determines if a LL entry contains a measurement (with a digitizer trigger)
    """
    if hasattr(entry, 'label') and entry.label == "MEAS":
        return True
    elif isinstance(entry, PulseBlock):
        for p in entry.pulses.values():
            if hasattr(p, 'label') and p.label == "MEAS":
                return True
    return False


def add_slave_trigger(seqs, slaveChan):
    '''
    Add the slave trigger to each sequence.
    '''
    for seq in seqs:
        # Attach a TRIG immediately after a WAIT.
        ct = 0
        while ct < len(seq) - 1:
            if isinstance(seq[ct], ControlFlow.Wait):
                try:
                    seq[ct + 1] = align('left', seq[ct + 1], TAPulse("TRIG", slaveChan, slaveChan.pulse_params['length'], 1.0, 0.0, 0.0))
                except:
                    seq.insert(ct + 1, TAPulse("TRIG", slaveChan,
                                               slaveChan.pulse_params['length'],
                                               1.0, 0.0, 0.0))
                ct += 2  # can skip over what we just modified
            else:
                ct += 1


def propagate_frame_changes(seq, wf_type):
    '''
    Propagates all frame changes through sequence
    '''
    frame = 0
    for entry in seq:
        if not isinstance(entry, wf_type):
            continue
        entry.phase = np.mod(frame + entry.phase, 2 * pi)
        frame += entry.frameChange + (-2 * np.pi * entry.frequency *
                                      entry.length
                                      )  #minus from negative frequency qubits
    return seq


def quantize_phase(seqs, precision, wf_type):
    '''
    Quantizes waveform phases with given precision (in radians).
    '''
    for entry in flatten(seqs):
        if not isinstance(entry, wf_type):
            continue
        phase = np.mod(entry.phase, 2 * np.pi)
        entry.phase = precision * round(phase / precision)
    return seqs


def convert_lengths_to_samples(instructions, sampling_rate, quantization=1, wf_type=None):
    for entry in flatten(instructions):
        if isinstance(entry, wf_type):
            entry.length = int(round(entry.length * sampling_rate))
            # TODO: warn when truncating?
            entry.length -= entry.length % quantization

    return instructions

def convert_length_to_samples(wf_length, sampling_rate, quantization=1):
    num_samples = int(round(wf_length * sampling_rate))
    num_samples -= num_samples % quantization
    return num_samples

# from Stack Overflow: http://stackoverflow.com/questions/2158395/flatten-an-irregular-list-of-lists-in-python/2158532#2158532
def flatten(l):
    for el in l:
        if isinstance(el, Iterable) and not isinstance(el, (str, Pulse, CompositePulse)) :
            for sub in flatten(el):
                yield sub
        else:
            yield el


def update_wf_library(pulses, path):
    """
    Update the waveform library in-place.

    Parameters
    ------------
    pulses : iterable of pulse object to update
        e.g. [X90(q1), X(q1), Y90(q1), Y(q1), X90(q2), X(q2), Y90(q2), Y(q2), ZX90_CR(q1, q2)]
    path : path to base name of files to update e.g. /path/to/GST/GST will update files such as
        /path/to/GST/GST-APSII1.h5 and /path/to/GST/GST-APSII2.h5
    """
    #Look through the pulses and figure out what pulses are associated with which APS
    awg_pulses = collections.defaultdict(dict)
    translators = {}

    def flatten_pulses():
        for p in flatten(pulses):
            if isinstance(p, CompositePulse):
                for sub_p in p.pulses:
                    yield sub_p
            else:
                yield p

    pulse_list = list(flatten_pulses())
    for ct, pulse in enumerate(pulse_list):
        awg = pulse.channel.phys_chan.instrument
        if awg not in translators:
            translators[awg] = getattr(QGL.drivers,
                                       pulse.channel.phys_chan.translator)
        if pulse.label not in awg_pulses[awg]:
            awg_pulses[awg][pulse.label] = pulse_list[ct]

    for awg, ps in awg_pulses.items():
        #load the offset dictionary for this AWG
        try:
            with open(path + "-" + awg + ".offsets", "rb") as FID:
                offsets = pickle.load(FID)
        except IOError:
            print("Offset file not found for {}, skipping pulses {}".format(
                awg, [str(p) for p in ps.values()]))
            continue
        print("Updating pulses for {}".format(awg))
        translators[awg].update_wf_library(path + "-" + awg + ".aps", ps,
                                           offsets)

def decouple_seqs(seqs, meas_qs, meas_decoupled_qs, CR_chs, CR_decoupled_chs):
    for seq in seqs:
        if meas_decoupled_qs:
            decouple_meas_pulses(seq, meas_qs, meas_decoupled_qs)
        if CR_decoupled_chs:
            decouple_CR_pulses(seq, CR_chs, CR_decoupled_chs)

def decouple_meas_pulses(seq, meas_qs, meas_decoupled_qs):
    """
    Add decoupling X pulses to qubits meas_decoupled_qs during measurement on qubits meas_qs
    """
    for (k,pulse) in enumerate(seq):
        if isinstance(pulse, Pulse):
            for qM in meas_qs:
                #TODO: check if pulse block
                if pulse.channel == ChannelLibraries.MeasFactory('M-%s' % qM.label):
                    #TODO: add arbitary shift of X from center
                    seq[k] = align(pulse *\
                        reduce(operator.mul, [X(q) for q in meas_decoupled_qs]))

def decouple_CR_pulses(seq, CR_qs, CR_decoupled_qs):
    """
    Add decoupling X pulses to qubits CR_decoupled_qs between CR pulses on qubit pairs CR_qs (list of tuples)
    """
    for seq_el in seq:
        #for qsCR in CR_qs:
        if isinstance(seq_el, CompoundGate):
            for (k, pulse) in enumerate(seq_el.seq):
                if isinstance(pulse.channel, collections.abc.KeysView) and any([ChannelLibraries.EdgeFactory(*qsCR) in pulse.channel for qsCR in CR_qs]):
                    seq_el.seq[k+1] = reduce(operator.mul, [seq_el.seq[k+1]] + [X(q) for q in CR_decoupled_qs])
                elif any([pulse.channel == ChannelLibraries.EdgeFactory(*qsCR) for qsCR in CR_qs]):# and pulse.channel == seq_el.seq[k+2].channel:
                    seq_el.seq[k+1] = reduce(operator.mul, [seq_el.seq[k+1]] + [X(q) for q in CR_decoupled_qs])
    return seq

