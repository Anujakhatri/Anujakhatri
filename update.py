import datetime
import hashlib
import json
import os
import time
from pathlib import Path

import requests
from dateutil import relativedelta

CACHE_DIR = Path("cache")
STATS_FILE = CACHE_DIR / "stats.json"

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "").strip()
if not ACCESS_TOKEN:
    raise ValueError("ACCESS_TOKEN environment variable is not set or is empty.")

HEADERS = {"authorization": "token " + ACCESS_TOKEN}

USER_NAME = os.environ.get("USER_NAME", "").strip()
if not USER_NAME:
    try:
        query = "query { viewer { login } }"
        request = requests.post(
            "https://api.github.com/graphql",
            json={"query": query},
            headers=HEADERS,
        )
        if request.status_code == 200:
            USER_NAME = request.json()["data"]["viewer"]["login"].strip()
            print(f"Automatically detected USER_NAME from ACCESS_TOKEN: {USER_NAME}")
    except Exception as e:
        print(f"Failed to automatically detect USER_NAME: {e}")

if not USER_NAME:
    raise ValueError("USER_NAME environment variable is not set and could not be auto-detected.")

QUERY_COUNT = {
    "user_getter": 0,
    "follower_getter": 0,
    "graph_repos_stars": 0,
    "starred_getter": 0,
    "commit_loc_getter": 0,
}

COMMENT_SIZE = 7
CACHE_FILENAME = CACHE_DIR / (
    hashlib.sha256(USER_NAME.encode("utf-8")).hexdigest() + ".txt"
)


def simple_request(func_name, query, variables):
    request = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=HEADERS,
    )
    if request.status_code == 200:
        return request
    raise Exception(
        func_name, "has failed with", request.status_code,
        request.text, QUERY_COUNT,
    )


def query_count(funct_id):
    QUERY_COUNT[funct_id] += 1


def perf_counter(funct, *args):
    start = time.perf_counter()
    result = funct(*args)
    return result, time.perf_counter() - start


def formatter(query_type, difference, whitespace=0):
    print("{:<23}".format("   " + query_type + ":"), sep="", end="")
    if difference > 1:
        print("{:>12}".format("%.4f" % difference + " s "))
    else:
        print("{:>12}".format("%.4f" % (difference * 1000) + " ms"))



def graph_repos_stars(count_type, owner_affiliation, cursor=None):
    """Return total repo count or total star count across the user's repos."""
    query_count("graph_repos_stars")
    query = """
    query ($login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 100, after: $cursor, privacy: PUBLIC) {
                totalCount
                edges {
                    node {
                        ... on Repository {
                            nameWithOwner
                            stargazers { totalCount }
                        }
                    }
                }
                pageInfo { endCursor hasNextPage }
            }
        }
    }"""
    variables = {
        "login": USER_NAME,
        "cursor": cursor,
    }
    request = simple_request(graph_repos_stars.__name__, query, variables)
    response_json = request.json()
    print(f"DEBUG: GraphQL response = {json.dumps(response_json)}")
    data = response_json["data"]["user"]["repositories"]
    
    owned_edges = [
        edge for edge in (data.get("edges") or [])
        if edge and edge.get("node") and edge["node"]["nameWithOwner"].split("/")[0].lower() == USER_NAME.lower()
    ]

    if count_type == "repos":
        return len(owned_edges)
    if count_type == "stars":
        return sum(
            (edge["node"].get("stargazers") or {}).get("totalCount", 0)
            for edge in owned_edges
        )
    if count_type == "repo_list":
        return [
            edge["node"]["nameWithOwner"]
            for edge in owned_edges
        ]
    raise ValueError(f"unknown count_type: {count_type!r}")


def follower_getter(username):
    query_count("follower_getter")
    query = """
    query($login: String!){
        user(login: $login) { followers { totalCount } }
    }"""
    request = simple_request(
        follower_getter.__name__, query, {"login": username}
    )
    return int(request.json()["data"]["user"]["followers"]["totalCount"])


