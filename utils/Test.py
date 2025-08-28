import os

# --- Import your function ---
from crawl_github_files import crawl_github_files  # Change 'your_crawler_file' to the .py file containing your code

# --- Set up the Github repo and token ---
# For public repo, token is optional. If you want, set your GITHUB_TOKEN env var.
github_token = os.environ.get("GITHUB_TOKEN")  # Reads from env if present (recommended for larger repos/private access).

# Pick a public repo for demonstration (can be changed to any repo)
repo_url = "https://github.com/Gouravyadav00/YTomic-Agentic-Ai"

# --- Run crawler ---
result = crawl_github_files(
    repo_url,
    token=github_token,            # None is fine for most public repos.
    max_file_size=50000,           # 50 KB; adjust as needed.
    use_relative_paths=True,
    include_patterns={"*.py", "*.md"},  # Only Python and Markdown files.
    exclude_patterns={"*test*", "*tests/*"},  # Skip test files.
)

# --- Print results summary ---
files = result["files"]
stats = result["stats"]
print(f"\nDownloaded {stats['downloaded_count']} files.")
print(f"Skipped {stats['skipped_count']} files due to size limits or patterns.\n")
print("Files fetched:")
for file_path in sorted(files.keys()):
    print(f"  {file_path}")

# Show a preview of the first fetched file
if files:
    sample_file = next(iter(files))
    print(f"\nSample file: {sample_file}")
    print("Content preview:")
    print(files[sample_file][:300])
else:
    print("No files downloaded. Check include/exclude patterns.")
