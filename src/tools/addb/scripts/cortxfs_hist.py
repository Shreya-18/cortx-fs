#
# Copyright (c) 2020 Seagate Technology LLC and/or its Affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# For any questions about this software or licensing,
# please email opensource@seagate.com or cortx-questions@seagate.com.
#

import argparse
import sys
from peewee import SqliteDatabase
from matplotlib import pyplot as plt
import numpy as np

DB      = SqliteDatabase(None)
BLOCK   = 16<<10
PROC_NR = 48
DBBATCH = 95
PID     = 0
rec_limit = -1
start_opid = 0
timesort = "NA"

def db_init(path):
    DB.init(path, pragmas={
        'journal_mode': 'memory',
        'cache_size': -1024*1024*256,
        'synchronous': 'off',
    })

def db_connect():
    DB.connect()

def db_close():
    DB.close()

def gen_perfc_op_hist_graph(fn_tag: str="fsal_read", op_file: str="cortxfs_perfc_graph"):
    xvals_opids=[]
    yvals_time=[]
    xmax = 0
    ymax = 0

    with DB.atomic():
        if rec_limit != -1:
            cursor = DB.execute_sql(f"SELECT DISTINCT opid from entity_states WHERE fn_tag LIKE \"{fn_tag}\" AND opid >= {start_opid} ORDER BY id ASC LIMIT {rec_limit}")
        else:
            cursor = DB.execute_sql(f"SELECT DISTINCT opid from entity_states WHERE fn_tag LIKE \"{fn_tag}\" ORDER BY id ASC")
        field_opids = list(cursor.fetchall())
    label_opids = ("o");
    opids = [dict(zip(label_opids, f)) for f in field_opids]

    if opids == []:
        print ("Could not find enough details in db for {0}", format(fn_tag))
        return

    for opid in opids:
        with DB.atomic():
            cursor = DB.execute_sql(f"SELECT * from entity_states WHERE opid = {opid['o']}")
            field_states = list(cursor.fetchall())
        label_states = ("id", "pid", "time", "tsdb_mod", "fn_tag", "entity_type", "opid", "state_type");
        states = [dict(zip(label_states, f)) for f in field_states]
        t0 = -1
        t1 = -1
        for state in states:
            if state['state_type'] in "finish":
                t1 = state['time']
            if state['state_type'] in "init":
                t0 = state['time']
        if t0 == -1 or t1 == -1:
            print (f"incomplete states, discarding this sample, {states}")
        else:
            time_diff = t1 - t0
            # print (f"opid {opid['o']} took {time_diff} us to complete")
            xvals_opids.append(opid['o'])
            yvals_time.append(time_diff)
            if xmax < opid['o']:
                xmax = opid['o']
            if ymax < time_diff:
                ymax = time_diff

    if timesort in "YES":
        opid_time = dict(zip(xvals_opids, yvals_time))
        opid_time1 = dict(sorted(opid_time.items(), key=lambda x: x[1]))
        xvals_opids = list(opid_time1.keys())
        yvals_time = list(opid_time1.values())

    x = np.arange(len(xvals_opids))  # the label locations
    width = 0.35  # the width of the bars

    fig, ax = plt.subplots()
    rects1 = ax.bar(x + width/2, yvals_time, width, label='execution_time')
    plt.title(f"{fn_tag} \n time")
    plt.xlabel(f"{fn_tag} opid(s)")
    plt.ylabel("time (us)")
    ax.set_xticks(x)
    ax.set_xticklabels(xvals_opids, rotation=90, ha='center', size=3)
    ax.set_yticklabels(yvals_time, rotation=90, ha='left', size=3)
    ax.legend()

    def autolabel(rects, yvals_time):
        """Attach a text label above each bar in *rects*, displaying its height."""
        idx = 0
        for rect in rects:
            height = rect.get_height()
            text = ax.annotate(str(yvals_time[idx]).format(height),
            xy=(rect.get_x() + rect.get_width() / 2, height),
            xytext=(0, -30),  # 3 points vertical offset
            textcoords="offset points",
            ha='center', va='bottom')
            idx=idx+1
            text.set_rotation(90)
            text.set_fontsize(3)

    autolabel(rects1, yvals_time)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.2)
    plt.savefig(fname=op_file, format="svg")
    print (f"Histogram graph render completed for operation {fn_tag}")

    return


def parse_args():
    parser = argparse.ArgumentParser(prog=sys.argv[0], description="""
    cortxfs_hist.py: Display histogram graph of a provided cortxfs function.
    """)
    parser.add_argument("-d", "--db", type=str, default="cortxfs_perfc.db",
                        help="Performance database (cortxfs_perfc.db)")
    parser.add_argument("fn_tag", type=str, help="A valid fn_tag from CORTXFS stack which is enabled for performance profiling")
    parser.add_argument("-l", "--rec_limit", type=str, default="10", help="How many max opids to be shown in a single graph, use 'NA' to specify no limit")
    parser.add_argument("-so", "--start_opid", type=str, default="0", help="Along with limit, from which opid the graph needs to be generated. Default is 0 to show from the start")
    parser.add_argument("-sort-by-time", "--sort_option", type=str, default="NA", help="use this to time sort the returned results incremental order, default is NA to not use this option. Use YES to activate it.")
    parser.add_argument("-o", "--op_graph", type=str, default="cortxfs_hist_graph.png",
                        help="CORTXFS fn_tag histogram graph output file (cortxfs_hist_graph.png)")
    return parser.parse_args()

if __name__ == '__main__':
    args=parse_args()
    db_init(args.db)
    db_connect()
    start_opid = int(args.start_opid)
    if args.rec_limit not in "NA":
        rec_limit = int(args.rec_limit)
        print('Creating cortxfs histogram graph for fn_tag {0}, opid max limit {3} from start opid {4}, from db file {1}, time sort {5}, o/p graph file {2}'. format(args.fn_tag, args.db, args.op_graph, rec_limit, args.start_opid, args.sort_option))
    else:
        print('Creating cortxfs histogram graph for fn_tag {0}, from db file {1}, time sort {3}, o/p graph file {2}'. format(args.fn_tag, args.db, args.op_graph, args.sort_option))
    timesort = args.sort_option
    gen_perfc_op_hist_graph(args.fn_tag, args.op_graph)
    db_close()
