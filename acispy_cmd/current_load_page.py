#!/usr/bin/env python

from datetime import datetime, timedelta, timezone
import os
import matplotlib
matplotlib.use("agg")
import acispy
from acispy.utils import cti_simodes, mylog
from acispy.thermal_models import short_name
import matplotlib.pyplot as plt
from cxotime import CxoTime
import argparse
import numpy as np
from Ska.Matplotlib import cxctime2plotdate
import bisect
import logging
from kadi.commands.states import decode_power, get_states, DEFAULT_STATE_KEYS
from kadi.commands import get_cmds
from kadi.events import load_segments, rad_zones, dsn_comms, scs107s
from pathlib import Path
import warnings
import astropy.units as u
import chandra_limits as cl


state_keys = DEFAULT_STATE_KEYS + ("hrc_15v", "hrc_24v", "hrc_i", "hrc_s",)

mylog.setLevel(logging.ERROR)

warnings.filterwarnings("ignore", "erfa")
warnings.filterwarnings("ignore", "redundantly")

chandra_models_path = Path(f"{os.environ['SKA']}/data/chandra_models/chandra_models/xija")

date2secs = lambda t: CxoTime(t).secs

header = '''
<?xml version="1.0" encoding="UTF-8">
<!DOCTYPE html PUBLIC "-//W3C/DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html lang="en" xml:lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="refresh" content="30" />
<title>Current ACIS Load Real-Time</title>
<link href="lr_web.css" rel="stylesheet" type="text/css">
</head>
<body text="#000000" bgcolor="#ffffff" link="#ff0000" vlink="#ffff22" alink="#7500FF">
<pre>
<h1><font face="times">Current ACIS Load Real-Time</font></h1>
<a name="review"><h2><font face="times">Load Commands</font></h2></a>'''

lr_web_css = """
commline {
    background-color: #26DDCC;
}
obsidline {
    background-color: pink;
}
padtime {
    background-color: yellow;
}
mechline {
    background-color: orange;
}
.scrollable-window {
    height: 600px;
    border: 2px solid #ccc;
    padding: 10px;
    overflow-y: auto;
    background-color: #f9f9f9;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    border-radius: 8px;
}
"""


script = '''
<script>
    function centerElement() {
      const container = document.getElementById("scrollableContainer");
      const targetElement = document.getElementById("now");

      // Calculate the position to center the target element in the scrollable window
      const offsetTop = targetElement.offsetTop - container.offsetTop;
      const containerHeight = container.clientHeight;
      const targetHeight = targetElement.clientHeight;

      // Adjust scrollTop to place the target element in the middle
      container.scrollTop = offsetTop - (containerHeight / 2) + (targetHeight / 2);
    }

    // Automatically center the element on page load
    document.addEventListener("DOMContentLoaded", centerElement);
</script>
'''

temps = ["fptemp_11", "1dpamzt", "1deamzt", "1pdeaat", "tmp_fep1_mong",
         "tmp_fep1_actel", "tmp_bep_pcb"]

plot_limits = {"fptemp_11": (-120.0, -95.0),
               "1deamzt": (5.0, 44.0),
               "1dpamzt": (5.0, 44.0),
               "1pdeaat": (15.0, 63.0),
               "tmp_fep1_mong": (-1.0, 55.0),
               "tmp_fep1_actel": (-1.0, 54.0),
               "tmp_bep_pcb": (5.0, 50.0)}


limit_classes = {
    "1deamzt": cl.DEALimit,
    "1dpamzt": cl.DPALimit,
    "1pdeaat": cl.PSMCLimit,
    "fptemp_11": cl.ACISFPLimit,
    "tmp_fep1_actel": cl.FEP1ActelLimit,
    "tmp_fep1_mong": cl.FEP1MongLimit,
    "tmp_bep_pcb": cl.BEPPCBLimit
}
                   
hi_red_limits = {"tmp_fep1_mong": 54.0,
                 "tmp_fep1_actel": 53.0,
                 "tmp_bep_pcb": 49.0}        
