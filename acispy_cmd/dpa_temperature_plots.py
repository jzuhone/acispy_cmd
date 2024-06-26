#!/usr/bin/env python

import matplotlib
matplotlib.use("agg")
matplotlib.rc("font", size=18, family="serif")
import acispy
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
from cxotime import CxoTime


def main():
    
    board_temps = ["tmp_bep_pcb", "tmp_bep_osc", "tmp_fep0_mong",
                   "tmp_fep0_pcb", "tmp_fep0_actel", "tmp_fep0_ram",
                   "tmp_fep0_fb", "tmp_fep1_mong", "tmp_fep1_pcb",
                   "tmp_fep1_actel", "tmp_fep1_ram", "tmp_fep1_fb"]
    
    tstop = CxoTime().secs
    tstart = tstop - 365.0*24.0*3600.0
    
    if len(sys.argv) > 1:
        outpath = sys.argv[1]
    else:
        outpath = os.getcwd()
    
    dc = acispy.EngArchiveData(tstart, tstop, ["1dpamzt", "ccsdstmf"]+board_temps, 
                               interpolate="nearest")
    
    unit_line = np.linspace(-10, 60, 200)
    
    colors = ["red", "orange", "green", "cyan", "blue", "violet", "brown"]
    limits = [44.0, 42.0, 48.0, 45.0, 47.0, 46.0, 43.0,
              49.0, 46.0, 48.0, 48.0, 43.0]
    
    dc.map_state_to_msid("fep_count", "1dpamzt")
    
    for j, msid in enumerate(board_temps):
        xx = dc["msids", "1dpamzt"].value
        yy = dc["msids", msid].value
        cc = dc["msids", "fep_count"].value
        fmt = dc["msids", "ccsdstmf"].value
        print(xx.size, yy.size, cc.size, fmt.size)
        print(dc["msids", msid].dates)
        print(dc["msids", "1dpamzt"].dates)
        fig = plt.figure(figsize=(36, 20))
        for i, n in enumerate(range(6, -1, -1)):
            ax = fig.add_subplot(241+i)
            fig.subplots_adjust(hspace=0.0, wspace=0.0)
            use = (cc == n) & (fmt == "FMT2")
            c = cc[use]
            x = xx[use]
            y = yy[use]
            ax.scatter(x, y, c=colors[i], linewidth=0.0, s=10.0, 
                       label="%d FEPs" % n)
            ax.plot(unit_line, unit_line, ls='--', lw=2, color='k')
            ax.axhline(limits[j], ls='dashed', color='gold', lw=3)
            ax.axvline(37.5, ls='dashed', color='gold', lw=3)
            ax.set_xlim(3, 47)
            ax.set_ylim(3, max(47, limits[j]+1))
            if i in [1, 2, 3, 5, 6]:
                ax.set_yticklabels([])
            if i in [3, 4, 5, 6]:
                ax.set_xlabel(r"1DPAMZT $\mathrm{(^{\circ}C)}$")
            if i in [0, 4]:
                ax.set_ylabel(r"%s $\mathrm{(^{\circ}C)}$" % msid.upper())
            ax.legend(loc=2)
        fig.suptitle("%s vs. 1DPAMZT\n%s - %s" % (msid.upper(),
                                                  CxoTime(tstart).date,
                                                  CxoTime(tstop).date),
                     y=0.94, fontsize=30)
        filename = os.path.join(outpath, "%s_scatter.png" % msid)
        fig.savefig(filename, bbox_inches='tight', dpi=50)


if __name__ == "__main__":
    main()