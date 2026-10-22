#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION='0.1.0'
PACKAGE='mainuan-atualizador-recursos'
WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT
chmod 0755 "${WORKDIR}"

mkdir -p \
  "${WORKDIR}/DEBIAN" \
  "${WORKDIR}/usr/bin" \
  "${WORKDIR}/usr/lib/${PACKAGE}/mainuan_recursos" \
  "${WORKDIR}/usr/share/applications" \
  "${WORKDIR}/etc/xdg/autostart" \
  "${WORKDIR}/etc/mainuan" \
  "${ROOT}/dist"

install -m 0755 "${ROOT}/bin/mainuan-atualizador-recursos" "${WORKDIR}/usr/bin/"
install -m 0644 "${ROOT}/src/mainuan_recursos/"*.py "${WORKDIR}/usr/lib/${PACKAGE}/mainuan_recursos/"
install -m 0644 "${ROOT}/data/mainuan-atualizador-recursos.desktop" "${WORKDIR}/usr/share/applications/"
install -m 0644 "${ROOT}/data/mainuan-atualizador-recursos-autostart.desktop" \
  "${WORKDIR}/etc/xdg/autostart/mainuan-atualizador-recursos.desktop"
install -m 0644 "${ROOT}/data/atualizador-recursos.conf" "${WORKDIR}/etc/mainuan/"

cat > "${WORKDIR}/DEBIAN/control" <<EOF
Package: ${PACKAGE}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Maintainer: Projeto Mainuan
Depends: python3, python3-apt, python3-pyqt6, apt, pkexec
Description: Atualizador de recursos do Mainuan com interface Qt6
 Apresenta e instala atualizações de pacotes da distribuição por APT.
EOF
printf '/etc/mainuan/atualizador-recursos.conf\n' > "${WORKDIR}/DEBIAN/conffiles"
dpkg-deb --build --root-owner-group "${WORKDIR}" "${ROOT}/dist/${PACKAGE}_${VERSION}_all.deb"
echo "Pacote gerado: ${ROOT}/dist/${PACKAGE}_${VERSION}_all.deb"
