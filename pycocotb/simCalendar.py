from itertools import chain
from sortedcontainers.sorteddict import SortedDict
from typing import Tuple


class SimTimeSlot():
    """

    :note: write/read only is related
           to access to circuit from python code
    :note: event types
        * timeslot_begin
        * write_only     - w
        * "circuit eval() memory update detected"
        * comb_read      - r
        * comb_stable    - r
        * mem_stable     - r ("rest of circuit eval()")
        * timeslot_end   - r
    :note: if write_only is required in comb_stable or later error is rised
        if it called before the SimTimeSlot is evaluated from beginning
    """

    def __init__(self):
        self.timeslot_begin = None
        self.write_only = None
        self.comb_read = None
        self.comb_stable = None
        self.mem_stable = None
        self.timeslot_end = None


# internal
class SimCalendar(SortedDict):
    """
    Priority queue where key is time and priority
    """

    def push(self, time: int, value: SimTimeSlot):
        super(SimCalendar, self).__setitem__(time, value)

    def pop(self) -> Tuple[int, object]:
        item = super(SimCalendar, self).popitem(0)
        return item