low_red_limits = {"tmp_fep1_mong": -10.0,
                  "tmp_fep1_actel": -10.0,
                  "tmp_bep_pcb": -10.0}


obsid_link_base = "https://cda.harvard.edu/chaser/startViewer.action"
mit_link_base = "http://acisweb.mit.edu/cgi-bin/get-atbls?tag="
lr_link_base = "http://cxc.cfa.harvard.edu/acis/lr_texts/%s/%s_lr.html"
tm_link_base = "http://cxc.cfa.harvard.edu/acis/Thermal/%s/%s.html"


def get_instr(simpos):
    if 104839 >= simpos >= 82109:
        instr = 'ACIS-I'
    elif 82108 >= simpos >= 60000:
        instr = 'ACIS-S'
    elif -20000 >= simpos >= -86147:
        instr = 'HRC-I'
    elif -86148 >= simpos >= -104362:
        instr = 'HRC-S'
    return instr


def detect_safing_actions(t):
    pass


def find_the_load(t):
    load_name = None
    load_time = None
    load_tstart = None
    ls = load_segments.filter(start=t-5*86400.0, stop=t+86400.0)
    try:
        if len(ls) > 0:
            for l in ls:
                if t > l.tstart:
                    load_name = l.load_name
                    load_time = l.start
                    load_tstart = l.tstart
                else:
                    break
    except:
        pass
    del ls
    s107s = scs107s.filter(start=t-5*86400.0, stop=t+86400.0)
    if load_tstart is not None:
        try:
            if len(s107s) > 0:
                for s in s107s:
                    if t > s.tstart and t > load_tstart:
                        load_name = "SCS-107"
                        load_time = s.start
                        load_scs = "107"
                    else:
                        break
        except:
            pass
        del s107s
    return load_name, load_time


def get_radzones(begin_time, last_time):
    try:
        radzones = list(rad_zones.filter(begin_time, last_time))
    except:
        radzones = []
    return radzones


