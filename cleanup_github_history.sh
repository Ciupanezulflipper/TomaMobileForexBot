# ====== cleanup_github_history.sh ======
#!/bin/bash
set -e

# Ask for your PAT at runtime (won't be stored in the file)
read -sp "Enter your GitHub Personal Access Token (PAT): " PAT
echo ""
USER="Ciupanezulfipper"
REPO="TomaForexBot_Railway"

# 1) Fresh mirror clone
cd ~
rm -rf temp-repo.git
git clone --mirror "https://${USER}:${PAT}@github.com/${USER}/${REPO}.git" temp-repo.git
cd temp-repo.git

# 2) Remove leaked files from ALL history
pip install -q git-filter-repo
git filter-repo --invert-paths \
  --path bot.log.20250810234038 \
  --path telegrambot.py.save

# 3) Force-push cleaned history
git push --force --all
git push --force --tags

# Optional: confirm they’re gone
git log -- bot.log.20250810234038 telegrambot.py.save || true

# 4) Sync your working repo
cd ~/TomaMobileForexBot
git fetch --all
git checkout phaseA-stable && git reset --hard origin/phaseA-stable
git checkout phaseB-work  && git reset --hard origin/phaseB-work

echo "✅ GitHub history cleaned and working repo synced."
