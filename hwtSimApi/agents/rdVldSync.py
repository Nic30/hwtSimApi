from collections import deque
from typing import Tuple

from hwtSimApi.agents.base import NOP, SyncAgentBase
from hwtSimApi.hdlSimulator import HdlSimulator
from hwtSimApi.process_utils import OnRisingCallbackLoop, OnFallingCallbackLoop
from hwtSimApi.triggers import WaitCombStable, WaitWriteOnly, WaitCombRead, \
    Timer


class DataRdVldAgent(SyncAgentBase):
    """
    Simulation/verification agent for handshaked interfaces
    interface there is onMonitorReady(simulator)
    and onDriverWriteAck(simulator) unimplemented method
    which can be used for interfaces with bi-directional data streams

    :note: 2-phase (xor) handshake

    :ivar presetBeforeClk: if this is driver set data and vld 1/4 clk period before clk tick (clk frequency must remain the same)
        (this is a debug feature which allows user to see what happens on clk tick better)
    """

    def __init__(self, sim: HdlSimulator, hwIO,
                 clk: "RtlSignal",
                 rst: Tuple["RtlSignal", bool],
                 presetBeforeClk=False):
        super(DataRdVldAgent, self).__init__(
            sim, hwIO, clk, rst)
        self.presetBeforeClk = presetBeforeClk
        self.actualData = NOP
        self.data = deque()

        # tmp variables to keep track of last send values to simulation
        self._lastWritten = None
        self._lastRd = None
        self._lastVld = None
        self._readyComnsummed = True
        # callbacks
        self._afterRead = None

    def setEnable_asDriver(self, en):
        super(DataRdVldAgent, self).setEnable_asDriver(en)
        if en:
            # pop new data if there are not any pending
            if self.actualData is NOP and self.data:
                self.actualData = self.data.popleft()

            doSend = self.actualData is not NOP
            if doSend:
                self.set_data(self.actualData)
            doSend = int(doSend)
            self.set_valid(doSend)
            self._lastVld = doSend
        else:
            self.set_valid(0)
            self.set_data(None)
            self._lastVld = 0

    def setEnable_asMonitor(self, en):
        super(DataRdVldAgent, self).setEnable_asMonitor(en)
        self.set_ready(int(en))
        self._lastRd = int(en)

    def get_ready(self) -> bool:
        """
        get value of "ready" signal
        """
        raise NotImplementedError("Implement this method to read ready signal on your interface")

    def set_ready(self, val: bool):
        raise NotImplementedError("Implement this method to write ready signal on your interface")

    def get_valid(self):
        """
        get value of "valid" signal, override e.g. when you
        need to use signal with reversed polarity
        """
        raise NotImplementedError("Implement this method to read valid signal on your interface")

    def set_valid(self, val):
        raise NotImplementedError("Implement this method to write valid signal on your interface")

    def get_data(self):
        """extract data from interface"""
        raise NotImplementedError("Implement this method to read data signals on your interface")

    def set_data(self, data):
        """write data to interface"""
        raise NotImplementedError("Implement this method to write data signals on your interface")

    def monitor(self):
        """
        Collect data from interface
        If onMonitorReady is present run it before setting ready and before data is read from the channel
        """
        start = self.sim.now
        yield WaitCombRead()
        if not self._enabled:
            return

        if self.notReset():
            yield WaitWriteOnly()
            if not self._enabled:
                return

            if self._readyComnsummed:
                # try to run onMonitorReady if there is any to preset value on signals potentially
                # going against main data flow of this channel
                onMonitorReady = getattr(self, "onMonitorReady", None)
                if onMonitorReady is not None:
                    onMonitorReady()
                self._readyComnsummed = False

            # update rd signal only if required
            if self._lastRd != 1:
                self.set_ready(1)
                self._lastRd = 1
            else:
                yield WaitCombRead()
                assert int(self.get_ready()) == self._lastRd, (
                    "Something changed the value of ready without notifying this agent"
                    " which is responsible for this",
                    self.sim.now, self.get_ready(), self._lastRd)

            if not self._enabled:
                return

            # wait for response of master
            yield WaitCombStable()
            if not self._enabled:
                return
            vld = self.get_valid()
            try:
                vld = int(vld)
            except ValueError:
                raise AssertionError(
                    self.sim.now, self.hwIO,
                    "vld signal is in invalid state")

            if vld:
                # master responded with positive ack, do read data
                d = self.get_data()
                if self._debugOutput is not None:
                    name = self.hwIO._getFullName()
                    self._debugOutput.write(
                        f"{name:s}, read, {self.sim.now:d}: {d}\n")
                self.data.append(d)
                if self._afterRead is not None:
                    self._afterRead()

                # data was read from th channel next ready bellongs to a different data chunk
                self._readyComnsummed = True
        else:
            self._readyComnsummed = True
            if self._lastRd != 0:
                yield WaitWriteOnly()
                # can not receive, say it to masters
                self.set_ready(0)
                self._lastRd = 0
            else:
                assert int(self.get_ready()) == self._lastRd

        assert start == self.sim.now

    def checkIfRdWillBeValid(self):
        yield WaitCombStable()
        rd = self.get_ready()
        try:
            rd = int(rd)
        except ValueError:
            raise AssertionError(self.sim.now, self.hwIO, "rd signal in invalid state")

    def _driverPreSetPriodically(self):
        sim = self.sim
        c = self.SELECTED_EDGE_CALLBACK
        period = self.clk._ag.period

        if c is OnRisingCallbackLoop:
            yield Timer(int(period // 4))
        elif c is OnFallingCallbackLoop:
            yield Timer(3 * int(period // 4))
        else:
            raise NotImplementedError(c)

        while True:
            yield WaitWriteOnly()
            sim._schedule_proc(sim.now, self.driverPreSet())
            yield Timer(period)

    def getDrivers(self):
        if self.presetBeforeClk:
            yield self._driverPreSetPriodically()
            self.driver = self.driverMarkDataSendOnClkTick
        yield from SyncAgentBase.getDrivers(self)
 
    def driverPreSet(self):
        """
        Set actual data and vld signal.
        """
        yield WaitWriteOnly()
        if not self._enabled:
            return
        # pop new data if there are not any pending
        if self.actualData is NOP and self.data:
            self.actualData = self.data.popleft()

        doSend = self.actualData is not NOP

        # update data on signals if it is required
        if self.actualData is not self._lastWritten:
            if doSend:
                data = self.actualData
            else:
                data = None
                if self._lastVld:
                    # forward set valid=0 to prevent spike right before clock edge
                    self.set_valid(0)
                    self._lastVld = 0

            self.set_data(data)
            self._lastWritten = self.actualData

        yield WaitCombRead()
        if not self._enabled:
            return
        en = self.notReset()
        vld = int(en and doSend)
        if self._lastVld is not vld:
            yield WaitWriteOnly()
            self.set_valid(vld)
            self._lastVld = vld

    def driverMarkDataSendOnClkTick(self):
        """
        Resolve monitor rd signal and if it was 1 pop next data
        """
        start = self.sim.now
        if not self._enabled:
            # we can not check rd it in this function because we can not wait
            # because we can be reactivated in this same time
            yield self.checkIfRdWillBeValid()
            return

        # wait for response of slave
        yield WaitCombStable()
        if not self._enabled:
            return
        rd = self.get_ready()
        try:
            rd = int(rd)
        except ValueError:
            raise AssertionError(
                self.sim.now, self.hwIO,
                "rd signal in invalid state") from None

        if not self._lastVld:
            assert start == self.sim.now
            return

        if rd:
            # slave did read data, take new one
            if self._debugOutput is not None:
                name = self.hwIO._getFullName()
                self._debugOutput.write(f"{name:s}, wrote, {self.sim.now:d}: {self.actualData}\n")

            a = self.actualData
            # pop new data, because actual was read by slave
            if self.data:
                self.actualData = self.data.popleft()
            else:
                self.actualData = NOP

            # try to run onDriverWriteAck if there is any
            onDriverWriteAck = getattr(self, "onDriverWriteAck", None)
            if onDriverWriteAck is not None:
                onDriverWriteAck()

            onDone = getattr(a, "onDone", None)
            if onDone is not None:
                onDone()

    def driver(self):
        """
        Push data to interface

        set vld high and wait on rd in high then pass new data
        """
        start = self.sim.now
        yield from self.driverPreSet()
        yield from self.driverMarkDataSendOnClkTick()
        assert start == self.sim.now
