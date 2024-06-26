#!/usr/bin/env python

import matplotlib
import matplotlib.pyplot as plt
import argparse
import acispy
from acispy.utils import state_labels
matplotlib.use("Qt5Agg")


def main():
    
    parser = argparse.ArgumentParser(description='Make plots of MSIDs and commanded states from the engineering archive')
    parser.add_argument("tstart", type=str, help='The start time in YYYY:DOY:HH:MM:SS format')
    parser.add_argument("tstop", type=str, help='The stop time in YYYY:DOY:HH:MM:SS format')
    parser.add_argument("plots", type=str, help="The MSIDs and states to plot, comma-separated")
    parser.add_argument("--one-panel", action='store_true', 
                        help="Whether to make a multi-panel plot or a single-panel plot. The latter is only valid if the quantities have the same units.")
    parser.add_argument("--maude", action="store_true", help="Use MAUDE to get telemetry data.")
    args = parser.parse_args()
    
    states = []
    msids = []
    
    for p in args.plots.split(','):
        if p in state_labels:
            states.append(p)
        else:
            msids.append(p)
    
    fields = [("msids", m) for m in msids] + [("states", s) for s in states]
    
    if len(msids) == 0:
        msids = None
    
    if args.maude:
        ds = acispy.MaudeData(args.tstart, args.tstop, msids)
    else:
        ds = acispy.EngArchiveData(args.tstart, args.tstop,
                                   msids, filter_bad=True)
    
    if args.one_panel:
        cp = acispy.DatePlot(ds, fields)
    else:
        cp = acispy.MultiDatePlot(ds, fields)
    cp.set_xlim(args.tstart, args.tstop)
    
    plt.show()


if __name__ == "__main__":
    main()