def process_commands(now_time_utc, cmds):

    now_time_secs = CxoTime(now_time_utc).secs
    end_time_secs = now_time_secs + 86400.0
    start_time_secs = now_time_secs - 2.0*86400.0

    cmdlines = []
    cmdtimes = []
    simtrans = []

    in_science = False

    duration = None

    for cmd in cmds:

        the_time = CxoTime(cmd["date"]).secs

        if the_time < start_time_secs or the_time > end_time_secs:
            continue

        if cmd["type"] == "LOAD_EVENT":
            continue
        if cmd["type"] == "COMMAND_SW":
            if "msid" not in cmd["params"]:
                continue
            if "OORM" not in cmd["params"]["msid"] and "ETG" not in cmd["params"]["msid"]:
                continue
        if cmd["type"] == "COMMAND_HW" and "CSELFMT" not in cmd["tlmsid"]:
            continue
        if cmd["type"].startswith("MP_") and not cmd["type"].endswith("OBSID"):
            continue
        if cmd["type"] == "ORBPOINT":
            if "EF100" not in cmd["params"]["event_type"] and \
               "GEE" not in cmd["params"]["event_type"]:
                continue
        if cmd["type"] == "SIMFOCUS":
            continue

        highlight = None
        param = None

        if cmd["type"] == "ACISPKT":
            param = f"\t<a href=\"{mit_link_base}{cmd['tlmsid']}\" target=\"_blank\" rel=\"noopener noreferrer\"><font color=\"blue\">{cmd['tlmsid']}</font></a>"
            if cmd["tlmsid"].startswith("XCZ") or cmd["tlmsid"].startswith("XTZ"):
                in_science = True
                duration = the_time
            if cmd["tlmsid"].startswith("AA000") and in_science:
                in_science = False
                duration -= the_time
        elif cmd["type"] == "SIMTRANS":
            simpos = int(cmd["params"]['pos'])
            instr = get_instr(simpos)
            param = "%d  (%s)" % (simpos, instr)
            highlight = "<mechline>%s</mechline>"
            simtrans.append((cmd["date"], instr))
        elif cmd["type"] == "COMMAND_SW" and "ETG" in cmd["params"]["msid"]:
            param = cmd["params"]["msid"]
            highlight = "<mechline>%s</mechline>"
        elif cmd["type"] == "COMMAND_SW" and "OORM" in cmd["params"]["msid"]:
            # Assuming that this is radmon commanding
            param = cmd["params"]['msid']
            highlight = "<padtime>%s</padtime>"
        elif cmd["type"] == "COMMAND_HW":
            # Assuming that this is a format change
            param = cmd["tlmsid"]
        elif cmd["type"] == "MP_OBSID":
            param = cmd["params"]['id']
            highlight = "<obsidline>%s</obsidline>"
        elif cmd["type"] == "ORBPOINT":
            param = cmd["event_type"]
            
        line = f"{cmd['date']}\t{cmd['type']}\t{param}"

        if highlight is not None:
            # Pad lines so highlighting happens across the page
            if len(line) < 74:
                line += ' ' * (74 - len(line))
            line = highlight % line

        if cmd["type"] == "MP_OBSID":
            if param < 40000:
                line = line.replace(str(param),
                                    f"<a href=\"{obsid_link_base}?obsid={param}\" target=\"_blank\" rel=\"noopener noreferrer\"><font color=\"blue\">{param}</font></a>")

        cmdlines.append(line+"\n")
        cmdtimes.append(the_time)

        if duration is not None and not in_science:
            line = "==> ACIS integration time is %.2f ks.\n" % (-duration*1.0e-3)
            cmdlines.append(line)
            cmdtimes.append(the_time)
            duration = None

        if cmd["type"] == "ACISPKT" and (cmd["tlmsid"].startswith("WSPOW") or cmd["tlmsid"] == "WSVIDALLDN"):
            if cmd["tlmsid"].startswith("WSPOW"):
                pow_dict = decode_power(cmd["tlmsid"])
                if pow_dict["fep_count"] == 0:
                    feps = "All FEPs down"
                else:
                    feps = "FEPs: %s" % pow_dict["feps"]
                if pow_dict["ccd_count"] == 0:
                    vids = "All vids down"
                else:
                    vids = "CCDs: %s" % pow_dict["ccds"]
                outcome = "%s; %s" % (feps, vids)
            elif cmd["tlmsid"] == "WSVIDALLDN":
                outcome = "All vids down"
            line = f"==> WSPOW COMMAND LOADS: {outcome}\n"
            cmdlines.append(line)
            cmdtimes.append(the_time)

    return cmdtimes, cmdlines, simtrans


def find_cti_runs(states):
    cti_runs = []
    si_modes = states["si_mode"]
    power_cmds = states["power_cmd"]
    for mode in cti_simodes:
        where_mode = np.logical_and(si_modes == mode,
                                    power_cmds == "XTZ0000005")
        idxs = np.concatenate([[False], where_mode, [False]])
        idxs = np.flatnonzero(idxs[1:] != idxs[:-1]).reshape(-1, 2)
        for ii, jj in idxs:
            cti_runs += [si_modes.dates[0, ii], si_modes.dates[0, jj-1]]
    return cti_runs


def get_comms(start, stop):
    comm_times = []
    durations = []
    comms = dsn_comms.filter(start=start, stop=stop)
    for comm in comms:
        words = comm.start.split(":")
        words[2] = comm.bot[:2]
        words[3] = comm.bot[2:]
        comm_start = CxoTime(":".join(words))
        if comm_start.secs < comm.tstart:
            comm_start += 1 * u.day
        words = comm.stop.split(":")
        words[2] = comm.eot[:2]
        words[3] = comm.eot[2:]
        comm_stop = CxoTime(":".join(words))
        if comm_stop.secs > comm.tstop:
            comm_stop -= 1 * u.day
        comm_times.append([comm_start.yday, comm_stop.yday])
        durations.append((comm_stop - comm_start).to_value("min"))
    return comm_times, durations


