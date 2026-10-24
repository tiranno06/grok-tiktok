#!/usr/bin/env bash
# Installe ffmpeg sur la machine de GitHub. Les paquets téléchargés sont gardés dans ~/paquets-ffmpeg (mis en cache par
# GitHub d'un passage à l'autre) : une fois le cache rempli, plus aucun téléchargement depuis les serveurs d'Ubuntu, qui
# sont parfois très lents (le 24/10 : plus de 12 minutes, la fabrication s'est arrêtée).
set -u
if which ffmpeg >/dev/null 2>&1; then ffmpeg -version | head -1; exit 0; fi
D="$HOME/paquets-ffmpeg"
mkdir -p "$D/partial"
echo "paquets déjà en cache : $(ls "$D"/*.deb 2>/dev/null | wc -l)"
installer() {
  sudo apt-get install -y -q --no-install-recommends -o Dir::Cache::archives="$D" \
    -o APT::Keep-Downloaded-Packages=true ffmpeg
}
# d'abord sans tout remettre à jour (« apt-get update » peut prendre 10 minutes) ; mise à jour seulement si besoin
installer || (sudo apt-get update -q && installer)
sudo chown -R "$(id -u):$(id -g)" "$D"
rm -rf "$D/partial" "$D/lock"
ffmpeg -version | head -1
