# Getting Started with QGL

## Table of Contents

1. [What is QGL](#What-is-QGL)
1. [Dependencies](#Dependencies)
1. [Installation](#Installation)
1. [Examples](#Examples)
1. [Channels and Qubits](#Channels-and-Qubits)
1. [Gate Primitives](#Gate-Primitives)
1. [Sequences and Concurrent Operations](#Sequences-and-Concurrent-Operations)
1. [Pulse Shapes and Waveforms](#Pulse-Shapes-and-Waveforms)
1. [Compiling and Plotting](#Compiling-and-Plotting)
1. [Built-in Basic Sequences](#Built-in-Basic-Sequences)


## What is QGL <a name="What-is-QGL"></a>

Quantum Gate Language (QGL) is a domain specific programming language embedded in python for
specifying gate sequences on quantum processors. It is a low-level language in
the sense that users write programs at the level of gates on physical qubits.
While the QGL developers pay particular attention to the requirements of
superconducting qubit systems, its structure is generic to any qubit system with
dipole-coupled qubits in a rotating frame. In such systems, the rotation axis in
the X-Y plane is determined by the pulse phase, and Z-axis rotations may be
achieved through *frame updates*.


## Dependencies <a name="Dependencies"></a>

QGL is embedded in the python programming language. Currently, it is dependent on python versions 3.6+. QGL programming constructs look very similar to python programming constructs.    

QGL relies on the concept of a "channel" to represent a qubit. The channel embodies the physical realization of the qubit in an experimental configuration or a simulation configuration. These characteristic can include physical qubit attributes, simulation or equipment mappings, and physical couplings between qubits. This configuration information is specified and maintained in an associated database, [bbndb](https://github.com/BBN-Q/bbndb), which is necessary for compiling the QGL program into inputs for physical systems (such as realizable signals/pulses) or simulation inputs (native instruction set). 

While QGL is *not* dependent on [Auspex](https://github.com/BBN-Q/auspex), Auspex is an experiment control framework which greatly facilitates executing QGL programs on laboratory hardware. Auspex provides constructs for abstracting (defining) instruments, connectivity, and post processing to enable "hands off" experimental control of sophiscated experiments on a variety of laboratory equipment including AWGs, digitizers, current sources, etc.    

For plotting pulse waveforms within jupyter notebooks, QGL uses the bqplot library (which should be installed automatically when using the methods detailed below) and should not require any additional infrastructure. **For Jupyter Lab compatibility** additional steps are required:

```
conda install nodejs
jupyter labextension install @jupyter-widgets/jupyterlab-manager
jupyter labextension install bqplot
```

## Installation <a name="Installation"></a>

There are a number of ways to obtain QGL:

Directly from the pypi, which will get the most recent master release, e.g. 2019.2:

```pip install qgl```

QGL can be cloned from GitHub to participate in QGL development:

```git clone https://github.com/BBN-Q/qgl.git```   

Or the source tree can be downloaded from GitHub. For the master branch:

```https://github.com/BBN-Q/QGL/archive/master.zip```   

For downloaded or cloned repositories, one most subsequently install the package using pip:

```
cd QGL    
pip install -e .       
```

which will automatically fetch and install all of the requirement packages. As typical with package managers,
this process will execute the package requirements enumerated in [setup.py](../setup.py).   
   
## Examples: where to start <a name="Examples"></a>

QGL comes with a number of example jupyter notebook files that illustrate most of the basic
QGL programming concepts (in the QGL/doc directory):

* ex1_basic_QGL.ipynb: Basic setup of 'qubit' objects, defining sequences of pulses on qubits, 
and visualizing these pulse sequences.
* ex2_single_qubit_sequences.ipynb: Simple spectroscopy and coherence experiments on a single qubit.
* ex3_two_qubit_sequences.ipynb: Examples of two-qubit sequences, including CR gates.

Note that running _Ex1_ will generate a channel library database, _example.sqlite_. _Ex2_ and _Ex3_ rely on 
this database, so _Ex1_ must be run before _Ex2_ and _Ex3_. If the database schema changes, _example.sqlite_
must be regenerated. So, make sure to remove _example.sqlite_ whenever updating QGL versions. 

In addition to these example notebooks for manipulating qubits, `channel_libriary.ipynb` provides a 
basic Channel Library that is used by `ex2_single_qubit_sequences` and `ex3_two_qubit_sequences` 
example notebooks. 


## Channels and Qubits <a name="Channels-and-Qubits"></a>

Many quantum processors require non-uniform control parameters to achieve
high-fidelity gates across all qubits in the device. To support this need, QGL
provides a number of *channel* objects to store the *individual* parameters
needed to control or measure particular qubits.

Gates in QGL operate on resources known as `logical channels`. For control, these
channels are either `Qubits` or `Edges`. The `qubit` channels encode properties
specific to manipulating individual qubits in quantum processor, while `Edges`
encode the connectivity of the device. Since some 2-qubit gates have a preferred
directionality due to the physical parameters of the device, `edges` correspond
to a *directed* edge in the qubit connectivity graph. Qubit measurements instead
act upon a third `logical channel` type which is the `measurement` channel. A
final logical resource type is the `logical marker channel` which is used to carry
ancillary pulse information for things such as event triggers.

All `logical channels` are associated with `physical channels` through a Channel 
Library database in order for the QGL
compiler to produce pulse files for the target hardware. The setup of this
mapping is briefly described in the QGL example notebooks in this folder 
and a more detailed description is provide with the Auspex tools. 

While setup of these channels is important for final sequence compilation, QGL
programs typically refer only to `Qubit` channels. Actions on other channel
types may be implied by the operation. For example, to create a `Qubit` object
in QGL, one can write:
```
cl = ChannelLibrary(":memory:")
q1 = cl.new_qubit("q1")
```
where the Channel Library contains the "physical" information for the logical "qubit" 
channel. 

The `new_qubit` method returns a `Qubit` object with the properties defined
by the name `q1` if found in the channel library. If the name is not found, then
the users gets a `Qubit` object with the default properties.

## Gate Primitives <a name="Gate-Primitives"></a>

The underlying representation of all QGL operations is a `Pulse` object.
However, users are not expected to create `Pulses` directly, but instead
interact with various pre-defined one- and two-qubit primitives.



### Single-Qubit Operations

QGL provides the following single-qubit gates:
```
# generic rotation angle and phase
Utheta(q, angle, phase)

# generic rotations about a specific axis (phase)
Xtheta(q, angle)
Ytheta(q, angle)
Ztheta(q, angle)

# generic rotations of a specific angle
U(q, phase)
U90(q, phase)

# rotations of particular angle and phase
# X (phase = 0)
X(q)    # rotates by pi (180 degrees)
X90(q)  # rotates by +pi/2
X90m(q) # rotates by -pi/2

# Y (phase = pi/2)
Y(q)
Y90(q)
Y90m(q)

# just frame-updates
Z(q)
Z90(q)
Z90m(q)

# identity (delay or no-op)
Id(q, length) # length parameter is optional

# measurement
MEAS(q)
```

Due to the utility of Clifford-group operations in characterizing gate
performance, QGL also directly provides a primitive to implement the 24-element
single-qubit Clifford group:

```
# atomic Clifford operation on 1-qubit
AC(q, n)
```

This method is "atomic" because it implements the full 1-qubit Clifford group
with one pulse per element, as opposed to requiring a sequence of the primitives
already given above. We known of no canonical way to specify the elements of the
Clifford group; consequently, `AC` identifies which Clifford by a numerical
index (0-23). See the definition of `AC` in `PulsePrimitives.py` or the
definition of `C1` in `Cliffords.py` to find our enumeration of the group.

### Two-qubit Operations

QGL provides only one high-level two-qubit primitive, `CNOT`. The implementation
of CNOT may be chosen by specifying the `cnot_implementation` key in QGL's
[config.py](../QGL/config.py) file.

```python
# high-level primitives
CNOT(q1, q2)

# mid-level primitives
CNOT_simple(q1, q2) # a single-pulse gate on Edge(q1, q2)
CNOT_CR(q1, q2)     # an "echoed" cross-resonance CNOT gate on Edge(q1, q2)
ZX90_CR(q1, q2)     # a ZX90 on Edge(q1, q2) implemented with "echoed"
                    # cross-resonance pulses

# lowest-level primitives
echoCR(q1, q2)  # A "echoed" cross-resonance pulse
```

### Composite Pulses 

Occasionally one wants to construct a sequence of pulses and treat them as if
the entire sequence were a single pulse. For this, QGL allows pulses to be
joined with the `+` operator. This allows, for example, us to define
```
def hadamard(q):
    return Y90(q) + X(q)
```
and then use `hadamard(q)` just like any other pulse primitive, even though it is
composed of a sequence of two pulses.

### Additional Pulse Parameters

All QGL pulse primitives accept an arbitrary number of additional keyword
arguments. In particular, any QGL primitive accepts a `length` keyword to modify
the length of the resulting operation. These additional parameters are passed to
the [shape function](#pulse-shapes-and-waveforms) when the QGL compiler
constructs waveforms from `Pulse` objects.

## Sequences and Concurrent Operations <a name="Sequences-and-Concurrent-Operations"></a>

Programs in QGL are specified using python lists. For example,    
```seq = [[X90(q1), X(q1), Y(q1), X90(q1), MEAS(q1)]]```

The elements of the list provide a time-ordered sequence of pulses to execute.
Using the python list to describe sequences allows for the use of python's
powerful list comprehension syntax to describe sequence variations. For
instance, you can concisely write a scan over a rotation angle or delay in a
list comprehension such as:
```
seq = [[X90(q1), Id(q1, length=d), X90(q1), MEAS(q1)] for d in np.linspace(0, 10e-6, 11)]
```
QGL's compiler assumes that such lists of lists represent a series of related
experiments and schedules them to occur sequentially in the AWG output.

Users express concurrent operation in QGL using the `*` operator. For instance,
```
q1 = cl.new_qubit("q1")
q2 = cl.new_qubit("q2")
seq = [[X90(q1)*X90(q2), MEAS(q1)*MEAS(q2)]]
```

would execute the same sequence on `Qubit`s `q1` and `q2`. If the gate durations
differ between `q1` and `q2`, the QGL compiler injects delays to create aligned
`PulseBlock`s. By default, simultaneous pulses are "left-aligned", meaning that
the leading pulse edges are aligned and padding delays are injected on the
trailing edge. However, the user may change this behavior with the `align`
method:
```python
seq = [[align(X90(q1)*X90(q2)), align(MEAS(q1)*MEAS(q2), mode="right")][
```

`align` takes a `mode` argument ("left", "right", or default "center") to
specify a particular pulse alignment within a `PulseBlock`.


## Pulse Shapes and Waveforms <a name="Pulse-Shapes-and-Waveforms"></a>

The QGL compiler constructs waveforms to implement the desired quantum
operations. To do this, each pulse has a `shape_fun` (shape function) that is
called with its `shapeParams`. A number of commonly used shapes are defined in
the `PulseShapes` module including:

* `constant` - i.e. a "square" pulse with constant amplitude
* `tanh` - essentially a square pulse with rounded edges
* `gaussian` - a truncated Gaussian shape
* `drag` - the DRAG pulse gives a Gaussian shape with its derivative on the opposite quadrature.
* `gaussOn` - the first half of a truncated Gaussian shape
* `gaussOff` - the second half of a truncated Gaussian shape

The default pulse shape is determined by properties in the Channel
Library. However, the QGL programmer may
override the default shape with a keyword argument. For example, to force the
use of square pulse shape we may write:

```
seq = [[X(q1, shape_fun=PulseShapes.constant), MEAS(q1)]]
```

One common use case for specifying a shape function is in the construction of
composite pulses. For instance, you may want a square pulse shape with Gaussian
edges rather than those given by the `tanh` function. To do this you might write:
```python
seq = [[X(q1, shape_fun=PulseShapes.gaussOn) +\
       X(q1, shape_fun=PulseShapes.constant) +\
       X(q1, shape_fun=PulseShapes.gaussOff),
       MEAS(q1)]]
```

Shape functions can be an arbitrary piece of python code that returns a NumPy
array of complex values. Shape functions must accept **all** of their arguments
as keyword arguments. The only arguments that are guaranteed to exist are
`sampling_rate` and `length`. The pulse length is always assumed to be in units of
seconds; it is up to the shape function to use the passed sampling rate to
convert from time into number of points/samples. As an example, we could define
a ramp shape with
```
def ramp(length=0, sampling_rate=1e9, **kwargs):
    numPts = int(np.round(length * sampling_rate))
    return np.linspace(0, 1, numPts)
```

Then use it with any pulse primitive, e.g.:
```
seq = [[X(q1, shape_fun=ramp)]]
```

If your custom shape function requires additional arguments, you must either
arrange for these parameters to exist in the `LogicalChannel`'s `shapeParams`
dictionary, or pass them at the call site. For instance,
```
def foo(length=0, sampling_rate=1e9, bar=1, **kwargs):
    numPts = int(np.round(length * sampling_rate))
    # something involving bar...

seq = [[X(q1, bar=0.5, shape_fun=foo)]] # bar is passed as a keyword arg
```

See the `PulseShapes` module for further examples.

## Compiling and Plotting <a name="Compiling-and-Plotting"></a>

To compile the QGL gate and pulse primitives to waveform and 
AWG vendor-specific hardware instructions, use the
`compile_to_hardware()` method, e.g.:

```
seq = [[X90(q1), Id(q1, length=d), X90(q1), MEAS(q1)] for d in np.linspace(0, 10e-6, 11)]
meta_info = compile_to_hardware(seq, 'test/ramsey')
```

This code snippet will create a folder called `test` inside
[`AWGDir`] (if defined) or a temp directory and produce sequence files for each
AWG targeted by the `PhysicalChannels` associated with the QGL program. For
instance, if the `q1` channel targeted an AWG named `APS1` and the `M-q1`
channel targeted `APS2`, then the above call to `compile_to_hardware` would
produce two files: `ramsey-APS1.aps2` and `ramsey-APS2.aps2` in the `test` folder.
It would also produce a *meta information* file `ramsey-meta.json` which
contains data about the QGL program that may be useful for executing the
program in an instrument control platform such as
[Auspex](https://github.com/BBN-Q/Auspex). `compile_to_hardware` returns the
path to this "meta info" file.

The `plot_pulse_files()` creates a visual representation of the pulse sequence
created by a QGL program. For example,
```
plot_pulse_files(meta_info)
```
will create an interactive plot where each line represents a physical output
channel of an AWG referenced by the QGL program.

## Built-in Basic Sequences <a name="Built-in-Basic-Sequences"></a>

QGL provides many pre-defined methods for sequences commonly used to characterize a quantum device. These methods are defined in QGL's BasicSequences package and include:    
•	RabiAmp   
•	RabiWidth   
•	PulsedSpec   
•	InversionRecovery   
•	Ramsey   
•	HahnEcho   
•	CPMG   
•	SingleQubitRB   
•	TwoQubitRB   

Usage of each is defined in its respective doc string. For instance, at an ipython prompt, you may type
```?RabiAmp```
to learn about the RabiAmp function. This will return information on the function usage and return types 
as illustrated below:
```
Signature: RabiAmp(qubit, amps, phase=0, showPlot=False)
Docstring:
Variable amplitude Rabi nutation experiment.

Parameters
----------
qubit : logical channel to implement sequence (LogicalChannel)
amps : pulse amplitudes to sweep over (iterable)
phase : phase of the pulse (radians)
showPlot : whether to plot (boolean)

Returns
-------
plotHandle : handle to plot window to prevent destruction
File:      ~/Repos/QGL/QGL/BasicSequences/Rabi.py
Type:      function
```

We encourage users to peruse the methods defined in BasicSequences for templates that may be useful in writing their own QGL programs.

For additional information into QGL settings and compiler customizations (such as type of 2-qubit gate), please reveiw [config.py](../QGL/config.py). 

