# Heating stage control. No hardware access.


class Heating:
    """Two-stage control with hysteresis on both stages.

    stage 0: off, stage 1: primary pad, stage 2: both pads.
    Control temperature is the inside sensor, the outside sensor if the inside one
    is lost, and FAILSAFE_STAGE if both are lost.
    """

    def __init__(self, cfg, pads):
        self.cfg = cfg
        self.pads = pads  # indexes of enabled pads, e.g. [0, 1]
        self.stage = 0
        self.primary = pads[0] if pads else 0
        self.source = "in"

    def update(self, t_in, t_out):
        c = self.cfg
        if t_in is not None:
            t = t_in
            self.source = "in"
        elif t_out is not None:
            t = t_out
            self.source = "out"
        else:
            t = None
            self.source = "failsafe"

        prev = self.stage
        if t is None:
            stage = c.FAILSAFE_STAGE
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