def commit_loc_getter(repo_list, username):
    """Total commits, additions, and deletions across given repos."""
    total_commits = 0
    total_additions = 0
    total_deletions = 0
    
    for repo in repo_list:
        url = f"https://api.github.com/repos/{repo}/stats/contributors"
        # The GitHub API may return 202 Accepted if stats are compiling. We retry up to 3 times.
        for attempt in range(3):
            query_count("commit_loc_getter")
            req = requests.get(url, headers=HEADERS)
            if req.status_code == 200:
                stats = req.json()
                if isinstance(stats, list):
                    for contributor in stats:
                        if contributor.get("author") and contributor["author"]["login"].lower() == username.lower():
                            total_commits += contributor.get("total", 0)
                            for week in contributor.get("weeks", []):
                                total_additions += week.get("a", 0)
                                total_deletions += week.get("d", 0)
                break
            elif req.status_code == 202:
                time.sleep(1)
            else:
                break
                
    return total_commits, total_additions, total_deletions


def starred_getter(username):
    """Total number of repositories the user has starred (NOT stars received)."""
    query_count("starred_getter")
    query = """
    query($login: String!){
        user(login: $login) {
            starredRepositories { totalCount }
        }
    }"""
    request = simple_request(
        starred_getter.__name__, query, {"login": username}
    )
    return int(request.json()["data"]["user"]["starredRepositories"]["totalCount"])


def user_getter(username):
    query_count("user_getter")
    query = """
    query($login: String!){
        user(login: $login) { 
            id 
            createdAt 
            repositoriesContributedTo(first: 1) { totalCount }
        }
    }"""
    request = simple_request(
        user_getter.__name__, query, {"login": username}
    )
    return request.json()["data"]["user"]


def _read_cache():
    if not CACHE_FILENAME.exists():
        return ["This line is a comment block. Write whatever you want here.\n"] * COMMENT_SIZE
    return CACHE_FILENAME.read_text(encoding="utf-8").splitlines(keepends=True)


def _write_cache(lines):
    CACHE_DIR.mkdir(exist_ok=True)
    CACHE_FILENAME.write_text("".join(lines), encoding="utf-8")


def refresh_cache_files():
    _read_cache()  # touch the file to confirm it exists
    return None


if __name__ == "__main__":
    CACHE_DIR.mkdir(exist_ok=True)
    print("Calculation times:")

    user_data, user_time = perf_counter(user_getter, USER_NAME)
    formatter("account data", user_time)

    repos, repos_time = perf_counter(
        graph_repos_stars, "repos", ["OWNER"]
    )
    formatter("repos", repos_time)

    followers, follower_time = perf_counter(follower_getter, USER_NAME)
    formatter("followers", follower_time)

    starred, starred_time = perf_counter(starred_getter, USER_NAME)
    formatter("starred", starred_time)

    repo_list, repo_list_time = perf_counter(
        graph_repos_stars, "repo_list", ["OWNER"]
    )
    formatter("repo_list", repo_list_time)

    (commits, additions, deletions), commit_time = perf_counter(commit_loc_getter, repo_list, USER_NAME)
    formatter("commits_loc", commit_time)

    stats = {
        "repos": int(repos),
        "contributed": int(user_data.get("repositoriesContributedTo", {}).get("totalCount", 0)),
        "stars": 0,
        "followers": int(followers),
        "starred": int(starred),
        "commits": int(commits),
        "additions": int(additions),
        "deletions": int(deletions),
        "fetched_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    STATS_FILE.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {STATS_FILE}: repos={stats['repos']} contributed={stats['contributed']} "
        f"stars={stats['stars']} followers={stats['followers']} "
        f"starred={stats['starred']} commits={stats['commits']} "
        f"additions={stats['additions']} deletions={stats['deletions']}"
    )

    refresh_cache_files()

    print("Total GitHub GraphQL API calls:", sum(QUERY_COUNT.values()))
    for funct_name, count in QUERY_COUNT.items():
        print(f"   {funct_name:<26} {count:>6}")
