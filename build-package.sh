#!/bin/bash

[ ! "${EUID}" = "0" ] && {
  echo "Execute esse script como root:"
  echo
  echo "  sudo ${0}"
  echo
  exit 1
}

HERE="$(dirname "$(readlink -f "${0}")")"

working_dir=$(mktemp -d)

mkdir -p "${working_dir}/usr/bin"
mkdir -p "${working_dir}/etc/xdg/autostart/"
mkdir -p "${working_dir}/DEBIAN/"
mkdir -p "${working_dir}/var/tiger-update/" 
mkdir -p "${working_dir}/usr/lib/tiger-os/"

cp -v "${HERE}/tiger-update"         "${working_dir}/usr/bin"
cp -v "${HERE}/tiger-update.desktop" "${working_dir}/etc/xdg/autostart/"
cp -v "${HERE}/banner.png"           "${working_dir}/usr/lib/tiger-os/"
cp -v "${HERE}/CURRENT"              "${working_dir}/var/tiger-update/version"

chmod +x "${working_dir}/usr/bin/tiger-update"

(
 echo "Package: feature-update-manager"
 echo "Priority: optional"
 echo "Version: $(date +%y.%m.%d%H%M%S)"
 echo "Architecture: all"
 echo "Maintainer: Natanael Barbosa Santos"
 echo "Depends: "
 echo "Description: Atualizador de recursos do Tiger OS"
 echo
) > "${working_dir}/DEBIAN/control"

dpkg -b ${working_dir}
rm -rfv ${working_dir}

mv "${working_dir}.deb" "${HERE}/feature-update-manager.deb"

chmod 777 "${HERE}/feature-update-manager.deb"
chmod -x  "${HERE}/feature-update-manager.deb"
