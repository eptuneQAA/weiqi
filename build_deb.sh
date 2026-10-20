#!/bin/sh
set -eu

cd "$(dirname "$0")"

VERSION=$(dpkg-parsechangelog -S Version)

rm -rf dist
mkdir -p dist

dpkg-buildpackage -us -uc -b

for path in "../weiqi_${VERSION}_all.deb" \
            ../weiqi_${VERSION}_*.buildinfo \
            ../weiqi_${VERSION}_*.changes; do
    if [ -e "$path" ]; then
        mv "$path" dist/
    fi
done

fakeroot debian/rules clean

echo "已生成安装包：$(pwd)/dist/weiqi_${VERSION}_all.deb"
