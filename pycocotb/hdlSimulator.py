"""
Pitfalls of delta-step based HDL simulators

* HDL simulator
    * manages communication between the RTL simulator and the simulation environment
* RTL simulator
    * simulates the circuit itself

* Simulation environment (=simulator).
    * HDL simulator + RTL simulator + user specified sim. processes
* User specified processes
    * Can read all signals in RTL simulator
    * Can write and wait for event only on top level signals.
    * Can preinitialize values of signals. (e.g. initialize memories before simulation start)

* Problem is how to ensure correct order of operations in RTL simulator
  in user specified processes which are controlling RTL simulator
  while keeping simulation simple and fast.

    * Requirements of UVM like interface agents.

        * Agents needs to be able to:

            * Perform combinational loop (e.g. tristate pull-up in I2C)

            * Wait for (before and after) edge of clock signal (e.g. BRAM port)

                * Clock signal can be driven directly by sim.
                  If this is a case synchronization is simple because simulator
                  and user knows when the event happens (before call delta step).

                * If clock signal is generated by circuit it is problematic because
                  value of clock signal is updated in simulation step together
                  with another signal updates. This can result in incorrect
                  event order and special care is required.

            * Perform combinational loop for clock signals.

                * Value has to be updated in same step.

                    * This practically means that the event can appear on multiple signals
                      at once.

        * Agent is full description of interface protocol and should be universal
          and extensible.

    * Combinational loops between simulator and RTL simulator.

        * If only one signal is updated per delta step there is no problem.

        * However if multiple signals signals (especially clock signals)
          are updated in same delta step combinational loop does not
          have to be resolved before some event dependent (e.g. FF) update
          This results in invalid resolution.

            * Updates of combinational logic has to be resolved before update
              of memory elements and dependent logic.

    * Clock generated by RTL simulator.

        * This is problem for non-pure DES simulators like Verilator.

        * Output signals from RTL simulator does not have to have
          values which they have when clock event was triggered, solution:


            * Manually add registers in to circuit to hold correct value.

            * Run simulation process which waits on event on specified signal
              exactly in time of the event. Problem is that in this state some
              values can be undefined and read only access is required.
"""

from inspect import isgenerator
from typing import List

from pycocotb.simCalendar import SimTimeSlot, SimCalendar, DONE
from pycocotb.triggers import Event, raise_StopSimulation, \
    StopSimumulation, Action


