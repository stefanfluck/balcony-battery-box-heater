# Heating stage control. No hardware access.


def failsafe_stage(cfg, t_rtc, prev=0):
    """Stage when both sensors are lost: FAILSAFE_STAGE, but only while the RTC chip (in
    the electronics enclosure) is cool, so a sensor failure in summer does not heat.
    Between FAILSAFE_RTC_ON and _OFF the previous stage stays. Without an RTC reading:
    FAILSAFE_STAGE."""
    if t_rtc is None or t_rtc <= cfg.FAILSAFE_RTC_ON:
        return cfg.FAILSAFE_STAGE
    if t_rtc >= cfg.FAILSAFE_RTC_OFF:
        return 0
    return prev


class Heating:
    """Two-stage control with hysteresis on both stages.

    stage 0: off, stage 1: primary pad, stage 2: both pads.
    Control temperature is the inside sensor, the outside sensor if the inside one
    is lost. If both are lost: FAILSAFE_STAGE, gated by the RTC chip temperature
    (source "rtc"), or without an RTC reading FAILSAFE_STAGE alone (source "failsafe").
    """

    def __init__(self, cfg, pads):
        self.cfg = cfg
        self.pads = pads  # indexes of enabled pads, e.g. [0, 1]
        self.stage = 0
        self.primary = pads[0] if pads else 0
        self.source = "in"

    def update(self, t_in, t_out, t_rtc=None):
        c = self.cfg
        if t_in is not None:
            t = t_in
            self.source = "in"
        elif t_out is not None:
            t = t_out
            self.source = "out"
        else:
            t = None
            self.source = "failsafe" if t_rtc is None else "rtc"

        prev = self.stage
        if t is None:
            stage = failsafe_stage(c, t_rtc, prev)
        elif t >= c.T_OFF:
            stage = 0
        elif t <= c.T_STAGE2_ON:
            stage = 2
        elif prev == 2 and t >= c.T_STAGE2_OFF:
            stage = 1
        elif prev == 0 and t <= c.T_STAGE1_ON:
            stage = 1
        else:
            stage = prev

        if stage == 1 and prev != 1 and c.ROTATE_PADS and len(self.pads) > 1:
            self.primary = self.pads[1] if self.primary == self.pads[0] else self.pads[0]
        self.stage = stage
        return self.relays()

    def relays(self):
        on = [False, False]
        if self.stage >= 1 and self.pads:
            on[self.primary] = True
        if self.stage >= 2:
            for p in self.pads:
                on[p] = True
        return on
