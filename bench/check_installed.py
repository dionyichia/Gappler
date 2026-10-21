"""Read-only drift check: candidate source vs the installed nav overlay.

Compares the tested candidate files in this checkout against what is actually
installed under install_nav/<pkg>/share/<pkg>/{launch,config} on the lab box.
Pure stdlib, never touches ROS, SSH, hardware, or builds; it only reads files
and hashes them.

Usage (run on the lab box, read-only):
    python3 bench/check_installed.py [--install-root ~/rcp-Gappler/install_nav]

Prints a per-file MATCH/DRIFT/MISSING/SKIP table. Exit 0 only if every
compared file matches; exit 1 on any drift or missing file. SKIP covers files
with no installed counterpart by design (e.g. shared/slam_maps.py, which no
CMakeLists installs under share/) and does not fail the check.

NOTE: drift is the EXPECTED current result -- the installed overlay predates
the t3.5-launch-prep candidate source, so a DRIFT table today proves the
checker works, not that anything is broken.

Self-test (pure-python, runs anywhere):
    python3 bench/check_installed.py --self-test
"""

import argparse
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_INSTALL_ROOT = Path.home() / "rcp-Gappler" / "install_nav"

# (repo-relative path, installed path relative to the install root).
# installed=None means the file is never installed under share/ by any
# CMakeLists, so there is no counterpart to compare -- SKIP, not MISSING.
FILES = (
    ("nav/robot_slam/launch/slam_mapping.launch.py",
     "robot_slam/share/robot_slam/launch/slam_mapping.launch.py"),
    ("nav/robot_slam/launch/slam_localization.launch.py",
     "robot_slam/share/robot_slam/launch/slam_localization.launch.py"),
    ("nav/robot_slam/launch/lidar_only.launch.py",
     "robot_slam/share/robot_slam/launch/lidar_only.launch.py"),
    ("nav/robot_slam/config/slam_toolbox.yaml",
     "robot_slam/share/robot_slam/config/slam_toolbox.yaml"),
    ("nav/robot_slam/config/slam_toolbox_localization.yaml",
     "robot_slam/share/robot_slam/config/slam_toolbox_localization.yaml"),
    ("nav/robot_slam/config/nav2_params.yaml",
     "robot_slam/share/robot_slam/config/nav2_params.yaml"),
    ("nav/robot_navigation/launch/navigation.launch.py",
     "robot_navigation/share/robot_navigation/launch/navigation.launch.py"),
    ("nav/robot_navigation/config/nav2_params.yaml",
     "robot_navigation/share/robot_navigation/config/nav2_params.yaml"),
    ("shared/slam_maps.py", None),
)


