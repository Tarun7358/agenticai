"""
GitHub & Local Git Operations Agent for AURA / JARVIS.
All repository actions are executed 100% locally on the host machine.
No telemetry or private data is transmitted outside.
"""
import os
import subprocess
import webbrowser
from typing import Dict, Any, List

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_git_status(repo_dir: str = WORKSPACE_DIR) -> Dict[str, Any]:
    """Inspects local git repo status, active branch, and uncommitted changes."""
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=repo_dir, text=True, stderr=subprocess.DEVNULL
        ).strip() or "main"
        
        status_out = subprocess.check_output(
            ["git", "status", "--short"],
            cwd=repo_dir, text=True, stderr=subprocess.DEVNULL
        ).strip()
        
        last_commit = subprocess.check_output(
            ["git", "log", "-1", "--pretty=format:%h - %s (%cr)"],
            cwd=repo_dir, text=True, stderr=subprocess.DEVNULL
        ).strip()
        
        changed_count = len([line for line in status_out.splitlines() if line.strip()]) if status_out else 0
        
        return {
            "status": "ok",
            "branch": branch,
            "changed_files_count": changed_count,
            "last_commit": last_commit,
            "is_clean": (changed_count == 0)
        }
    except Exception as ex:
        return {"status": "error", "message": str(ex)}

def get_recent_commits(limit: int = 3, repo_dir: str = WORKSPACE_DIR) -> List[str]:
    """Retrieves recent commits from the active local repo."""
    try:
        out = subprocess.check_output(
            ["git", "log", f"-n{limit}", "--pretty=format:%s (%cr)"],
            cwd=repo_dir, text=True, stderr=subprocess.DEVNULL
        ).strip()
        return [c.strip() for c in out.splitlines() if c.strip()]
    except Exception:
        return []

def open_github_repo(repo_dir: str = WORKSPACE_DIR) -> str:
    """Opens the GitHub repository or profile in the default browser."""
    try:
        remote_url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_dir, text=True, stderr=subprocess.DEVNULL
        ).strip()
        if remote_url.endswith(".git"):
            remote_url = remote_url[:-4]
        if remote_url.startswith("git@github.com:"):
            remote_url = "https://github.com/" + remote_url.split("git@github.com:")[1]
    except Exception:
        remote_url = "https://github.com/Tarun7358"
    
    webbrowser.open(remote_url)
    return remote_url
