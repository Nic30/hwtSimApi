from hwtSimApi.basic_hdl_simulator.io import BasicRtlSimIo


class BasicRtlSimModel(object):
    """
    Base class for model in simulator
    """

    def __init__(self, sim, name=None):
        self.sim = sim
        self._name = name
        self.io = BasicRtlSimIo()
        self._hwIOs = []
        self._processes = []
        self._subHwModules = []
        self._outputs = {}

    def _init_body(self):
        """
        This method is used to initializes all containers on this object
        after signals are connected
        """
        pass
