#!/usr/bin/env python

import matplotlib
import matplotlib.pyplot as plt
import argparse
import acispy
from acispy.utils import state_labels
matplotlib.use("Qt5Agg")


def main():
    
    parser = argparse.ArgumentParser(description='Make plots of MSIDs from a tracelog file. Commanded states will be loaded from the commanded states database.')
    parser.add_argument("tracelog", type=str, help='The tracelog file to load the MSIDs from')
    parser.add_argument("plots", type=str, help='The MSIDs and states to plot, comma-separated')
    parser.add_argument("--one-panel", action='store_true',
                        help="Whether to make a multi-panel plot or a single-panel plot. The latter is only valid if the quantities have the same units.")
    args = parser.parse_args()
    
    states = []
    msids = []
    
    for p in args.plots.split(','):
        if p in state_labels:
            states.append(p)
        else:
            msids.append(p)
    
    fields = [("msids", m) for m in msids] + [("states", s) for s in states]
    
    ds = acispy.TracelogData(args.tracelog)
    if args.one_panel:
        cp = acispy.DatePlot(ds, fields)
    else:
        cp = acispy.MultiDatePlot(ds, fields)
    
    plt.show()


if __name__ == "__main__":
    main()