def insert_comms(cmdtimes, cmdlines, comms, durations, tmin, tmax):
    for i, comm in enumerate(comms):
        tbegin = date2secs(comm[0])
        tend = date2secs(comm[1])
        if tbegin < tmin or tend > tmax:
            continue
        tbegin_loc = datetime.strptime(comm[0], "%Y:%j:%H:%M:%S.%f").replace(tzinfo=timezone.utc).astimezone(tz=None) 
        tend_loc = datetime.strptime(comm[1], "%Y:%j:%H:%M:%S.%f").replace(tzinfo=timezone.utc).astimezone(tz=None)
        idx = bisect.bisect_right(cmdtimes, tbegin)
        cmdtimes.insert(idx, tbegin)
        cmdlines.insert(idx, "<commline>%s   REAL-TIME COMM BEGINS   %s  ET              </commline>\n" % (comm[0], tbegin_loc.strftime("%Y:%j:%H:%M:%S")))
        idx = bisect.bisect_right(cmdtimes, tend)
        cmdtimes.insert(idx, tend)
        cmdlines.insert(idx, "<commline>%s   REAL-TIME COMM ENDS     %s  ET              </commline>\n" % (comm[1], tend_loc.strftime("%Y:%j:%H:%M:%S")))
        idx = bisect.bisect_right(cmdtimes, tend)
        cmdtimes.insert(idx, tend)
        cmdlines.insert(idx, "==> COMM DURATION:  %.2f mins.\n" % durations[i])


def insert_now_time(cmdtimes, cmdlines, now_time_secs, now_time_utc, now_time_local):
    new_line = '<a id="now" name="now"></a>NOW: %s (%s ET)' % (now_time_utc.strftime("%Y:%j:%H:%M:%S"),
                                                      now_time_local.strftime("%D %H:%M:%S"))
    new_line += ' ' * (100 - len(new_line))
    new_line = f'<font style="background-color:#5AC831"><b>{new_line}</b></font>\n'
    idx = bisect.bisect_right(cmdtimes, now_time_secs)
    cmdtimes.insert(idx, now_time_secs)
    cmdlines.insert(idx, new_line)


def add_annotations(dp, tmin, tmax, simtrans, comms, cti_runs, radzones):
    for tran in simtrans:
        dp.add_vline(tran[0], color='brown', ls='-')
        t = date2secs(tran[0])
        tdt = CxoTime(t + 1800.0).date
        if t < tmin or t+3600.0 > tmax:
            continue
        ymin, ymax = dp.ax.get_ylim()
        y = 0.25*ymin + 0.75*ymax
        dp.add_text(tdt, y, tran[1], fontsize=15,
                    rotation='vertical', color="brown", zorder=100)
    for cti_run in cti_runs:
        dp.add_vline(cti_run, color='darkgreen', ls='--')
    ybot, ytop = dp.ax.get_ylim()
    t = np.linspace(tmin, tmax, 1000)
    tplot = cxctime2plotdate(t)
    for radzone in radzones:
        in_evt = (t >= radzone.tstart) & (t <= radzone.tstop)
        dp.ax.fill_between(tplot, ybot, ytop, where=in_evt, 
                           color="mediumpurple", alpha=0.333333)
        dp.add_vline(radzone.perigee, color='dodgerblue', ls='--')
    for comm in comms:
        tc_start = date2secs(comm[0])
        tc_end = date2secs(comm[1])
        in_evt = (t >= tc_start) & (t <= tc_end)
        dp.ax.fill_between(tplot, ybot, ytop,
                           where=in_evt, color="pink", alpha=0.75)


class NowFinder:
    def __init__(self, start_now=None):
        self.start_now_real = datetime.utcnow()
        if start_now is None:
            start_now = self.start_now_real
        else:
            start_now = CxoTime(start_now).datetime
        self.start_now = start_now
        
    def get_now(self):
        return self.start_now + (datetime.utcnow() - self.start_now_real)

        
