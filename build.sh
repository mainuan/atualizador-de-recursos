#!/usr/bin/env bash

working_dir=$(mktemp -d)
repo_dir=${PWD}

(
  cd "${working_dir}"
  
  while read package; do
    echo "${package}" | grep "^https://" && {
      url="${package}"
      package=$(basename "${package}")
      
      wget "${url}"
      dpkg -x "${package}" .
      rm "${package}"
    } || {
      wget "https://github.com/Tiger-OperatingSystem/${package}/releases/download/continuous/${package}.deb"
      dpkg -x "${package}.deb" .
      rm "${package}.deb"
    }
  done < "${repo_dir}/packages.txt"


  mkdir -p var/tiger-update/
  date +%y.%m.%d%H%M%S > var/tiger-update/version

  tar -cvf ../update-pack.tar.gz ./*
  chmod 777 ../update-pack.tar.gz
  
  rm index.html
)

mv /tmp/update-pack.tar.gz tiger-update-package.tgz
cp "${working_dir}/var/tiger-update/version" CURRENT

# sudo tar --same-permissions --same-owner -xzvf tiger-update-package.tgz -C /


