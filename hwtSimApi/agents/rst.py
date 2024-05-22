from hwtSimApi.agents.base import AgentBase
from hwtSimApi.constants import CLK_PERIOD
from hwtSimApi.hdlSimulator import HdlSimulator
from hwtSimApi.triggers import Timer, WaitWriteOnly


class PullUpAgent(AgentBase):
    """
    After specified time value of the signal is set to 1
    :note: usually used for negated reset
    """

    def __init__(self, sim: HdlSimulator, hwIO: "RtlSignal", initDelay=int(0.6 * CLK_PERIOD)):
        super(PullUpAgent, self).__init__(sim, hwIO)
        assert isinstance(initDelay, int)
        self.initDelay = initDelay
        self.data = []

    def driver(self):
        sig = self.hwIO
        yield WaitWriteOnly()
        sig.write(0)
        yield Timer(self.initDelay)
        yield WaitWriteOnly()
        sig.write(1)


class PullDownAgent(AgentBase):
    """
    After specified time value of the signal is set to 0
    :note: usually used for reset
    """

    def __init__(self, sim: HdlSimulator, hwIO: "RtlSignal", initDelay=int(0.6 * CLK_PERIOD)):
        super(PullDownAgent, self).__init__(sim, hwIO)
        assert isinstance(initDelay, int)
        self.initDelay = initDelay
        self.data = []

    def driver(self):
        sig = self.hwIO
        yield WaitWriteOnly()
        sig.write(1)
        yield Timer(self.initDelay)
        yield WaitWriteOnly()
        sig.write(0)