def main():

    parser = argparse.ArgumentParser(description='Run script for the "ACIS Current Load Real-Time" page.')
    parser.add_argument("--page_path", type=str, default="/data/wdocs/jzuhone/current_acis_load.html",
                        help='The file to write the page to.')
    parser.add_argument("--start_now")
    args = parser.parse_args()
    
    outfile = os.path.abspath(args.page_path)
    outdir = os.path.dirname(outfile)
    cssfile = os.path.join(outdir, "lr_web.css")
    
    ds_models = {}
    ds_tlm = None
    last_tl_ts = 0.0
    last_dea_tl_ts = 0.0
    old_load_name = ""
    reload = True
    cmds = None
    comms = None
    cti_runs = None
    radzones = None
    durations = None
    
    now_finder = NowFinder(start_now=args.start_now)

    run_start_time = now_finder.get_now()

    while (now_finder.get_now()-run_start_time).seconds < 21600.0:
    
        # Find the current time
        now_time_utc = now_finder.get_now()
        now_time_str = now_time_utc.strftime("%Y:%j:%H:%M:%S")
        now_time_secs = date2secs(now_time_str)
        now_time_local = now_time_utc.replace(tzinfo=timezone.utc).astimezone(tz=None)
    
        load_name, load_time = find_the_load(now_time_secs)
    
        if load_name is None:
            load_name = old_load_name
        elif load_name != "SCS-107":
            old_load_name = load_name
    
        load_year = "20%s" % load_name[-3:-1]
        lr_link = lr_link_base % (load_year, load_name)
        load_dir = load_name[:-1]
    
        begin_time = now_time_utc - timedelta(days=2)
        end_time = begin_time + timedelta(days=3)
        last_time = begin_time + timedelta(days=4)
        begin_time_str = begin_time.strftime("%Y:%j:%H:%M:%S")
        end_time_str = end_time.strftime("%Y:%j:%H:%M:%S")
        last_time_str = last_time.strftime("%Y:%j:%H:%M:%S")
        begin_time_secs = date2secs(begin_time_str)
        end_time_secs = date2secs(end_time_str)
    
        tl_ts = os.path.getmtime("/data/acis/eng_plots/acis_eng_10day.tl")
        dea_tl_ts = os.path.getmtime("/data/acis/eng_plots/acis_dea_10day.tl")
        if tl_ts != last_tl_ts or dea_tl_ts != last_dea_tl_ts or ds_tlm is None:
            try:
                ds_tlm = acispy.TenDayTracelogData(tbegin=now_time_secs-5.0*86400.0)
                last_tl_ts = tl_ts
                last_dea_tl_ts = dea_tl_ts
            except:
                pass
    
        if reload or cmds is None:
            cmds = get_cmds(begin_time_str, last_time_str)
            cmds.fetch_params()
            comms, durations = get_comms(begin_time_str, last_time_str)
            radzones = get_radzones(begin_time_str, last_time_str)
            model_start = now_time_secs - 4.0*86400.0
            model_end = now_time_secs + 4.0*86400.0
            states = get_states(model_start, model_end, state_keys=state_keys,
                                merge_identical=True).as_array()
            for temp in temps:
                if temp == "fptemp_11":
                    spec_filename = "acisfp_spec_matlab.json" 
                else:
                    spec_filename = f"{short_name[temp]}_spec.json"
                model_spec = chandra_models_path / short_name[temp] / spec_filename
                T_init = ds_tlm["msids", temp][model_start-700.0:model_start+700.0].value.mean()
                ds_models[temp] = acispy.ThermalModelRunner(temp, model_start, model_end,
                                                            states=states, T_init=T_init,
                                                            get_msids=False, model_spec=model_spec)
            cti_runs = find_cti_runs(ds_models["1dpamzt"].states)
            reload = False
            last_reload_time = now_time_secs
    
        last_reload_date = CxoTime(last_reload_time).date
        last_reload_loc = datetime.strptime(last_reload_date, "%Y:%j:%H:%M:%S.%f").replace(tzinfo=timezone.utc).astimezone(tz=None).strftime("%D %H:%M:%S")
    
        if load_name == "SCS-107":
            load_string = f"<font color=\"red\">SCS-107 detected at {load_time}.</font>"
        else:
            load_string = f"This is the <a href=\"{lr_link}\"><font style=\"color:blue\">{load_name}</font></a> load."
            
        outlines = [
            f"<font face=\"times\">{load_string}</font>\n",
            f"<font face=\"times\">The last data update was at {last_reload_date} ({last_reload_loc} ET).</font>\n",
            "<button onclick=\"centerElement()\">Reset to Current Time</button>"
        ]
            
        cmdtimes, cmdlines, simtrans = process_commands(now_time_utc, cmds)
        if comms is not None:
            insert_comms(cmdtimes, cmdlines, comms, durations, begin_time_secs, end_time_secs)
    
        insert_now_time(cmdtimes, cmdlines, now_time_secs, now_time_utc, now_time_local)
    
        outlines.append("<div class=\"scrollable-window\" id=\"scrollableContainer\">")
        outlines += cmdlines
        outlines += ["</div>", "</pre>"]
    
        for temp in temps:
            ds_m = ds_models[temp]
            if temp.startswith("tmp_"):
                dp = acispy.DatePlot(ds_tlm, ("msids", temp), field2="pitch", color="blue",
                                     figsize=(15, 10))
            else:
                dp = acispy.DatePlot(ds_m, ("model", temp), field2="pitch", color="red",
                                     figsize=(15, 10))
                acispy.DatePlot(ds_tlm, ("msids", temp), color="blue", plot=dp)
            dp.add_vline(now_time_str, lw=3)
            title_str = "%s\nCurrent %s prediction: %.2f $\mathrm{^\circ{C}}$\nCurrent pitch: %.2f degrees"
            title_str %= (now_time_str, temp.upper(), ds_m["model", temp][now_time_str].value,
                          ds_m["pitch"][now_time_str].value)
            title_str += "\nCurrent instrument: %s, Current ObsID: %d" % (ds_m["states", "instrument"][now_time_str],
                                                                          ds_m["states", "obsid"][now_time_str])

            if temp == "fptemp_11":
                spec_filename = "acisfp_spec_matlab.json"
            else:
                spec_filename = f"{short_name[temp]}_spec.json"
            model_spec = chandra_models_path / short_name[temp] / spec_filename
            limit_obj = limit_classes[temp](model_spec=model_spec)
            if temp == "fptemp_11":
                obs_list = cl.determine_obsid_info(states)
                limit_obj.set_obs_info(obs_list)
            upper_limit = limit_obj.get_limit_line(states)
            
            upper_limit.plot(
                fig_ax=(dp.fig, dp.ax),
                lw=3,
                zorder=2,
                use_colors=True,
                show_changes=False,
            )

            if temp == "fptemp_11":
                pass
            else:
                dp.add_hline(limit_obj.limits["yellow_hi"]["value"], color='gold')
                if "odb.warning.high" in limit_obj.limits:
                    dp.add_hline(limit_obj.limits["odb.warning.high"]["value"], color='r')
            if temp.startswith("tmp_"):
                lower_limit = limit_obj.get_limit_line(states, which="low")
                lower_limit.plot(
                    fig_ax=(dp.fig, dp.ax),
                    lw=3,
                    zorder=2,
                    use_colors=True,
                    show_changes=False,
                )
                dp.add_hline(limit_obj.limits["yellow_lo"]["value"], color='gold')
                dp.add_hline(hi_red_limits[temp], color='r')
                dp.add_hline(low_red_limits[temp], color='r')
            dp.set_title(title_str)
            dp.set_ylim(plot_limits[temp][0], plot_limits[temp][1])
            add_annotations(dp, begin_time_secs, end_time_secs, simtrans, comms, cti_runs, radzones)
            dp.set_xlim(begin_time_str, end_time_str)
            if temp == "fptemp_11":
                dp.annotate_obsids(-111.5, ywidth=1.0, color='dodgerblue',
                                   datestart=begin_time_str, datestop=end_time_str,
                                   txtheight=0.25, txtloc=0.1, fontsize=12)
            dp.fig.subplots_adjust(right=0.8)
            dp.savefig(os.path.join(outdir, "current_%s.png" % temp))
    
        w1, h1 = dp.fig.get_size_inches()
    
        ccd = acispy.DatePlot(ds_m, ["ccd_count", "fep_count"], ls=["-", "--"],
                              field2=("states", "simpos"), color=["blue"]*2, figsize=(15,8))
        ccd.add_vline(now_time_str, lw=3)
        title_str = "%s\nCurrent CCD count: %d, Current FEP count: %d\nCurrent SIM-Z: %g" % (now_time_str,
                                                                                             ds_m["ccd_count"][now_time_str].value,
                                                                                             ds_m["fep_count"][now_time_str].value, 
                                                                                             ds_m["states","simpos"][now_time_str].value)
        ccd.set_title(title_str)
        ccd.set_ylabel("CCD/FEP Count")
        add_annotations(ccd, begin_time_secs, end_time_secs, simtrans, comms, cti_runs, radzones)
        ccd.set_xlim(begin_time_str, end_time_str)
        ccd.set_ylim(0, 6.5)
    
        w2, h2 = ccd.fig.get_size_inches()
        lm = dp.fig.subplotpars.left*w1/w2
        rm = dp.fig.subplotpars.right*w1/w2
        ccd.fig.subplots_adjust(left=lm, right=rm)
        ccd.savefig(os.path.join(outdir, "current_ccd.png"))
    
        roll = acispy.DatePlot(ds_models["fptemp_11"], "off_nom_roll", field2="earth_solid_angle", 
                               color="blue", figsize=(15, 8))
        roll.add_vline(now_time_str, lw=3)
        title_str = "%s\nCurrent Off-nominal roll: %.2f degree\nEarth Solid Angle: %s sr" % (now_time_str,
            ds_models["fptemp_11"]["off_nom_roll"][now_time_str].value,
            ds_models["fptemp_11"]["earth_solid_angle"][now_time_str].value)
        roll.set_title(title_str)
        roll.set_ylim(-20.0, 20.0)
        roll.set_ylim2(1.0e-3, 1.0)
        add_annotations(roll, begin_time_secs, end_time_secs, simtrans, comms, cti_runs, radzones)
        roll.set_xlim(begin_time_str, end_time_str)
        roll.ax2.set_yscale("log")
        roll.set_ylabel2("Earth Solid Angle (sr)")
    
        w3, h3 = roll.fig.get_size_inches()
        lm = dp.fig.subplotpars.left*w1/w2
        rm = dp.fig.subplotpars.right*w1/w2
        roll.fig.subplots_adjust(left=lm, right=rm)
        roll.savefig(os.path.join(outdir, "current_roll.png"))
    
        plots = ["fptemp_11", "1dpamzt", "1deamzt", "1pdeaat", "ccd", "roll",
                 "tmp_fep1_mong", "tmp_fep1_actel", "tmp_bep_pcb"]
    
        plt.close("all")
    
        tm_link = tm_link_base % (load_year, load_dir)
        footer = ["<a name=\"plots\"><h2><font face=\"times\">Temperature Models</font></h2></a>"]
        if load_name != "SCS-107":
            footer.append("<a href=\"%s\"><font face=\"times\" color=\"blue\">Full thermal models for %s</font></a><p />" % (tm_link, load_name))
    
        for fig in plots:
            footer.append("<img src=\"current_%s.png\" />" % fig)
            footer.append("<p />")
        footer.append(script)
        footer.append("</body>")
        
        with open(outfile, "w") as f:
            f.write(header+"\n".join(outlines+footer))
    
        if not os.path.exists(cssfile):
            with open(cssfile, "w") as f:
                f.write(lr_web_css)
    
        if now_time_secs - last_reload_time > 600.0:
            reload = True
            

if __name__ == "__main__":
    main()