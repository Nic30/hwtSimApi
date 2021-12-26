from typing import Union

from hwtSimApi.constants import Time


def freq_to_period(f: Union[float, int]):
    return Time.s / f


def period_to_freq(t: Union[float, int]):
    return Time.s / float(t)
