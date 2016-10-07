import pygit2
import tornado.options
import csv
import os
import glob
import logging
import datetime

from formatters import _utf8, _dt

tornado.options.define("git_log_output_file", default="../repo_cache/commit_log.csv", type=str)


def git_log():
    # columns = ["repo","commit","author_email","author_name","ts","short_msg", "message","merge"]
    for line in csv.DictReader(open(tornado.options.options.git_log_output_file)):
        line['ts'] = int(line['ts'])
        line['dt'] = _dt(line['ts'])
        yield line

def run(d, o, year):
    if not d:
        logging.debug('skipping; missing directory')
        return
    repo_dir = os.path.abspath(os.path.expanduser(d))
    # repo_name = repo_dir.split('/')[-2]
    repo_name = repo_dir
    logging.info('opening repo %s', repo_dir)
    repo_config_file = repo_dir + "/.git/config"
    if not os.path.exists(repo_config_file):
        logging.warning('skipping; non-git directory (no .git/config found)')
        return
    
    if 'github.com' not in open(repo_config_file).read():
        logging.warning('skipping; nogithub.com remote')
        return
    
    found = 0
    skip_year = 0
    skip_author = 0
    skip_commit_type = 0
    revisited_comimts = 0
    
    repo = pygit2.Repository(repo_dir)
    
    walker = repo.walk(repo.head.target, pygit2.GIT_SORT_TIME)
    targets = [repo.head.target]
    
    branches = repo.listall_branches()
    if branches:
        for branch_name in branches:
            branch = repo.lookup_branch(branch_name)
            if not branch.is_head():
                if tornado.options.options.branch_filter and branch_name not in tornado.options.options.branch_filter:
                    logging.info('skipping branch %r (not in --branch-filter)', branch_name)
                    continue
                targets.append(repo.lookup_reference("refs/heads/" + branch_name).target)
    
    seen_commits = set()
    
    for target in targets:
        logging.info('walking %r', target)
        walker.reset()
        walker.push(target)
        try:
            for i, commit in enumerate(walker):
                if year > 0:
                    dt = _dt(commit.committer.time)
                    if dt.year != year:
                        skip_year+=1
                        continue
                if tornado.options.options.author_filter and tornado.options.options.author_filter != commit.committer.email:
                    skip_author+=1
                    continue
                merge_commit = len(commit.parents) == 2
                if merge_commit and not tornado.options.options.include_merges:
                    skip_commit_type+=1
                    continue
                if not merge_commit and not tornado.options.options.include_commits:
                    skip_commit_type+=1
                    continue
            
                if commit.hex in seen_commits:
                    revisited_comimts += 1
                    continue
                seen_commits.add(commit.hex)
            
                short_msg = commit.message.split("\n")[0][:70]

                msg = dict(
                    repo=repo_name,
                    commit=commit.hex,
                    author_email=commit.author.email,
                    author_name=_utf8(commit.author.name),
                    committer_email=commit.committer.email,
                    committer_name=_utf8(commit.committer.name),
                    ts=str(commit.committer.time),
                    short_msg='',
                    message='',
                    merge='1' if len(commit.parents) == 2 else '0'
                )
                if tornado.options.options.short_message:
                    msg['short_msg'] = _utf8(short_msg)
                if tornado.options.options.long_message:
                    msg['message'] = _utf8(commit.message)
            
                found += 1
                print msg
                if not tornado.options.options.dry_run:
                    o.writerow(msg)
        except:
            logging.exception('failed walking commit %r %r', target, walker)
    
    logging.info('found %d skipped %d:year %d:author %d:commit type for %r (revisited commits %d)', found, skip_year, skip_author, skip_commit_type, repo_name, revisited_comimts)

if __name__ == "__main__":
    tornado.options.define("repo", default=".git", type=str, help="the path to the repo .git directory")
    tornado.options.define("repo_file", default=None, type=str, help="file with paths to .git directories")
    tornado.options.define("repo_pattern", default=None, type=str, multiple=True, help="glob pattern for repos")
    tornado.options.define("year", type=int, default=datetime.datetime.utcnow().year, help="-1 to skip")
    tornado.options.define("dry_run", type=bool, default=False)
    tornado.options.define("include_merges", type=bool, default=True)
    tornado.options.define("include_commits", type=bool, default=True)
    tornado.options.define("author_filter", type=str, default="")
    tornado.options.define("short_message", type=bool, default=True)
    tornado.options.define("long_message", type=bool, default=False)
    tornado.options.define("branch_filter", type=str, multiple=True, default=[])
    tornado.options.parse_command_line()
    
    o = tornado.options.options
    ow = None
    if not tornado.options.options.dry_run:
        f = open(o.git_log_output_file, 'w')
        columns = ["repo","commit", "committer_email", "committer_name", "author_email","author_name","ts","short_msg", "message","merge"]
        ow = csv.DictWriter(f, columns)
        ow.writeheader()
    if o.repo_file:
        for repo in open(o.repo_file, 'r'):
            run(repo.strip(), ow, o.year)
    elif o.repo_pattern:
        for pattern in o.repo_pattern:
            logging.info('matching pattern %r', pattern)
            for directory in glob.glob(os.path.expanduser(pattern)):
                run(directory, ow, o.year)
    else:
        run(o.repo, ow, o.year)

    if not tornado.options.options.dry_run:
        f.close()