# similar to https://github.com/potentialventures/cocotb/blob/master/cocotb/scheduler.py
class HdlSimulator():
    """
    This simulator simulates the communication between circuit simulator
    and simulation processes which are driving the circuit simulation.
    Simulation processes are usually provided by simulation agents or user.

    :ivar now: actual simulation time
    :ivar _events: heap of simulation events and processes
    :ivar rtl_simulator: circuit simulator used for simulation of circuit itself
    """

    def __init__(self, rtl_simulator):
        self.rtl_simulator = rtl_simulator
        self.now = 0
        self._events = SimCalendar()
        self._current_time_slot = None  # type: SimTimeSlot
        self._current_event_list = None  # type: List

        schedule = self._events.push

        # def schedule(*args):
        #     assert self.now <= args[0]
        #     print(self.now, "sched:", *args)
        #     self._events.push(*args)
        #
        self.schedule = schedule

    def _run_process(self, process):
        """
        Execute process and process it's requests
        """
        # run process or activate processes dependent on Event
        for ev in process:
            # if process requires waiting put it back in queue
            if isinstance(ev, Action):
                if not ev.applyProcess(self, process):
                    break
            elif isinstance(ev, Event):
                ev.applyProcess(self, process)
                break
            elif isgenerator(ev):
                # else this process spotted new process
                # and it has to be put in queue
                self._schedule_proc_now(ev)
            else:
                raise ValueError(ev)

    def _eval_rtl_events(self):
        """
        Run processes/events triggered by RTL simulator
        """
        rtl_sim = self.rtl_simulator
        rtl_pending_event_list = rtl_sim.pending_event_list
        if rtl_pending_event_list:
            # proper solution is to put triggered events to sim.
            # calendar with urgent priority  but we evaluate
            # it directly because of performance
            for _process in rtl_pending_event_list:
                if not isgenerator(_process):
                    _process = _process(self)

                self._run_process(_process)
            rtl_pending_event_list.clear()

    def _run_event_list(self, events):
        """
        Run block of events or processes
        """
        if events is not None:
            self._current_event_list = events
            for ev in events:
                # process is Python generator or Event
                if isinstance(ev, Event):
                    for p in ev:
                        self._run_process(p)
                else:
                    self._run_process(ev)

        self._current_event_list = None

    def run(self, until: int, extraProcesses=[]) -> None:
        """
        Run simulation for a specified time

        :note: Can be used to run simulation again after it ends from time when it ends.
        :note: Simulator restart is performed by new instantiation of the simulator.
        """

        assert until >= self.now, (until, self.now)
        if until == self.now:
            return

        now = self.now
        time_slot = SimTimeSlot()
        time_slot.write_only = []
        for proc in extraProcesses:
            assert isgenerator(proc), proc
            time_slot.write_only.append(proc)
        # add handle to stop simulation
        self.schedule(now, time_slot)

        end_time_slot = SimTimeSlot()
        end_time_slot.write_only = [raise_StopSimulation(self), ]
        self.schedule(now + until, end_time_slot)

        next_time_slot = self._events.pop
        rtl_sim = self.rtl_simulator
        _run_event_list = self._run_event_list
        END = rtl_sim.END_OF_STEP
        try:
            # for all events
            while True:
                now, time_slot = next_time_slot()
                self._current_time_slot = time_slot
                assert now >= self.now, (now, time_slot)
                rtl_sim.time = self.now = now

                # run preinitialization of sim. environment
                _run_event_list(time_slot.timeslot_begin)
                time_slot.timeslot_begin = DONE

                # run resolution of combinational lopps
                first_run = True
                while first_run or time_slot.write_only:
                    _run_event_list(time_slot.write_only)
                    time_slot.write_only = None
                    s = rtl_sim.eval()

                    assert s == rtl_sim.COMB_UPDATE_DONE, (self.now, s)
                    if time_slot.comb_read is None:
                        self._current_event_list = time_slot.comb_read = []
                    else:
                        self._current_event_list = time_slot.comb_read
                    self._eval_rtl_events()

                    _run_event_list(time_slot.comb_read)
                    time_slot.comb_read = None

                    if time_slot.write_only is not None:
                        # we have to reevaluate the combinational logic
                        # if write in this time stamp is required
                        rtl_sim.reset_eval()
                    first_run = False

                time_slot.write_only = DONE
                time_slot.comb_read = DONE

                # run evaluation of rest of the circuit
                while not rtl_sim.read_only_not_write_only:
                    rtl_sim.eval()
                    if rtl_sim.pending_event_list:
                        if time_slot.comb_read is None:
                            self._current_event_list = time_slot.comb_stable = []
                        else:
                            self._current_event_list = time_slot.comb_stable
                        self._eval_rtl_events()

                _run_event_list(time_slot.comb_stable)
                time_slot.comb_stable = DONE

                while True:
                    ret = rtl_sim.eval()
                    if rtl_sim.pending_event_list:
                        if time_slot.mem_stable is None:
                            self._current_event_list = time_slot.mem_stable = []
                        else:
                            self._current_event_list = time_slot.mem_stable
                        self._eval_rtl_events()
                    if ret == END:
                        break
                _run_event_list(time_slot.mem_stable)
                time_slot.mem_stable = DONE

                _run_event_list(time_slot.timeslot_end)
                time_slot.timeslot_end = DONE
                rtl_sim.set_write_only()

        except StopSimumulation:
            pass
        finally:
            rtl_sim.finalize()
        # to allow tesbenches to peek in to DUT after sim ended
        rtl_sim.read_only_not_write_only = True

    def _schedule_proc_now(self, ev):
        assert isinstance(ev, (Action, Event)) or isgenerator(ev), ev
        self._current_event_list.append(ev)

    def _schedule_proc(self, time: int, ev) -> None:
        assert isinstance(ev, (Action, Event)) or isgenerator(ev), ev
        if self.now == time:
            self._current_event_list.append(ev)
        else:
            try:
                ts = self._events[time]
            except KeyError:
                ts = SimTimeSlot()
                self.schedule(time, ts)
            if ts.write_only is None:
                ts.write_only = []
            ts.write_only.append(ev)
