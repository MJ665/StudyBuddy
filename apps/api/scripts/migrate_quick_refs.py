import os
import sys

# Unified Path Logic: Ensure apps/api and root are reachable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.append(BASE_DIR)

import os  # noqa: E402
import sys  # noqa: E402

import models  # noqa: E402

# Add current directory to path if needed
from database import SessionLocal  # noqa: E402

QUICK_REFS = {
    "Bash": [
        {"cmd": "declare -r", "desc": "Read-only variable"},
        {"cmd": "declare -i", "desc": "Integer attribute"},
        {"cmd": "declare -a", "desc": "Indexed array"},
        {"cmd": "declare -A", "desc": "Associative array"},
    ],
    "Linux": [
        {"cmd": "chmod 755", "desc": "rwxr-xr-x"},
        {"cmd": "chown u:g", "desc": "Change owner"},
        {"cmd": "find -type f", "desc": "Files only"},
        {"cmd": "ps aux", "desc": "All processes"},
    ],
    "Python": [
        {"cmd": "list comp", "desc": "[x for x in y]"},
        {"cmd": "__init__", "desc": "Constructor"},
        {"cmd": "@property", "desc": "Getter decorator"},
        {"cmd": "with open()", "desc": "Context manager"},
    ],
    "Docker": [
        {"cmd": "docker ps -a", "desc": "All containers"},
        {"cmd": "COPY vs ADD", "desc": "COPY is preferred"},
        {"cmd": "ENTRYPOINT", "desc": "Container start cmd"},
        {"cmd": "--no-cache", "desc": "Fresh build layer"},
    ],
    "Kubernetes": [
        {"cmd": "kubectl get po", "desc": "List pods"},
        {"cmd": "kubectl describe", "desc": "Full details"},
        {"cmd": "livenessProbe", "desc": "Health check"},
        {"cmd": "ClusterIP", "desc": "Internal service"},
    ],
    "SQL": [
        {"cmd": "INNER JOIN", "desc": "Matching rows only"},
        {"cmd": "GROUP BY", "desc": "Aggregate rows"},
        {"cmd": "HAVING", "desc": "Filter aggregates"},
        {"cmd": "EXPLAIN", "desc": "Query plan"},
    ],
    "Terraform": [
        {"cmd": "terraform plan", "desc": "Preview changes"},
        {"cmd": "depends_on", "desc": "Explicit dependency"},
        {"cmd": "data source", "desc": "Read existing resource"},
        {"cmd": "for_each", "desc": "Dynamic resources"},
    ],
    "Git": [
        {"cmd": "git rebase -i", "desc": "Interactive rebase"},
        {"cmd": "git stash pop", "desc": "Restore stash"},
        {"cmd": "git bisect", "desc": "Find bad commit"},
        {"cmd": "git reflog", "desc": "All HEAD moves"},
    ],
    "Regex": [
        {"cmd": "^...$", "desc": "Start/end anchors"},
        {"cmd": "[a-zA-Z]", "desc": "Character class"},
        {"cmd": "\\d+ \\w+", "desc": "Digits / word chars"},
        {"cmd": "(?:...)", "desc": "Non-capturing group"},
    ],
    "AWS": [
        {"cmd": "aws s3 cp", "desc": "Copy to/from S3"},
        {"cmd": "aws iam", "desc": "Identity mgmt"},
        {"cmd": "aws ec2", "desc": "Compute instances"},
        {"cmd": "aws lambda", "desc": "Serverless functions"},
    ],
}


def migrate():
    db = SessionLocal()
    try:
        # For each bank that has a chapter matching one of these keys, populate quick_references
        banks = db.query(models.QuestionBank).all()
        updated_count = 0
        for bank in banks:
            if not bank.chapter:
                continue

            # Find matching ref
            match_key = next(
                (k for k in QUICK_REFS if k.lower() in bank.chapter.lower()), None
            )
            if match_key:
                bank.quick_references = QUICK_REFS[match_key]
                updated_count += 1

        db.commit()
        print(
            f"Successfully updated {updated_count} question banks with quick references."
        )
    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
