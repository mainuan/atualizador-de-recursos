#!/usr/bin/env bash
set -euo pipefail
umask 022
DEST="${1:?Informe o diretório de preparação}"
install -Dm755 bin/mainuan-atualizador-recursos "$DEST/usr/bin/mainuan-atualizador-recursos"
install -d "$DEST/usr/lib/mainuan-atualizador-recursos/mainuan_recursos"
install -m644 src/mainuan_recursos/*.py "$DEST/usr/lib/mainuan-atualizador-recursos/mainuan_recursos/"
install -Dm644 src/mainuan_recursos/assets/mainuan-novidades.png "$DEST/usr/lib/mainuan-atualizador-recursos/mainuan_recursos/assets/mainuan-novidades.png"
install -Dm644 data/org.mainuan.Recursos.desktop "$DEST/usr/share/applications/org.mainuan.Recursos.desktop"
install -Dm644 data/mainuan-recursos-autostart.desktop "$DEST/etc/xdg/autostart/mainuan-recursos.desktop"
install -Dm644 data/atualizador-recursos.json "$DEST/etc/mainuan/atualizador-recursos.json"
install -Dm644 data/mainuan-recursos.svg "$DEST/usr/share/icons/hicolor/scalable/apps/mainuan-recursos.svg"
install -d "$DEST/usr/share/doc/mainuan-atualizador-recursos/examples"
install -m644 README.md LICENSE "$DEST/usr/share/doc/mainuan-atualizador-recursos/"
install -m644 docs/*.md "$DEST/usr/share/doc/mainuan-atualizador-recursos/"
install -m644 examples/*.json "$DEST/usr/share/doc/mainuan-atualizador-recursos/examples/"
install -Dm644 data/man/mainuan-atualizador-recursos.1 "$DEST/usr/share/man/man1/mainuan-atualizador-recursos.1"

gzip -n -9 -c debian/changelog > "$DEST/usr/share/doc/mainuan-atualizador-recursos/changelog.gz"
gzip -n -9 "$DEST/usr/share/man/man1/mainuan-atualizador-recursos.1"
