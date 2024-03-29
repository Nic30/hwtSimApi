# hwtSimApi

[![CircleCI](https://circleci.com/gh/Nic30/hwtSimApi.svg?style=svg)](https://circleci.com/gh/Nic30/hwtSimApi)
[![Coverage Status](https://coveralls.io/repos/github/Nic30/hwtSimApi/badge.svg?branch=master)](https://coveralls.io/github/Nic30/hwtSimApi?branch=master)
[![PyPI version](https://badge.fury.io/py/hwtSimApi.svg)](http://badge.fury.io/py/hwtSimApi)
[![Documentation Status](https://readthedocs.org/projects/hwtsimapi/badge/?version=latest)](http://hwtsimapi.readthedocs.io/en/latest/?badge=latest)

This library contains an implementation of DES (Discrete Event Simulation) for communication with RTL simulators and a backup RTL simulator written in python.
In addition there is a UVM like environment with some example interface agents.
This means that this library can be used to handle synchronization, data exchange and verification related staff.
The simulation is an object without any special requirements which greatly simplifies automatization and debugging.

* examples of usage in [hwtLib](https://github.com/Nic30/hwtLib) and other [HWT](https://github.com/Nic30/hwt) based projects

# Installation

* run `python3 setup.py install --user`
* or from git `git clone https://github.com/Nic30/hwtSimApi.git && cd hwtSimApi && python3 setup.py install --user`


# Similar software

* [cocotb](https://github.com/cocotb/cocotb) - there is also WIP version of cocotb-verilator integration
* [cocotb-coverage](https://github.com/mciepluc/cocotb-coverage) - Functional Coverage and Constrained Randomization Extensions for Cocotb
* [chisel-testers](https://github.com/freechipsproject/chisel-testers)
* [firesim](https://github.com/firesim/firesim)
* [fli](https://github.com/andrepool/fli) - using ModelSim Foreign Language Interface for c – VHDL
* [kratos](https://github.com/Kuree/kratos) - hardware generator/simulator
* [midas](https://github.com/ucb-bar/midas)
* [py-hpi](https://github.com/fvutils/py-hpi) - Python/Simulator integration using procedure calls
* [PyVSC](https://github.com/fvutils/pyvsc) Python package providing a library for Verification Stimulus and Coverage
* [uvm-python](https://github.com/tpoikela/uvm-python) - cocotb based python UVM
* [PySpice](https://github.com/FabriceSalvaire/PySpice) - Python binding for Ngspice / Xyce Simulators
* [pysv](https://github.com/Kuree/pysv) - Python binding to System Verilog using DPI

