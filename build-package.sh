#!/usr/bin/env bash
# Construção local sem instalar pacotes e sem privilégios administrativos.
set -euo pipefail
umask 022
cd "$(dirname "$(readlink -f "$0")")"
PACKAGE=mainuan-atualizador-recursos
VERSION="$(dpkg-parsechangelog -S Version)"
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
bash tools/stage-package.sh "$STAGING"
mkdir -p "$STAGING/DEBIAN" dist
sed -n '/^Package: /,$p' debian/control | sed 's/${misc:Depends}, //g' > "$STAGING/DEBIAN/control"
printf 'Version: %s\nSection: utils\nPriority: optional\nMaintainer: Mainuan Packaging <openwebosbr@gmail.com>\n' "$VERSION" >> "$STAGING/DEBIAN/control"
printf '/etc/mainuan/atualizador-recursos.json\n/etc/xdg/autostart/mainuan-recursos.desktop\n' > "$STAGING/DEBIAN/conffiles"
install -m644 debian/copyright "$STAGING/usr/share/doc/$PACKAGE/copyright"
chmod 0755 "$STAGING"
dpkg-deb --build --root-owner-group "$STAGING" "dist/${PACKAGE}_${VERSION}_all.deb"
