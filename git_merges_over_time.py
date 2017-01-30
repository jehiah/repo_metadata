import csv
import tornado.options
import sys
import datetime
from collections import defaultdict

from formatters import _dt
import plotly.offline as py
import plotly.graph_objs as go

def apply_activity_filter(d):
    for dt, activity in d:
        summary = defaultdict(int)
        for user in activity:
            summary[user] += 1
        filtered_activity = filter(lambda x: summary[x] > tornado.options.options.min_activity, activity)
        if filtered_activity:
            yield (dt, filtered_activity)
        

if __name__ == "__main__":
    tornado.options.define("git_log_output_file", default="../repo_cache/commit_log.csv", type=str)
    tornado.options.define("min_dt", type=str, default="2011/1/1", help="in %Y/%m/%d format")
    tornado.options.define("max_dt", type=str, default=datetime.datetime.utcnow().strftime('%Y/%m/%d'), help="in %Y/%m/%d format")
    tornado.options.define("min_activity", type=int, default=0)
    tornado.options.define("group_by", type=str, default="month", help="month|week")
    tornado.options.parse_command_line()
    
    
    o = tornado.options.options

    min_dt = datetime.datetime.strptime(o.min_dt, "%Y/%m/%d")
    max_dt = datetime.datetime.strptime(o.max_dt, "%Y/%m/%d")

    w = csv.writer(sys.stdout)
    data = defaultdict(list)
    for line in csv.DictReader(open(o.git_log_output_file, 'r')):
        if line['merge'] != '1':
            continue
        dt = _dt(line['ts'])
        if dt < min_dt:
            continue
        if dt > max_dt:
            continue
        if o.group_by == "week":
            dt = dt - datetime.timedelta(days=dt.isoweekday() - 1)
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        elif o.group_by == "month":
            dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif o.group_by == "year":
            dt = dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise Exception("unknown group_by")
        data[dt].append(line['author_email'])
    
    records = sorted(apply_activity_filter(data.items()))
    xdata = map(lambda x: x[0], records)
    
    chart_data = [
        go.Scatter(x=xdata, y=map(lambda x: len(x[1]), records), name='Merge Commits', text='merges'),
        go.Scatter(x=xdata, y=map(lambda x: len(set(x[1])), records), name='Active Commiters', text='commiters'),
        ]
    py.plot(dict(data=chart_data, layout=go.Layout(title="Github activity over time")), 
        output_type='file', include_plotlyjs=True, filename = 'git_activity_over_time.html')
        