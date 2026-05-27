"""Git backend — all git operations via subprocess."""

import os
import subprocess
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class Commit:
    hash: str
    short_hash: str
    parents: List[str]
    subject: str
    author: str
    date: str
    refs: List[str]          # branch/tag labels attached to this commit
    lane: int = 0            # assigned by graph layout
    color_idx: int = 0


@dataclass
class FileStatus:
    path: str
    status: str              # M, A, D, R, C, U, ?, !
    staged: bool = False
    old_path: str = ""       # for renames


@dataclass
class ConflictHunk:
    line_start: int
    ours_lines: List[str]
    theirs_lines: List[str]
    base_lines: List[str] = field(default_factory=list)
    resolved: bool = False
    resolution: str = ""     # 'ours'|'theirs'|'both'|'custom'


@dataclass
class Remote:
    name: str
    fetch_url: str
    push_url: str


# ── GitBackend ────────────────────────────────────────────────────────────────

class GitError(Exception):
    pass


class GitBackend:
    """Thin wrapper around git subprocess calls."""

    def __init__(self, repo_path: str = ""):
        self.repo_path = repo_path or os.getcwd()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _run(self, args: List[str], check=True, input_text=None) -> str:
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                input=input_text,
            )
            if check and result.returncode != 0:
                raise GitError(result.stderr.strip() or result.stdout.strip())
            return result.stdout
        except FileNotFoundError:
            raise GitError("git not found in PATH")

    def _run_lines(self, args: List[str]) -> List[str]:
        out = self._run(args)
        return [l for l in out.splitlines() if l]

    def is_git_repo(self) -> bool:
        try:
            self._run(["rev-parse", "--git-dir"])
            return True
        except GitError:
            return False

    def repo_root(self) -> str:
        try:
            return self._run(["rev-parse", "--show-toplevel"]).strip()
        except GitError:
            return self.repo_path

    # ── Commits / Log ─────────────────────────────────────────────────────────

    def get_commits(self, max_count: int = 500) -> List[Commit]:
        sep = "\x1e"  # ASCII record-separator, safe in subprocess args
        fmt = f"%H{sep}%P{sep}%s{sep}%an{sep}%ad{sep}%D"
        lines = self._run([
            "log", "--all", "--topo-order",
            f"--max-count={max_count}",
            f"--format={fmt}",
            "--date=format:%Y-%m-%d %H:%M",
        ]).strip()

        commits = []
        for line in lines.split("\n"):
            if not line.strip():
                continue
            parts = line.split(sep)
            if len(parts) < 6:
                continue
            h, parents_raw, subject, author, date, refs_raw = parts
            parents = [p for p in parents_raw.split() if p]
            refs = [r.strip() for r in refs_raw.split(",") if r.strip()]
            commits.append(Commit(
                hash=h,
                short_hash=h[:7],
                parents=parents,
                subject=subject,
                author=author,
                date=date,
                refs=refs,
            ))

        self._assign_lanes(commits)
        return commits

    def _assign_lanes(self, commits: List[Commit]):
        """Simple lane-assignment algorithm for graph drawing."""
        lanes: List[Optional[str]] = []
        hash_to_commit = {c.hash: c for c in commits}
        color_map: Dict[str, int] = {}
        next_color = [0]
        COLORS = 8

        def alloc_color(h: str) -> int:
            if h not in color_map:
                color_map[h] = next_color[0] % COLORS
                next_color[0] += 1
            return color_map[h]

        for commit in commits:
            h = commit.hash
            if h in lanes:
                idx = lanes.index(h)
            else:
                try:
                    idx = lanes.index(None)
                except ValueError:
                    idx = len(lanes)
                    lanes.append(None)
                lanes[idx] = h

            commit.lane = idx
            commit.color_idx = alloc_color(h)

            parents = commit.parents
            if parents:
                lanes[idx] = parents[0]
                color_map.setdefault(parents[0], color_map.get(h, 0))
                for extra_parent in parents[1:]:
                    if extra_parent not in lanes:
                        try:
                            free = lanes.index(None)
                        except ValueError:
                            free = len(lanes)
                            lanes.append(None)
                        lanes[free] = extra_parent
                        color_map.setdefault(extra_parent, alloc_color(extra_parent))
            else:
                lanes[idx] = None

            while lanes and lanes[-1] is None:
                lanes.pop()

    def get_commit_detail(self, hash: str) -> Dict:
        raw = self._run(["show", "--stat", "--format=%H%n%an%n%ae%n%ad%n%s%n%b",
                          "--date=format:%Y-%m-%d %H:%M", hash])
        lines = raw.splitlines()
        return {
            "hash": lines[0] if lines else hash,
            "author": lines[1] if len(lines) > 1 else "",
            "email": lines[2] if len(lines) > 2 else "",
            "date": lines[3] if len(lines) > 3 else "",
            "subject": lines[4] if len(lines) > 4 else "",
            "body": "\n".join(lines[5:]) if len(lines) > 5 else "",
        }

    def get_commit_files(self, hash: str) -> List[FileStatus]:
        out = self._run(["diff-tree", "--no-commit-id", "-r", "--name-status", hash])
        files = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                status = parts[0][0]
                path = parts[-1]
                old_path = parts[1] if len(parts) == 3 else ""
                files.append(FileStatus(path=path, status=status, old_path=old_path))
        return files

    def get_file_diff(self, hash: str, file_path: str) -> str:
        return self._run(["show", f"{hash}:{file_path}"], check=False)

    def get_diff_between(self, hash1: str, hash2: str, file_path: str = "") -> str:
        args = ["diff", hash1, hash2]
        if file_path:
            args += ["--", file_path]
        return self._run(args, check=False)

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> List[FileStatus]:
        out = self._run(["status", "--porcelain=v1", "-u"])
        files = []
        for line in out.splitlines():
            if len(line) < 4:
                continue
            xy = line[:2]
            path = line[3:]
            # Handle renames: "old -> new"
            old_path = ""
            if " -> " in path:
                old_path, path = path.split(" -> ", 1)

            index_status = xy[0]   # staged
            work_status = xy[1]    # unstaged

            if index_status != " " and index_status != "?":
                files.append(FileStatus(
                    path=path.strip('"'),
                    status=index_status,
                    staged=True,
                    old_path=old_path,
                ))
            if work_status not in (" ", "?", "!"):
                files.append(FileStatus(
                    path=path.strip('"'),
                    status=work_status,
                    staged=False,
                ))
            elif work_status == "?":
                files.append(FileStatus(path=path.strip('"'), status="?", staged=False))
            elif work_status == "!":
                files.append(FileStatus(path=path.strip('"'), status="!", staged=False))

        return files

    def get_status_map(self) -> Dict[str, FileStatus]:
        return {f.path: f for f in self.get_status()}

    # ── Branches ──────────────────────────────────────────────────────────────

    def get_branches(self) -> List[Dict]:
        out = self._run([
            "branch", "-avv",
            "--format=%(refname:short)|%(upstream:short)|%(HEAD)|%(objectname:short)"
        ])
        branches = []
        for line in out.splitlines():
            parts = line.split("|")
            if len(parts) < 4:
                continue
            name, upstream, head, sha = parts
            branches.append({
                "name": name,
                "upstream": upstream,
                "current": head == "*",
                "sha": sha,
                "is_remote": name.startswith("remotes/"),
            })
        return branches

    def current_branch(self) -> str:
        try:
            return self._run(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        except GitError:
            return "HEAD"

    def create_branch(self, name: str, from_ref: str = "") -> str:
        args = ["branch", name]
        if from_ref:
            args.append(from_ref)
        return self._run(args)

    def checkout(self, ref: str, new_branch: str = "") -> str:
        if new_branch:
            return self._run(["checkout", "-b", new_branch, ref])
        return self._run(["checkout", ref])

    def delete_branch(self, name: str, force: bool = False) -> str:
        flag = "-D" if force else "-d"
        return self._run(["branch", flag, name])

    def rename_branch(self, old: str, new: str) -> str:
        return self._run(["branch", "-m", old, new])

    def merge(self, branch: str, no_ff: bool = False, message: str = "") -> str:
        args = ["merge"]
        if no_ff:
            args.append("--no-ff")
        if message:
            args += ["-m", message]
        args.append(branch)
        return self._run(args)

    def rebase(self, onto: str) -> str:
        return self._run(["rebase", onto])

    def reset(self, ref: str, mode: str = "mixed") -> str:
        return self._run(["reset", f"--{mode}", ref])

    # ── Remote operations ─────────────────────────────────────────────────────

    def get_remotes(self) -> List[Remote]:
        out = self._run(["remote", "-v"], check=False)
        remotes: Dict[str, Remote] = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            name, url, direction = parts[0], parts[1], parts[2].strip("()")
            if name not in remotes:
                remotes[name] = Remote(name=name, fetch_url="", push_url="")
            if direction == "fetch":
                remotes[name].fetch_url = url
            else:
                remotes[name].push_url = url
        return list(remotes.values())

    def add_remote(self, name: str, url: str) -> str:
        return self._run(["remote", "add", name, url])

    def remove_remote(self, name: str) -> str:
        return self._run(["remote", "remove", name])

    def set_remote_url(self, name: str, url: str) -> str:
        return self._run(["remote", "set-url", name, url])

    def fetch(self, remote: str = "", prune: bool = False) -> str:
        args = ["fetch"]
        if remote:
            args.append(remote)
        else:
            args.append("--all")
        if prune:
            args.append("--prune")
        return self._run(args)

    def pull(self, remote: str = "origin", branch: str = "") -> str:
        args = ["pull", remote]
        if branch:
            args.append(branch)
        return self._run(args)

    def push(self, remote: str = "origin", branch: str = "",
             force: bool = False, set_upstream: bool = False) -> str:
        args = ["push"]
        if force:
            args.append("--force-with-lease")
        if set_upstream:
            args += ["--set-upstream"]
        args.append(remote)
        if branch:
            args.append(branch)
        return self._run(args)

    # ── Staging / Commit ──────────────────────────────────────────────────────

    def stage(self, paths: List[str]) -> str:
        return self._run(["add", "--"] + paths)

    def unstage(self, paths: List[str]) -> str:
        return self._run(["restore", "--staged", "--"] + paths)

    def discard(self, paths: List[str]) -> str:
        return self._run(["restore", "--"] + paths)

    def commit(self, message: str, amend: bool = False, signoff: bool = False) -> str:
        args = ["commit", "-m", message]
        if amend:
            args.append("--amend")
        if signoff:
            args.append("--signoff")
        return self._run(args)

    def get_staged_diff(self) -> str:
        return self._run(["diff", "--cached"], check=False)

    def get_unstaged_diff(self) -> str:
        return self._run(["diff"], check=False)

    def get_file_unstaged_diff(self, path: str) -> str:
        return self._run(["diff", "--", path], check=False)

    def get_file_staged_diff(self, path: str) -> str:
        return self._run(["diff", "--cached", "--", path], check=False)

    # ── Cherry-pick / Revert ──────────────────────────────────────────────────

    def cherry_pick(self, hash: str) -> str:
        return self._run(["cherry-pick", hash])

    def revert_commit(self, hash: str, no_commit: bool = False) -> str:
        args = ["revert", hash]
        if no_commit:
            args.append("--no-commit")
        return self._run(args)

    def revert_file(self, path: str, ref: str = "HEAD") -> str:
        return self._run(["checkout", ref, "--", path])

    # ── Stash ─────────────────────────────────────────────────────────────────

    def get_stashes(self) -> List[Dict]:
        out = self._run(["stash", "list", "--format=%gd|%s|%cr"], check=False)
        stashes = []
        for line in out.splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                stashes.append({"ref": parts[0], "message": parts[1], "date": parts[2]})
        return stashes

    def stash_push(self, message: str = "", include_untracked: bool = True) -> str:
        args = ["stash", "push"]
        if include_untracked:
            args.append("-u")
        if message:
            args += ["-m", message]
        return self._run(args)

    def stash_apply(self, ref: str = "") -> str:
        args = ["stash", "apply"]
        if ref:
            args.append(ref)
        return self._run(args)

    def stash_pop(self, ref: str = "") -> str:
        args = ["stash", "pop"]
        if ref:
            args.append(ref)
        return self._run(args)

    def stash_drop(self, ref: str) -> str:
        return self._run(["stash", "drop", ref])

    def stash_branch(self, branch: str, ref: str) -> str:
        return self._run(["stash", "branch", branch, ref])

    # ── Tags ──────────────────────────────────────────────────────────────────

    def get_tags(self) -> List[Dict]:
        out = self._run(["tag", "-l", "--format=%(refname:short)|%(objectname:short)|%(creatordate:short)"], check=False)
        tags = []
        for line in out.splitlines():
            parts = line.split("|")
            if parts:
                tags.append({
                    "name": parts[0],
                    "sha": parts[1] if len(parts) > 1 else "",
                    "date": parts[2] if len(parts) > 2 else "",
                })
        return tags

    def create_tag(self, name: str, ref: str = "HEAD",
                   message: str = "", annotated: bool = False) -> str:
        if annotated and message:
            return self._run(["tag", "-a", name, ref, "-m", message])
        return self._run(["tag", name, ref])

    def delete_tag(self, name: str) -> str:
        return self._run(["tag", "-d", name])

    def push_tag(self, remote: str, name: str) -> str:
        return self._run(["push", remote, name])

    # ── Conflict resolution ───────────────────────────────────────────────────

    def get_conflicts(self) -> List[str]:
        out = self._run(["diff", "--name-only", "--diff-filter=U"], check=False)
        return [l for l in out.splitlines() if l]

    def get_conflict_hunks(self, path: str) -> Tuple[str, str, str, List[ConflictHunk]]:
        full_path = os.path.join(self.repo_path, path)
        try:
            with open(full_path, "r", errors="replace") as f:
                content = f.read()
        except OSError:
            return "", "", "", []

        ours_ver = self._run(["show", f":2:{path}"], check=False)
        theirs_ver = self._run(["show", f":3:{path}"], check=False)
        base_ver = self._run(["show", f":1:{path}"], check=False)

        hunks = []
        lines = content.splitlines(keepends=True)
        i = 0
        while i < len(lines):
            if lines[i].startswith("<<<<<<<"):
                hunk_start = i
                ours, theirs, base = [], [], []
                state = "ours"
                i += 1
                while i < len(lines):
                    if lines[i].startswith("======="):
                        state = "theirs"
                    elif lines[i].startswith(">>>>>>>"):
                        hunks.append(ConflictHunk(
                            line_start=hunk_start,
                            ours_lines=ours,
                            theirs_lines=theirs,
                            base_lines=base,
                        ))
                        i += 1
                        break
                    elif lines[i].startswith("|||||"):
                        state = "base"
                    else:
                        if state == "ours":
                            ours.append(lines[i])
                        elif state == "theirs":
                            theirs.append(lines[i])
                        elif state == "base":
                            base.append(lines[i])
                    i += 1
            else:
                i += 1

        return ours_ver, theirs_ver, base_ver, hunks

    def resolve_file(self, path: str, resolution: str) -> str:
        """resolution: 'ours' | 'theirs'"""
        flag = "--ours" if resolution == "ours" else "--theirs"
        self._run(["checkout", flag, "--", path])
        return self._run(["add", "--", path])

    def write_resolved(self, path: str, content: str):
        full_path = os.path.join(self.repo_path, path)
        with open(full_path, "w") as f:
            f.write(content)
        self._run(["add", "--", path])

    def merge_continue(self, message: str = "") -> str:
        if message:
            return self._run(["commit", "-m", message])
        return self._run(["commit", "--no-edit"])

    def merge_abort(self) -> str:
        return self._run(["merge", "--abort"], check=False)

    def rebase_abort(self) -> str:
        return self._run(["rebase", "--abort"], check=False)

    def cherry_pick_abort(self) -> str:
        return self._run(["cherry-pick", "--abort"], check=False)

    # ── Clone ─────────────────────────────────────────────────────────────────

    def clone(self, url: str, dest: str, branch: str = "",
              depth: int = 0, progress_callback=None) -> subprocess.Popen:
        args = ["git", "clone", "--progress"]
        if branch:
            args += ["-b", branch]
        if depth:
            args += ["--depth", str(depth)]
        args += [url, dest]
        proc = subprocess.Popen(
            args,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        return proc

    # ── Remote file tree ──────────────────────────────────────────────────────

    def get_remote_tree(self, ref: str) -> List[Dict]:
        out = self._run(["ls-tree", "-r", "--name-only", ref], check=False)
        files = []
        for line in out.splitlines():
            if line:
                files.append({"path": line, "type": "blob"})
        return files

    def get_remote_file_content(self, ref: str, path: str) -> str:
        return self._run(["show", f"{ref}:{path}"], check=False)

    def get_ahead_behind(self, branch: str, remote_branch: str) -> Tuple[int, int]:
        out = self._run(
            ["rev-list", "--left-right", "--count", f"{remote_branch}...{branch}"],
            check=False
        ).strip()
        if out:
            parts = out.split()
            if len(parts) == 2:
                return int(parts[1]), int(parts[0])  # ahead, behind
        return 0, 0

    # ── File operations ───────────────────────────────────────────────────────

    def rm_file(self, path: str, cached: bool = False) -> str:
        args = ["rm"]
        if cached:
            args.append("--cached")
        args += ["--", path]
        return self._run(args)

    def mv_file(self, src: str, dst: str) -> str:
        return self._run(["mv", src, dst])

    def clean(self, force: bool = True, dirs: bool = False) -> str:
        args = ["clean"]
        if force:
            args.append("-f")
        if dirs:
            args.append("-d")
        return self._run(args)

    # ── Search ────────────────────────────────────────────────────────────────

    def search_commits(self, query: str, field: str = "all") -> List[Commit]:
        sep = "\x1e"
        args = ["log", "--all", "--topo-order", "--max-count=200",
                f"--format=%H{sep}%P{sep}%s{sep}%an{sep}%ad{sep}%D",
                "--date=format:%Y-%m-%d %H:%M"]
        if field in ("message", "all"):
            args += [f"--grep={query}"]
        if field in ("author", "all"):
            args += [f"--author={query}"]
        out = self._run(args, check=False)
        commits = []
        for line in out.strip().split("\n"):
            if not line:
                continue
            parts = line.split(sep)
            if len(parts) < 6:
                continue
            h, parents_raw, subject, author, date, refs_raw = parts
            commits.append(Commit(
                hash=h, short_hash=h[:7],
                parents=[p for p in parents_raw.split() if p],
                subject=subject, author=author, date=date,
                refs=[r.strip() for r in refs_raw.split(",") if r.strip()],
            ))
        return commits

    def get_file_log(self, path: str, max_count: int = 100) -> List[Commit]:
        sep = "\x1e"
        fmt = f"%H{sep}%P{sep}%s{sep}%an{sep}%ad{sep}%D"
        out = self._run([
            "log", f"--max-count={max_count}",
            f"--format={fmt}",
            "--date=format:%Y-%m-%d %H:%M",
            "--follow", "--", path
        ], check=False)
        commits = []
        for line in out.strip().split("\n"):
            if not line:
                continue
            parts = line.split(sep)
            if len(parts) < 6:
                continue
            h, parents_raw, subject, author, date, refs_raw = parts
            commits.append(Commit(
                hash=h, short_hash=h[:7],
                parents=[p for p in parents_raw.split() if p],
                subject=subject, author=author, date=date,
                refs=[r.strip() for r in refs_raw.split(",") if r.strip()],
            ))
        return commits