def sha256_of(path):
    """SHA256 hex digest of a file's bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_one(repo_root, install_root, repo_rel, installed_rel):
    """Compare one file pair. Returns (status, repo_sha, installed_sha)."""
    if installed_rel is None:
        return ("SKIP", sha256_of(repo_root / repo_rel)
                if (repo_root / repo_rel).is_file() else "-", "no installed counterpart")
    repo_path = repo_root / repo_rel
    installed_path = install_root / installed_rel
    if not repo_path.is_file():
        return ("REPO-MISSING", "-", "-")
    repo_sha = sha256_of(repo_path)
    if not installed_path.is_file():
        return ("MISSING", repo_sha[:12], "-")
    installed_sha = sha256_of(installed_path)
    if repo_sha == installed_sha:
        return ("MATCH", repo_sha[:12], installed_sha[:12])
    return ("DRIFT", repo_sha[:12], installed_sha[:12])


def check_all(repo_root, install_root):
    """Compare every file in FILES. Returns a list of row dicts."""
    rows = []
    for repo_rel, installed_rel in FILES:
        status, repo_sha, installed_sha = check_one(
            Path(repo_root), Path(install_root), repo_rel, installed_rel)
        rows.append({"repo": repo_rel,
                     "installed": installed_rel or "(not installed)",
                     "status": status,
                     "repo_sha": repo_sha,
                     "installed_sha": installed_sha})
    return rows


def all_match(rows):
    """True only if no row drifted or went missing (SKIP is fine)."""
    return all(row["status"] in ("MATCH", "SKIP") for row in rows)


def print_table(rows):
    """Print the per-file MATCH/DRIFT/MISSING table."""
    widths = {"repo": max(len(row["repo"]) for row in rows),
              "installed": max(len(row["installed"]) for row in rows)}
    header = (f"{'repo file':<{widths['repo']}}  "
              f"{'installed file':<{widths['installed']}}  "
              f"{'status':<12}  {'repo sha':<12}  {'installed sha'}")
    print(header)
    print("-" * len(header))
    for row in rows:
        print(f"{row['repo']:<{widths['repo']}}  "
              f"{row['installed']:<{widths['installed']}}  "
              f"{row['status']:<12}  {row['repo_sha']:<12}  {row['installed_sha']}")


def main(argv=None):
    """Entry point: parse args, compare, print table, return exit code."""
    parser = argparse.ArgumentParser(
        description="Compare candidate source against the installed nav overlay (read-only).",
        epilog="Drift is the expected current result: the installed overlay "
               "predates the candidate source.")
    parser.add_argument("--install-root", default=str(DEFAULT_INSTALL_ROOT),
                        help="installed overlay root (default: %(default)s)")
    parser.add_argument("--repo-root", default=str(REPO),
                        help="candidate source root (default: repo containing this file)")
    args = parser.parse_args(argv)
    rows = check_all(Path(args.repo_root), Path(args.install_root).expanduser())
    print(f"repo: {args.repo_root}")
    print(f"install-root: {args.install_root}")
    print_table(rows)
    matched = sum(row["status"] == "MATCH" for row in rows)
    drifted = sum(row["status"] == "DRIFT" for row in rows)
    missing = sum(row["status"] in ("MISSING", "REPO-MISSING") for row in rows)
    skipped = sum(row["status"] == "SKIP" for row in rows)
    print(f"\n{matched} match, {drifted} drift, {missing} missing, {skipped} skipped")
    if all_match(rows):
        print("OK: installed overlay matches candidate source")
        return 0
    print("DRIFT/MISSING: installed overlay differs from candidate source "
          "(expected: overlay predates candidate)")
    return 1


class DriftCheckTests(unittest.TestCase):
    """Self-test with temp dirs: identical files MATCH, edited files DRIFT."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.installed = Path(self.tmp.name) / "install_nav"
        for repo_rel, installed_rel in FILES:
            if installed_rel is None:
                continue
            (self.repo / repo_rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / repo_rel).write_text(f"candidate content of {repo_rel}\n")
            target = self.installed / installed_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"candidate content of {repo_rel}\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_identical_trees_all_match(self):
        rows = check_all(self.repo, self.installed)
        comparable = [row for row in rows if row["status"] != "SKIP"]
        self.assertTrue(comparable)
        for row in rows:
            with self.subTest(entry=row["repo"]):
                self.assertIn(row["status"], ("MATCH", "SKIP"))
        self.assertTrue(all_match(rows))

    def test_modified_installed_file_drifts(self):
        victim = self.installed / "robot_slam/share/robot_slam/launch/lidar_only.launch.py"
        victim.write_text("stale overlay content\n")
        rows = check_all(self.repo, self.installed)
        by_repo = {row["repo"]: row for row in rows}
        self.assertEqual(
            by_repo["nav/robot_slam/launch/lidar_only.launch.py"]["status"], "DRIFT")
        self.assertEqual(
            by_repo["nav/robot_slam/launch/slam_mapping.launch.py"]["status"], "MATCH")
        self.assertFalse(all_match(rows))

    def test_missing_installed_file_and_skip(self):
        gone = self.installed / "robot_navigation/share/robot_navigation/config/nav2_params.yaml"
        gone.unlink()
        rows = check_all(self.repo, self.installed)
        by_repo = {row["repo"]: row for row in rows}
        self.assertEqual(
            by_repo["nav/robot_navigation/config/nav2_params.yaml"]["status"], "MISSING")
        self.assertEqual(by_repo["shared/slam_maps.py"]["status"], "SKIP")
        self.assertFalse(all_match(rows))

    def test_main_exit_codes(self):
        self.assertEqual(main(["--repo-root", str(self.repo),
                               "--install-root", str(self.installed)]), 0)
        victim = self.installed / "robot_slam/share/robot_slam/config/slam_toolbox.yaml"
        victim.write_text("stale overlay content\n")
        self.assertEqual(main(["--repo-root", str(self.repo),
                               "--install-root", str(self.installed)]), 1)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.argv.remove("--self-test")
        unittest.main()
    else:
        sys.exit(main())
