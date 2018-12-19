"""
Pitfalls of delta-step based HDL simulators

* Situation
    * RTL simulator which simulates behavior of circuit step by step
    * Simulation environment (=simulator) composed of user specified processes.
        * Simulator can read all signals in RTL simulator
        * Simulator can write and wait for event only on top level signals.

* Problem is how to ensure correct order of operations in RTL simulator
  and in user specified processes which are controlling RTL simulator
  while keeping simulation simple.

    * Requirements of UVM like interface agents.

        * Agents need to be able:

            * Perform combinational loop (e.g. tristate pull-up in I2C)

            * Wait for (before and after) edge of clock signal (e.g. BRAM port)

                * Clock signal can be driven directly by sim.
                  If this is a case synchronization is simple because simulator
                  and user knows when the event happens (before call delta step).

                * If clock signal is generated by circuit it is problematic because
                  value of clock signal is updated in simulation step together
                  with another signal updates. This can result in incorrect
                  event order and special care is required.

                * After clock event is used to signalize that clock cycle
                  has passed and state of interface and it's agent can be updated.
                  This event is triggered on the end of delta step
                  as it can be triggered only once per delta step.

        * Agent is full description of interface protocol and should be universal
          and extensible.

    * Combinational loops between simulator and RTL simulator.

        * If only one signal is updated per delta step there is no problem.

        * However if multiple signals signals (especially clock signals)
          are updated in same delta step combinational loop does not
          have to be resolved before some event dependent (e.g. FF) update
          This results in invalid resolution.

            * Updates of combinational logic has to be resolved before update
              of sequential logic.

    * Clock generated by RTL simulator.

        * Output signals from RTL simulator does not have to have
          values which they have when clock event was triggered, solution:

            * Manually add registers in to circuit to hold correct value.

            * Run simulation process which waits on event on specified signal
              exactly in time of the event. Problem is that in this state some
              values can be undefined and read only access is required.

# Simulator delta step:

* (Event names written in capital)

def delta_step():
    * PRESET - write only
    * RTL simulator eval() call
        * combinational update                     -|
        * COMB_UPDATE - read only                   | Care for comb. loops
        * COMB_REWRITE - write only                 | in sim. agents
        * rerun eval() if write was used            |
        * COMB_STABLE - read only                  -|
        * check for event on signals driven by sim -| Care for sim. driven events
        * for each clock signal:
            * BEFORE_EDGE(clk) - read only                  -| Care for clock
            * for each start of evaluation                   | dependent agents
              of event dependent code                        | where clock is generated
              (clock sig. updated but none of the registers)-| from circuit
    * END_OF_STEP - read only                    -| Final state resolution

# Run of the simulator:

* eval_init()
* END_OF_STEP - read only
* while True:
    * delta_step()
"""

from heapq import heappush, heappop
from typing import Tuple

from pycocotb.triggers import Event, raise_StopSimulation, Timer, \
    StopSimumulation, PRIORITY_URGENT, PRIORITY_NORMAL, ReadOnly, \
    WriteOnly, WriteClkOnly
from inspect import isgenerator


# [TODO] use c++ red-black tree
# internal
class CalendarItem():

    def __init__(self, time: int, sub_step: int, priority: int, value):
        """
        :param time: time when this event this list of event should be evoked
        :param sub_step: index of delta step in this time
            (there is read/write phase cycle to settle values down)
        :param priority: priority as described in this file
        """
        self.key = (time, sub_step, priority)
        self.value = value

    def __lt__(self, other):
        return self.key < other.key


# internal
class SimCalendar():
    """
    Priority queue where key is time and priority
    """

    def __init__(self):
        self._q = []

    def push(self, time: int, step_no: int, priority: int, value):
        item = CalendarItem(time, step_no, priority, value)
        heappush(self._q, item)

    def pop(self) -> Tuple[int, int, int, object]:
        item = heappop(self._q)
        return (*item.key, item.value)


# similar to https://github.com/potentialventures/cocotb/blob/master/cocotb/scheduler.py
class HdlSimulator():
    """
    This simulator simulates the communication between circuit simulator
    and simulation processes which are driving the simulation.
    Simulation processes are usually provided by simulation agents or user.

    .. note: *Delta steps*
        Delta step is minimum quantum of changes in simulation.

    :ivar now: actual simulation time
    :ivar _events: heap of simulation events and processes
    :ivar rtl_simulator: circuit simulator used for simulation of circuit itself
    """

    def __init__(self, rtl_simulator):
        super(HdlSimulator, self).__init__()
        self.rtl_simulator = rtl_simulator
        self.now = 0

        # container of outputs for every process
        self._events = SimCalendar()

    # internal
    def _add_process(self, proc, priority) -> None:
        """
        Schedule process on actual time with specified priority
        """
        self._events.push(self.now, priority, proc)

    def _run_process(self, process, now, step_no, priority, schedule):
        # run process or activate processes dependent on Event
        while True:
            try:
                # print(now, process)
                ev = next(process)
            except StopIteration:
                break

            # if process requires waiting put it back in queue
            if isinstance(ev, Timer):
                # put process to sleep as required by Timer event
                schedule(now + ev.time, 0, priority, process)
                break
            elif isinstance(ev, Event):
                # process going to wait for event
                # if ev.process_to_wake is None event was already
                # destroyed
                ev.process_to_wake.append(process)
                break
            elif isgenerator(ev):
                # else this process spotted new process
                # and it has to be put in queue
                schedule(now, priority, ev)
            else:
                # process is going to wait on different simulation step
                p = ev.PRIORITY
                if p == priority:
                    continue
                elif priority < p:
                    step_no += 1

                schedule(now, step_no, ev.PRIORITY, process)
                break

    def run(self, until: float, extraProcesses=[]) -> None:
        """
        Run simulation for a specified time

        :note: Can be used to run simulation again after it ends from time when it ends.
        :note: Simulator restart is performed by new instantiation of the simulator.
        """
        add_proc = self.add_process
        for p in extraProcesses:
            add_proc(p(self))

        assert until >= self.now, (until, self.now)
        if until == self.now:
            return

        events = self._events

        schedule = events.push
        # def schedule(*args):
        #     print("sched:", *args)
        #     events.push(*args)

        next_event = events.pop

        # add handle to stop simulation
        now, step_no, priority = (self.now, 0, ReadOnly.PRIORITY)
        schedule(now + until, 0, PRIORITY_URGENT, raise_StopSimulation(self))

        rtl_sim = self.rtl_simulator
        rtl_pending_event_list = rtl_sim.pending_event_list
        try:
            # for all events
            while True:
                now, step_no, priority, process = next_event()
                eval_circuit = now > self.now or priority == WriteOnly.PRIORITY or priority == WriteClkOnly.PRIORITY  # [TODO]
                if eval_circuit:
                    while True:
                        # use while because we are resolving combinational loops
                        # between event callbacks and rtl_simulator
                        # print("eval", self.now)
                        rtl_sim.eval()
                        for _process in rtl_pending_event_list:
                            if not isgenerator(_process):
                                _process = _process(self)

                            self._run_process(_process, self.now, 0, PRIORITY_NORMAL, schedule)

                        if not rtl_pending_event_list:
                            break  # no callback triggered another callback

                        rtl_pending_event_list.clear()

                rtl_sim.time = self.now = now

                # process is Python generator or Event
                if isinstance(process, Event):
                    process = iter(process)

                self._run_process(process, now, step_no, priority, schedule)

        except StopSimumulation:
            return

    def add_process(self, proc) -> None:
        """
        Add process to events with default priority on current time
        """
        self._events.push(self.now, 0, PRIORITY_NORMAL, proc)

